# Guide: Testing Worker Safety Gear Detection Application Using Balluff SDK

This guide explains how to create a custom Docker image based on the Intel DL Streamer Pipeline Server, with Balluff SDK and Gencamsrc support. It supports Balluff, Basler, and other GenICam-compatible cameras over USB and GigE interfaces.

Note: You may observe a watermark in the camera feed when testing with a non-Balluff camera, as it is the free version.

---

## Prerequisites

- [System Requirements](system-requirements.md)

---

## Cloning and building the docker image

### Step 1: Base Image and User Setup
Download the edge-ai-libraries source and go to `dlstreamer-pipeline-server` folder

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git
cd edge-ai-libraries/microservices/dlstreamer-pipeline-server
```

---

### Step 2: Create the Docker Image

Create a Docker file named `BalluffDockerfile` inside your `dlstreamer-pipeline-server` directory with the following content.

```dockerfile
FROM intel/dlstreamer-pipeline-server:2025.2.0-ubuntu24

USER root

RUN apt-get update && apt-get install -y wget gnupg gstreamer1.0-plugins-base libxcb-cursor0 make autoconf vim libgstreamer-plugins-base1.0-dev libgstreamer1.0-dev g++-11 g++ && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

COPY ./thirdparty/install_gencamsrc_gstreamer_plugin.sh /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh

COPY ./plugins/camera/src-gst-gencamsrc /home/pipeline-server/src-gst-gencamsrc

RUN chmod +x /home/pipeline-server/src-gst-gencamsrc/setup.sh
RUN chmod +x /home/pipeline-server/src-gst-gencamsrc/autogen.sh
RUN chmod +x /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh
RUN /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh

# For Ubuntu24 intel/dlstreamer-pipeline-server:3.1.0-ubuntu24 base image
RUN apt-get update && apt-get install -y libwxgtk-webview3.2-dev

# For Ubuntu 22 with intel/dlstreamer-pipeline-server:3.1.0-ubuntu22, uncomment the line below and comment the above line
# RUN apt-get update && apt-get install -y libwxgtk-webview3.0-gtk3-dev

RUN mkdir /home/pipeline-server/Balluff_Impact_Acquire_V3
RUN wget https://assets-2.balluff.com/mvIMPACT_Acquire/3.0.0/install_mvGenTL_Acquire.sh -P /home/pipeline-server/Balluff_Impact_Acquire_V3
RUN wget https://assets-2.balluff.com/mvIMPACT_Acquire/3.0.0/mvGenTL_Acquire-x86_64_ABI2-3.0.0.tgz -P /home/pipeline-server/Balluff_Impact_Acquire_V3
RUN cd Balluff_Impact_Acquire_V3 && chmod +x ./install_mvGenTL_Acquire.sh && ./install_mvGenTL_Acquire.sh -u3v -gev -u

ENV MVIMPACT_ACQUIRE_DIR="/opt/mvIMPACT_Acquire" \
    MVIMPACT_ACQUIRE_DATA_DIR="/opt/mvIMPACT_Acquire/data" \
    GENICAM_ROOT="/opt/mvIMPACT_Acquire/runtime" \
    MVIMPACT_ACQUIRE_FAVOUR_SYSTEMS_LIBUSB="1" \
    GENICAM_GENTL64_PATH=/opt/Impact_Acquire/lib/x86_64 \
    GST_PLUGIN_PATH=/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/gstreamer/lib/gstreamer-1.0:/opt/intel/dlstreamer/gstreamer/lib/:/usr/lib/x86_64-linux-gnu/gstreamer-1.0:/usr/local/lib/gstreamer-1.0

