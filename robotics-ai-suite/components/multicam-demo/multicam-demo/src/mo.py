#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import torch

# PyTorch 2.6+ changed torch.load default to weights_only=True, which blocks
# loading ultralytics checkpoints that contain custom classes. Override it here
# since we trust local model files.
_torch_load_orig = torch.load
def _torch_load_unsafe(*args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _torch_load_orig(*args, **kwargs)
torch.load = _torch_load_unsafe

from ultralytics import YOLO

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--model', default=None, help='model path')
	parser.add_argument('--data_type', default='FP32')

	args = parser.parse_args()

	half=True if args.data_type=="FP16" else False

	model = YOLO(args.model)
	model.export(format="openvino", dynamic=True, half=half, opset=18)


