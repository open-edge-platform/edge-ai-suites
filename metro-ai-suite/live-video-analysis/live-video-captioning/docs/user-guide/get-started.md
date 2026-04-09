# Get Started

The Live Video Captioning sample application demonstrates real-time video captioning using Deep Learning Streamer (DL Streamer) and OpenVINO™ toolkit. The sample application processes the Real-Time Streaming Protocol (RTSP) video stream, applies video analytics pipelines for efficient decoding and inference, and leverages a Vision-Language Model (VLM) to generate live captions for the video content. In addition to captioning, the application provides performance metrics such as throughput and latency, enabling developers to evaluate and optimize end-to-end system performance for real-time scenarios.

This section shows how to:
- **Set up the sample application**: Use Docker Compose tool to quickly deploy the application in your environment.
- **Run the application**: Execute the application to see real-time captioning from your video stream.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker Engine: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- RTSP stream source (live camera or test feed). See this [guide](https://github.com/open-edge-platform/scenescape/tree/main/tools/streamer) to create a simulated RTSP test feed stream using existing video files.
- OpenVINO-compatible VLM in `ov_models/`. See [Model Preparation](#model-preparation) to prepare the model.
- OpenVINO-compatible Object Detection Models in `ov_detection_models/`. This is only required
when object detection in the pipeline is enabled. See [Object Detection Pipeline configuration](./object-detection-pipeline.md) to enable.

## Run the Application

1. Clone the repository:

     ```bash
     # Clone the latest on the mainline
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-suites.git edges-ai-suites -b <release-tag>
     ```

     > **Note:** If the repository is forked, edit the link.

2. Navigate to the directory:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
     ```

3. Configure the image registry and tag:

     ```bash
        export REGISTRY="intel/"
        export TAG="latest"
     ```
    Skip this step if you prefer to build the sample application from the source. For detailed instructions, see [Build from Source](./get-started/build-from-source.md).

4. Configure the environment:

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
     ALERT_MODE=False
     ENABLE_DETECTION_PIPELINE=False
     CAPTION_HISTORY=3
     ```
    > **Notes**:
    - `HOST_IP` must be reachable by the browser client for WebRTC signaling.
    - `PIPELINE_SERVER_URL` defaults to `http://dlstreamer-pipeline-server:8080`.
    - `WEBRTC_BITRATE` controls the video bitrate in kbps for WebRTC streaming (default: 2048).
    - `CAPTION_HISTORY` controls how many previous captions are shown in the caption timeline. The UI shows the current and `CAPTION_HISTORY` previous entries (`0` means only current). You can also change this value from the UI.

5. Download and export the models:

    See the [Model Preparation](#model-preparation) section.

6. Start the application using Docker Compose tool:

     ```bash
     docker compose up
     ```

7. Access the application:

    To start processing video with live captioning:

    a. Open the dashboard at `http://<HOST_IP>:4173`.
    b. Enter an RTSP URL for your video stream.
    c. Select a VLM model from the dropdown.
    d. Customize the prompt and maximum tokens as needed.
    e. Click **Start** to begin captioning.

    > **Note:** If running in a proxy network, add your RTSP stream URLs or IPs to the `no_proxy` environment variable to allow direct connections to the stream source without going through the proxy.

8. Stop the sample application services:

     ```bash
     docker compose down
     ```

## Model Preparation

To run this sample application, a Vision-Language Model (VLM) is required. If you want to enable the detection pipeline, you will also need a YOLO vision model. Model preparation is handled using the [model-download microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-download) from the open-edge-platform/edge-ai-libraries. Use the following steps to download and convert the required models:

1. Open a new terminal and clone the edge-ai-libraries repository:
	 
     ```bash
     # Clone the latest on the mainline
     git clone https://github.com/open-edge-platform/edge-ai-libraries.git edge-ai-libraries
     # Alternatively, clone a specific release branch
     git clone https://github.com/open-edge-platform/edge-ai-libraries.git edge-ai-libraries -b <release-tag>
     ```

2. Navigate to the directory:

     ```bash
     cd edge-ai-libraries/microservices/model-download
     ```

3. Configure the environment variables:

     ```bash
     export REGISTRY="intel/"
     export TAG=latest
     export HUGGINGFACEHUB_API_TOKEN=<your-huggingface-token>
     ```

4. Launch the service with required plugins:

     ```bash
     export MODEL_PATH=<path-to-directory-for-models-to-be-stored>
     # Example paths:
          # - ~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning  (for live-video-captioning and RAG)
          # - ~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag (for live-video-captioning only)

     # Run the script to launch the service
     source scripts/run_service.sh --plugins openvino,ultralytics --model-path $MODEL_PATH
     ```

5. Download and convert the models:

     Return to the live-captioning repository terminal you opened earlier:
	 
     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
     ```

     Download and convert the required models using the provided script:
	 
     ```bash
     # export MODEL_PATH with the same directory that exported in previous step.
     export MODEL_PATH=<path-to-directory-for-models-to-be-stored>

     # Parameters:
     # model_name: specify the model identifier from Hugging Face
     # model_type: choose from vlm, vision, or llm
     # model_quantization: select int4, int8, or fp16

     ./model_download_scripts/download_models.sh --model <model_name> --type <model_type> --weight-format <model_quantization>
     ```

    **Examples:**

     - For a VLM model (required for live-video-captioning):
	 
         ```bash
         ./model_download_scripts/download_models.sh --model OpenGVLab/InternVL2-1B --type vlm --weight-format int8
         ```

    - For a YOLO vision model (for live-video-captioning with object-detection pipeline):
	
         ```bash
         ./model_download_scripts/download_models.sh --model yolov8s --type vision
         ```

    - For a LLM model (for live-video-captioning with RAG):
	
         ```bash
         ./model_download_scripts/download_models.sh --model microsoft/Phi-3.5-mini-instruct --type llm --device <CPU/GPU> --weight-format int8
         ```

    - For detailed information about the scripts:
	
         ```bash
         ./model_download_scripts/download_models.sh -h
         ```

    The script will download and convert the models to the OpenVINO Intermediate Representation (IR) format and store them in the following directories:
    - VLM models → `ov_models/`
    - Vision detection models → `ov_detection_models/`
    - LLM models → `llm_models/`

6. **Stop the service**:

    This service handles the downloading and conversion of models needed for the Live Video Captioning sample application. The service functions independently and is not tied to the operation of the Live Video Captioning sample application. You can stop or terminate the service once the required models have been prepared.

## Build from Source

If you want to build the application from source, see [Build from Source](./get-started/build-from-source.md).

## Additional Features

If you want to use the application with additional features, see:

- [Alert Mode](./alert-mode.md) - Enable alert-style responses for binary detection scenarios
- [Enable Detection Pipeline](./object-detection-pipeline.md) - Enable object detection for live captioning.
- [Enable Embedding Creation with RAG](./embedding-creation-with-rag.md) - Enable embedding creation and RAG for live captioning.

## Testing

The project uses **pytest** for unit testing. Tests are located in the `tests/` directory
under the `app/` folder.

### Install Test Dependencies

```bash
cd app
uv sync --group test
```

### Run All Tests

```bash
uv run pytest
```

### Run a Specific Test File

```bash
uv run pytest tests/test_routes_runs.py
```

### Run Tests with Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=term-missing
```

### Generate an HTML Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=html
```

Open `htmlcov/index.html` in a browser to view the detailed coverage report.

## Learn More

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Model Download Microservice Get Started Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started.md)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
get-started/build-from-source.md

:::
hide_directive-->
