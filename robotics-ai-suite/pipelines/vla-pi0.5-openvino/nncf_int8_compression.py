# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import openvino.runtime as ov
from nncf import compress_weights
from nncf import CompressWeightsMode

# --- Configuration ---
# 1. Define the paths to your model files
model_xml_path = "pi05_lerobot_ov_ir_FP32/model.xml"

# 2. Define the output paths for the compressed model
output_xml_path = "pi05_lerobot_ov_ir_INT8/model.xml"

# 3. Choose your compression mode
compression_mode = CompressWeightsMode.INT8_ASYM 

# --- Compression Steps ---

# 1. Initialize OpenVINO Core and read the model
core = ov.Core()
print(f"Loading uncompressed model from: {model_xml_path}")
uncompressed_model = core.read_model(model=model_xml_path)

# 2. Apply Weight Compression using NNCF
print(f"Applying NNCF Weight Compression to {compression_mode.name}...")
compressed_model = compress_weights(
    model=uncompressed_model, 
    mode=compression_mode
)

# 3. Save the compressed OpenVINO IR model
print(f"Saving compressed model to: {output_xml_path}")
ov.save_model(
    model=compressed_model, 
    output_model=output_xml_path
)

print("Compression complete! The model size has been reduced.")
