# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""The UI carries generated copies of the catalogs; this catches drift.

Adding a feature, changing a `depends_on` or reordering a stage without
re-running Scripts/gen_catalog.py leaves those copies wrong: the settings
screen's dependency warning names the wrong features, the history panel draws
the wrong pips.

Replaces test_feature_dependencies.py, which parsed both sides out of source
with `ast` and `re` because there was no single table to import.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_GENERATOR = _ROOT / "scripts" / "gen_catalog.py"


def _load_generator():
    """By path, not by name: pywin32 puts a `win32/scripts` namespace package on
    sys.path inside the venv, which shadows this repo's `scripts` directory."""
    spec = importlib.util.spec_from_file_location("_gen_catalog", _GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen_catalog = _load_generator()


@pytest.mark.parametrize("rel", sorted(gen_catalog.OUTPUTS))
def test_generated_file_exists(rel):
    assert (_ROOT / rel).is_file(), f"{rel} is missing; run Scripts/gen_catalog.py"


@pytest.mark.parametrize("rel", sorted(gen_catalog.OUTPUTS))
def test_generated_file_is_current(rel):
    wanted = gen_catalog.OUTPUTS[rel]()
    current = (_ROOT / rel).read_text(encoding="utf-8")
    assert current == wanted, (
        f"{rel} is stale. Run: python Scripts/gen_catalog.py"
    )


@pytest.mark.parametrize("rel", sorted(gen_catalog.OUTPUTS))
def test_generated_file_says_it_is_generated(rel):
    """The banner is the only thing warning a reader off hand-editing it."""
    head = (_ROOT / rel).read_text(encoding="utf-8")[:600]
    assert "GENERATED FILE - do not edit." in head
    assert "Scripts/gen_catalog.py" in head


def test_check_mode_agrees():
    """--check is the CI gate; exercise it as a process, not just in-tree."""
    result = subprocess.run(
        [sys.executable, str(_GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )
    assert result.returncode == 0, result.stderr
