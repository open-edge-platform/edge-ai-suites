from queue import Queue, Empty

import cv2
import numpy as np

from da.avatar2d.avatar_ov import AvatarOV
from da.util.log import logger
from da.util.woker import PipelineWorker, WorkerType
from ext.musetalk.utils.blending import get_image_blending


class CombineFaceWorker(PipelineWorker):
    def __init__(self, avatar: AvatarOV, face_input_queue: Queue, frame_output_queue: Queue):

        self.avatar = avatar
        self.face_input_queue = face_input_queue
        self.frame_output_queue = frame_output_queue

        super().__init__(self.__class__.__name__, WorkerType.Thread)

    def _init(self):
        pass

    def _run(self):
        while self._is_running():
            try:
                face_frame, frame_idx = self.face_input_queue.get(timeout=1)
            except Empty:
                continue

            if face_frame is None:
                # No face generated, use original img.
                ori_frame = self.avatar.frame_list_cycle[frame_idx].copy()
                self.frame_output_queue.put(ori_frame)
                continue

            # Face generated
            bbox = self.avatar.coord_list_cycle[frame_idx]
            ori_frame = self.avatar.frame_list_cycle[frame_idx].copy()

            try:
                x1, y1, x2, y2 = bbox
                res_frame = cv2.resize(face_frame.astype(np.uint8), (x2 - x1, y2 - y1))
            except Exception as e:
                logger.error(f"Error resizing frame: {e}")
                continue

            mask = self.avatar.mask_list_cycle[frame_idx]
            mask_crop_box = self.avatar.mask_coords_list_cycle[frame_idx]
            combine_frame = get_image_blending(ori_frame, res_frame, bbox, mask, mask_crop_box)
            self.frame_output_queue.put(combine_frame)
