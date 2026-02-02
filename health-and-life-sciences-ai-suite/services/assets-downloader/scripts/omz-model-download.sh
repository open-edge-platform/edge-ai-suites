#!/bin/bash
set -e

MODEL_NAME="human-pose-estimation-3d-0001"
PRECISION="FP16"

if [[ -n "$http_proxy" || -n "$https_proxy" ]]; then
    cat <<EOF > /etc/wgetrc
use_proxy = on
http_proxy = $http_proxy
https_proxy = $https_proxy
no_proxy = $no_proxy
EOF
    git config --global http.proxy "$http_proxy"
    git config --global https.proxy "$https_proxy"
fi

MODELS_PATH=${2:-"/models/3d-pose"}
VIDEOS_PATH="/videos/3d-pose"
OMZ_DIR="/tmp/open_model_zoo"

mkdir -p "$MODELS_PATH" "$VIDEOS_PATH"

MODEL_XML_FINAL="$MODELS_PATH/$MODEL_NAME.xml"
MODEL_BIN_FINAL="$MODELS_PATH/$MODEL_NAME.bin"

if [[ -f "$MODEL_XML_FINAL" && -f "$MODEL_BIN_FINAL" ]]; then
    echo "Model $MODEL_NAME already exists in $MODELS_PATH"
    exit 0
fi

rm -rf "$OMZ_DIR"
git clone --depth 1 https://github.com/openvinotoolkit/open_model_zoo.git "$OMZ_DIR"

TOOLS_DIR="$OMZ_DIR/tools/model_tools"

python3 "$TOOLS_DIR/downloader.py" \
    --name "$MODEL_NAME" \
    --output_dir "$MODELS_PATH" \
    --cache_dir /tmp/omz_cache \
    --precisions "$PRECISION"

python3 "$TOOLS_DIR/converter.py" \
    --name "$MODEL_NAME" \
    --precisions "$PRECISION" \
    --download_dir "$MODELS_PATH" \
    --output_dir "$MODELS_PATH"

XML_SRC=$(find "$MODELS_PATH" -type f -name "$MODEL_NAME.xml" | head -n1 || true)
BIN_SRC=$(find "$MODELS_PATH" -type f -name "$MODEL_NAME.bin" | head -n1 || true)

if [[ -z "$XML_SRC" || -z "$BIN_SRC" ]]; then
    echo "ERROR: Could not locate converted IR files for $MODEL_NAME under $MODELS_PATH" >&2
    exit 1
fi

mv "$XML_SRC" "$MODEL_XML_FINAL"
mv "$BIN_SRC" "$MODEL_BIN_FINAL"

for item in "$MODELS_PATH"/*; do
    if [[ "$item" != "$MODEL_XML_FINAL" && "$item" != "$MODEL_BIN_FINAL" ]]; then
        rm -rf "$item"
    fi
done

rm -rf "$OMZ_DIR" /tmp/omz_cache || true

VIDEO_URL="https://storage.openvinotoolkit.org/data/test_data/videos/face-demographics-walking.mp4"
VIDEO_PATH="$VIDEOS_PATH/face-demographics-walking.mp4"

if [[ ! -f "$VIDEO_PATH" ]]; then
    wget -O "$VIDEO_PATH" "$VIDEO_URL"
fi

find "$MODELS_PATH" -maxdepth 1 -type f \( -name "*.xml" -o -name "*.bin" \)
find "$VIDEOS_PATH" -maxdepth 1 -type f -name "*.mp4"
