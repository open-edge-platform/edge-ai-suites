// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

[
	{
		"name": 	"yolov8n-seg",
		"model": 	"models/yolov8/FP16/yolov8n-seg.xml",
		"device": 	"GPU",
		"data_type": "FP16",
		"source": 	"/dev/video-rs-color-0",
		"adapter":  "yolov8",
		"width":	640,
		"height":   480,
        "format":   "YUYV"
	}
]
