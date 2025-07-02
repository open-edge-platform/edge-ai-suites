#!/bin/bash

# Download artifacts for a specific sample application
#   by calling respective app's install.sh script
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
MODEL_XML_URL="https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/9da6eb59431eb7edbc5491e8d6ee37d347bebcbb/manufacturing-ai-suite/pallet-defect-detection/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml"
MODEL_BIN_URL="https://github.com/open-edge-platform/edge-ai-suites/raw/9da6eb59431eb7edbc5491e8d6ee37d347bebcbb/manufacturing-ai-suite/pallet-defect-detection/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.bin"
VIDEO_URL="https://github.com/open-edge-platform/edge-ai-suites/raw/9da6eb59431eb7edbc5491e8d6ee37d347bebcbb/manufacturing-ai-suite/pallet-defect-detection/resources/videos/warehouse.avi"
VIDEO_FILENAME="warehouse.avi"

err() {
    echo "ERROR: $1" >&2
}

download_artifacts() {
    local app_name=$1
    echo "$SCRIPT_DIR"
    if [ ! -d "$SCRIPT_DIR" ]; then
        err "Application directory '$SCRIPT_DIR' does not exist."
        return 1
    fi
    # Download model artifacts if not already present
    LOCAL_MODEL_DIR="$SCRIPT_DIR/../../resources/$app_name/models/pallet-defect-detection"
    if [ ! -d $LOCAL_MODEL_DIR ]; then
        # create the models directory if it does not exist

        if ! mkdir -p $LOCAL_MODEL_DIR; then
            err "Failed to create models directory for $app_name."
            return 1
        fi
        echo "Downloading model artifacts for $app_name..."
        echo "Model XML: $MODEL_XML_URL"
        echo "Model BIN: $MODEL_BIN_URL"
        # Download model XML and BIN files
        if curl -L "$MODEL_XML_URL" -o "$LOCAL_MODEL_DIR/model.xml"; then
            echo "Model XML for $app_name downloaded successfully."
        else
            err "Failed to download model XML for $app_name."
            return 1
        fi
        if curl -L "$MODEL_BIN_URL" -o "$LOCAL_MODEL_DIR/model.bin"; then
            echo "Model BIN for $app_name downloaded successfully."
        else
            err "Failed to download model BIN for $app_name."
            return 1
        fi
    else
        echo "Model artifacts for $app_name already exist."
    fi

    # Download video artifacts if not already present
    LOCAL_VIDEO_DIR="$SCRIPT_DIR/../../resources/$app_name/videos"
    if [ ! -d $LOCAL_VIDEO_DIR ]; then
        # create the videos directory if it does not exist
        if ! mkdir -p $LOCAL_VIDEO_DIR; then
            err "Failed to create videos directory for $app_name."
            return 1
        fi
        echo "Downloading video artifacts for $app_name..."
        if ! curl -L "$VIDEO_URL" -o "$LOCAL_VIDEO_DIR/$(basename $VIDEO_URL)"; then
            err "Failed to download video for $app_name."
            return 1
        fi
        echo "Video artifacts for $app_name downloaded successfully."
    else
        echo "Video artifacts for $app_name already exist."
    fi
    return 0

}

download_artifacts "pallet-defect-detection"
