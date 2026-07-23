import logging
from typing import Dict, List

from fastapi import APIRouter

from utils.config_loader import config

logger = logging.getLogger(__name__)

router = APIRouter()


class VideoAnalyticsFeature:

    id: str = "video_analytics"
    requires: List[str] = []
    depends_on: List[str] = []
    router: APIRouter = router

    def __init__(self) -> None:
        self._media_service = None
        self.front_enabled = True
        self.back_enabled = True
        self.board_enabled = False

    def build(self) -> None:
        """Trigger the MediaMTX/VA launch and read camera sub-flags."""
        self._read_subflags()

        from components.va.media_service import ensure_media_service_running
        self._media_service = ensure_media_service_running()
        logger.info(
            "VideoAnalyticsFeature built; media service running "
            "(front=%s, back=%s, board=%s).",
            self.front_enabled, self.back_enabled, self.board_enabled,
        )

    def teardown(self) -> None:
        """Stop the MediaMTX server if this feature started it."""
        if self._media_service is not None:
            try:
                self._media_service.stop_server()
            except Exception as e:  # pragma: no cover - defensive cleanup
                logger.error("Error stopping media service: %s", e)
        self._media_service = None
        logger.info("VideoAnalyticsFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
            "type": "panel",
            "panel": "video_analytics",
            "title": "Video Analytics",
            "cameras": {
                "front": self.front_enabled,
                "back": self.back_enabled,
                "board": self.board_enabled,
            },
        }

    def _read_subflags(self) -> None:
        va_cfg = getattr(config, "va_pipeline", None)
        self.front_enabled = bool(getattr(va_cfg, "front_enabled", True))
        self.back_enabled = bool(getattr(va_cfg, "back_enabled", True))

        board_cfg = getattr(config, "board_ocr", None)
        self.board_enabled = bool(getattr(board_cfg, "enabled", False))
