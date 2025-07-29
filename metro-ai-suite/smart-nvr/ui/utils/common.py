# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
import time
import tempfile
from config import logger


def cleanup_temp_files():
    try:
        temp_dir = tempfile.gettempdir()
        for f in os.listdir(temp_dir):
            path = os.path.join(temp_dir, f)
            if f.endswith(".mp4") and time.time() - os.path.getmtime(path) > 3600:
                os.remove(path)
                logger.info(f"Deleted: {path}")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
