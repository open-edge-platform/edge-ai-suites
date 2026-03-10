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
# Desc: Controller program for ARM1
import sys
import subprocess
import threading
import time


# Third-Party Library Imports
import rclpy
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
from smach import State, StateMachine
from rclpy.parameter import Parameter
import tf2_ros

# Custom Module Imports
from robot_config import utils
from robots import ur5 as robot


class RobotController(Node):
    def __init__(self, args):
        super().__init__('ARM1Controller')
        self.last_pose = None
        self.cube_detected_time = None  # Track when cube was first detected
        # use_sim_time may already be declared by launch file parameters
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', True)
        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.declare_parameter('state', 'run')
        self.setup_qos_and_groups()

        self.setup_logging()
        self.logger.info("robot controller constructor")
        self.moveit2_robot0 = self.setup_moveit()

        self.grasping = False
        # Conveyor belt speed matching SDF max_velocity at 100% power
        self.conveyor_velocity_y = 0.12  # m/s in world Y direction

        # TF setup for cube tracking
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Target zone for cube detection (world frame Y coordinates)
        self.GRASP_Y_WORLD = 2.92     # Intercept shifted downstream to match real motion timing
        self.GRASP_Z_OFFSET = 0.030   # finger center is 0.030m BELOW ee_link
        self.CONVEYOR_SPEED = 0.12    # m/s (default, matches belt max_velocity)
        self.GRIPPER_CLOSE_TIME = 0.8  # seconds for gripper to fully close
        self.MIN_ETA = 2.0            # Minimum time to position arm (seconds)
        self.MAX_ETA = 20.0           # Maximum time to wait for cube (seconds)
        self.CUBE_LOCK_MAX_DISTANCE = 1.0  # Lock cubes with enough lead time
        self.CUBE_LOCK_MIN_Y = self.GRASP_Y_WORLD - self.CUBE_LOCK_MAX_DISTANCE
        self.READY_Z_ARM = 0.45
        self.MIN_TARGET_X_ARM = 0.35
        self.MAX_TARGET_X_ARM = 0.80

        # Subscribe to conveyor belt joint states to get real-time velocity
        self.conveyor_velocity_sub = self.create_subscription(
            JointState,
            '/world/default/model/conveyor_belt/joint_state',
            self.conveyor_velocity_callback,
            10
        )

        self._stopped_cube_world_pose = None  # Set in APPROACH, used in GRASP
        self.setup_subscriptions_and_services()

        # Derive GRASP_Y_ARM from TF (arm1/base_link Y offset from world)
        self._init_grasp_y_arm()

    def _init_grasp_y_arm(self):
        """Compute GRASP_Y_ARM using the live TF tree."""
        for _ in range(50):  # retry for up to 5s
            try:
                tf = self.tf_buffer.lookup_transform(
                    'arm1/base_link', 'world', rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.5),
                )
                # world origin in arm frame tells us the offset
                world_origin_in_arm = tf.transform.translation
                # GRASP_Y_WORLD expressed in arm1/base_link frame:
                self.GRASP_Y_ARM = (
                    world_origin_in_arm.y
                    + self.GRASP_Y_WORLD
                )
                self.logger.info(
                    f"GRASP_Y_ARM resolved via TF: {self.GRASP_Y_ARM:.4f}"
                )
                return
            except Exception:
                time.sleep(0.1)
        # Fallback — should never be needed once TF is up
        self.GRASP_Y_ARM = -0.08
        self.logger.warn(
            f"TF not ready, using fallback GRASP_Y_ARM={self.GRASP_Y_ARM}"
        )

    def get_pose_in_base_frame(self, target_frame, timeout_sec=0.5):
        """Return (x, y, z) of target_frame in arm1/base_link frame via TF.

        This is the standard ROS2 approach — let TF traverse the tree
        rather than manually subtracting hardcoded base coordinates.
        Returns None on failure.
        """
        try:
            transform = self.tf_buffer.lookup_transform(
                'arm1/base_link',
                target_frame,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception as e:
            self.logger.debug(
                f"TF lookup arm1/base_link←{target_frame} failed: {e}"
            )
            return None

    def get_cube_world_pose(self, cube_name, timeout_sec=0.1):
        """Return cube position tuple in world frame or None."""
        try:
            transform = self.tf_buffer.lookup_transform(
                'world',
                cube_name,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception:
            return None

    def cube_distance_to_ee(self, cube_name, timeout_sec=0.1):
        """Return euclidean distance from ee-area links to cube frame, or None.
        Uses world-frame lookups to avoid TF timestamp domain mismatch
        (arm uses sim_time, cube_controller uses wall_clock)."""
        cube_pose = self.get_cube_world_pose(cube_name, timeout_sec=timeout_sec)
        if cube_pose is None:
            return None

        ee_frame_candidates = [
            'arm1/wrist_3_link',
            'arm1/left_finger',
            'arm1/right_finger',
        ]

        best_distance = None
        for ee_frame in ee_frame_candidates:
            try:
                transform = self.tf_buffer.lookup_transform(
                    'world',
                    ee_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=timeout_sec),
                )
                t = transform.transform.translation
                dx = t.x - cube_pose[0]
                dy = t.y - cube_pose[1]
                dz = t.z - cube_pose[2]
                distance = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5
                if best_distance is None or distance < best_distance:
                    best_distance = distance
            except Exception:
                continue

        return best_distance

    def _query_gz_model_pose(self, model_name, timeout=0.5):
        """Query actual model pose directly from Gazebo via CLI.
        Returns (x, y, z) tuple or None."""
        try:
            result = subprocess.run(
                ["gz", "model", "-m", model_name, "--pose"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=timeout,
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.splitlines():
                if "[" in line and "]" in line:
                    coords = line.strip().strip('[]').split()
                    if len(coords) >= 3:
                        return (float(coords[0]), float(coords[1]), float(coords[2]))
        except Exception:
            pass
        return None

    def conveyor_velocity_callback(self, msg):
        """Update conveyor speed from belt joint state"""
        if msg.name and 'belt_joint' in msg.name[0] and msg.velocity:
            # Conveyor moves in Y direction, velocity is linear
            self.CONVEYOR_SPEED = abs(msg.velocity[0]) if msg.velocity[0] != 0 else 0.12
            # Only log significant changes
            if abs(self.CONVEYOR_SPEED - 0.12) > 0.01:
                self.logger.info(f"[CONVEYOR] Speed updated: {self.CONVEYOR_SPEED:.3f} m/s")

    def setup_qos_and_groups(self):
        self.qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.callback_group0 = MutuallyExclusiveCallbackGroup()
        self.client_cb_group0 = MutuallyExclusiveCallbackGroup()
        self.moveit_callback_group0 = MutuallyExclusiveCallbackGroup()
        time.sleep(1)

    def setup_moveit(self):
        return MoveIt2(
            node=self,
            joint_names=robot.joint_names('arm1/'),
            base_link_name=robot.base_link_name('arm1/'),
            end_effector_name=robot.end_effector_name('arm1/'),
            group_name=robot.MOVE_GROUP_ARM,
            callback_group=self.moveit_callback_group0,
            execute_via_moveit=False,
            ignore_new_calls_while_executing=True,
            namespace_prefix='/arm1/',
        )

    def setup_logging(self):
        self.logger = self.get_logger()
        self.logger.set_level(LoggingSeverity.INFO)

    def setup_subscriptions_and_services(self):
        # Ready status publisher - signals when arm controller and MoveIt are fully initialized
        self.ready_publisher = self.create_publisher(
            Bool,
            '/arm1/controller_ready',
            qos_profile=self.qos_profile,
        )

        # Gripper action client (JointTrajectoryController)
        self._gripper_action_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/arm1/gripper_controller/follow_joint_trajectory'
        )
        self._gripper_joint_names = [
            'arm1/left_finger_joint',
        ]

        # Gripper state tracking
        self._gripper_desired_position = 0.0  # 0.0=open, 0.035=closed

        # Persistent joint_states subscription for finger position monitoring
        # (avoids creating/destroying subscriptions in tight loops which causes stale reads)
        self._finger_positions = {'left': None, 'right': None}
        self._finger_lock = threading.Lock()
        self._joint_states_sub = self.create_subscription(
            JointState,
            '/arm1/joint_states',
            self._joint_states_callback,
            10
        )

        # Conveyor belt control service client
        self._conveyor_client = self.create_client(
            ConveyorBeltControl,
            '/conveyor/control'
        )
        self._conveyor_stopped = False

    def find_target_cube(self):
        """Find nearest cube approaching grasp point"""
        closest_cube = None
        closest_distance = float('inf')

        for i in range(5):
            cube_frame = f'cube_{i}'
            try:
                transform = self.tf_buffer.lookup_transform(
                    'world',
                    cube_frame,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.05)
                )

                cube_y = transform.transform.translation.y

                # Only cubes before grasp point (approaching)
                if cube_y < self.GRASP_Y_WORLD - 0.1:
                    distance_to_grasp = self.GRASP_Y_WORLD - cube_y
                    if distance_to_grasp < closest_distance:
                        closest_distance = distance_to_grasp
                        closest_cube = (cube_frame, transform)

            except Exception:
                continue

        return closest_cube if closest_cube else (None, None)

    def _joint_states_callback(self, msg):
        """Persistent callback to cache finger joint positions."""
        with self._finger_lock:
            for i, name in enumerate(msg.name):
                if 'left_finger_joint' in name:
                    self._finger_positions['left'] = msg.position[i]
                elif 'right_finger_joint' in name:
                    self._finger_positions['right'] = msg.position[i]

    def _read_finger_position(self):
        """Read cached left finger joint position (non-blocking)."""
        with self._finger_lock:
            return self._finger_positions['left']

    def _read_both_finger_positions(self):
        """Read cached positions for both fingers (non-blocking)."""
        with self._finger_lock:
            return self._finger_positions['left'], self._finger_positions['right']

    def wait_for_gripper_controller(self, timeout=15.0):
        """Wait until the gripper_controller action server is available.
        If not found, attempt to spawn it via controller_manager."""
        self.logger.info("[GRIPPER] Waiting for gripper_controller action server...")
        ready = self._gripper_action_client.wait_for_server(timeout_sec=timeout)
        if not ready:
            self.logger.warn("[GRIPPER] Not found, attempting to spawn gripper_controller...")
            try:
                subprocess.run(
                    ["ros2", "run", "controller_manager", "spawner",
                     "gripper_controller", "-c", f"/{self.arm_name}/controller_manager"],
                    capture_output=True, text=True, timeout=15,
                )
            except Exception as e:
                self.logger.warn(f"[GRIPPER] Spawn attempt failed: {e}")
            ready = self._gripper_action_client.wait_for_server(timeout_sec=timeout)
        if ready:
            self.logger.info("[GRIPPER] gripper_controller action server is ready")
            # Set high PID gains on the JointTrajectoryController for aggressive finger closing
            try:
                subprocess.run(
                    ["ros2", "param", "set", f"/{self.arm_name}/gripper_controller",
                     f"gains.{self.arm_name}__left_finger_joint.p", "100.0"],
                    capture_output=True, text=True, timeout=5,
                )
                subprocess.run(
                    ["ros2", "param", "set", f"/{self.arm_name}/gripper_controller",
                     f"gains.{self.arm_name}__left_finger_joint.i", "10.0"],
                    capture_output=True, text=True, timeout=5,
                )
                subprocess.run(
                    ["ros2", "param", "set", f"/{self.arm_name}/gripper_controller",
                     f"gains.{self.arm_name}__left_finger_joint.d", "1.0"],
                    capture_output=True, text=True, timeout=5,
                )
                self.logger.info("[GRIPPER] Set PID gains P=100 I=10 D=1 for left_finger")
            except Exception:
                pass
        else:
            self.logger.warn("[GRIPPER] Timed out waiting for gripper_controller action server")
        return ready

    def _send_gripper_trajectory(self, left_pos, right_pos, duration_sec=0.5, timeout=5.0):
        """Send a gripper trajectory goal and wait for completion. Returns True on success.
        Only commands left_finger_joint; right finger follows via mimic."""
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = self._gripper_joint_names
        point = JointTrajectoryPoint()
        point.positions = [float(left_pos)]
        point.time_from_start = Duration(
            sec=int(duration_sec),
            nanosec=int((duration_sec % 1) * 1e9)
        )
        goal.trajectory.points = [point]

        self.logger.info(
            f"[GRIPPER] Sending trajectory: left={left_pos:.4f}, right={right_pos:.4f}, "
            f"duration={duration_sec}s"
        )

        send_future = self._gripper_action_client.send_goal_async(goal)
        start = time.time()
        while not send_future.done() and time.time() - start < timeout:
            time.sleep(0.01)

        if not send_future.done():
            self.logger.warn("[GRIPPER] Timeout sending goal")
            return False

        goal_handle = send_future.result()
        if not goal_handle.accepted:
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
        error_code = result.result.error_code
        success = (error_code == FollowJointTrajectory.Result.SUCCESSFUL)
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
        self._send_gripper_trajectory(position, position, duration_sec=0.8)
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
        self._send_gripper_trajectory(position, position, duration_sec=0.3)
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
            action = "STOPPED" if power == 0.0 else f"SET to {power}%"
            self.logger.info(f"[CONVEYOR] Belt {action} (success={result.success})")
            self._conveyor_stopped = (power == 0.0)
            return result.success
        self.logger.warn(f"[CONVEYOR] Service call timed out (power={power})")
        return False

    def conveyor_stop(self) -> bool:
        """Stop the conveyor belt."""
        return self.conveyor_set_power(0.0)

    def conveyor_resume(self) -> bool:
        """Resume the conveyor belt at full speed."""
        return self.conveyor_set_power(100.0)


class Setup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: SETUP] "
            "========== ENTERING SETUP STATE =========="
        )

        # Wait for MoveIt planning service to become available before attempting any moves
        self.robot_controller.logger.info("[STATE: SETUP] Waiting for MoveIt planning service...")
        for i in range(40):
            svc_ready = (
                self.robot_controller.moveit2_robot0
                ._plan_kinematic_path_service
                .wait_for_service(timeout_sec=0.5)
            )
            if svc_ready:
                self.robot_controller.logger.info(
                    "[STATE: SETUP] MoveIt planning service is ready!"
                )
                break
            self.robot_controller.logger.info(
                f"[STATE: SETUP] Waiting for MoveIt... ({i+1}/40)"
            )

        # Wait for gripper_controller to be fully spawned and active
        self.robot_controller.wait_for_gripper_controller(timeout=20.0)

        # Set position_proportional_gain at runtime (YAML loading is broken for gz_ros_control)
        # Higher P-gain = more responsive finger & mimic tracking under GazeboSimSystem
        for gain_val in ['50.0']:
            try:
                result = subprocess.run(
                    ["ros2", "param", "set", "/arm1/gz_ros_control",
                     "position_proportional_gain", gain_val],
                    capture_output=True, text=True, timeout=5.0,
                )
                self.robot_controller.logger.info(
                    f"[STATE: SETUP] Set P-gain={gain_val}: {result.stdout.strip()}"
                )
            except Exception as e:
                self.robot_controller.logger.warn(f"[STATE: SETUP] Failed to set P-gain: {e}")

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
        return 'home'


