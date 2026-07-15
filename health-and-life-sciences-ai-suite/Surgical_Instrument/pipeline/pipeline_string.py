"""Build the gst-launch-1.0 pipeline string for the surgical polyp detector.

This module intentionally keeps the runtime graph simple and reviewable:
source -> gvadetect -> gvawatermark -> gvafpscounter -> vajpegenc -> sink.
Only source kind, source arg, and target device are variable.
"""
from __future__ import annotations


VALID_DEVICES = {"CPU", "GPU", "NPU"}
VALID_SOURCE_KINDS = {"file", "file_novasource", "v4l2", "basler"}


def _build_source(kind: str, arg: str, target_fps: int, paced: bool = False) -> list[str]:
    """Return the source-segment elements up to (but not including) `gvadetect`.

    File sources use the hand-picked HW-decoder chain
    (`filesrc ! qtdemux ! h264parse ! vah264dec`) — this is the VFINAL
    body validated in out/tune/. `urisourcebin + decodebin3` was tried
    and yielded identical LIVE latency but a ~295 ms inflated raw
    e2e_mean (decodebin3 pre-buffer + videorate residency), which was
    confusing in latency traces. `file_novasource` is kept as a legacy
    alias (identical to `file` in this build).

    Live sources already pace themselves at sensor rate.
    """
    kind = kind.lower()
    if kind in ("file", "file_novasource"):
        # Hand-picked HW decoder chain. Kept minimal:
        #   filesrc -> qtdemux -> h264parse -> vah264dec
        # No `videorate` / `capsfilter` — the source is already exactly
        # `target_fps`, so those elements would only add residency.
        # `identity sync=true` (added when paced) is enough for wall-clock
        # pacing against the pipeline clock.
        elems = [
            f"filesrc location={arg}",
            "qtdemux",
            "h264parse",
            "vah264dec",
        ]
        if paced:
            # `identity sync=true` waits on PTS against the pipeline clock,
            # making the file behave like a live camera at its native rate.
            # Result: latency_tracer e2e reflects real source-to-sink time
            # instead of decoder-queue accumulation, and multifilesink
            # writes for the full clip duration so the UI stays live.
            elems.append("identity sync=true")
        return elems
    if kind == "v4l2":
        # Standard UVC USB camera path (webcams, most USB3 cameras). MJPG
        # UVC mode (`image/jpeg → jpegdec`) is the only reliable way to
        # get 1080p60 out of a bandwidth-limited USB3 link on a UVC cam.
        # `arg` is the device path, e.g. `/dev/video0`.
        return [
            f"v4l2src device={arg}",
            f"image/jpeg,width=1920,height=1080,framerate={target_fps}/1",
            "jpegdec",
            "videoconvert",
        ]
    if kind == "basler":
        # Basler USB3 industrial camera. The DL Streamer 2026.1 base image
        # does not ship `gencamsrc` or Basler's `pylonsrc`, so we bridge
        # via a small Python helper that streams raw frames from pypylon
        # to stdout; launcher.py pipes that stdout into `gst-launch-1.0`
        # here on fd=0.
        #
        # `arg` is the camera serial number (used by basler_reader.py).
        # The 1920x1080 geometry + framerate must match what
        # basler_reader.py configures — kept in sync via the same
        # target_fps and a fixed 1080p full-frame ROI (per acA1920-150uc
        # native sensor). Change both together.
        #
        # Camera-native YCbCr422_8 (2 B/px packed). On PTL/DLS 2026.1 this
        # stream must be parsed as YUY2 in rawvideoparse; UYVY parsing causes
        # a green-corrupted frame.
        blocksize = 1920 * 1080 * 2  # UYVY = 2 B/px
        return [
            f"fdsrc fd=0 blocksize={blocksize} do-timestamp=true",
            (
                f"rawvideoparse format=yuy2 width=1920 height=1080 "
                f"framerate={target_fps}/1"
            ),
            # Caps segment double-quoted so the outer shell (launcher.py uses
            # shell=True) does not treat the parens in `(memory:VAMemory)` as
            # a subshell.
            "vapostproc",
            '"video/x-raw(memory:VAMemory),format=NV12"',
        ]
    raise ValueError(
        f"unsupported source_kind: {kind!r} (want file|v4l2|basler)"
    )


