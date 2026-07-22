"""Build the finalized gst-launch-1.0 pipeline strings.

The runtime only exposes two source modes:
file -> tuned recorded-file pipeline
basler -> live Basler pipeline via pypylon -> fdsrc

Both variants share the same post-source body and differ only in the source
segment and the gvadetect pre-process backend.
"""
from __future__ import annotations


VALID_DEVICES = {"CPU", "GPU", "NPU"}
VALID_SOURCE_KINDS = {"file", "basler"}

PRE_DETECT_QUEUE = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=16000000"
POST_DETECT_QUEUE = "queue max-size-buffers=1 max-size-bytes=0 max-size-time=0"


def _build_source(kind: str, arg: str, target_fps: int) -> tuple[list[str], str]:
    """Return the source elements and the matching gvadetect preproc backend."""
    kind = kind.lower()
    if kind == "file":
        return [
            f"filesrc location={arg}",
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
    raise ValueError(
        f"unsupported source_kind: {kind!r} (want file|basler)"
    )


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
) -> str:
    """Return the finalized single-branch gst-launch pipeline string."""
    dev = device.upper()
    if dev not in VALID_DEVICES:
        raise ValueError(f"unsupported device: {device!r} (want CPU|GPU|NPU)")

    if source_arg is None:
        if video is None:
            raise ValueError("must supply source_arg (or legacy `video=`)")
        source_arg = video

    src_elems, pre_proc = _build_source(source_kind, source_arg, target_fps)
    sink = f"{video_sink} sync=false" if display_view else "fakesink sync=false async=false"
    eos = f"identity eos-after={frame_limit}" if frame_limit > 0 else "identity"
    gvadetect = (
        f"gvadetect model={ir_xml} device={dev} threshold={threshold} "
        f"pre-process-backend={pre_proc} nireq=1 "
        "ie-config=PERFORMANCE_HINT=LATENCY"
    )
    return " ! ".join(
        src_elems
        + [
            eos,
            PRE_DETECT_QUEUE,
            gvadetect,
            POST_DETECT_QUEUE,
            "gvawatermark",
            "gvafpscounter interval=1",
            sink,
        ]
    )


if __name__ == "__main__":  # smoke: `python3 pipeline_string.py [file|basler]`
    import sys

    kind = sys.argv[1] if len(sys.argv) > 1 else "file"
    arg = {
        "file": "/videos/polyp_test.mp4",
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
            frame_limit=3000,
            display_view=False,
        )
    )
