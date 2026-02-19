# Run RTSP Camera Capture and AI Inference

This guide explains how to set up and run the RTSP camera capture and AI inference pipeline.

## Download AI Model and Resources

First, download the necessary AI models and supporting libraries.

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git
cd edge-ai-libraries/microservices/dlstreamer-pipeline-server
wget -c https://github.com/open-edge-platform/edge-ai-resources/raw/a7c9522f5f936c47de8922046db7d7add13f93a0/models/INT8/pallet_defect_detection.zip
unzip -q pallet_defect_detection.zip -d models/
cd docker
```

## Configure the Environment

Before running the services, you need to configure the environment variables.

### Update .env file

Set the `MQTT_PORT` in the `.env` file. If you are behind a proxy, configure the proxy
settings as well.

```text
MQTT_PORT=1883
# http_proxy=...
# https_proxy=...
```

### Copy Configuration Files

Copy the `ptp_frame_timestamp.py` and `config.json` from the `deterministic-threat-detection`
module to the current docker directory.

```bash
cp edge-ai-suites/metro-ai-suite/deterministic-threat-detection/rtsp_camera_stream/ptp_frame_timestamp.py .
cp edge-ai-suites/metro-ai-suite/deterministic-threat-detection/rtsp_camera_stream/config.json .
```

> **Note:** Make sure to update the RTSP camera `<rtsp-camera-username>`,
`<rtsp-camera-password>`, and `<rtsp-camera-url>` in the `config.json` file before proceeding.
Also, add the RTSP camera IP to the `no_proxy environment` variable if you are behind a proxy.

## Update Docker Compose File

Comment the existing resources folder mapping and add volume mappings to the `docker-compose.yml`
file to make the custom script and configuration available to the `dlstreamer-pipeline-server`
container.

```yaml
services:
  dlstreamer-pipeline-server:
    # ... existing configuration ...
    volumes:
      # - "../resources:/home/pipeline-server/resources/"
      - "../models:/home/pipeline-server/resources/"
      - "./ptp_frame_timestamp.py:/home/pipeline-server/ptp_frame_timestamp.py"
      - "./config.json:/home/pipeline-server/config.json"
      # ... other volumes ...
```

## Run the Services

Start the services using Docker Compose.

```bash
docker compose up -d
```

## Start the RTSP Camera Pipeline

Finally, start the pipeline by sending a POST request to the pipeline server.

```bash
curl -k http://localhost:8080/pipelines/user_defined_pipelines/rtsp_camera_pipeline -X POST -H 'Content-Type: application/json' -d '{
    "destination": {
        "metadata": {
            "type": "mqtt",
            "publish_frame": true,
            "topic": "tsn_demo/camera/inference"
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/deployment/Detection/model/model.xml",
            "device": "CPU"
        }
    }
}'
```

> **Note:** Update the topic name if you are running the pipeline on multiple machines.
