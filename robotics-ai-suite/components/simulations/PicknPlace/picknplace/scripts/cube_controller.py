#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# Desc: Controller program to spawn cubes on conveyor belt and publish their coordinates

# Standard Library Imports
import sys
import time
import math
import random
from copy import deepcopy

# Third-Party Library Imports
import rclpy
import rclpy.time
import rclpy.duration
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup

from ament_index_python.packages import get_package_share_directory

import subprocess

# Gazebo Transport Imports
import gz.transport13 as gz_transport
import gz.msgs10.boolean_pb2 as boolean_pb2
import gz.msgs10.entity_pb2 as entity_pb2
import gz.msgs10.entity_factory_pb2 as entity_factory_pb2
import gz.msgs10.pose_pb2 as pose_pb2

# ROS 2 Imports
from picknplace.msg import BoxState
from rosgraph_msgs.msg import Clock
from geometry_msgs.msg import Pose

# Custom Module Imports
import robot_config.utils as utils


class CubeController(Node):
    # Node to spawn an entity in Gazebo.
    def __init__(self, args):
        super().__init__('Cube_Controller')
        self.last_spawn = 0

        self.get_logger().info('Cube Controller Node Initialized')

    def run(self):
        self.entity_xml = open(
            get_package_share_directory('picknplace') +
            '/urdf/marker_0/model.sdf'
        ).read()

        self._init_pose()
        self._init_ros_resources()

        self.index = 0
        self.cubes = [None] * 5
        self.arm1_range = [0.25, 1.3, 1.5, 2.8]
        self.delete_range = [0.25, 3.1, 1.5, 5.0]

        return 0

    def _init_pose(self):
        self.initial_pose = pose_pb2.Pose()
        self.initial_pose.position.x = 0.6
        self.initial_pose.position.y = 0.0
        self.initial_pose.position.z = 0.5
        self.initial_pose.orientation.w = 0
        self.initial_pose.orientation.x = 0.0
        self.initial_pose.orientation.y = 0.0
        self.initial_pose.orientation.z = 0.0

    def _init_ros_resources(self):
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        location_qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.callback_group = ReentrantCallbackGroup()
        self.client_cb_group = MutuallyExclusiveCallbackGroup()
        self.timer_cb_group = MutuallyExclusiveCallbackGroup()

        # Initialize Gazebo Transport Node for direct Gazebo communication
        self.gz_node = gz_transport.Node()
        self.world_name = "default"  # Default world name

        # Service topics for Gazebo Harmonic
        self.create_service_name = f"/world/{self.world_name}/create"
        self.remove_service_name = f"/world/{self.world_name}/remove"

        self.object_location_publisher = self.create_publisher(
            BoxState,
            '/object_location',
            qos_profile=location_qos_profile,
            callback_group=self.client_cb_group,
        )
        self.subscription = self.create_subscription(
            Clock,
            '/clock',
            self.clock_cb,
            callback_group=self.callback_group,
            qos_profile=qos_profile,
        )
        self.timer = self.create_timer(
            1,
            self.timer_callback,
            callback_group=self.timer_cb_group
        )

    # Timer to publish cube location and delete cube if it's out of range.
    def timer_callback(self):
        self.timer.cancel()
        start = time.time()
        array_len = len(self.cubes)
        cubelist = ''
        try:
            for index in range(array_len):
                if self.cubes[index] is not None:
                    cube = self.cubes[index]
                    self.get_logger().info(f"Processing cube: {cube}")
                    pose = self._cube_location(cube)
                    # Check if pose is valid and within deletion criteria
                    if (pose is not None and
                        (pose.position.z < .1 or
                         utils.pointInRect(pose, self.delete_range))):
                        self.get_logger().info(
                            f"Cube {cube} is out of range or on the floor. "
                            "Deleting..."
                        )
                        self._delete_cube(index)
                        array_len -= 1
                    elif (pose is not None and
                          utils.pointInRect(pose, self.arm1_range)):
                        box_state = BoxState()
                        box_state.name = cube
                        box_state.pose = pose
                        self.object_location_publisher.publish(box_state)
                    else:
                        pass
        except Exception:
            pass

        self.timer.reset()

    def is_cube_missed(self, pose):
        if pose.x > 0.0 and pose.x < 1.5 and pose.y > 1.7 and pose.y < 3.0:
            return True
        else:
            return False

    def clock_cb(self, entity):
        if entity.clock.sec - self.last_spawn > 10 or self.last_spawn == 0:
            self.last_spawn = entity.clock.sec
            array_len = len(self.cubes)
            for index in range(array_len):
                if self.cubes[index] is None:
                    success = self._spawn_cube(index)
                    return

    def _spawn_cube(self, index):
        self.get_logger().info("Spawning cube")

        # Create EntityFactory protobuf message for Gazebo Transport
        entity_factory = entity_factory_pb2.EntityFactory()
        entity_factory.name = 'cube_' + str(index)
        entity_factory.sdf = self.entity_xml
        entity_factory.allow_renaming = False

        # Set pose using protobuf message structure
        initial_pose = deepcopy(self.initial_pose)
        initial_pose.position.x += random.uniform(-0.15, 0.15)
        initial_pose.position.y += random.uniform(-0.15, 0.15)

        entity_factory.pose.CopyFrom(initial_pose)
        entity_factory.relative_to = 'world'

        executed, result = self.gz_node.request(
            self.create_service_name,
            entity_factory,
            entity_factory_pb2.EntityFactory,
            boolean_pb2.Boolean,
            timeout=5000
        )

        if executed and result:
            self.cubes[index] = entity_factory.name
            self.get_logger().info(f"Successfully spawned cube {index}")
        else:
            self.get_logger().error(f"Failed to spawn cube {index}")

        return 0

    def _cube_location(self, cube_name):
        """Get cube location using Gazebo pose topic"""
        try:
            # Run gz model command to get pose
            cmd = ["gz", "model", "-m", cube_name, "--pose"]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            output = result.stdout

            # Parse output for pose
            lines = output.splitlines()
            xyz_line = None
            for i, line in enumerate(lines):
                if ("Pose [ XYZ (m) ] [ RPY (rad) ]:" in line and
                        i + 1 < len(lines)):
                    xyz_line = lines[i + 1].strip()
                    rpy_line = lines[i + 2].strip()
                    break
            if xyz_line:
                xyz = xyz_line.strip("[]").split()
                pose = Pose()
                if len(xyz) == 3:
                    pose.position.x = float(xyz[0])
                    pose.position.y = float(xyz[1])
                    pose.position.z = float(xyz[2])
                if rpy_line:
                    rpy = rpy_line.strip("[]").split()
                    if len(rpy) == 3:
                        roll = float(rpy[0])
                        pitch = float(rpy[1])
                        yaw = float(rpy[2])
                        # Convert RPY to quaternion
                        cy = math.cos(yaw * 0.5)
                        sy = math.sin(yaw * 0.5)
                        cp = math.cos(pitch * 0.5)
                        sp = math.sin(pitch * 0.5)
                        cr = math.cos(roll * 0.5)
                        sr = math.sin(roll * 0.5)

                        pose.orientation.w = cr * cp * cy + sr * sp * sy
                        pose.orientation.x = sr * cp * cy - cr * sp * sy
                        pose.orientation.y = cr * sp * cy + sr * cp * sy
                        pose.orientation.z = cr * cp * sy - sr * sp * cy
                    else:
                        pose.orientation.x = 0.0
                        pose.orientation.y = 0.0
                        pose.orientation.z = 0.0
                        pose.orientation.w = 1.0
                    self.get_logger().info(f"Cube {cube_name} pose: {pose}")
                    return pose
        except Exception:
            pass
        return None

    def _delete_cube(self, index):
        # Delete entity from gazebo using gz_transport

        # Create Entity protobuf message for Gazebo Transport
        entity = entity_pb2.Entity()
        entity.name = 'cube_' + str(index)
        entity.type = entity_pb2.Entity.MODEL

        # Call Gazebo service directly
        executed, result = self.gz_node.request(
            self.remove_service_name,
            entity,
            entity_pb2.Entity,
            boolean_pb2.Boolean,
            timeout=5000
        )

        if executed and result:
            self.cubes[index] = None
            self.get_logger().info(f"Successfully deleted cube {index}")
        else:
            self.get_logger().error(f"Failed to delete cube {index}")

        return 0


def main(args=sys.argv):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)
    cube_controller_node = CubeController(args_without_ros)
    cube_controller_node.get_logger().info('Spawn Entity started')

    executor = MultiThreadedExecutor()
    executor.add_node(cube_controller_node)
    exit_code = cube_controller_node.run()
    executor.spin()

    rclpy.shutdown()
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
