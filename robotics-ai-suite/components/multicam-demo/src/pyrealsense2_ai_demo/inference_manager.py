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
import time
from pathlib import Path
import cv2
import numpy as np
from threading import Thread, Condition
from queue import Queue, Empty
from time import perf_counter
from collections import deque
import psutil
import pathlib
from .images_capture import VideoCapture
from . import perf_visualizer as pv

class InferenceManager(Thread):
	def __init__(self, model_adapter, input, data_type, async_mode=False):
		super().__init__()
		self.adapter = model_adapter
		self.input = input
		self.data_type = data_type
		self.cap = VideoCapture(input, True) if input is not None else None
		self.async_mode = async_mode
		self.frames_number = 0
		self.start_time = None
		self.cv = Condition()
		self.queue = Queue(maxsize=10)
		self.running = False
		self.image = None
		self.cpu_loads = deque(maxlen=120)
		self.cpu_loads.append(psutil.cpu_percent(0.1))
		self.adapter.cap = self.cap

	def start(self, block=False):

		if block is False:
			self.cv.acquire()
			if self.running == False:
				self.running = True;
				Thread.start(self)
				self.proc = Thread(target=self.cpu_load_handler)
				self.proc.daemon = True
				self.proc.start()
			self.cv.release()

		else:
			self.handler()

	def stop(self):
		self.cv.acquire()

		if self.running:

			self.running = False;
			self.cv.notify()
			self.cv.release()
			self.proc.join()
			Thread.join(self)
			self.cv.acquire()
			
		self.cv.release()

	def infer(self, image):
		if self.start_time is None:
			self.start_time = perf_counter()

		return self.adapter.infer(image)

	def result(self, withPerf=True):
		image = self.adapter.result()
		if withPerf:
			self.frames_number += 1

			pv.draw_perf(image, self.adapter.name, self.adapter.device, 
								self.fps(), self.adapter.fps(), self.cpu_load(), self.data_type, self.async_mode)
			return image

	def fps(self):
		return self.frames_number/(perf_counter() - self.start_time)

	def cpu_load(self):
		return np.average(self.cpu_loads);

	def get(self, to=None):
		return self.image

	def run(self):
		if self.cap is None:
			print("No input provided")
			return False

		self.cv.acquire()

		self.frames_number = 0
		self.start_time = perf_counter()

		while self.running:

			self.cv.release()

			image = self.cap.read()
			if image is None:
				self.cv.acquire()
				break
			
			self.adapter.infer(image)
			
			self.cv.acquire()

			image = self.adapter.result()
			if image is not None:
				self.frames_number += 1
				
				pv.draw_perf(image, self.adapter.name, self.adapter.device, 
							self.fps(), self.adapter.fps(), self.cpu_load(), self.data_type, self.async_mode)

				self.image = image

		self.cv.release()
		
	def cpu_load_handler(self):

		self.cpu_loads.append(psutil.cpu_percent(0.1))
		
		while self.running:
			self.cv.acquire()
			self.cpu_loads.append(psutil.cpu_percent(0))
			self.cv.release()
			time.sleep(0.5)

