#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os, argparse
import time
from pathlib import Path
import cv2
import numpy as np
from threading import Thread, Condition, Event
from queue import Queue, Empty
from time import perf_counter
from collections import deque
import psutil
import pathlib
from .images_capture import VideoCapture
from . import perf_visualizer as pv

class InferenceManager(Thread):
	def __init__(self, model_adapter, input, data_type, async_mode=False, camera_resolution=(1280, 720), fourcc=None, no_draw=False):
		super().__init__()
		self.adapter = model_adapter
		self.input = input
		self.data_type = data_type
		self.no_draw = no_draw
		self.cap = VideoCapture(input, True, camera_resolution, fourcc=fourcc) if input is not None else None
		self.async_mode = async_mode
		self.frames_number = 0
		self.frames_missed = 0
		self.start_time = None
		self.cv = Condition()
		self.running = False
		self.image = None
		self.cpu_loads = deque(maxlen=120)
		self.cpu_loads.append(psutil.cpu_percent(0.1))
		self.adapter.cap = self.cap
		# Single-slot camera buffer: camera reader thread always overwrites with
		# the latest frame so the inference loop never blocks on cap.read().
		self._cam_buf = deque(maxlen=1)
		self._cam_frames_total = 0  # total frames produced by camera
		self._frame_ready = Event()  # set by camera reader, cleared by inference loop
		self._cam_fps = 0.0         # camera capture fps, updated by camera reader

	def _camera_reader(self):
		"""Dedicated thread: reads camera as fast as possible into _cam_buf."""
		cam_start = perf_counter()
		while self.running:
			frame = self.cap.read()
			if frame is None:
				break
			self._cam_buf.append(frame)
			self._cam_frames_total += 1
			elapsed = perf_counter() - cam_start
			if elapsed > 0:
				self._cam_fps = self._cam_frames_total / elapsed
			self._frame_ready.set()  # wake the inference thread

	def start(self, block=False):

		if block is False:
			self.cv.acquire()
			if self.running == False:
				self.running = True;
				self._cam_reader_thread = Thread(target=self._camera_reader, daemon=True)
				self._cam_reader_thread.start()
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
			self._cam_reader_thread.join(timeout=2)
			self.proc.join()
			Thread.join(self)
			# Drain any in-flight async inferences before tearing down so the
			# OV runtime doesn't fire callbacks during interpreter shutdown.
			q = getattr(self.adapter, 'infer_queue', None)
			if q is not None:
				try:
					q.wait_all()
				except Exception:
					pass
			self.cv.acquire()

		self.cv.release()

	def infer(self, image):
		if self.start_time is None:
			self.start_time = perf_counter()

		return self.adapter.infer(image)

	def result(self, withPerf=True):
		image = self.adapter.result()
		if withPerf:
			if self.start_time is None:
				self.start_time = perf_counter()
			self.frames_number += 1

			pv.draw_perf(image, self.adapter.name, self.adapter.device,
							self.fps(), self.adapter.fps(), self.cpu_load(), self.data_type, self.async_mode, self.frames_number,
							stream_label=self.input)
			return image

	def fps(self):
		if self.start_time is None or self.frames_number == 0:
			return 0.0
		return self.frames_number / (perf_counter() - self.start_time)

	def cpu_load(self):
		return np.average(self.cpu_loads)

	def get(self, to=None):
		return self.image

	def run(self):
		if self.cap is None:
			print("No input provided")
			return False

		self.cv.acquire()

		self.frames_number = 0
		self.frames_missed = 0
		self._cam_frames_total = 0
		self.start_time = None

		# Wait for the camera reader to produce the first frame before starting
		self._frame_ready.wait(timeout=5.0)
		self._frame_ready.clear()

		while self.running:

			self.cv.release()

			# Block until camera reader signals a new frame (no busy-poll)
			self._frame_ready.wait(timeout=0.1)
			self._frame_ready.clear()

			try:
				image = self._cam_buf.pop()
			except IndexError:
				self.cv.acquire()
				continue

			self.adapter.infer(image)

			self.cv.acquire()

			if self.no_draw:
				# Headless: skip postprocess+draw entirely; throughput comes from
				# the adapter's async callback (_infer_count). This avoids serializing
				# the loop on CPU NMS/mask-resize/cv2 draws.
				if self.start_time is None:
					self.start_time = perf_counter()
				self.frames_number = getattr(self.adapter, '_infer_count', 0)
				self.frames_missed = max(0, self._cam_frames_total - self.frames_number)
				continue

			image = self.adapter.result()
			if image is not None:
				if self.start_time is None:
					self.start_time = perf_counter()
				self.frames_number += 1
				# frames_missed = camera frames produced but not yet consumed
				self.frames_missed = max(0, self._cam_frames_total - self.frames_number)

				pv.draw_perf(image, self.adapter.name, self.adapter.device,
							self.fps(), self.adapter.fps(), self.cpu_load(), self.data_type, self.async_mode, self.frames_number, self.frames_missed,
							stream_label=self.input, cam_fps=self._cam_fps)

				self.image = image

		self.cv.release()

	def cpu_load_handler(self):

		self.cpu_loads.append(psutil.cpu_percent(0.1))

		while self.running:
			self.cv.acquire()
			self.cpu_loads.append(psutil.cpu_percent(0))
			self.cv.release()
			time.sleep(0.5)

