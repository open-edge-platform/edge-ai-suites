"""Build the gst-launch-1.0 pipeline string for the surgical polyp detector.

Ported from the POC winner (poc/st2_app/dls/bench/latency_probe.py) with
production additions:
  - `gvatrack tracking-type=short-term-imageless`   → persistent object IDs
  - `gvametaconvert format=json`                    → JSON detection metadata
  - `tee` splits post-metadata into two branches:
      · gvametapublish (MQTT)  → surgical/detections topic
      · gvawatermark → jpegenc → multifilesink /frames/latest.jpg
  - No `model-proc` — DLS 2026.1 auto-detects the YOLO11 converter from
    Ultralytics' metadata.yaml shipped next to best.xml. Passing a
    hand-written model-proc collapses confidence scores (verified in the
    Phase 5.0.5 smoke).
"""
from __future__ import annotations


VALID_DEVICES = {"CPU", "GPU", "NPU"}


def build(
    *,
    video: str,
    ir_xml: str,
    device: str,
    threshold: float,
    target_fps: int,
    mqtt_host: str,
    mqtt_topic: str,
    frame_path: str,
) -> str:
    """Return a single-line gst-launch pipeline string."""
    dev = device.upper()
    if dev not in VALID_DEVICES:
        raise ValueError(f"unsupported device: {device!r} (want CPU|GPU|NPU)")

    # `pre-process-backend=ie` works for CPU/GPU/NPU on system-memory buffers
    # (what `videoconvert` produces). `va-surface-sharing` needs upstream VA
    # memory, which our decode+scale chain doesn't guarantee. Using `ie`
    # matches the POC pipeline that produced 12.6ms mean / 21.9ms p99 on GPU.
    pre_proc = "ie"

    # Target the customer requirement: 1080p @ 60 fps camera-to-screen.
    # `videorate framerate=60/1` sets 60 fps output timestamps; `identity
    # sync=true` enforces the 60 fps *wall-clock* cadence — this is what a
    # real 60 fps camera provides naturally (frames arrive on a 16.7 ms
    # tick) and is why NICU/MMPM and other DL Streamer demos use it for
    # filesrc-based pipelines. It inflates the DLS `frame_latency` metric
    # (source→sink residence includes the pacing wait, an artefact of
    # filesrc pushing ahead of the clock) so we hide that field from the
    # primary UI and instead report *processing latency*: the per-frame
    # sum of `element-latency` across gvadetect + gvatrack +
    # gvametaconvert + gvawatermark + jpegenc. That number IS the
    # camera-to-screen latency on a live source and is what the <30 ms
    # requirement is measured against. See
    # `backend/consumer/latency_tail.py` header for the details.
    main = " ! ".join(
        [
            f"filesrc location={video}",
            "decodebin",
            "videoconvert",
            "videoscale",
            "video/x-raw,width=1920,height=1080",
            "videorate",
            f"video/x-raw,width=1920,height=1080,framerate={target_fps}/1",
            "identity sync=true",
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
            "gvawatermark",
            "videoconvert",
            "jpegenc quality=80",
            f"multifilesink location={frame_path}",
        ]
    )

    # gst-launch tee syntax: branches share the `meta.` pad-reference, and
    # each branch starts a NEW element chain (no `!` between branches).
    return f"{main} {mqtt_branch} {jpeg_branch}"


if __name__ == "__main__":  # smoke: `python3 pipeline_string.py`
    print(
        build(
            video="/videos/polyp_test.mp4",
            ir_xml="/models/yolo11n_polyp/best_openvino_model/best.xml",
            device="GPU",
            threshold=0.5,
            target_fps=60,
            mqtt_host="surgical-mqtt",
            mqtt_topic="surgical/detections",
            frame_path="/frames/latest.jpg",
        )
    )
