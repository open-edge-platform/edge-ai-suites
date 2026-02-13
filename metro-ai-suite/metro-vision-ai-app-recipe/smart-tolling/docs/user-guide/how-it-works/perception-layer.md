# The Perception Layer

The core of the system is the **DLStreamer Pipeline Server**, which orchestrates
three parallel pipelines defined in `config.json`.

## Pipeline Strategy

| Pipeline Name | Camera View | Primary Adapters | Key Models |
| :--- | :--- | :--- | :--- |
| **`toll-front`** | Front LPR | `sscape_adapter_lpr.py` | `vehicle-detection`, `license-plate-detection`, `PP-OCRv4` |
| **`toll-rear`** | Rear LPR | `sscape_adapter_lpr.py` | `vehicle-detection`, `license-plate-detection`, `PP-OCRv4` |
| **`toll-side1`** | Side Profile Lane 1 | `sscape_adapter_side.py` | **`axle_int8`**, `vehicle_type_model`, `color_int8` |
| **`toll-side2`** | Side Profile Lane 2 | `sscape_adapter_side.py` | **`axle_int8`**, `vehicle_type_model`, `color_int8` |

## Algorithm Logic

### A. Smart Axle Counting (`sscape_adapter_side.py`)

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

### B. Multi-View Image Fusion & Optimizations

The system captures evidence from all angles to create a complete "Vehicle Package".
Instead of sending raw video streams, adapters encode "Evidence Crops" as
**Base64 strings** directly inside the JSON MQTT payload.

## Learn More

- [Optimizations](./optimization.md)
- [Analytics Pipeline](../how-it-works.md)
- [Support and Troubleshooting](../troubleshooting.md)
