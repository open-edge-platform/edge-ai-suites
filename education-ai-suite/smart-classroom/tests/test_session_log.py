import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

from utils.session_log import session_log_handler


def _patch_dir(tmp):
    return patch(
        "utils.session_log.SessionPaths.app_log_path",
        return_value=Path(tmp) / "logs" / "app.log",
    )


def test_handler_added_and_removed():
    root = logging.getLogger()
    before = len(root.handlers)
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        with session_log_handler("s1"):
            assert len(root.handlers) == before + 1
        assert len(root.handlers) == before


def test_logs_written_to_session_file():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        with session_log_handler("s1"):
            logging.getLogger("some.module").info("hello inside session")
        path = Path(tmp) / "logs" / "app.log"
        assert path.exists()
        assert "hello inside session" in path.read_text(encoding="utf-8")


def test_no_write_after_exit():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp):
        with session_log_handler("s1"):
            pass
        logging.getLogger("some.module").info("after exit")
        path = Path(tmp) / "logs" / "app.log"
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        assert "after exit" not in content


def test_makedirs_failure_does_not_raise():
    with tempfile.TemporaryDirectory() as tmp, _patch_dir(tmp), patch(
        "utils.session_log.os.makedirs", side_effect=OSError("no perm")
    ):
        with session_log_handler("s1"):
            logging.getLogger("some.module").info("still works")  # no raise
