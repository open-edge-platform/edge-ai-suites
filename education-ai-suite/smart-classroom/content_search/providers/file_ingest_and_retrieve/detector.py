# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Edit based on: https://github.com/Megvii-BaseDetection/YOLOX/blob/main/demo/OpenVINO/python/openvino_inference.py

import os
import subprocess

from PIL import Image
import numpy as np
import openvino as ov

from content_search.file_ingest_and_retrieve.yolox_utils import preproc, multiclass_nms, demo_postprocess

MODEL_DIR = "./models"


class Detector:
    def __init__(self, device="CPU", conf=0.85, nms=0.45, input_size=(640, 640)):
        self.model_path = os.path.join(MODEL_DIR, "detection_model")
        self.model_file = os.path.join(self.model_path, "yolox_s.xml")
        self.download_model()
        self.device = device
        self.conf = conf
        self.nms = nms
        self.input_size = input_size

        core = ov.Core()
        self.net = core.read_model(model=self.model_file)
        self.exec_net = core.compile_model(self.net, self.device)
        _, _, self.h, self.w = self.exec_net.inputs[0].shape

    def download_model(self):
        if not os.path.exists(self.model_file):
            os.makedirs(self.model_path, exist_ok=True)
            download_cmd = [
                "curl", "-L", "--retry", "5", "--retry-delay", "5",
                "--connect-timeout", "30",
                "-o", os.path.join(self.model_path, "yolox_s_openvino.tar.gz"),
                "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s_openvino.tar.gz",
            ]
            subprocess.run(download_cmd, capture_output=True, text=True)
            tar_cmd = ["tar", "-xvf", os.path.join(self.model_path, "yolox_s_openvino.tar.gz"), "-C", self.model_path]
            subprocess.run(tar_cmd, capture_output=True, text=True)
            if not os.path.exists(self.model_file):
                raise FileNotFoundError(f"Model file {self.model_file} does not exist.")

    def get_det_results(self, image):
        image, ratio = preproc(image, (self.h, self.w))
        # res = self.exec_net.infer(inputs={self.input_blob: image})
        res = self.exec_net.infer_new_request(image)["output"]
        predictions = demo_postprocess(res, (self.h, self.w))[0]
        boxes = predictions[:, :4]
        scores = predictions[:, 4, None] * predictions[:, 5:]
        boxes_xyxy = np.ones_like(boxes)
        boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.
        boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.
        boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.
        boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.
        boxes_xyxy /= ratio
        dets = multiclass_nms(boxes_xyxy, scores, nms_thr=self.nms, score_thr=self.conf)
        final_boxes, final_scores, final_cls_inds = [], [], []
        if dets is not None:
            final_boxes = dets[:, :4]
            final_scores, final_cls_inds = dets[:, 4], dets[:, 5]
        return final_boxes, final_scores, final_cls_inds

    def get_cropped_images(self, image):
        if not isinstance(image, Image.Image):
            image = Image.fromarray(image)
        boxes, _, _ = self.get_det_results(np.array(image))
        cropped_images = []
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(image.width, x2), min(image.height, y2)
            if x1 >= x2 or y1 >= y2:
                continue
            cropped_images.append(image.crop((x1, y1, x2, y2)))
        return cropped_images
