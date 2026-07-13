import logging
import os


def setup_logger() -> None:
    level_name = os.getenv("SMART_KIOSK_RAG_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
