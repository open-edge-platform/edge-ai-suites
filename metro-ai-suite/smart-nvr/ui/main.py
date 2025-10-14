# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Main entry point for NVR Event Router UI.
"""

import logging
import os
import sys

# Make script executable both as module (python -m ui.main) and as a file (python main.py)
# by ensuring parent directory is on sys.path and attempting absolute then relative imports.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:  # Preferred absolute imports when package context is established
    from interface.interface import create_ui, initialize_app, stop_event_updates  # type: ignore
except ImportError:
    # Fallback to relative (works when executed with -m) or if layout differs
    from .interface.interface import create_ui, initialize_app, stop_event_updates  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("vms_event_router_ui.log")],
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("=== Starting NVR Event Router UI ===")

    try:
        # Initialize application
        initialize_app()

        # Create and launch UI
        ui = create_ui()
        ui.launch(server_name="0.0.0.0", show_error=True, favicon_path=None)

    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)

    finally:
        logger.info("Application shutdown initiated")
        stop_event_updates()
        logger.info("=== Application shutdown complete ===")
