# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for UR5 robot configuration constants and helper functions."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from robots.ur5 import (  # noqa: E402  # pylint: disable=wrong-import-position,import-error
    MOVE_GROUP_ARM,
    MOVE_GROUP_GRIPPER,
    OPEN_GRIPPER_JOINT_POSITIONS,
    CLOSED_GRIPPER_JOINT_POSITIONS,
    joint_names,
    base_link_name,
    end_effector_name,
    gripper_joint_names,
)

UR5_JOINT_COUNT = 6
EXPECTED_JOINTS = [
    'shoulder_pan_joint',
    'shoulder_lift_joint',
    'elbow_joint',
    'wrist_1_joint',
    'wrist_2_joint',
    'wrist_3_joint',
]


def test_move_group_names():
    """Move group names must be non-empty strings."""
    assert isinstance(MOVE_GROUP_ARM, str) and MOVE_GROUP_ARM
    assert isinstance(MOVE_GROUP_GRIPPER, str) and MOVE_GROUP_GRIPPER


def test_gripper_positions_are_lists():
    """Gripper joint positions must be non-empty lists of floats."""
    assert isinstance(OPEN_GRIPPER_JOINT_POSITIONS, list) and OPEN_GRIPPER_JOINT_POSITIONS
    assert isinstance(CLOSED_GRIPPER_JOINT_POSITIONS, list) and CLOSED_GRIPPER_JOINT_POSITIONS
    assert all(isinstance(v, float) for v in OPEN_GRIPPER_JOINT_POSITIONS)
    assert all(isinstance(v, float) for v in CLOSED_GRIPPER_JOINT_POSITIONS)


def test_gripper_open_less_than_closed():
    """Open gripper position must be less than closed position."""
    assert OPEN_GRIPPER_JOINT_POSITIONS[0] < CLOSED_GRIPPER_JOINT_POSITIONS[0]


def test_joint_names_count():
    """UR5 must have exactly 6 arm joints."""
    assert len(joint_names()) == UR5_JOINT_COUNT


def test_joint_names_without_prefix():
    """Joint names without prefix must match expected UR5 joint names."""
    assert joint_names() == EXPECTED_JOINTS


def test_joint_names_with_prefix():
    """Joint names with a prefix must be prepended correctly."""
    prefix = 'arm1_'
    names = joint_names(prefix)
    assert all(n.startswith(prefix) for n in names)
    assert [n[len(prefix):] for n in names] == EXPECTED_JOINTS


def test_base_link_name_without_prefix():
    """Base link name without prefix must be 'base_link'."""
    assert base_link_name() == 'base_link'


def test_base_link_name_with_prefix():
    """Base link name with prefix must be prepended correctly."""
    assert base_link_name('arm1_') == 'arm1_base_link'


def test_end_effector_name_without_prefix():
    """End effector name without prefix must be non-empty."""
    assert isinstance(end_effector_name(), str) and end_effector_name()


def test_end_effector_name_with_prefix():
    """End effector name with prefix must be prepended correctly."""
    prefix = 'arm1_'
    assert end_effector_name(prefix).startswith(prefix)


def test_gripper_joint_names_without_prefix():
    """Gripper joint names must be a non-empty list."""
    names = gripper_joint_names()
    assert isinstance(names, list) and names


def test_gripper_joint_names_with_prefix():
    """Gripper joint names with prefix must be prepended correctly."""
    prefix = 'arm1_'
    names = gripper_joint_names(prefix)
    assert all(n.startswith(prefix) for n in names)
