import logging
import os
import threading
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from utils.session_paths import SessionPaths

logger = logging.getLogger(__name__)

_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Which session the current thread belongs to. A per-session file handler only
# accepts records whose originating thread is bound to that same session, so
# concurrent sessions do not bleed into each other's app.log.
_local = threading.local()


def _current_session():
    return getattr(_local, "session_id", None)


def bind_session(session_id):
    """Bind the calling thread to a session (call at the start of a worker
    thread that belongs to `session_id`, e.g. the VA thread)."""
    _local.session_id = session_id


class _SessionFilter(logging.Filter):
    def __init__(self, session_id):
        super().__init__()
        self._session_id = session_id

    def filter(self, record):
        return _current_session() == self._session_id


@contextmanager
def session_log_handler(session_id):
    """Attach a per-session app.log handler to the root logger for the duration
    of a session's execution, then remove it. Binds the current thread to the
    session so its records are routed to this handler.
    """
    prev = _current_session()
    bind_session(session_id)
    handler = None
    root = logging.getLogger()
    try:
        try:
            path = SessionPaths.app_log_path(session_id)
            os.makedirs(path.parent, exist_ok=True)
            handler = RotatingFileHandler(
                path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter(fmt=_FORMAT, datefmt=_DATEFMT))
            handler.addFilter(_SessionFilter(session_id))
            # Ensure INFO records reach handlers; setup_logger normally sets this,
            # but guard so the session log works even if root is left at WARNING.
            if root.level > logging.INFO or root.level == logging.NOTSET:
                root.setLevel(logging.INFO)
            root.addHandler(handler)
        except OSError as e:
            logger.warning(f"[session_log] could not open app.log for {session_id}: {e}")
            handler = None
        yield
    finally:
        if handler is not None:
            root.removeHandler(handler)
            handler.close()
        _local.session_id = prev
