# Integrate a Camera SDK into the Pallet Defect Detection Application

This guide explains how to create a custom Docker image based on the DL Streamer Pipeline Server with Gencamsrc support, using either the Balluff SDK or the pylon SDK.
It supports Balluff, Basler, and other GenICam-compatible cameras connected over USB and GigE interfaces.

> **Note:** You may observe a watermark in the camera feed when testing with a non-Balluff camera, as it is the free version.

## Prerequisites

- [System Requirements](../../get-started/vision-system-requirements.md)

## Clone and Build the Docker Image

### Step 1: Base Image and User Setup

Download the edge-ai-libraries source and go to the `dlstreamer-pipeline-server` folder.

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git -b main
cd edge-ai-libraries/microservices/dlstreamer-pipeline-server
```

### Step 2: Create the Docker Image

Create a Dockerfile inside your `dlstreamer-pipeline-server` directory with the content shown for your SDK.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

Create a Dockerfile named `BalluffDockerfile`.

```dockerfile
FROM intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2

USER root

RUN apt-get update && apt-get install -y wget gnupg cmake gstreamer1.0-plugins-base libgstreamer-plugins-base1.0-dev libgstreamer1.0-dev g++ libxcb-cursor0 vim && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./plugins/camera/src-gst-gencamsrc /home/pipeline-server/src-gst-gencamsrc

RUN cd /home/pipeline-server/src-gst-gencamsrc && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j$(nproc) && cmake --install build && ldconfig

# For Ubuntu24 intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2 base image
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

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

Create a Dockerfile named `BaslerDockerfile`.

```dockerfile
FROM intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2

USER root

RUN apt-get update && apt-get install -y wget gnupg cmake gstreamer1.0-plugins-base libgstreamer-plugins-base1.0-dev libgstreamer1.0-dev g++ libxcb-cursor0 vim && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN cd /tmp && wget https://downloads-ctf.baslerweb.com/dg51pdwahxgw/16EbjATpV78LtOFUQ1VpJM/ab3db40227afb59df3eb1cccf0c5addc/pylon-7.5.0.15658-linux-x86_64_debs.tar.gz &&     tar -xvzf pylon-7.5.0.15658-linux-x86_64_debs.tar.gz && rm pylon-7.5.0.15658-linux-x86_64_debs.tar.gz && dpkg -i pylon_7.5.0.15658-deb0_amd64.deb || apt-get install -fy && rm pylon_7.5.0.15658-deb0_amd64.deb

RUN cd /tmp && wget https://github.com/basler/gst-plugin-pylon/releases/download/v1.0.0/gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb && dpkg -i gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb && rm gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb

COPY ./plugins/camera/src-gst-gencamsrc /home/pipeline-server/src-gst-gencamsrc

RUN cd /home/pipeline-server/src-gst-gencamsrc && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j$(nproc) && cmake --install build && ldconfig

ENV GENICAM_GENTL64_PATH=/opt/pylon/lib/gentlproducer/gtl \
    GST_PLUGIN_PATH=/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/gstreamer/lib/gstreamer-1.0:/opt/intel/dlstreamer/gstreamer/lib/:/usr/lib/x86_64-linux-gnu/gstreamer-1.0:/usr/local/lib/gstreamer-1.0

USER intelmicroserviceuser
```

<!--hide_directive
:::
::::
hide_directive-->

### Step 3: Build the Docker Image

Run the following command to build the image.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

```bash
docker build -t intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-balluff -f BalluffDockerfile .
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

```bash
docker build -t intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-basler -f BaslerDockerfile .
```

<!--hide_directive
:::
::::
hide_directive-->

This command builds your Docker image using the steps defined above.

### Step 4: Verify the Image

After the build completes, inside `dlstreamer-pipeline-server/docker` directory, update `.env` and start the container.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

Update `.env` with:

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-balluff
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

Update `.env` with:

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-basler
```

<!--hide_directive
:::
::::
hide_directive-->

```bash
docker compose up -d
```

### Step 5: Run a Test Pipeline to Get Camera Output

Check the camera serial number and update it in the command below.

The output will be written to a file in the `/tmp` directory.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

Replace `<balluff-camera-serial>` with your Balluff camera serial number.

```bash
docker exec -it dlstreamer-pipeline-server bash
$ gst-launch-1.0 gencamsrc serial=<balluff-camera-serial> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! queue ! jpegenc ! avimux ! filesink location=/tmp/gencam_balluff_output.avi
```

Verify that `/tmp/gencam_balluff_output.avi` has the captured content.

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

Replace `<basler-camera-serial>` with your Basler camera serial number.

