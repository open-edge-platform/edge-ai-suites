# Object Detection Pipeline

Object Detection is an optional configuration to enhances the base live captioning pipeline by integrating object detection as a pre-filtering step. Instead of sending every video frame to the captioning model, only frames containing detected objects are passed to VLM for caption generation. This approach significantly reduces compute overhead while maintaining meaningful captions, as frames without relevant objects are skipped. It is ideal for scenarios where captions should focus on detected entities rather than every frame.

## Enabling Object Detection Pipeline
User can enable object detection in the pipeline by following the steps below:

1. Set `ENABLE_DETECTION_PIPELINE` to `true` in the .env file.
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
     METADATA_POLL_SECONDS=0.5
     AGENT_MODE=False
     ENABLE_DETECTION_PIPELINE=True  # Enable detection pipeline
     ```

2. Prepare the object-detection models by using this [script](https://github.com/open-edge-platform/dlstreamer/blob/master/samples/download_public_models.sh).
     ```bash
     # Navigate to the directory
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning

     # Clean-up and create `ov_detection_models` dir.
     sudo rm -rf ov_detection_models && mkdir ov_detection_models

     # Download the script
     curl -O https://raw.githubusercontent.com/open-edge-platform/dlstreamer/master/samples/download_public_models.sh && chmod +x download_public_models.sh

     # Export the MODELS_PATH to store the detection model files downloaded. For example: `yolov8s`
     export MODELS_PATH=${PWD}/ov_detection_models/yolov8s

     # Run the script follwed by the model name to be download.
     # You may view all the available supported models inside the script.
     ./download_public_models.sh yolov8s
     ```

3. Then, now you are ready to deploy the pipeline which enabled with object detection model. You may find those pipelines available under the `Select Pipelines` dropdown menu.

## Troubleshooting

## No detection models in dropdown

Symptoms:
- Detection Model list is empty in the UI.

Checks:
- Ensure `ov_detection_models/` contains at least one model directory with OpenVINO IR files.
- If you downloaded models, re-run the stack so the service rescans.

## Next Steps

- [Get Started](./get-started.md) - Basic setup and configuration
- [API Reference](./api-reference.md) - REST API documentation
- [System Requirements](./system-requirements.md) - Hardware and software requirements
