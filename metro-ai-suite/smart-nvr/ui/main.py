# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Main entry point for NVR Event Router UI.
"""

import logging
from interface.interface import create_ui
from interface.interface import initialize_app, stop_event_updates, cleanup_temp_files

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
