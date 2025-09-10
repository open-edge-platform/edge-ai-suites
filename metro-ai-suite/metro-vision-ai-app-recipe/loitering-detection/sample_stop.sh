#!/bin/bash

DLSPS_NODE_IP="localhost"
DLSPS_PORT=8080

function stop_all_pipelines() {
  echo
  echo -n ">>>>>Stopping all running pipelines."
  pipelines=$(curl -k -s -X GET "https://$DLSPS_NODE_IP/api/pipelines/status" -H "accept: application/json" | grep id | awk ' { print $2 } ' | tr -d \"  | tr -d '\n')
  if [ $? -ne 0 ]; then
    echo -e "\nError: curl -k command failed."
    return 1
  fi
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



stop_all_pipelines

if [ $? -ne 0 ]; then
  exit 1
  echo "Error: Check pipelines manually"
else
  echo ">>>>>All running pipelines stopped."
fi



