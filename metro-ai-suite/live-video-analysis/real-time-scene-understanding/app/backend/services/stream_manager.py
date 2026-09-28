# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""PyAV-based RTSP relay into MediaMTX for WebRTC rendering.

Each :class:`StreamManager` owns one video source. A single dedicated daemon
thread (``_stream_loop``) opens the source with PyAV *once* and, per demuxed
packet, does up to two jobs on that one connection:

* decode, downscale (to the same benchmarked dimensions used for segment
  recording), and re-encode into MediaMTX over RTSP, which then serves the
  stream to the browser over WebRTC (WHEP) for low-latency playback; and
* decode (the same pass) for segment writing, frame registration, and VLM
  inference handoff.

Both jobs share one input connection, one decode pass per frame, one scale
pass per frame, and one reconnect/backoff timeline instead of opening the
source twice, halving the load placed on the camera and avoiding two
independent, potentially out-of-sync reconnect cycles. The relay is
re-encoded rather than stream-copied so the browser never has to pull the
full source resolution (e.g. 1080p) just to render a live preview — it's
downscaled proportionally using the same ``_calculate_scaled_dimensions``
logic segment recording uses, which trades a modest amount of decode/encode
CPU for a large cut in relay bandwidth.
"""

from __future__ import annotations

import errno
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Optional

import av

from ..config import settings
from .deep_analyzer import get_deep_analyzer
from .frame_registry import FrameRecord
from .frame_registry import SegmentFrameRegistry
from .vlm import get_vlm_engine
from .vlm import parse_yes_no

logger = logging.getLogger(__name__)

# Area-averaging gives better downscale quality than the default bilinear;
# fall back for older PyAV/ffmpeg builds that don't expose it.
_REFORMAT_INTERPOLATION = getattr(
    av.video.reformatter.Interpolation, "AREA", av.video.reformatter.Interpolation.BILINEAR
)

_ENCODE_PIX_FMT = "yuv420p"
_ENCODER = "libx264"

# x264 defaults to the "medium" preset, which is far more CPU than a rolling
# on-disk buffer needs. "veryfast" cuts encode time several-fold at a small
# size/quality cost; set it back to "medium" if archival quality matters more
# than throughput.
_SEGMENT_X264_OPTIONS = {"preset": "veryfast"}

# The relay feeds a live WebRTC preview, so latency matters more than size:
# zerolatency drops B-frames and lookahead, which removes the reorder delay
# between a frame arriving and the browser being able to show it.
_RELAY_X264_OPTIONS = {"preset": "veryfast", "tune": "zerolatency"}

# A WHEP viewer can only start decoding at an IDR. x264's default keyint of 250
# frames would make a new browser tab wait ~8s at 30fps before showing a
# picture; 2s of keyframe interval trades a little bitrate for a fast join.
_RELAY_KEYFRAME_SECONDS = 2.0
_RELAY_FALLBACK_GOP = 50  # used when the source reports no usable frame rate

# health.last_packet_ts is liveness telemetry, not a timestamp anyone diffs at
# sub-second precision — updating it 4x/s instead of once per packet removes a
# lock acquisition from the per-packet path.
_HEALTH_TS_INTERVAL = 0.25
_CAPTION_HISTORY_LIMIT = 3

_MAX_MUX_EINVAL = 30
_MAX_BACKWARD_DTS = 10
_PACING_RESET_LAG = 1.0  # seconds behind real time before the clock is re-based


def _close_quietly(container) -> None:
    """Close a container, swallowing teardown errors."""
    if container is not None:
        try:
            container.close()
        except Exception:  # noqa: BLE001
            pass


def _encode_frame_jpeg_bytes(frame, *, max_width: int = 160) -> bytes:
    """Encode an RGB24 frame ndarray as a small JPEG thumbnail byte string."""
    if frame is None:
        return b""

    src = av.VideoFrame.from_ndarray(frame, format="rgb24")
    src_w = int(src.width)
    src_h = int(src.height)
    if src_w <= 0 or src_h <= 0:
        return b""

    target_w = min(max_width, src_w)
    target_h = max(1, int(round(target_w * src_h / src_w)))
    resized = src.reformat(width=target_w, height=target_h, format="yuv420p")

    codec = av.CodecContext.create("mjpeg", "w")
    codec.width = resized.width
    codec.height = resized.height
    codec.pix_fmt = "yuvj420p"
    codec.open()

    packets = list(codec.encode(resized))
    packets.extend(codec.encode(None))
    jpeg_bytes = b"".join(bytes(packet) for packet in packets)
    if not jpeg_bytes:
        return b""
    return jpeg_bytes


@dataclass
class StreamHealth:
    """Runtime snapshot for one stream."""

    publishing: bool = False
    resolution: Optional[str] = None  # published (downscaled) size, e.g. "640x360"
    codec: Optional[str] = None  # published codec, always h264 for WebRTC
    reconnect_count: int = 0
    last_packet_ts: Optional[float] = None  # monotonic
    caption: Optional[str] = None
    caption_history: list[dict[str, Any]] = field(default_factory=list)
    caption_ts: Optional[float] = None  # wall clock (epoch seconds)
    ttft_ms: Optional[float] = None
    tpot_ms: Optional[float] = None
    throughput_tps: Optional[float] = None
    total_tokens_generated: Optional[float] = None


class _SegmentCtx:
    """Per-connection segment-writer state, resolved once at connect time.

    Holds *bound methods* rather than objects so the frame loop can call
    ``encode``/``mux`` without walking an attribute chain on every decoded
    frame.
    """

    __slots__ = ("container", "encode", "mux", "avg_fps", "sample_every")


class StreamManager:
    """Relay a single video source into MediaMTX with PyAV."""

    def __init__(
        self,
        stream_id: str,
        source_url: str,
        vlm_prompt: str = "",
        deep_analyzer_prompt: str = "",
        alert_event: str = "",
        frame_registry: Optional[SegmentFrameRegistry] = None,
    ):
        self.stream_id = stream_id
        self.source_url = source_url
        self.vlm_prompt = str(vlm_prompt or "").strip()
        self.deep_analyzer_prompt = str(deep_analyzer_prompt or "").strip()
        self.alert_event = " ".join(str(alert_event or "").strip().split())
        self.target_url = f"{settings.WEBRTC_RELAY_URL.rstrip('/')}/{stream_id}"

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._infer_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.health = StreamHealth()

        # Latest sampled frame handed from the segment loop to the inference worker.
        self._frame_lock = threading.Lock()
        # Signalled whenever a fresh frame is published, so the inference worker
        # can block instead of polling.
        self._frame_event = threading.Event()
        self._latest_frame = None  # np.ndarray (H×W×3, RGB) or None
        self._latest_frame_ts: float = 0.0  # monotonic; 0 = no frame yet
        self._latest_frame_id: Optional[uuid.UUID] = None  # ties back to the registered FrameRecord
        self._caption_history: deque[dict[str, Any]] = deque(maxlen=_CAPTION_HISTORY_LIMIT)
        self._playback_start_ts: float = 0.0

        # Segment writer + frame metadata registry (deep-analysis handoff).
        self.frame_registry = frame_registry
        self._segment_output_pattern = str(
            Path(settings.SEGMENT_OUTPUT_DIR) / f"{stream_id}_segment_%04d.mp4"
        )
        self._finalized_segments: list[str] = []  # oldest-first; reclaimed past SEGMENT_MAX_ON_DISK

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the relay thread and the inference worker when a prompt is set."""
        if self._running:
            return
        self._running = True
        self._playback_start_ts = time.monotonic()
        self._caption_history.clear()
        self._frame_event.clear()

        if self.frame_registry is not None:
            Path(settings.SEGMENT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(
            target=self._stream_loop,
            daemon=True,
            name=f"stream-{self.stream_id}",
        )
        self._thread.start()
        logger.info(
            "Started stream loop '%s' (%s -> %s, segments=%s)",
            self.stream_id,
            self.source_url,
            self.target_url,
            self.frame_registry is not None,
        )

        if self.vlm_prompt:
            self._infer_thread = threading.Thread(
                target=self._infer_worker,
                daemon=True,
                name=f"infer-{self.stream_id}",
            )
            self._infer_thread.start()
            logger.info("Started VLM inference for '%s'", self.stream_id)
        else:
            logger.info(
                "VLM prompt not set for '%s' — captions disabled until stream is re-added with a prompt",
                self.stream_id,
            )

    def stop(self) -> None:
        """Stop the relay and inference threads, waiting for them to exit."""
        self._running = False
        self._frame_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        if self._infer_thread:
            self._infer_thread.join(timeout=5.0)
        with self._lock:
            self.health.publishing = False
        logger.info("Stopped relay '%s'", self.stream_id)

    # ------------------------------------------------------------------ #
    # Consumers
    # ------------------------------------------------------------------ #

    def get_health(self) -> StreamHealth:
        """Return a snapshot of the stream's current health state."""
        with self._lock:
            return StreamHealth(
                publishing=self.health.publishing,
                resolution=self.health.resolution,
                codec=self.health.codec,
                reconnect_count=self.health.reconnect_count,
                last_packet_ts=self.health.last_packet_ts,
                caption=self.health.caption,
                caption_history=[dict(entry) for entry in self.health.caption_history],
                caption_ts=self.health.caption_ts,
                ttft_ms=self.health.ttft_ms,
                tpot_ms=self.health.tpot_ms,
                throughput_tps=self.health.throughput_tps,
                total_tokens_generated=self.health.total_tokens_generated,
            )

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _input_options(self) -> dict:
        if str(self.source_url).startswith(("rtsp://", "rtsps://")):
            return {
                "rtsp_transport": "tcp",
                "fflags": "nobuffer",
                "flags": "low_delay",
            }
        return {}

    @staticmethod
    def _source_fps(in_stream) -> float:
        """Best-effort source frame rate; 0.0 when the source doesn't report one."""
        try:
            return float(in_stream.average_rate or 0.0)
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------ #
    # Connection setup (runs once per connect — cost here is irrelevant, so it
    # is optimised for clarity and keeps the packet loop short enough to read)
    # ------------------------------------------------------------------ #

    def _open_relay(self, in_stream, width: int, height: int):
        """Open the MediaMTX output as a downscaled H.264 encode.

        Returns ``(container, encode, mux)`` — bound methods, so the frame loop
        doesn't re-resolve them per frame. Failures propagate: a relay that
        cannot be opened must trigger the shared reconnect/backoff path.
        """
        output = av.open(
            self.target_url,
            mode="w",
            format="rtsp",
            options={"rtsp_transport": "tcp"},
        )
        out_stream = output.add_stream(
            _ENCODER, rate=in_stream.average_rate, options=_RELAY_X264_OPTIONS
        )
        out_stream.width = width
        out_stream.height = height
        out_stream.pix_fmt = _ENCODE_PIX_FMT
        out_stream.thread_type = "AUTO"
        # thread_type alone leaves thread_count at 1; 0 lets x264 pick a count
        # from the host CPU.
        out_stream.thread_count = 0

        fps = self._source_fps(in_stream)
        out_stream.gop_size = (
            max(1, int(fps * _RELAY_KEYFRAME_SECONDS)) if fps else _RELAY_FALLBACK_GOP
        )

        with self._lock:
            self.health.publishing = True
            # Report what subscribers actually receive, not what the camera sends.
            self.health.codec = "h264"
            self.health.resolution = f"{width}x{height}"
        logger.info(
            "Relay '%s' publishing %dx%d h264 to MediaMTX (gop=%d)",
            self.stream_id,
            width,
            height,
            out_stream.gop_size,
        )
        return output, out_stream.encode, output.mux

    def _open_segment_writer(
        self, in_stream, width: int, height: int, *, start_number: int = 0
    ) -> Optional[_SegmentCtx]:
        """Open the segment muxer/encoder, or return ``None`` on failure.

        Segment writing is independent of the relay: a bad segments directory
        (or any other setup failure) must not tear down an otherwise-healthy
        relay connection, so this never raises — it logs and returns ``None``,
        and the caller retries on the next reconnect.
        """
        container = None
        try:
            container = av.open(
                self._segment_output_pattern,
                mode="w",
                format="stream_segment",
                options={
                    "segment_time": str(settings.SEGMENT_TIME_SECONDS),
                    "segment_start_number": str(start_number),
                    "reset_timestamps": "1",
                },
            )
            out_stream = container.add_stream(
                _ENCODER, rate=in_stream.average_rate, options=_SEGMENT_X264_OPTIONS
            )
            out_stream.width = width
            out_stream.height = height
            out_stream.pix_fmt = _ENCODE_PIX_FMT
            out_stream.thread_type = "AUTO"
            out_stream.thread_count = 0

            avg_fps = self._source_fps(in_stream)

            ctx = _SegmentCtx()
            ctx.container = container
            ctx.encode = out_stream.encode
            ctx.mux = container.mux
            ctx.avg_fps = avg_fps
            ctx.sample_every = max(1, int(avg_fps / settings.FRAME_SAMPLE_FPS)) if avg_fps else 1
            return ctx
        except Exception as exc:  # noqa: BLE001 - e.g. permission/disk errors
            logger.warning(
                "[%s] segment writer setup failed, continuing without segments this "
                "connection (will retry next reconnect): %s",
                self.stream_id,
                exc,
            )
            _close_quietly(container)
            return None

    def _stream_loop(self) -> None:
        """Single connection driving both the MediaMTX relay and segment/VLM sampling.

        Opens the source exactly once per (re)connect attempt and, per demuxed
        packet: decodes it once, downscales each frame once, then feeds that
        frame to whichever consumers are active — the MediaMTX relay encoder
        (if relaying is enabled) and the segment writer / frame registry / VLM
        handoff (if a ``frame_registry`` was supplied). Both consumers share
        one reconnect and backoff timeline.

        Because the relay is re-encoded rather than stream-copied, decoding
        happens whenever *either* job is enabled — there is no zero-decode
        path. The cost per stream is one decode plus up to two encodes at the
        downscaled resolution; the benefit is that browsers pull a preview-
        sized stream instead of the full source, and that the published codec
        is always H.264 regardless of what the camera speaks (H.265 sources
        would otherwise be undecodable in most browsers).

        Trade-off of sharing one connection: relay-side failures (a persistent
        mux error, or the input connection itself dropping) do reconnect
        segment writing too, since both read from the same demux loop.
        Segment-writer-side failures (e.g. a bad segments directory/disk
        error) are isolated and do *not* tear down a healthy relay — they
        just disable segment writing until the next reconnect attempt.

        Segment writing never stops on its own: SEGMENT_MAX_ON_DISK caps disk
        usage as a rolling buffer (oldest finalized segment deleted once the
        count is exceeded, see ``_reclaim_old_segments``), not a hard limit on
        writer lifetime.

        Performance notes: everything invariant for the lifetime of a
        connection — settings, bound methods, the float form of the stream
        time base, the segment-path prefix/suffix — is resolved before the
        packet loop and read from locals inside it. The only work left per
        packet is demux/decode; the only work left per frame is one scale plus
        the active encodes.
        """
        do_relay = settings.WEBRTC_AUTO_PUBLISH
        do_segment = self.frame_registry is not None
        if not do_relay and not do_segment:
            logger.info(
                "WEBRTC_AUTO_PUBLISH disabled and no frame registry configured — stream '%s' idle",
                self.stream_id,
            )
            return

        is_rtsp = str(self.source_url).startswith(("rtsp://", "rtsps://"))
        pace_playback = do_relay and not is_rtsp
        vlm_active = do_segment and bool(self.vlm_prompt)

        # Hoist settings lookups, bound methods and globals into locals: these
        # are read once per frame otherwise, and Python resolves each one at
        # runtime through a dict.
        vlm_interval = settings.ALERT_VLM_INTERVAL
        seg_seconds = settings.SEGMENT_TIME_SECONDS
        rtsp_timeout = settings.RTSP_TIMEOUT
        stream_id = self.stream_id
        source_url = self.source_url
        register = self.frame_registry.register if do_segment else None
        frame_event = self._frame_event
        frame_lock = self._frame_lock
        health_lock = self._lock
        monotonic = time.monotonic
        sleep = time.sleep
        new_uuid = uuid.uuid4

        # Segment paths only change when the segment index does, so split the
        # pattern once instead of running str.replace() per frame.
        pattern_head, _, pattern_tail = self._segment_output_pattern.partition("%04d")

        last_vlm_sample = 0.0
        last_segment_idx = -1
        last_segment_path: Optional[str] = None

        backoff = 1.0
        max_backoff = 20.0

        while self._running:
            input_container = None
            relay_output = None
            segment_output = None
            relay_encode = None
            relay_mux = None
            seg = None
            try:
                input_container = av.open(
                    source_url,
                    options=self._input_options(),
                    timeout=rtsp_timeout,
                )
                in_stream = input_container.streams.video[0]
                in_stream.thread_type = "AUTO"
                in_stream.thread_count = 0  # 0 = auto; PyAV's default of 1 serialises decode

                time_base = float(in_stream.time_base)
                new_width, new_height = _calculate_scaled_dimensions(
                    in_stream.width, in_stream.height
                )
                logger.info(
                    "[%s] source=%dx%d (aspect=%.4f) -> encode=%dx%d",
                    stream_id,
                    in_stream.width,
                    in_stream.height,
                    in_stream.width / in_stream.height,
                    new_width,
                    new_height,
                )
                reformat = av.video.reformatter.VideoReformatter().reformat

                if do_relay:
                    relay_output, relay_encode, relay_mux = self._open_relay(
                        in_stream, new_width, new_height
                    )

                encode = seg_mux = None
                avg_fps = sample_every = None
                if do_segment:
                    seg = self._open_segment_writer(in_stream, new_width, new_height)
                    if seg is not None:
                        segment_output = seg.container
                        encode = seg.encode
                        seg_mux = seg.mux
                        avg_fps = seg.avg_fps
                        sample_every = seg.sample_every

                backoff = 1.0
                frame_count = 0
                last_dts = None
                mux_errors = 0
                backward = 0
                next_health_ts = 0.0
                pacing_deadline = None
                # Segment rotation is detected from wall-clock elapsed time
                # rather than the source's own PTS: many RTSP cameras emit
                # unreliable/flat presentation timestamps, which would leave
                # ``segment_idx`` stuck and the deep analyzer's finalize
                # signal never fired (see _notify_segment_finalized). Wall
                # clock tracks ffmpeg's own real-time ``segment_time``-based
                # rotation of the on-disk file closely enough for a live
                # source, regardless of what the camera reports as PTS.
                connect_monotonic_ts = monotonic()
                segment_number_offset = 0

                for packet in input_container.demux(in_stream):
                    if not self._running:
                        break
                    dts = packet.dts
                    if dts is None:
                        continue  # skip non-timed packets (e.g. header flushes)

                    # Cameras occasionally emit backward/duplicate timestamps,
                    # which produce out-of-order frames and upset both encoders.
                    # Drop them here instead of tearing the whole session down.
                    # If the clock genuinely reset (many backward in a row),
                    # adopt the new timeline rather than dropping frames
                    # forever. Applying this once, before decode, keeps the
                    # relay and the segment/VLM frames on the same deduped
                    # timeline.
                    if last_dts is not None and dts <= last_dts:
                        backward += 1
                        if backward <= _MAX_BACKWARD_DTS:
                            continue
                    backward = 0
                    last_dts = dts

                    decoded_frames = packet.decode()

                    now = monotonic()
                    if now >= next_health_ts:
                        next_health_ts = now + _HEALTH_TS_INTERVAL
                        with health_lock:
                            self.health.last_packet_ts = now

                    for frame in decoded_frames:
                        frame_count += 1

                        # One scale pass feeds every consumer. The pixel-format
                        # conversion is folded in: the encoders would otherwise
                        # each convert to yuv420p in a second full-frame pass.
                        if (
                            frame.width != new_width
                            or frame.height != new_height
                            or frame.format.name != _ENCODE_PIX_FMT
                        ):
                            frame = reformat(
                                frame,
                                width=new_width,
                                height=new_height,
                                format=_ENCODE_PIX_FMT,
                                interpolation=_REFORMAT_INTERPOLATION,
                            )

                        if do_relay:
                            try:
                                relay_mux(relay_encode(frame))
                                mux_errors = 0
                            except av.error.FFmpegError as exc:
                                if exc.errno == errno.EINVAL and mux_errors < _MAX_MUX_EINVAL:
                                    mux_errors += 1  # skip the bad frame, keep publishing
                                else:
                                    raise  # persistent/other error → reconnect

                        if seg is None:
                            continue

                        pts = frame.pts
                        pts_seconds = (
                            pts * time_base if pts is not None else frame_count / avg_fps
                        )
                        # Rotation itself is driven by wall-clock elapsed time
                        # (see comment above ``connect_monotonic_ts``); source
                        # PTS is still reported/logged but no longer trusted
                        # to decide when a segment has rolled over.
                        segment_idx = (
                            int((monotonic() - connect_monotonic_ts) / seg_seconds)
                            + segment_number_offset
                        )

                        if segment_idx != last_segment_idx:
                            if last_segment_path is not None:
                                self._reclaim_old_segments(last_segment_path)
                                self._notify_segment_finalized(last_segment_path)
                            last_segment_idx = segment_idx
                            last_segment_path = (
                                f"{pattern_head}{segment_idx:04d}{pattern_tail}"
                            )

                        if frame_count % sample_every == 0:
                            frame_id = new_uuid()
                            register(
                                FrameRecord(
                                    frame_id=frame_id,
                                    stream_id=stream_id,
                                    rtsp_url=source_url,
                                    segment_path=last_segment_path,
                                    pts_seconds=pts_seconds,
                                )
                            )
                            logger.info(
                                "[%s] registered frame_id=%s segment=%s pts=%.2fs",
                                stream_id,
                                frame_id,
                                last_segment_path,
                                pts_seconds,
                            )

                            if vlm_active:
                                now = monotonic()
                                if now - last_vlm_sample >= vlm_interval:
                                    last_vlm_sample = now
                                    # to_ndarray copies a full frame — do it
                                    # outside the lock so the inference worker
                                    # is never blocked on a memcpy. Publishing
                                    # is a pointer swap; the worker only ever
                                    # reads the array it was handed, so the
                                    # buffer is never mutated underneath it.
                                    rgb = frame.to_ndarray(format="rgb24")
                                    with frame_lock:
                                        self._latest_frame = rgb
                                        self._latest_frame_ts = now
                                        self._latest_frame_id = frame_id
                                    frame_event.set()
                                    logger.info(
                                        "[%s] handed frame_id=%s to VLM inference worker",
                                        stream_id,
                                        frame_id,
                                    )

                        try:
                            seg_mux(encode(frame))  # mux() accepts the packet list directly
                        except Exception as exc:  # noqa: BLE001 - keep relay alive
                            logger.warning(
                                "[%s] segment encode/mux failed, reopening segment writer "
                                "at segment %04d: %s",
                                stream_id,
                                max(last_segment_idx + 1, segment_idx + 1),
                                exc,
                            )
                            _close_quietly(segment_output)
                            segment_output = None
                            seg = self._open_segment_writer(
                                in_stream,
                                new_width,
                                new_height,
                                start_number=max(last_segment_idx + 1, segment_idx + 1),
                            )
                            if seg is None:
                                logger.error(
                                    "[%s] segment writer recovery failed; "
                                    "segments disabled until reconnect",
                                    stream_id,
                                )
                            else:
                                segment_output = seg.container
                                encode = seg.encode
                                seg_mux = seg.mux
                                segment_number_offset += 1
                                last_segment_idx = segment_idx + 1
                                last_segment_path = (
                                    f"{pattern_head}{last_segment_idx:04d}{pattern_tail}"
                                )

                    # Local files have no wall-clock pacing; play at real time.
                    # Pace against a running deadline rather than sleeping a full
                    # packet duration each time, so the cost of decode/encode
                    # doesn't accumulate as drift.
                    if pace_playback and packet.duration:
                        span = packet.duration * time_base
                        pacing_deadline = (
                            now + span if pacing_deadline is None else pacing_deadline + span
                        )
                        delay = pacing_deadline - monotonic()
                        if delay > 0:
                            sleep(delay)
                        elif delay < -_PACING_RESET_LAG:
                            pacing_deadline = monotonic()  # can't keep up; re-base

                # Flush both encoders on a clean exit so trailing frames aren't lost.
                if seg is not None:
                    try:
                        seg_mux(encode(None))
                    except Exception as exc:  # noqa: BLE001 - best-effort flush
                        logger.warning(
                            "[%s] segment writer final flush failed: %s", stream_id, exc
                        )
                if relay_encode is not None:
                    try:
                        relay_mux(relay_encode(None))
                    except Exception as exc:  # noqa: BLE001 - best-effort flush
                        logger.warning("[%s] relay final flush failed: %s", stream_id, exc)

            except av.error.FFmpegError as exc:
                logger.warning("[%s] PyAV stream error: %s", stream_id, exc)
            except Exception as exc:  # noqa: BLE001 - keep the loop resilient
                logger.warning("[%s] stream loop error: %s", stream_id, exc)
            finally:
                _close_quietly(relay_output)
                _close_quietly(segment_output)
                _close_quietly(input_container)

            if not self._running:
                break

            with health_lock:
                if do_relay:
                    self.health.publishing = False
                self.health.reconnect_count += 1
            logger.info("[%s] reconnecting stream in %.0fs ...", stream_id, backoff)
            sleep(backoff)
            backoff = min(backoff * 1.5, max_backoff)

        logger.info("Stream loop exited for stream '%s'", stream_id)

    def _infer_worker(self) -> None:
        """Caption the most recent sampled frame, off the packet-draining path.

        The VLM ``generate`` call blocks for seconds on CPU; running it here
        instead of inside the sampler keeps the source socket drained the whole
        time, so inference bursts never stall the relay.

        Waits on an event rather than polling: no idle wakeups, and inference
        starts the instant the sampler publishes a frame instead of up to one
        poll interval later.
        """
        try:
            engine = get_vlm_engine()
        except Exception as exc:  # noqa: BLE001 - model may be missing/misconfigured
            logger.error("[%s] VLM disabled: %s", self.stream_id, exc)
            return

        stream_id = self.stream_id
        caption_with_metrics = engine.caption_with_metrics
        prompt = self.vlm_prompt
        deep_prompt = self.deep_analyzer_prompt
        alert_context = self.alert_event or prompt
        priority = bool(prompt)
        deep_enabled = settings.DEEP_ANALYZER_ENABLED and bool(prompt)
        get_segment = self.frame_registry.get_segment if self.frame_registry else None
        frame_event = self._frame_event
        frame_lock = self._frame_lock
        health_lock = self._lock

        processed_ts = 0.0
        while self._running:
            # Bounded wait so shutdown is still observed even if nothing signals;
            # clear before reading so a frame published mid-inference is never missed.
            if not frame_event.wait(0.5):
                continue
            frame_event.clear()

            with frame_lock:
                frame = self._latest_frame
                frame_ts = self._latest_frame_ts
                frame_id = self._latest_frame_id

            if frame is None or frame_ts == processed_ts:
                continue  # nothing new to caption yet
            processed_ts = frame_ts
            logger.info("[%s] VLM inferencing on frame_id=%s", stream_id, frame_id)

            try:
                caption, metrics = caption_with_metrics(
                    frame, prompt=prompt, priority=priority
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] VLM inference error: %s", stream_id, exc)
                continue

            if caption is None:
                logger.warning(
                    "[%s] dropping truncated/malformed VLM response for frame_id=%s",
                    stream_id,
                    frame_id,
                )
                continue

            logger.info(
                "[%s] VLM inference done for frame_id=%s: %s",
                stream_id,
                frame_id,
                caption.replace("\n", " | "),
            )

            # Resolve everything before taking the lock so the health lock is
            # held for assignments only — API readers contend on it.
            caption_ts = time.time()
            playback_seconds = max(0.0, frame_ts - self._playback_start_ts)
            ttft_ms = metrics.get("ttft_ms")
            tpot_ms = metrics.get("tpot_ms")
            throughput_tps = metrics.get("throughput_tps")
            total_tokens_generated = metrics.get("total_tokens_generated")
            with health_lock:
                self._caption_history.appendleft(
                    {
                        "response": caption,
                        "playback_seconds": playback_seconds,
                    }
                )
                self.health.caption = caption
                self.health.caption_history = list(self._caption_history)
                self.health.caption_ts = caption_ts
                if ttft_ms is not None:
                    self.health.ttft_ms = ttft_ms
                if tpot_ms is not None:
                    self.health.tpot_ms = tpot_ms
                if throughput_tps is not None:
                    self.health.throughput_tps = throughput_tps
                if total_tokens_generated is not None:
                    self.health.total_tokens_generated = total_tokens_generated
            logger.debug("[%s] caption: %s", stream_id, caption)

            if deep_enabled and frame_id is not None and parse_yes_no(caption):
                segment_path = get_segment(frame_id) if get_segment else None
                if segment_path:
                    trigger_thumbnail_jpeg = b""
                    try:
                        trigger_thumbnail_jpeg = _encode_frame_jpeg_bytes(frame)
                    except Exception as exc:  # noqa: BLE001 - best effort for sidecar enrichment
                        logger.warning(
                            "[%s] failed to encode trigger frame for frame_id=%s: %s",
                            stream_id,
                            frame_id,
                            exc,
                        )
                    try:
                        get_deep_analyzer().submit(
                            stream_id=stream_id,
                            segment_path=segment_path,
                            alert_event=alert_context,
                            deep_prompt=deep_prompt,
                            frame_id=frame_id,
                            trigger_caption=caption,
                            trigger_thumbnail_jpeg=trigger_thumbnail_jpeg,
                        )
                    except Exception as exc:  # noqa: BLE001 - model may be missing/misconfigured
                        logger.error("[%s] deep analyzer disabled: %s", stream_id, exc)
                else:
                    logger.warning(
                        "[%s] 'Yes' verdict for frame_id=%s but no segment on record",
                        stream_id,
                        frame_id,
                    )

        logger.info("Inference worker exited for stream '%s'", stream_id)

    def _reclaim_old_segments(self, finalized_segment_path: str) -> None:
        """Roll the per-stream segment buffer: drop the oldest once over SEGMENT_MAX_ON_DISK.

        This is what makes SEGMENT_MAX_ON_DISK a rolling buffer rather than a hard
        stop — every time a segment finalizes, the oldest surviving segment
        is deleted once the retained count exceeds SEGMENT_MAX_ON_DISK, so the
        writer keeps running indefinitely while disk usage stays bounded.
        Only ever called with a segment that has already rotated out (never
        the one ``ffmpeg`` is still writing), so this can't delete an open file.

        Segments the deep analyzer still has a pending/queued/in-flight job
        for are skipped (left in the buffer for the next pass) rather than
        deleted: if that dispatch thread is backed up, deleting on a pure
        rotation-count basis would pull the file out from under a job that
        hasn't run yet (a real "SEGMENT MISSED" case). This can let the
        buffer temporarily exceed SEGMENT_MAX_ON_DISK while a backlog is
        being worked through; it self-corrects once analysis catches up.
        """
        if not settings.SEGMENT_MAX_ON_DISK:
            return
        self._finalized_segments.append(finalized_segment_path)
        excess = len(self._finalized_segments) - settings.SEGMENT_MAX_ON_DISK
        if excess <= 0:
            return
        survivors = []
        deleted = 0
        for path in self._finalized_segments:
            if deleted >= excess or self._segment_reserved(path):
                survivors.append(path)
                continue
            self._delete_segment(path)
            deleted += 1
        self._finalized_segments = survivors

    def _segment_reserved(self, segment_path: str) -> bool:
        """Whether the deep analyzer still needs `segment_path` on disk."""
        if not settings.DEEP_ANALYZER_ENABLED:
            return False
        try:
            return get_deep_analyzer().is_segment_active(segment_path)
        except Exception:  # noqa: BLE001 - model may be missing/misconfigured
            return False

    def _notify_segment_finalized(self, finalized_segment_path: str) -> None:
        """Tell the deep analyzer this segment has rotated out and is safe to read."""
        if not settings.DEEP_ANALYZER_ENABLED:
            return

        try:
            get_deep_analyzer().on_segment_finalized(finalized_segment_path)
        except Exception as exc:  # noqa: BLE001 - model may be missing/misconfigured
            logger.error("[%s] deep analyzer disabled: %s", self.stream_id, exc)

    def _delete_segment(self, segment_path: str) -> None:
        try:
            Path(segment_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("[%s] failed to delete segment %s: %s", self.stream_id, segment_path, exc)
            return
        removed = self.frame_registry.remove_segment(self.stream_id, segment_path) if self.frame_registry else 0
        logger.info(
            "[%s] reclaimed segment=%s (removed %d registry entries)",
            self.stream_id,
            segment_path,
            removed,
        )


def _calculate_scaled_dimensions(width: int, height: int) -> tuple[int, int]:
    """Snap to the closest benchmarked segment-recording dimensions for the source aspect ratio.

    Picks the nearest of SEGMENT_DIM_1_1/4_3/16_9 by aspect ratio, oriented to
    match the source (landscape vs portrait). All presets are even, as
    required by libx264.
    """
    is_portrait = height > width
    long_side, short_side = (height, width) if is_portrait else (width, height)
    ratio = long_side / short_side

    presets = (
        (1.0, settings.SEGMENT_DIM_1_1),
        (4 / 3, settings.SEGMENT_DIM_4_3),
        (16 / 9, settings.SEGMENT_DIM_16_9),
    )
    _, (preset_w, preset_h) = min(presets, key=lambda item: abs(item[0] - ratio))

    new_width, new_height = (preset_h, preset_w) if is_portrait else (preset_w, preset_h)
    new_width = new_width if new_width % 2 == 0 else new_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1
    return new_width, new_height