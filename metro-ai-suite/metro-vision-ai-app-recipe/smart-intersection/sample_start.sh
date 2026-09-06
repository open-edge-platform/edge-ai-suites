#!/bin/bash

DLSPS_NODE_IP="localhost"

function detect_sku() {
  CPU_MODEL=$(grep "model name" /proc/cpuinfo 2>/dev/null | head -1 | sed 's/.*: //' | xargs)
  GPU_INFO="Not detected"
  if ls /dev/dri/renderD* 1>/dev/null 2>&1; then
    for card in /sys/class/drm/card*/; do
      pname=$(cat "${card}device/product_name" 2>/dev/null)
      if [ -n "$pname" ]; then
        GPU_INFO="$pname"
        break
      fi
    done
    [ "$GPU_INFO" = "Not detected" ] && GPU_INFO="Intel iGPU (device present)"
  fi
  NPU_INFO="Not present"
  ls /dev/accel/accel* 1>/dev/null 2>&1 && NPU_INFO="Intel NPU (device present)"
  echo "============================================================"
  echo "  SYSTEM SKU"
  echo "  CPU : ${CPU_MODEL:-Unknown}"
  echo "  iGPU: ${GPU_INFO}"
  echo "  NPU : ${NPU_INFO}"
  echo "============================================================"
}

