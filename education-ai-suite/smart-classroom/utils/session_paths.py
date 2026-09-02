from pathlib import Path

from utils.runtime_config_loader import RuntimeConfig


class SessionPaths:
    @staticmethod
    def base_dir() -> Path:
        """<location>/<name> - project base, where global files (e.g. sessions.db) live."""
        proj = RuntimeConfig.get_section("Project")
        return Path(proj.get("location")) / proj.get("name")

    @staticmethod
    def session_dir(session_id: str) -> Path:
        """<location>/<name>/<session_id> - root directory for one session's artifacts."""
        return SessionPaths.base_dir() / session_id

    @staticmethod
    def va_dir(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "va"

    @staticmethod
    def logs_dir(session_id: str) -> Path:
        """<session>/logs - debug/observability output, kept apart from artifacts."""
        return SessionPaths.session_dir(session_id) / "logs"

    @staticmethod
    def app_log_path(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "app.log"

    @staticmethod
    def stage_events_path(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "stage_events.jsonl"

    @staticmethod
    def transcript_path(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "transcription.txt"

    @staticmethod
    def segmentation_transcript_path(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "content_segmentation_transcription.txt"

    @staticmethod
    def summary_path(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "summary.md"

    @staticmethod
    def mindmap_path(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "mindmap.mmd"

    @staticmethod
    def topics_path(session_id: str) -> Path:
        return SessionPaths.session_dir(session_id) / "topics.json"
