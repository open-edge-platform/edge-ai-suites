#!/bin/bash

# multifilesrc loop=true location=/home/pipeline-server/videos/1122east.ts name=source ! decodebin3 \
# ! vapostproc ! video/x-raw(memory:VAMemory) \
# ! gvapython class=PostDecodeTimestampCapture function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=timesync \
# ! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=/home/pipeline-server/models/object_detection/intersection/openvino.xml pre-process-backend=va-surface-sharing \
# ! queue ! gvametaconvert add-tensor-data=true name=metaconvert ! vapostproc ! video/x-raw,format=BGRA ! videoconvert ! video/x-raw,format=BGR \
# ! gvapython class=PostInferenceDataPublish function=processFrame module=/home/pipeline-server/user_scripts/gvapython/sscape/sscape_adapter.py name=datapublisher \
# ! gvametapublish name=destination ! appsink sync=true

INPUT=1122east.ts

INPUT_ARRAY=(1122east.ts 1122north.ts 1122south.ts 1122west.ts)

VIDEOS_DIR=./src/dlstreamer-pipeline-server/videos
MODELS_DIR=./src/dlstreamer-pipeline-server/models
OUTPUT_DIR=./perf_test/output

# echo "ROOT_DIR=$(pwd)" > perf_test/.env
# docker compose -f perf_test/docker-compose.yml up -d --force-recreate --remove-orphans

# docker run --rm \
# -v ${VIDEOS_DIR}:/data \
# -v ${MODELS_DIR}:/models \
# -v ${OUTPUT_DIR}:/output \
# -e GST_DEBUG="GST_TRACER:7" \
# -e GST_TRACERS="latency_tracer(flags=pipeline,interval=1000)" \
# --device /dev/dri \
# --group-add $(stat -c "%g" /dev/dri/render*) \
# --device /dev/accel \
# --group-add $(stat -c "%g" /dev/accel/accel*) \
# intel/dlstreamer:2025.1.2-ubuntu24 \
# gst-launch-1.0 multifilesrc loop=true location=/data/${INPUT} name=source ! decodebin3 ! timecodestamper set=always ! vapostproc ! "video/x-raw(memory:VAMemory)" \
#  ! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=/models/intersection/openvino.xml pre-process-backend=va-surface-sharing ! queue \
#  ! gvafpscounter ! gvametaconvert add-empty-results=true name=metaconvert ! gvametapublish method=file file-path=/output/results.jsonl file-format=2 ! appsink sync=false

# Create logs directory if it doesn't exist
mkdir -p logs

# Run multiple pipelines in parallel, each with different video from INPUT_ARRAY
for i in "${!INPUT_ARRAY[@]}"; do
    PPL_ID=$i
    INPUT=${INPUT_ARRAY[$i]}
    
    echo "Starting pipeline ${PPL_ID} with input: ${INPUT}"
    
    docker run --rm -v ${VIDEOS_DIR}:/data -v ${MODELS_DIR}:/models \
    -e GST_DEBUG="GST_TRACER:7" \
    -e GST_TRACERS="latency_tracer(flags=pipeline,interval=1000)" \
    --device /dev/dri \
    --group-add $(stat -c "%g" /dev/dri/render*) \
    --device /dev/accel \
    --group-add $(stat -c "%g" /dev/accel/accel*) \
    intel/dlstreamer:2025.1.2-ubuntu24 \
    gst-launch-1.0 multifilesrc loop=true location=/data/${INPUT} name=source ! decodebin3 ! timecodestamper set=always ! vapostproc ! "video/x-raw(memory:VAMemory)" \
     ! gvadetect batch-size=8 device=GPU model-instance-id=detect${PPL_ID} inference-interval=1 model=/models/intersection/openvino.xml pre-process-backend=va-surface-sharing ! queue \
     ! gvafpscounter interval=1 starting-frame=1000 print-latency=true ! appsink sync=false > logs/run_dls_ppl_${PPL_ID}.log 2>&1 &

    echo "Pipeline ${PPL_ID} started with PID: $!"
done

echo "All pipelines started. Log files:"
for i in "${!INPUT_ARRAY[@]}"; do
    echo "  - logs/run_dls_ppl_${i}.log (${INPUT_ARRAY[$i]})"
done
echo ""
echo "To monitor progress, use: tail -f logs/run_dls_ppl_*.log"
echo "To stop all pipelines, use: pkill -f 'gst-launch-1.0.*multifilesrc'"

# Wait for all background jobs to complete (optional)
wait

# gst-launch-1.0 filesrc location=${VIDEOS_DIR}/${INPUT} name=source ! parsebin ! vah264dec ! "video/x-raw(memory:VAMemory)" \
# ! gvadetect device=GPU model-instance-id=detect1 inference-interval=1 model=${MODELS_DIR}/intersection/openvino.xml pre-process-backend=va-surface-sharing ! queue \
# ! gvafpscounter ! appsink sync=true
