# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import openvino.runtime as ov
import numpy as np
import torch

# NOTE: Replace this path with the actual path to your model's XML file.
model_xml_file = "../pi05_lerobot_ov_ir_INT8/model.xml"


file_path = 'lerobot_pi05_input_tensor.pt'
checkpoint = torch.load(file_path, map_location='cpu')

# Access individual components
images = checkpoint['images']
img_masks = checkpoint['img_masks']
lang_tokens = checkpoint['lang_tokens']
lang_masks = checkpoint['lang_masks']
state = checkpoint['state']
actions = checkpoint['actions']

core = ov.Core()

model = core.read_model(model=model_xml_file)
compiled_model = core.compile_model(model, "CPU")

inputs_dict = {
    "images":images,    
    "img_masks":img_masks,
    "lang_tokens": lang_tokens,
    "lang_masks": lang_masks,
    "state": state,
    "actions": actions 
}

results = compiled_model(inputs_dict)

for output_node in compiled_model.outputs:
    output = results[output_node]
    print(f"Output '{output_node.any_name}' shape: {output.shape}")
    print("Output type", type(output))
    torch.save(torch.from_numpy(output), "openvino_pi05_INT8_output.pt")
