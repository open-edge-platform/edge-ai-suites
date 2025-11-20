#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import torch
from ultralytics import YOLO

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--model', default=None, help='model path')
	parser.add_argument('--data_type', default='FP32')

	args = parser.parse_args()

	half=True if args.data_type=="FP16" else False

	model = YOLO(args.model)
	model.export(format="openvino", dynamic=True, half=half)


