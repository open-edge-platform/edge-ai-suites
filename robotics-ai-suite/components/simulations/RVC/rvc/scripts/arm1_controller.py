#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

# Copyright (C) 2026 Intel Corporation
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
# Desc: Controller program for ARM1
import sys
import subprocess
import threading
import time
import math


# Third-Party Library Imports
import rclpy
import rclpy.duration
import rclpy.time
import rclpy.utilities
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.logging import LoggingSeverity
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import Bool
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration
from rclpy.action import ActionClient
from robot_config_plugins.srv import ConveyorBeltControl
from moveit2 import MoveIt2
from moveit_msgs.msg import CollisionObject, JointConstraint
from shape_msgs.msg import SolidPrimitive
from geometry_msgs.msg import Pose
from smach import State, StateMachine
from rclpy.parameter import Parameter
import tf2_ros

# Custom Module Imports
from robots import ur5 as robot


class RobotController(Node):
    def __init__(self, args):
        super().__init__("ARM1Controller")
        self.arm_name = "arm1"
        # use_sim_time may already be declared by launch file parameters
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        # TODO Currently forces sim time. Need to test with real time or explicitly enforce sim time.
        self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.declare_parameter("state", "run")
        self.declare_parameter("verbose_conveyor", False)
        # Cache the flag so the high-rate belt joint callback doesn't acquire the
        # parameter lock on every message.
        self._verbose_conveyor = (
            self.get_parameter("verbose_conveyor").get_parameter_value().bool_value
        )
        self.setup_qos_and_groups()

        self.setup_logging()
        self.logger.info("robot controller constructor")
        self.moveit2_robot0 = self.setup_moveit()

        self.grasping = False

        # TF setup for cube tracking
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Target zone for cube detection (world frame Y coordinates)
        self.GRASP_Y_WORLD = (
            2.92  # Intercept shifted downstream to match real motion timing
        )
        # How far DOWNSTREAM of the nominal grasp line (in +Y) a cube can sit and
        # still be physically reachable / graspable. Cubes travel +Y, so once a
        # cube crosses GRASP_Y_WORLD its distance_to_grasp goes negative — but the
        # arm can still reach a band just past the line. Treating that band as part
        # of the active detection zone means a cube that is already sitting right
        # in front of the robot (e.g. the second of two cubes that spawned stacked,
        # left behind at the grasp line after its neighbour was picked) is still
        # selected and grabbed instead of being ignored because it is no longer
        # "incoming". 0.18 m ≈ 1.5 s of belt travel at 0.12 m/s.
        self.GRASP_ZONE_BACK = 0.18

        self.GRASP_Z_OFFSET = 0.030  # finger center is 0.030m BELOW ee_link
        # Extra upward clearance so the fingertips (which extend below the finger
        # center) grip the UPPER portion of the cube instead of driving into the
        # belt surface. Without this the tips bottom out on the conveyor collision
        # geometry and the contact force jams the gripper before it can close.
        # Cubes are 4.5 cm tall (half-height 0.0225 m), so 0.012 m still leaves the
        # fingers well overlapped with the cube body for a solid grasp.
        self.GRASP_BELT_CLEARANCE = 0.012
        # Gripper finger joint reads ~0.0 fully open, ~0.035 fully closed. A cube
        # physically blocks the fingers partway, so a reading at/above
        # GRASP_FINGER_EMPTY means the fingers bottomed out on nothing (the gripper
        # closed on air — cube left on the belt), while a reading inside the
        # (GRASP_FINGER_MIN, GRASP_FINGER_EMPTY) band means the fingers stalled on
        # the cube. Tune these if the finger kinematics change.
        self.GRASP_FINGER_EMPTY = 0.034
        self.GRASP_FINGER_MIN = 0.008
        self.CONVEYOR_SPEED = 0.12  # m/s (default, matches belt max_velocity)
        self.READY_Z_ARM = 0.45
        self.MIN_TARGET_X_ARM = 0.35
        # Cap the grasp reach at ~82% of the UR5's ~0.85 m reach. At the old 0.80
        # (≈94% reach) the far targets — combined with the parked cube's outer
        # arm-Y (≈-0.23) — drove the elbow toward full extension (the elbow
        # singularity), where IK conditioning collapses, planning burns the whole
        # time budget, and the descent gets jerky. 0.70 keeps every grasp in
        # well-conditioned space; cubes beyond it are simply re-presented next
        # conveyor cycle rather than attempted at the workspace edge.
        self.MAX_TARGET_X_ARM = 0.70

        # --- Pick belt (belt1) spatial gate for cube selection -----------------
        # belt1 (source) sits at world x≈0.83; belt2 (sink) sits at world x≈-0.48,
        # mirrored across arm1's base (world x=0.18). find_target_cube() must only
        # ever lock onto cubes that are physically on belt1. Without this gate, a
        # cube that has already been picked and placed on belt2 — which then
        # travels from y≈2.92 down toward y<0, i.e. the SAME y-range an approaching
        # belt1 cube occupies — would register a positive distance-to-grasp and
        # could be (re)selected as the target, sending the arm chasing a cube it
        # already delivered. Gating on world-X keeps selection on the pick belt.
        self.PICK_BELT_X_WORLD = 0.83
        self.PICK_BELT_X_TOL = 0.45  # accept world-X in [0.38, 1.28]; excludes belt2

        # Subscribe to conveyor belt 1 joint states to get real-time velocity
        self.conveyor_velocity_sub_belt1 = self.create_subscription(
            JointState,
            "/world/default/model/conveyor_belt1/joint_state",
            self.conveyor_velocity_callback,
            10,
        )
        # Subscribe to conveyor belt 2 joint states to get real-time velocity
        self.conveyor_velocity_sub_belt2 = self.create_subscription(
            JointState,
            "/world/default/model/conveyor_belt2/joint_state",
            self.conveyor_velocity_callback,
            10,
        )

        self._stopped_cube_world_pose = None  # Set in APPROACH, used in GRASP
        self.setup_subscriptions_and_services()

        # GRASP_Y_ARM is resolved from TF in Setup.execute() once the executor is spinning.
        self.GRASP_Y_ARM = -0.08  # fallback default (arm1 base at world y=3.0, GRASP_Y_WORLD=2.92)

    def _init_grasp_y_arm(self):
        """Compute GRASP_Y_ARM using the live TF tree."""
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                tf = self.tf_buffer.lookup_transform(
                    "arm1/base_link",
                    "world",
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.1),
                )
                # world origin in arm frame tells us the offset
                world_origin_in_arm = tf.transform.translation
                # GRASP_Y_WORLD expressed in arm1/base_link frame:
                self.GRASP_Y_ARM = world_origin_in_arm.y + self.GRASP_Y_WORLD
                self.logger.info(f"GRASP_Y_ARM resolved via TF: {self.GRASP_Y_ARM:.4f}")
                return
            except Exception:
                time.sleep(0.05)
        self.GRASP_Y_ARM = -0.08
        self.logger.warn(f"TF not ready, using fallback GRASP_Y_ARM={self.GRASP_Y_ARM}")

    def get_pose_in_base_frame(self, target_frame, timeout_sec=0.5):
        """Return (x, y, z) of target_frame in arm1/base_link frame via TF.

        This is the standard ROS2 approach — let TF traverse the tree
        rather than manually subtracting hardcoded base coordinates.
        Returns None on failure.
        """
        try:
            transform = self.tf_buffer.lookup_transform(
                "arm1/base_link",
                target_frame,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception as e:
            self.logger.debug(f"TF lookup arm1/base_link←{target_frame} failed: {e}")
            return None

    def get_cube_world_pose(self, cube_name, timeout_sec=0.1):
        """Return cube position tuple in world frame or None."""
        try:
            transform = self.tf_buffer.lookup_transform(
                "world",
                cube_name,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception:
            return None

    def _query_gz_model_pose(self, model_name, timeout=0.5):
        """Query actual model pose directly from Gazebo via CLI.
        Returns (x, y, z) tuple or None."""
        try:
            result = subprocess.run(
                ["gz", "model", "-m", model_name, "--pose"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.splitlines():
                if "[" not in line or "]" not in line:
                    continue
                try:
                    coords = line.strip().strip("[]").split()
                    if len(coords) >= 3:
                        return (float(coords[0]), float(coords[1]), float(coords[2]))
                except (ValueError, IndexError):
                    continue  # skip header/non-coordinate lines, try next
        except Exception:
            pass
        return None

    def _query_gz_model_yaw(self, model_name, timeout=0.5):
        """Query a model's yaw (rotation about world Z, radians) from Gazebo.

        `gz model -m <name> --pose` prints two bracketed coordinate lines: the
        first is the XYZ translation, the second is the RPY orientation. We
        return the yaw (3rd value of the RPY line). The arm1 base_link sits at
        world yaw 0, so this world yaw equals the cube's yaw in the arm frame.
        Returns None on failure.
        """
        try:
            result = subprocess.run(
                ["gz", "model", "-m", model_name, "--pose"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return None
            coord_lines = []
            for line in result.stdout.splitlines():
                if "[" not in line or "]" not in line:
                    continue
                coords = line.strip().strip("[]").split()
                if len(coords) >= 3:
                    try:
                        coord_lines.append([float(c) for c in coords[:3]])
                    except ValueError:
                        continue
            # coord_lines[0] == XYZ, coord_lines[1] == RPY
            if len(coord_lines) >= 2:
                return coord_lines[1][2]
        except Exception:
            pass
        return None

    @staticmethod
    def _grasp_quat_for_cube_yaw(cube_yaw):
        """Top-down grasp quaternion [x, y, z, w] aligned with the cube's faces.

        The default top-down grasp orientation is [1, 0, 0, 0] (gripper pointing
        straight down, wrist_3 ≈ 0). A square cube has 90° rotational symmetry,
        so we fold the cube's yaw into (-π/4, π/4] and rotate the gripper about
        the world vertical by that angle. This keeps the finger gap parallel to
        two opposing cube faces, so the fingers drop into the side clearances
        instead of clipping a corner and shoving the cube — while keeping wrist_3
        within ±0.79 rad of 0 (well inside the grasp-branch constraint band).

        Composing a world-frame Rz(θ) onto the straight-down base quaternion
        [1, 0, 0, 0] yields [cos(θ/2), sin(θ/2), 0, 0].
        """
        # Normalize to (-π, π], then fold into (-π/4, π/4] via 90° symmetry.
        theta = math.atan2(math.sin(cube_yaw), math.cos(cube_yaw))
        half_pi = math.pi / 2.0
        theta = theta - half_pi * round(theta / half_pi)
        h = theta / 2.0
        return [math.cos(h), math.sin(h), 0.0, 0.0]

    def conveyor_velocity_callback(self, msg):
        """Update conveyor speed from belt joint state"""
        if msg.name and "belt_joint" in msg.name[0] and msg.velocity:
            # Conveyor moves in Y direction, velocity is linear
            self.CONVEYOR_SPEED = abs(msg.velocity[0]) if msg.velocity[0] != 0 else 0.12
            # Only log significant changes, and only when verbose_conveyor is set
            if abs(self.CONVEYOR_SPEED - 0.12) > 0.01 and self._verbose_conveyor:
                self.logger.info(
                    f"[CONVEYOR] Speed updated: {self.CONVEYOR_SPEED:.3f} m/s"
                )

    def setup_qos_and_groups(self):
        self.qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.callback_group0 = MutuallyExclusiveCallbackGroup()
        self.client_cb_group0 = MutuallyExclusiveCallbackGroup()
        self.moveit_callback_group0 = MutuallyExclusiveCallbackGroup()

    def setup_moveit(self):
        m = MoveIt2(
            node=self,
            joint_names=robot.joint_names("arm1/"),
            base_link_name=robot.base_link_name("arm1/"),
            end_effector_name=robot.end_effector_name("arm1/"),
            group_name=robot.MOVE_GROUP_ARM,
            callback_group=self.moveit_callback_group0,
            execute_via_moveit=False,
            ignore_new_calls_while_executing=True,
            namespace_prefix="/arm1/",
        )
        # Faster joint-space moves (default 0.5). Cartesian paths set their
        # own scaling internally in the moveit2 wrapper.
        m.max_velocity = 0.9
        m.max_acceleration = 0.9
        return m

    def setup_logging(self):
        self.logger = self.get_logger()
        self.logger.set_level(LoggingSeverity.INFO)

    def setup_subscriptions_and_services(self):
        # Ready status publisher - signals when arm controller and MoveIt are fully initialized
        self.ready_publisher = self.create_publisher(
            Bool,
            "/arm1/controller_ready",
            qos_profile=self.qos_profile,
        )

        # Gripper action client (JointTrajectoryController)
        self._gripper_action_client = ActionClient(
            self,
            FollowJointTrajectory,
            "/arm1/gripper_controller/follow_joint_trajectory",
        )
        self._gripper_joint_names = [
            "arm1/left_finger_joint",
        ]

        # Gripper state tracking
        self._gripper_desired_position = 0.0  # 0.0=open, 0.035=closed

        # Persistent joint_states subscription for finger position monitoring
        # (avoids creating/destroying subscriptions in tight loops which causes stale reads)
        self._finger_positions = {"left": None, "right": None}
        self._finger_lock = threading.Lock()
        self._joint_states_sub = self.create_subscription(
            JointState, "/arm1/joint_states", self._joint_states_callback, 10
        )

        # Conveyor belt control service client
        self._conveyor_client = self.create_client(
            ConveyorBeltControl, "/conveyor/control"
        )
        self._conveyor_stopped = False

    def find_target_cube(self):
        """Find the best cube to grasp on the pick belt.

        Selection covers two regions, in priority order by proximity to leaving
        the workspace:
          * the ACTIVE zone — cubes already at or just past the grasp line
            (distance_to_grasp in [-GRASP_ZONE_BACK, 0]), i.e. sitting right in
            front of the robot and still reachable. These are the most urgent
            (they are about to ride off the reachable band) so the most-advanced
            cube wins.
          * the APPROACH zone — cubes still travelling toward the grasp line
            (distance_to_grasp > 0); among these the closest/incoming one wins,
            preserving the original tracking behaviour.
        Picking the cube with the smallest distance_to_grasp that is still
        reachable naturally orders both regions: an already-present cube
        (small/negative distance) is chosen before a farther approaching one, so
        two cubes that spawned stacked are both serviced — pick one, then the
        leftover sitting in front is selected on the next cycle.

        Cubes are gated to belt1's world-X band so a cube already placed on belt2
        (which re-enters the same y-range) can never be re-selected as the
        target."""
        closest_cube = None
        closest_distance = float("inf")

        # Scan cube_0..cube_N. Cubes are despawned once delivered and new ones
        # spawn with ever-increasing indices, so early indices (cube_0, cube_1…)
        # become permanently missing. We therefore must NOT stop at the first
        # missing index — that would blind us to every newer cube. Instead we
        # tolerate gaps and only stop after a long run of consecutive missing
        # indices (past the highest live cube).
        i = 0
        miss_streak = 0
        MAX_MISS_STREAK = 12
        MAX_INDEX = 200
        while i < MAX_INDEX:
            cube_frame = f"cube_{i}"
            try:
                transform = self.tf_buffer.lookup_transform(
                    "world",
                    cube_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.02),
                )
                miss_streak = 0
                cube_x = transform.transform.translation.x
                cube_y = transform.transform.translation.y
                distance_to_grasp = self.GRASP_Y_WORLD - cube_y
                # Reject cubes that are not on the pick belt (e.g. already placed
                # on belt2, or mid-carry across the base): only belt1's X band is
                # a valid pick source.
                on_pick_belt = (
                    abs(cube_x - self.PICK_BELT_X_WORLD) <= self.PICK_BELT_X_TOL
                )
                # Reachable = still approaching (distance > 0) OR sitting in the
                # active zone just past the line (distance down to -GRASP_ZONE_BACK).
                reachable = distance_to_grasp > -self.GRASP_ZONE_BACK
                # Smallest distance among reachable cubes wins — the most advanced
                # (or already-present) cube is serviced first.
                if on_pick_belt and reachable and distance_to_grasp < closest_distance:
                    closest_distance = distance_to_grasp
                    closest_cube = (cube_frame, transform)
            except Exception:
                miss_streak += 1
                if miss_streak >= MAX_MISS_STREAK:
                    break
            i += 1

        return closest_cube if closest_cube else (None, None)

    def _joint_states_callback(self, msg):
        """Persistent callback to cache finger joint positions."""
        with self._finger_lock:
            for i, name in enumerate(msg.name):
                if "left_finger_joint" in name:
                    self._finger_positions["left"] = msg.position[i]
                elif "right_finger_joint" in name:
                    self._finger_positions["right"] = msg.position[i]

    def _read_finger_position(self):
        """Read cached left finger joint position (non-blocking)."""
        with self._finger_lock:
            return self._finger_positions["left"]

    def _read_both_finger_positions(self):
        """Read cached positions for both fingers (non-blocking)."""
        with self._finger_lock:
            return self._finger_positions["left"], self._finger_positions["right"]

    def wait_for_gripper_controller(self, timeout=15.0):
        """Wait until the gripper_controller action server is available.
        The controller is spawned by the launch file; this method only waits.
        PID gains are declared in params/gripper_controller.yaml and applied
        at controller startup via the spawner's --param-file argument."""
        self.logger.info("[GRIPPER] Waiting for gripper_controller action server...")
        ready = self._gripper_action_client.wait_for_server(timeout_sec=timeout)
        if ready:
            self.logger.info("[GRIPPER] gripper_controller action server is ready")
        else:
            self.logger.warn(
                "[GRIPPER] Timed out waiting for gripper_controller action server"
            )
        return ready

    def _send_gripper_trajectory(
        self, left_pos, duration_sec=0.5, timeout=5.0
    ):
        """Send a gripper trajectory goal and wait for completion. Returns True on success.
        Only commands left_finger_joint; right finger follows via mimic."""
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = self._gripper_joint_names
        point = JointTrajectoryPoint()
        point.positions = [float(left_pos)]
        point.time_from_start = Duration(
            sec=int(duration_sec), nanosec=int((duration_sec % 1) * 1e9)
        )
        goal.trajectory.points = [point]

        self.logger.info(
            f"[GRIPPER] Sending trajectory: left={left_pos:.4f}, duration={duration_sec}s"
        )

        send_future = self._gripper_action_client.send_goal_async(goal)
        start = time.time()
        while not send_future.done() and time.time() - start < timeout:
            time.sleep(0.01)

        if not send_future.done():
            self.logger.warn("[GRIPPER] Timeout sending goal")
            return False

        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.logger.warn("[GRIPPER] Goal rejected by gripper_controller")
            return False

        self.logger.info("[GRIPPER] Goal accepted, waiting for execution...")
        result_future = goal_handle.get_result_async()
        while not result_future.done() and time.time() - start < timeout:
            time.sleep(0.01)

        if not result_future.done():
            self.logger.warn("[GRIPPER] Timeout waiting for trajectory execution")
            return False

        result = result_future.result()
        if result is None:
            self.logger.warn("[GRIPPER] No result from trajectory execution")
            return False
        error_code = result.result.error_code
        success = error_code == FollowJointTrajectory.Result.SUCCESSFUL
        left_pos_after, right_pos_after = self._read_both_finger_positions()
        self.logger.info(
            f"[GRIPPER] Result: error_code={error_code}, success={success}, "
            f"left={left_pos_after}, right={right_pos_after}"
        )
        return success

    def gripper_close(self, position=0.035):
        """Close gripper via FollowJointTrajectory action.
        Commands both finger joints to the same position.
        0.0=open, 0.035=closed."""
        left_pos, right_pos = self._read_both_finger_positions()
        self.logger.info(
            f"[GRIPPER] Closing to {position}: "
            f"current left={left_pos}, right={right_pos}"
        )
        self._gripper_desired_position = position
        self._send_gripper_trajectory(position, duration_sec=0.8)
        # Always set grasping=True — physical validation is done in GRASP lift test
        self.grasping = True
        return True

    def gripper_open(self, position=0.0):
        """Open gripper via FollowJointTrajectory action.
        0.0=open, 0.035=closed."""
        left_pos, right_pos = self._read_both_finger_positions()
        self.logger.info(
            f"[GRIPPER] Opening to {position}: "
            f"current left={left_pos}, right={right_pos}"
        )
        self._gripper_desired_position = position
        self._send_gripper_trajectory(position, duration_sec=0.3)
        self.grasping = False
        return True

    def conveyor_set_power(self, power: float, timeout: float = 2.0) -> bool:
        """Set conveyor belt power (0.0 = stop, 100.0 = full speed).
        Returns True if service call succeeded."""
        if not self._conveyor_client.wait_for_service(timeout_sec=timeout):
            self.logger.warn("[CONVEYOR] Service /conveyor/control not available")
            return False
        req = ConveyorBeltControl.Request()
        req.power = float(power)
        future = self._conveyor_client.call_async(req)
        # Spin until result (non-blocking, brief wait)
        start = time.time()
        while not future.done() and time.time() - start < timeout:
            time.sleep(0.01)
        if future.done():
            result = future.result()
            if result is None:
                self.logger.warn(
                    f"[CONVEYOR] Service returned no result (power={power})"
                )
                return False
            action = "STOPPED" if power == 0.0 else f"SET to {power}%"
            self.logger.info(f"[CONVEYOR] Belt {action} (success={result.success})")
            self._conveyor_stopped = power == 0.0
            return result.success
        self.logger.warn(f"[CONVEYOR] Service call timed out (power={power})")
        return False

    def conveyor_stop(self) -> bool:
        """Stop the conveyor belt."""
        return self.conveyor_set_power(0.0)

    def conveyor_resume(self) -> bool:
        """Resume the conveyor belt at full speed."""
        return self.conveyor_set_power(100.0)

    def _set_grasp_branch_path_constraints(self):
        """Pin the grasp to a single, front-facing, elbow-up IK branch.

        A bare pose goal lets OMPL choose any of the UR5's 8 IK branches *and*
        any ±2π joint-wrapped variant. Two of those freedoms cause the arm to
        "spin around" and swipe the cube instead of descending onto it:
          * wrist_3 is a redundant roll for a symmetric top-down gripper, so the
            planner is free to wind it through full revolutions.
          * shoulder_pan can reach the same Cartesian point from behind, sweeping
            the arm through the cube on the way.
        Bounding elbow (up), shoulder_pan and wrist_3 with JointConstraints
        narrows OMPL's sampling to the nearby HOME-side branch. JointConstraints
        only tighten sampling bounds, so RRTConnect handles them cleanly (unlike
        Cartesian position/orientation path constraints).
        """
        # Pick side: every valid cube sits roughly straight ahead (pan ≈ 0), but
        # the cube's arm-frame Y varies cycle to cycle (it can park on either the
        # +Y or -Y side of the belt). A top-down grasp at +Y wants wrist_2 near a
        # different solution than one at -Y, so a hard wrist_2 band (as used in the
        # shared branch helper) makes OMPL's *goal* sampler reject >80% of states
        # for one of the two sides — the plan comes back empty and the arm never
        # descends. We therefore pin only elbow-up (belt clearance), shoulder_pan
        # (anti-sweep) and wrist_3 (anti-±2π-wind) here and let wrist_2 take
        # whichever top-down solution the actual cube Y needs.
        req = self.moveit2_robot0._MoveIt2__move_action_goal.request
        req.path_constraints.joint_constraints.clear()

        elbow = JointConstraint()
        elbow.joint_name = "arm1/elbow_joint"
        elbow.position = 1.57
        elbow.tolerance_above = 1.57
        elbow.tolerance_below = 1.47
        elbow.weight = 1.0
        req.path_constraints.joint_constraints.append(elbow)

        pan = JointConstraint()
        pan.joint_name = "arm1/shoulder_pan_joint"
        pan.position = 0.0
        pan.tolerance_above = 1.2
        pan.tolerance_below = 1.2
        pan.weight = 1.0
        req.path_constraints.joint_constraints.append(pan)

        # Wrist 1 near its nominal top-down value (≈ -1.57, as in
        # SAFE_INTERMEDIATE_JOINTS). wrist_1 is the tool-pitch compensation: for a
        # straight-down grasp it tracks the reach distance (shoulder_lift), not the
        # cube's Y side, so it stays in a tight band cycle to cycle. Left unbounded
        # it is the one wrist OMPL is free to wind a full turn one way and back
        # again on the way to the above-cube pose (the "wrist_1 flips around" spin).
        # A ±1.5 rad band [-3.07, -0.07] covers all real reach/tilt variation while
        # forbidding the ±2π wind and the opposite-sign flip. Unlike wrist_2 (which
        # genuinely differs between +Y and -Y cubes and must stay free), bounding
        # wrist_1 does not starve the goal sampler.
        wrist1 = JointConstraint()
        wrist1.joint_name = "arm1/wrist_1_joint"
        wrist1.position = -1.57
        wrist1.tolerance_above = 1.5
        wrist1.tolerance_below = 1.5
        wrist1.weight = 1.0
        req.path_constraints.joint_constraints.append(wrist1)

        wrist3 = JointConstraint()
        wrist3.joint_name = "arm1/wrist_3_joint"
        wrist3.position = 0.0
        wrist3.tolerance_above = 2.0
        wrist3.tolerance_below = 2.0
        wrist3.weight = 1.0
        req.path_constraints.joint_constraints.append(wrist3)

    def _set_place_branch_path_constraints(self):
        """Lightly pin the belt2 descent to the elbow-up, belt2-side branch.

        We arrive at this move already sitting exactly on PLACE_TRANSFER_JOINTS
        (pan=π, elbow-up), so we only need to stop OMPL from leaving that branch —
        not pin every wrist. Bounding just the elbow (up, anti-collision) and the
        shoulder_pan (belt2 side, anti-wind) is enough. The wrist_2/wrist_3 bounds
        used for the pick are deliberately omitted here: they add nothing for
        belt-collision safety (gripper-down is enforced by the goal quaternion) but
        over-narrow OMPL so the reach out to belt2 (X≈-0.66) often finds no IK
        solution — the arm then fails to plan and carries the cube away unplaced.
        A wider ±1.5 rad pan band also gives the outward reach room to solve.
        """
        req = self.moveit2_robot0._MoveIt2__move_action_goal.request
        req.path_constraints.joint_constraints.clear()

        elbow = JointConstraint()
        elbow.joint_name = "arm1/elbow_joint"
        elbow.position = 1.57
        elbow.tolerance_above = 1.57
        elbow.tolerance_below = 1.47
        elbow.weight = 1.0
        req.path_constraints.joint_constraints.append(elbow)

        pan = JointConstraint()
        pan.joint_name = "arm1/shoulder_pan_joint"
        pan.position = 3.14159
        pan.tolerance_above = 1.5
        pan.tolerance_below = 1.5
        pan.weight = 1.0
        req.path_constraints.joint_constraints.append(pan)

    def _set_elbow_up_only_path_constraint(self):
        """Elbow-up bound with NO shoulder_pan limit, for the wide HOME sweep.

        The return from belt2 to home crosses the full shoulder_pan range
        (≈π → 0), so the pan-bounded grasp/place constraints cannot be used here.
        But without *any* path constraint, RRTConnect is free to plan a joint-space
        sweep in which the elbow sags mid-path, dropping the forearm/gripper into
        belt2; the controller then aborts on path tolerance and the arm goes limp
        ("falls into the conveyor"). Bounding only the elbow positive keeps the
        whole sweep high while leaving pan free to rotate all the way back.
        """
        req = self.moveit2_robot0._MoveIt2__move_action_goal.request
        req.path_constraints.joint_constraints.clear()

        elbow = JointConstraint()
        elbow.joint_name = "arm1/elbow_joint"
        elbow.position = 1.57  # centre of elbow-up range
        elbow.tolerance_above = 1.57  # allows up to ~π rad
        elbow.tolerance_below = 1.47  # allows down to ~0.1 rad (strictly positive)
        elbow.weight = 1.0
        req.path_constraints.joint_constraints.append(elbow)

    def _clear_path_constraints(self):
        """Remove all path constraints."""
        req = self.moveit2_robot0._MoveIt2__move_action_goal.request
        req.path_constraints.joint_constraints.clear()
        req.path_constraints.position_constraints.clear()
        req.path_constraints.orientation_constraints.clear()


class Setup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["home"])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: SETUP] ========== ENTERING SETUP STATE =========="
        )

        # Wait for MoveIt planning service to become available before attempting any moves
        self.robot_controller.logger.info(
            "[STATE: SETUP] Waiting for MoveIt planning service..."
        )
        for i in range(40):
            svc_ready = self.robot_controller.moveit2_robot0._plan_kinematic_path_service.wait_for_service(
                timeout_sec=0.5
            )
            if svc_ready:
                self.robot_controller.logger.info(
                    "[STATE: SETUP] MoveIt planning service is ready!"
                )
                break
            self.robot_controller.logger.info(
                f"[STATE: SETUP] Waiting for MoveIt... ({i + 1}/40)"
            )

        # Resolve GRASP_Y_ARM now that the executor is spinning and TF is live.
        self.robot_controller._init_grasp_y_arm()

        # Add in collision objects for conveyor belts and base for MoveIt planning
        collision_pub = (
            self.robot_controller.moveit2_robot0._MoveIt2__collision_object_publisher
        )

        for belt_id, belt_x_arm in [
            ("conveyor_belt1", 0.65),
            ("conveyor_belt2", -0.66),
        ]:
            co = CollisionObject()
            co.id = belt_id
            co.header.frame_id = "arm1/base_link"
            co.header.stamp = self.robot_controller.get_clock().now().to_msg()

            box = SolidPrimitive()
            box.type = SolidPrimitive.BOX
            # Collision box is intentionally shorter than the physical belt so
            # wrist/forearm links at the grasp pose don't trigger collision
            # avoidance before the gripper reaches cube height.
            # Physical belt surface is at z≈-0.015m (arm frame); box top is at
            # z = -0.130 + 0.06 = -0.070m, giving ~55mm clearance below the
            # belt surface for the arm to approach without early termination.
            box.dimensions = [0.26, 4.0, 0.12]
            co.primitives = list(co.primitives)
            co.primitives.append(box)

            pose = Pose()
            pose.position.x = belt_x_arm
            pose.position.y = -0.70
            pose.position.z = -0.130
            pose.orientation.w = 1.0
            co.primitive_poses = list(co.primitive_poses)
            co.primitive_poses.append(pose)

            co.operation = CollisionObject.ADD
            collision_pub.publish(co)
            self.robot_controller.logger.info(
                f"[STATE: SETUP] Added collision object for {belt_id} at X={belt_x_arm}"
            )

        base_cyl = CollisionObject()
        base_cyl.id = "robot_base"
        base_cyl.header.frame_id = "arm1/base_link"
        base_cyl.header.stamp = self.robot_controller.get_clock().now().to_msg()

        cyl = SolidPrimitive()
        cyl.type = SolidPrimitive.CYLINDER
        cyl.dimensions = [
            0.40,
            0.18,
        ]  # height=0.40m, radius=0.18m (larger than UR5 base)
        base_cyl.primitives = [cyl]

        cyl_pose = Pose()
        cyl_pose.position.x = 0.0
        cyl_pose.position.y = 0.0
        cyl_pose.position.z = (
            -0.20
        )  # center: covers pedestal below base_link down to ground
        cyl_pose.orientation.w = 1.0
        base_cyl.primitive_poses = [cyl_pose]

        base_cyl.operation = CollisionObject.ADD
        collision_pub.publish(base_cyl)
        self.robot_controller.logger.info(
            "[STATE: SETUP] Added collision cylinder for robot base (r=0.18m, h=0.40m)"
        )

        # Wait for gripper_controller to be fully spawned and active
        self.robot_controller.wait_for_gripper_controller(timeout=20.0)

        self.robot_controller.logger.info("[STATE: SETUP] Opening gripper")
        self.robot_controller.gripper_open()
        time.sleep(0.5)  # Give controller time to process first command

        # Verify gripper actually responded
        finger_pos = self.robot_controller._read_finger_position()
        self.robot_controller.logger.info(
            f"[STATE: SETUP] Finger position after open: {finger_pos}"
        )
        self.robot_controller.logger.info(
            "[STATE: SETUP] Setup complete, transitioning to HOME"
        )
        return "home"


HOME_JOINT_POSITIONS = [0.0, -1.5447, 0.5447, -0.03, 1.18, 0.0]
# Elbow-up waypoint on the same IK branch as HOME (wrist_2=1.57 ≈ HOME wrist_2=1.18,
# avoids a ~160° wrist swing that would let the planner pick a different solution branch).
SAFE_INTERMEDIATE_JOINTS = [0.0, -1.57, 1.57, -1.57, 1.57, 0.0]
# Mirror of SAFE_INTERMEDIATE_JOINTS rotated 180° at the shoulder so the same
# high elbow-up silhouette hovers over belt2 (the -X place side). Routing the
# GRASP->PLACE traversal through SAFE_INTERMEDIATE_JOINTS then this config turns
# the unavoidable 180° base-crossing into a pure shoulder_pan sweep held high
# above the base, instead of letting RRTConnect arc low through belt1 where the
# next cube is already approaching.
PLACE_TRANSFER_JOINTS = [3.14159, -1.57, 1.57, -1.57, 1.57, 0.0]


class Home(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["wait"])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        # Keep the elbow up for the whole return sweep so the forearm/gripper
        # cannot sag into belt2 mid-path (which would abort the controller and
        # let the arm fall limp). Pan is left free so the sweep can rotate all
        # the way back from the belt2 side (≈π) to the pick side (0).
        self.robot_controller._set_elbow_up_only_path_constraint()

        self.robot_controller.logger.info(
            f"[STATE: HOME] Moving to safe elbow up position: {SAFE_INTERMEDIATE_JOINTS}"
        )
        self.robot_controller.moveit2_robot0.move_to_configuration(
            joint_positions=SAFE_INTERMEDIATE_JOINTS, cartesian=False
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        self.robot_controller.logger.info(
            f"[STATE: HOME] Moving to home joint positions: {HOME_JOINT_POSITIONS}"
        )
        self.robot_controller.moveit2_robot0.move_to_configuration(
            joint_positions=HOME_JOINT_POSITIONS, cartesian=False
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Sweep complete — drop the constraint so later states plan freely.
        self.robot_controller._clear_path_constraints()

        self.robot_controller.logger.info(
            "[STATE: HOME] Home position reached, resuming conveyor"
        )
        self.robot_controller.conveyor_resume()
        return "wait"


class Wait(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["approach"])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: WAIT] Scanning for approaching cubes..."
        )
        locked_cube = None  # name of the cube we are tracking

        while True:
            if locked_cube is None:
                # Scan for the best cube (active zone first, then closest incoming)
                cube_name, cube_transform = self.robot_controller.find_target_cube()
                if cube_name:
                    cube_y = cube_transform.transform.translation.y
                    distance = self.robot_controller.GRASP_Y_WORLD - cube_y
                    # Lock cubes that are still approaching (distance < 2.5) OR
                    # already sitting in the active zone right in front of the
                    # robot (distance down to -GRASP_ZONE_BACK). The cube_y > 0.5
                    # floor rejects cubes that have not really spawned on the belt.
                    if (
                        -self.robot_controller.GRASP_ZONE_BACK < distance < 2.5
                        and cube_y > 0.5
                    ):
                        locked_cube = cube_name
                        self.robot_controller.target_cube_name = cube_name
                        self.robot_controller.target_cube_x = (
                            cube_transform.transform.translation.x
                        )
                        self.robot_controller.target_cube_y = cube_y
                        self.robot_controller.target_cube_z = (
                            cube_transform.transform.translation.z
                        )
                        eta = distance / max(self.robot_controller.CONVEYOR_SPEED, 0.01)
                        zone = "ACTIVE" if distance <= 0.15 else "approaching"
                        self.robot_controller.logger.info(
                            f"[STATE: WAIT] Locked onto {cube_name} at Y={cube_y:.3f}m, "
                            f"distance={distance:.3f}m ({zone}), ETA={eta:.1f}s"
                        )
            else:
                # Track the locked cube by name
                try:
                    tf = self.robot_controller.tf_buffer.lookup_transform(
                        "world",
                        locked_cube,
                        rclpy.time.Time(),
                        timeout=rclpy.duration.Duration(seconds=0.1),
                    )
                    cube_y = tf.transform.translation.y
                    distance = self.robot_controller.GRASP_Y_WORLD - cube_y

                    if distance <= -self.robot_controller.GRASP_ZONE_BACK:
                        # Cube has ridden fully past the reachable band — reset
                        # and scan for the next one.
                        self.robot_controller.logger.warn(
                            f"[STATE: WAIT] {locked_cube} left reachable zone "
                            f"(Y={cube_y:.3f}, dist={distance:.3f}), resetting"
                        )
                        locked_cube = None
                    elif distance <= 0.15:
                        # Within the active/stop window (down to -GRASP_ZONE_BACK):
                        # stop the belt and go grasp. Covers both a cube that
                        # arrived normally and one already parked in front.
                        self.robot_controller.logger.info(
                            f"[STATE: WAIT] {locked_cube} in active zone "
                            f"(dist={distance:.3f}) — stopping conveyor"
                        )
                        self.robot_controller.conveyor_stop()
                        return "approach"
                except Exception:
                    # Lost TF for locked cube — reset
                    self.robot_controller.logger.warn(
                        f"[STATE: WAIT] Lost TF for {locked_cube}, resetting"
                    )
                    locked_cube = None

            time.sleep(0.05)


class ApproachObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["approached", "failed"])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: APPROACH] ========== PRE-POSITIONING FOR GRASP =========="
        )

        # Get latest cube position
        try:
            latest_tf = self.robot_controller.tf_buffer.lookup_transform(
                "world",
                self.robot_controller.target_cube_name,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.2),
            )
            cube_x = latest_tf.transform.translation.x
            cube_y = latest_tf.transform.translation.y
            cube_z = latest_tf.transform.translation.z
        except Exception as e:
            self.robot_controller.logger.error(
                f"[STATE: APPROACH] Failed to acquire cube TF: {e}"
            )
            return "failed"

        # Compute arm-frame X via TF (direct lookup)
        cube_arm = self.robot_controller.get_pose_in_base_frame(
            self.robot_controller.target_cube_name, timeout_sec=0.2
        )
        if cube_arm is None:
            self.robot_controller.logger.error(
                "[STATE: APPROACH] TF arm1/base_link←cube failed"
            )
            return "failed"
        target_x_arm = max(
            self.robot_controller.MIN_TARGET_X_ARM,
            min(self.robot_controller.MAX_TARGET_X_ARM, cube_arm[0]),
        )

        # Phase 1: Move to READY position above conveyor — high enough to clear cubes.
        # When the conveyor is already stopped (cube parked by WAIT), use the cube's
        # actual arm-frame Y so Phase 1 pre-positions directly above the cube.
        # This avoids asking Phase 4's cartesian move to travel up to 0.5 m back,
        # which frequently fails and causes the arm to descend at the wrong Y.
        if self.robot_controller._conveyor_stopped:
            ready_y_arm = cube_arm[1]
            self.robot_controller.logger.info(
                f"[STATE: APPROACH] Cube parked — using cube arm-Y={ready_y_arm:.3f} for Phase 1"
            )
        else:
            ready_y_arm = self.robot_controller.GRASP_Y_ARM
        ready_z_arm = self.robot_controller.READY_Z_ARM  # well above cube height
        ready_pos = [target_x_arm, ready_y_arm, ready_z_arm]

        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Cube {self.robot_controller.target_cube_name}: "
            f"world=({cube_x:.3f}, {cube_y:.3f}, {cube_z:.3f}) "
            f"arm=({cube_arm[0]:.3f}, {cube_arm[1]:.3f}, {cube_arm[2]:.3f})"
        )
        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Moving to ready position: {ready_pos}"
        )

        self.robot_controller.gripper_open()

        # Brief settle so TF reflects the parked cube position before we read it
        if self.robot_controller._conveyor_stopped:
            time.sleep(0.15)

        # Pin the grasp IK branch for the ready move too, not just the descent.
        # If Phase 1 pre-positions on an arbitrary branch (elbow-down or a wrist
        # flip), Phases 4-5 then have to recover onto the grasp branch, which
        # shows up as the arm wandering/re-orienting just before it descends.
        # Constraining here makes Phase 1 land on the same branch the descent
        # needs, so the descent is a clean straight drop. Cleared on every exit.
        self.robot_controller._set_grasp_branch_path_constraints()

        self.robot_controller.moveit2_robot0.move_to_pose(
            position=ready_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=False,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller.logger.info(
            "[STATE: APPROACH] Ready position reached, waiting for cube..."
        )

        # Phase 2: Wait for cube to enter trigger zone.
        # If the conveyor was already stopped in WAIT (cube parked), skip straight
        # to Phase 3 — no need to wait for the cube to arrive.
        trigger_y = self.robot_controller.GRASP_Y_WORLD - 0.15
        hard_miss_y = self.robot_controller.GRASP_Y_WORLD + 0.25
        timeout = 30.0
        start_time = time.time()
        last_log_time = 0.0
        last_tracking_warn_time = 0.0

        if self.robot_controller._conveyor_stopped:
            self.robot_controller.logger.info(
                "[STATE: APPROACH] Conveyor already stopped (cube parked) — skipping trigger wait"
            )
        else:
            self.robot_controller.logger.info(
                f"[STATE: APPROACH] Trigger at Y>={trigger_y:.3f}m, miss at Y>{hard_miss_y:.3f}m"
            )
            # Wait for cube to reach trigger zone
            while True:
                if time.time() - start_time >= timeout:
                    self.robot_controller.logger.warn(
                        "[STATE: APPROACH] Timeout waiting for cube"
                    )
                    self.robot_controller._clear_path_constraints()
                    return "failed"
                try:
                    current_tf = self.robot_controller.tf_buffer.lookup_transform(
                        "world",
                        self.robot_controller.target_cube_name,
                        rclpy.time.Time(),
                        timeout=rclpy.duration.Duration(seconds=0.05),
                    )
                    current_y = current_tf.transform.translation.y
                except Exception as e:
                    now = time.time()
                    if now - last_tracking_warn_time > 1.0:
                        self.robot_controller.logger.warn(
                            f"[STATE: APPROACH] Lost tracking: {e}"
                        )
                        last_tracking_warn_time = now
                    time.sleep(0.02)
                    continue

                if current_y < trigger_y:
                    now = time.time()
                    if now - last_log_time > 1.0:
                        distance = self.robot_controller.GRASP_Y_WORLD - current_y
                        self.robot_controller.logger.info(
                            f"[STATE: APPROACH] Waiting: cube Y={current_y:.3f}m, dist={distance:.3f}m"
                        )
                        last_log_time = now
                    time.sleep(0.02)
                    continue

                if current_y > hard_miss_y:
                    self.robot_controller.logger.warn(
                        f"[STATE: APPROACH] Cube passed gripper (Y={current_y:.3f}), missed!"
                    )
                    self.robot_controller._clear_path_constraints()
                    return "failed"

                # Cube reached trigger zone — stop conveyor
                self.robot_controller.conveyor_stop()
                time.sleep(0.15)  # let physics settle
                break

        # Phase 3: Get cube's EXACT stopped position via direct Gazebo query
        gz_pose = self.robot_controller._query_gz_model_pose(
            self.robot_controller.target_cube_name, timeout=1.0
        )
        if gz_pose is not None:
            exact_x, exact_y, exact_z = gz_pose
        else:
            # Fallback to TF
            try:
                stopped_tf = self.robot_controller.tf_buffer.lookup_transform(
                    "world",
                    self.robot_controller.target_cube_name,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.5),
                )
                exact_x = stopped_tf.transform.translation.x
                exact_y = stopped_tf.transform.translation.y
                exact_z = stopped_tf.transform.translation.z
            except Exception:
                self.robot_controller.logger.error(
                    "[STATE: APPROACH] Cannot get stopped cube position"
                )
                self.robot_controller._clear_path_constraints()
                self.robot_controller.conveyor_resume()
                return "failed"

        # Store stopped cube world pose for GRASP validation
        self.robot_controller._stopped_cube_world_pose = (exact_x, exact_y, exact_z)

        # Read the cube's settled yaw and build a top-down grasp orientation whose
        # finger gap is aligned with the cube faces. Cubes tumble to varying yaw on
        # the belt; with a fixed gripper yaw the fingers occasionally clip a corner
        # and shove the cube on the way down. Aligning to the nearest face (90°
        # symmetry) drops the fingers into the side clearances instead. Falls back
        # to the plain straight-down orientation if the yaw can't be read.
        cube_yaw = self.robot_controller._query_gz_model_yaw(
            self.robot_controller.target_cube_name, timeout=1.0
        )
        if cube_yaw is not None:
            grasp_quat = self.robot_controller._grasp_quat_for_cube_yaw(cube_yaw)
            self.robot_controller.logger.info(
                f"[STATE: APPROACH] Cube yaw={cube_yaw:.3f} rad → "
                f"aligned grasp quat={[round(q, 3) for q in grasp_quat]}"
            )
        else:
            grasp_quat = [1.0, 0.0, 0.0, 0.0]
            self.robot_controller.logger.warn(
                "[STATE: APPROACH] Could not read cube yaw — using straight-down grasp"
            )
        self.robot_controller.approach_grasp_quat = grasp_quat

        # Convert world pose to arm frame using the static TF offset.
        world_in_arm = self.robot_controller.get_pose_in_base_frame(
            "world", timeout_sec=0.5
        )
        if world_in_arm is not None:
            cube_in_arm = (
                world_in_arm[0] + exact_x,
                world_in_arm[1] + exact_y,
                world_in_arm[2] + exact_z,
            )
        else:
            # Fallback: direct TF lookup for the cube frame
            cube_in_arm = self.robot_controller.get_pose_in_base_frame(
                self.robot_controller.target_cube_name, timeout_sec=0.5
            )
        if cube_in_arm is None:
            self.robot_controller.logger.error(
                "[STATE: APPROACH] Cannot convert cube to arm frame"
            )
            self.robot_controller._clear_path_constraints()
            self.robot_controller.conveyor_resume()
            return "failed"

        grasp_x_arm = max(
            self.robot_controller.MIN_TARGET_X_ARM,
            min(self.robot_controller.MAX_TARGET_X_ARM, cube_in_arm[0]),
        )
        grasp_y_arm = cube_in_arm[1]
        grasp_z_arm = (
            cube_in_arm[2]
            + self.robot_controller.GRASP_Z_OFFSET
            + self.robot_controller.GRASP_BELT_CLEARANCE
        )

        self.robot_controller.approach_target_x_arm = grasp_x_arm
        self.robot_controller.approach_target_y_arm = grasp_y_arm
        self.robot_controller.approach_target_z_arm = grasp_z_arm

        grasp_pos = [grasp_x_arm, grasp_y_arm, grasp_z_arm]
        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Cube stopped at world "
            f"({exact_x:.3f}, {exact_y:.3f}, {exact_z:.3f})"
        )
        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Descending to grasp position: {grasp_pos}"
        )

        # Pin the grasp IK branch (elbow-up, front-facing pan, un-wound wrist_3)
        # for the Phase 4 "move above the cube" step so the arm arrives directly
        # over the cube on the correct branch, ready for a straight drop.
        self.robot_controller._set_grasp_branch_path_constraints()

        # Phase 4: move above the cube using joint-space planning.
        # This is significantly lighter and more stable than multi-waypoint
        # Cartesian planning under path constraints.
        above_pos = [grasp_x_arm, grasp_y_arm, ready_z_arm]
        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Moving above cube: {above_pos}"
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=above_pos,
            quat_xyzw=grasp_quat,
            cartesian=False,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Phase 5: descend onto the cube. Robust against the intermittent
        # "EE did not descend" failure that leaves the arm hovering and aborts the
        # pick before the gripper ever closes. We try several strategies and
        # verify the EE actually dropped after each:
        #   * Attempts 1..N-1: straight-DOWN Cartesian path (no path constraints).
        #     The arm is already above the cube on the elbow-up branch, so this is
        #     a clean vertical interpolation with no IK goal sampling. It can
        #     occasionally return a low-fraction path when the post-Phase-4 wrist
        #     configuration makes the vertical segment near-singular, so before
        #     each retry we re-establish the above-cube pose to re-seed a fresh
        #     starting configuration.
        #   * Final attempt: UNCONSTRAINED joint-space pose goal straight to the
        #     grasp pose. With no elbow-up path constraint, OMPL is free to pick
        #     the more-extended elbow IK a far/low grasp needs — succeeding where
        #     the constrained/Cartesian descent was marginal.
        descend_threshold = self.robot_controller.READY_Z_ARM - 0.10

        def _verify_descended():
            # The arm TF lags wait_until_executed() by tens of ms, so poll instead
            # of reading once (a single read can catch the stale pre-descent
            # height and falsely report failure). Accept as soon as the EE drops
            # below the ready band.
            last_z = None
            deadline = time.time() + 1.5
            while time.time() < deadline:
                ee = self.robot_controller.get_pose_in_base_frame(
                    "arm1/wrist_3_link", timeout_sec=0.2
                )
                if ee is not None:
                    last_z = ee[2]
                    if last_z <= descend_threshold:
                        return True, last_z
                time.sleep(0.05)
            return False, last_z

        MAX_DESCEND_ATTEMPTS = 3
        descended = False
        last_ee_z = None
        for d_attempt in range(1, MAX_DESCEND_ATTEMPTS + 1):
            # Re-establish the above-cube pose on retries so the descent starts
            # from a clean, repeatable configuration directly over the cube.
            if d_attempt > 1:
                self.robot_controller._set_grasp_branch_path_constraints()
                self.robot_controller.moveit2_robot0.move_to_pose(
                    position=above_pos,
                    quat_xyzw=grasp_quat,
                    cartesian=False,
                    frame_id="arm1/base_link",
                )
                self.robot_controller.moveit2_robot0.wait_until_executed()

            self.robot_controller._clear_path_constraints()
            use_cartesian = d_attempt < MAX_DESCEND_ATTEMPTS
            self.robot_controller.logger.info(
                f"[STATE: APPROACH] Descending to grasp "
                f"(attempt {d_attempt}/{MAX_DESCEND_ATTEMPTS}, "
                f"{'cartesian' if use_cartesian else 'joint-space'}): {grasp_pos}"
            )
            self.robot_controller.moveit2_robot0.move_to_pose(
                position=grasp_pos,
                quat_xyzw=grasp_quat,
                cartesian=use_cartesian,
                frame_id="arm1/base_link",
            )
            self.robot_controller.moveit2_robot0.wait_until_executed()

            descended, last_ee_z = _verify_descended()
            if last_ee_z is not None:
                self.robot_controller.logger.info(
                    f"[STATE: APPROACH] EE z={last_ee_z:.3f}, target={grasp_z_arm:.3f}"
                )
            if descended:
                break
            self.robot_controller.logger.warn(
                f"[STATE: APPROACH] EE did not descend on attempt "
                f"{d_attempt}/{MAX_DESCEND_ATTEMPTS} (ee_z={last_ee_z})"
            )

        if not descended:
            self.robot_controller.logger.warn(
                f"[STATE: APPROACH] EE did not descend after "
                f"{MAX_DESCEND_ATTEMPTS} attempts (ee_z={last_ee_z}) — aborting"
            )
            self.robot_controller._clear_path_constraints()
            self.robot_controller.conveyor_resume()
            return "failed"

        self.robot_controller.logger.info(
            "[STATE: APPROACH] At grasp position, ready to close"
        )
        return "approached"


