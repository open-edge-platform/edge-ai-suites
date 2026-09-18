<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Detection Output Contract

## Wire format

Published to `uav/{uav_id}/camera/{cam}/detections`, QoS 0, one message per frame that
produced at least one detection. Frames with zero detections publish nothing — absence of a
message is not a heartbeat failure.

```json
{
  "timestamp": 1758038400.123,
  "camera_id": "nadir",
  "frame_id": 1482,
  "objects": [
    {
      "detection": {
        "bounding_box": {
          "x_min": 0.3125, "y_min": 0.4010,
          "x_max": 0.5240, "y_max": 0.6133
        },
        "label": "vehicle",
        "confidence": 0.8
      }
    }
  ]
}
```

- Coordinates are **normalised 0–1**, rounded to 4 decimals, origin top-left.
- `timestamp` is `time.time()` float seconds (Unix epoch), not ISO-8601 — unlike the
  telemetry topics, which use ISO-8601. Consumers reading both must handle each separately.
- `frame_id` is a per-camera monotonic counter that **resets to 0 on every pipeline rebuild**
  (i.e. on each disarm→arm cycle). It is not globally unique.
- The `objects[].detection` nesting mirrors DL Streamer's own JSON convention; keep it if you
  want existing consumers (`edge-ai-showcase`) to keep working.

## Current producer is lossy

`_detect_boxes_from_watermark()` (`detector_multicam_rtsp.py:248`) does not read inference
metadata. It thresholds the drawn watermark:

```python
lower_blue = np.array([100, 150, 150])
upper_blue = np.array([130, 255, 255])
```

then keeps contours passing all of: `area >= 500 px²`, `0.3 < w/h < 3.5`, `w > 30 and h > 30`,
and centre at least 5 % inside each frame edge. `label` and `confidence` are then **hard-coded**
to `"vehicle"` and `0.8`.

So the published `confidence` carries no information, and `CONF_THRESH` influences output only
indirectly — by controlling which boxes `gvadetect` asks `gvawatermark` to draw in the first place.

## Reading real GVA metadata instead

When the task needs true labels, per-object confidence, multi-class output, or tracking IDs,
replace the watermark parser with metadata extraction in the appsink callback.

> **Unverified against this tree.** `gstgva` ships only inside
> `intel/dlstreamer:2026.1.0-ubuntu24` (the vision-processor base image) and is not importable
> on the host, so the snippet below is written from the DL Streamer API rather than checked
> here. Confirm the accessor names before relying on them:
>
> ```bash
> docker run --rm intel/dlstreamer:2026.1.0-ubuntu24 \
>   python3 -c "from gstgva import VideoFrame; from gstgva.region_of_interest import RegionOfInterest; print([m for m in dir(RegionOfInterest) if not m.startswith('_')])"
> ```

```python
from gstgva import VideoFrame

def _on_new_sample(self, sink, _):
    sample = sink.emit("pull-sample")
    buf = sample.get_buffer()
    caps = sample.get_caps()

    objects = []
    for region in VideoFrame(buf, caps=caps).regions():
        rect = region.normalized_rect()       # already 0-1
        objects.append({
            "detection": {
                "bounding_box": {
                    "x_min": round(rect.x, 4),
                    "y_min": round(rect.y, 4),
                    "x_max": round(rect.x + rect.w, 4),
                    "y_max": round(rect.y + rect.h, 4),
                },
                "label": region.label(),
                "confidence": round(region.confidence(), 4),
            }
        })
```

Notes when switching:

- `gvawatermark` becomes optional for the detection path. Keep it only if the annotated
  `.../processed` JPEG is still wanted; metadata survives the watermark element either way.
- Drop the `video/x-raw,format=BGR` conversion before appsink if you no longer need pixels —
  it costs a full-frame convert per frame.
- Add `gvatrack` between `gvadetect` and `gvawatermark` for persistent object IDs, then emit
  `region.object_id()` so downstream consumers can count unique objects rather than per-frame
  detections.
- Verify `model-proc` actually declares the label list. Without a correct `model-proc`,
  `region.label()` returns class indices as strings rather than names.

## Downstream consumers

`sample-apps/edge-ai-showcase/app.py` subscribes to these topics and renders boxes. Changing
the schema — including adding real labels where `"vehicle"` was assumed — may require updating
the dashboard's rendering and any label-based filtering alongside it.
