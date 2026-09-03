import shutil
import tempfile
from pathlib import Path

import pytest

from utils import orchestrator, session_store
from utils.runtime_config_loader import RuntimeConfig


@pytest.fixture(autouse=True)
def _reset_global_state():
    orchestrator._RUNNING.clear()
    session_store.SessionStore._states.clear()

    tmp_root = Path(tempfile.mkdtemp())
    config_path = tmp_root / "runtime_config.yaml"
    config_path.write_text(
        "Project:\n"
        "  name: test-sessions\n"
        "  location: '" + str(tmp_root / "storage").replace("\\", "/") + "'\n"
        "  microphone: ''\n",
        encoding="utf-8",
    )

    orig = RuntimeConfig.CONFIG_PATH
    RuntimeConfig.CONFIG_PATH = str(config_path)

    yield

    RuntimeConfig.CONFIG_PATH = orig
    shutil.rmtree(tmp_root, ignore_errors=True)