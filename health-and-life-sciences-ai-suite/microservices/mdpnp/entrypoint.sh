#!/bin/bash
set -e

DOMAIN=${DOMAIN:-10}
DEVICES=${DEVICES:-"ECG_Simulator,CO2_Simulator"}

echo "Starting devices: $DEVICES"

for DEVICE in $(echo $DEVICES | tr "," " "); do
  echo "Launching device: $DEVICE"
  java -jar demo-apps-1.5.0-SNAPSHOT.jar \
    -app ICE_Device_Interface \
    -domain $DOMAIN \
    -device $DEVICE &
done

wait
