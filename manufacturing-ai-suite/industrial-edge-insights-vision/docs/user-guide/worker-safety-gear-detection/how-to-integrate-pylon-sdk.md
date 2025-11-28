# Guide: Testing Worker Safety Gear Detection Application Using pylon SDK

This guide explains how to create a custom Docker image based on the Intel DL Streamer Pipeline Server, with pylon SDK and Gencamsrc support. It supports Basler camera that are connected over the USB and GigE.

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

Create a Docker file named `BaslerDockerfile` inside your `dlstreamer-pipeline-server` directory with the following content.

```dockerfile
FROM intel/dlstreamer-pipeline-server:3.1.0-ubuntu24

USER root

RUN apt-get update && apt-get install -y wget gnupg gstreamer1.0-plugins-base libxcb-cursor0 make autoconf vim libgstreamer-plugins-base1.0-dev libgstreamer1.0-dev g++-11 g++ && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

RUN wget https://downloads-ctf.baslerweb.com/dg51pdwahxgw/16EbjATpV78LtOFUQ1VpJM/ab3db40227afb59df3eb1cccf0c5addc/pylon-7.5.0.15658-linux-x86_64_debs.tar.gz &&     tar -xvzf pylon-7.5.0.15658-linux-x86_64_debs.tar.gz && rm pylon-7.5.0.15658-linux-x86_64_debs.tar.gz && dpkg -i pylon_7.5.0.15658-deb0_amd64.deb || apt-get install -fy && rm pylon_7.5.0.15658-deb0_amd64.deb

RUN wget https://github.com/basler/gst-plugin-pylon/releases/download/v1.0.0/gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb && dpkg -i gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb && rm gst-plugin-pylon_1.0.0-1.ubuntu-24.04_amd64.deb

COPY ./thirdparty/install_gencamsrc_gstreamer_plugin.sh /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh
COPY ./plugins/camera/src-gst-gencamsrc /home/pipeline-server/src-gst-gencamsrc

RUN chmod +x /home/pipeline-server/src-gst-gencamsrc/setup.sh
RUN chmod +x /home/pipeline-server/src-gst-gencamsrc/autogen.sh
RUN chmod +x /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh
RUN /home/pipeline-server/install_gencamsrc_gstreamer_plugin.sh

ENV GENICAM_GENTL64_PATH=/opt/pylon/lib/gentlproducer/gtl \
    GST_PLUGIN_PATH=/opt/intel/dlstreamer/lib:/opt/intel/dlstreamer/gstreamer/lib/gstreamer-1.0:/opt/intel/dlstreamer/gstreamer/lib/:/usr/lib/x86_64-linux-gnu/gstreamer-1.0:/usr/local/lib/gstreamer-1.0

USER intelmicroserviceuser
```

---

### Step 3: Build the Docker Image

Run the following command to build the image:

```bash
docker build -t intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-basler -f BaslerDockerfile .
```

This command builds your Docker image using the steps defined above.

---

### Step 4: Verify the Image

After the build completes, update .env and start the container:

> update .env DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-basler

```bash
docker compose up -d
```

---

### Step 5: Run a test pipeline and dump the camera output into a file in the /tmp directory

Note down serial number of the basler camera and update `<basler-camera-serial>` in the following command
```bash
docker exec -it dlstreamer-pipeline-server bash
$ gst-launch-1.0 gencamsrc serial=<basler-camera-serial> pixel-format=bayerrggb name=source ! bayer2rgb ! videoscale ! video/x-raw, width=1920,height=1080 ! videoconvert ! queue ! jpegenc ! avimux ! filesink location=/tmp/gencam_basler_output.avi
```

Verify that the /tmp/gencam_basler_output.avi has the captured content

---

## Deploying the Worker Safety Gear Detection Application Using live camera

This guide provides detailed, step-by-step instructions for setting up and deploying the **Worker Safety Gear Detection** pipeline to use the **Balluff** or **Basler** camera connected over USB or GigE.  
It covers environment setup, configuration updates, and validation steps to ensure a successful deployment.

---

### Step 1: Set Up the Environment

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision
cp .env_worker_safety_gear_detection .env
```

---

### Step 2: Configure the .env File

Update the `.env` file with the newly created image as below and modify any other required variables.

```bash
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:3.1.0-ubuntu24-gencamsrc-basler
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

Replace <camera id> with balser camera id connected over the USB or GigE

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

For Basler USB Cameras if you face issue with the detection of the camera, you can perform the following steps
```bash
sudo apt install v4l-utils
v4l2-ctl --list-devices
stat /dev/bus/usb
sudo usermod -a -G dialout $USER
# Download the setup file
wget https://downloadbsl.blob.core.windows.net/software/pylon-8.1.0_linux-x86_64_setup.tar.gz
# Create the target directory and extract the setup file in one step
mkdir -p pylon-8.1.0_linux-x86_64_setup
tar xvf pylon-8.1.0_linux-x86_64_setup.tar.gz -C pylon-8.1.0_linux-x86_64_setup
# Extract the second tarball inside the setup directory
tar xvf pylon-8.1.0_linux-x86_64_setup/pylon-8.1.0_linux-x86_64.tar.gz -C pylon-8.1.0_linux-x86_64_setup
# Run the USB setup script
./pylon-8.1.0_linux-x86_64_setup/share/pylon/setup-usb.sh
sudo reboot
```
