# Get Started

The Live Video Captioning sample application demonstrates real-time video captioning using Intel® DLStreamer and OpenVINO™. It processes RTSP video stream, applies video analytics pipelines for efficient decoding and inference, and leverages a Vision-Language Model(VLM) to generate live captions for the video content. In addition to captioning, the application provides performance metrics such as throughput and latency, enabling developers to evaluate and optimize end-to-end system performance for real-time scenarios.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run the application**: Execute the application to see real-time captioning from your video stream.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./system-requirements.md) for details.
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose: [Installation Guide](https://docs.docker.com/compose/install/).
- RTSP stream source (live camera or test feed). Please refer to this [guide](https://github.com/open-edge-platform/scenescape/tree/main/tools/streamer) to create simulated RTSP test feed stram using exisiting video files.
- OpenVINO-compatible VLM in `ov_models/`. User may use the [script](../../download_models.sh) provided to prepare the model.
- OpenVINO-compatible Object Detection Models in `ov_detection_models/`. Only required when user wish to enable object detection in the pipeline. Please refer to this [guide](./object-detection-pipeline.md) to enable object detection in the pipeline.

## Running the application

1. **Clone the repository**:
     ```bash
     # Clone the latest on mainline
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edges-ai-suites -b <release-tag>
     ```
    Note: Adjust the repo link appropriately in case of forked repo.

2. **Navigate to the Directory**:
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
     ```

3. **Configure Image Registry and Tag**:
     ```bash
     export REGISTRY="intel/"
     export TAG="rc2026.1.3"
     ```
    Skip this step if you prefer to build the sample applciation from source. For detailed instructions, refer to [How to Build from Source](./how-to-build-source.md) guide for details.

4. **Configure Environment**:
    Create a `.env` file in the repository root:
     ```bash
     WHIP_SERVER_IP=mediamtx
     WHIP_SERVER_PORT=8889
     WHIP_SERVER_TIMEOUT=30s
     PROJECT_NAME=live-captioning
     HOST_IP=<HOST_IP>
     EVAM_HOST_PORT=8040
     EVAM_PORT=8080
     DASHBOARD_PORT=4173
     WEBRTC_PEER_ID=stream
     WEBRTC_BITRATE=5000
     METADATA_POLL_SECONDS=0.5
     AGENT_MODE=False
     ENABLE_DETECTION_PIPELINE=False
     ```
    Notes:
    - `HOST_IP` must be reachable by the browser client for WebRTC signaling.
    - `PIPELINE_SERVER_URL` defaults to `http://dlstreamer-pipeline-server:8080`.
    - `WEBRTC_BITRATE` controls the video bitrate in kbps for WebRTC streaming (default: 2048).

5. **Download/Export Models**:
    Run the following scripts to download and convert VLM models.
     ```bash
     chmod +x download_models.sh
     ./download_models.sh [internvl2_1B|gemma3|internvl2_2B]
     ```

    For other OpenVINO supported models, provide the HuggingFace model name.

    ```
    ./download_models.sh OpenGVLab/InternVL2_5-1B
    ```

    For gated models, please export you HF_TOKEN before running the scripts above:
    
     ```bash
     export HF_TOKEN=<YOUR_HUGGING_FACE_TOKEN>
     ```

6. **Start the Application**:
    Start the application using Docker Compose tool:
     ```bash
     docker compose up
     ```

7. **Access the Application**:
    Following are the exposed services with their default ports:
     - Pipeline API: `http://<HOST_IP>:8040`
     - WebRTC signaling: `ws://<HOST_IP>:8889`
     - Dashboard UI: `http://<HOST_IP>:4173`

    Run a captioning pipeline
     1. Open the dashboard at `http://<HOST_IP>:4173`.
     2. Enter an RTSP URL.
     3. Select a VLM model.
     4. Edit prompt/max tokens as needed.
     5. Click **Start**.

8. **Stop the Services**:
    Stop the sample application services using below:
     ```bash
     docker compose down
     ```

## Advanced Setup Options
For alternative ways to setup the application, see:
- [How to build from Source](./how-to-build-source.md)

## Supporting Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Agent Mode](./agent-mode.md) - Enable alert-style responses for binary detection scenarios
- [Enable Detection Pipeline](./object-detection-pipeline.md) - Enable object detection for live captioning.
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)
