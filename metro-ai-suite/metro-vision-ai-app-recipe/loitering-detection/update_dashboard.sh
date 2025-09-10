#!/bin/bash

# Get HOST_IP from command line argument or .env file
if [ $# -ge 1 ]; then
  HOST_IP="$1"
  echo "Using HOST_IP from command line: $HOST_IP"
else
  echo "Error: No command line argument provided!"
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
if [ -d "./src/grafana/dashboards" ]; then
  DASH_DIR="./src/grafana/dashboards"
  echo "Found dashboards folder: $DASH_DIR"
elif [ -d "./src/grafana/dashboards" ]; then
  DASH_DIR="./src/grafana/dashboards"
  echo "Using legacy grafana dashboards folder: $DASH_DIR"
else
  echo "Warning: No dashboards folder found."
  DASH_DIR=""
fi

if [ -n "$DASH_DIR" ]; then
  for file in "$DASH_DIR"/*.json; do
    [ -f "$file" ] && sed -i "s|\"text\": *\"https://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}/|\"text\": \"https://$HOST_IP/|g" "$file" 
  sed -i "s|\"value\": *\"https://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}/|\"value\": \"https://$HOST_IP/|g" "$file"
  sed -i "s|\"query\": *\"https://[0-9]\{1,3\}\(\.[0-9]\{1,3\}\)\{3\}/|\"query\": \"https://$HOST_IP/|g" "$file"
  done
fi