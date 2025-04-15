#!/bin/bash

DLSPS_NODE_IP="localhost"
DLSPS_PORT=8080

function run_sample() {
  pipelines=$1
  device=$2
  interval=10
  if [ $device == "GPU" ]; then
    pipeline_name="yolov10_1_gpu"
  else
    pipeline_name="yolov10_1_cpu"
  fi
  
  pipeline_list=()

  for x in $(seq 1 $pipelines); do
    payload=$(cat <<EOF
   {
    "source": {
        "uri": "file:///home/pipeline-server/videos/new_video_$x.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "host": "0.0.0.0:1883",
            "topic": "object_detection_$x",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_$x"
        }
    },
    "parameters": {
        "detection-device": "$device",
        "classification-device": "$device"
    }
  }
EOF
)

    response=$(curl  -s "http://$DLSPS_NODE_IP:$DLSPS_PORT/pipelines/user_defined_pipelines/${pipeline_name}" -X POST -H "Content-Type: application/json" -d "$payload")
    pipeline_list+=("$response")
  done
  running=false
  while [ "$running" != true ]; do
    status=$(curl -s --location -X GET "http://$DLSPS_NODE_IP:$DLSPS_PORT/pipelines/status" | grep state | awk ' { print $2 } ' | tr -d \")
    if [[ "$status" == *"QUEUED"* ]]; then
      running=false
    else
      running=true
      echo -e "\n>>>>>Pipelines initialized."
    fi
  done
}

function stop_all_pipelines() {
  echo
  echo -n ">>>>>Stopping all running pipelines."
  pipelines=$(curl -s -X GET "http://$DLSPS_NODE_IP:$DLSPS_PORT/pipelines/status" -H "accept: application/json" | grep id | awk ' { print $2 } ' | tr -d \"  | tr -d '\n')
  if [ $? -ne 0 ]; then
    echo -e "\nError: curl command failed."
    return 1
  fi
  IFS=','
  for pipeline in $pipelines; do
    response=$(curl -s --location -X DELETE "http://$DLSPS_NODE_IP:$DLSPS_PORT/pipelines/${pipeline}")
  done
  unset IFS
  running=true
  while [ "$running" == true ]; do
    echo -n "."
    status=$(curl -s --location -X GET "http://$DLSPS_NODE_IP:$DLSPS_PORT/pipelines/status" | grep state | awk ' { print $2 } ' | tr -d \")
    if [[ "$status" == *"RUNNING"* ]]; then
      running=true
      sleep 2
     else
      running=false
     fi
  done
  echo -n " done."
  echo
  return 0
}


forcedCPU=true
forcedGPU=false

for arg in "$@"; do
  if [ "$arg" == "cpu" ]; then
      forcedCPU=true
  elif [ "$arg" == "gpu" ]; then
      forcedGPU=true
  fi
done


stop_all_pipelines

if [ $? -ne 0 ]; then
   exit 1
fi


# Check if any render device exists
if $forcedGPU; then
  if ls /dev/dri/renderD* 1> /dev/null 2>&1; then
    echo -e "\n>>>>>GPU device selected."
    run_sample 4 GPU
  else
    echo -e "\n>>>>>No GPU device found. Please check your GPU driver installation or use CPU."
    exit 0
  fi
elif $forcedCPU; then
  echo -e "\n>>>>>CPU device selected."
  run_sample 4 CPU
fi

echo -e "\n>>>>>Results are visualized in Grafana at 'http://localhost:3000' "
echo -e "\n>>>>>Pipelines status can be checked with 'curl --location -X GET http://localhost:8080/pipelines/status' or using script 'sample_status.sh'. \n"

