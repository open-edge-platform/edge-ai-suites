"""Build the gst-launch-1.0 pipeline string for the surgical polyp detector.

Ported from the POC winner (poc/st2_app/dls/bench/latency_probe.py) with
production additions:
  - `gvatrack tracking-type=short-term-imageless`   → persistent object IDs
  - `gvametaconvert format=json`                    → JSON detection metadata
  - `tee` splits post-metadata into two branches:
      · gvametapublish (MQTT)  → surgical/detections topic
      · watermark_green (gvapython) → jpegenc → multifilesink /frames/latest.jpg
  - No `model-proc` — DLS 2026.1 auto-detects the YOLO11 converter from
    Ultralytics' metadata.yaml shipped next to best.xml. Passing a
    hand-written model-proc collapses confidence scores (verified in the
    Phase 5.0.5 smoke).
"""
from __future__ import annotations


VALID_DEVICES = {"CPU", "GPU", "NPU"}
VALID_SOURCE_KINDS = {"file", "v4l2", "basler"}


def _build_source(kind: str, arg: str, target_fps: int) -> list[str]:
    """Return the source-segment elements up to (but not including) `gvadetect`.

    File source needs pacing (`videorate + identity sync=true`) because
    filesrc pushes ahead of the wall clock. Live sources (v4l2, basler)
    already pace themselves at sensor rate — pacing would double-buffer
    and add latency.
    """
    kind = kind.lower()
    if kind == "file":
        return [
            f"filesrc location={arg}",
            "decodebin",
            "videoconvert",
            "videoscale",
            "video/x-raw,width=1920,height=1080",
            "videorate",
            f"video/x-raw,width=1920,height=1080,framerate={target_fps}/1",
            "identity sync=true",
        ]
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
        # Basler USB3 industrial camera via the DL Streamer `gencamsrc`
        # plugin. Requires pylon SDK + gst-plugin-gencamsrc on top of the
        # base image — the current pipeline/Dockerfile does NOT install
        # these, so selecting this source kind before that add-on lands
        # will fail with "no such element gencamsrc". Tracking as a
        # follow-up to keep the base image slim for MTL/PTL bring-up.
        # `arg` is the camera serial number.
        return [
            f"gencamsrc serial={arg} pixel-format=ycbcr422_8",
            f"video/x-raw,format=YUY2,width=1920,height=1080,framerate={target_fps}/1",
            "videoconvert",
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
) -> str:
    """Return a single-line gst-launch pipeline string.

    `source_kind` is "file" | "v4l2" | "basler". `source_arg` is the file
    path, /dev/videoN, or Basler serial respectively. `video=` is kept as
    a legacy alias for `source_kind="file", source_arg=video`.
    """
    dev = device.upper()
    if dev not in VALID_DEVICES:
        raise ValueError(f"unsupported device: {device!r} (want CPU|GPU|NPU)")

    if source_arg is None:
        if video is None:
            raise ValueError("must supply source_arg (or legacy `video=`)")
        source_arg = video

    # `pre-process-backend=ie` works for CPU/GPU/NPU on system-memory buffers
    # (what `videoconvert` produces). `va-surface-sharing` needs upstream VA
    # memory, which our decode+scale chain doesn't guarantee. Using `ie`
    # matches the POC pipeline that produced 12.6ms mean / 21.9ms p99 on GPU.
    pre_proc = "ie"

    # Target the customer requirement: 1080p @ 60 fps camera-to-screen.
    # Pacing (`videorate + identity sync=true`) lives inside _build_source
    # for the file case; live sources skip it — the sensor already paces
    # at wall-clock rate. Adding pacing to a live source would double-
    # buffer and add ~one frame period of latency.
    main = " ! ".join(
        _build_source(source_kind, source_arg, target_fps)
        + [
            (
                f"gvadetect name=det model={ir_xml} device={dev} "
                f"threshold={threshold} pre-process-backend={pre_proc} nireq=1"
            ),
            # Drop garbage full-frame boxes yolo11n occasionally emits
            # before the tracker assigns them a persistent ID.
            "gvapython module=/opt/bbox_filter.py class=BBoxFilter",
            "gvatrack tracking-type=short-term-imageless",
            # add-empty-results=true emits a JSON message for every frame,
            # even ones with no detections. Without this, gvametaconvert
            # skips empty frames and the backend's detection_rate stays
            # pinned at 100% because the denominator (total frames) never
            # counts no-detection frames.
            "gvametaconvert format=json add-tensor-data=false add-empty-results=true",
            "tee name=meta",
        ]
    )

    # gvametapublish MQTT in the DLS 2026.1 image never opens a TCP connection
    # to the broker (verified during Phase 5.1 smoke). We push the JSON
    # metadata through a gvapython callback that uses paho-mqtt instead.
    # MQTTPublisher reads MQTT_HOST / MQTT_TOPIC from environment, so no kwarg
    # is needed here.
    mqtt_branch = " ! ".join(
        [
            "meta.",
            "queue max-size-buffers=4 leaky=downstream",
            "gvapython module=/opt/mqtt_publisher.py class=MQTTPublisher",
            "fakesink sync=false",
        ]
    )

    jpeg_branch = " ! ".join(
        [
            "meta.",
            "queue max-size-buffers=4 leaky=downstream",
            # Force BGRx so the gvapython drawer can write pixels with OpenCV.
            "videoconvert",
            "video/x-raw,format=BGRx",
            # Replaces gvawatermark: draws every polyp box in a single neutral
            # green (see watermark_green.py) instead of the per-track-ID rainbow.
            # Named `drawer` so latency_tail.py's processing-chain allowlist can
            # find its element-latency ticks in the tracer log.
            "gvapython name=drawer module=/opt/watermark_green.py class=GreenWatermark",
            # Move to NV12 system memory so vajpegenc can uplift to VAMemory
            # and run the encode on the iGPU media engine (~1 ms) instead of
            # libjpeg-turbo on a CPU thread (3-11 ms, whichever core the
            # kernel picks). Fixes PTL jpegenc placing on E/LP-E cores under
            # the 6.17 hybrid scheduler and removes CPU-placement variance
            # on MTL too.
            "videoconvert",
            "video/x-raw,format=NV12",
            "vajpegenc quality=80",
            f"multifilesink location={frame_path}",
        ]
    )

    # gst-launch tee syntax: branches share the `meta.` pad-reference, and
    # each branch starts a NEW element chain (no `!` between branches).
    return f"{main} {mqtt_branch} {jpeg_branch}"


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
