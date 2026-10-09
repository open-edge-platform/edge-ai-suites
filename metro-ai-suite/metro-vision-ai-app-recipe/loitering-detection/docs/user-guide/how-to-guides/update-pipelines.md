# Updating the Pipeline

The loitering detection pipeline is a DL Streamer Pipeline Server pipeline: a GStreamer
`gst-launch`-style string plus a small REST-overridable parameters schema, both defined in one
JSON file. This guide covers where it lives, what each stage does, and how to change it safely.

## Where it lives

- **File**: `loitering-detection/src/dlstreamer-pipeline-server/config.json`
- **Custom Python stages**: `loitering-detection/src/dlstreamer-pipeline-server/configs/*.py`
  (loaded by `gvapython` elements named in the pipeline string)
- **Zone definitions**: `loitering-detection/src/dlstreamer-pipeline-server/configs/loitering_analytics_config.json`

All three are bind-mounted (`:ro`) into the `dlstreamer-pipeline-server` container (see
`compose-without-scenescape.yml`), so editing them on the host and recreating that one container
is enough - no image rebuild:

```bash
docker compose up -d --force-recreate dlstreamer-pipeline-server
```

`config.json` is only read at container start, so this restart is required even for a small
pipeline-string edit; it also drops every currently-running stream (CLI and Console UI alike).

## Structure of config.json

```json
{
  "config": {
    "pipelines": [
      {
        "name": "object_tracking_gpu",
        "source": "gstreamer",
        "pipeline": "{auto_source} name=source ! ... ! appsink name=destination",
        "parameters": {
          "type": "object",
          "properties": {
            "detection-properties": { "element": { "name": "detection", "format": "element-properties" } }
          }
        }
      }
    ]
  }
}
```

- One object per **device variant** - this app defines `object_tracking_cpu`, `object_tracking_gpu`,
  `object_tracking_npu`, selected by whichever `device` the caller (Console UI or `sample_start.sh`)
  asked for.
- `pipeline` is the actual GStreamer pipeline, written exactly like a `gst-launch-1.0` command
  line. `{auto_source}` is substituted by the Pipeline Server for whatever `source.type`/`source.uri`
  the REST request supplies (a file or RTSP URL here).
- `parameters.properties` declares which elements can have properties overridden **per REST
  request**, by name. Each entry maps a request-time key (e.g. `"detection-properties"`) to a
  pipeline element `name=...` and its GObject property, letting one static pipeline definition
  serve many different models/zones/devices without editing the file per request.

## The pipeline stage-by-stage

```
{auto_source} ! <decode> ! gvadetect ! gvatrack ! gvaanalytics ! gvametaconvert ! gvawatermark ! appsink
```

| Stage | Purpose |
| --- | --- |
| `decodebin3` (CPU) / `parsebin ! vah264dec ! vapostproc` (GPU/NPU) | Decode the source video; GPU/NPU decode into `video/x-raw(memory:VAMemory)` for hardware-accelerated inference. |
| `gvadetect` | Runs the detection model on the **full frame** |
| `gvatrack tracking-type=zero-term` | Assigns/keeps a stable id per object across frames. |
| `gvaanalytics evaluation-point=bottom-center draw-zones=true` | Matches each tracked object against the active zone(s) (polygons from the zone file, or a custom rectangle - see below), computes dwell time, and draws the zone outline(s). This is the only zone-awareness in the pipeline - it decides what counts toward the loiter table, not what gets boxed. |
| `gvametaconvert add-empty-results=false` | Serialises detections + zone/dwell info into the JSON published to MQTT. |
| `gvawatermark` | Draws a labelled box for **every** detected object, zone or not. |
| `appsink` | Hands frames+metadata to the Pipeline Server, which fans them out to the configured destinations (MQTT for metadata, WebRTC for video). |

## What overrides what, per request

Both the Console UI (`console-addon/console/api_pipelines.py`, function `_launch`) and the CLI
sample (`sample_start.sh`) call `POST /pipelines/{name}/{version}` with a `parameters` object
matching `config.json`'s schema:

| Request key | Element it targets | What it sets |
| --- | --- | --- |
| `detection-properties` | `detection` (`gvadetect`) | `model`, `device`, `model-instance-id`, `model_proc` |
| `analytics-properties` | `analytics` (`gvaanalytics`) | `zones` - the file's zones, or a single custom rectangle, never both (see [Getting started - Loitering Detection Console UI](../getting-started-ui.md#changing-the-zone)) |

There is **no live-update path**: changing any of these (switching model, device, or zone)
always stops the current pipeline instance and starts a brand new one with the new parameters -
confirmed in `dlstreamer-pipeline-server`'s own logs, where a zone/model change shows as a
`Pipeline <old-id> Ended` / `Aborted` line immediately followed by a new
`Creating Instance of Pipeline user_defined_pipelines/<name>` with a different instance id.

## Adding or changing a stage

1. Edit the `pipeline` string for the device variant(s) you want to change - keep the three
   variants (CPU/GPU/NPU) consistent unless the change is genuinely device-specific.
2. If the new/changed element needs to be overridable per request, add it to every pipeline's
   `parameters.properties` with a unique `element.name` matching a `name=...` you gave it in the
   `pipeline` string.
3. For a new `gvapython` stage, drop the `.py` file under `configs/` (already bind-mounted) and
   reference it with `module=/home/pipeline-server/configs/<file>.py class=<ClassName>`.
4. Recreate the container (see above) and verify with:

   ```bash
   docker logs dlstreamer-pipeline-server --tail 50
   ```

   A malformed pipeline string fails loudly here at container start, before any stream is ever
   requested.

## Related

- [Getting started - Loitering Detection Console UI](../getting-started-ui.md) - the operator-facing side of zones/models/devices.
- `loitering-detection/sample_start.sh` - the CLI equivalent of the Console UI's `_launch`, useful
  as a second working reference for the same `parameters` schema.
