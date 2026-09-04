import json
import logging
import os

from utils.session_paths import SessionPaths

logger = logging.getLogger(__name__)


class AsrEventWriter:
    @staticmethod
    def write(session_id, event) -> None:
        try:
            path = SessionPaths.asr_events_path(session_id)
            os.makedirs(path.parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError) as e:
            logger.warning(f"[asr_events] failed to write event for {session_id}: {e}")
