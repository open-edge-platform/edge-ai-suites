#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import os, argparse
from pathlib import Path
from typing import Tuple, Dict
import random
from collections import deque
import cv2
import numpy as np
from time import perf_counter
import pathlib
import openvino.runtime as ov
from openvino.runtime import Core, Model, AsyncInferQueue


class Model():
	def __init__(self, model_path, device, image_size=640):
		
		self.device = device

		self.core = Core()
		self.ov_model = self.core.read_model(model_path)
		#if device != "CPU":
		#	self.ov_model.reshape({0: [1, 3, image_size, image_size]})

		self.compiled_model = self.core.compile_model(self.ov_model, device)

		self.input_layer_ir = self.ov_model.input(0)

		self.infer_queue = AsyncInferQueue(self.compiled_model,2)
		self.infer_queue.set_callback(self.callback)

		self.infer_request = self.compiled_model.create_infer_request()

		self.infer_times = []
		self.outputs = deque()

		self.async_mod = False


	def infer(self, image:np.ndarray):

		_,_,h,w = self.input_layer_ir.shape
		resized_image = self.preprocess(image, w, h)

		start_time = perf_counter()
		if self.async_mod:
			self.infer_queue.start_async({self.input_layer_ir.any_name:  resized_image}, (image, resized_image, start_time))
		else:
			self.infer_request.set_tensor(self.input_layer_ir, ov.Tensor(resized_image))
			self.infer_request.infer()
			self.callback(self.infer_request, (image, resized_image, start_time))

	def async_mode(self,flag):
		self.async_mod = flag
		self.infer_times = []

	def result(self):
		image = None
		try:
			outputs = self.outputs.pop()
			image = self.postprocess(outputs)
		except IndexError:
			pass

		return image

	def fps(self):
		if len(self.infer_times) > 0:
			return 1/np.average(self.infer_times);
		else:
			return 0

	def callback(self, infer_request, info) -> None:

		outputs = infer_request.results
		image, resized_image, start_time = info

		infer_time = (perf_counter() - start_time)	
		self.infer_times.append(infer_time)

		self.put(infer_request, image, resized_image)
		

	def put(self, infer_request, image, resized_image):
		return False

	def preprocess(self, image, width, height):
	
		return None


	def postprocess(self, outputs, threshold=0.5):

		return NOne


	
