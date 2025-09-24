#!/bin/bash

# multifilesrc loop=true location=/home/pipeline-server/videos/1122east.ts name=source ! decodebin3 \
# ! vapostproc ! video/x-raw(memory:VAMemory) \
# ! gvapython class=PostDecodeTimestampCapture function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=timesync \
# ! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=/home/pipeline-server/models/object_detection/intersection/openvino.xml pre-process-backend=va-surface-sharing \
# ! queue ! gvametaconvert add-tensor-data=true name=metaconvert ! vapostproc ! video/x-raw,format=BGRA ! videoconvert ! video/x-raw,format=BGR \
# ! gvapython class=PostInferenceDataPublish function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=datapublisher \
# ! gvametapublish name=destination ! appsink sync=true

INPUTS=1122east.ts
VIDEOS_DIR=./src/dlstreamer-pipeline-server/videos
MODELS_DIR=./src/dlstreamer-pipeline-server/models

docker run --rm -e GST_DEBUG=3 -v ${VIDEOS_DIR}:/data -v ${MODELS_DIR}:/models \
--device /dev/dri \
--group-add $(stat -c "%g" /dev/dri/render*) \
--device /dev/accel \
--group-add $(stat -c "%g" /dev/accel/accel*) \
intel/dlstreamer:2025.1.2-ubuntu24 \
gst-launch-1.0 multifilesrc loop=true location=/data/${INPUTS} name=source ! decodebin3 \
! vapostproc ! video/x-raw\(memory:VAMemory\) \
! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=/models/object_detection/intersection/openvino.xml pre-process-backend=va-surface-sharing \
! queue ! gvafpscounter ! fakesink
