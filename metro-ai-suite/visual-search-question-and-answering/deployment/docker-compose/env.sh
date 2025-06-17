host_ip=$(hostname -I | awk '{print $1}')
HOST_IP=$(hostname -I | awk '{print $1}')
USER_GROUP_ID=$(id -g)
VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}')
RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}')
export host_ip
export HOST_IP
export USER_GROUP_ID
export VIDEO_GROUP_ID
export RENDER_GROUP_ID

# Append the value of the public IP address to the no_proxy list 
export no_proxy="localhost, 127.0.0.1, ::1" 
export http_proxy=${http_proxy}
export https_proxy=${https_proxy}
export no_proxy_env=${no_proxy}

export MILVUS_HOST=${host_ip}
export MILVUS_PORT=19530

export DATA_INGEST_WITH_DETECT=true

# huggingface mirror 
export HF_ENDPOINT=https://hf-mirror.com

export DEVICE="GPU.1"
export VLM_DEVICE="GPU.1"
export HOST_DATA_PATH="$HOME/data"
export MODEL_DIR="$HOME/models"
# export LOCAL_EMBED_MODEL_ID="CLIP-ViT-H-14"
# export VLM_MODEL_NAME="Qwen/Qwen2.5-VL-7B-Instruct"

export VLM_COMPRESSION_WEIGHT_FORMAT=int4
export WORKERS=1

export VLM_SEED=42
export VLM_SERVICE_PORT=9764
export DATAPREP_SERVICE_PORT=9990
export RETRIEVER_SERVICE_PORT=7770
export VISUAL_SEARCH_QA_UI_PORT=17580
export BACKEND_VQA_BASE_URL="http://${host_ip}:${VLM_SERVICE_PORT}"
export BACKEND_SEARCH_BASE_URL="http://${host_ip}:${RETRIEVER_SERVICE_PORT}"
export BACKEND_DATAPREP_BASE_URL="http://${host_ip}:${DATAPREP_SERVICE_PORT}"

docker volume create ov-models
echo "Created docker volume for the models."

if [[ -z "$LOCAL_EMBED_MODEL_ID" ]]; then
    echo "Warning: LOCAL_EMBED_MODEL_ID is not defined."
    read -p "Please enter the LOCAL_EMBED_MODEL_ID: " user_model_name
    if [[ -n "$user_model_name" ]]; then
        echo "Using provided model name: $user_model_name"
        export LOCAL_EMBED_MODEL_ID="$user_model_name"
    else
        echo "Error: No model name provided. Exiting."
        exit 1
    fi
fi

if [[ -z "$VLM_MODEL_NAME" ]]; then
    echo "Warning: VLM_MODEL_NAME is not defined."
    read -p "Please enter the VLM_MODEL_NAME: " user_model_name
    if [[ -n "$user_model_name" ]]; then
        echo "Using provided model name: $user_model_name"
        export VLM_MODEL_NAME="$user_model_name"
    else
        echo "Error: No model name provided. Exiting."
        exit 1
    fi
fi