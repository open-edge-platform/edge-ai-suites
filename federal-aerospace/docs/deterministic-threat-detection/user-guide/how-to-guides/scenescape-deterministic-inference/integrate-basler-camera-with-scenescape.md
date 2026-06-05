# Set Up SceneScape with Basler GigE Camera and PTP Support

## Choose a Camera That Supports PTP
Use a Basler GigE camera model that supports IEEE 1588v2 PTP hardware timestamping. The Basler ace U series (for example, acA1920-40GC) is a validated option.

## Configure the Basler Camera with PTP Support

The Basler camera only supports IEEE 1588v2 over UDP, so the switch and host must be configured for that profile. Follow the guides below before continuing:

- [Configure MOXA Switch and Host for IEEE 1588v2](./configure-ptp-1588v2.md)
- [Configure the Basler Camera to Use PTP Timestamps](./configure-basler-ptp-timestamps.md)

## Set Up SceneScape with Basler GigE Support

### Step 1: Clone SceneScape

```bash
git clone https://github.com/open-edge-platform/scenescape --branch 2026.1.0-rc2
cd scenescape
```

---

### Step 2: Build the DL Streamer Pipeline Server Image with Basler Support

The standard DL Streamer Pipeline Server image does not include the Basler pylon SDK or the `gencamsrc` GStreamer plugin. Follow the instructions below to build a custom image:

[Integrate Pylon SDK — Step 2: Create the Docker Image](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/manufacturing-ai-suite/industrial-edge-insights-vision/docs/user-guide/pallet-defect-detection/how-to-guides/integrate-pylon-sdk.md#step-2-create-the-docker-image)

> **Note:** Patch `gencamsrc` to propagate the PTP timestamp before building the image. By default, `gencamsrc` discards the camera's PTP hardware timestamp after setting the GStreamer buffer PTS. The following patch adds a `GstReferenceTimestampMeta` to each buffer so downstream elements such as `gvapython` can read the original camera timestamp before any clock correction occurs.

```bash
git -C /path/to/edge-ai-libraries apply \
  /path/to/deterministic-threat-detection/usecases/scenescape-deterministic-inference/basler/patches/genicam.patch
```

---

### Step 3: Update the Docker Compose Image Reference

After the image build completes, update `sample_data/docker-compose-dl-streamer-example.yml` so the `queuing-video` service uses your custom Basler-enabled image.

```yaml
services:
  queuing-video:
    image: <your-basler-enabled-image>:<tag>
```

---

### Step 4: Patch Docker Compose to Add a macvlan Network

The Basler GigE camera is connected to the private TSN switch network, while Docker containers use a bridge network by default. A macvlan network bridges the two, giving the `queuing-video` container a routable address on the camera subnet, for the Basler GigE camera detection to work correctly.

Apply the patch to your SceneScape checkout:

```bash
git -C /path/to/scenescape apply \
  /path/to/deterministic-threat-detection/usecases/scenescape-deterministic-inference/basler/patches/macvlan_docker.patch
```

> **Note:** Edit the patched `docker-compose-dl-streamer-example.yml` to set the correct host NIC name (default: `enp5s0.1`) and IP address (`192.168.127.51`) for the macvlan interface to match your network configuration.

---

### Step 5: Patch `sscape_adapter` to Publish the PTP Timestamp

The `sscape_adapter.py` patch extracts the `GstReferenceTimestampMeta` added by the patched `gencamsrc` and uses the camera PTP timestamp as the frame `timestamp` field in the SceneScape MQTT message. Without this patch, the adapter falls back to the post-decode software timestamp.

Apply the patch to your SceneScape checkout:

```bash
git -C /path/to/scenescape apply \
  /path/to/deterministic-threat-detection/usecases/scenescape-deterministic-inference/basler/patches/sscape_adapter.patch
```

---

### Step 6: Configure the GStreamer Pipeline

Update the pipeline definition in SceneScape (eg: `dlstreamer-pipeline-server/queuing-config.json`) to use `gencamsrc` as the source and insert the `gvapython` timestamp capture element before inference. Note down the serial number of your Basler camera and substitute it for `<basler-camera-serial>`:

```text
gencamsrc serial=<basler-camera-serial> pixel-format=bayerrggb frame-rate=10 name=source ! bayer2rgb ! videoscale ! video/x-raw,width=1920,height=1080 ! videoconvert ! video/x-raw,format=BGR ! gvapython class=PostDecodeTimestampCapture function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=timesync ! gvadetect model=/home/pipeline-server/models/intel/person-detection-retail-0013/FP32/person-detection-retail-0013.xml model-proc=/home/pipeline-server/models/object_detection/person/person-detection-retail-0013.json ! gvametaconvert add-tensor-data=true name=metaconvert ! gvapython class=PostInferenceDataPublish function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=datapublisher ! gvametapublish name=destination ! appsink sync=true
```

> **Tip:** SceneScape tracking quality depends on the camera feed. You can either configure the camera for your real-world scene or point the camera at a monitor that plays the queuing demo video. The monitor-based setup is often the quickest way to validate Basler camera tracking behavior.
