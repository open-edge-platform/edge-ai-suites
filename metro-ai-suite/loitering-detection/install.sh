#!/bin/bash
set -e  # Exit on error
cd "$(dirname "$(readlink -f "$0")")"

##############################################################################
# Helper function: create_dir
# Attempts to create a directory; if it fails due to permission issues,
# changes the ownership of the parent directory and then creates the folder.
##############################################################################
create_dir() {
    local dir="$1"
    if ! mkdir -p "$dir" 2>/dev/null; then
        echo "Failed to create '$dir'. It may be owned by root. Attempting to fix ownership..."
        # Change ownership of the parent directory
        sudo chown -R "$(id -un):$(id -gn)" "$(dirname "$dir")" || true
        mkdir -p "$dir"
    fi
    # Ensure the created directory is owned by the current user
    sudo chown -R "$(id -un):$(id -gn)" "$dir" || true
}

##############################################################################
# 0. Check for python3-venv (only place we use sudo)
##############################################################################
if ! dpkg -s python3.12-venv &>/dev/null; then
    echo "Package python3-venv not installed. Attempting to install..."
    sudo apt update
    sudo apt install -y python3-venv
fi

##############################################################################
# 1. Configure application to use the primary IP address
##############################################################################
if [ -z "$1" ]; then
    HOST_IP=$(hostname -I | cut -f 1 -d " ")
    echo "No HOST_IP provided. Using detected IP: $HOST_IP"
else
    HOST_IP="$1"
    echo "Using provided HOST_IP: $HOST_IP"
fi

echo "Configuring application to use $HOST_IP"
echo "HOST_IP=$HOST_IP" > .env 

if [ ! -f ".env" ]; then
    echo "Error: .env file not found in current directory!"
    exit 1
fi
# shellcheck disable=SC1091
source .env
source ./update_dashboard.sh

##############################################################################
# 2. Create/Activate a Python virtual environment to avoid pip system issues
##############################################################################
VENV_DIR=".venv"  # or pick another name/path if you wish

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating Python virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Error: Virtual environment activate script not found at $VENV_DIR/bin/activate"
    exit 1
fi

echo "Activating Python virtual environment..."
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

pip install --upgrade pip

##############################################################################
# 3. Locate and parse the model.txt
##############################################################################
MODEL_TXT="model.txt"
cat "$MODEL_TXT"

if [ ! -f "$MODEL_TXT" ]; then
    echo "Error: $MODEL_TXT not found!"
    deactivate
    exit 1
fi

YOLO_MODEL=""
OMZ_MODELS=()

