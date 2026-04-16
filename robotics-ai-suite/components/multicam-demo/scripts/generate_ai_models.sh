#!/bin/bash
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# Generating Yolov8 models
echo "------------------------------------------------------------------------"
echo "Generating Yolov8 models."
echo "------------------------------------------------------------------------"

yolov8_models=("yolov8n" "yolov8s" "yolov8m" "yolov8n-seg" "yolov8s-seg" "yolov8m-seg")
datatype="FP16"
ros_version=""
release=$(lsb_release -cs)

case ${release} in
  "jammy")
    ros_version="humble"
    ;;
  "noble")
    ros_version="jazzy"
    ;;
  "*")
    ros_version="jazzy"
    ;;
esac


mkdir -p ./models/yolov8/"$datatype"
cd ./models/yolov8/ || exit
i=1
status=0
for i in "${yolov8_models[@]}"; do
  python3 /opt/ros/"$ros_version"/share/pyrealsense2-ai-demo/src/mo.py --model="$i".pt --data_type="$datatype"
  if [[ $? -ne 0 ]]
  then
    status=1
    break
  else
    mv "$i"_openvino_model/*.xml "$i"_openvino_model/*.bin ./"$datatype" && rm -rf "$i"_openvino_model
  fi
done

if [[ "$status" -eq 1 ]]
then
  echo "Yolov8 models generation failed."
else
  echo "Yolov8 models are successfully generated in ./models/yolov8/$datatype."
fi
cd - || exit

echo ""
echo ""
