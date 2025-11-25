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

mkdir -p ./models/yolov8/"$datatype"
cd ./models/yolov8/ || exit
i=1
status=0
for i in "${yolov8_models[@]}"; do
  gen_yolov8_model_cmd=$(python3 ../../src/mo.py --model="$i".pt --data_type="$datatype")
  if [[ "$gen_yolov8_model_cmd" -ne 0 ]]
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
