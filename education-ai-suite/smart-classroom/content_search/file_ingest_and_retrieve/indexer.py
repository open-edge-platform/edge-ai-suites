# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import copy

from moviepy.editor import VideoFileClip
from PIL import Image

from multimodal_embedding_serving import get_model_handler, EmbeddingModel
from llama_index.embeddings.huggingface_openvino import OpenVINOEmbedding

from content_search.chromadb_wrapper.chroma_client import ChromaClientWrapper
from content_search.file_ingest_and_retrieve.document_parser import DocumentParser
from content_search.file_ingest_and_retrieve.detector import Detector
from content_search.file_ingest_and_retrieve.utils import generate_unique_id, encode_image_to_base64
from utils.config_loader import config

logger = logging.getLogger(__name__)

_cfg = config.content_search.file_ingest


def create_chroma_data(embedding, meta=None):
    return {"id": generate_unique_id(), "meta": meta, "vector": embedding}


class Indexer:
    def __init__(self, collection_name="default"):
        self.client = ChromaClientWrapper()

        self.visual_collection_name = collection_name
        handler = get_model_handler(_cfg.visual_embedding_model)
        handler.load_model()
        self.visual_embedding_model = EmbeddingModel(handler)
        self.detector = Detector(device=_cfg.device)
        self.visual_id_map = {}
        self.visual_db_inited = False
        if self.client.load_collection(collection_name=self.visual_collection_name):
            logger.info(f"Collection '{self.visual_collection_name}' already exist.")
            self.visual_db_inited = True
            self._recover_id_map(self.visual_collection_name, self.visual_id_map)

        self.document_collection_name = f"{collection_name}_documents"
        self.document_embedding_model = OpenVINOEmbedding(
            model_id_or_path=_cfg.doc_embedding_model,
            device=_cfg.device,
        )
        self.document_parser = DocumentParser(
            chunk_size=250,
            chunk_overlap=50,
            # embed_model=self.document_embedding_model,  # ✅ OpenVINOEmbedding 实例，不是字符串
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
        }

    def recover_id_maps(self):
        """Clear and rebuild both id_maps by querying the database."""
        self.visual_id_map.clear()
        self.document_id_map.clear()
        self._recover_id_map(self.visual_collection_name, self.visual_id_map)
        self._recover_id_map(self.document_collection_name, self.document_id_map)
        logger.info(
            f"ID maps recovered: {len(self.visual_id_map)} visual file(s), "
            f"{len(self.document_id_map)} document file(s)."
        )
        return {
            "visual_files": len(self.visual_id_map),
            "document_files": len(self.document_id_map),
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
        if file_path in self.visual_id_map:
            ids = self.visual_id_map.pop(file_path)
            return self.client.delete(collection_name=self.visual_collection_name, ids=ids), ids
        if file_path in self.document_id_map:
            ids = self.document_id_map.pop(file_path)
            return self.client.delete(collection_name=self.document_collection_name, ids=ids), ids
        logger.warning(f"File {file_path} not found in id_map.")
        return None, []

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
        self._update_id_map(self.document_id_map, meta_data["file_path"], node["id"])
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
        
        frame_interval = kwargs.get("frame_interval", 15)
        minimal_duration = kwargs.get("minimal_duration", 1)
        do_detect_and_crop = kwargs.get("do_detect_and_crop", True)
        entities = []
        doc_extensions = ('.txt', '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx',
                          '.xls', '.html', '.htm', '.xml', '.md', '.rst')

        for file, meta in zip(files, metas):
            if meta["file_path"] in self.visual_id_map or meta["file_path"] in self.document_id_map:
                logger.info(f"File {file} already processed, skipping.")
                continue
            file_lower = file.lower()
            if file_lower.endswith('.mp4'):
                meta["type"] = "video"
                entities.extend(self.process_video(file, meta, frame_interval, minimal_duration, do_detect_and_crop))
            elif file_lower.endswith(('.jpg', '.png', '.jpeg')):
                meta["type"] = "image"
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
