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

3. **Starting a stream** (required):
   - **Source**, **Model** and **Device** are already pre-filled with working defaults, so you
     can click **Start stream** right away to see video with live detections - no field needs
     to be touched first.
   - Each stream gets its own panel with a live WebRTC view and a per-object loiter table
     underneath it. Clicking a card's header (**Source**, **Model**, **Zone (ROI)**) collapses
     or expands just that card - useful for focusing on one section at a time on a short screen.
   - Need a different video, model, device or zone first? See
     [Customization](#customization) below for what each field does and how to add more
     options - **Model compare (side-by-side)** and **Zone (ROI)** are covered there too.

## Customization

### Changing the video, model or device

- **Source**: pick a bundled sample video from the **Camera / stream** dropdown, or type an
  RTSP URL instead. The RTSP field takes priority when filled in. See
  [Changing the video source](#changing-the-video-source) below to add another bundled option.
- **Model**: choose the **Primary model** to run. Checking **Model compare (side-by-side)**
  starts a second panel with a different model on the same source, so you can judge two
  models against each other on identical input. See
  [Adding a model to compare](#adding-a-model-to-compare) below to add another option.
- **Device**: CPU, GPU or NPU. GPU is pre-selected because it gives the best throughput on
  most deployments; switch it if your hardware or model does not support that device.
- **Zone**: see [Changing the zone](#changing-the-zone) below.
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

The rail's four fields are a **rectangle** in source-video pixels, labelled directly above each
box so there is no guessing which field is which:

| Field | Meaning |
| --- | --- |
| `x` | left edge of the rectangle, in source-video pixels |
| `y` | top edge of the rectangle, in source-video pixels |
| `w` | width of the rectangle, in source-video pixels |
| `h` | height of the rectangle, in source-video pixels |

Hovering the &#9432; next to **Zone (ROI)**, or any individual field, shows the same
explanation. The fields are pre-filled from the deployment's own zone file purely for
reference - **starting a stream without touching them keeps that file's zones exactly as
configured**. Editing a field, checking **Draw zone on video** and dragging a box on a running
stream, or clicking **Apply zone to live streams**, all switch the session to a single custom
rectangle under the id `OperatorZone` that **entirely replaces** the file's zones rather than
being added alongside them - `gvaanalytics` evaluates one zone set or the other, never both.
**Apply zone to live streams** lights up once the values differ from what is currently running,
and applying restarts every live stream with the new zone (`gvaanalytics` has no in-place zone
update).

Polygon and multi-zone support exists in `gvaanalytics` and is used by the file's own zones:
`loitering-detection/src/dlstreamer-pipeline-server/configs/loitering_analytics_config.json` can
define any number of zones, each a rectangle or an arbitrary polygon - see the
[upstream sample's config](https://github.com/open-edge-platform/dlstreamer/blob/main/samples/gstreamer/gst_launch/python-elements/loitering_detection/virat_s_000101-config.json)
for the schema. Its contents are read fresh on every stream start (not baked into the pipeline),
so editing the file takes effect on the next **Start stream** - no service restart needed. Once
a session has been switched to a custom rectangle there is no UI action to switch it back to the
file's zones; stop the stream and start a new one instead.

## How detection and zones interact

Detection and tracking (`gvadetect`/`gvatrack`) run on the full frame so that an object's track
stays continuous even while it is outside every zone. `gvaanalytics` then matches each tracked
object's position against whichever zone set is active for that session - the file's zones by
default, or a single custom `OperatorZone` rectangle once the operator customises it (never
both at once, see [Changing the zone](#changing-the-zone)) - and draws each zone's outline in
its configured color (e.g. the sample config's `Pathway` in red and `Driveway` in cyan;
`OperatorZone` draws in green since the console does not set a color for it). A pipeline stage
right after that only keeps the bounding box of objects matched to at least one zone, so **the
video only highlights objects that are inside a zone outline** — an object outside every drawn
zone is tracked internally but is not boxed on screen and does not appear in the table below.

A box missing on an object that does look like it is inside a zone outline usually means the
model itself did not detect it that frame (confidence below the pipeline's threshold), not that
the zone logic dropped it — check the stream's raw MQTT topic if this needs confirming, or try
the `yolo11s` model, which may have better recall for some object types/angles than the default
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

