"""Build the finalized gst-launch-1.0 pipeline strings.

Source modes:
    file   -> tuned recorded-file pipeline
    basler -> live Basler pipeline via gencamsrc

A handful of env-driven knobs make the pipeline configurable at `make up`
time without introducing new pipeline shapes:

    SCHEDULING_POLICY   -> gvadetect scheduling-policy=<val>  (e.g. "latency")
    BATCH_SIZE          -> gvadetect batch-size=<N>           (e.g. 1)
    AUTOVIDEOSINK       -> render popup + set sink sync=true|false
    DETECT              -> include/skip the gvadetect stage
    PIPELINE_IDENTITY   -> include/skip the passthrough `identity` element
    PIPELINE_SINK_SYNC  -> force sink `sync=true|false` (aka clock-sync)
"""
from __future__ import annotations

import shlex


VALID_DEVICES = {"CPU", "GPU", "NPU"}
VALID_SOURCE_KINDS = {"file", "basler"}

# File source: no leaky — every frame of the recorded clip must be inferred.
# Basler live source: leaky=downstream so the queue sheds old frames instead
# of building up unbounded latency when inference is slower than capture.
PRE_DETECT_QUEUE_FILE   = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000"
POST_DETECT_QUEUE_FILE  = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=0"
PRE_DETECT_QUEUE_LIVE   = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream"
POST_DETECT_QUEUE_LIVE  = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000 leaky=downstream"


def _build_source(
    kind: str,
    arg: str,
    target_fps: int,
    *,
    basler_pixel_format: str = "bayerbggr",
    basler_fixed_camera: bool = False,
    basler_exposure_us: str | None = None,
    basler_gain: str | None = None,
) -> tuple[list[str], str]:
    """Return the source elements and the matching gvadetect preproc backend."""
    kind = kind.lower()
    if kind == "file":
        # Quote file paths so uploaded filenames with spaces (e.g. "qa upload.mp4")
        # do not break gst-launch tokenization.
        file_arg = shlex.quote(arg)
        return [
            f"filesrc location={file_arg}",
            "qtdemux",
            "h264parse",
            "vah264dec",
        ], "ie"
    if kind == "basler":
        camera_serial = shlex.quote(arg)
        pixel_format = shlex.quote(basler_pixel_format)
        # Explicit frame-rate is REQUIRED: without it, gencamsrc lets the
        # camera default to a very low rate (~7 fps observed on
        # acA1920-150uc), which then propagates through the entire pipeline
        # regardless of downstream tuning. Set to target_fps so the sensor
        # actually delivers frames at the intended rate.
        source_props = [
            f"serial={camera_serial}",
            f"pixel-format={pixel_format}",
            f"frame-rate={target_fps}",
        ]
        if basler_fixed_camera:
            source_props.extend(["exposure-auto=off", "gain-auto=off"])
            if basler_exposure_us:
                source_props.append(f"exposure-time={shlex.quote(basler_exposure_us)}")
            if basler_gain:
                source_props.append(f"gain={shlex.quote(basler_gain)}")
        return [
            f"gencamsrc {' '.join(source_props)}",
            "bayer2rgb",
            "videoscale",
            "videoconvert",
            "video/x-raw,width=1280,height=720,format=NV12",
        ], "ie"
    raise ValueError(f"unsupported source_kind: {kind!r} (want file|basler)")


