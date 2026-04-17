#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os
import cv2
import numpy as np


def draw_perf(image:np.ndarray, model_name, device, fps, infer_fps, cpu_load, data_type, async_mode, frames=None, frames_missed=None, stream_label=None, cam_fps=None):
	frame_size = image.shape[:-1]
	fontFace = cv2.FONT_HERSHEY_SIMPLEX

	# Scale text proportionally to frame height so it stays readable after
	# imutils.resize() scales each tile down in multi-camera layouts.
	# Reference: 360px = half of 720p (typical 4-cam tile height).
	s = max(frame_size[0] / 360.0, 1.0)
	fs_large  = round(0.8 * s, 2)   # FPS / device headline
	fs_medium = round(0.65 * s, 2)  # secondary stats
	fs_model  = round(0.6 * s, 2)   # model name bar
	thick = max(1, int(round(2 * s)))
	pad = max(4, int(round(6 * s)))

	def put_label(lines, x, y):
		sizes = []
		for text, scale, _ in lines:
			(tw, th), bl = cv2.getTextSize(text, fontFace, scale, thick)
			sizes.append((tw, th + bl))

		max_w = max(sz[0] for sz in sizes)
		total_h = sum(sz[1] + pad for sz in sizes)
		cv2.rectangle(image, (x - pad, y - pad),
		              (x + max_w + pad, y + total_h + pad),
		              (0, 0, 0), cv2.FILLED)
		cv2.rectangle(image, (x - pad, y - pad),
		              (x + max_w + pad, y + total_h + pad),
		              (0, 200, 0), 1, cv2.LINE_AA)

		cy = y
		for (text, scale, color), (tw, th) in zip(lines, sizes):
			cy += th
			cv2.putText(image, text, (x + 1, cy + 1), fontFace, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
			cv2.putText(image, text, (x, cy), fontFace, scale, color, thick, cv2.LINE_AA)
			cy += pad

	# --- top-left: cam FPS + pipeline FPS + frames + missed ---
	lines_left = []
	if cam_fps is not None:
		lines_left.append((f"Cam: {cam_fps:.1f} fps", fs_large, (0, 255, 0)))
	lines_left.append((f"Pipe: {fps:.1f} fps", fs_large if cam_fps is None else fs_medium,
	                   (0, 255, 0) if cam_fps is None else (180, 255, 180)))
	if frames is not None:
		lines_left.append((f"Frames: {frames}", fs_medium, (200, 255, 200)))
	if frames_missed is not None:
		missed_color = (0, 100, 255) if frames_missed == 0 else (0, 60, 220)
		lines_left.append((f"Missed: {frames_missed}", fs_medium, missed_color))
	put_label(lines_left, 8, 8)

	# --- top-right: device + inf latency + cpu ---
	if not async_mode and infer_fps > 0:
		inf_lat  = f"Inf: {(1000.0 / infer_fps):.1f}ms"
		inf_spd  = f"     {int(infer_fps)} fps"
	else:
		inf_lat, inf_spd = "Async", ""
	lines_right = [
		(device, fs_large, (0, 220, 255)),
		(inf_lat, fs_medium, (255, 160, 0)),
	]
	if inf_spd:
		lines_right.append((inf_spd, fs_medium, (255, 200, 100)))
	if cpu_load is not None:
		lines_right.append((f"CPU: {int(cpu_load)}%", fs_medium, (255, 100, 100)))
	max_w = max(cv2.getTextSize(t, fontFace, sc, thick)[0][0] for t, sc, _ in lines_right)
	put_label(lines_right, frame_size[1] - max_w - 8 - pad * 2, 8)

	# --- bottom-center: model name bar + stream label ---
	cam = os.path.basename(stream_label) if stream_label else ""
	info = f"{model_name}  {data_type}{' Async' if async_mode else ''}{'  |  ' + cam if cam else ''}"
	(tw, th), bl = cv2.getTextSize(info, fontFace, fs_model, thick)
	bx = (frame_size[1] - tw) // 2
	by = frame_size[0] - th - bl - pad * 2
	cv2.rectangle(image, (bx - pad, by - pad),
	              (bx + tw + pad, by + th + bl + pad),
	              (0, 0, 0), cv2.FILLED)
	cv2.rectangle(image, (bx - pad, by - pad),
	              (bx + tw + pad, by + th + bl + pad),
	              (0, 200, 0), 1, cv2.LINE_AA)
	cv2.putText(image, info, (bx + 1, by + th + 1), fontFace, fs_model, (0, 0, 0), thick + 1, cv2.LINE_AA)
	cv2.putText(image, info, (bx, by + th), fontFace, fs_model, (0, 255, 0), thick, cv2.LINE_AA)


