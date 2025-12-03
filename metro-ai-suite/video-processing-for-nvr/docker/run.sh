DOCKER_IMAGE=${1-intel/vppsample:2025.2.0}
NPU_ON=${2-false}

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


# -e DISPLAY_NEW_PLATFORM=1 \
if [[ "$NPU_ON" == "true" ]]; then
    echo "Running with NPU support"
    docker run -it --net=host \
        -e no_proxy=localhost,127.0.0.1 \
        -e http_proxy=${http_proxy} \
        -e https_proxy=${https_proxy} \
        -e LD_LIBRARY_PATH=/usr/local/lib \
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
        -e http_proxy=${http_proxy} \
        -e https_proxy=${https_proxy} \
        -e LD_LIBRARY_PATH=/usr/local/lib \
        --cap-add=SYS_ADMIN \
        --device /dev/dri \
        --group-add $VIDEO_GROUP_ID --group-add $RENDER_GROUP_ID \
        --user root \
        --entrypoint /home/vpp/vppsample/docker/svet.sh \
        -e DISPLAY=$DISPLAY \
        -w /home/vpp \
        $DOCKER_IMAGE
fi
