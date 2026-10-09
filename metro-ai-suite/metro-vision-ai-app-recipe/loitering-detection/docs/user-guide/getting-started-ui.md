# Getting started - Loitering Detection Console UI

The Loitering Detection Console is the sample application's operator UI: a single page to
start/stop video analytics streams, pick a model and device, draw an evaluation zone, and watch
live per-object loitering analytics without going through Grafana or the DL Streamer Pipeline
Server's REST API directly.

## Prerequisites

- Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
  Enable running docker without "sudo": [Post Install](https://docs.docker.com/engine/install/linux-postinstall/)
- Install Git: [Installing Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

## Set up and first use

1. **Clone the Suite**:

   ```bash
   git clone --filter=blob:none --sparse --branch gg/ld-ui https://github.com/guptagunjan/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/metro-vision-ai-app-recipe/
   ```

2. **Setup Application and Download Assets**:
   - Use the installation script to configure the application and download required models:

     ```bash
     ./install.sh loitering-detection
     ```

   > [!NOTE]
   > For environments requiring a specific host IP address (for example, when deploying across different network interfaces), you can explicitly
   > specify the IP address: `./install.sh loitering-detection <HOST_IP>` (Replace `<HOST_IP>` with
   > your target IP address.)

## Run the application

1. **Start the Application**:
   - Download container images with Application microservices and run with Docker Compose:

     ```bash
     docker compose up -d
     ```

     <details>
     <summary>
     Check Status of Microservices
     </summary>
     - The application starts the following microservices.
     - To check if all microservices are in Running state:

          docker ps

     **Expected Services:**
     - Grafana Dashboard
     - DL Streamer Pipeline Server
     - MQTT Broker
     - Loitering Detection Console (operator UI)

     </details>

2. **Access the Console UI**:
   - Open a browser and go to `https://localhost/console/` to access the Console UI.
     - Change `localhost` to your host IP if you are accessing it remotely.

3. **Starting pipelines** (required):
   - **Number of pipelines** defaults to 1, each with its own **Pipeline N** card below it for
     **Source**, **Model** and **Device** - all pre-filled with working defaults, so you can
     click **Start pipelines** right away to see video with live detections - no field needs to
     be touched first. Raise **Number of pipelines** to add more cards (e.g. to compare two
     models on the same source side by side).
   - Each pipeline gets its own panel titled **Pipeline N · model · device**, with a live WebRTC
     view and a per-object loiter table underneath it. Clicking a card's header collapses or
     expands just that card - useful for focusing on one section at a time on a short screen.
   - Need a different zone first? See [Changing the zone](#changing-the-zone) below - zones are
     set by drawing on a pipeline's video after it starts, not from the rail.

## Customization

### Number of pipelines

Raising **Number of pipelines** (1-8) adds one **Pipeline N** card per unit increase, each a
fully independent pipeline with its own Source/Model/Device - every pipeline you start becomes
its own DL Streamer Pipeline Server instance and its own panel, so they can run different
sources, models or devices at once, or the exact same ones for a true side-by-side comparison.
Lowering the count removes the trailing card(s); an already-started pipeline that corresponded
to a removed card keeps running until you **Stop** (Click `X` on right most corner of indidual stream window) it or **Stop all** - lowering the count only
affects what the next **Start pipelines** click will create.

**Start pipelines** only launches cards that are not already running - a card linked to a live
pipeline is marked **Running** next to its title and is left alone. So after starting
Pipeline 1 and 2, raising the count to add Pipeline 3 and clicking **Start pipelines** again
starts only Pipeline 3; it does not relaunch (duplicate) the pipelines already running. To
restart a card that is already running, **Stop** its panel first, then click **Start pipelines**
again.

A newly added card defaults to the **first** source and model in their dropdowns and GPU (if
available) for device - the same defaults every card gets, not a copy of another card's current
selection - so two freshly added pipelines start out identically configured. Change the fields
you want to differ (typically **Model**, to compare) before clicking **Start pipelines**; only
one card expands at a time (click another card's header to switch to it).

### Example: comparing two models side by side

1. Set **Number of pipelines** to `2`. A **Pipeline 2** card appears below **Pipeline 1**,
   defaulted to the same source/model/device as pipeline 1.
2. Expand **Pipeline 1** and pick the first model you want to compare (e.g. the default
   `pedestrian-and-vehicle-detector-adas-0001`) and its **Source** and **Device**.
3. Expand **Pipeline 2**. Set its **Source** to the *same* video as Pipeline 1 (so both
   pipelines see identical input) and its **Model** to the second model you want to compare
   (e.g. `yolo11s` - see [Adding a model to compare](#adding-a-model-to-compare) if it is not
   listed yet). Leave **Device** as-is, or change it too if you also want to compare devices
   rather than just models.
4. Click **Start pipelines**. Two panels appear side by side, titled
   **Pipeline 1 · pedestrian-and-vehicle-detector-adas-0001 (FP16) · GPU** and
   **Pipeline 2 · yolo11s (FP16) · GPU** - same video, different model's boxes/labels/loiter
   table underneath each, so you can judge recall and false positives side by side on identical
   input.
5. To compare a third model, raise **Number of pipelines** to `3` and repeat step 3 for the new
   **Pipeline 3** card before clicking **Start pipelines** again - pipelines 1 and 2 keep running
   unaffected; only the newly started one is added alongside them.

### Changing the video, model or device

Each pipeline card has its own:
- **Source**: pick a bundled sample video from the **Camera / stream** dropdown, or type an
  RTSP URL instead. The RTSP field takes priority when filled in. See
  [Changing the video source](#changing-the-video-source) below to add another bundled option.
- **Model**: choose the model to run. See [Adding a model to compare](#adding-a-model-to-compare)
  below to add another option - with two or more pipelines you can run different models on the
  same source side by side for comparison.
- **Device**: CPU, GPU or NPU. GPU is pre-selected because it gives the best throughput on
  most deployments; switch it if your hardware or model does not support that device.
- **Pipeline configuration**: for how Start/Stop map to DL Streamer Pipeline Server REST calls
  and element properties, see [Updating the Pipeline](./how-to-guides/update-pipelines.md).

### Adding a model to compare

The **Model** dropdown lists whatever is under the mounted model store
(`loitering-detection/src/dlstreamer-pipeline-server/models/`) as `<model>.xml` + `<model>.bin`
pairs, with an optional `<model>.json` model_proc beside them. Drop a new model's files into
that folder using the same layout and click the refresh button (&#x27F3;) next to **Model** -
no restart or code change is needed. A model whose IR has a dynamic input shape is still listed
but flagged, since GPU and NPU reject that shape and returns no detections for it;
re-export the model with a fixed input size to use it on every device.

### Changing the video source

Add a source to the **Camera / stream** dropdown by adding an entry to `SOURCES_JSON` in
`console-addon/.env` (id, label, and a `file://` or `rtsp://` URI), then restart the `console`
service. For a one-off source there is no need to edit anything - use the RTSP field instead.

### Changing the zone

The Zone (ROI) card has no manual coordinate entry - check **Draw zone on video**, pick
**Rectangle (drag)** or **Polygon (click points)**, then draw directly on a running pipeline's
video. The shape previews there until you apply it with either **Apply to this pipeline**
(appears on the pipeline you drew on) or the card's **Apply zone to live pipelines** (every live
pipeline). Either way it replaces that pipeline's zones entirely with the shape you drew, under
the id `OperatorZone` - `gvaanalytics` evaluates one zone set or the other, never both. Starting
a new pipeline without drawing anything first keeps the deployment's own zone file exactly as
configured.

Polygon and multi-zone support exists in `gvaanalytics` and is used by the file's own zones:
`loitering-detection/src/dlstreamer-pipeline-server/configs/loitering_analytics_config.json` can
define any number of zones, each a rectangle or an arbitrary polygon - see the
[upstream sample's config](https://github.com/open-edge-platform/dlstreamer/blob/main/samples/gstreamer/gst_launch/python-elements/loitering_detection/virat_s_000101-config.json)
for the schema. Its contents are read fresh on every pipeline start (not baked into the
pipeline), so editing the file takes effect on the next **Start pipelines** - no service restart
needed. Once a pipeline has been switched to a custom zone there is no UI action to switch it
back to the file's zones; stop it and start a new one instead.

## How detection and zones interact

Detection and tracking (`gvadetect`/`gvatrack`) always run on the full frame, and `gvawatermark`
draws a box for every detected object - zones do not affect what gets boxed on screen.
`gvaanalytics` separately matches each tracked object's position against whichever zone set is
active for that session - the file's zones by default, or a single custom `OperatorZone`
rectangle once the operator customises it (never both at once, see
[Changing the zone](#changing-the-zone)) - and draws each zone's outline in its configured color
(e.g. the sample config's `Pathway` in red and `Driveway` in cyan; `OperatorZone` draws in green
since the console does not set a color for it). Only objects matched to at least one zone appear
in the table below and count toward that stream's dwell/loiter stats; an object outside every
zone is still detected and boxed, it just never shows up there.

A box missing on an object that does look like it should be detected usually means the model
itself did not detect it that frame (confidence below the pipeline's threshold) — check the
stream's raw MQTT topic if this needs confirming, or try the `yolo11s` model, which may have
better recall for some object types/angles than the default
`pedestrian-and-vehicle-detector-adas-0001`.

## Reading the panel

- **fps / objects / max dwell / loiter** summarise the stream: they count every object currently
  inside the session's active zone set (the config file's zones by default, or the custom
  `OperatorZone` rectangle once customised), not everything detected in the frame.
- The table below it lists every object currently inside any of those zones:
  - **Object ID** — the tracker's id for this object.
  - **Type** — the detected class (e.g. `pedestrian`).
  - **Zone** — every zone id this object currently matches (e.g. `Pathway, Driveway` if a
    track spans both polygons), so you can tell which zone(s) a row's dwell time is coming from
    when more than one file zone is active at once. Only ever shows `OperatorZone` once a
    custom rectangle has replaced the file's zones.
  - **Status** — `Present` below the loiter threshold shown under the Zone card, `Loitering`
    at or above it.
  - **Entry Time** — fixed at first sighting; does not change as dwell grows.
  - **Dwell (s)** — `gvaanalytics`'s own measurement for the longest-running zone the object is
    currently in. This is the same figure Grafana reports.
- **System Utilization** reports host-wide CPU/GPU/NPU/memory load, not per-stream load; the
  GPU sub-line breaks down per-engine ratios (`bcs`/`ccs`/`rcs`/`vcs`/`vecs`) as percentages.

## Troubleshooting

See [Troubleshooting the Console UI](./troubleshooting.md#troubleshooting-the-console-ui) for
UI-specific issues (missing bounding boxes, zone edits, stuck/silent streams).

