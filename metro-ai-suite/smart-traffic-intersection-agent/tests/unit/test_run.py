# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for run.py - Traffic Intersection Agent launcher script."""

import runpy
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


RUN_PATH = Path(__file__).parent.parent.parent / "src" / "run.py"
SRC_DIR = str(RUN_PATH.parent)


class TestRunPathSetup:
    """Tests for the launcher path setup behavior."""

    def test_run_script_adds_src_directory_to_sys_path(self):
        """Test the launcher inserts src at the front of sys.path."""
        original_path = sys.path.copy()

        try:
            namespace = {"__file__": str(RUN_PATH)}
            exec(RUN_PATH.read_text(), namespace)

            assert namespace["current_dir"] == RUN_PATH.parent
            assert sys.path[0] == SRC_DIR
        finally:
            sys.path = original_path


class TestRunEntrypoint:
    """Tests for the script entrypoint behavior."""

    def test_run_script_calls_main_when_executed_as_script(self):
        """Test that the __main__ guard imports and calls main()."""
        original_path = sys.path.copy()
        fake_main_module = ModuleType("main")
        fake_main_module.main = Mock()

        try:
            sys.path.insert(0, SRC_DIR)
            with patch.dict(sys.modules, {"main": fake_main_module}):
                runpy.run_path(str(RUN_PATH), run_name="__main__")

            fake_main_module.main.assert_called_once()
        finally:
            sys.path = original_path
