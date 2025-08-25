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

import os, sys, argparse
import cv2
import numpy as np
import json
import imutils
from yolov8_model  import YoloV8Model
import pyrealsense2_ai_demo
from pyrealsense2_ai_demo import InferenceManager

MAX_APP = 4

adapters = dict (
	yolov8 = YoloV8Model
)

def run(config_file):

	config = json.load(open(config_file))

	apps = []
	for app in  config:
		adapter = adapters[app["adapter"]]
		model = adapter(app["model"], app["device"], app["name"])
		apps.append(InferenceManager(model, app["source"], config[0]["data_type"]))
		if len(apps) > MAX_APP:
			break;

	for app in apps:
		app.start()
	
	vis =  np.zeros((720, 1280, 3), dtype = np.uint8)
	height,width = vis.shape[:2]
	margin = 5
	cv2.namedWindow("demo", cv2.WND_PROP_FULLSCREEN)
	cv2.setWindowProperty("demo", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
	fullScreen = None
	num_frames = 0;
	while True:
		images = []
		for app in apps:
			img = app.get(1)
			if img is not None:
				images.append(img)

		if len(images) != len(apps):
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

	for app in apps:
		app.stop()
		
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--config', default='./config.js', help='confile file')
	
	args = parser.parse_args()
		
	run(args.config)

	
