#!/bin/bash

DLSPS_NODE_IP="localhost"
ZONE_CONFIG="$(dirname "$(readlink -f "$0")")/src/dlstreamer-pipeline-server/configs/loitering_analytics_config.json"
# The pipelines bake in no model, so that a different one can be selected per
# request without inheriting this model's post-processing.
MODEL_DIR="/home/pipeline-server/models/intel/pedestrian-and-vehicle-detector-adas-0001"
MODEL_XML="$MODEL_DIR/FP16/pedestrian-and-vehicle-detector-adas-0001.xml"
MODEL_PROC="$MODEL_DIR/pedestrian-and-vehicle-detector-adas-0001.json"

# The pipelines deliberately bake in no zone: gvaanalytics does not cleanly
# replace a zone already loaded from a config= file, so a baked zone could
# never be overridden by the console. The zone is therefore always supplied
# at start time, and this file is its single source of truth - edit it to
# change the zone the sample pipelines evaluate.
if [ ! -f "$ZONE_CONFIG" ]; then
  echo "Error: zone configuration not found at $ZONE_CONFIG"
  exit 1
fi
ZONES_JSON=$(python3 -c "import json,sys; print(json.dumps(json.dumps(json.load(open(sys.argv[1]))['zones'])))" "$ZONE_CONFIG") || {
  echo "Error: could not read zones from $ZONE_CONFIG"
  exit 1
}
# gvaattachroi restricts inference to the zone (the pipeline sets
# inference-region=1), and takes opposite corners rather than x/y/w/h.
ATTACH_ROI=$(python3 -c "
import json,sys
pts = json.load(open(sys.argv[1]))['zones'][0]['points']
xs = [p['x'] for p in pts]; ys = [p['y'] for p in pts]
print('%d,%d,%d,%d' % (min(xs), min(ys), max(xs), max(ys)))
" "$ZONE_CONFIG") || {
  echo "Error: could not derive the inference ROI from $ZONE_CONFIG"
  exit 1
}

function run_sample() {
  pipelines=$1
  device=$2
  interval=10
  if [ $device == "GPU" ]; then
    pipeline_name="object_tracking_gpu"
  elif [ $device == "NPU" ]; then
    pipeline_name="object_tracking_npu"
  else
    pipeline_name="object_tracking_cpu"
  fi
  pipeline_list=()
  echo
  echo -n ">>>>>Initialization..."
  for x in $(seq 1 $pipelines); do
    payload=$(cat <<EOF
   {
    "source": {
        "uri": "file:///home/pipeline-server/videos/VIRAT_S_00010$x.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_tracking_$x",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_$x"
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "$MODEL_XML",
            "model_proc": "$MODEL_PROC"
        },
        "analytics-properties": {
            "zones": $ZONES_JSON
        },
        "attachroi-properties": {
            "roi": "$ATTACH_ROI"
        }
    }
  }
EOF
)
    response=$(curl -k  -s "https://$DLSPS_NODE_IP/api/pipelines/user_defined_pipelines/${pipeline_name}" -X POST -H "Content-Type: application/json" -d "$payload")
    if [ $? -ne 0 ]; then
      echo -e "\nError: curl -k command failed. Check the deployment status."
      return 1
    fi
    sleep 2
    pipeline_list+=("$response")
  done
  running=false
  while [ "$running" != true ]; do
    status=$(curl -k -s --location -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" | grep state | awk ' { print $2 } ' | tr -d \")
    if [[ "$status" == *"QUEUED"* ]]; then
      running=false
      echo -n "."
      sleep 1
    else
      running=true
      echo -n "Pipelines initialized."
      echo
    fi
  done
}

function stop_all_pipelines() {
  echo
  echo -n ">>>>>Stopping all running pipelines."
  status=$(curl -k -s -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" -H "accept: application/json")
  if [ $? -ne 0 ]; then
    echo -e "\nError: curl -k command failed. Check the deployment status."
    return 1
  fi
  pipelines=$(echo $status  | grep -o '"id": "[^"]*"' | awk ' { print $2 } ' | tr -d \"  | paste -sd ',' - )
  IFS=','
  for pipeline in $pipelines; do
    response=$(curl -k -s --location -X DELETE "https://$DLSPS_NODE_IP/api/pipelines/${pipeline}")
    sleep 2
  done
  unset IFS
  running=true
  while [ "$running" == true ]; do
    echo -n "."
    status=$(curl -k -s --location -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" | grep state | awk ' { print $2 } ' | tr -d \")
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


forcedCPU=false
forcedGPU=false
forcedNPU=false

for arg in "$@"; do
  if [ "$arg" == "cpu" ]; then
      forcedCPU=true
      forcedGPU=false
      forcedNPU=false
  elif [ "$arg" == "gpu" ]; then
      forcedCPU=false
      forcedGPU=true
      forcedNPU=false
  elif [ "$arg" == "npu" ]; then
      forcedCPU=false
      forcedGPU=false
      forcedNPU=true
  else
      echo "Unknown argument '$arg', defaulting to CPU"
      forcedCPU=true
      forcedGPU=false
      forcedNPU=false
  fi
done

# If no arguments provided, default to CPU
if [ $# -eq 0 ]; then
  echo "No device selected, defaulting to CPU"
  forcedCPU=true
fi


stop_all_pipelines

if [ $? -ne 0 ]; then
   exit 1
fi


# Check if any render device exists
if $forcedGPU; then
  if ls /dev/dri/renderD* 1> /dev/null 2>&1; then
    echo -e "\n>>>>>GPU device selected."
    run_sample 4 GPU
    if [ $? -ne 0 ]; then
      exit 1
    fi
  else
    echo -e "\n>>>>>No GPU device found. Please check your GPU driver installation or use CPU."
    exit 0
  fi
elif $forcedNPU; then
  if ls /dev/accel/accel* 1> /dev/null 2>&1; then
    echo -e "\n>>>>>NPU device selected."
    run_sample 4 NPU
    if [ $? -ne 0 ]; then
      exit 1
    fi
  else
    echo -e "\n>>>>>No NPU device found. Please check your NPU driver installation or use CPU."
    exit 0
  fi
elif $forcedCPU; then
  echo -e "\n>>>>>CPU device selected."
  run_sample 4 CPU
  if [ $? -ne 0 ]; then
      exit 1
    fi
fi

echo -e "\n>>>>>Results are visualized in Grafana at 'https://localhost/grafana' "
echo -e "\n>>>>>Pipelines status can be checked with 'curl -k --location -X GET https://localhost/api/pipelines/status' or using script 'sample_status.sh'. \n"

