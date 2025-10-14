#!/bin/bash

# multifilesrc loop=true location=/home/pipeline-server/videos/1122east.ts name=source ! decodebin3 \
# ! vapostproc ! video/x-raw(memory:VAMemory) \
# ! gvapython class=PostDecodeTimestampCapture function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=timesync \
# ! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=/home/pipeline-server/models/object_detection/intersection/openvino.xml pre-process-backend=va-surface-sharing \
# ! queue ! gvametaconvert add-tensor-data=true name=metaconvert ! vapostproc ! video/x-raw,format=BGRA ! videoconvert ! video/x-raw,format=BGR \
# ! gvapython class=PostInferenceDataPublish function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=datapublisher \
# ! gvametapublish name=destination ! appsink sync=true

INPUT_VIDEO=1122east.ts
INPUT_RTSP=rtsp://127.0.0.1:8554/cam1

VIDEOS_DIR=./src/dlstreamer-pipeline-server/videos
MODELS_DIR=./src/dlstreamer-pipeline-server/models
OUTPUT_DIR=./perf_test/output

echo "ROOT_DIR=$(pwd)" > perf_test/.env
echo "INPUT_RTSP=${INPUT_RTSP}" >> perf_test/.env

# Create logs directory if it doesn't exist
mkdir -p logs

docker compose -f perf_test/docker-compose_rtsp.yml up -d
echo "Started RTSP server and camera stream in Docker containers."
echo "Run to stop: docker compose -f perf_test/docker-compose_rtsp.yml down"
echo "Waiting for the RTSP stream to initialize..."

# Wait until the RTSP stream is available
until gst-discoverer-1.0 ${INPUT_RTSP} > /dev/null 2>&1; do
    echo "Waiting for RTSP stream at ${INPUT_RTSP} to become available..."
    sleep 2
done
echo "RTSP stream at ${INPUT_RTSP} is now available."

docker run --rm -v ${VIDEOS_DIR}:/data -v ${MODELS_DIR}:/models \
--network=host \
-e GST_DEBUG="3,GST_TRACER:7" \
-e GST_TRACERS="latency_tracer(flags=pipeline)" \
--device /dev/dri \
--group-add $(stat -c "%g" /dev/dri/render*) \
--device /dev/accel \
--group-add $(stat -c "%g" /dev/accel/accel*) \
intel/dlstreamer:2025.1.2-ubuntu24 \
gst-launch-1.0 \
rtspsrc location=${INPUT_RTSP} latency=100 protocols=udp ! decodebin3 ! timecodestamper set=always ! vapostproc ! "video/x-raw(memory:VAMemory)" \
 ! gvadetect batch-size=2 scheduling-policy=latency device=GPU model-instance-id=detect1 inference-interval=1 model=/models/intersection/openvino.xml pre-process-backend=va-surface-sharing ! queue \
 ! gvafpscounter interval=1 starting-frame=1000 print-latency=true ! appsink sync=false \
rtspsrc location=${INPUT_RTSP} latency=100 protocols=udp ! decodebin3 ! timecodestamper set=always ! vapostproc ! "video/x-raw(memory:VAMemory)" \
 ! gvadetect batch-size=2 scheduling-policy=latency device=GPU model-instance-id=detect1 inference-interval=1 model=/models/intersection/openvino.xml pre-process-backend=va-surface-sharing ! queue \
 ! gvafpscounter interval=1 starting-frame=1000 print-latency=true ! appsink sync=false > logs/run_dls_2ppl_rtsp.log 2>&1 &
