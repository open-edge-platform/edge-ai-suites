#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FileValidator:
    DOCUMENT_MAX_MB = int(os.environ.get("DOCUMENT_MAX_MB", "100"))
    VIDEO_MAX_MB = int(os.environ.get("VIDEO_MAX_MB", "1024"))

    VIDEO_CONTENT_PREFIX = "video/"
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

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

    MAGIC_NUMBERS = {
        ".pdf": [b"%PDF"],
        ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        ".ppt": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        ".docx": [b"PK\x03\x04"],
        ".pptx": [b"PK\x03\x04"],
        ".xlsx": [b"PK\x03\x04"],
        ".zip": [b"PK\x03\x04"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        # MP4 and MOV use ftyp-based validation in validate_file_content()
        ".avi": [b"RIFF"],
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
        if not filename or not first_chunk:
            return True, None

        name_lower = filename.lower()

        # MP4/MOV: check for 'ftyp' signature at bytes 4-8
        if name_lower.endswith(('.mp4', '.mov')):
            if len(first_chunk) >= 8:
                if first_chunk[4:8] == b'ftyp':
                    return True, None
                else:
                    error_msg = f"File content mismatch: {filename} has MP4/MOV extension but missing 'ftyp' signature (found: {first_chunk[4:8]})"
                    logger.warning(error_msg)
                    return False, error_msg
            else:
                error_msg = f"File content mismatch: {filename} is too small to be a valid MP4/MOV file"
                logger.warning(error_msg)
                return False, error_msg
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

    @staticmethod
    def validate_file_integrity(file_path: str) -> Tuple[bool, Optional[str]]:
        if not os.path.exists(file_path):
            return False, "File does not exist"

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == '.pdf':
                try:
                    import pypdf
                except ImportError:
                    logger.warning("pypdf not installed, skipping PDF integrity check")
                    return True, None

                try:
                    with open(file_path, 'rb') as f:
                        reader = pypdf.PdfReader(f)
                        page_count = len(reader.pages)
                        if page_count == 0:
                            return False, "PDF has no readable pages"
                    logger.info(f"PDF validation passed: {page_count} pages")
                    return True, None
                except Exception as e:
                    error_msg = f"PDF file is corrupted or unreadable: {str(e)}"
                    logger.error(error_msg)
                    return False, error_msg

            elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
                try:
                    import cv2
                except ImportError:
                    logger.warning("cv2 not installed, skipping video integrity check")
                    return True, None

                try:
                    cap = cv2.VideoCapture(file_path)
                    if not cap.isOpened():
                        return False, "Video file is corrupted or unreadable"

                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if frame_count <= 0:
                        cap.release()
                        return False, "Video file has no readable frames"

                    cap.release()
                    logger.info(f"Video validation passed: {frame_count} frames")
                    return True, None
                except Exception as e:
                    error_msg = f"Video validation failed: {str(e)}"
                    logger.error(error_msg)
                    return False, error_msg

        except Exception as e:
            error_msg = f"File integrity validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        return True, None


file_validator = FileValidator()