while read -r model_name model_type; do
    # Skip empty lines or those starting with '#'
    [[ -z "$model_name" || "$model_name" == \#* ]] && continue

    if [ "$model_type" = "yolo" ]; then
        YOLO_MODEL="$model_name"
    elif [ "$model_type" = "omz" ]; then
        OMZ_MODELS+=("$model_name")
    fi
done < "$MODEL_TXT"


echo "Found YOLO model: $YOLO_MODEL"
echo "Found OMZ models: ${OMZ_MODELS[@]}"

##############################################################################
# 4. Process YOLO model (if any)
##############################################################################
if [ -n "$YOLO_MODEL" ]; then
    echo ">>> Processing YOLO model: $YOLO_MODEL"

    pip install ultralytics==8.3.50 openvino==2025.0.0

    if [ ! -f "${YOLO_MODEL}.pt" ]; then
        echo "Warning: ${YOLO_MODEL}.pt not found in current directory. If not local, ultralytics will try to download."
    fi

    echo "Exporting ${YOLO_MODEL} to OpenVINO..."
    yolo export model="${YOLO_MODEL}.pt" format=openvino

    EXPORTED_DIR="${YOLO_MODEL}_openvino_model"
    if [ ! -d "$EXPORTED_DIR" ]; then
        echo "Error: Expected folder $EXPORTED_DIR not found after export!"
        deactivate
        exit 1
    fi

    if [ -d "dlsps/models/public/${YOLO_MODEL}" ]; then
        rm -rf "dlsps/models/public/${YOLO_MODEL}"
    fi
    create_dir "dlsps/models/public"
    mv "$EXPORTED_DIR" "dlsps/models/public/${YOLO_MODEL}"

    XML_FILE="dlsps/models/public/${YOLO_MODEL}/${YOLO_MODEL}.xml"
    if [ -f "$XML_FILE" ]; then
        sed -i '11172s/YOLO/yolo_v10/' "$XML_FILE" || true
        echo "XML file updated for ${YOLO_MODEL} (if line 11172 existed)."
    else
        echo "Warning: XML file not found for ${YOLO_MODEL}"
    fi

    create_dir "dlsps/models/public/${YOLO_MODEL}/FP32"

    if [ -f "${YOLO_MODEL}.pt" ]; then
        mv "${YOLO_MODEL}.pt" "dlsps/models/public/${YOLO_MODEL}/FP32/"
    fi

    mv "dlsps/models/public/${YOLO_MODEL}/${YOLO_MODEL}.xml" "dlsps/models/public/${YOLO_MODEL}/FP32/" 2>/dev/null || true
    mv "dlsps/models/public/${YOLO_MODEL}/${YOLO_MODEL}.bin" "dlsps/models/public/${YOLO_MODEL}/FP32/" 2>/dev/null || true
    mv "dlsps/models/public/${YOLO_MODEL}/"*.yaml "dlsps/models/public/${YOLO_MODEL}/FP32/" 2>/dev/null || true
fi

##############################################################################
# 5. Process OMZ models (if any)
##############################################################################
if [ ${#OMZ_MODELS[@]} -gt 0 ]; then
    echo ">>> Processing OMZ models: ${OMZ_MODELS[@]}"

    pip install "openvino-dev[onnx,tensorflow,pytorch]"

    if [ ! -d "dlstreamer" ]; then
        git clone https://github.com/dlstreamer/dlstreamer.git
    else
        echo "dlstreamer directory already exists. Skipping clone."
    fi

    export MODELS_PATH="$HOME/intel/models"
    create_dir "$MODELS_PATH"

    pushd dlstreamer/samples > /dev/null

    echo "Overwriting models_omz_samples.lst with OMZ models..."
    > models_omz_samples.lst
    for model in "${OMZ_MODELS[@]}"; do
        echo "$model" >> models_omz_samples.lst
    done

    echo "Downloading OMZ models..."
    ./download_omz_models.sh

    popd > /dev/null

    if [ -d "$HOME/intel/models/public" ]; then
        echo "Merging public models into intel folder..."
        create_dir "$HOME/intel/models/intel"
        for item in "$HOME/intel/models/public/"*; do
            base_item=$(basename "$item")
            target="$HOME/intel/models/intel/$base_item"
            if [ -e "$target" ]; then
                echo "Removing existing $target to overwrite."
                rm -rf "$target"
            fi
            mv "$item" "$target"
        done
        rm -rf "$HOME/intel/models/public"
    fi

    create_dir "dlsps/models/intel"
    if [ -d "$HOME/intel/models/intel" ]; then
        for item in "$HOME/intel/models/intel/"*; do
            base_item=$(basename "$item")
            target="dlsps/models/intel/$base_item"
            if [ -e "$target" ]; then
                echo "Removing existing $target to overwrite."
                rm -rf "$target"
            fi
            mv "$item" "$target"
        done
        rm -rf "$HOME/intel/models/intel"
    else
        echo "Warning: $HOME/intel/models/intel not found. Download may have failed."
    fi

    for model in "${OMZ_MODELS[@]}"; do
        MODEL_PROC_URL="https://github.com/dlstreamer/dlstreamer/blob/master/samples/gstreamer/model_proc/intel/${model}.json?raw=true"
        DEST_DIR="dlsps/models/intel/${model}"
        create_dir "$DEST_DIR"
        echo "Downloading model proc for ${model}..."
        curl -L -o "${DEST_DIR}/${model}.json" "${MODEL_PROC_URL}" || \
            echo "Warning: Could not download model proc for ${model}"
    done
fi

##############################################################################
# 6. (Optional) Ensure current user owns everything under current directory
##############################################################################
CURRENT_USER=$(id -un)
CURRENT_GROUP=$(id -gn)
echo "Fixing ownership for current directory..."
sudo chown -R "$CURRENT_USER:$CURRENT_GROUP" "." 2>/dev/null || true

##############################################################################
# 7. Remove the dlstreamer and dlsps folders (if they exist), deactivate the venv, and finish
##############################################################################
if [ -d "dlstreamer" ]; then
    echo "Removing dlstreamer folder..."
    rm -rf dlstreamer
fi

##############################################################################
# Download and setup videos for Smart Parking
##############################################################################
echo "Setting up videos for Smart Parking..."
# Create videos directory if it doesn't exist
VIDEO_DIR="dlsps/videos"
create_dir "$VIDEO_DIR"

# Download and rename videos
declare -A video_urls=(
    ["VIRAT_S_000101.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000101.mp4"
    ["VIRAT_S_000102.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000102.mp4"
    ["VIRAT_S_000103.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000103.mp4"
    ["VIRAT_S_000104.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000104.mp4"
)

for video_name in "${!video_urls[@]}"; do
    echo "Downloading ${video_name}..."
    curl -L "${video_urls[$video_name]}" -o "${VIDEO_DIR}/${video_name}"
    if [ ! -f "${VIDEO_DIR}/${video_name}" ]; then
        echo "Error: Failed to download ${video_name}"
        exit 1
    fi
done

echo "Videos setup completed."

deactivate
echo "=== All tasks completed successfully. ==="



