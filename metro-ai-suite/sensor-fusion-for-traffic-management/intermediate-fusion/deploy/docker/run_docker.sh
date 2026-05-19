set -euo pipefail

DOCKER_IMAGE=${1:-tfcc:bevfusion}

EXTRA_PARAMS=""

VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}' || true)
if [[ -n "${VIDEO_GROUP_ID:-}" ]]; then
    EXTRA_PARAMS+="--group-add ${VIDEO_GROUP_ID} "
else
    printf "\nWARNING: video group wasn't found! GPU device(s) may not work inside the container.\n\n"
fi

RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}' || true)
if [[ -n "${RENDER_GROUP_ID:-}" ]]; then
    EXTRA_PARAMS+="--group-add ${RENDER_GROUP_ID} "
fi

ACCEL_PARAMS=""
if [[ -d /dev/accel ]]; then
    ACCEL_GID=$(stat -c "%g" /dev/accel/accel* 2>/dev/null | sort -u | head -n 1 || true)
    if [[ -n "${ACCEL_GID:-}" ]]; then
        ACCEL_PARAMS+="--device /dev/accel --group-add ${ACCEL_GID} --env ZE_ENABLE_ALT_DRIVERS=libze_intel_vpu.so "
    else
        ACCEL_PARAMS+="--device /dev/accel --env ZE_ENABLE_ALT_DRIVERS=libze_intel_vpu.so "
    fi
fi


docker run -itd --net=host \
    --entrypoint /bin/bash \
    -e no_proxy=localhost,127.0.0.1 \
    -e http_proxy=${http_proxy:-} \
    -e https_proxy=${https_proxy:-} \
    --cap-add=SYS_ADMIN \
    --device /dev/dri \
    ${EXTRA_PARAMS} \
    ${ACCEL_PARAMS} \
    -e DISPLAY=$DISPLAY \
    -e QT_X11_NO_MITSHM=1 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $HOME/.Xauthority:/home/tfcc/.Xauthority:rw \
    -w /home/tfcc/bevfusion \
    $DOCKER_IMAGE