def build(
    *,
    ir_xml: str,
    device: str,
    threshold: float,
    target_fps: int,
    mqtt_host: str,
    mqtt_topic: str,
    frame_path: str,
    source_kind: str = "file",
    source_arg: str | None = None,
    video: str | None = None,
    bench_mode: bool = False,
    paced: bool | None = None,
    mqtt_leaky: bool = False,  # kept for CLI back-compat; ignored in VFINAL topology
    pp_backend: str = "ie",
    mqtt_only: bool = False,
) -> str:
    """Return a single-line gst-launch pipeline string (VFINAL topology).

    VFINAL was picked from a 6-way tuning matrix (out/tune/) as the pipeline
    that minimises LIVE_p99 while keeping the UI live for the entire clip:
      * tee is placed AFTER gvadetect (both branches share the inference).
      * pre-detect queue is bounded by both buffer count and 100 ms residency.
      * MQTT branch queue is deep (8 buffers) and non-leaky so no metadata
        frame is silently dropped.
      * Video branch queue is bounded (4 buffers, 100 ms) and leaky=downstream
        so occasional sink-write jitter drops frames instead of stalling
        upstream - keeps LIVE_p99 tight (~117 ms vs. 153 ms without leaky).
      * multifilesink is sync=false because pacing is done by identity sync=true
        upstream (for file sources) or by the camera itself (for live sources).
      * gvadetect uses nireq=2 to keep two inferences pipelined on the GPU.

    Sources:
      "file"           urisourcebin + decodebin3 (default)
      "file_novasource" filesrc + qtdemux + h264parse + vah264dec (hand-picked)
      "v4l2"           UVC USB camera
      "basler"         Basler USB3 via fdsrc bridge (basler_reader.py)

    `paced` defaults to True for file sources (adds identity sync=true so the
    file plays at wall-clock rate). Live sources ignore `paced` - the sensor
    is already the clock. `bench_mode` forces paced=False regardless (for
    unpaced e2e latency measurement).

    `mqtt_only=True` drops the render/UI branch entirely and publishes only
    to MQTT. UI renders bounding boxes client-side.
    """
    dev = device.upper()
    if dev not in VALID_DEVICES:
        raise ValueError(f"unsupported device: {device!r} (want CPU|GPU|NPU)")

    if source_arg is None:
        if video is None:
            raise ValueError("must supply source_arg (or legacy `video=`)")
        source_arg = video

    is_file = source_kind.lower() in ("file", "file_novasource")
    # Pace file sources by default so multifilesink writes for the full clip
    # duration - without pacing the file plays "as fast as possible" and the
    # UI freezes after a burst of writes. Live sources are always self-paced.
    if paced is None:
        paced = is_file and not bench_mode
    del mqtt_leaky  # obsolete in VFINAL; retained in signature for CLI back-compat

    pre_proc = pp_backend
    src_elems = _build_source(source_kind, source_arg, target_fps, paced=paced)

    # multifilesink sync=false: upstream is already paced (identity for file,
    # sensor for live). sync=true here would double-pace and force the video
    # queue to accumulate buffers, hurting LIVE_p99.
    sink = f"multifilesink location={frame_path} max-files=2 async=false sync=false"

    # Pre-detect queue: bounded by buffers AND wall-clock time. The
    # max-size-time cap keeps LIVE_p99 tight when downstream jitters.
    pre_detect_q = (
        "queue max-size-buffers=2 max-size-bytes=0 max-size-time=100000000"
    )
    gvadetect = (
        f"gvadetect model={ir_xml} device={dev} "
        f"threshold={threshold} pre-process-backend={pre_proc} nireq=2"
    )

    use_mqtt = bool(mqtt_host and mqtt_topic)

    # ---- No-MQTT: single branch, no tee ------------------------------------
    if not use_mqtt:
        return " ! ".join(
            src_elems
            + [
                pre_detect_q,
                gvadetect,
                (
                    "queue max-size-buffers=4 max-size-bytes=0 "
                    "max-size-time=100000000 leaky=downstream"
                ),
                "gvawatermark",
                "gvafpscounter interval=1",
                "vajpegenc quality=90",
                sink,
            ]
        )

    # ---- MQTT-only: no render/UI branch, no tee ----------------------------
    if mqtt_only:
        return " ! ".join(
            src_elems
            + [
                pre_detect_q,
                gvadetect,
                "queue max-size-buffers=8 max-size-bytes=0 max-size-time=0",
                "gvafpscounter interval=1",
                "gvametaconvert format=json add-tensor-data=false add-empty-results=false",
                "gvapython module=/opt/mqtt_publisher.py class=MQTTPublisher",
                "fakesink sync=false async=false",
            ]
        )

    # ---- UI + MQTT: tee AFTER gvadetect ------------------------------------
    # Metadata (MQTT) branch: deep non-leaky queue, gvametaconvert only here
    # (video branch doesn't need JSON meta). VFINAL body is preserved verbatim
    # here — no gvafpscounter on this branch (that lives on the render branch,
    # where it measures actually-delivered UI frames).
    main = " ! ".join(
        src_elems + [pre_detect_q, gvadetect, "tee name=t"]
    )
    mqtt_branch = " ! ".join(
        [
            "t.",
            "queue max-size-buffers=8 max-size-bytes=0 max-size-time=0",
            "gvametaconvert format=json add-empty-results=false add-tensor-data=false",
            "gvapython module=/opt/mqtt_publisher.py class=MQTTPublisher",
            "fakesink sync=false async=false",
        ]
    )
    render_branch = " ! ".join(
        [
            "t.",
            (
                "queue max-size-buffers=4 max-size-bytes=0 "
                "max-size-time=100000000 leaky=downstream"
            ),
            "gvawatermark",
            "gvafpscounter interval=1",
            "vajpegenc quality=90",
            sink,
        ]
    )
    return f"{main} {mqtt_branch} {render_branch}"


if __name__ == "__main__":  # smoke: `python3 pipeline_string.py [file|v4l2|basler]`
    import sys

    kind = sys.argv[1] if len(sys.argv) > 1 else "file"
    arg = {
        "file": "/videos/polyp_test.mp4",
        "v4l2": "/dev/video0",
        "basler": "12345678",
    }[kind]

    print(
        build(
            source_kind=kind,
            source_arg=arg,
            ir_xml="/models/yolo11n_polyp/best_openvino_model/best.xml",
            device="GPU",
            threshold=0.5,
            target_fps=60,
            mqtt_host="surgical-mqtt",
            mqtt_topic="surgical/detections",
            frame_path="/frames/latest.jpg",
        )
    )
