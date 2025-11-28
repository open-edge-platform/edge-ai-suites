# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Minimal settings + logger used by the directory watcher & upload pipeline.

This trims unrelated search/index/embedding configuration to reduce noise.
Extend cautiously if new watcher features require more settings.
"""

import logging
import os
from pydantic import Field
from dotenv import load_dotenv

try:  # Prefer pydantic-settings if present
    from pydantic_settings import BaseSettings  # type: ignore
except ImportError:  # Fallback
    from pydantic import BaseSettings  # type: ignore


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watcher")

env_path = os.path.join(os.path.dirname(__file__), "../../", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.debug(f"Loaded environment variables from {env_path}")


class Settings(BaseSettings):
    # Core watcher paths
    WATCH_DIRECTORY_CONTAINER_PATH: str = Field(default="/media/frigate/recordings", env="WATCH_DIRECTORY_CONTAINER_PATH")
    WATCH_DIRECTORY_CONTAINER_PATHS: str = Field(default="", env="WATCH_DIRECTORY_CONTAINER_PATHS")
    # Debounce + deletion behavior
    DEBOUNCE_TIME: int = Field(default=5, env="DEBOUNCE_TIME")
    DELETE_PROCESSED_FILES: bool = Field(default=False, env="DELETE_PROCESSED_FILES")
    WATCH_DIRECTORY_RECURSIVE: bool = Field(default=False, env="WATCH_DIRECTORY_RECURSIVE")
    # Upload target (Video Search / embeddings service)
    VIDEO_UPLOAD_ENDPOINT: str = Field(default="", env="VSS_SEARCH_IP")
    # Proxy control (trimmed to only what upload code references)
    no_proxy_env: str = Field(default="", env="no_proxy_env")


settings = Settings()
logger.debug(f"Active settings (trimmed): {settings.dict()}")


class ErrorMessages:
    WATCHER_LAST_UPDATED_ERROR = "Error in getting watcher last updated timestamp"