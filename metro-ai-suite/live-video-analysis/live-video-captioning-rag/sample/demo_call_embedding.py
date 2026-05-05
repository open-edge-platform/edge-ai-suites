#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Standalone demo client for the /api/embeddings endpoint.

What this script does:
1. Downloads a sample image from the edge-ai-libraries repository.
2. Converts the image bytes into a base64 string.
3. Sends the payload to the embeddings endpoint so the backend can store
   the generated embedding in VDMS.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_IMAGE_URL = (
    "https://github.com/open-edge-platform/edge-ai-libraries/blob/main/"
    "microservices/dlstreamer-pipeline-server/resources/images/classroom.jpg?raw=1"
)
DEFAULT_EMBEDDINGS_URL = "http://localhost:4172/api/embeddings"


def download_image_bytes(image_url: str, timeout: int = 30) -> bytes:
    """Fetch image bytes from a remote URL."""
    request = Request(
        image_url,
        headers={"User-Agent": "embedding-demo-client/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def image_bytes_to_base64(image_bytes: bytes) -> str:
    """Convert binary image content to a UTF-8 base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def build_mock_metadata() -> dict[str, Any]:
    """Create metadata with the required preview and mocked fields."""
    caption = (
        "The image shows five people in a classroom with blue chairs and "
        "white desks, with four seated at desks and one standing in the "
        "middle, while daylight enters from large windows along one wall."
    )
    return {
        # "result" is the caption text used by the embedding service to
        # generate and store the vector in VDMS.
        "result": caption,
        "timestamp": 2754121008,
        "timestamp_seconds": 2.75,
        "resolution": {
          "height": 1080,
          "width": 1920
        },
        "frame_id": 101,
        "img_format": "BGR",
    }


def post_embedding(
    embeddings_url: str,
    image_data_b64: str,
    metadata: dict[str, Any],
    timeout: int = 60,
) -> dict[str, Any]:
    """Send embedding request and return JSON response."""
    payload = {
        "image_data": image_data_b64,
        "metadata": metadata,
    }

    request = Request(
        embeddings_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw_response": body}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo client for /api/embeddings that stores an embedding in VDMS."
    )
    parser.add_argument(
        "--embeddings-url",
        default=DEFAULT_EMBEDDINGS_URL,
        help=f"Embeddings endpoint URL (default: {DEFAULT_EMBEDDINGS_URL})",
    )
    parser.add_argument(
        "--image-url",
        default=DEFAULT_IMAGE_URL,
        help="Image URL to download and encode as base64.",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=30,
        help="Timeout in seconds for image download (default: 30).",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=60,
        help="Timeout in seconds for embedding API request (default: 60).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        print(f"Downloading image from: {args.image_url}")
        image_bytes = download_image_bytes(args.image_url, timeout=args.download_timeout)
        image_data_b64 = image_bytes_to_base64(image_bytes)

        metadata = build_mock_metadata()
        print(f"Constructed metadata for embedding request: {json.dumps(metadata, indent=2)}")
        print(f"Posting embedding request to: {args.embeddings_url}")

        response = post_embedding(
            args.embeddings_url,
            image_data_b64,
            metadata,
            timeout=args.request_timeout,
        )

        print("Embedding API response:")
        print(json.dumps(response, indent=2))
        return 0

    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {details}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())