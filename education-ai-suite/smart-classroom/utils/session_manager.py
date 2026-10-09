import re
import uuid
from datetime import datetime

# The exact shape generate_session_id() produces: <YYYYMMDD>-<HHMMSS>-<4 hex>.
# Used to vet ids that arrive from a client (POST /sessions/register), which the
# server would otherwise take on faith.
_GENERATED_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")

# A deliberately wider net for anything that ends up in a filesystem path. It
# only has to guarantee the id is a single, relative path segment: no separator,
# no drive letter, and no leading dot so "." and ".." cannot slip through.
PATH_SAFE_SESSION_ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_PATH_SAFE_RE = re.compile(PATH_SAFE_SESSION_ID)


def generate_session_id():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_uid = str(uuid.uuid4())[:4]  # short random suffix
    return f"{timestamp}-{short_uid}"


def is_generated_session_id(session_id) -> bool:
    """True if `session_id` looks like this server minted it."""
    return isinstance(session_id, str) and bool(_GENERATED_RE.match(session_id))


def is_path_safe_session_id(session_id) -> bool:
    """True if `session_id` is safe to use as a directory name."""
    return isinstance(session_id, str) and bool(_PATH_SAFE_RE.match(session_id))
