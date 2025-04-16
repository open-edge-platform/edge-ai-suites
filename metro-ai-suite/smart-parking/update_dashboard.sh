#!/bin/bash

# Load environment variables
if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found!"
  exit 1
fi

# Check for required variables
if [ -z "$HOST_IP" ]; then
  echo "Error: HOST_IP environment variable is not set."
  exit 1
fi

#############################################
# Update dashboard JSON files IP address  #
#############################################

# Prefer the new folder, then legacy grafana folder
if [ -d "./grafana/dashboards" ]; then
  DASH_DIR="./grafana/dashboards"
  echo "Found dashboards folder: $DASH_DIR"
elif [ -d "./grafana/dashboards" ]; then
  DASH_DIR="./grafana/dashboards"
  echo "Using legacy grafana dashboards folder: $DASH_DIR"
else
  echo "Warning: No dashboards folder found."
  DASH_DIR=""
fi

if [ -n "$DASH_DIR" ]; then
  for file in "$DASH_DIR"/*.json; do
    [ -f "$file" ] && sed -i "s|\"url\": *\"http://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}:|\"url\": \"http://$HOST_IP:|g" "$file" 
    sed -i "s|\"mqttLink\": *\"ws://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}:|\"mqttLink\": \"ws://$HOST_IP:|g" "$file" 
  sed -i "s|\"webrtcUrl\": *\"http://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}:|\"webrtcUrl\": \"http://$HOST_IP:|g" "$file"
  done
fi

#############################################
# Update datasources.yml file IP address  #
#############################################

# Check for the new location first, then legacy location
if [ -f "./grafana/datasources.yml" ]; then
  DS_FILE="./grafana/datasources.yml"
  echo "Found datasources file: $DS_FILE"
elif [ -f "./grafana/datasources.yml" ]; then
  DS_FILE="./grafana/datasources.yml"
  echo "Using legacy grafana datasources file: $DS_FILE"
else
  DS_FILE=""
  echo "Warning: No datasources.yml file found."
fi

if [ -n "$DS_FILE" ]; then
  sed -i "s|tcp://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}:1883|tcp://$HOST_IP:1883|g" "$DS_FILE"
fi

#############################################
# Update Node-RED flows IP address          #
#############################################

# Check for the new location first, then legacy location
if [ -f "./node-red/flows.json" ]; then
  NR_FILE="./node-red/flows.json"
  echo "Found node-red flows file: $NR_FILE"
elif [ -f "./node-red/flows.json" ]; then
  NR_FILE="./node-red/flows.json"
  echo "Using legacy node-red flows file: $NR_FILE"
else
  NR_FILE=""
  echo "Warning: No node-red flows file found."
fi

if [ -n "$NR_FILE" ]; then
  sed -i "s|http://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}|http://$HOST_IP|g" "$NR_FILE"
  sed -i "s|\"broker\": *\"[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}\",|\"broker\": \"$HOST_IP\",|" "$NR_FILE"
fi

#############################################
# Update sample_start.sh for video paths and  #
# MQTT host IP                              #
#############################################

# Check if the run_sample.sh exists in the folder for the current case
if [ -f "./sample_start.sh" ]; then
  echo "Found sample start file: ./sample_start.sh"
  # Update the video source path to point to the folder
  sed -i "s|file:///home/pipeline-server/videos/|file:///home/pipeline-server/videos/|g" ./sample_start.sh
  
  # Update the MQTT host IP in the file
  sed -i "s|\"host\": *\"[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}:|\"host\": \"$HOST_IP:|g" ./sample_start.sh
  
else
  echo "Warning: sample_start.sh not found in folder"
fi
