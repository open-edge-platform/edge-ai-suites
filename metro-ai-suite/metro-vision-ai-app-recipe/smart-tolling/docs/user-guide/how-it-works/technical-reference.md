# Technical Reference

## 1. The Perception Layer

The core of the system is the **DLStreamer Pipeline Server**, which orchestrates
three parallel pipelines defined in `config.json`.

### 1.1 Pipeline Strategy

| Pipeline Name | Camera View | Primary Adapters | Key Models |
| :--- | :--- | :--- | :--- |
| **`toll-front`** | Front LPR | `sscape_adapter_lpr.py` | `vehicle-detection`, `license-plate-detection`, `PP-OCRv4` |
| **`toll-rear`** | Rear LPR | `sscape_adapter_lpr.py` | `vehicle-detection`, `license-plate-detection`, `PP-OCRv4` |
| **`toll-side1`** | Side Profile Lane 1 | `sscape_adapter_side.py` | **`axle_int8`**, `vehicle_type_model`, `color_int8` |
| **`toll-side2`** | Side Profile Lane 2 | `sscape_adapter_side.py` | **`axle_int8`**, `vehicle_type_model`, `color_int8` |

### 1.2 Algorithm Logic ("Under the Hood")

#### A. Smart Axle Counting (`sscape_adapter_side.py`)

Counting wheels is easy; counting *taxable* wheels is hard. Our adapter implements physics-based logic:

1. **IoU Deduplication:**
   - *Problem:* A slow-moving truck might trigger multiple detections for the same wheel.
   - *Solution:* We apply Intersection-over-Union (IoU) filtering. If extensive
     overlap (>40%) is detected between wheel bounding boxes, only the highest confidence detection is kept.

2. **Ground Contact Physics (Lift Axle Detection):**
   - *Problem:* Trucks often lift axles to save tires. These should not be taxed.
   - *Solution:* The algorithm calculates a dynamic "Ground Plane" `($Y_{ground}$)`
     based on the lowest points of the vehicle body and clearly grounded wheels.
   - *Logic:*

     ```text
     $$ Wheel_{status} = \begin{cases} Grounded, & \text{if } Y_{wheel\_bottom} \ge Y_{ground} - \text{Tolerance} \\ Lifted, & \text{otherwise} \end{cases} $$
     ```

   - *Result:* The payload reports `wheels_touching_ground` separately from `wheel_count`.

#### B. Multi-View Image Fusion & Optimizations

The system captures evidence from all angles to create a complete "Vehicle Package".
Instead of sending raw video streams, adapters encode "Evidence Crops" as
**Base64 strings** directly inside the JSON MQTT payload.

## 2. Performance & Optimization

The system achieves high-throughput processing on Edge hardware through specific optimizations defined in `config.json`.
The `docker-compose.yml` file mentions all the services and the pipelines are configured in `config.json` file.

### 2.1 Zero-Copy Video Pipeline

Unlike standard OpenCV pipelines that copy frames to CPU RAM, this solution utilizes **VASurface Sharing plugin**.

- **Mechanism:** Decoded video frames remain in GPU memory (`video/x-raw(memory:VAMemory)`).
- **Benefit:** Zero-copy inference eliminates PCIe bandwidth bottlenecks, reducing end-to-end latency by ~40%.
- **Config Evidence:** `pre-process-backend=va-surface-sharing` used in all `gvadetect` elements.

### 2.2 Dynamic ROI Inference (Hierarchical Execution)

To maximize efficiency, heavy neural networks (like Axle Counting) do not run on the full 4K frame.

- **Logic:** The "Vehicle Type" model runs first to find the bounding box.
- **Optimization:** The Axle model is configured with `inference-region=roi-list`,
  forcing it to execute *only* within the coordinates of the detected vehicle.
- **Impact:** Reduces pixel processing load by >80% for sparse traffic scenes.

### 2.3 Hybrid Workload Distribution

The pipeline intelligently maps models to available accelerators to prevent resource contention:

- **GPU (Flex Series):** Handles heavy convolution tasks (Vehicle Detection, LPR, Axle Counting).
- **CPU (Xeon):** Handles lighter classification tasks (Vehicle Color) and post-processing adapters (`gvapython`).

## 3. Analytics Pipeline (Downstream)

Raw metadata is valuable, but actionable insights come from the Analytics Pipeline.

### 3.1 Node-RED Transformation

- **Input:** The **MQTT IN Node** subscribes to `scenescape/event/region/+/+/objects`.
- **Logic:** The **Function node** aggregates counts per region and calculates **Dwell Time** (congestion).
- **Output:** The **InfluxDB OUT Node** writes normalized data points to InfluxDB.

![Node-RED Flow](../_assets/smart_tolling_nodered.png)

### 3.2 Storage (InfluxDB)

InfluxDB acts as a single source of truth. All critical and shared data is
stored in one location, ensuring every user and system accesses the same,
accurate and consistent information.

![InfluxDB Dashboard 1](../_assets/smart_tolling_influx_db.png)

### 3.3 Visualization (Grafana)

The system ships with a pre-configured dashboard (`anthem-intersection.json` schema)
focusing on Traffic Volume, Flow Efficiency and Safety Alerts.

![Grafana Dashboard 1](../_assets/garfana_Dashboard1.png)

## 4. API Reference

Integrators can subscribe to `scenescape/cmd/camera/#` for real-time events.
See the sample JSON Payload Schema (v2) below:

```json
{
  "id": "toll_side_1",
  "timestamp": "2026-02-03T12:00:00.000Z",
  "objects": {
    "vehicle": [
      {
        "id": 1,
        "vehicle_type": "truck",
        "confidence": 0.98,
        "bounding_box_px": { "x": 100, "y": 200, "width": 500, "height": 300 },

        "axle_count": 3,
        "wheel_count": 6,
        "wheels_touching_ground": 4,  // 1 Lift Axle detected!

        "vehicle_color": "white",
        "vehicle_image_b64": "..."    // High-res crop for audit
      }
    ]
  }
}
```

## Summary of Data Flow

- Video loops or RTSP is fed into DL Streamer.
- Trained AI models detect vehicles and license plates.
- Metadata is published to MQTT.
- SceneScape maps detections to scene regions to get exact location of objects on the scene.
- Exit events are generated when vehicles leave the region.
- Node-RED processes only finalized exit events by subscribing to SceneScape topics.
- Data is written to InfluxDB for system to access for consistent information.
- Grafana visualizes real time and historical data enabling access to metrics and vehicle details.