USER intelmicroserviceuser
```

---

### Step 3: Build the Docker Image

Run the following command to build the image:

```bash
docker build -t intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-balluff -f BalluffDockerfile .
```

This command builds your Docker image using the steps defined above.

---

### Step 4: Verify the Image

After the build completes, update .env and start the container:

> update .env DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-balluff

```bash
docker compose up -d
```

---

### Step 5: Run a test pipeline and dump the camera output into a file in the /tmp directory

Note down serial number of the balluff camera and update `<balluff-camera-serial>` in the following command
```bash
docker exec -it dlstreamer-pipeline-server bash
$ gst-launch-1.0 gencamsrc serial=<balluff-camera-serial> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! queue ! jpegenc ! avimux ! filesink location=/tmp/gencam_balluff_output.avi
```

Verify that the /tmp/gencam_balluff_output.avi has the captured content

---

## Deploying the Worker Safety Gear Detection Application Using live camera

This guide provides detailed, step-by-step instructions for setting up and deploying the **Worker Safety Gear Detection** pipeline to use the **Balluff** or **Basler** camera connected over USB or GigE.
It covers environment setup, configuration updates, and validation steps to ensure a successful deployment.

---

### Step 1: Set Up the Environment

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b release-2025.2.0
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision
cp .env_worker_safety_gear_detection .env
```

---

### Step 2: Configure the .env File

Update the `.env` file with the newly created image as below and modify any other required variables.

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-balluff
```

---

### Step 3: Run the Setup Script

Execute the setup script to initialize project directories and configurations.

```bash
./setup.sh
```
---

### Step 4: Update the Pipeline Configuration

Update the pipeline in `./apps/worker-safety-gear-detection/configs/pipeline-server-config.json` to use the camera:

```json
{
    "name": "worker_safety_gear_detection",
    "source": "gstreamer",
    "queue_maxsize": 50,
    "pipeline": "gencamsrc serial=<camera id> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=640, height=480 ! videoconvert ! gvadetect name=detection model-instance-id=inst0 ! gvametaconvert add-empty-results=true name=metaconvert ! queue ! gvafpscounter ! gvawatermark ! appsink name=destination"
}
```

Replace <camera id> with balluff/balser camera id connected over the USB or GigE

---

### Step 5: Configure docker-compose.yml (Optional, if testing with a GigE network camera)

When testing with a GigE camera, you need to adjust the `docker-compose.yml` configuration for all the services. Follow these steps:

1. Add `network_mode` set to `"host"`.
2. Remove the `networks` section.

The configuration for each service should look like this:

```yaml
services:
  service_name:
    .
    .
    network_mode: "host"
    # networks:
    #   - mraas
```

Additionally, add the following entries to the `/etc/hosts` file on the host machine:

```bash
127.0.0.1       dlstreamer-pipeline-server
127.0.0.1       prometheus
127.0.0.1       mediamtx-server
127.0.0.1       mraas-minio
127.0.0.1       otel-collector
127.0.0.1       mqtt-broker
127.0.0.1       model_registry
```

---

### Step 6: Launch the Containers

Start all required services using Docker Compose:

```bash
docker compose up -d
```
---

### Step 7: Modify the Payload File

Edit `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/apps/worker-safety-gear-detection/payload.json` and remove the `source` section so that it looks like this:

```json
[
    {
        "pipeline": "worker_safety_gear_detection",
        "payload": {
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "wsgd",
                    "overlay": false
                }
            },
            "parameters": {
                "detection-properties": {
                    "model": "/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml",
                    "device": "CPU"
                }
            }
        }
    }
]
```
---

### Step 8: Start the Sample Pipeline

Run the sample script to start the pipeline:

```bash
./sample_start.sh -p worker_safety_gear_detection
```
---

### Step 9: Access the Web Interface

Open a browser and navigate to:

```
https://<HOST_IP>/mediamtx/wsgd/
```

Replace `<HOST_IP>` with the IP address configured in your `.env` file.

## Troubleshooting

- For initial configuration and advanced configuration of the Balluff camera, please use the company-provided visualization tool **ImpactAcquire**, which is part of the **Balluff SDK**.
- Instructions to install the **Balluff SDK** on the host can be found in the [Balluff SDK Installation Guide](./how-to-install-balluff-sdk-on-host.md).