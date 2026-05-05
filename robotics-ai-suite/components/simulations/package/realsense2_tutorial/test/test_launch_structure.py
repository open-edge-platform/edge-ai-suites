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


def test_launch_file_exists():
    """The launch file must exist on disk."""
    assert os.path.isfile(LAUNCH_FILE), f'Launch file not found: {LAUNCH_FILE}'


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
    assert 'generate_launch_description' in func_names, (
        'generate_launch_description() not found in launch file'
    )


def test_launch_file_declares_use_usb_camera_arg():
    """The launch file must declare the use_usb_camera argument."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    assert 'use_usb_camera' in source, (
        "Expected 'use_usb_camera' argument declaration in launch file"
    )
