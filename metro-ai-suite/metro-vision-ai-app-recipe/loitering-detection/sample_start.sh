#!/bin/bash

DLSPS_NODE_IP="localhost"

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
            "topic": "object_tracking/$x",
            "publish_frame":false
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_tracking_$x",
            "overlay-properties": {
                "font-scale": 1.0,
                "draw-txt-bg": false
            }
        }
    },
    "parameters": {
        "analytics-properties": {
            "config": "/home/pipeline-server/zones/VIRAT_S_00010$x.json"
        },
        "loitering-watermark-properties": {
            "loitering-threshold": 5.0
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


function deploy_with_gui() {
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

  echo
  echo ">>>>>--gui requested: stopping any running pipelines first."
  # Tolerate failure here: on a first-ever run nothing is deployed yet, so
  # the pipeline-server this talks to does not exist and the curls below
  # fail - that is expected, not an error worth aborting over.
  "$SCRIPT_DIR/sample_stop.sh" || true

  HOST_IP="$(grep -E '^HOST_IP=' "$REPO_ROOT/.env" 2>/dev/null | cut -d '=' -f2)"
  HOST_IP="${HOST_IP:-$(hostname -I | cut -f1 -d' ')}"

  echo ">>>>>Regenerating docker-compose.yml with the Console UI service included..."
  (cd "$REPO_ROOT" && WITH_GUI=1 ./install.sh loitering-detection "$HOST_IP")
  if [ $? -ne 0 ]; then
    echo "Error: install.sh failed; see output above."
    exit 1
  fi

  echo ">>>>>Deploying the full stack, including the Console UI..."
  (cd "$REPO_ROOT" && docker compose up -d --build)
  if [ $? -ne 0 ]; then
    echo "Error: docker compose up failed; see output above."
    exit 1
  fi
  echo ">>>>>Console UI available at https://$HOST_IP/console/"
}

forcedCPU=false
forcedGPU=false
forcedNPU=false
withGui=false

# --gui is consumed here, before the cpu/gpu/npu loop below, so it is never
# mistaken for an unrecognised device argument (which would otherwise force
# CPU and print a warning).
args=()
for arg in "$@"; do
  if [ "$arg" == "--gui" ]; then
    withGui=true
  else
    args+=("$arg")
  fi
done
set -- "${args[@]}"

if $withGui; then
  deploy_with_gui
fi

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

