"""Build the finalized gst-launch-1.0 pipeline strings.

Source modes:
    file   -> tuned recorded-file pipeline
    basler -> live Basler pipeline via pypylon -> fdsrc

A handful of env-driven knobs make the pipeline configurable at `make up`
time without introducing new pipeline shapes:

    SCHEDULING_POLICY   -> gvadetect scheduling-policy=<val>  (e.g. "latency")
    BATCH_SIZE          -> gvadetect batch-size=<N>           (e.g. 1)
    AUTOVIDEOSINK       -> render popup + set sink sync=true|false
    DETECT              -> include/skip the gvadetect stage
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


def _build_source(kind: str, arg: str, target_fps: int) -> tuple[list[str], str]:
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
        blocksize = 1920 * 1080 * 2  # UYVY = 2 B/px
        return [
            f"fdsrc fd=0 blocksize={blocksize} do-timestamp=true",
            (
                f"rawvideoparse format=yuy2 width=1920 height=1080 "
                f"framerate={target_fps}/1"
            ),
            "vapostproc",
            '"video/x-raw(memory:VAMemory),format=NV12"',
        ], "va-surface-sharing"
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
    minimal: bool = False,
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

    src_elems, pre_proc = _build_source(source_kind, source_arg, target_fps)

    is_live = source_kind == "basler"
    if sink_sync is None:
        sink_sync_str = "false" if is_live else "true"
    else:
        sink_sync_str = "true" if sink_sync else "false"

    if minimal:
        # Absolute minimum: just source -> sink. For the basler path we skip
        # the VA upload (no vapostproc / NV12) so the raw UYVY frames go
        # straight through videoconvert into the sink. Detect / queues /
        # identity are all disabled.
        if is_live:
            raw_src = [
                src_elems[0],   # fdsrc
                src_elems[1],   # rawvideoparse
            ]
        else:
            raw_src = src_elems  # file source keeps its demux/decoder
        if display_view:
            sink_tail = ["videoconvert", f"{video_sink} sync={sink_sync_str}"]
        else:
            sink_tail = ["fakesink sync=false async=false"]
        return " ! ".join(raw_src + sink_tail)

    eos = f"identity eos-after={frame_limit}" if frame_limit > 0 else "identity"
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
        sink_tail = [
            "vapostproc",
            '"video/x-raw"',
            "videoconvert",
            f"{video_sink} sync={sink_sync_str}",
        ]
    else:
        sink_tail = ["fakesink sync=false async=false"]

    if enable_detect:
        detect_tail: list[str] = []
        if enable_watermark:
            detect_tail.append("gvawatermark")
        detect_tail.append("gvafpscounter interval=1")
        chain = src_elems + [eos, pre_q, gvadetect, post_q] + detect_tail + sink_tail
    else:
        chain = src_elems + [eos, pre_q] + sink_tail
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
    minimal = os.environ.get("MINIMAL", "0").strip().lower() not in {"0", "false", "no"}

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
            minimal=minimal,
        )
    )
