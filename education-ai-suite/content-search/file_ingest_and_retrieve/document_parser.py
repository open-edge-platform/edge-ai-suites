import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode
from llama_index.readers.file import UnstructuredReader
from unstructured.partition.docx import register_picture_partitioner

from file_ingest_and_retrieve.utils import DocxParagraphPicturePartitioner, ensure_directory, is_supported_file

logger = logging.getLogger(__name__)

class DocumentParser:
    """
    Standalone document parser that extracts text and images from various file formats.
    Based on EdgeCraftRAG's UnstructedNodeParser.

    Supported formats: TXT, PDF, DOCX, DOC, PPTX, PPT, XLSX, HTML, XML, MD, etc.

    Features:
    - High-resolution PDF parsing with OCR
    - Image extraction from PDFs and DOCX files
    - Multi-language OCR support (English, Chinese Simplified, Chinese Traditional)
    - Configurable chunking with overlap
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
    ):
        """
        Initialize the document parser.

        Args:
            chunk_size: Maximum characters per chunk (default: 250)
            chunk_overlap: Characters overlap between chunks (default: 50)
            extract_images: Whether to extract images from PDFs (default: True)
            image_output_dir: Directory to save extracted images (default: './extracted_images')
            ocr_languages: List of OCR languages (default: ['eng', 'chi_sim', 'chi'])
            use_hi_res_strategy: Use high-resolution parsing (slower but more accurate)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.extract_images = extract_images
        self.image_output_dir = ensure_directory(image_output_dir)
        self.ocr_languages = ocr_languages or ["eng", "chi_sim", "chi"]
        self.use_hi_res_strategy = use_hi_res_strategy
        self.reader = UnstructuredReader()

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

        register_picture_partitioner(DocxParagraphPicturePartitioner)

        unstructured_kwargs = {
            "strategy": "hi_res" if self.use_hi_res_strategy else "fast",
            "chunking_strategy": "basic",
            "overlap_all": True,
            "max_characters": self.chunk_size,
            "overlap": self.chunk_overlap,
        }

        if Path(file_path).suffix.lower() == ".pdf":
            unstructured_kwargs.update(
                {
                    "extract_images_in_pdf": self.extract_images,
                    "extract_image_block_types": ["Image"],
                    "extract_image_block_output_dir": self.image_output_dir,
                    "languages": self.ocr_languages,
                }
            )

        try:
            nodes = self.reader.load_data(
                file=file_path,
                unstructured_kwargs=unstructured_kwargs,
                split_documents=True,
                document_kwargs={
                    "excluded_embed_metadata_keys": self.excluded_embed_metadata_keys,
                    "excluded_llm_metadata_keys": self.excluded_llm_metadata_keys,
                },
            )
            return nodes
        except Exception as e:
            raise RuntimeError(f"Failed to parse {file_path}: {str(e)}")

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
                    print(f"Skipping duplicate: {file_path}")
                    continue
                processed_paths.add(abs_path)

            try:
                print(f"Parsing: {file_path}")
                nodes = self.parse_file(file_path)
                all_nodes.extend(nodes)
                print(f"  ✓ Extracted {len(nodes)} chunks")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

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

        file_paths = []
        path_obj = Path(directory_path)

        if file_patterns:
            for pattern in file_patterns:
                if recursive:
                    file_paths.extend(path_obj.rglob(pattern))
                else:
                    file_paths.extend(path_obj.glob(pattern))
        else:
            if recursive:
                all_files = path_obj.rglob("*")
            else:
                all_files = path_obj.glob("*")

            file_paths = [f for f in all_files if f.is_file() and is_supported_file(str(f))]

        file_path_strs = [str(f) for f in file_paths]
        print(f"Found {len(file_path_strs)} files to parse")

        return self.parse_files(file_path_strs)

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
        nodes = splitter.get_nodes_from_documents([doc])
        return nodes

    def get_stats(self, nodes: List[BaseNode]) -> Dict[str, Any]:
        """
        Get statistics about parsed nodes.

        Args:
            nodes: List of parsed nodes

        Returns:
            Dictionary with statistics
        """
        total_chars = sum(len(node.get_content()) for node in nodes)
        avg_chunk_size = total_chars / len(nodes) if nodes else 0

        return {
            "total_nodes": len(nodes),
            "total_characters": total_chars,
            "average_chunk_size": avg_chunk_size,
            "unique_files": len(set(node.metadata.get("file_path", "") for node in nodes if node.metadata)),
        }

    def _is_libreoffice_available(self) -> bool:
        """Check if LibreOffice soffice command is available"""
        import shutil

        return shutil.which("soffice") is not None
