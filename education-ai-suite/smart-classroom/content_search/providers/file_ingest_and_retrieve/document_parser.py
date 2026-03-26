# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.schema import BaseNode
from llama_index.readers.file import UnstructuredReader
from unstructured.partition.docx import register_picture_partitioner

from content_search.file_ingest_and_retrieve.utils import DocxParagraphPicturePartitioner, ensure_directory, is_supported_file

logger = logging.getLogger(__name__)

# Sentence boundary pattern for both Chinese and English.
# Splits after: 。！？；…… \n\n  or  . ! ? followed by whitespace
_SENT_SPLIT_RE = re.compile(r'(?<=[。！？；…\n])|(?<=[.!?])(?=\s)')


def _bilingual_sentence_splitter(text: str) -> List[str]:
    """Split text into sentences supporting both Chinese and English."""
    parts = _SENT_SPLIT_RE.split(text)
    sentences: List[str] = []
    buf = ""
    for part in parts:
        buf += part
        if len(buf.strip()) >= 10:
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
    - OCR for PDFs: enabled when use_hi_res_strategy=True (hi_res renders each page as image for Tesseract OCR);
      fast strategy only uses OCR as fallback for image-only pages
    - Multi-language OCR support (English, Chinese Simplified, Chinese Traditional) via ocr_languages parameter
    - Image extraction from PDFs (extract_images=True) and DOCX files: saves image files to disk only,
      no further OCR or text recognition is performed on extracted images
    - Deduplication of processed files
    """

    def __init__(
        self,
        chunk_size: int = 250,
        chunk_overlap: int = 50,
        extract_images: bool = True,
        image_output_dir: str = "./extracted_images",
        ocr_languages: Optional[List[str]] = None,
        use_hi_res_strategy: bool = True,
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
            extract_images: Whether to extract images from PDFs (default: True)
            image_output_dir: Directory to save extracted images (default: './extracted_images')
            ocr_languages: List of OCR languages (default: ['eng', 'chi_sim', 'chi'])
            use_hi_res_strategy: Use high-resolution parsing (slower but more accurate)
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
        self.image_output_dir = ensure_directory(image_output_dir)
        self.ocr_languages = ocr_languages or ["eng", "chi_sim", "chi"]
        self.use_hi_res_strategy = use_hi_res_strategy
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
            logger.info("DocumentParser: using SemanticSplitterNodeParser.")
        else:
            self.splitter = None  # unstructured basic chunking will be used
            logger.info("DocumentParser: using unstructured basic chunking.")

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
                f"Supported: txt, pdf, docx, pptx, xlsx, html, htm, xml, md, rst"
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
            register_picture_partitioner(DocxParagraphPicturePartitioner)

        unstructured_kwargs = {
            "strategy": "hi_res" if self.use_hi_res_strategy else "fast",
        }

        if self.splitter is None:
            unstructured_kwargs.update({
                "chunking_strategy": "basic",
                "overlap_all": True,
                "max_characters": self.chunk_size,
                "overlap": self.chunk_overlap,
            })

        if ext == ".pdf":
            unstructured_kwargs.update({
                "extract_images_in_pdf": self.extract_images,
                "extract_image_block_types": ["Image"],
                "extract_image_block_output_dir": self.image_output_dir,
                "languages": self.ocr_languages,
            })

        try:
            nodes = self.reader.load_data(
                file=file_path,
                unstructured_kwargs=unstructured_kwargs,
                split_documents=self.splitter is None,
                document_kwargs={
                    "excluded_embed_metadata_keys": self.excluded_embed_metadata_keys,
                    "excluded_llm_metadata_keys": self.excluded_llm_metadata_keys,
                },
            )
            if self.splitter is not None:
                # reader returned a single Document; attach file_path meta and semantic-split
                nodes[0].metadata["file_path"] = file_path
                logger.info(f"SemanticSplitter input: {len(nodes[0].get_content())} chars")
                nodes = self.splitter.get_nodes_from_documents(nodes)
                for _n in nodes:
                    _n.set_content(re.sub(r'\s*\n+\s*', ' ', _n.get_content()).strip())
                nodes = self._merge_short_chunks(nodes)
                logger.info(f"SemanticSplitter: {file_path} → {len(nodes)} chunks")
            return nodes
        except Exception as e:
            raise RuntimeError(f"Failed to parse {file_path}: {str(e)}")

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
        logger.info(f"Semantic split: {len(nodes)} → {len(merged)} chunks after merging short ones.")
        return merged

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