class Home(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['wait', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: HOME] Moving to standby position above conveyor..."
        )
        self.robot_controller.gripper_open()
        time.sleep(0.2)

        # Go to a safe high position above conveyor intercept line, gripper open, ready to descend
        standby_y = self.robot_controller.GRASP_Y_ARM  # Y at intercept line
        standby_pos = [0.52, standby_y, 0.40]  # High above conveyor
        self.robot_controller.logger.info(
            f"[STATE: HOME] Moving to standby: {standby_pos}"
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=standby_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=False,
            frame_id='arm1/base_link'
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        self.robot_controller.logger.info(
            "[STATE: HOME] Standby position reached, scanning for cubes"
        )
        return 'wait'


class Wait(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approach', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: WAIT] Scanning for approaching cubes..."
        )
        self.robot_controller.last_pose = None

        while True:
            cube_name, cube_transform = self.robot_controller.find_target_cube()

            if cube_name:
                cube_y = cube_transform.transform.translation.y
                distance = self.robot_controller.GRASP_Y_WORLD - cube_y

                # Lock on when cube is far enough for the arm to pre-position
                # (>2m gives ~17s at 0.12m/s)
                # But also close enough that TF positions are fresh
                if distance > 0.3 and distance < 2.5 and cube_y > 0.5:
                    self.robot_controller.target_cube_name = cube_name
                    self.robot_controller.target_cube_x = cube_transform.transform.translation.x
                    self.robot_controller.target_cube_y = cube_y
                    self.robot_controller.target_cube_z = cube_transform.transform.translation.z

                    eta = distance / max(self.robot_controller.CONVEYOR_SPEED, 0.01)
                    self.robot_controller.logger.info(
                        f"[STATE: WAIT] Locked onto {cube_name} at Y={cube_y:.3f}m, "
                        f"distance={distance:.3f}m, ETA={eta:.1f}s"
                    )
                    return 'approach'

            time.sleep(0.1)


class ApproachObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approached', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: APPROACH] "
            "========== PRE-POSITIONING FOR GRASP =========="
        )

        # Get latest cube position
        try:
            latest_tf = self.robot_controller.tf_buffer.lookup_transform(
                'world',
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
            return 'failed'

        # Compute arm-frame X via TF (direct lookup)
        cube_arm = self.robot_controller.get_pose_in_base_frame(
            self.robot_controller.target_cube_name, timeout_sec=0.2
        )
        if cube_arm is None:
            self.robot_controller.logger.error(
                "[STATE: APPROACH] TF arm1/base_link←cube failed"
            )
            return 'failed'
        target_x_arm = max(
            self.robot_controller.MIN_TARGET_X_ARM,
            min(self.robot_controller.MAX_TARGET_X_ARM, cube_arm[0])
        )

        # Phase 1: Move to READY position above conveyor — high enough to clear cubes
        ready_y_arm = self.robot_controller.GRASP_Y_ARM
        ready_z_arm = self.robot_controller.READY_Z_ARM  # well above cube height
        ready_pos = [target_x_arm, ready_y_arm, ready_z_arm]

        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Cube {self.robot_controller.target_cube_name}: "
            f"world=({cube_x:.3f}, {cube_y:.3f}, {cube_z:.3f})"
        )
        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Moving to ready position: {ready_pos}"
        )

        self.robot_controller.gripper_open()

        self.robot_controller.moveit2_robot0.move_to_pose(
            position=ready_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm1/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller.logger.info(
            "[STATE: APPROACH] Ready position reached, waiting for cube..."
        )

        # Phase 2: Wait for cube to enter trigger zone
        # earlier trigger since we descend after stop
        trigger_y = self.robot_controller.GRASP_Y_WORLD - 0.15
        hard_miss_y = self.robot_controller.GRASP_Y_WORLD + 0.25
        timeout = 30.0
        start_time = time.time()
        last_log_time = 0.0

        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Trigger at Y>={trigger_y:.3f}m, miss at Y>{hard_miss_y:.3f}m"
        )

        while time.time() - start_time < timeout:
            try:
                current_tf = self.robot_controller.tf_buffer.lookup_transform(
                    'world',
                    self.robot_controller.target_cube_name,
                    rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.05),
                )
                current_y = current_tf.transform.translation.y

                if current_y >= trigger_y:
                    if current_y > hard_miss_y:
                        self.robot_controller.logger.warn(
                            f"[STATE: APPROACH] Cube passed gripper (Y={current_y:.3f}), missed!"
                        )
                        return 'failed'

                    # STOP the conveyor belt — cube becomes stationary
                    self.robot_controller.conveyor_stop()
                    time.sleep(0.15)  # let physics settle

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
                                'world',
                                self.robot_controller.target_cube_name,
                                rclpy.time.Time(),
                                timeout=rclpy.duration.Duration(seconds=0.5),
                            )
                            exact_x = stopped_tf.transform.translation.x
                            exact_y = stopped_tf.transform.translation.y
                            exact_z = stopped_tf.transform.translation.z
                        except Exception:
                            exact_x = current_tf.transform.translation.x
                            exact_y = current_y
                            exact_z = current_tf.transform.translation.z

                    # Store stopped cube world pose for GRASP validation
                    self.robot_controller._stopped_cube_world_pose = (exact_x, exact_y, exact_z)

                    # Compute exact grasp position in arm frame via TF
                    cube_in_arm = self.robot_controller.get_pose_in_base_frame(
                        self.robot_controller.target_cube_name,
                        timeout_sec=0.5,
                    )
                    if cube_in_arm is None:
                        # Fallback: try world→arm via the stored world pose
                        world_in_arm = self.robot_controller.get_pose_in_base_frame(
                            'world', timeout_sec=0.5
                        )
                        if world_in_arm is not None:
                            cube_in_arm = (
                                world_in_arm[0] + exact_x,
                                world_in_arm[1] + exact_y,
                                world_in_arm[2] + exact_z,
                            )
                    if cube_in_arm is None:
                        self.robot_controller.logger.error(
                            "[STATE: APPROACH] Cannot convert cube to arm frame"
                        )
                        return 'failed'
                    grasp_x_arm = max(
                        self.robot_controller.MIN_TARGET_X_ARM,
                        min(self.robot_controller.MAX_TARGET_X_ARM, cube_in_arm[0])
                    )
                    grasp_y_arm = cube_in_arm[1]
                    grasp_z_arm = (
                        cube_in_arm[2]
                        + self.robot_controller.GRASP_Z_OFFSET
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

                    # Phase 4: Move to position directly above cube first (X,Y aligned, Z high)
                    above_pos = [grasp_x_arm, grasp_y_arm, ready_z_arm]
                    self.robot_controller.logger.info(
                        f"[STATE: APPROACH] Moving above cube: {above_pos}"
                    )
                    self.robot_controller.moveit2_robot0.move_to_pose(
                        position=above_pos,
                        quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                        cartesian=True,
                        frame_id='arm1/base_link',
                    )
                    self.robot_controller.moveit2_robot0.wait_until_executed()

                    # Phase 5: Descend straight down to grasp position
                    self.robot_controller.logger.info(
                        f"[STATE: APPROACH] Descending to grasp: {grasp_pos}"
                    )
                    self.robot_controller.moveit2_robot0.move_to_pose(
                        position=grasp_pos,
                        quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                        cartesian=True,
                        frame_id='arm1/base_link',
                    )
                    self.robot_controller.moveit2_robot0.wait_until_executed()
                    self.robot_controller.logger.info(
                        "[STATE: APPROACH] At grasp position, ready to close"
                    )
                    return 'approached'

                now = time.time()
                if now - last_log_time > 1.0:
                    distance = self.robot_controller.GRASP_Y_WORLD - current_y
                    self.robot_controller.logger.info(
                        f"[STATE: APPROACH] Waiting: cube Y={current_y:.3f}m, dist={distance:.3f}m"
                    )
                    last_log_time = now
            except Exception as e:
                self.robot_controller.logger.warn(f"[STATE: APPROACH] Lost tracking: {e}")

            time.sleep(0.02)

        self.robot_controller.logger.warn("[STATE: APPROACH] Timeout waiting for cube")
        return 'failed'


class GraspObject(State):
    MAX_GRASP_ATTEMPTS = 3

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['grasped', 'failed'])
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
                'world', timeout_sec=0.5
            )
            if world_in_arm is None:
                self.robot_controller.logger.warn(
                    "[STATE: GRASP] TF fallback failed"
                )
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
            min(self.robot_controller.MAX_TARGET_X_ARM, cube_arm[0])
        )
        grasp_y = cube_arm[1]
        grasp_z = cube_arm[2] + self.robot_controller.GRASP_Z_OFFSET

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

        # Move above
        above_z = self.robot_controller.READY_Z_ARM
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=[grasp_x, grasp_y, above_z],
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True, frame_id='arm1/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Descend straight down
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=[grasp_x, grasp_y, grasp_z],
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True, frame_id='arm1/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
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
        self.robot_controller.logger.info(f"[STATE: GRASP] Lifting to z_arm={lift_z:.3f}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=lift_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True, frame_id='arm1/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        time.sleep(0.15)

        # Validate via Gazebo / TF
        pose_after_gz = self.robot_controller._query_gz_model_pose(cube_name, timeout=1.0)
        if pose_after_gz is None:
            cube_tf_pose = self.robot_controller.get_cube_world_pose(cube_name, timeout_sec=0.3)
            if cube_tf_pose is not None:
                pose_after_gz = cube_tf_pose
        left_pos, right_pos = self.robot_controller._read_both_finger_positions()

        # EE world position
        ee_world = None
        try:
            ee_tf = self.robot_controller.tf_buffer.lookup_transform(
                'world', 'arm1/wrist_3_link', rclpy.time.Time(),
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

        # Finger-only fallback
        if pose_after_gz is None:
            both_closed = (
                (left_pos is not None and left_pos > 0.005) or
                (right_pos is not None and right_pos > 0.020)
            )
            if both_closed:
                self.robot_controller.grasping = True
                return True
            return False

        z_after = pose_after_gz[2]
        z_gain = z_after - z_before

        ee_dist = None
        if ee_world is not None:
            dx = pose_after_gz[0] - ee_world[0]
            dy = pose_after_gz[1] - ee_world[1]
            dz = pose_after_gz[2] - ee_world[2]
            ee_dist = (dx**2 + dy**2 + dz**2) ** 0.5

        close_enough = (ee_dist is not None and ee_dist < 0.15)
        lifted = z_gain > 0.02 or z_after > 0.25
        finger_closed = (left_pos is not None and left_pos > 0.01)

        self.robot_controller.logger.info(
            f"[STATE: GRASP] z_gain={z_gain:.4f}, close_enough={close_enough}, "
            f"lifted={lifted}, finger_closed={finger_closed}"
        )

        if (close_enough and lifted) or (finger_closed and (close_enough or lifted)):
            self.robot_controller.grasping = True
            return True
        return False

    def execute(self, userdata):
        cube_name = self.robot_controller.target_cube_name
        stopped_pose = getattr(self.robot_controller, '_stopped_cube_world_pose', None)
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
                stopped_pose = getattr(self.robot_controller, '_stopped_cube_world_pose', None)
                z_before = stopped_pose[2] if stopped_pose else z_before

            if self._attempt_grasp(cube_name, z_before):
                self.robot_controller.conveyor_resume()
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] ✓ GRASP SUCCESS on attempt {attempt}"
                )
                return 'grasped'

            self.robot_controller.logger.warn(
                f"[STATE: GRASP] ✗ Attempt {attempt} failed"
            )

        # All attempts exhausted
        self.robot_controller.grasping = False
        self.robot_controller.gripper_open()
        self.robot_controller.conveyor_resume()
        self.robot_controller.logger.error(
            f"[STATE: GRASP] ✗ All {self.MAX_GRASP_ATTEMPTS} attempts FAILED for {cube_name}"
        )
        return 'failed'


class PlaceObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['placed', 'failed'])
        self.robot_controller = robot_controller

    # Tray visual is offset +0.13m above tray link frame in SDF
    TRAY_SURFACE_OFFSET = 0.13
    CUBE_HALF_HEIGHT = 0.0225  # 4.5cm cubes
    GRASP_Z_OFFSET_PLACE = 0.030  # finger center below ee_link

    def _resolve_amr_place_pose(self):
        """Resolve AMR tray center in arm1/base_link frame via direct TF lookup."""
        tray_frames = [
            ('amr1/turtlebot3_tray', True),
            ('amr1/base_link', False),
            ('amr1/base_footprint', False),
        ]

        for frame_name, is_tray_frame in tray_frames:
            pose = self.robot_controller.get_pose_in_base_frame(
                frame_name, timeout_sec=1.0
            )
            if pose is None:
                continue

            arm_x, arm_y, arm_z = pose

            if is_tray_frame:
                # Tray surface is ~0.13m above the tray link frame (SDF visual offset)
                surface_z = arm_z + self.TRAY_SURFACE_OFFSET
                # Position ee so cube bottom is ~5mm above tray surface
                place_z = (
                    surface_z
                    + self.GRASP_Z_OFFSET_PLACE
                    + self.CUBE_HALF_HEIGHT
                    + 0.005
                )
                above_z = place_z + 0.06
            else:
                # base_link/footprint: use conservative defaults
                place_z = 0.20
                above_z = 0.30

            self.robot_controller.logger.info(
                f"[STATE: PLACE] Resolved '{frame_name}' in arm1/base_link: "
                f"({arm_x:.3f}, {arm_y:.3f}, {arm_z:.3f}), "
                f"place_z={place_z:.3f}, above_z={above_z:.3f}"
            )
            return [arm_x, arm_y, place_z], [arm_x, arm_y, above_z]

        self.robot_controller.logger.warn(
            '[STATE: PLACE] All TF lookups failed, using static fallback'
        )
        return [-0.28, -0.5, 0.20], [-0.28, -0.5, 0.30]

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: PLACE] ========== ENTERING PLACE STATE =========="
        )
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Object to place: "
            f"{self.robot_controller.target_cube_name}"
        )

        # FIRST: Lift cube HIGH to clear belt before any horizontal movement
        lift_pos = [
            self.robot_controller.approach_target_x_arm,
            self.robot_controller.GRASP_Y_ARM,
            0.50,
        ]
        self.robot_controller.logger.info(
            "[STATE: PLACE] Lifting cube HIGH (Z=0.50m)..."
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=lift_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,  # Straight up
            frame_id='arm1/base_link'
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Get AMR placement target in arm frame
        self.robot_controller.logger.info(
            "[STATE: PLACE] Resolving AMR placement pose..."
        )
        self.turtlebot_pos, above_pos = self._resolve_amr_place_pose()

        # Move to above AMR (already high, safe horizontal movement)
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Moving above AMR: {above_pos}"
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=above_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm1/base_link'
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Check grasp
        if not self.robot_controller.grasping:
            self.robot_controller.logger.error("[STATE: PLACE] ✗ Lost object!")
            return 'failed'

        # Lower to place
        self.robot_controller.logger.info(
            f"[STATE: PLACE] Lowering to place: {self.turtlebot_pos}"
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=self.turtlebot_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,  # Straight down
            frame_id='arm1/base_link'
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Release cube
        self.robot_controller.logger.info("[STATE: PLACE] Releasing object")
        self.robot_controller.gripper_open()
        time.sleep(0.3)

        self.robot_controller.logger.info("[STATE: PLACE] ✓ Placed successfully")
        return 'placed'


class TransferObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: TRANSFER] "
            "========== ENTERING TRANSFER STATE =========="
        )
        self.robot_controller.logger.info(
            f"[STATE: TRANSFER] Instructing AMR to transport: "
            f"{self.robot_controller.target_cube_name}"
        )

        self.robot_controller.logger.info(
            "[STATE: TRANSFER] Setting AMR target position: "
            "x=-3.5, y=0.3 (near arm2)"
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('point_x', Parameter.Type.DOUBLE, -3.5),
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('point_y', Parameter.Type.DOUBLE, 0.3),
        )
        self.robot_controller.logger.info(
            f"[STATE: TRANSFER] Setting object name: "
            f"{self.robot_controller.target_cube_name}"
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter(
                'object_name',
                Parameter.Type.STRING,
                self.robot_controller.target_cube_name,
            ),
        )
        self.robot_controller.logger.info(
            "[STATE: TRANSFER] Commanding AMR to 'goto' state"
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('state', Parameter.Type.STRING, 'goto'),
        )
        self.robot_controller.logger.info(
            "[STATE: TRANSFER] Setting ARM1 state to 'wait'"
        )
        self.robot_controller.set_parameters(
            [Parameter('state', Parameter.Type.STRING, 'wait')]
        )
        self.robot_controller.logger.info(
            "[STATE: TRANSFER] Transfer initiated — cycle complete"
        )
        return 'home'


