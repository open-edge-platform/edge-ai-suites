#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FileValidator:
    """Centralized file validation for uploads"""

    # File size limits (in MB)
    DOCUMENT_MAX_MB = int(os.environ.get("DOCUMENT_MAX_MB", "100"))
    VIDEO_MAX_MB = int(os.environ.get("VIDEO_MAX_MB", "1024"))

    # Video content type prefix and extensions
    VIDEO_CONTENT_PREFIX = "video/"
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

    # Expected content types for common extensions
    EXTENSION_TO_CONTENT_TYPE = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    # Magic numbers (file signatures) for validation
    MAGIC_NUMBERS = {
        ".pdf": [b"%PDF"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".docx": [b"PK\x03\x04"],
        ".pptx": [b"PK\x03\x04"],
        ".xlsx": [b"PK\x03\x04"],
        ".zip": [b"PK\x03\x04"],
        ".mp4": [b"\x00\x00\x00\x18ftypmp4", b"\x00\x00\x00\x1cftypmp42", b"\x00\x00\x00\x20ftypisom"],
        ".avi": [b"RIFF"],
        ".mov": [b"\x00\x00\x00\x14ftyp", b"\x00\x00\x00\x18ftyp", b"\x00\x00\x00\x1cftyp", b"\x00\x00\x00\x20ftyp"],
        ".mkv": [b"\x1a\x45\xdf\xa3"],
    }

    @staticmethod
    def get_max_size_bytes(content_type: Optional[str], filename: Optional[str]) -> int:
        """Get maximum allowed file size based on content type and filename"""
        ctype = (content_type or "").lower()
        if ctype.startswith(FileValidator.VIDEO_CONTENT_PREFIX):
            return FileValidator.VIDEO_MAX_MB * 1024 * 1024

        name = (filename or "").lower()
        if any(name.endswith(ext) for ext in FileValidator.VIDEO_EXTENSIONS):
            return FileValidator.VIDEO_MAX_MB * 1024 * 1024

        return FileValidator.DOCUMENT_MAX_MB * 1024 * 1024

    @staticmethod
    def validate_basic_file(
        filename: Optional[str],
        content_type: Optional[str],
        file_size: Optional[int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate basic file properties before upload
        Returns: (is_valid, error_message)
        """
        if not filename:
            return False, "Filename is required"

        if file_size is not None and file_size == 0:
            return False, "File is empty (0 bytes)"

        name_lower = filename.lower()
        ext = None
        for possible_ext in FileValidator.EXTENSION_TO_CONTENT_TYPE.keys():
            if name_lower.endswith(possible_ext):
                ext = possible_ext
                break

        if not ext:
            logger.warning(f"Unknown file extension for: {filename}")
            return True, None

        if not content_type:
            return True, None

        expected_type = FileValidator.EXTENSION_TO_CONTENT_TYPE.get(ext)
        actual_type = content_type.lower()

        if expected_type and not actual_type.startswith(expected_type.split('/')[0]):
            error_msg = f"File extension mismatch: {filename} has extension {ext} but content-type is {content_type}"
            logger.warning(error_msg)
            return False, error_msg

        return True, None

    @staticmethod
    def validate_file_content(
        first_chunk: bytes,
        filename: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate file content by checking magic number (file signature)
        Returns: (is_valid, error_message)
        """
        if not filename or not first_chunk:
            return True, None

        name_lower = filename.lower()
        ext = None
        for possible_ext in FileValidator.MAGIC_NUMBERS.keys():
            if name_lower.endswith(possible_ext):
                ext = possible_ext
                break

        if not ext:
            return True, None

        expected_signatures = FileValidator.MAGIC_NUMBERS.get(ext, [])
        if not expected_signatures:
            return True, None

        for signature in expected_signatures:
            if first_chunk.startswith(signature):
                return True, None

        error_msg = f"File content mismatch: {filename} has extension {ext} but content does not match expected file signature"
        logger.warning(error_msg)
        return False, error_msg


file_validator = FileValidator()
