DOCKER_IMAGE=${1-tfcc:latest}
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
MEI_DEVICES=""
for device in /dev/mei*; do
    if [ -e "$device" ]; then
        MEI_DEVICES="$MEI_DEVICES --device $device"
        echo "Found MEI device: $device"
    fi
done

if [[ "$NPU_ON" == "true" ]]; then
    echo "Running with NPU support"
    docker run -itd --net=host \
        --entrypoint /bin/bash \
        -e no_proxy=localhost,127.0.0.1 \
        -e http_proxy=${http_proxy} \
        -e https_proxy=${https_proxy} \
        --cap-add=SYS_ADMIN \
        --device /dev/dri \
        --group-add $VIDEO_GROUP_ID --group-add $RENDER_GROUP_ID \
        --device /dev/accel \
        $MEI_DEVICES \
        --group-add $(stat -c "%g" /dev/accel/accel* | sort -u | head -n 1) \
        --env ZE_ENABLE_ALT_DRIVERS=libze_intel_vpu.so \
        -e DISPLAY=$DISPLAY \
        -e QT_X11_NO_MITSHM=1 \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v $HOME/.Xauthority:/home/tfcc/.Xauthority:rw \
        -w /home/tfcc/metro \
        $DOCKER_IMAGE
else
    echo "Running without NPU support"
    docker run -itd --net=host \
        --entrypoint /bin/bash \
        -e no_proxy=localhost,127.0.0.1 \
        -e http_proxy=${http_proxy} \
        -e https_proxy=${https_proxy} \
        --cap-add=SYS_ADMIN \
        --device /dev/dri \
        $MEI_DEVICES \
        --group-add $VIDEO_GROUP_ID --group-add $RENDER_GROUP_ID \
        -e DISPLAY=$DISPLAY \
        -e QT_X11_NO_MITSHM=1 \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v $HOME/.Xauthority:/home/tfcc/.Xauthority:rw \
        -w /home/tfcc/metro \
        $DOCKER_IMAGE
fi
