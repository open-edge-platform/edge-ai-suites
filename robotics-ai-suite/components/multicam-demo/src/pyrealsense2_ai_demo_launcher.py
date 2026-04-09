#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os, sys, argparse
import cv2
import numpy as np
import json
import time
import imutils
from yolov8_model  import YoloV8Model
import pyrealsense2_ai_demo
from pyrealsense2_ai_demo import InferenceManager

MAX_APP = 4

adapters = dict (
	yolov8 = YoloV8Model
)

def run(config_file, no_display=False, verbose=False):

	with open(config_file) as f:
		raw = '\n'.join(line for line in f if not line.lstrip().startswith('//'))
	config = json.loads(raw)

	apps = []
	for app in  config:
		adapter = adapters[app["adapter"]]
		if verbose:
			print(f"[VERBOSE] Loading model: {app['model']} on {app['device']} for source {app['source']}")
		model = adapter(app["model"], app["device"], app["name"])
		resolution = (app.get("width", 1280), app.get("height", 720))
		if verbose:
			print(f"[VERBOSE] Opening camera: {app['source']} at {resolution}")
		apps.append(InferenceManager(model, app["source"], app["data_type"], camera_resolution=resolution))
		if len(apps) >= MAX_APP:
			break;

	if verbose:
		print(f"[VERBOSE] Starting {len(apps)} inference thread(s)...")
	for app in apps:
		app.start()

	if verbose:
		print("[VERBOSE] All threads started. Entering main loop. Press Ctrl+C to stop.")

	vis =  np.zeros((720, 1280, 3), dtype = np.uint8)
	height,width = vis.shape[:2]
	margin = 5
	if not no_display:
		cv2.namedWindow("demo", cv2.WND_PROP_FULLSCREEN)
		cv2.setWindowProperty("demo", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
	fullScreen = None
	num_frames = 0
	last_verbose_time = time.time()
	try:
		while True:
			images = []
			for app in apps:
				img = app.get(1)
				if img is not None:
					images.append(img)

			if verbose and (time.time() - last_verbose_time) >= 2.0:
				last_verbose_time = time.time()
				for idx, app in enumerate(apps):
					img = app.get()
					shape = img.shape if img is not None else None
					fps = app.fps() if app.start_time is not None else 0
					print(f"[VERBOSE] cam[{idx}] source={app.input}  frames={app.frames_number}  fps={fps:.1f}  last_shape={shape}")

			if len(images) != len(apps):
				continue

			if no_display:
				num_frames += 1
				if verbose and num_frames % 30 == 0:
					print(f"[VERBOSE] {num_frames} composite frames rendered (no-display mode)")
				continue

			if len(images) == 1:
				vis = images[0]
			else:
				sh,sw = int(height/2),int(width/2)
				for i in range(len(images)):
					app_image = imutils.resize(images[i], height=sh-margin)
					h,w = app_image.shape[:2]
					xoff = int(i%2)*sw + int((sw-w)/2) + int(i%2)*margin
					yoff = int(i/2)*sh + int(i/2)*margin
					vis[yoff:yoff+h, xoff:xoff+w] = app_image

			cv2.imshow("demo", vis)
			key = cv2.waitKey(1)

			if key in {ord('q'), ord('Q'), 27}:
				break

			if key == ord('f'):
				cv2.setWindowProperty("demo", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN if not fullScreen else cv2.WINDOW_NORMAL)
				fullScreen = not fullScreen

			num_frames += 1
			if fullScreen is None and num_frames > 3:
				cv2.setWindowProperty("demo", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
				fullScreen = False
	except KeyboardInterrupt:
		print("\n[INFO] Interrupted by user.")

	for app in apps:
		app.stop()

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--config', default='./config.js', help='config file')
	parser.add_argument('--no-display', action='store_true', help='skip cv2 window rendering')
	parser.add_argument('--verbose', action='store_true', help='print per-camera stats every 2 seconds')

	args = parser.parse_args()

	run(args.config, no_display=args.no_display, verbose=args.verbose)