class GraspObject(State):
    MAX_GRASP_ATTEMPTS = 3

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["grasped", "failed"])
        self.robot_controller = robot_controller

    def _requery_cube_pose(self, cube_name):
        """Re-read cube world position (cube is stationary — conveyor stopped)."""
        gz_pose = self.robot_controller._query_gz_model_pose(cube_name, timeout=1.0)
        if gz_pose is not None:
            return gz_pose
        tf_pose = self.robot_controller.get_cube_world_pose(cube_name, timeout_sec=0.5)
        return tf_pose

    def _readjust_to_cube(self, cube_name):
        """Open gripper, re-read cube position, move above then descend straight down."""
        self.robot_controller.gripper_open()
        time.sleep(0.15)

        # Return to the home-side safe config before re-attempting. A failed
        # descent often leaves the arm in a contorted pose the planner could not
        # finish; re-planning the next descent from there tends to fail the same
        # way. Resetting to the canonical elbow-up SAFE_INTERMEDIATE config gives
        # the planner a clean, known starting point ("rest the positioning") so
        # the retry descends fresh. The conveyor stays stopped, so the cube
        # remains parked and the re-read below is still valid.
        self.robot_controller.logger.info(
            "[STATE: GRASP] Returning to safe home config before retry"
        )
        self.robot_controller._set_elbow_up_only_path_constraint()
        self.robot_controller.moveit2_robot0.move_to_configuration(
            joint_positions=SAFE_INTERMEDIATE_JOINTS, cartesian=False
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller._clear_path_constraints()

        # Get cube position directly in arm frame via TF
        cube_arm = self.robot_controller.get_pose_in_base_frame(
            cube_name, timeout_sec=0.5
        )
        if cube_arm is None:
            # Fallback: world pose + TF conversion
            world_pose = self._requery_cube_pose(cube_name)
            if world_pose is None:
                self.robot_controller.logger.warn(
                    "[STATE: GRASP] Cannot re-locate cube for retry"
                )
                return False
            self.robot_controller._stopped_cube_world_pose = world_pose
            world_in_arm = self.robot_controller.get_pose_in_base_frame(
                "world", timeout_sec=0.5
            )
            if world_in_arm is None:
                self.robot_controller.logger.warn("[STATE: GRASP] TF fallback failed")
                return False
            cube_arm = (
                world_in_arm[0] + world_pose[0],
                world_in_arm[1] + world_pose[1],
                world_in_arm[2] + world_pose[2],
            )
        else:
            # Update stored world pose from TF too
            world_pose = self._requery_cube_pose(cube_name)
            if world_pose is not None:
                self.robot_controller._stopped_cube_world_pose = world_pose

        grasp_x = max(
            self.robot_controller.MIN_TARGET_X_ARM,
            min(self.robot_controller.MAX_TARGET_X_ARM, cube_arm[0]),
        )
        grasp_y = cube_arm[1]
        grasp_z = (
            cube_arm[2]
            + self.robot_controller.GRASP_Z_OFFSET
            + self.robot_controller.GRASP_BELT_CLEARANCE
        )

        # Update stored approach target for the lift test
        self.robot_controller.approach_target_x_arm = grasp_x
        self.robot_controller.approach_target_y_arm = grasp_y
        self.robot_controller.approach_target_z_arm = grasp_z

        wp = self.robot_controller._stopped_cube_world_pose
        self.robot_controller.logger.info(
            f"[STATE: GRASP] Readjusted: cube world="
            f"({wp[0]:.3f},{wp[1]:.3f},{wp[2]:.3f}) "
            f"→ arm=({grasp_x:.3f},{grasp_y:.3f},{grasp_z:.3f})"
        )

        # Re-read the cube yaw so the retry descent stays aligned with the cube
        # faces (same reasoning as the initial approach). Fall back to the
        # orientation computed during APPROACH, then to plain straight-down.
        cube_yaw = self.robot_controller._query_gz_model_yaw(cube_name, timeout=1.0)
        if cube_yaw is not None:
            grasp_quat = self.robot_controller._grasp_quat_for_cube_yaw(cube_yaw)
        else:
            grasp_quat = getattr(
                self.robot_controller, "approach_grasp_quat", [1.0, 0.0, 0.0, 0.0]
            )

        # Move above
        above_z = self.robot_controller.READY_Z_ARM
        self.robot_controller._set_grasp_branch_path_constraints()
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=[grasp_x, grasp_y, above_z],
            quat_xyzw=grasp_quat,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Descend straight down
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=[grasp_x, grasp_y, grasp_z],
            quat_xyzw=grasp_quat,
            cartesian=False,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller._clear_path_constraints()
        return True

    def _attempt_grasp(self, cube_name, z_before):
        """Close gripper, lift, validate. Returns True on success, False on failure."""
        # Close gripper
        close_success = self.robot_controller.gripper_close(position=0.035)
        left_pos, right_pos = self.robot_controller._read_both_finger_positions()
        self.robot_controller.logger.info(
            f"[STATE: GRASP] After close cmd: left={left_pos}, "
            f"right={right_pos}, success={close_success}"
        )

        # Wait for fingers to physically close
        close_deadline = time.time() + 3.0
        while time.time() < close_deadline:
            left_pos, right_pos = self.robot_controller._read_both_finger_positions()
            if left_pos is not None and right_pos is not None:
                if left_pos > 0.005 or right_pos > 0.005:
                    self.robot_controller.logger.info(
                        f"[STATE: GRASP] Fingers closing: "
                        f"left={left_pos:.4f}, right={right_pos:.4f}"
                    )
                    break
            time.sleep(0.1)
        time.sleep(0.15)

        left_pos, right_pos = self.robot_controller._read_both_finger_positions()
        self.robot_controller.logger.info(
            f"[STATE: GRASP] Before lift: left={left_pos:.4f}, right={right_pos:.4f}"
        )

        # Lift test
        lift_z = min(0.42, self.robot_controller.approach_target_z_arm + 0.15)
        lift_pos = [
            self.robot_controller.approach_target_x_arm,
            self.robot_controller.approach_target_y_arm,
            lift_z,
        ]
        self.robot_controller.logger.info(
            f"[STATE: GRASP] Lifting to z_arm={lift_z:.3f}"
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=lift_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        time.sleep(0.15)

        # Validate via Gazebo / TF
        pose_after_gz = self.robot_controller._query_gz_model_pose(
            cube_name, timeout=1.0
        )
        if pose_after_gz is None:
            cube_tf_pose = self.robot_controller.get_cube_world_pose(
                cube_name, timeout_sec=0.3
            )
            if cube_tf_pose is not None:
                pose_after_gz = cube_tf_pose
        left_pos, right_pos = self.robot_controller._read_both_finger_positions()

        # EE world position
        ee_world = None
        try:
            ee_tf = self.robot_controller.tf_buffer.lookup_transform(
                "world",
                "arm1/wrist_3_link",
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.2),
            )
            ee_world = (
                ee_tf.transform.translation.x,
                ee_tf.transform.translation.y,
                ee_tf.transform.translation.z,
            )
        except Exception:
            pass

        self.robot_controller.logger.info(
            f"[STATE: GRASP] After lift: gz_pose={pose_after_gz}, ee={ee_world}, "
            f"left={left_pos}, right={right_pos}"
        )

        # Finger travel discriminates a real grasp from an empty close: a cube
        # stalls the fingers partway, while closing on air runs them to the
        # fully-closed command.
        fingers_empty = (
            left_pos is not None
            and left_pos >= self.robot_controller.GRASP_FINGER_EMPTY
        )
        fingers_on_object = (
            left_pos is not None
            and self.robot_controller.GRASP_FINGER_MIN
            < left_pos
            < self.robot_controller.GRASP_FINGER_EMPTY
        )

        # Finger-only fallback (no ground-truth cube pose from gz or TF).
        # Accept ONLY if the fingers stalled on an object; fully-closed fingers
        # here mean an empty gripper, not a successful grasp.
        if pose_after_gz is None:
            if fingers_on_object:
                self.robot_controller.logger.info(
                    "[STATE: GRASP] No cube pose; fingers stalled on object "
                    f"(left={left_pos:.4f}) — accepting grasp"
                )
                self.robot_controller.grasping = True
                return True
            self.robot_controller.logger.warn(
                "[STATE: GRASP] No cube pose and fingers "
                f"{'fully closed (empty)' if fingers_empty else 'not on object'} "
                f"(left={left_pos}) — grasp FAILED"
            )
            self.robot_controller.grasping = False
            return False

        z_after = pose_after_gz[2]
        z_gain = z_after - z_before

        ee_dist = None
        if ee_world is not None:
            dx = pose_after_gz[0] - ee_world[0]
            dy = pose_after_gz[1] - ee_world[1]
            dz = pose_after_gz[2] - ee_world[2]
            ee_dist = (dx**2 + dy**2 + dz**2) ** 0.5

        # Ground-truth confirmation: after the commanded +0.15 m lift a genuinely
        # grasped cube rises with the gripper (clear z gain) AND stays co-located
        # with the end effector. A cube left on the belt shows ~zero z gain and a
        # large EE distance. This pose-based check is the authoritative signal —
        # the 0.05 m gain threshold is well above sim/measurement noise yet far
        # below the 0.15 m lift a real grasp produces.
        close_enough = ee_dist is not None and ee_dist < 0.15
        lifted = z_gain > 0.05

        self.robot_controller.logger.info(
            f"[STATE: GRASP] z_gain={z_gain:.4f}, "
            f"ee_dist={'n/a' if ee_dist is None else round(ee_dist, 4)}, "
            f"close_enough={close_enough}, lifted={lifted}, "
            f"fingers_on_object={fingers_on_object}, fingers_empty={fingers_empty}"
        )

        # Fully-closed fingers mean nothing is held — reject even if the cube
        # happens to sit near the EE on the belt.
        if fingers_empty:
            self.robot_controller.logger.warn(
                "[STATE: GRASP] Fingers fully closed (empty) — cube NOT grasped"
            )
            self.robot_controller.grasping = False
            return False

        # Require the cube to have physically moved up with the gripper.
        if close_enough and lifted:
            self.robot_controller.grasping = True
            return True

        self.robot_controller.logger.warn(
            "[STATE: GRASP] Cube did not lift with gripper — grasp FAILED"
        )
        self.robot_controller.grasping = False
        return False

    def execute(self, userdata):
        cube_name = self.robot_controller.target_cube_name
        stopped_pose = getattr(self.robot_controller, "_stopped_cube_world_pose", None)
        z_before = stopped_pose[2] if stopped_pose else 0.20

        for attempt in range(1, self.MAX_GRASP_ATTEMPTS + 1):
            self.robot_controller.logger.info(
                f"[STATE: GRASP] ========== ATTEMPT {attempt}/{self.MAX_GRASP_ATTEMPTS} =========="
            )

            if attempt > 1:
                # Readjust: open gripper, re-read cube pose, re-descend
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] Retrying — conveyor still stopped, readjusting to {cube_name}"
                )
                if not self._readjust_to_cube(cube_name):
                    break  # Can't find cube anymore, give up
                # Refresh z_before from updated stopped pose
                stopped_pose = getattr(
                    self.robot_controller, "_stopped_cube_world_pose", None
                )
                z_before = stopped_pose[2] if stopped_pose else z_before

            if self._attempt_grasp(cube_name, z_before):
                # Keep conveyor stopped — arm still needs to travel to PLACE and back HOME.
                # It will be resumed at the end of the HOME state.
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] ✓ GRASP SUCCESS on attempt {attempt}"
                )
                return "grasped"

            self.robot_controller.logger.warn(
                f"[STATE: GRASP] ✗ Attempt {attempt} failed"
            )

        # All attempts exhausted
        self.robot_controller.grasping = False
        self.robot_controller.gripper_open()
        # raise arm slightly before next transition
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=[
                self.robot_controller.approach_target_x_arm,
                self.robot_controller.approach_target_y_arm,
                self.robot_controller.READY_Z_ARM,
            ],
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        # Do NOT resume conveyor here — HOME state will resume it once the arm
        # is back in a known safe configuration.
        self.robot_controller.logger.error(
            f"[STATE: GRASP] ✗ All {self.MAX_GRASP_ATTEMPTS} attempts FAILED for {cube_name}"
        )
        return "failed"


