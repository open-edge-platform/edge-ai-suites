# HOTA Script Reference

## [mqtt_camera_capture_processor.py](../../../../usecases/scenescape-deterministic-inference/hota/scripts/hota-metrics/mqtt_camera_capture_processor.py)

**Location:** `usecases/scenescape-deterministic-inference/hota/scripts/hota-metrics/`

**Purpose:** Subscribes to MQTT camera detection topics, captures a fixed number of frames, reconstructs a clean dataset with no gaps, and triggers the HOTA evaluation pipeline.

The script will:
1. Subscribe to `scenescape/data/camera/Cam_x1_0` and `scenescape/data/camera/Cam_x2_0`
2. Wait silently until **frame 0** arrives on both cameras (start of a fresh video loop)
3. Collect 1,856 frames per camera
4. Fill any dropped frames with empty-object placeholders
5. Replace all timestamps with the reference timestamps from `frame_timestamp_mapping.csv` (so they align with `gtLoc.json` ground truth)
6. Write the reconstructed detection files to `hota-metrics/dataset/`
7. Automatically invoke `pipeline_engine metric_test_evaluation.yaml` to run HOTA scoring

HOTA results are written to `/tmp/tracker-evaluation/<run-ID>/`.

**Key behaviours:**

| Behaviour | Detail |
|-----------|--------|
| **Frame synchronization** | Waits for `frame == 0` before starting capture — ensures the dataset always starts at the beginning of the video loop |
| **Drop detection** | Detects missing frame numbers (for example, frame 5 followed by frame 8 means frames 6 and 7 were dropped) |
| **Drop compensation** | Inserts placeholder entries with empty `objects` for every missing frame number |
| **Timestamp normalization** | Replaces all captured timestamps with the reference mapping from `frame_timestamp_mapping.csv`, so they match the `gtLoc.json` ground truth timestamps |
| **Pipeline trigger** | After capture completes, runs `python -m pipeline_engine metric_test_evaluation.yaml` automatically with `PYTHONPATH=..` so it can import evaluation modules |

**Configuration (edit at top of script):**

```python
MAX_SAMPLES = 1856               # Number of frames to capture per camera
MQTT_BROKER_HOST = "127.0.0.1"  # MQTT broker address (Machine 1 local)
TIMESTAMP_MAPPING_CSV = "frame_timestamp_mapping.csv"  # Frame → timestamp reference
OUTPUT_DIRECTORY = "dataset"     # Where reconstructed JSON files are written
```

---

## [traffic_generator.py](../../../../usecases/scenescape-deterministic-inference/hota/scripts/traffic_generator.py)

**Location:** `usecases/scenescape-deterministic-inference/hota/scripts/`

**Purpose:** Injects controlled network congestion using `iperf3`, gated by MQTT camera frame numbers so it does not interfere with the capture start or end.

**Key behaviours:**

| Behaviour | Detail |
|-----------|--------|
| **MQTT-gated start** | Waits until frame 0 is received on **all** configured camera topics before launching `iperf3` |
| **Burst pattern** | Runs `iperf3` for `--duration` seconds, sleeps `--sleep` seconds, repeats — mimics real-world bursty congestion |
| **Automatic stop** | Exits when any camera frame exceeds `--stop-frame`, ensuring the final frames of the capture window are not interrupted |

**Key CLI arguments:**

```
--broker       MQTT broker host (default: 127.0.0.1)
--topics       Camera MQTT topics to monitor for frame gating
--target       iperf3 server host
--bitrate      iperf3 UDP bitrate (default: 960M)
--duration     iperf3 run time in seconds (default: 2)
--sleep        Sleep between iperf3 runs (default: 1.0)
--stop-frame   Stop traffic when this frame number is exceeded (default: 1700)
```

---

## [sei_parser.py](../../../../usecases/scenescape-deterministic-inference/hota/scripts/gvapython/sei_parser.py)

**Location:** `usecases/scenescape-deterministic-inference/hota/scripts/gvapython/`

**Purpose:** GVAPython plugin that extracts the SEI-embedded frame number from each H.264 buffer before inference and adds it as `sei_frame_num` to the MQTT detection message.

The UUID used to identify the SEI payload is `12345678-1234-5678-1234-567812345678`. This matches the UUID used when the test videos were prepared with `ffmpeg`.
