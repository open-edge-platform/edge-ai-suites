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
    eos = f"identity eos-after={frame_limit}" if frame_limit > 0 else "identity"
    gvadetect = (
        f"gvadetect model={ir_xml} device={dev} threshold={threshold} "
        f"pre-process-backend={pre_proc} nireq=1 "
        "ie-config=PERFORMANCE_HINT=LATENCY"
    )
    is_live = (source_kind == "basler")
    pre_q  = PRE_DETECT_QUEUE_LIVE  if is_live else PRE_DETECT_QUEUE_FILE
    post_q = POST_DETECT_QUEUE_LIVE if is_live else POST_DETECT_QUEUE_FILE
    if display_view:
        # The VA pipeline keeps frames in VAMemory (NV12) all the way to the
        # sink. A software X sink such as `ximagesink` cannot negotiate those
        # caps ("not-negotiated") and the pipeline aborts before a window ever
        # opens — which the launcher then masks by falling back to a headless
        # fakesink, so no popup appears (notably on the Basler path, which
        # forces `video/x-raw(memory:VAMemory),format=NV12`). Download to
        # system memory with `vapostproc ! video/x-raw` and colour-convert
        # before the sink. Matches the known-good DISPLAY sink tail in
        # scripts/run_basler_pipeline.sh.
        #
        # sync=true on the sink for file sources: without it the pipeline
        # decodes/renders as fast as the GPU allows (e.g. 105 fps for a 25 fps
        # file), so a 69 s clip finishes in ~16 s wall time. sync=true lets
        # the GStreamer clock throttle each buffer to the file's native PTS so
        # playback runs at the encoded speed. Live sources (basler) keep
        # sync=false — they have no file clock and must render as frames arrive.
        sink_sync = "false" if source_kind == "basler" else "true"
        sink_tail = [
            "gvawatermark",
            "gvafpscounter interval=1",
            "vapostproc",
            '"video/x-raw"',
            "videoconvert",
            f"{video_sink} sync={sink_sync}",
        ]
    else:
        sink_tail = [
            "gvawatermark",
            "gvafpscounter interval=1",
            "fakesink sync=false async=false",
        ]
    return " ! ".join(
        src_elems
        + [
            eos,
            pre_q,
            gvadetect,
            post_q,
        ]
        + sink_tail
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
