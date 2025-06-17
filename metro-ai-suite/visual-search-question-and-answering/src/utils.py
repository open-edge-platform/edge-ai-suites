# Copyright 2018-2021 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# some utils adopted from: https://github.com/streamlit/streamlit/blob/develop/lib/streamlit/runtime/memory_media_file_storage.py#L104

import imghdr
import io
import mimetypes
from typing import cast
from urllib.parse import urlparse

import numpy as np
from PIL import Image, ImageFile
import hashlib
import base64


# This constant is related to the frontend maximum content width specified
# in App.jsx main container
# 730 is the max width of element-container in the frontend, and 2x is for high
# DPI.
MAXIMUM_CONTENT_WIDTH = 2 * 730


def _image_has_alpha_channel(image):
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        return True
    else:
        return False


def _format_from_image_type(image, output_format):
    output_format = output_format.upper()
    if output_format == "JPEG" or output_format == "PNG":
        return output_format

    # We are forgiving on the spelling of JPEG
    if output_format == "JPG":
        return "JPEG"

    if _image_has_alpha_channel(image):
        return "PNG"

    return "JPEG"


def _PIL_to_bytes(image, format="JPEG", quality=100):
    tmp = io.BytesIO()

    # User must have specified JPEG, so we must convert it
    if format == "JPEG" and _image_has_alpha_channel(image):
        image = image.convert("RGB")

    image.save(tmp, format=format, quality=quality)

    return tmp.getvalue()


def _BytesIO_to_bytes(data):
    data.seek(0)
    return data.getvalue()


def _normalize_to_bytes(data, width, output_format):
    image = Image.open(io.BytesIO(data))
    actual_width, actual_height = image.size
    format = _format_from_image_type(image, output_format)
    if output_format.lower() == "auto":
        ext = imghdr.what(None, data)
        mimetype = mimetypes.guess_type("image.%s" % ext)[0]
    else:
        mimetype = "image/" + format.lower()

    if width < 0 and actual_width > MAXIMUM_CONTENT_WIDTH:
        width = MAXIMUM_CONTENT_WIDTH

    if width > 0 and actual_width > width:
        new_height = int(1.0 * actual_height * width / actual_width)
        image = image.resize((width, new_height), resample=Image.BILINEAR)
        data = _PIL_to_bytes(image, format=format, quality=90)
        mimetype = "image/" + format.lower()

    return data, mimetype

def generate_image_hash(image, mimetype):
    # Generate a SHA-256 hash
    return generate_sha224(image, mimetype) 

def generate_sha224(image, mimetype):
    filehash = hashlib.new("sha224", usedforsecurity=False)
    filehash.update(image)
    filehash.update(bytes(mimetype.encode()))
    return filehash.hexdigest()  # SHA-224 hash


def image_to_url(
    image, output_format, width=MAXIMUM_CONTENT_WIDTH
):
    # PIL Images
    if isinstance(image, ImageFile.ImageFile) or isinstance(image, Image.Image):
        format = _format_from_image_type(image, output_format)
        data = _PIL_to_bytes(image, format)

    # BytesIO
    # Note: This doesn't support SVG. We could convert to png (cairosvg.svg2png)
    # or just decode BytesIO to string and handle that way.
    elif isinstance(image, io.BytesIO):
        data = _BytesIO_to_bytes(image)

    # Strings
    elif isinstance(image, str):
        # If it's a url, then set the protobuf and continue
        try:
            p = urlparse(image)
            if p.scheme:
                return image
        except UnicodeDecodeError:
            pass

    # Assume input in bytes.
    else:
        data = image

    (data, mimetype) = _normalize_to_bytes(data, width, output_format)
    file_id = generate_image_hash(data, mimetype)
    return file_id, mimetype

def video_to_url(
    video, output_format
):
    data = video

    # (data, mimetype) = _normalize_to_bytes(data, MAXIMUM_CONTENT_WIDTH, output_format)
    mimetype = f"video/{output_format.lower()}"
    file_id = generate_image_hash(data, mimetype)
    return file_id, mimetype