function stop_all_pipelines() {
  echo
  echo -n ">>>>>Stopping all running pipelines."
  status=$(curl -k -s -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" -H "accept: application/json")
  if [ $? -ne 0 ]; then
    echo -e "\nError: curl -k command failed. Check the deployment status."
    return 1
  fi
  pipelines=$(echo $status | grep -o '"id": "[^"]*"' | awk '{ print $2 }' | tr -d \" | paste -sd ',' -)
  IFS=','
  for pipeline in $pipelines; do
    curl -k -s --location -X DELETE "https://$DLSPS_NODE_IP/api/pipelines/${pipeline}" > /dev/null
    sleep 2
  done
  unset IFS
  running=true
  while [ "$running" == true ]; do
    echo -n "."
    status=$(curl -k -s --location -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" | grep state | awk '{ print $2 }' | tr -d \")
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

function run_sample() {
  pipeline_suffix=$1
  echo
  echo -n ">>>>>Initialization..."

  cameras=("1:north:camera1" "2:east:camera2" "3:south:camera3" "4:west:camera4")
  for entry in "${cameras[@]}"; do
    idx="${entry%%:*}"
    rest="${entry#*:}"
    dir="${rest%%:*}"
    camid="${rest#*:}"

    pipeline_name="intersection-cam${idx}${pipeline_suffix}"
    payload=$(cat <<EOF
{
  "destination": {
    "frame": {
      "type": "rtsp",
      "path": "${camid}"
    }
  },
  "parameters": {
    "ntp_config": {
      "ntpServer": "ntpserv"
    },
    "camera_config": {
      "cameraid": "${camid}",
      "metadatagenpolicy": "detectionPolicy"
    }
  }
}
EOF
)
    response=$(curl -k -s "https://$DLSPS_NODE_IP/api/pipelines/user_defined_pipelines/${pipeline_name}" \
      -X POST -H "Content-Type: application/json" -d "$payload")
    if [ $? -ne 0 ]; then
      echo -e "\nError: curl -k command failed. Check the deployment status."
      return 1
    fi
    sleep 2
  done

  running=false
  while [ "$running" != true ]; do
    status=$(curl -k -s --location -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" | grep state | awk '{ print $2 }' | tr -d \")
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

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

forcedCPU=false
forcedGPU=false
forcedNPU=false
forcedIGPUCPU=false
forcedIGPUNPUCPU=false

for arg in "$@"; do
  if [ "$arg" == "cpu" ]; then
      forcedCPU=true
      forcedGPU=false
      forcedNPU=false
      forcedIGPUCPU=false
      forcedIGPUNPUCPU=false
  elif [ "$arg" == "gpu" ]; then
      forcedCPU=false
      forcedGPU=true
      forcedNPU=false
      forcedIGPUCPU=false
      forcedIGPUNPUCPU=false
  elif [ "$arg" == "npu" ]; then
      forcedCPU=false
      forcedGPU=false
      forcedNPU=true
      forcedIGPUCPU=false
      forcedIGPUNPUCPU=false
  elif [ "$arg" == "igpu_cpu" ]; then
      forcedCPU=false
      forcedGPU=false
      forcedNPU=false
      forcedIGPUCPU=true
      forcedIGPUNPUCPU=false
  elif [ "$arg" == "igpu_npu_cpu" ]; then
      forcedCPU=false
      forcedGPU=false
      forcedNPU=false
      forcedIGPUCPU=false
      forcedIGPUNPUCPU=true
  else
      echo "Unknown argument '$arg', defaulting to CPU"
      forcedCPU=true
      forcedGPU=false
      forcedNPU=false
      forcedIGPUCPU=false
      forcedIGPUNPUCPU=false
  fi
done

# Default to CPU when no argument is given
if [ $# -eq 0 ]; then
  echo "No device selected, defaulting to CPU"
  forcedCPU=true
fi

detect_sku

stop_all_pipelines
if [ $? -ne 0 ]; then
  exit 1
fi

# ---------------------------------------------------------------------------
# Launch the appropriate pipeline set
# ---------------------------------------------------------------------------
if $forcedGPU; then
  if ls /dev/dri/renderD* 1>/dev/null 2>&1; then
    echo -e "\n>>>>>GPU device selected."
    run_sample "-gpu"
    if [ $? -ne 0 ]; then exit 1; fi
  else
    echo -e "\n>>>>>No GPU device found. Please check your GPU driver installation or use CPU."
    exit 0
  fi
elif $forcedNPU; then
  if ls /dev/accel/accel* 1>/dev/null 2>&1; then
    echo -e "\n>>>>>NPU device selected."
    run_sample "-npu"
    if [ $? -ne 0 ]; then exit 1; fi
  else
    echo -e "\n>>>>>No NPU device found. Please check your NPU driver installation or use CPU."
    exit 0
  fi
elif $forcedIGPUCPU; then
  if ls /dev/dri/renderD* 1>/dev/null 2>&1; then
    echo -e "\n>>>>>iGPU+CPU mode selected (iGPU hardware decode, CPU inference)."
    run_sample "-igpu_cpu"
    if [ $? -ne 0 ]; then exit 1; fi
  else
    echo -e "\n>>>>>No GPU device found. Please check your GPU driver installation or use CPU."
    exit 0
  fi
elif $forcedIGPUNPUCPU; then
  if ls /dev/dri/renderD* 1>/dev/null 2>&1; then
    if ls /dev/accel/accel* 1>/dev/null 2>&1; then
      echo -e "\n>>>>>iGPU+NPU+CPU mode selected (iGPU hardware decode, NPU inference)."
      run_sample "-npu"
      if [ $? -ne 0 ]; then exit 1; fi
    else
      echo -e "\n>>>>>No NPU device found. Please check your NPU driver installation or use igpu_cpu mode."
      exit 0
    fi
  else
    echo -e "\n>>>>>No GPU device found. Please check your GPU driver installation or use CPU."
    exit 0
  fi
elif $forcedCPU; then
  echo -e "\n>>>>>CPU device selected."
  run_sample ""
  if [ $? -ne 0 ]; then exit 1; fi
fi

echo -e "\n>>>>>Results are visualized via the SceneScape UI and Grafana at 'https://localhost/grafana'"
echo -e "\n>>>>>Pipelines status can be checked with 'curl -k --location -X GET https://localhost/api/pipelines/status' or using script 'sample_status.sh'.\n"
