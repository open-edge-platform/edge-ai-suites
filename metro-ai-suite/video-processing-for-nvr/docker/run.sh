MODEL_PATH=${1-/home/vpp/yolov8n_int8/yolov8n_with_preprocess.xml}
DOCKER_IMAGE=${2-vppsample:2025.2.0}
NPU_ON=${3-false}

EXTRA_PARAMS=""
 
VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}')
if [[ -n "$VIDEO_GROUP_ID" ]]; then
    EXTRA_PARAMS+="--group-add $VIDEO_GROUP_ID "
else
    printf "\nWARNING: video group wasn't found! GPU device(s) probably won't work inside the Docker image.\n\n";
fi
RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}')
if [[ -n "$RENDER_GROUP_ID" ]]; then
    EXTRA_PARAMS+="--group-add $RENDER_GROUP_ID "
fi
USER_GROUP_ID=$(id -g)
echo $EXTRA_PARAMS

if [[ -z "${MODEL_PATH}" ]]; then
    echo "Error: MODEL_PATH (1rd argument) is required."
    exit 1
fi

ABS_MODEL_PATH=$(realpath "$MODEL_PATH")
if [[ ! -f "$ABS_MODEL_PATH" ]]; then
    echo "Error: Model file not found: $MODEL_PATH"
    exit 1
fi
MODEL_DIR=$(dirname "$ABS_MODEL_PATH")
MODEL_FILE=$(basename "$ABS_MODEL_PATH")

echo $MODEL_DIR
echo $MODEL_FILE

if [[ "$NPU_ON" == "true" ]]; then
    echo "Running with NPU support"
    docker run -it --net=host \
        -e no_proxy=localhost,127.0.0.1 \
        -e http_proxy=${http_proxy} \
        -e https_proxy=${https_proxy} \
        -e LD_LIBRARY_PATH=/usr/local/lib \
        -e DISPLAY_NEW_PLATFORM=1 \
        --cap-add=SYS_ADMIN \
        --device /dev/dri \
        --group-add $VIDEO_GROUP_ID --group-add $RENDER_GROUP_ID \
        --device /dev/accel \
        --group-add $(stat -c "%g" /dev/accel/accel* | sort -u | head -n 1) \
        --env ZE_ENABLE_ALT_DRIVERS=libze_intel_vpu.so \
        --user root \
        -e DISPLAY=$DISPLAY \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v $HOME/.Xauthority:/root/.Xauthority:rw \
        -w /home/vpp \
        $DOCKER_IMAGE
else
    docker run -it --net=host \
        -e no_proxy=localhost,127.0.0.1 \
        -e http_proxy="${http_proxy}" \
        -e https_proxy="${https_proxy}" \
        -e LD_LIBRARY_PATH=/usr/local/lib \
        -e DISPLAY_NEW_PLATFORM=1 \
        --cap-add=SYS_ADMIN \
        --device /dev/dri \
        ${VIDEO_GROUP_ID:+--group-add $VIDEO_GROUP_ID} \
        ${RENDER_GROUP_ID:+--group-add $RENDER_GROUP_ID} \
        --user root \
        --entrypoint /home/vpp/vppsample/docker/run_dec_det.sh \
        -e DISPLAY="$DISPLAY" \
        -w /home/vpp \
        -v "$MODEL_DIR:/models:ro" \
        "$DOCKER_IMAGE" \
        "/models/$MODEL_FILE"
    # docker run -it --rm \
    #     --net=host \
    #     -e no_proxy=localhost,127.0.0.1 \
    #     -e http_proxy="${http_proxy}" \
    #     -e https_proxy="${https_proxy}" \
    #     -e LD_LIBRARY_PATH=/usr/local/lib \
    #     -e DISPLAY_NEW_PLATFORM=1 \
    #     --cap-add=SYS_ADMIN \
    #     --device /dev/dri \
    #     ${VIDEO_GROUP_ID:+--group-add $VIDEO_GROUP_ID} \
    #     ${RENDER_GROUP_ID:+--group-add $RENDER_GROUP_ID} \
    #     --user root \
    #     -e DISPLAY="$DISPLAY" \
    #     -w /home/vpp \
    #     -v "$MODEL_DIR:/models:ro" \
    #     "$DOCKER_IMAGE" \
    #     bash
fi