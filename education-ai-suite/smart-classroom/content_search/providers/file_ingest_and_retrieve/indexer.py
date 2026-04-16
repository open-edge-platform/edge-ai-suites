# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import copy
import os
import sys

from moviepy import VideoFileClip
from PIL import Image

from providers.chromadb_wrapper.chroma_client import ChromaClientWrapper
from providers.file_ingest_and_retrieve.document_parser import DocumentParser
from providers.file_ingest_and_retrieve.detector import Detector
from providers.file_ingest_and_retrieve.utils import generate_unique_id, encode_image_to_base64, file_key_to_path, extract_bucket_name
from providers.file_ingest_and_retrieve.models import (
    get_visual_embedding_model,
    get_document_embedding_model,
)

logger = logging.getLogger(__name__)

def create_chroma_data(embedding, meta=None):
    return {"id": generate_unique_id(), "meta": meta, "vector": embedding}

class Indexer:
    def __init__(self, collection_name="content-search", visual_embedding_model=None, document_embedding_model=None, video_summary_id_map=None):
        self.client = ChromaClientWrapper()
        run_device = os.getenv("INGEST_DEVICE", "CPU")
        self.visual_collection_name = collection_name

        self.visual_embedding_model = visual_embedding_model or get_visual_embedding_model()

        self.detector = Detector(device=run_device)
        self.visual_id_map = {}
        self.visual_db_inited = False

        if self.client.load_collection(collection_name=self.visual_collection_name):
            logger.info(f"Collection '{self.visual_collection_name}' already exist.")
            self.visual_db_inited = True
            self._recover_id_map(self.visual_collection_name, self.visual_id_map)

        self.document_collection_name = f"{collection_name}_documents"

        self.document_embedding_model = document_embedding_model or get_document_embedding_model()

        self.document_parser = DocumentParser(
            chunk_size=250,
            chunk_overlap=50,
            # embed_model=self.document_embedding_model,
            # semantic_breakpoint_percentile=95,
            # semantic_min_chunk_size=150,
            extract_images=False,  # Don't extract images for now
            use_hi_res_strategy=False  # Use fast strategy for better performance
        )
        logger.info("Document parser initialized successfully.")
        self.document_id_map = {}
        self.document_db_inited = False
        if self.client.load_collection(collection_name=self.document_collection_name):
            logger.info(f"Document collection '{self.document_collection_name}' already exist.")
            self.document_db_inited = True
            self._recover_id_map(self.document_collection_name, self.document_id_map)

        # Shared map: video file_path -> list of summary embedding IDs.
        # Owned and recovered externally in server.py
        self.video_summary_id_map = video_summary_id_map if video_summary_id_map is not None else {}

    def _init_collection(self, collection_name, id_map_dict):
        """Generic method to initialize a collection."""
        self.client.create_collection(collection_name=collection_name)
        self._recover_id_map(collection_name, id_map_dict)

    def init_visual_db_client(self, dim):
        """Initialize visual data collection."""
        self._init_collection(self.visual_collection_name, self.visual_id_map)
        self.visual_db_inited = True
    
    def init_document_db_client(self, dim):
        """Initialize document collection."""
        self._init_collection(self.document_collection_name, self.document_id_map)
        self.document_db_inited = True

    def _update_id_map(self, id_map_dict, file_path, node_id):
        """Generic method to update an ID map."""
        if file_path not in id_map_dict:
            id_map_dict[file_path] = []
        id_map_dict[file_path].append(node_id)

    def _recover_id_map(self, collection_name, id_map_dict):
        res = self.client.query_all(collection_name, output_fields=["id", "meta"])
        if not res:
            logger.info(f"No data found in collection '{collection_name}'.")
            return
        for item in res:
            if "file_path" in item["meta"]:
                file_path = item["meta"]["file_path"]
                if file_path not in id_map_dict:
                    id_map_dict[file_path] = []
                id_map_dict[file_path].append(int(item["id"]))

    def get_id_maps(self):
        """Return current in-memory id_maps content."""
        return {
            "visual": {fp: list(ids) for fp, ids in self.visual_id_map.items()},
            "document": {fp: list(ids) for fp, ids in self.document_id_map.items()},
            "video_summary": {fp: list(ids) for fp, ids in self.video_summary_id_map.items()},
        }

    def recover_id_maps(self):
        """Clear and rebuild visual/document id_maps by querying the database."""
        self.visual_id_map.clear()
        self.document_id_map.clear()
        self._recover_id_map(self.visual_collection_name, self.visual_id_map)
        self._recover_id_map(self.document_collection_name, self.document_id_map)
        logger.info(
            f"ID maps recovered: {len(self.visual_id_map)} visual file(s), "
            f"{len(self.document_id_map)} document file(s), "
            f"{len(self.video_summary_id_map)} video summary file(s)."
        )
        return {
            "visual_files": len(self.visual_id_map),
            "document_files": len(self.document_id_map),
            "video_summary_files": len(self.video_summary_id_map),
        }

    def count_files(self):
        files = set()
        for key, value in self.visual_id_map.items():
            if key not in files:  
                files.add(key)
        for key, value in self.document_id_map.items():
            if key not in files:
                files.add(key)
        return len(files)
    
    def query_file(self, file_path):
        ids = []
        collection = None
        
        if file_path in self.visual_id_map:
            ids = self.visual_id_map[file_path]
            collection = self.visual_collection_name
        elif file_path in self.document_id_map:
            ids = self.document_id_map[file_path]
            collection = self.document_collection_name
        else:
            logger.warning(f"File {file_path} not found in id_map.")

        res = None
        # TBD: are vector and meta needed from db?
        # if ids and collection:
        #     res = self.client.get(
        #         collection_name=collection,
        #         ids=ids,
        #         output_fields=["id", "vector", "meta"]
        #     )
        
        return res, ids
        
    
    def delete_by_file_path(self, file_path):
        all_ids = []
        res = None

        if file_path in self.visual_id_map:
            ids = self.visual_id_map.pop(file_path)
            res = self.client.delete(collection_name=self.visual_collection_name, ids=ids)
            all_ids.extend(ids)
        if file_path in self.document_id_map:
            ids = self.document_id_map.pop(file_path)
            res = self.client.delete(collection_name=self.document_collection_name, ids=ids)
            all_ids.extend(ids)

        # Also remove associated summaries (keyed by video file_path)
        if file_path in self.video_summary_id_map:
            summary_ids = self.video_summary_id_map.pop(file_path)
            self.client.delete(collection_name=self.document_collection_name, ids=summary_ids)
            all_ids.extend(summary_ids)
            # Clean stale references from document_id_map
            summary_id_set = set(summary_ids)
            for fp, fids in list(self.document_id_map.items()):
                remaining = [i for i in fids if i not in summary_id_set]
                if remaining:
                    self.document_id_map[fp] = remaining
                else:
                    del self.document_id_map[fp]

        if not all_ids:
            logger.warning(f"File {file_path} not found in id_map.")
            return None, []
        return res, all_ids

    def delete_by_ids(self, ids):
        """Delete specific entries by their IDs and update id_maps accordingly.

        Args:
            ids: List of IDs (as strings, matching ChromaDB internal format)
        """
        visual_ids = []
        document_ids = []

        id_set = set(str(i) for i in ids)

        # Find which collection each ID belongs to and remove from id_maps
        for file_path, file_ids in list(self.visual_id_map.items()):
            remaining = [i for i in file_ids if i not in id_set]
            removed = [i for i in file_ids if i in id_set]
            visual_ids.extend(removed)
            if remaining:
                self.visual_id_map[file_path] = remaining
            elif removed:
                del self.visual_id_map[file_path]

        for file_path, file_ids in list(self.document_id_map.items()):
            remaining = [i for i in file_ids if i not in id_set]
            removed = [i for i in file_ids if i in id_set]
            document_ids.extend(removed)
            if remaining:
                self.document_id_map[file_path] = remaining
            elif removed:
                del self.document_id_map[file_path]

        # Also clean video_summary_id_map
        for fp, file_ids in list(self.video_summary_id_map.items()):
            remaining = [i for i in file_ids if i not in id_set]
            if remaining:
                self.video_summary_id_map[fp] = remaining
            else:
                del self.video_summary_id_map[fp]

        res = {}
        if visual_ids:
            res["visual"] = self.client.delete(collection_name=self.visual_collection_name, ids=visual_ids)
        if document_ids:
            res["document"] = self.client.delete(collection_name=self.document_collection_name, ids=document_ids)

        removed_ids = visual_ids + document_ids
        not_found = [i for i in ids if i not in removed_ids]

        # Fallback: try deleting orphaned IDs directly from both collections
        if not_found:
            logger.warning(f"IDs not found in id_map, attempting direct DB delete: {not_found}")
            for collection_name in [self.visual_collection_name, self.document_collection_name]:
                try:
                    self.client.delete(collection_name=collection_name, ids=not_found)
                except Exception as e:
                    logger.debug(f"Fallback delete from '{collection_name}' failed: {e}")
            removed_ids.extend(not_found)

        return res, removed_ids

    def delete_all(self):
        all_ids = []
        res_visual = res_document = None
        if self.visual_id_map:
            visual_ids = [id_ for ids in self.visual_id_map.values() for id_ in ids]
            res_visual = self.client.delete(collection_name=self.visual_collection_name, ids=visual_ids)
            self.visual_id_map.clear()
            all_ids.extend(visual_ids)
        if self.document_id_map:
            document_ids = [id_ for ids in self.document_id_map.values() for id_ in ids]
            res_document = self.client.delete(collection_name=self.document_collection_name, ids=document_ids)
            self.document_id_map.clear()
            all_ids.extend(document_ids)
        self.video_summary_id_map.clear()
        if not all_ids:
            return None, []
        return {"visual": res_visual, "document": res_document}, all_ids

    def get_image_embedding(self, image):
        embedding_tensor = self.visual_embedding_model.handler.encode_image(image)
        # Convert tensor to a list of floats for ChromaDB
        # The result is a batch of one, so we extract the single embedding list

        return embedding_tensor.cpu().numpy().tolist()[0]

    def get_document_embedding(self, text):
        if not self.document_embedding_model:
            raise RuntimeError("Document embedding model not available.")
        return self.document_embedding_model.get_text_embedding(text)

    def process_video(self, video_path, meta, frame_extract_interval=15, do_detect_and_crop=True):
        entities = []
        video = VideoFileClip(video_path)
        try:
            frame_counter = 0
            frame_extract_interval = int(frame_extract_interval)
            fps = video.fps
            total_frames = int(video.duration * fps)
            extracted_count = 0
            logger.debug(f"Video {video_path}: fps={fps}, total_frames={total_frames}, frame_extract_interval={frame_extract_interval}, "
                         f"estimated extractions={total_frames // frame_extract_interval + 1}")
            for frame in video.iter_frames():
                if frame_counter % frame_extract_interval == 0:
                    extracted_count += 1
                    image = Image.fromarray(frame)
                    seconds = frame_counter / fps
                    half_window = frame_extract_interval / fps / 2 + 3
                    meta_data = copy.deepcopy(meta)
                    meta_data["video_pin_second"] = round(seconds, 2)
                    meta_data["video_start_second"] = round(max(0, seconds - half_window), 2)
                    meta_data["video_end_second"] = round(min(video.duration, seconds + half_window), 2)
                    if do_detect_and_crop:
                        for crop in self.detector.get_cropped_images(image):
                            embedding = self.get_image_embedding(crop)
                            if not self.visual_db_inited:
                                self.init_visual_db_client(len(embedding))
                            node = create_chroma_data(embedding, meta_data)
                            entities.append(node)
                            self._update_id_map(self.visual_id_map, meta_data["file_path"], node["id"])
                    embedding = self.get_image_embedding(image)
                    if not self.visual_db_inited:
                        self.init_visual_db_client(len(embedding))
                    node = create_chroma_data(embedding, meta_data)
                    entities.append(node)
                    self._update_id_map(self.visual_id_map, meta_data["file_path"], node["id"])
                frame_counter += 1
            logger.info(f"Processed video {video_path}: {extracted_count} frames extracted, {len(entities)} embeddings")
        finally:
            video.close()
        return entities

    def process_image(self, image_path, meta, do_detect_and_crop=True):
        entities = []
        image = Image.open(image_path).convert('RGB')
        meta_data = copy.deepcopy(meta)
        if do_detect_and_crop:
            for crop in self.detector.get_cropped_images(image):
                embedding = self.get_image_embedding(crop)
                if not self.visual_db_inited:
                    self.init_visual_db_client(len(embedding))
                node = create_chroma_data(embedding, meta_data)
                entities.append(node)
                self._update_id_map(self.visual_id_map, meta_data["file_path"], node["id"])
        embedding = self.get_image_embedding(image)
        if not self.visual_db_inited:
            self.init_visual_db_client(len(embedding))
        node = create_chroma_data(embedding, meta_data)
        entities.append(node)
        self._update_id_map(self.visual_id_map, meta_data["file_path"], node["id"])
        logger.info(f"Processed image {image_path}: {len(entities)} embeddings")
        return entities

    def process_document(self, document_path, meta):
        """Process a document file and create text embeddings for each chunk.
        
        Args:
            document_path: Path to the document file
            meta: Metadata dictionary for the document
            
        Returns:
            List of entities with embeddings and metadata
        """
        entities = []
        if not self.document_parser:
            raise RuntimeError("Document parser not available. Please install required dependencies.")
        
        try:
            # Parse the document into chunks and process
            nodes = self.document_parser.parse_file(document_path)
            for idx, node in enumerate(nodes):
                meta_data = copy.deepcopy(meta)
                meta_data["chunk_index"] = idx
                meta_data["chunk_text"] = node.get_content()
                
                if hasattr(node, 'metadata') and node.metadata:
                    for key, value in node.metadata.items():
                        if key not in meta_data:
                            meta_data[f"doc_{key}"] = value
                
                embedding = self.get_document_embedding(node.get_content())
                
                if not self.document_db_inited:
                    self.init_document_db_client(len(embedding))
                
                node_data = create_chroma_data(embedding, meta_data)
                entities.append(node_data)
                self._update_id_map(self.document_id_map, meta_data["file_path"], node_data["id"])
            
            logger.info(f"Processed document {document_path}: {len(nodes)} chunks")
            
        except Exception as e:
            logger.error(f"Error processing document {document_path}: {e}")
            raise
        
        return entities

    def process_text(self, text: str, meta: dict) -> list:
        """Embed a raw text string as a single node (no chunking)."""
        meta_data = copy.deepcopy(meta)
        meta_data["chunk_text"] = text
        meta_data["chunk_index"] = 0

        embedding = self.get_document_embedding(text)

        if not self.document_db_inited:
            self.init_document_db_client(len(embedding))

        node = create_chroma_data(embedding, meta_data)
        file_path = meta_data.get("file_path", "__independent_text__")
        self._update_id_map(self.document_id_map, file_path, node["id"])

        if "summary_key" in meta_data and "file_key" in meta_data and "file_path" in meta_data:
            bucket = extract_bucket_name(meta_data["file_path"])
            if bucket:
                video_fp = file_key_to_path(meta_data["file_key"], bucket)
                self._update_id_map(self.video_summary_id_map, video_fp, node["id"])

        return [node]

    def ingest_text(self, text: str, meta: dict) -> dict:
        """Ingest a single text string into the document collection without chunking."""
        if not text or not isinstance(text, str):
            raise ValueError("text must be a non-empty string.")

        meta = {**meta, "type": "document", "doc_filetype": "text/plain"}
        entities = self.process_text(text, meta)
        return self.client.insert(collection_name=self.document_collection_name, data=entities)

    def add_embedding(self, files, metas, **kwargs):
        if len(files) != len(metas):
            raise ValueError(f"Number of files and metas must be the same. files: {len(files)}, metas: {len(metas)}")
        
        frame_extract_interval = kwargs.get("frame_extract_interval")
        do_detect_and_crop = kwargs.get("do_detect_and_crop", True)
        entities = []
        doc_extensions = ('.txt', '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx',
                          '.xls', '.html', '.htm', '.xml', '.md')

        for file, meta in zip(files, metas):
            if meta["file_path"] in self.visual_id_map or meta["file_path"] in self.document_id_map:
                logger.info(f"File {file} already processed, skipping.")
                continue
            file_lower = file.lower()
            if file_lower.endswith('.mp4'):
                meta["type"] = "video"
                logger.info(f"Processing video: {file}")
                entities.extend(self.process_video(file, meta, frame_extract_interval, do_detect_and_crop))
            elif file_lower.endswith(('.jpg', '.png', '.jpeg')):
                meta["type"] = "image"
                logger.info(f"Processing image: {file}")
                entities.extend(self.process_image(file, meta, do_detect_and_crop))
            elif file_lower.endswith(doc_extensions):
                meta["type"] = "document"
                try:
                    logger.info(f"Processing document: {file}")
                    entities.extend(self.process_document(file, meta))
                except Exception as e:
                    logger.error(f"Error processing document {file}: {e}")
            else:
                logger.warning(f"Unsupported file type: {file}")

        visual_entities = [e for e in entities if e.get("meta", {}).get("type") in ["video", "image"]]
        document_entities = [e for e in entities if e.get("meta", {}).get("type") == "document"]
        res = {}
        if visual_entities:
            res["visual"] = self.client.insert(collection_name=self.visual_collection_name, data=visual_entities)
        if document_entities:
            res["document"] = self.client.insert(collection_name=self.document_collection_name, data=document_entities)
        return res
