# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import threading
import time
import logging
import cv2
from utils.mobilesam_helper import MobileSamHelper

print("execute logging basic Config")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class InferenceThread(threading.Thread):

    def __init__(self, inferenceQueue, inference_queue_lock, output_queue, output_lock):
        super().__init__()
        self.inference_device = "GPU"
        # self.inference_device = "CPU"
        self.isInference = True
        self.inferenceQueue = inferenceQueue
        self.inference_queue_lock = inference_queue_lock
        self.output_queue = output_queue
        self.output_lock = output_lock
        self.infResultImage = None
        self.mobilesam = MobileSamHelper(sam_device=self.inference_device, clip_device=self.inference_device)

    def _inference(self):
        if self.inferenceQueue.empty() == True:
            time.sleep(0.1)
            return

        logger.info("Received inference request ...")
        POIDepthInM = -1.0
        inferenceState = {
            "isRunning": True,
            "POIDistance": POIDepthInM,
            "status": "Starting to inference ..."
        }
        self.inference_queue_lock.acquire()
        frame = self.inferenceQueue.get()
        self.inference_queue_lock.release()

        inference_color_frame = frame['color_frame']
        text_prompt = frame['text_prompt']
        text_prompt = text_prompt.lower()
        logger.info(f"Text prompt : {text_prompt}")

        try:
            # Perform inferencing here
            self.mobilesam.label = text_prompt
            self.mobilesam.color_image = cv2.cvtColor(inference_color_frame, cv2.COLOR_BGR2RGB)
            masks = self.mobilesam.mask_everything()
            #save bbox
            #self.mobilesam.save_bbox(masks)
            #print("==========>test_bbox_clip")
            #self.mobilesam.test_bbox_clip()
            #print("==========>test_bbox_clip end")
            max_idx, max_similarity, max_prob = self.mobilesam.clip_predict(masks)
            print(f'max_idx={max_idx}, max_similarity={max_similarity}, max_prob={max_prob}')
            #debug target
            #self.mobilesam.save_predict_bbox(masks, max_idx)
            roi = masks[max_idx]['bbox']  #x, y, w, h
            centerbox = self.mobilesam.calculate_centroid([roi[0], roi[1], roi[0] + roi[2], roi[1] + roi[3]]) 
            object_centroid = centerbox[0]
            resultImage = self.mobilesam.get_result_image(masks, max_idx)
            confid_score = max_prob
        except Exception as error:
            logger.error(f"Error in inferencing: {error}")
            return
        
        if object_centroid:
            logger.info(f"Found ROI, POI: {object_centroid}, score: {confid_score}")
            formatted_object_centroid = (0 + object_centroid[0], 0 + object_centroid[1])
            logger.info(f"Postprocess ROI: {formatted_object_centroid}")

            # scale: 495/475 = 1.042105263
            logger.info(f"Postprocess ROI with scale: {formatted_object_centroid[0] * 1.042105263}, {formatted_object_centroid[1] * 1.042105263}")
            self.infResultImage = resultImage

            inferenceState.update({
                "isRunning": False,
                "POIDistance": -1.0,
                "centerX": (formatted_object_centroid[0] - 640) * 1.042105263 / 1000.0,
                "centerY": (formatted_object_centroid[1] - 360) * 1.042105263 / 1000.0,
                "centerZ": 0.9517,
                "score": confid_score,
                "status": "Requested object found in the frame.\nGoing to pick up the object ..."
            })

            self.output_lock.acquire()
            self.output_queue.put(inferenceState)
            self.output_lock.release()
        else:
            inferenceState.update({
                "isRunning": False,
                "POIDistance": -1.0,
                "status": "Unable to find the object requested by user. Please try with another input."
            })
            self.output_lock.acquire()
            self.output_queue.put(inferenceState)
            self.output_lock.release()
            return

        inferenceState.update({
            "isRunning": False,
            "POIDistance": POIDepthInM,
            "status": "Requested object found in the frame.\nGoing to pick up the object ..."
        })

    def run(self):
        while self.isInference:
            self._inference()

    def resumeWorker(self):
        self.isInference = True

    def pauseWorker(self):
        self.isInference = False

    def stopWorker(self):
        self.isInference = False

    def getInfResultImg(self):
        return self.infResultImage

if __name__ == "__main__":
    infThread = InferenceThread()
    infThread.start()
