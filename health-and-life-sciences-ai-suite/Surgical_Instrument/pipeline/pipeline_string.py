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
    PIPELINE_PREPROC_BACKEND -> gvadetect pre-process backend override
    PIPELINE_IE_CONFIG  -> gvadetect ie-config string override
    PIPELINE_FPSCOUNTER -> include/skip gvafpscounter in detect branch
"""
from __future__ import annotations

import shlex


VALID_DEVICES = {"CPU", "GPU", "NPU"}
VALID_SOURCE_KINDS = {"file", "basler"}

# File source: no leaky — every frame of the recorded clip must be inferred.
# Basler live source: leaky=downstream so the queue sheds old frames instead
# of building up unbounded latency when inference is slower than capture.
PRE_DETECT_QUEUE_FILE   = "queue max-size-buffers=1"
POST_DETECT_QUEUE_FILE  = "queue max-size-buffers=1"
PRE_DETECT_QUEUE_LIVE   = "queue "
POST_DETECT_QUEUE_LIVE  = "queue "


def _build_source(
    kind: str,
    arg: str,
    target_fps: int,
    *,
    pre_proc_backend: str = "ie",
    basler_pixel_format: str = "bayerbggr",
    basler_fixed_camera: bool = False,
    basler_exposure_us: str | None = None,
    basler_gain: str | None = None,
    basler_throughput_limit: str | None = None,
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
        # width/height are set on gencamsrc so it emits the intended
        # 1280x720 frame directly and no downstream `videoscale` is needed.
        # Frame rate is intentionally NOT pinned here: the finalized
        # production pipeline lets the camera free-run and paces on the
        # display clock via `autovideosink sync=true`.
        source_props = [
            f"serial={camera_serial}",
            f"pixel-format={pixel_format}",
            "width=1280",
            "height=720",
        ]
        # DeviceLinkThroughputLimit (bytes/sec) caps camera streaming rate; the
        # default 160 MB/s throttles dart cameras. Applied regardless of
        # fixed-camera mode since it is not an auto-exposure setting.
        if basler_throughput_limit:
            source_props.append(
                f"throughput-limit={shlex.quote(basler_throughput_limit)}"
            )
        if basler_fixed_camera:
            source_props.append("exposure-auto=off")
            if basler_exposure_us:
                source_props.append(f"exposure-time={shlex.quote(basler_exposure_us)}")
            # gain-auto=off is only pinned when an explicit gain is supplied.
            if basler_gain:
                source_props.append("gain-auto=off")
                source_props.append(f"gain={shlex.quote(basler_gain)}")
        gencamsrc_elem = f"gencamsrc {' '.join(source_props)}"
        is_bayer = basler_pixel_format.lower().startswith("bayer")
        if pre_proc_backend == "va-surface-sharing":
            # Finalized production Basler pipeline. See
            # docs/user-guide/basler-final-pipeline.md.
            # gencamsrc emits YCbCr422_8 (default) or Bayer directly; a single
            # `vapostproc` uploads to VAMemory as NV12 for zero-copy inference
            # via gvadetect(pre-process-backend=va-surface-sharing).
            # The caps element is single-quoted because it contains parens
            # (memory:VAMemory) which the shell would otherwise interpret.
            va_caps = "'video/x-raw(memory:VAMemory),format=NV12'"
            if is_bayer:
                return [
                    gencamsrc_elem,
                    "bayer2rgb",
                    "vapostproc",
                    va_caps,
                ], pre_proc_backend
            return [
                gencamsrc_elem,
                "vapostproc",
                va_caps,
            ], pre_proc_backend

        # Non-VA (ie) preproc backend needs system-memory NV12/RGB.
        if is_bayer:
            return [
                gencamsrc_elem,
                "bayer2rgb",
                "videoconvert",
                "video/x-raw",
            ], "ie"
        return [
            gencamsrc_elem,
            "videoconvert",
            "video/x-raw",
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
    pre_proc_backend: str | None = None,
    ie_config: str | None = "PERFORMANCE_HINT=LATENCY",
    enable_detect: bool = True,
    enable_watermark: bool = True,
    enable_fpscounter: bool = True,
    enable_identity: bool = True,
    minimal: bool = False,
    basler_pixel_format: str = "bayerbggr",
    basler_fixed_camera: bool = False,
    basler_exposure_us: str | None = None,
    basler_gain: str | None = None,
    basler_throughput_limit: str | None = None,
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

    requested_pre_proc = (pre_proc_backend or "").strip().lower()
    src_elems, pre_proc = _build_source(
        source_kind,
        source_arg,
        target_fps,
        pre_proc_backend=requested_pre_proc or "ie",
        basler_pixel_format=basler_pixel_format,
        basler_fixed_camera=basler_fixed_camera,
        basler_exposure_us=basler_exposure_us,
        basler_gain=basler_gain,
        basler_throughput_limit=basler_throughput_limit,
    )

    if requested_pre_proc:
        pre_proc = requested_pre_proc

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
      
    ]
    if ie_config:
        gvadetect_parts.append(f"ie-config={ie_config}")
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
        if is_live and pre_proc == "va-surface-sharing":
            sink_tail = ["vapostproc", f"{video_sink} sync={sink_sync_str}"]
        elif is_live:
            sink_tail = ["videoconvert", f"{video_sink} sync={sink_sync_str}"]
        else:
            sink_tail = [
            "vapostproc",
            f"{video_sink} sync={sink_sync_str}",
            ]
    else:
        sink_tail = ["fakesink sync=false async=false"]

    if enable_detect:
        detect_tail: list[str] = []
        if enable_watermark:
            detect_tail.append("gvawatermark")
        if enable_fpscounter:
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
    fpscounter_enabled = os.environ.get("PIPELINE_FPSCOUNTER", "1").strip().lower() not in {"0", "false", "no"}
    identity_enabled = os.environ.get("PIPELINE_IDENTITY", "0").strip().lower() not in {"0", "false", "no"}
    minimal = os.environ.get("MINIMAL", "0").strip().lower() not in {"0", "false", "no"}
    pre_proc_backend = os.environ.get("PIPELINE_PREPROC_BACKEND", "").strip() or None
    ie_config = os.environ.get("PIPELINE_IE_CONFIG", "PERFORMANCE_HINT=LATENCY").strip() or None
    basler_pixel_format = os.environ.get("BASLER_PIXEL_FORMAT", "bayerbggr").strip() or "bayerbggr"
    basler_fixed_camera = os.environ.get("BASLER_FIXED_CAMERA", "0").strip().lower() not in {"0", "false", "no"}

    print(
        build(
            source_kind=kind,
            source_arg=arg,
            ir_xml="/models/yolo11n_polyp/best_openvino_model/best.xml",
            device="GPU",
            target_fps=60,
            frame_limit=3000,
            display_view=True,
            video_sink="autovideosink",
            sink_sync=True,
            scheduling_policy=sched,
            batch_size=batch,
            pre_proc_backend=pre_proc_backend,
            ie_config=ie_config,
            enable_detect=detect_enabled,
            enable_watermark=watermark_enabled,
            enable_fpscounter=fpscounter_enabled,
            enable_identity=identity_enabled,
            minimal=minimal,
            basler_pixel_format=basler_pixel_format,
            basler_fixed_camera=basler_fixed_camera,
            basler_exposure_us=os.environ.get("BASLER_EXPOSURE_US", "").strip() or None,
            basler_gain=os.environ.get("BASLER_GAIN", "").strip() or None,
        )
    )
