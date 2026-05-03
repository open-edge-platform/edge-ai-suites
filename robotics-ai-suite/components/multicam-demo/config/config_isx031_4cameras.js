// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

[
        {
                "name":         "yolov8n-seg",
                "model":        "./models/yolov8/FP16/yolov8n-seg.xml",
                "device":       "GPU",
                "data_type":    "FP16",
                "source":       "/dev/video-isx031-a-0",
                "adapter":      "yolov8",
                "width":        1920,
                "height":       1536,
                "format":   "UYUV"
        },
        {
                "name":         "yolov8n-seg",
                "model":        "./models/yolov8/FP16/yolov8n-seg.xml",
                "device":       "CPU",
                "data_type":    "FP16",
                "source":       "/dev/video-isx031-b-0",
                "adapter":      "yolov8",
                "width":        1920,
                "height":       1536,
                "format":   "UYUV"

        },
        {
                "name":         "yolov8n",
                "model":        "./models/yolov8/FP16/yolov8n.xml",
                "device":       "GPU",
                "data_type":    "FP16",
                "source":       "/dev/video-isx031-c-0",
                "adapter":      "yolov8",
                "width":        1920,
                "height":       1536,
                "format":   "UYUV"
        },
        {
                "name":         "yolov8n",
                "model":        "./models/yolov8/FP16/yolov8n.xml",
                "device":       "GPU",
                "data_type":    "FP16",
                "source":       "/dev/video-isx031-d-0",
                "adapter":      "yolov8",
                "width":        1920,
                "height":       1536,
                "format":   "UYUV"

        }
]