```bash
docker exec -it dlstreamer-pipeline-server bash
$ gst-launch-1.0 gencamsrc serial=<basler-camera-serial> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! queue ! jpegenc ! avimux ! filesink location=/tmp/gencam_basler_output.avi
```

Verify that `/tmp/gencam_basler_output.avi` has the captured content.

<!--hide_directive
:::
::::
hide_directive-->

## Deploy the Pallet Defect Detection (PDD) Application Using Live Camera

This section provides detailed, step-by-step instructions for setting up and deploying the **Pallet Defect Detection (PDD)** pipeline using a live camera feed.

### Step 1: Set Up the Environment

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b main
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision
cp .env_pallet-defect-detection .env
```

### Step 2: Configure the .env File

Update the `.env` file with the image you built and modify any other required variables.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-balluff
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc2-gencamsrc-basler
```

<!--hide_directive
:::
::::
hide_directive-->

### Step 3: Run the Setup Script

Execute the setup script to initialize project directories and configurations.

```bash
./setup.sh
```

### Step 4: Update the Pipeline Configuration

Update the pipeline in `./apps/pallet-defect-detection/configs/pipeline-server-config.json` to use the camera.

```json
{
    "name": "pallet_defect_detection",
    "source": "gstreamer",
    "queue_maxsize": 50,
    "pipeline": "gencamsrc serial=<camera id> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=640, height=480 ! videoconvert ! gvadetect name=detection model-instance-id=inst0 ! gvametaconvert add-empty-results=true name=metaconvert ! queue ! gvafpscounter ! gvawatermark ! appsink name=destination"
}
```

Replace `<camera id>` with the camera ID connected over USB or GigE.

### Step 5: Configure docker-compose.yml (Optional, if Testing with a GigE Network Camera)

When testing with a GigE camera, adjust the `docker-compose.yml` configuration for all services.

1. Add `network_mode` set to `"host"`.
2. Remove the `networks` section.

The configuration for each service should look like this.

```yaml
services:
  service_name:
    .
    .
    network_mode: "host"
    # networks:
    #   - industrial-edge-vision
```

Additionally, add the following entries to the `/etc/hosts` file on the host machine.

```bash
127.0.0.1       dlstreamer-pipeline-server
127.0.0.1       prometheus
127.0.0.1       mediamtx-server
127.0.0.1       minio
127.0.0.1       otel-collector
127.0.0.1       mqtt-broker
```

### Step 6: Launch the Containers

Start all the required services using Docker Compose.

> **Note:** If you are running multiple instances of the application, start the services using `./run.sh up` instead.

```bash
docker compose up -d
```

### Step 7: Modify the Payload File

Edit `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/apps/pallet-defect-detection/payload.json` and remove the `source` section so that it looks like this.

```json
[
    {
        "pipeline": "pallet_defect_detection",
        "payload": {
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "pdd",
                    "overlay": false
                }
            },
            "parameters": {
                "detection-properties": {
                    "model": "/home/pipeline-server/resources/models/pallet-defect-detection/deployment/Detection/model/model.xml",
                    "device": "CPU"
                }
            }
        }
    }
]
```

### Step 8: Start the Sample Pipeline

Run the sample script to start the pipeline.

```bash
./sample_start.sh -p pallet_defect_detection
```

### Step 9: Access the Web Interface

Open a browser and navigate to:

```text
https://<HOST_IP>/mediamtx/pdd/
```

Replace `<HOST_IP>` with the IP address configured in your `.env` file.

> **Note:** If you are running multiple instances of the application, ensure to provide `NGINX_HTTPS_PORT` number in the URL for the application instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.
> If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

## Troubleshooting

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Balluff SDK**
<!--hide_directive :sync: balluff-sdk hide_directive-->

- For initial configuration and advanced configuration of the Balluff camera, use the company-provided visualization tool **ImpactAcquire**, which is part of the **Balluff SDK**.
- Instructions to install the **Balluff SDK** on the host can be found in the [Balluff SDK Installation Guide](./install-balluff-sdk-on-host.md).

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **pylon SDK**
<!--hide_directive :sync: pylon-sdk hide_directive-->

- For initial configuration and advanced configuration of the Basler camera, use the company-provided visualization tool **pylonviewer**, which is part of the **pylon SDK**.
- Instructions to install the **pylon SDK** on the host can be found in the [pylon SDK Installation Guide](./install-pylon-sdk-on-host.md).
- If you face any issues related to camera detection over USB, refer to the [pylon Troubleshooting Guide](./install-pylon-sdk-on-host.md#troubleshooting).

<!--hide_directive
:::
::::
hide_directive-->

<!--hide_directive
:::{toctree}
:hidden:

Install Balluff SDK <install-balluff-sdk-on-host>
Install pylon SDK <install-pylon-sdk-on-host>

:::
hide_directive-->