class Idle(State):
    """Final state — arm returns to spawn pose and idles after cycle 1."""

    HOME_JOINT_POSITIONS = [0.0, -1.57, 1.57, -1.57, -1.57, 0.0]

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['done'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: IDLE] ========== CYCLE COMPLETE =========="
        )
        self.robot_controller.moveit2_robot0.move_to_configuration(
            joint_positions=self.HOME_JOINT_POSITIONS,
            cartesian=False,
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller.gripper_open()
        self.robot_controller.set_parameters(
            [Parameter('state', Parameter.Type.STRING, 'idle')]
        )
        self.robot_controller.logger.info(
            "[STATE: IDLE] ARM1 at spawn pose. Demo complete."
        )
        while rclpy.ok():
            time.sleep(1.0)
        return 'done'


def run_smach(client):
    client.logger.info("========================================")
    client.logger.info("=== STARTING STATE MACHINE ===")
    client.logger.info("========================================")

    # Create the top level SMACH state machine
    sm = StateMachine(outcomes=['succeeded', 'aborted'])
    with sm:
        StateMachine.add('SETUP', Setup(client), transitions={'home': 'HOME', 'failed': 'HOME'})
        StateMachine.add('HOME', Home(client), transitions={'wait': 'WAIT', 'failed': 'HOME'})
        StateMachine.add(
            'WAIT', Wait(client), transitions={'approach': 'APPROACH', 'failed': 'HOME'}
        )
        StateMachine.add(
            'APPROACH',
            ApproachObject(client),
            transitions={'approached': 'GRASP', 'failed': 'HOME'},
        )
        StateMachine.add(
            'GRASP', GraspObject(client), transitions={'grasped': 'PLACE', 'failed': 'HOME'}
        )
        StateMachine.add(
            'PLACE', PlaceObject(client), transitions={'placed': 'TRANSFER', 'failed': 'HOME'}
        )
        StateMachine.add(
            'TRANSFER',
            TransferObject(client),
            transitions={'home': 'IDLE', 'failed': 'HOME'},
        )
        StateMachine.add(
            'IDLE', Idle(client), transitions={'done': 'succeeded'}
        )

    client.logger.info("=== State machine configured, starting execution ===")
    # Execute SMACH plan
    sm.execute()


def main(args=None):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)

    robot_controller = RobotController(args_without_ros)
    robot_controller.get_logger().info('Robot Controller started')

    # Wait for MoveIt to be fully ready
    time.sleep(1.0)

    # Publish ready status
    ready_msg = Bool()
    ready_msg.data = True
    robot_controller.ready_publisher.publish(ready_msg)
    robot_controller.get_logger().info('✓ ARM1 Controller ready - MoveIt initialized')

    # Create and start the thread for running the state machine
    smach_thread = threading.Thread(target=run_smach, args=(robot_controller,))
    smach_thread.start()

    executor = MultiThreadedExecutor()
    executor.add_node(robot_controller)
    executor.spin()
    robot_controller.destroy_node()
    rclpy.shutdown()
    sys.exit(0)


if __name__ == '__main__':
    main()
