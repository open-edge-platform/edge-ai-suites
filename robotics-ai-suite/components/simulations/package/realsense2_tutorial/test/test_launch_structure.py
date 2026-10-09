# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the realsense2_tutorial launch file structure."""

import ast
import os


LAUNCH_FILE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'realsense2_tutorial',
    'launch',
    'realsense2_tutorial.launch.py',
)

FIND_CAMERAS_SCRIPT = os.path.join(
    os.path.dirname(__file__),
    '..',
    'scripts',
    'find_cameras.sh',
)


def test_launch_file_exists():
    """The launch file must exist on disk."""
    assert os.path.isfile(LAUNCH_FILE), f'Launch file not found: {LAUNCH_FILE}'  # nosec B101


def test_launch_file_valid_python():
    """The launch file must be syntactically valid Python."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    ast.parse(source)


def test_launch_file_has_generate_function():
    """The launch file must define generate_launch_description()."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    tree = ast.parse(source)
    func_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert 'generate_launch_description' in func_names, (  # nosec B101
        'generate_launch_description() not found in launch file'
    )


def test_launch_file_declares_camera_type_arg():
    """The launch file must declare the camera_type argument."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    assert 'camera_type' in source, (  # nosec B101
        "Expected 'camera_type' argument declaration in launch file"
    )


def test_find_cameras_script_exists():
    """The find_cameras.sh helper must exist on disk."""
    assert os.path.isfile(FIND_CAMERAS_SCRIPT), (  # nosec B101
        f'find_cameras.sh not found: {FIND_CAMERAS_SCRIPT}'
    )


def test_find_cameras_script_executable():
    """The find_cameras.sh helper must be executable."""
    assert os.access(FIND_CAMERAS_SCRIPT, os.X_OK), (  # nosec B101
        f'find_cameras.sh is not executable: {FIND_CAMERAS_SCRIPT}'
    )
