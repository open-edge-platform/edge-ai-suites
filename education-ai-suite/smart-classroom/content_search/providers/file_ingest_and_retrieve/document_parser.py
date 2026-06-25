# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

import fitz
import httpx
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.schema import BaseNode, TextNode
from llama_index.readers.file import UnstructuredReader
from unstructured.partition.auto import partition
from unstructured.partition.docx import register_picture_partitioner

# ---------------------------------------------------------------------------
# Monkey-patch: llama-index-readers-file 0.6.0 passes both deprecated
# ``doc_id`` AND ``id_`` to Document/TextNode constructors, which triggers
# "'doc_id' is deprecated and 'id_' will be used instead" on every node.
# Remove the redundant ``doc_id`` kwarg from __init__ until the upstream
# package drops it.
# ---------------------------------------------------------------------------
_orig_document_init = Document.__init__
_orig_textnode_init = TextNode.__init__


def _patched_document_init(self, **data):
    data.pop("doc_id", None)
    _orig_document_init(self, **data)


def _patched_textnode_init(self, **data):
    data.pop("doc_id", None)
    _orig_textnode_init(self, **data)


Document.__init__ = _patched_document_init
TextNode.__init__ = _patched_textnode_init

from providers.file_ingest_and_retrieve.utils import DocxParagraphPicturePartitioner, ensure_directory, is_supported_file

logger = logging.getLogger(__name__)

# Sentence boundary pattern for both Chinese and English.
# Splits after: 。！？；…… \n\n  or  . ! ? followed by whitespace
_SENT_SPLIT_RE = re.compile(r'(?<=[。！？；…\n])|(?<=[.!?])(?=\s)')

# Matches a lowercase letter directly followed by an uppercase letter (e.g. "systemsAre")
_GLUED_LOWER_UPPER_RE = re.compile(r'([a-z])([A-Z])')
# Matches a letter directly followed by a CJK character or vice versa
_GLUED_CJK_RE = re.compile(r'([a-zA-Z])([一-鿿])')
_GLUED_CJK_REV_RE = re.compile(r'([一-鿿])([a-zA-Z])')


