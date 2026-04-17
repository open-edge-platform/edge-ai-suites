# Model Preparation

To run this sample application, a Vision-Language Model (VLM) is required. If you wish to enable the detection pipeline, you will also need a YOLO vision model. Model preparation is handled using the [Model Download Microservice](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/index.html) from the open-edge-platform/edge-ai-libraries. Follow the steps below to download and convert the required models:

1. Clone the repository:

     Open a new terminal, clone the edge-ai-libraries repository.

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
          # - ~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning  (for live-video-captioning and with rag)
          # - ~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag (for live-video-captioning only deployment)

     # Run the script to launch the service
     source scripts/run_service.sh --plugins openvino,ultralytics --model-path $MODEL_PATH
     ```

5. Download and convert the models:

     Navigate to `live-video-analysis/live-video-captioning` and use the provided script to download and convert the required models:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning

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

     - For more detailed information about the scripts:

         ```bash
         ./model_download_scripts/download_models.sh -h
         ```

    The script will download and convert the models to OpenVINO IR format and store them in the respective directories:
    - VLM models → `ov_models/`
    - Vision detection models → `ov_detection_models/`
    - LLM models → `llm_models/`

6. Stop the Model Download service:

    The Model Download service handles the downloading and conversion of models needed for the Live Video Captioning and Live Video Captioniong RAG sample applications. The Model Download service functions independently and is not tied to the operations of the Live Video Captioning and Live Video Captioniong RAG sample applications. You can stop or terminate the service once the required models have been prepared.
