# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the turtlesim_tutorial launch file structure."""

import ast
import os


LAUNCH_FILE = os.path.join(
    os.path.dirname(__file__),
    '..',
    'turtlesim_tutorial',
    'launch',
    'turtlesim_tutorial.launch.py',
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


def test_launch_file_starts_turtlesim_node():
    """The launch file must include a turtlesim_node."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    assert 'turtlesim_node' in source, (
        "Expected 'turtlesim_node' executable in launch file"
    )


def test_launch_file_uses_turtlesim_package():
    """The launch file must reference the turtlesim package."""
    with open(LAUNCH_FILE, 'r', encoding='utf-8') as fh:
        source = fh.read()
    assert "'turtlesim'" in source or '"turtlesim"' in source, (
        "Expected 'turtlesim' package reference in launch file"
    )
