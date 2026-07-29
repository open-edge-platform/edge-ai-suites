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

def run(config_file, no_display=False, verbose=False, duration=None):
	"""Run demo. Returns exit code (0=ok, 2=setup failure, 3=zero-frame failure)."""

	if duration is not None and duration > 0:
		no_display = True

	try:
		with open(config_file) as f:
			raw = '\n'.join(line for line in f if not line.lstrip().startswith('//'))
		config = json.loads(raw)
	except (OSError, json.JSONDecodeError) as exc:
		print(f"[ERROR] Failed to load config '{config_file}': {exc}", file=sys.stderr)
		return 2

	apps = []
	try:
		for app in config:
			adapter = adapters[app["adapter"]]
			if verbose:
				print(f"[VERBOSE] Loading model: {app['model']} on {app['device']} for source {app['source']}")
			model = adapter(app["model"], app["device"], app["name"])
			resolution = (app.get("width", 1280), app.get("height", 720))
			fourcc = app.get("format")
			if verbose:
				print(f"[VERBOSE] Opening camera: {app['source']} at {resolution} fourcc={fourcc}")
			apps.append(InferenceManager(model, app["source"], app["data_type"], camera_resolution=resolution, fourcc=fourcc, no_draw=no_display))
			if len(apps) >= MAX_APP:
				break
	except Exception as exc:
		print(f"[ERROR] Failed to construct app pipeline: {exc}", file=sys.stderr)
		return 2

	if not apps:
		print("[ERROR] No apps configured", file=sys.stderr)
		return 2

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
	start_time = time.time()
	deadline = (start_time + duration) if duration else None
	try:
		while True:
			if deadline is not None and time.time() >= deadline:
				break
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
					a = app.adapter
					pre_ms = getattr(a, '_pre_ms', 0.0)
					sub_ms = getattr(a, '_submit_ms', 0.0)
					times = getattr(a, 'infer_times', None)
					gpu_ms = (sum(times) / len(times) * 1000.0) if times else 0.0
					print(f"[VERBOSE] cam[{idx}] source={app.input}  frames={app.frames_number}  fps={fps:.1f}  "
						  f"pre={pre_ms:.1f}ms submit={sub_ms:.1f}ms gpu={gpu_ms:.1f}ms  last_shape={shape}")

			if len(images) != len(apps):
				continue

			if no_display:
				num_frames += 1
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

	elapsed = time.time() - start_time

	for app in apps:
		app.stop()

	print(f"\n=== Run summary (elapsed {elapsed:.2f}s) ===")
	rc = 0
	for idx, app in enumerate(apps):
		infer_frames = getattr(app, 'frames_number', 0) or 0
		try:
			infer_fps = app.fps() if app.start_time is not None else 0.0
		except Exception:
			infer_fps = 0.0
		cam_fps = getattr(app, '_cam_fps', 0.0) or 0.0
		cam_frames = getattr(app, '_cam_frames_total', 0) or 0
		source = getattr(app, 'input', '?')
		print(f"cam[{idx}] source={source}  cam_fps={cam_fps:.2f} ({cam_frames} frames)  "
			  f"infer_fps={infer_fps:.2f} ({infer_frames} frames)")
		if infer_frames == 0:
			print(f"cam[{idx}] FAILED: no inference frames produced", file=sys.stderr)
			rc = 3
	return rc

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--config', default='./config.js', help='config file')
	parser.add_argument('--no-display', action='store_true', help='skip cv2 window rendering')
	parser.add_argument('--verbose', action='store_true', help='print per-camera stats every 2 seconds')
	parser.add_argument('--duration', type=float, default=None,
						help='run headless for this many seconds, then exit with FPS summary')

	args = parser.parse_args()

	sys.exit(run(args.config, no_display=args.no_display, verbose=args.verbose, duration=args.duration))


