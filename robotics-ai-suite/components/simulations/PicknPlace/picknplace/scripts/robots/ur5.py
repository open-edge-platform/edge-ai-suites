# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
from typing import List

MOVE_GROUP_ARM: str = "arm"
MOVE_GROUP_GRIPPER: str = "gripper"

OPEN_GRIPPER_JOINT_POSITIONS: List[float] = [0.0]
CLOSED_GRIPPER_JOINT_POSITIONS: List[float] = [0.80285]


def joint_names(prefix: str = "") -> List[str]:
    return [        
        prefix + "shoulder_pan_joint",
        prefix + "shoulder_lift_joint",
        prefix + "elbow_joint",
        prefix + "wrist_1_joint",
        prefix + "wrist_2_joint",
        prefix + "wrist_3_joint",
    ]


def base_link_name(prefix: str = "") -> str:
    return prefix + "base_link"


def end_effector_name(prefix: str = "") -> str:
    return prefix + "wrist_3_link"


def gripper_joint_names(prefix: str = "") -> List[str]:
    return [
        prefix + "robotiq_85_left_knuckle_joint",        
    ]
