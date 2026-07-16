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
import random
import threading
from copy import deepcopy

# Third-Party Library Imports
import rclpy
import rclpy.time
import rclpy.duration
import rclpy.parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup

from ament_index_python.packages import get_package_share_directory

# Gazebo Transport Imports
import gz.transport13 as gz_transport
import gz.msgs10.boolean_pb2 as boolean_pb2
import gz.msgs10.entity_pb2 as entity_pb2
import gz.msgs10.entity_factory_pb2 as entity_factory_pb2
import gz.msgs10.pose_pb2 as pose_pb2
import gz.msgs10.pose_v_pb2 as pose_v_pb2

# ROS 2 Imports
from rvc.msg import BoxState
from rosgraph_msgs.msg import Clock
from geometry_msgs.msg import Pose, TransformStamped
from tf2_ros import TransformBroadcaster

# Custom Module Imports
import robot_config.utils as utils


class CubeController(Node):
    """Spawns cubes onto belt1, tracks their poses via gz_transport, broadcasts
    TF, publishes BoxState, and deletes cubes once they leave either belt."""

    def __init__(self, args):
        super().__init__("Cube_Controller")
        # CRITICAL: use sim time so position estimates match Gazebo physics clock
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        # TODO Currently forces sim time. Need to test with real time or explicitly enforce sim time.
        self.set_parameters(
            [
                rclpy.parameter.Parameter(
                    "use_sim_time", rclpy.parameter.Parameter.Type.BOOL, True
                )
            ]
        )
        self.last_spawn = 0
        self.cube_spawn_data = {}  # {cube_name: {'spawn_time': float, 'spawn_y': float}}
        self.cube_actual_pose = {}
        self._gz_pose_lock = (
            threading.Lock()
        )  # protects cube_actual_pose from gz_transport thread
        self._gz_request_lock = (
            threading.Lock()
        )  # serialises gz_node.request calls across threads
        self.conveyor_speed = (
            0.12  # m/s - keep aligned with conveyor SDF plugin max_velocity
        )

        self.get_logger().info("Cube Controller Node Initialized")

    def run(self):
        with open(
            get_package_share_directory("rvc") + "/urdf/marker_0/model.sdf"
        ) as f:
            self.entity_xml = f.read()

        self._init_pose()
        self._init_ros_resources()

        self.cubes = [None] * 5
        self.arm1_range = [
            0.25,
            1.3,
            1.5,
            3.5,
        ]  # x:0.25-1.5, y:1.3-3.5 (pick zone - expanded)
        # Belt 1 (source) footprint: spawned at world (0.83, 2.3) size 1x6m.
        # Belt 1 X span: 0.33..1.33, Y span: -0.7..5.3.
        # Delete cubes ~1cm before the belt-1 far end (y=5.3) to prevent
        # floating at the edge.
        self.delete_range = [-1.0, 5.29, 2.5, 12.0]
        # Belt 2 (sink) footprint: spawned at world (-0.48, 2.3) yaw 180,
        # size 1x6m -> X span -0.98..0.02, Y span -0.7..5.3. Cubes are
        # placed by arm1 near y=2.92 and travel toward y=-0.7 (belt2's far
        # end after the 180 yaw). Delete them shortly before they leave the
        # belt so they do not pile up on the ground.
        self.delete_range_belt2 = [-0.98, -10.0, 0.02, -0.3]

        # Cleanup thresholds
        self.max_cube_age_sec = 120.0  # 2 minutes (belt takes ~50s at full speed)
        self.on_floor_z = 0.02  # only triggers on physics glitch (cube through floor); belt surface puts cubes above this

        return 0

    def _init_pose(self):
        self.initial_pose = pose_pb2.Pose()
        self.initial_pose.position.x = 0.7
        self.initial_pose.position.y = 0.0
        # Spawn close to belt surface to avoid high-energy drops and bouncing out
        self.initial_pose.position.z = 0.20
        self.initial_pose.orientation.w = 1.0
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
            depth=1,
        )

        self.callback_group = ReentrantCallbackGroup()
        self.client_cb_group = MutuallyExclusiveCallbackGroup()
        self.timer_cb_group = MutuallyExclusiveCallbackGroup()
        self.spawn_cb_group = (
            MutuallyExclusiveCallbackGroup()
        )  # serialises clock_cb spawns

        # Initialize TF2 broadcaster for publishing cube transforms
        self.tf_broadcaster = TransformBroadcaster(self)

        # Initialize Gazebo Transport Node for direct Gazebo communication
        self.gz_node = gz_transport.Node()
        self.world_name = "default"  # Default world name

        # Service topics for Gazebo Harmonic
        self.create_service_name = f"/world/{self.world_name}/create"
        self.remove_service_name = f"/world/{self.world_name}/remove"

        # Subscribe to Gazebo dynamic pose topic for real-time cube positions
        # This replaces unreliable CLI queries (gz model --pose) that frequently timeout
        pose_info_topic = f"/world/{self.world_name}/dynamic_pose/info"
        try:
            self.gz_node.subscribe(pose_v_pb2.Pose_V, pose_info_topic, self._gz_pose_cb)
            self.get_logger().info(
                f"Subscribed to Gazebo pose updates: {pose_info_topic}"
            )
        except Exception as e:
            self.get_logger().warn(
                f"Failed to subscribe to {pose_info_topic}: "
                f"{e}, falling back to estimates"
            )

        self.object_location_publisher = self.create_publisher(
            BoxState,
            "/object_location",
            qos_profile=location_qos_profile,
            callback_group=self.client_cb_group,
        )
        self.subscription = self.create_subscription(
            Clock,
            "/clock",
            self.clock_cb,
            callback_group=self.spawn_cb_group,
            qos_profile=qos_profile,
        )
        self.timer = self.create_timer(
            0.1, self.timer_callback, callback_group=self.timer_cb_group
        )

    def _gz_pose_cb(self, msg):
        """Callback for Gazebo dynamic pose updates via gz_transport.
        Runs on gz_transport thread — use lock for thread safety."""
        with self._gz_pose_lock:
            for pose in msg.pose:
                name = pose.name
                # Only update poses for cubes we are actively tracking.
                # This prevents stale buffered messages from re-inserting a cube
                # that was just deleted (which would cause a false orphan hit).
                if name in self.cube_actual_pose:
                    ros_pose = self.cube_actual_pose[name]
                    if ros_pose is None:
                        ros_pose = Pose()
                        self.cube_actual_pose[name] = ros_pose
                    ros_pose.position.x = pose.position.x
                    ros_pose.position.y = pose.position.y
                    ros_pose.position.z = pose.position.z
                    ros_pose.orientation.w = pose.orientation.w
                    ros_pose.orientation.x = pose.orientation.x
                    ros_pose.orientation.y = pose.orientation.y
                    ros_pose.orientation.z = pose.orientation.z

    def _calculate_cube_pose(self, cube_name):
        """Calculate cube position based on spawn time and conveyor speed (non-blocking)"""
        if cube_name not in self.cube_spawn_data:
            return None

        spawn_info = self.cube_spawn_data[cube_name]
        current_time = self.get_clock().now().nanoseconds / 1e9
        elapsed_time = current_time - spawn_info["spawn_time"]

        # Calculate Y position: spawn_y + (conveyor_speed * time)
        current_y = spawn_info["spawn_y"] + (self.conveyor_speed * elapsed_time)

        pose = Pose()
        pose.position.x = spawn_info["spawn_x"]
        pose.position.y = current_y
        pose.position.z = self.initial_pose.position.z
        pose.orientation.w = 1.0
        pose.orientation.x = 0.0
        pose.orientation.y = 0.0
        pose.orientation.z = 0.0

        return pose

    # Timer to publish cube location and delete cube if it's out of range.
    def timer_callback(self):
        self.timer.cancel()
        array_len = len(self.cubes)
        try:
            for index in range(array_len):
                if self.cubes[index] is None or self.cubes[index] == "__pending__":
                    continue
                cube = self.cubes[index]
                # Get actual Gazebo pose from gz_transport subscription (non-blocking)
                # This replaces the slow/hanging CLI queries that caused TF drift
                with self._gz_pose_lock:
                    actual_pose = self.cube_actual_pose.get(cube)

                if actual_pose is not None:
                    pose = actual_pose
                else:
                    # Fallback to mathematical estimate (only before first gz pose arrives)
                    pose = self._calculate_cube_pose(cube)
                deletion_pose = pose

                # Check if pose is valid and within deletion criteria
                should_delete = False
                delete_reasons = []
                if deletion_pose is not None:
                    cube_age = None
                    if cube in self.cube_spawn_data:
                        cube_age = (
                            self.get_clock().now().nanoseconds / 1e9
                            - self.cube_spawn_data[cube]["spawn_time"]
                        )

                    on_floor = deletion_pose.position.z < self.on_floor_z
                    in_end_delete_zone = utils.pointInRect(
                        deletion_pose, self.delete_range
                    )
                    in_belt2_end_zone = utils.pointInRect(
                        deletion_pose, self.delete_range_belt2
                    )

                    # Delete based on any available pose (actual or estimated)
                    if on_floor:
                        delete_reasons.append("on_floor")
                    if in_end_delete_zone:
                        delete_reasons.append("belt1_end")
                    if in_belt2_end_zone:
                        delete_reasons.append("belt2_end")

                    # Stale: very old cube that's well past either belt end
                    stale = (
                        cube_age is not None
                        and cube_age > self.max_cube_age_sec
                        and (
                            deletion_pose.position.y > 5.0
                            or deletion_pose.position.y < -0.5
                        )
                    )
                    if stale:
                        delete_reasons.append("stale")

                    should_delete = len(delete_reasons) > 0

                if should_delete:
                    self.get_logger().info(
                        f"Cube {cube} deleting: {','.join(delete_reasons)} "
                        f"pose=({deletion_pose.position.x:.2f},"
                        f"{deletion_pose.position.y:.2f},"
                        f"{deletion_pose.position.z:.2f})"
                    )
                    self._delete_cube(index)
                elif pose is not None:
                    # ALWAYS publish TF for all alive cubes (not just those in arm1_range)
                    # This ensures the arm can track cubes even when the conveyor is stopped
                    t = TransformStamped()
                    t.header.stamp = self.get_clock().now().to_msg()
                    t.header.frame_id = "world"
                    t.child_frame_id = cube

                    t.transform.translation.x = pose.position.x
                    t.transform.translation.y = pose.position.y
                    t.transform.translation.z = pose.position.z

                    t.transform.rotation.x = pose.orientation.x
                    t.transform.rotation.y = pose.orientation.y
                    t.transform.rotation.z = pose.orientation.z
                    t.transform.rotation.w = pose.orientation.w

                    self.tf_broadcaster.sendTransform(t)

                    # Publish BoxState for backward compatibility if in arm range
                    if utils.pointInRect(pose, self.arm1_range):
                        box_state = BoxState()
                        box_state.name = cube
                        box_state.pose = pose
                        self.object_location_publisher.publish(box_state)
        except Exception as e:
            self.get_logger().warn(f"timer_callback error: {e}")

        self.timer.reset()

    def clock_cb(self, entity):
        if entity.clock.sec - self.last_spawn > 10 or self.last_spawn == 0:
            self.last_spawn = entity.clock.sec
            array_len = len(self.cubes)
            for index in range(array_len):
                if self.cubes[index] is None:
                    self._spawn_cube(index)
                    return

    def _spawn_cube(self, index):
        self.get_logger().info(f"Spawning cube {index}")
        self.cubes[index] = (
            "__pending__"  # prevent concurrent spawn attempts on same slot
        )

        # Create EntityFactory protobuf message for Gazebo Transport
        entity_factory = entity_factory_pb2.EntityFactory()
        entity_factory.name = "cube_" + str(index)
        entity_factory.sdf = self.entity_xml
        entity_factory.allow_renaming = (
            False  # names must match self.cubes entries exactly
        )

        # Set pose using protobuf message structure
        initial_pose = deepcopy(self.initial_pose)
        initial_pose.position.x += random.uniform(-0.15, 0.15)
        initial_pose.position.y += random.uniform(-0.15, 0.15)

        entity_factory.pose.CopyFrom(initial_pose)
        entity_factory.relative_to = "world"

        # Try Gazebo Transport first
        with self._gz_request_lock:
            executed, result = self.gz_node.request(
                self.create_service_name,
                entity_factory,
                entity_factory_pb2.EntityFactory,
                boolean_pb2.Boolean,
                timeout=5000,
            )

        if executed and result.data:
            self.cubes[index] = entity_factory.name
            # Register slot so _gz_pose_cb starts accepting pose updates for this cube
            with self._gz_pose_lock:
                self.cube_actual_pose[entity_factory.name] = None
            # Track spawn data for mathematical position calculation
            self.cube_spawn_data[entity_factory.name] = {
                "spawn_time": self.get_clock().now().nanoseconds / 1e9,
                "spawn_x": initial_pose.position.x,
                "spawn_y": initial_pose.position.y,
            }
            self.get_logger().info(
                f"Successfully spawned {entity_factory.name}"
                f" at Y={initial_pose.position.y:.2f}m"
            )
        else:
            self.cubes[index] = None  # release slot so it can be retried
            self.get_logger().error(f"Failed to spawn cube {index}")

    def _delete_cube(self, index):
        # Delete entity from gazebo using gz_transport

        # Create Entity protobuf message for Gazebo Transport
        entity = entity_pb2.Entity()
        entity.name = "cube_" + str(index)
        entity.type = entity_pb2.Entity.MODEL

        # Call Gazebo service directly
        with self._gz_request_lock:
            executed, result = self.gz_node.request(
                self.remove_service_name,
                entity,
                entity_pb2.Entity,
                boolean_pb2.Boolean,
                timeout=5000,
            )

        if executed and result.data:
            self.get_logger().info(f"Successfully deleted cube {index}")
        else:
            self.get_logger().warn(
                f"Failed to delete cube {index} from Gazebo, cleaning up locally"
            )

        cube_name = "cube_" + str(index)
        self.cubes[index] = None
        # Clean up spawn tracking data
        if cube_name in self.cube_spawn_data:
            del self.cube_spawn_data[cube_name]
        with self._gz_pose_lock:
            if cube_name in self.cube_actual_pose:
                del self.cube_actual_pose[cube_name]


def main(args=sys.argv):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)
    cube_controller_node = CubeController(args_without_ros)
    cube_controller_node.get_logger().info("Spawn Entity started")

    executor = MultiThreadedExecutor()
    executor.add_node(cube_controller_node)
    cube_controller_node.run()
    executor.spin()

    rclpy.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