class PlaceObject(State):
    """Place the grasped cube onto conveyor_belt2 (the sink belt).

    Belt2 sits mirrored across arm1's base on the -X side:
        world (-0.67, 2.3, 0.08), yaw 180 deg, surface top ~ z=0.155 m.
    arm1 base_link is at world (0.18, 3.0, 0.17), yaw 0, so the place
    pose in arm1/base_link is roughly (-0.85, -0.08, ~0.04).
    """

    CUBE_HALF_HEIGHT = 0.0225  # 4.5 cm cubes
    GRASP_Z_OFFSET_PLACE = 0.030  # finger center below ee_link
    BELT_TOP_Z_ARM = -0.015  # belt2 surface (world 0.155) - arm base (world 0.17)
    PLACE_X_ARM = -0.66
    PLACE_Y_ARM = -0.08
    PLACE_CLEARANCE = 0.005  # cube bottom hovers above belt surface
    ABOVE_Z_ARM = 0.40  # safe travel height

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=["placed", "failed"])
        self.robot_controller = robot_controller
        # The grasp grips the UPPER portion of the cube: APPROACH descends the EE
        # to cube_z + GRASP_Z_OFFSET + GRASP_BELT_CLEARANCE, so the cube ends up
        # held GRASP_BELT_CLEARANCE (0.012 m) LOWER in the gripper than the EE
        # offset alone implies. The place height must add that same term, otherwise
        # the EE stops GRASP_BELT_CLEARANCE too low and drives the held cube into
        # belt2's collision surface — the cube jams, the gripper cannot fully open,
        # and the release check fails on every attempt even though the arm reached
        # the target. Including it lands the cube bottom PLACE_CLEARANCE above the
        # belt as intended.
        place_z = (
            self.BELT_TOP_Z_ARM
            + self.GRASP_Z_OFFSET_PLACE
            + self.robot_controller.GRASP_BELT_CLEARANCE
            + self.CUBE_HALF_HEIGHT
            + self.PLACE_CLEARANCE
        )
        self.place_pos = [self.PLACE_X_ARM, self.PLACE_Y_ARM, place_z]
        self.above_pos = [self.PLACE_X_ARM, self.PLACE_Y_ARM, self.ABOVE_Z_ARM]

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: PLACE] ========== ENTERING PLACE STATE =========="
        )
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Object to place: {self.robot_controller.target_cube_name}"
        )

        # Traverse from the pick side to belt2 through two high elbow-up
        # waypoints so the 180° base-crossing happens as a pure shoulder_pan
        # sweep held high above the base — never a low RRTConnect arc through
        # belt1 (where the next cube is already approaching).
        #   1. SAFE_INTERMEDIATE_JOINTS — canonical elbow-up high over the pick side
        #   2. PLACE_TRANSFER_JOINTS    — same silhouette rotated 180° over belt2
        # Gripper orientation is enforced via the goal quat_xyzw on the descent
        # below; do NOT add path_constraints here — they force OMPL into a
        # constrained state space that reliably fails with RRTConnect.
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Lifting through transfer waypoint (pick side): "
            f"{SAFE_INTERMEDIATE_JOINTS}"
        )
        self.robot_controller.moveit2_robot0.move_to_configuration(
            joint_positions=SAFE_INTERMEDIATE_JOINTS, cartesian=False
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        if not self.robot_controller.grasping:
            self.robot_controller.logger.error(
                "[STATE: PLACE] Lost object during lift to transfer waypoint."
            )
            self.robot_controller.gripper_open()
            return "failed"

        self.robot_controller.logger.info(
            f"[STATE: PLACE] Sweeping to transfer waypoint (belt2 side): "
            f"{PLACE_TRANSFER_JOINTS}"
        )
        # Cross the base from the pick side to belt2 as a sequence of small
        # shoulder_pan-ONLY steps. SAFE_INTERMEDIATE_JOINTS and
        # PLACE_TRANSFER_JOINTS differ in shoulder_pan ALONE (0 → π); every other
        # joint is identical. Commanding the full 180° in one move lets RRTConnect
        # wind the other joints into a spiral that can graze a singularity, and
        # pinning them with path constraints turns it into a hard constrained
        # plan that OMPL "solves" by shuffling shoulder_lift instead of the base —
        # leaving the arm folded above itself, unable to descend. Stepping the pan
        # in small increments makes each plan an almost-identical config: the only
        # valid motion is a short, near-straight base rotation, with no freedom to
        # spiral. No path constraints required.
        pan_start = SAFE_INTERMEDIATE_JOINTS[0]
        pan_goal = PLACE_TRANSFER_JOINTS[0]
        n_steps = 4
        for i in range(1, n_steps + 1):
            pan = pan_start + (pan_goal - pan_start) * i / n_steps
            waypoint = list(SAFE_INTERMEDIATE_JOINTS)
            waypoint[0] = pan
            self.robot_controller.logger.info(
                f"[STATE: PLACE] Base sweep step {i}/{n_steps} (shoulder_pan={pan:.3f})"
            )
            self.robot_controller.moveit2_robot0.move_to_configuration(
                joint_positions=waypoint, cartesian=False
            )
            self.robot_controller.moveit2_robot0.wait_until_executed()

        # Descend from the belt2-side transfer waypoint to the above-belt2 pose.
        # Pin the IK branch to the belt2 side (pan≈π, elbow-up, wrist_3 un-wound)
        # so this pose goal cannot leave the branch we are already in and wind the
        # arm around — the source of the wild planned movement on the belt2 drop.
        self.robot_controller._set_place_branch_path_constraints()
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Moving above belt2: {self.above_pos}"
        )

        outgoing_traj = None
        for attempt in range(1, 4):
            outgoing_traj = self.robot_controller.moveit2_robot0.plan(
                position=self.above_pos,
                quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                cartesian=False,
                frame_id="arm1/base_link",
            )
            if outgoing_traj is not None and len(outgoing_traj.points) > 0:
                break
            self.robot_controller.logger.warn(
                f"[STATE: PLACE] Planning attempt {attempt}/3 failed, retrying..."
            )

        # Fallback: if the branch-constrained plan never solved, drop the path
        # constraints and try again. We are already parked at PLACE_TRANSFER_JOINTS
        # directly over belt2, so an unconstrained descent here is short and safe —
        # far better than carrying the cube away unplaced and holding it forever.
        if outgoing_traj is None or len(outgoing_traj.points) == 0:
            self.robot_controller.logger.warn(
                "[STATE: PLACE] Constrained planning failed — retrying "
                "with path constraints cleared"
            )
            self.robot_controller._clear_path_constraints()
            for attempt in range(1, 4):
                outgoing_traj = self.robot_controller.moveit2_robot0.plan(
                    position=self.above_pos,
                    quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                    cartesian=False,
                    frame_id="arm1/base_link",
                )
                if outgoing_traj is not None and len(outgoing_traj.points) > 0:
                    break
                self.robot_controller.logger.warn(
                    f"[STATE: PLACE] Unconstrained attempt {attempt}/3 failed, "
                    "retrying..."
                )

        if outgoing_traj is None or len(outgoing_traj.points) == 0:
            self.robot_controller.logger.error(
                "[STATE: PLACE] All planning attempts failed, aborting"
            )
            self.robot_controller._clear_path_constraints()
            self.robot_controller.gripper_open()
            return "failed"
        self.robot_controller.moveit2_robot0.execute(outgoing_traj)
        self.robot_controller.moveit2_robot0.wait_until_executed()

        if not self.robot_controller.grasping:
            self.robot_controller.logger.error(
                "[STATE: PLACE] Lost object during traversal."
            )
            self.robot_controller.gripper_open()
            self.robot_controller._clear_path_constraints()
            return "failed"

        # Lower onto belt2 and release. Placement does NOT need to be precise:
        # belt2 immediately carries the cube away, so getting the cube near the
        # belt surface and opening the gripper is sufficient. We therefore:
        #   * descend with a STRAIGHT Cartesian drop (no constrained pose goal —
        #     the far/low belt2 point makes a joint-space goal under the branch
        #     constraints fail the same way the grasp descend did, leaving the arm
        #     hovering and never releasing),
        #   * try up to PLACE_MAX_ATTEMPTS times, accepting partial descents, and
        #   * ALWAYS open the gripper before leaving this state — whether placement
        #     succeeded or every attempt failed — so the arm never carries the cube
        #     back HOME still gripping it.
        self.robot_controller._clear_path_constraints()
        PLACE_MAX_ATTEMPTS = 3
        released = False
        for attempt in range(1, PLACE_MAX_ATTEMPTS + 1):
            self.robot_controller.logger.info(
                f"[STATE: PLACE] Lower+release attempt "
                f"{attempt}/{PLACE_MAX_ATTEMPTS}: {self.place_pos}"
            )
            # Straight vertical descent from directly above the drop point.
            self.robot_controller.moveit2_robot0.move_to_pose(
                position=self.place_pos,
                quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                cartesian=True,
                frame_id="arm1/base_link",
            )
            self.robot_controller.moveit2_robot0.wait_until_executed()

            # Release. Even if the descent only went partway, opening here drops
            # the cube onto / just above the belt — close enough for belt2 to take
            # it. Precision is intentionally not required.
            self.robot_controller.logger.info("[STATE: PLACE] Releasing object")
            self.robot_controller.gripper_open()
            time.sleep(0.4)  # let fingers physically open and the cube settle

            # Confirm the fingers actually opened (cube released). Fingers read
            # ~0.0 fully open, ~0.035 closed; a low reading means we let go.
            left_pos, right_pos = self.robot_controller._read_both_finger_positions()
            if left_pos is not None and right_pos is not None:
                if left_pos < 0.010 and right_pos < 0.010:
                    released = True
                    self.robot_controller.logger.info(
                        f"[STATE: PLACE] Released (fingers left={left_pos:.4f}, "
                        f"right={right_pos:.4f})"
                    )
                    break
                self.robot_controller.logger.warn(
                    f"[STATE: PLACE] Gripper still not open "
                    f"(left={left_pos:.4f}, right={right_pos:.4f}), "
                    f"attempt {attempt}/{PLACE_MAX_ATTEMPTS}"
                )
            else:
                # No finger feedback — assume the open command took effect.
                released = True
                break

        if not released:
            # Every attempt failed to confirm release — force the gripper open one
            # last time before handing back to HOME so the arm does not carry the
            # cube away. This satisfies "if it fails three placements it should
            # just open gripper before going home".
            self.robot_controller.logger.error(
                "[STATE: PLACE] Could not confirm release after "
                f"{PLACE_MAX_ATTEMPTS} attempts — forcing gripper open before HOME"
            )
            self.robot_controller.gripper_open()
            time.sleep(0.4)

        self.robot_controller.grasping = False

        # Retract back to above-belt2 altitude before handing control back
        # to HOME so the gripper does not catch the cube as belt2 moves it.
        # cartesian=True ensures a straight vertical lift rather than an arc
        # that could sweep through the just-placed cube.
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=self.above_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id="arm1/base_link",
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Clear the belt2-branch path constraints before returning so the HOME
        # state (which sweeps shoulder_pan back to 0) plans unconstrained.
        self.robot_controller._clear_path_constraints()

        self.robot_controller.logger.info(
            "[STATE: PLACE] Placed successfully on belt2; ready for next cube."
        )
        return "placed"


