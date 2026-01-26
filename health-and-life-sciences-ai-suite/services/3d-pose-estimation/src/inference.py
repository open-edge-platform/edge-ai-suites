import cv2
import numpy as np
from openvino import Core

MODEL_XML = "models/human-pose-estimation-3d-0001.xml"
MODEL_BIN = "models/human-pose-estimation-3d-0001.bin"


class PoseEstimator:
    def __init__(self, device="CPU"):
        ie = Core()
        model = ie.read_model(MODEL_XML, MODEL_BIN)
        self.compiled_model = ie.compile_model(model, device)

        _, _, self.h, self.w = self.compiled_model.input(0).shape

    def preprocess(self, frame):
        img = cv2.resize(frame, (self.w, self.h))
        img = img.transpose((2, 0, 1))
        img = img[None, ...].astype("float32")
        return img

    def infer(self, frame):
        tensor = self.preprocess(frame)
        result = self.compiled_model([tensor])
        return list(result.values())
