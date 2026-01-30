# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import copy
import json
import sys
import numpy as np
from pathlib import Path

from moviepy.editor import VideoFileClip
from PIL import Image

from multimodal_embedding_serving import get_model_handler, EmbeddingModel

from video_ingest_and_retrieve.detector import Detector
from video_ingest_and_retrieve.utils import generate_unique_id, encode_image_to_base64

from chromadb_wrapper.chroma_client import ChromaClientWrapper


DEVICE = os.getenv("DEVICE", "CPU")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "CLIP/clip-vit-b-16")


def create_chroma_data(embedding, meta=None):
    data = {}
    data["id"] = generate_unique_id()
    data["meta"] = meta
    data["vector"] = embedding
    return data

class Indexer:
    def __init__(self, collection_name="default"):
        self.model_name = EMBEDDING_MODEL_NAME
        
        handler = get_model_handler(self.model_name)
        handler.load_model()
        self.embedding_model = EmbeddingModel(handler)

        self.detector = Detector(device=DEVICE)

        self.id_map = {}
        self.db_inited = False
        self.client = ChromaClientWrapper()
        self.collection_name = collection_name

        if self.client.load_collection(collection_name=self.collection_name):
            print(f"Collection '{self.collection_name}' already exist.")
            self.db_inited = True
            self.recover_id_map()

    def init_db_client(self, dim):
        self.client.create_collection(collection_name=self.collection_name)

        self.db_inited = True
        self.recover_id_map()

    def update_id_map(self, file_path, node_id):
        if file_path not in self.id_map:
            self.id_map[file_path] = []
        self.id_map[file_path].append(node_id)

    def recover_id_map(self):
        res = self.client.query_all(self.collection_name, output_fields=["id", "meta"])
        if not res:
            print("No data found in the collection.")
            return
        for item in res:
            if "file_path" in item["meta"]:
                file_path = item["meta"]["file_path"]
                if file_path not in self.id_map:
                    self.id_map[file_path] = []
                self.id_map[file_path].append(int(item["id"]))

    def count_files(self):
        files = set()
        for key, value in self.id_map.items():
            if key not in files:  
                files.add(key)    
        return len(files)
    
    def query_file(self, file_path):
        ids = []
        if file_path in self.id_map:
            ids = self.id_map[file_path]

        res = None
        # TBD: are vector and meta needed from db?
        # res = self.client.get(
        #     collection_name=self.collection_name,
        #     ids=ids,
        #     output_fields=["id", "vector", "meta"]
        # )
        
        return res, ids
        
    
    def delete_by_file_path(self, file_path):
        ids = []
        if file_path in self.id_map:
            ids = self.id_map[file_path]
            res = self.client.delete(
                collection_name=self.collection_name,
                ids=ids,
            )
            del self.id_map[file_path]
        else:
            print(f"File {file_path} not found in db.")
        return res, ids
    
    def delete_all(self):
        if not self.id_map:
            return None, []
        ids = []
        for key, value in self.id_map.items():
            ids.extend(value)
        res = self.client.delete(
            collection_name=self.collection_name,
            ids=ids,
        )
        self.id_map.clear()

        return res, ids
    
    def get_image_embedding(self, image):
        embedding_tensor = self.embedding_model.handler.encode_image(image)
        # Convert tensor to a list of floats for ChromaDB
        embedding_list = embedding_tensor.cpu().numpy().tolist()
        # The result is a batch of one, so we extract the single embedding list
        return embedding_list[0]
        
    def process_video(self, video_path, meta, frame_interval=15, minimal_duration=1, do_detect_and_crop=True):
        entities = []
        video = VideoFileClip(video_path)

        frame_counter = 0
        frame_interval = int(frame_interval)
        fps = video.fps
        for frame in video.iter_frames():
            if frame_counter % frame_interval == 0:
                image = Image.fromarray(frame)
                seconds = frame_counter / fps
                meta_data = copy.deepcopy(meta)
                meta_data["video_pin_second"] = seconds
                if do_detect_and_crop:
                    crops = self.detector.get_cropped_images(image)
                    for crop in crops:
                        embedding = self.get_image_embedding(crop)
                        if not self.db_inited:
                            self.init_db_client(len(embedding))
                        node = create_chroma_data(embedding, meta_data)
                        entities.append(node)
                        self.update_id_map(meta_data["file_path"], node["id"])

                embedding = self.get_image_embedding(image)
                if not self.db_inited:
                    self.init_db_client(len(embedding))
                node = create_chroma_data(embedding, meta_data)
                entities.append(node)
                self.update_id_map(meta_data["file_path"], node["id"])
            frame_counter += 1
            
        return entities

    def process_image(self, image_path, meta, do_detect_and_crop=True):
        entities = []
        image = Image.open(image_path).convert('RGB')
        meta_data = copy.deepcopy(meta)
        if do_detect_and_crop:
            crops = self.detector.get_cropped_images(image)
            for crop in crops:
                embedding = self.get_image_embedding(crop)
                if not self.db_inited:
                    self.init_db_client(len(embedding))
                node = create_chroma_data(embedding, meta_data)
                entities.append(node)
                self.update_id_map(meta_data["file_path"], node["id"])
        
        embedding = self.get_image_embedding(image)
        if not self.db_inited:
            self.init_db_client(len(embedding))
        node = create_chroma_data(embedding, meta_data)
        entities.append(node)
        self.update_id_map(meta_data["file_path"], node["id"])
        return entities

    def add_embedding(self, files, metas, **kwargs):
        if len(files) != len(metas):
            raise ValueError(f"Number of files and metas must be the same. files: {len(files)}, metas: {len(metas)}")
        
        frame_interval = kwargs.get("frame_interval", 15)
        minimal_duration = kwargs.get("minimal_duration", 1)
        do_detect_and_crop = kwargs.get("do_detect_and_crop", True)
        entities = []
        for file, meta in zip(files, metas):
            # print("processing file: ", file)
            if meta["file_path"] in self.id_map:
                print(f"File {file} already processed, skipping.")
                continue
            if file.lower().endswith(('.mp4')):
                meta["type"] = "video"
                entities.extend(self.process_video(file, meta, frame_interval, minimal_duration, do_detect_and_crop))
            elif file.lower().endswith(('.jpg', '.png', '.jpeg')):
                meta["type"] = "image"
                entities.extend(self.process_image(file, meta, do_detect_and_crop))
            else:
                print(f"Unsupported file type: {file}. Supported types are: jpg, png, mp4")

        res = {}
        if entities:
            res = self.client.insert(
                collection_name=self.collection_name,
                data=entities,
            )
        return res


    def _submit_embedding(self, entities):
        # aync thread which collects embeddings and insert to db in batch
        pass

    def _build_index(self):
        # build index
        pass