def run_smach(client):
    client.logger.info("========================================")
    client.logger.info("=== STARTING STATE MACHINE ===")
    client.logger.info("========================================")

    # Create the top level SMACH state machine.
    # The picknplace TRANSFER (instructs AMR) and IDLE (terminal) states have
    # been removed: rvc loops PLACE -> HOME indefinitely so arm1 keeps
    # shuttling cubes between belt1 and belt2.
    sm = StateMachine(outcomes=["succeeded", "aborted"])
    with sm:
        StateMachine.add(
            "SETUP", Setup(client), transitions={"home": "HOME"}
        )
        StateMachine.add(
            "HOME", Home(client), transitions={"wait": "WAIT"}
        )
        StateMachine.add(
            "WAIT", Wait(client), transitions={"approach": "APPROACH"}
        )
        StateMachine.add(
            "APPROACH",
            ApproachObject(client),
            transitions={"approached": "GRASP", "failed": "HOME"},
        )
        StateMachine.add(
            "GRASP",
            GraspObject(client),
            transitions={"grasped": "PLACE", "failed": "HOME"},
        )
        StateMachine.add(
            "PLACE",
            PlaceObject(client),
            transitions={"placed": "HOME", "failed": "HOME"},
        )

    client.logger.info("=== State machine configured, starting execution ===")
    # Execute SMACH plan
    sm.execute()


def main(args=None):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)

    robot_controller = RobotController(args_without_ros)
    robot_controller.get_logger().info("Robot Controller started")

    # Wait for MoveIt to be fully ready
    time.sleep(1.0)

    # Publish ready status
    ready_msg = Bool()
    ready_msg.data = True
    robot_controller.ready_publisher.publish(ready_msg)
    robot_controller.get_logger().info("✓ ARM1 Controller ready - MoveIt initialized")

    # Create and start the thread for running the state machine
    smach_thread = threading.Thread(target=run_smach, args=(robot_controller,))
    smach_thread.start()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(robot_controller)
    executor.spin()
    robot_controller.destroy_node()
    rclpy.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
