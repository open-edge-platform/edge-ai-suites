# API Reference

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
