"""MinIO wrapper utilities for this repo.

This package is intentionally named `content_search_minio` to avoid colliding with
the third-party `minio` SDK package.
"""

from .minio_client import MinioStore

__all__ = ["MinioStore"]
