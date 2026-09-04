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
    def logs_dir(session_id: str) -> Path:
        """<session>/logs - logs and statistics, kept apart from artifacts."""
        return SessionPaths.session_dir(session_id) / "logs"

    @staticmethod
    def raw_dir(session_id: str) -> Path:
        """<session>/raw - CNN/small-model output and lightly processed data."""
        return SessionPaths.session_dir(session_id) / "raw"

    @staticmethod
    def result_dir(session_id: str) -> Path:
        """<session>/result - LLM/VLM generated deliverables."""
        return SessionPaths.session_dir(session_id) / "result"

    @staticmethod
    def app_log_path(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "app.log"

    @staticmethod
    def stage_events_path(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "stage_events.jsonl"

    @staticmethod
    def metrics_path(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "performance_metrics.csv"

    @staticmethod
    def utilization_logs_dir(session_id: str) -> Path:
        return SessionPaths.logs_dir(session_id) / "utilization_logs"

    @staticmethod
    def transcript_path(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "transcription.txt"

    @staticmethod
    def teacher_transcript_path(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "teacher_transcription.txt"

    @staticmethod
    def segmentation_transcript_path(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "content_segmentation_transcription.txt"

    @staticmethod
    def ocr_result_path(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "ocr_result.txt"

    @staticmethod
    def asr_events_path(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "asr_events.jsonl"

    @staticmethod
    def va_dir(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "va"

    @staticmethod
    def va_logs_dir(session_id: str) -> Path:
        return SessionPaths.va_dir(session_id) / "logs"

    @staticmethod
    def class_statistics_path(session_id: str) -> Path:
        return SessionPaths.va_dir(session_id) / "class_statistics.json"

    @staticmethod
    def board_ocr_dir(session_id: str) -> Path:
        return SessionPaths.raw_dir(session_id) / "board_ocr"

    @staticmethod
    def summary_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "summary.md"

    @staticmethod
    def mindmap_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "mindmap.mmd"

    @staticmethod
    def topics_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "topics.json"

    @staticmethod
    def report_md_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "class_report.md"

    @staticmethod
    def report_docx_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "class_report.docx"

    @staticmethod
    def report_pdf_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "class_report.pdf"

    @staticmethod
    def report_fields_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "class_report_fields.json"

    @staticmethod
    def mindmap_png_path(session_id: str) -> Path:
        return SessionPaths.result_dir(session_id) / "mindmap_report.png"