def build(
    *,
    ir_xml: str,
    device: str,
    threshold: float,
    target_fps: int,
    source_kind: str = "file",
    source_arg: str | None = None,
    video: str | None = None,
    frame_limit: int = 0,
    display_view: bool = False,
    video_sink: str = "ximagesink",
    scheduling_policy: str | None = None,
    batch_size: int | None = None,
    sink_sync: bool | None = None,
    enable_detect: bool = True,
    enable_watermark: bool = True,
    enable_identity: bool = True,
    minimal: bool = False,
    basler_pixel_format: str = "bayerbggr",
    basler_fixed_camera: bool = False,
    basler_exposure_us: str | None = None,
    basler_gain: str | None = None,
) -> str:
    """Return the finalized single-branch gst-launch pipeline string.

    When ``minimal`` is True the returned string is literally
    ``<source_raw> ! videoconvert ! <sink>`` (no queue, no identity, no
    detect stage, no VA upload). This is the "just camera to autovideosink"
    shape used for Case 2 sanity checks.
    """
    dev = device.upper()
    if dev not in VALID_DEVICES:
        raise ValueError(f"unsupported device: {device!r} (want CPU|GPU|NPU)")

    if source_arg is None:
        if video is None:
            raise ValueError("must supply source_arg (or legacy `video=`)")
        source_arg = video

    src_elems, pre_proc = _build_source(
        source_kind,
        source_arg,
        target_fps,
        basler_pixel_format=basler_pixel_format,
        basler_fixed_camera=basler_fixed_camera,
        basler_exposure_us=basler_exposure_us,
        basler_gain=basler_gain,
    )

    is_live = source_kind == "basler"
    if sink_sync is None:
        sink_sync_str = "false" if is_live else "true"
    else:
        sink_sync_str = "true" if sink_sync else "false"

    if minimal:
        # Absolute minimum: just source -> sink. Detect / queues / identity
        # are all disabled.
        raw_src = src_elems
        if display_view:
            sink_tail = ["videoconvert", f"{video_sink} sync={sink_sync_str}"]
        else:
            sink_tail = ["fakesink sync=false async=false"]
        return " ! ".join(raw_src + sink_tail)

    eos = f"identity eos-after={frame_limit}" if frame_limit > 0 else "identity"
    # When frame_limit > 0 the `identity eos-after=N` element is structurally
    # required to terminate the pipeline cleanly, so the toggle is ignored in
    # that case. When frame_limit == 0 `identity` is a pure passthrough and
    # can safely be dropped via PIPELINE_IDENTITY=0.
    include_identity = enable_identity or frame_limit > 0
    model_arg = shlex.quote(ir_xml)
    gvadetect_parts = [
        f"gvadetect model={model_arg} device={dev} threshold={threshold}",
        f"pre-process-backend={pre_proc}",
        "nireq=1",
        "ie-config=PERFORMANCE_HINT=LATENCY",
    ]
    if scheduling_policy:
        gvadetect_parts.append(f"scheduling-policy={scheduling_policy}")
    if batch_size is not None and batch_size > 0:
        gvadetect_parts.append(f"batch-size={batch_size}")
    gvadetect = " ".join(gvadetect_parts)

    pre_q  = PRE_DETECT_QUEUE_LIVE  if is_live else PRE_DETECT_QUEUE_FILE
    post_q = POST_DETECT_QUEUE_LIVE if is_live else POST_DETECT_QUEUE_FILE

    if display_view:
        # The VA pipeline keeps frames in VAMemory (NV12). Download to system
        # memory with `vapostproc ! video/x-raw` and colour-convert before
        # the sink. sync=false for live (basler) sources — no file clock.
        sink_tail = ["videoconvert", f"{video_sink} sync={sink_sync_str}"] if is_live else [
            "vapostproc",
            f"{video_sink} sync={sink_sync_str}",
        ]
    else:
        sink_tail = ["fakesink sync=false async=false"]

    if enable_detect:
        detect_tail: list[str] = []
        if enable_watermark:
            detect_tail.append("gvawatermark")
        detect_tail.append("gvafpscounter interval=1")
        head = src_elems + ([eos] if include_identity else [])
        chain = head + [pre_q, gvadetect, post_q] + detect_tail + sink_tail
    else:
        head = src_elems + ([eos] if include_identity else [])
        chain = head + [pre_q] + sink_tail
    return " ! ".join(chain)


if __name__ == "__main__":  # smoke: `python3 pipeline_string.py [file|basler]`
    import os
    import sys

    kind = sys.argv[1] if len(sys.argv) > 1 else "file"
    arg = {"file": "/videos/polyp_test.mp4", "basler": "12345678"}[kind]

    sched = os.environ.get("SCHEDULING_POLICY", "").strip() or None
    batch_raw = os.environ.get("BATCH_SIZE", "").strip()
    batch = int(batch_raw) if batch_raw.isdigit() else None
    detect_enabled = os.environ.get("DETECT", "1").strip().lower() not in {"0", "false", "no"}
    watermark_enabled = os.environ.get("WATERMARK", "1").strip().lower() not in {"0", "false", "no"}
    identity_enabled = os.environ.get("PIPELINE_IDENTITY", "0").strip().lower() not in {"0", "false", "no"}
    minimal = os.environ.get("MINIMAL", "0").strip().lower() not in {"0", "false", "no"}
    basler_pixel_format = os.environ.get("BASLER_PIXEL_FORMAT", "bayerbggr").strip() or "bayerbggr"
    basler_fixed_camera = os.environ.get("BASLER_FIXED_CAMERA", "0").strip().lower() not in {"0", "false", "no"}

    print(
        build(
            source_kind=kind,
            source_arg=arg,
            ir_xml="/models/yolo11n_polyp/best_openvino_model/best.xml",
            device="GPU",
            threshold=0.5,
            target_fps=60,
            frame_limit=3000,
            display_view=True,
            video_sink="autovideosink",
            sink_sync=True,
            scheduling_policy=sched,
            batch_size=batch,
            enable_detect=detect_enabled,
            enable_watermark=watermark_enabled,
            enable_identity=identity_enabled,
            minimal=minimal,
            basler_pixel_format=basler_pixel_format,
            basler_fixed_camera=basler_fixed_camera,
            basler_exposure_us=os.environ.get("BASLER_EXPOSURE_US", "").strip() or None,
            basler_gain=os.environ.get("BASLER_GAIN", "").strip() or None,
        )
    )
