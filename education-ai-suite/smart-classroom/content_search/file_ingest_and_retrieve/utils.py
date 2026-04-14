# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import uuid
import numpy as np
from pathlib import Path
import base64
from io import BytesIO
from typing import Iterator

from PIL import Image as PILImage
from unstructured.documents.elements import ElementMetadata, Image
from unstructured.partition.docx import DocxPartitionerOptions
from docx.text.paragraph import Paragraph


def normalize(arr, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]):
    arr = arr.astype(np.float32)
    arr /= 255.0
    for i in range(3):
        arr[..., i] = (arr[..., i] - mean[i]) / std[i]
    return arr


def preprocess_image(image, shape=[224, 224]):
    img = image.resize(shape, PILImage.Resampling.NEAREST)
    img = normalize(np.asarray(img))
    return img.transpose(2, 0, 1)


def generate_unique_id():
    return uuid.uuid4().int & 0x7FFFFFFFFFFFFFFF


def encode_image_to_base64(image, format="PNG", add_header=False):
    """
    Encode an image to a base64 string.

    Args:
        image: PIL.Image.Image, path-like, or numpy ndarray (H,W,C in RGB).
        format: Output image format (e.g., "PNG", "JPEG").
        add_header: If True, prepend data URI header.

    Returns:
        Base64-encoded string (optionally with data URI header).
    """
    if isinstance(image, (str, Path)):
        img = PILImage.open(image).convert("RGB")
    elif isinstance(image, PILImage.Image):
        img = image.convert("RGB")
    elif isinstance(image, np.ndarray):
        if image.dtype != np.uint8:
            # Attempt to bring into 0-255 range if float
            if np.issubdtype(image.dtype, np.floating):
                arr = np.clip(image, 0, 1) if image.max() <= 1.0 else image
                image = (arr * (255 if arr.max() <= 1.0 else 1)).astype(np.uint8)
            else:
                image = image.astype(np.uint8)
        if image.ndim == 2:
            img = PILImage.fromarray(image, mode="L").convert("RGB")
        else:
            img = PILImage.fromarray(image[..., :3])
    else:
        raise TypeError("Unsupported image type for base64 encoding.")

    buffer = BytesIO()
    img.save(buffer, format=format)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    if add_header:
        return f"data:image/{format.lower()};base64,{encoded}"
    return encoded


class DocxParagraphPicturePartitioner:
    """
    Custom partitioner to extract images from DOCX paragraphs.
    This preserves images that might be lost with standard parsing.
    """

    @classmethod
    def iter_elements(cls, paragraph: Paragraph, opts: DocxPartitionerOptions) -> Iterator[Image]:
        if paragraph is None:
            return
        imgs = paragraph._element.xpath(".//pic:pic")
        if imgs:
            img_output_dir = "extracted_images"
            os.makedirs(img_output_dir, exist_ok=True)
            for img in imgs:
                try:
                    embed = img.xpath(".//a:blip/@r:embed")[0]
                    related_part = opts.document.part.related_parts[embed]
                    image_blob = related_part.blob
                    image = PILImage.open(BytesIO(image_blob))
                    image_filename = f"{embed}_{related_part.sha1}.png"
                    image_path = os.path.join(img_output_dir, image_filename)
                    image.save(image_path)
                    element_metadata = ElementMetadata(image_path=image_path)
                    yield Image(text="IMAGE", metadata=element_metadata)
                except Exception as e:
                    print(f"Warning: Failed to extract image from DOCX: {e}")
                    continue


def ensure_directory(path: str) -> str:
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def get_file_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower().lstrip(".")


def is_supported_file(file_path: str) -> bool:
    supported_extensions = {
        "txt", "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
        "html", "htm", "xml", "md", "rst",
    }
    return get_file_extension(file_path) in supported_extensions
