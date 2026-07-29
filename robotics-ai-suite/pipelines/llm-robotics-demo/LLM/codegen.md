# Documentation for LLM code generation model
1. Setup a virtual environment for application

    python3 -m venv venv_name

    source venv_name/bin/activate

    pip install -r requirement.txt

2. Set the environment variable

    ```bash
    # If you have connection issue on HuggingFace in PRC, please set-up the networking environment by following commands:
    export HF_ENDPOINT="https://hf-mirror.com"
    # transformers offline: export TRANSFORMERS_OFFLINE=1
    ```

3. Download the LLM OpenVINO model

    ```bash
    sudo apt install git-lfs
    mkdir ~/ov_models && cd ~/ov_models
    GIT_LFS_SKIP_SMUDGE=1 git clone https://hf-mirror.com/OpenVINO/Phi-4-mini-instruct-int8-ov
    git lfs pull
    ```
    To use Qwen3 instead, clone the Qwen3 OpenVINO model:
    ```bash
    GIT_LFS_SKIP_SMUDGE=1 git clone https://hf-mirror.com/OpenVINO/Qwen3-8B-int8-ov
    git lfs pull
    ```
    After downloading the LLM model, update the model loading path to match your local model directory. For example:
    ```bash
    # vim llm_bridge.py:L27
    self.model_path = "/home/intel/ov_models/Phi-4-mini-instruct-int8-ov"
    ```

4. Setup the SAM and CLIP models

    Follow the documentation below to export and save SAM (ViT-B) and CLIP (ViT-B) models:
    ```bash
    SAM: https://github.com/openvinotoolkit/openvino_notebooks/tree/2026.1/notebooks/segment-anything

    CLIP: https://github.com/openvinotoolkit/openvino_notebooks/tree/2026.1/notebooks/clip-zero-shot-image-classification
    ```

    Copy the generated model and XML files to the `ov_models` directory, or update the model loading paths to point to your exported model locations. For example:
    ```bash
    # vim utils/mobilesam_helper.py:L87-L89
    clip_model_path = f"/home/intel/ov_models/clip-vit-base-patch16.xml"
    ov_sam_encoder_path = f"/home/intel/ov_models/sam_image_encoder.xml"
    ov_sam_predictor_path = f"/home/intel/ov_models/sam_mask_predictor.xml"
    ```

5. Run codegen in virtual environment which setup in step 1.

    python main.py