def _clean_text(text: str) -> str:
    """Collapse newlines to spaces and insert spaces between glued words."""
    text = re.sub(r'\s*\n+\s*', ' ', text)
    text = _GLUED_LOWER_UPPER_RE.sub(r'\1 \2', text)
    text = _GLUED_CJK_RE.sub(r'\1 \2', text)
    text = _GLUED_CJK_REV_RE.sub(r'\1 \2', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def _bilingual_sentence_splitter(text: str) -> List[str]:
    """Split text into sentences supporting both Chinese and English."""
    parts = _SENT_SPLIT_RE.split(text)
    sentences: List[str] = []
    buf = ""
    for part in parts:
        buf += part
        if len(buf.strip()) >= 10:
            if buf and not buf[-1].isspace():
                buf += " "
            sentences.append(buf)
            buf = ""
    if buf.strip():
        if sentences:
            sentences[-1] += buf
        else:
            sentences.append(buf)
    return sentences if sentences else [text]


class DocumentParser:
    """
    Standalone document parser that extracts text and images from various file formats.
    Based on EdgeCraftRAG's UnstructedNodeParser.

    Supported formats: TXT, PDF, DOCX, DOC, PPTX, PPT, XLSX, HTML, XML, MD, etc.

    Features:
    - Two chunking modes: fixed-size (basic) chunking by default; semantic chunking when embed_model is provided
    - Always uses "fast" strategy for PDF text extraction to preserve layout and speed
    - Image extraction from PDFs: extracted images are sent to PaddleOCR service for text recognition,
      and each image's OCR text becomes an independent searchable node
    - Image extraction from DOCX files: saves image files to disk
    - Deduplication of processed files
    """

    def __init__(
        self,
        chunk_size: int = 250,
        chunk_overlap: int = 50,
        extract_images: bool = True,
        image_output_dir: Optional[str] = None,
        ocr_service_url: Optional[str] = None,
        embed_model=None,
        semantic_buffer_size: int = 2,
        semantic_breakpoint_percentile: int = 85,
        semantic_min_chunk_size: int = 200,
    ):
        """
        Initialize the document parser.

        Args:
            chunk_size: Maximum characters per chunk (default: 250). Used only when embed_model is None.
            chunk_overlap: Characters overlap between chunks (default: 50). Used only when embed_model is None.
            extract_images: Whether to extract and OCR images from PDFs (default: True)
            image_output_dir: Directory to save extracted images (default: './extracted_images')
            ocr_service_url: URL of the PaddleOCR service (default: env OCR_SERVICE_URL or http://127.0.0.1:8000)
            embed_model: LlamaIndex-compatible embedding model for semantic chunking.
                         If provided, SemanticSplitterNodeParser is used instead of basic chunking.
            semantic_buffer_size: Number of surrounding sentences to compare when detecting
                                  semantic boundaries (default: 2).
            semantic_breakpoint_percentile: Percentile threshold for breakpoint detection (default: 85).
                                            Higher = fewer, larger chunks.
            semantic_min_chunk_size: Minimum characters per chunk when using semantic splitting.
                                     Chunks shorter than this are merged into the next chunk (default: 400).
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.extract_images = extract_images
        _default_img_dir = os.path.join(os.getcwd(), "logs", "extracted_images")
        self.image_output_dir = image_output_dir or _default_img_dir
        if extract_images:
            ensure_directory(self.image_output_dir)
        self.ocr_service_url = ocr_service_url or os.getenv("OCR_SERVICE_URL", "http://127.0.0.1:8000")
        self.semantic_min_chunk_size = semantic_min_chunk_size
        self.reader = UnstructuredReader()

        # Splitter: semantic or basic fixed-size
        if embed_model is not None:
            self.splitter = SemanticSplitterNodeParser(
                embed_model=embed_model,
                buffer_size=semantic_buffer_size,
                breakpoint_percentile_threshold=semantic_breakpoint_percentile,
                sentence_splitter=_bilingual_sentence_splitter,
            )
            logger.info("Using SemanticSplitterNodeParser.")
        else:
            self.splitter = None  # unstructured basic chunking will be used
            logger.info("Using unstructured basic chunking.")

        self.excluded_embed_metadata_keys = [
            "file_size",
            "creation_date",
            "last_modified_date",
            "last_accessed_date",
            "orig_elements",
        ]
        self.excluded_llm_metadata_keys = ["orig_elements"]

    def parse_file(self, file_path: str) -> List[BaseNode]:
        """
        Parse a single file and return chunks as nodes.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of BaseNode objects containing chunked content

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not is_supported_file(file_path):
            raise ValueError(
                f"Unsupported file format: {Path(file_path).suffix}. "
                f"Supported: txt, pdf, docx, pptx, xlsx, html, htm, xml, md"
            )

        # Check for legacy formats that need LibreOffice
        ext = Path(file_path).suffix.lower()
        legacy_formats = [".doc", ".ppt", ".xls"]

        if ext in legacy_formats:
            if not self._is_libreoffice_available():
                raise RuntimeError(
                    f"Legacy format {ext} requires LibreOffice. "
                    f"Please install LibreOffice or convert to modern format (.docx, .pptx, .xlsx)"
                )

        if ext == ".docx":
            DocxParagraphPicturePartitioner.output_dir = self.image_output_dir
            register_picture_partitioner(DocxParagraphPicturePartitioner)

        unstructured_kwargs = {
            "strategy": "fast",
        }

        if self.splitter is None:
            unstructured_kwargs.update({
                "chunking_strategy": "basic",
                "overlap_all": True,
                "max_characters": self.chunk_size,
                "overlap": self.chunk_overlap,
            })

        try:
            if self.splitter is not None:
                nodes = self._parse_file_semantic(file_path, unstructured_kwargs)
            else:
                nodes = self.reader.load_data(
                    file=file_path,
                    unstructured_kwargs=unstructured_kwargs,
                    split_documents=True,
                    document_kwargs={
                        "excluded_embed_metadata_keys": self.excluded_embed_metadata_keys,
                        "excluded_llm_metadata_keys": self.excluded_llm_metadata_keys,
                    },
                )
            for _n in nodes:
                _n.set_content(_clean_text(_n.get_content()))
                _n.metadata.pop("filename", None)
                _n.metadata.pop("file_directory", None)

            if ext == ".pdf":
                if not self.extract_images:
                    logger.info(f"Image extraction disabled for DocumentParser.")
                elif not self._is_ocr_enabled():
                    pass
                else:
                    file_hash = hashlib.md5(os.path.abspath(file_path).encode()).hexdigest()[:12]
                    file_image_dir = os.path.join(self.image_output_dir, file_hash)
                    ensure_directory(file_image_dir)
                    self._extract_pdf_images(file_path, file_image_dir)
                    image_count = len([f for f in os.listdir(file_image_dir) if not f.startswith('.')])
                    logger.info(f"{image_count} image(s) extracted to {file_image_dir}")
                    if image_count > 0:
                        image_ocr_nodes = self._ocr_extracted_images(file_path, file_image_dir)
                        logger.info(f"OCR produced {len(image_ocr_nodes)} text node(s)")
                        nodes.extend(image_ocr_nodes)
            return nodes
        except Exception as e:
            raise RuntimeError(f"Failed to parse {file_path}: {str(e)}")

    def _parse_file_semantic(self, file_path: str, unstructured_kwargs: dict) -> List[BaseNode]:
        """Semantic-split per page: partition → group elements by page → split each page."""

        elements = partition(filename=file_path, **unstructured_kwargs)
        if not elements:
            return []

        file_meta = {
            k: v for k, v in elements[0].metadata.to_dict().items()
            if k not in {"orig_elements", "page_number", "coordinates", "languages", "file_directory", "filename"}
               and isinstance(v, (str, int, float, type(None)))
        }
        file_meta["file_path"] = file_path

        pages: Dict[int, list] = {}
        for el in elements:
            pg = getattr(el.metadata, "page_number", None) or 1
            pages.setdefault(pg, []).append(el)

        all_nodes: List[BaseNode] = []
        for page_num in sorted(pages):
            page_elements = pages[page_num]
            text = " ".join(" ".join(str(el).split()) for el in page_elements)
            text = _clean_text(text)
            if not text.strip():
                continue

            doc = Document(
                text=text,
                metadata={**file_meta, "page_number": page_num},
                excluded_embed_metadata_keys=self.excluded_embed_metadata_keys,
                excluded_llm_metadata_keys=self.excluded_llm_metadata_keys,
            )
            page_nodes = self.splitter.get_nodes_from_documents([doc])
            for _n in page_nodes:
                _n.set_content(_clean_text(_n.get_content()))
                _n.metadata["page_number"] = page_num
                _n.metadata["file_path"] = file_path
            all_nodes.extend(page_nodes)

        all_nodes = self._merge_short_chunks(all_nodes)
        logger.info(f"SemanticSplitter: {file_path} → {len(all_nodes)} chunks across {len(pages)} pages")
        return all_nodes

    def _merge_short_chunks(self, nodes: List[BaseNode]) -> List[BaseNode]:
        """Merge chunks shorter than semantic_min_chunk_size into the following chunk."""
        if not nodes or self.semantic_min_chunk_size <= 0:
            return nodes
        merged = []
        carry_text = ""
        carry_meta = None
        for node in nodes:
            text = node.get_content()
            if carry_text:
                text = carry_text + " " + text
                node.set_content(text)
                if carry_meta:
                    node.metadata = {**carry_meta, **node.metadata}
                carry_text = ""
                carry_meta = None
            if len(text) < self.semantic_min_chunk_size:
                carry_text = text
                carry_meta = node.metadata
            else:
                merged.append(node)
        if carry_text:
            if merged:
                last = merged[-1]
                last.set_content(last.get_content() + " " + carry_text)
            else:
                nodes[-1].set_content(carry_text)
                merged.append(nodes[-1])
        logger.info(f"{len(nodes)} → {len(merged)} chunks after merging short ones.")
        return merged

    @staticmethod
    def _is_ocr_enabled() -> bool:
        enabled = os.getenv("OCR_ENABLED", "false").lower() in ("true", "1", "yes")
        if not enabled:
            logger.info("OCR is disabled (OCR_ENABLED env var). Skipping image text extraction.")
        return enabled

    @staticmethod
    def _extract_pdf_images(pdf_path: str, output_dir: str, min_size: int = 100) -> None:
        """Extract embedded images from a PDF using PyMuPDF, saving to output_dir.

        Filenames encode page number: page{N}_img{I}.png
        """
        doc = fitz.open(pdf_path)
        try:
            for page_num, page in enumerate(doc, start=1):
                for img_idx, img_info in enumerate(page.get_images(full=True)):
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    if width < min_size or height < min_size:
                        continue
                    img_bytes = base_image["image"]
                    img_ext = base_image.get("ext", "png")
                    filename = f"page{page_num}_img{img_idx}.{img_ext}"
                    with open(os.path.join(output_dir, filename), "wb") as f:
                        f.write(img_bytes)
        finally:
            doc.close()

    def _ocr_extracted_images(self, file_path: str, image_dir: str) -> List[BaseNode]:
        """Scan per-file image directory for extracted images and OCR each via PaddleOCR service."""
        if not os.path.isdir(image_dir):
            return []

        image_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")
        image_files = [
            f for f in os.listdir(image_dir)
            if f.lower().endswith(image_extensions)
        ]
        if not image_files:
            return []

        nodes: List[BaseNode] = []
        for img_file in sorted(image_files):
            img_path = os.path.join(image_dir, img_file)
            ocr_text = self._ocr_image_via_service(img_path)
            if not ocr_text.strip():
                continue

            page_num = self._extract_page_number(img_file)
            node = TextNode(
                text=_clean_text(ocr_text),
                metadata={
                    "file_path": file_path,
                    "page_number": page_num,
                    "source_type": "image_ocr",
                    "image_file": img_file,
                },
                excluded_embed_metadata_keys=self.excluded_embed_metadata_keys,
                excluded_llm_metadata_keys=self.excluded_llm_metadata_keys,
            )
            nodes.append(node)

        if not nodes and image_files:
            logger.warning(
                f"Found {len(image_files)} image(s) in {file_path} but OCR service returned no text. "
                f"Check that OCR is enabled (ocr.enabled: true in config.yaml) and the service is running at {self.ocr_service_url}"
            )
        return nodes

    def _ocr_image_via_service(self, image_path: str) -> str:
        """Call PaddleOCR service to extract text from an image file."""
        try:
            with httpx.Client(timeout=60.0) as client:
                with open(image_path, 'rb') as f:
                    resp = client.post(
                        f"{self.ocr_service_url}/ocr/extract-text",
                        files={'file': (Path(image_path).name, f, 'application/octet-stream')},
                        headers={'X-Session-ID': str(uuid.uuid4())},
                    )
            if resp.status_code != 200:
                logger.warning(f"OCR service returned {resp.status_code} for {image_path}")
                return ""
            result_file = resp.json().get("data", {}).get("result_file")
            if result_file and os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as tf:
                    return tf.read()
            if result_file and not os.path.isabs(result_file):
                alt_path = os.path.join("..", result_file)
                if os.path.exists(alt_path):
                    with open(alt_path, 'r', encoding='utf-8') as tf:
                        return tf.read()
            return ""
        except Exception as e:
            logger.warning(f"OCR service call failed for {image_path}: {e}")
            return ""

    @staticmethod
    def _extract_page_number(image_filename: str) -> int:
        """Extract page number from image filename (e.g. 'figure-page3-0.png' -> 3)."""
        match = re.search(r'page(\d+)', image_filename, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r'(\d+)', image_filename)
        if match:
            return int(match.group(1))
        return 1

    def parse_files(self, file_paths: List[str], deduplicate: bool = True) -> List[BaseNode]:
        """
        Parse multiple files and return all chunks as nodes.

        Args:
            file_paths: List of file paths to parse
            deduplicate: Skip duplicate file paths (default: True)

        Returns:
            Combined list of BaseNode objects from all files
        """
        all_nodes = []
        processed_paths = set()
        for file_path in file_paths:
            if deduplicate:
                abs_path = os.path.abspath(file_path)
                if abs_path in processed_paths:
                    continue
                processed_paths.add(abs_path)
            try:
                nodes = self.parse_file(file_path)
                all_nodes.extend(nodes)
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
        return all_nodes

    def parse_directory(
        self, directory_path: str, recursive: bool = True, file_patterns: Optional[List[str]] = None
    ) -> List[BaseNode]:
        """
        Parse all supported files in a directory.

        Args:
            directory_path: Path to directory
            recursive: Search subdirectories (default: True)
            file_patterns: List of file patterns to match (e.g., ['*.pdf', '*.docx'])

        Returns:
            Combined list of BaseNode objects from all files
        """
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"Not a directory: {directory_path}")
        path_obj = Path(directory_path)
        if file_patterns:
            file_paths = []
            for pattern in file_patterns:
                file_paths.extend(path_obj.rglob(pattern) if recursive else path_obj.glob(pattern))
        else:
            all_files = path_obj.rglob("*") if recursive else path_obj.glob("*")
            file_paths = [f for f in all_files if f.is_file() and is_supported_file(str(f))]
        return self.parse_files([str(f) for f in file_paths])

    def parse_with_simple_chunker(self, file_path: str) -> List[BaseNode]:
        """
        Alternative parsing method using LlamaIndex's SentenceSplitter.
        Faster but less accurate than unstructured parsing.

        Args:
            file_path: Path to file

        Returns:
            List of chunked nodes
        """
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        doc = Document(text=content, metadata={"file_path": file_path})
        splitter = SentenceSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        return splitter.get_nodes_from_documents([doc])

    def get_stats(self, nodes: List[BaseNode]) -> Dict[str, Any]:
        total_chars = sum(len(node.get_content()) for node in nodes)
        return {
            "total_nodes": len(nodes),
            "total_characters": total_chars,
            "average_chunk_size": total_chars / len(nodes) if nodes else 0,
            "unique_files": len(set(node.metadata.get("file_path", "") for node in nodes if node.metadata)),
        }

    def _is_libreoffice_available(self) -> bool:
        import shutil
        return shutil.which("soffice") is not None
