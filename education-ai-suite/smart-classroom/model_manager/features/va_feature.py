import logging
from typing import Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


class VideoAnalyticsFeature:

    id: str = "video_analytics"
    requires: List[str] = []
    depends_on: List[str] = []
    router: APIRouter = router

    def __init__(self) -> None:
        self._media_service = None

    def build(self) -> None:
        """Trigger the MediaMTX/VA launch."""
        from components.va.media_service import ensure_media_service_running
        self._media_service = ensure_media_service_running()
        logger.info("VideoAnalyticsFeature built; media service running.")

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
        }
