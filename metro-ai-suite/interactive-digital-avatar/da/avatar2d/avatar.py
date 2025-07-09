import glob
import json
import os
import pickle
import queue
import shutil
import sys
import threading
from queue import Queue

import cv2
import numpy as np
import torch
from tqdm import tqdm

from da.util.log import logger
from ext.musetalk.utils.blending import get_image_prepare_material, get_image_blending
from ext.musetalk.utils.preprocessing import read_imgs, get_landmark_and_bbox
from ext.musetalk.utils.utils import load_all_model, datagen


def video2imgs(vid_path, save_path, ext='png', cut_frame=10000000):
    cap = cv2.VideoCapture(vid_path)
    count = 0
    while True:
        if count > cut_frame:
            break
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(f"{save_path}/{count:08d}.{ext}", frame)
            count += 1
        else:
            break


def osmakedirs(path_list):
    for path in path_list:
        os.makedirs(path) if not os.path.exists(path) else None


class Avatar:
    def __init__(self, avatar_id, video_path, bbox_shift, batch_size, preparation, fps):
        self.avatar_id = avatar_id
        self.video_path = video_path
        self.bbox_shift = bbox_shift
        self.preparation = preparation
        self.batch_size = batch_size
        self.fps = fps

        self.idx = 0
        self.avatar_path = f"./output/avatars2d/{avatar_id}"
        self.full_imgs_path = f"{self.avatar_path}/full_imgs"
        self.coords_path = f"{self.avatar_path}/coords.pkl"
        self.latents_out_path = f"{self.avatar_path}/latents.pt"
        self.video_out_path = f"{self.avatar_path}/vid_output/"
        self.mask_out_path = f"{self.avatar_path}/mask"
        self.mask_coords_path = f"{self.avatar_path}/mask_coords.pkl"
        self.avatar_info_path = f"{self.avatar_path}/avator_info.json"
        self.avatar_info = {
            "avatar_id": avatar_id,
            "video_path": video_path,
            "bbox_shift": bbox_shift
        }

        # load model weights
        self.audio_processor, self.vae, self.unet, self.pe = load_all_model()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device.type != "cpu":  # cpu not support half on some part of model
            self.pe = self.pe.half()
            self.vae.vae = self.vae.vae.half()
            self.unet.model = self.unet.model.half()

        self.timesteps = torch.tensor([0], device=device)

        self.init()

        logger.info(f"Avatar {self.avatar_id} initialized")

    def init(self):
        if self.preparation:
            if os.path.exists(self.avatar_path):
                shutil.rmtree(self.avatar_path)

            logger.info(f"creating 2D avator: {self.avatar_id}")
            osmakedirs([self.avatar_path, self.full_imgs_path, self.video_out_path, self.mask_out_path])
            self.prepare_material()

        else:
            if not os.path.exists(self.avatar_path):
                logger.error(f"avatar {self.avatar_id} does not exist, you should prepare it at first.")
                sys.exit()

            logger.info(f"Loading Avatar {self.avatar_id} from {self.avatar_path}")

            self.input_latent_list_cycle = torch.load(self.latents_out_path)
            with open(self.coords_path, 'rb') as f:
                self.coord_list_cycle = pickle.load(f)
            input_img_list = glob.glob(os.path.join(self.full_imgs_path, '*.[jpJP][pnPN]*[gG]'))
            input_img_list = sorted(input_img_list, key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))
            self.frame_list_cycle = read_imgs(input_img_list)
            with open(self.mask_coords_path, 'rb') as f:
                self.mask_coords_list_cycle = pickle.load(f)
            input_mask_list = glob.glob(os.path.join(self.mask_out_path, '*.[jpJP][pnPN]*[gG]'))
            input_mask_list = sorted(input_mask_list, key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))
            self.mask_list_cycle = read_imgs(input_mask_list)

    def prepare_material(self):
        with open(self.avatar_info_path, "w") as f:
            json.dump(self.avatar_info, f)

        # extract frames
        if os.path.isfile(self.video_path):
            video2imgs(self.video_path, self.full_imgs_path, ext='png')
        else:
            logger.info(f"copy files in {self.video_path}")
            files = os.listdir(self.video_path)
            files.sort()
            files = [file for file in files if file.split(".")[-1] == "png"]
            for filename in files:
                shutil.copyfile(f"{self.video_path}/{filename}", f"{self.full_imgs_path}/{filename}")
        input_img_list = sorted(glob.glob(os.path.join(self.full_imgs_path, '*.[jpJP][pnPN]*[gG]')))

        # extract landmarks
        coord_list, frame_list = get_landmark_and_bbox(input_img_list, self.bbox_shift)
        input_latent_list = []
        idx = -1
        # maker if the bbox is not sufficient
        coord_placeholder = (0.0, 0.0, 0.0, 0.0)
        for bbox, frame in tqdm(zip(coord_list, frame_list), total=len(coord_list), desc="get video latent"):
            idx = idx + 1
            if bbox == coord_placeholder:
                continue
            x1, y1, x2, y2 = bbox
            crop_frame = frame[y1:y2, x1:x2]
            resized_crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
            latents = self.vae.get_latents_for_unet(resized_crop_frame)
            input_latent_list.append(latents)

        self.frame_list_cycle = frame_list + frame_list[::-1]
        self.coord_list_cycle = coord_list + coord_list[::-1]
        self.input_latent_list_cycle = input_latent_list + input_latent_list[::-1]
        self.mask_coords_list_cycle = []
        self.mask_list_cycle = []

        # extract mask
        for i, frame in enumerate(tqdm(self.frame_list_cycle, desc="get muse mask")):
            cv2.imwrite(f"{self.full_imgs_path}/{str(i).zfill(8)}.png", frame)

            face_box = self.coord_list_cycle[i]
            mask, crop_box = get_image_prepare_material(frame, face_box)
            cv2.imwrite(f"{self.mask_out_path}/{str(i).zfill(8)}.png", mask)
            self.mask_coords_list_cycle += [crop_box]
            self.mask_list_cycle.append(mask)

        with open(self.mask_coords_path, 'wb') as f:
            pickle.dump(self.mask_coords_list_cycle, f)

        with open(self.coords_path, 'wb') as f:
            pickle.dump(self.coord_list_cycle, f)

        torch.save(self.input_latent_list_cycle, os.path.join(self.latents_out_path))

        logger.info(f"2D avatar saved to {self.avatar_path}")

    def audio2chunks(self, audio_path, fps):
        whisper_feature = self.audio_processor.audio2feat(audio_path)
        whisper_chunks = self.audio_processor.feature2chunks(feature_array=whisper_feature, fps=fps)
        return whisper_chunks

    def gen_face(self, whisper_chunks, output_face_queue: Queue):
        gen = datagen(whisper_chunks, self.input_latent_list_cycle, self.batch_size, delay_frame=self.idx)
        for i, (whisper_batch, latent_batch) in enumerate(gen):
            audio_feature_batch = torch.from_numpy(whisper_batch)
            audio_feature_batch = audio_feature_batch.to(device=self.unet.device, dtype=self.unet.model.dtype)
            audio_feature_batch = self.pe(audio_feature_batch)
            latent_batch = latent_batch.to(device=self.unet.device, dtype=self.unet.model.dtype)

            pred_latents = self.unet.model(latent_batch, self.timesteps, encoder_hidden_states=audio_feature_batch).sample
            recon = self.vae.decode_latents(pred_latents)

            for res_frame in recon:
                output_face_queue.put(res_frame)

    def combine_face_to_frame(self, input_face_frames: Queue, output_frame_queue: Queue, frame_count: int):
        for _ in range(frame_count):
            face_frame = input_face_frames.get()

            frame_idx = self.idx % (len(self.coord_list_cycle))
            bbox = self.coord_list_cycle[frame_idx]
            ori_frame = self.frame_list_cycle[frame_idx].copy()

            try:
                x1, y1, x2, y2 = bbox
                res_frame = cv2.resize(face_frame.astype(np.uint8), (x2 - x1, y2 - y1))
            except:
                continue

            mask = self.mask_list_cycle[frame_idx]
            mask_crop_box = self.mask_coords_list_cycle[frame_idx]
            combine_frame = get_image_blending(ori_frame, res_frame, bbox, mask, mask_crop_box)
            output_frame_queue.put(combine_frame)

            self.idx += 1

    def inference(self, audio_path, fps):
        with torch.no_grad():
            whisper_chunks = self.audio2chunks(audio_path, fps)
            frame_count = len(whisper_chunks)

            face_queue = queue.Queue()
            frame_queue = queue.Queue()

            face_thread = threading.Thread(target=self.gen_face, args=(whisper_chunks, face_queue))
            face_thread.daemon = True
            face_thread.start()

            combine_thread = threading.Thread(target=self.combine_face_to_frame, args=(face_queue, frame_queue, frame_count))
            combine_thread.daemon = True
            combine_thread.start()

            output_frames = []
            for _ in tqdm(range(frame_count), desc="Generating frames"):
                output_frames.append(frame_queue.get())

            return output_frames
