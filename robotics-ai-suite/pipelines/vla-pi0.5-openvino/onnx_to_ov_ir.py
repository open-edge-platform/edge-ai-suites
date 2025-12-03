# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import openvino as ov

# 1. Load and convert the ONNX file to an OpenVINO Model object
ov_model = ov.convert_model("pi05_onnx/pi05.onnx")

# 2. Save the OpenVINO Model object to the Intermediate Representation (IR) format
output_dir = "pi05_lerobot_ov_ir_FP32"

ov.save_model(ov_model, 
              output_model=f"{output_dir}/model.xml", 
              compress_to_fp16=False) 

print(f"Conversion complete. IR files saved to: {output_dir}/model.xml and {output_dir}/model.bin")
