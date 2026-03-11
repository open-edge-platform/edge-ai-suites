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
# Desc: Controller program for ARM2
#       Picks cubes from AMR tray and places them at a destination.
#       Uses parallel gripper via JointTrajectory (same as ARM1).
import sys
import subprocess
import threading
import time

# Third-Party Library Imports
import rclpy
import tf2_ros
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
from moveit2 import MoveIt2
from smach import State, StateMachine
from rclpy.parameter import Parameter

# Custom Module Imports
from robot_config import utils
from robots import ur5 as robot


class RobotController(Node):
    def __init__(self, args):
        super().__init__('ARM2Controller')

        # Declare parameters — guard against double declaration from launch file
        for pname, pval in [('state', 'wait'), ('object_name', '')]:
            if not self.has_parameter(pname):
                self.declare_parameter(pname, pval)
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', True)

        self.setup_qos_and_groups()
        self.setup_logging()
        self.logger.info("ARM2 controller constructor")
        self.moveit2_robot0 = self.setup_moveit()

        self.grasping = False

        # TF setup for cube tracking
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Place destination (arm2 frame)
        self.PLACE_X_ARM = 0.3
        self.PLACE_Y_ARM = -0.4
        self.PLACE_Z_ARM = 0.10

        self.target_cube_name = None

        self.setup_subscriptions_and_services()

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
            joint_names=robot.joint_names('arm2/'),
            base_link_name=robot.base_link_name('arm2/'),
            end_effector_name=robot.end_effector_name('arm2/'),
            group_name=robot.MOVE_GROUP_ARM,
            callback_group=self.moveit_callback_group0,
            execute_via_moveit=False,
            ignore_new_calls_while_executing=True,
            namespace_prefix='/arm2/',
        )

    def setup_logging(self):
        self.logger = self.get_logger()
        self.logger.set_level(LoggingSeverity.INFO)

    def setup_subscriptions_and_services(self):
        # Ready status publisher
        self.ready_publisher = self.create_publisher(
            Bool, '/arm2/controller_ready', qos_profile=self.qos_profile
        )

        # Gripper action client (JointTrajectoryController)
        self._gripper_action_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/arm2/gripper_controller/follow_joint_trajectory'
        )
        self._gripper_joint_names = [
            'arm2/left_finger_joint',
        ]

        # Gripper state tracking
        self._gripper_desired_position = 0.0

        # Persistent joint_states subscription for finger position monitoring
        self._finger_positions = {'left': None, 'right': None}
        self._finger_lock = threading.Lock()
        self._joint_states_sub = self.create_subscription(
            JointState, '/arm2/joint_states',
            self._joint_states_callback, 10
        )

    def _joint_states_callback(self, msg):
        with self._finger_lock:
            for i, name in enumerate(msg.name):
                if 'left_finger_joint' in name:
                    self._finger_positions['left'] = msg.position[i]
                elif 'right_finger_joint' in name:
                    self._finger_positions['right'] = msg.position[i]

    def _read_both_finger_positions(self):
        with self._finger_lock:
            return self._finger_positions['left'], self._finger_positions['right']

    def wait_for_gripper_controller(self, timeout=15.0):
        self.logger.info("[GRIPPER] Waiting for gripper_controller action server...")
        ready = self._gripper_action_client.wait_for_server(timeout_sec=timeout)
        if not ready:
            self.logger.warn("[GRIPPER] Not found, attempting to spawn gripper_controller...")
            try:
                subprocess.run(
                    ["ros2", "run", "controller_manager", "spawner",
                     "gripper_controller", "-c", "/arm2/controller_manager"],
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
                    ["ros2", "param", "set", "/arm2/gripper_controller",
                     "gains.arm2__left_finger_joint.p", "100.0"],
                    capture_output=True, text=True, timeout=5,
                )
                subprocess.run(
                    ["ros2", "param", "set", "/arm2/gripper_controller",
                     "gains.arm2__left_finger_joint.i", "10.0"],
                    capture_output=True, text=True, timeout=5,
                )
                subprocess.run(
                    ["ros2", "param", "set", "/arm2/gripper_controller",
                     "gains.arm2__left_finger_joint.d", "1.0"],
                    capture_output=True, text=True, timeout=5,
                )
                self.logger.info("[GRIPPER] Set PID gains P=100 I=10 D=1 for left_finger")
            except Exception:
                pass
        else:
            self.logger.warn("[GRIPPER] Timed out waiting for gripper_controller")
        return ready

    def _send_gripper_trajectory(self, left_pos, right_pos, duration_sec=0.5, timeout=5.0):
        """Only commands left_finger_joint; right finger follows via mimic."""
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
            f"[GRIPPER] Sending trajectory: left={left_pos:.4f}, right={right_pos:.4f}"
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
            self.logger.warn("[GRIPPER] Goal rejected")
            return False

        result_future = goal_handle.get_result_async()
        while not result_future.done() and time.time() - start < timeout:
            time.sleep(0.01)
        if not result_future.done():
            self.logger.warn("[GRIPPER] Timeout waiting for execution")
            return False

        result = result_future.result()
        success = (result.result.error_code == FollowJointTrajectory.Result.SUCCESSFUL)
        left_after, right_after = self._read_both_finger_positions()
        self.logger.info(
            f"[GRIPPER] Result: success={success},"
            f" left={left_after}, right={right_after}"
        )
        return success

    def gripper_close(self, position=0.035):
        """Close gripper via FollowJointTrajectory action with squeeze."""
        left_pos, right_pos = self._read_both_finger_positions()
        self.logger.info(f"[GRIPPER] Closing to {position}: left={left_pos}, right={right_pos}")
        self._gripper_desired_position = position
        # Initial close command
        self._send_gripper_trajectory(position, position, duration_sec=0.8)
        time.sleep(0.15)
        # Squeeze: re-send close to reinforce grip force
        self._send_gripper_trajectory(position, position, duration_sec=0.3)
        # Always set grasping=True — physical validation is done in lift test
        self.grasping = True
        return True

    def gripper_open(self, position=0.0):
        """Open gripper via FollowJointTrajectory action."""
        left_pos, right_pos = self._read_both_finger_positions()
        self.logger.info(f"[GRIPPER] Opening to {position}: left={left_pos}, right={right_pos}")
        self._gripper_desired_position = position
        self._send_gripper_trajectory(position, position, duration_sec=0.3)
        self.grasping = False
        return True

    def get_cube_world_pose(self, cube_name, timeout_sec=0.5):
        try:
            transform = self.tf_buffer.lookup_transform(
                'world', cube_name, rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception:
            return None

    def get_amr_tray_pose(self, timeout_sec=0.5):
        for frame in ['amr1/turtlebot3_tray', 'amr1/base_link', 'amr1/base_footprint']:
            try:
                transform = self.tf_buffer.lookup_transform(
                    'world', frame, rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=timeout_sec),
                )
                t = transform.transform.translation
                return (t.x, t.y, t.z)
            except Exception:
                continue
        return None

    def get_pose_in_base_frame(self, target_frame, timeout_sec=0.5):
        """Look up target_frame position directly in arm2/base_link frame via TF."""
        try:
            transform = self.tf_buffer.lookup_transform(
                'arm2/base_link', target_frame, rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=timeout_sec),
            )
            t = transform.transform.translation
            return (t.x, t.y, t.z)
        except Exception:
            return None


# ====================== STATE MACHINE ======================

class Setup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info("[STATE: SETUP] ========== ARM2 INITIALIZING ==========")
        self.robot_controller.wait_for_gripper_controller(timeout=30.0)

        # Set position_proportional_gain at runtime — required for gripper/mimic to work
        try:
            result = subprocess.run(
                ["ros2", "param", "set", "/arm2/gz_ros_control",
                 "position_proportional_gain", "100.0"],
                capture_output=True, text=True, timeout=5.0,
            )
            self.robot_controller.logger.info(
                f"[STATE: SETUP] Set P-gain=100.0: {result.stdout.strip()}"
            )
        except Exception as e:
            self.robot_controller.logger.warn(f"[STATE: SETUP] Failed to set P-gain: {e}")

        self.robot_controller.gripper_open()
        time.sleep(0.5)

        ready_msg = Bool()
        ready_msg.data = True
        self.robot_controller.ready_publisher.publish(ready_msg)
        self.robot_controller.logger.info("[STATE: SETUP] ARM2 setup complete")
        return 'home'


class Home(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['wait', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info("[STATE: HOME] Moving to standby position...")
        self.robot_controller.gripper_open()
        time.sleep(0.2)

        standby_pos = [0.3, 0.3, 0.30]
        self.robot_controller.logger.info(f"[STATE: HOME] Standby: {standby_pos}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=standby_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=False,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller.logger.info("[STATE: HOME] Standby reached, waiting for trigger")
        return 'wait'


class Wait(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approach', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info("[STATE: WAIT] Waiting for AMR delivery trigger...")
        while self.robot_controller.get_parameter('state').value == 'wait':
            time.sleep(0.5)

        self.robot_controller.target_cube_name = (
            self.robot_controller.get_parameter('object_name').value
        )
        self.robot_controller.logger.info(
            f"[STATE: WAIT] Triggered! Target cube: {self.robot_controller.target_cube_name}"
        )
        return 'approach'


class ApproachObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approached', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: APPROACH] ========== APPROACHING CUBE ON AMR =========="
        )
        cube_name = self.robot_controller.target_cube_name

        # Locate cube directly in arm2/base_link frame via TF
        cube_arm = self.robot_controller.get_pose_in_base_frame(
            cube_name, timeout_sec=2.0
        )
        if cube_arm is None:
            self.robot_controller.logger.warn(
                f"[STATE: APPROACH] Cannot find {cube_name} via TF, using AMR tray"
            )
            tray_arm = None
            for frame in ['amr1/turtlebot3_tray', 'amr1/base_link',
                          'amr1/base_footprint']:
                tray_arm = self.robot_controller.get_pose_in_base_frame(
                    frame, timeout_sec=2.0
                )
                if tray_arm is not None:
                    break
            if tray_arm is None:
                self.robot_controller.logger.error(
                    "[STATE: APPROACH] Cannot find AMR position"
                )
                return 'failed'
            cube_arm = (tray_arm[0], tray_arm[1], tray_arm[2] + 0.10)

        self.robot_controller.logger.info(
            f"[STATE: APPROACH] Cube in arm2 frame: "
            f"({cube_arm[0]:.3f}, {cube_arm[1]:.3f}, {cube_arm[2]:.3f})"
        )

        grasp_x = cube_arm[0]
        grasp_y = cube_arm[1]
        grasp_z = cube_arm[2] + 0.025

        # Phase 1: Above
        above_pos = [grasp_x, grasp_y, grasp_z + 0.10]
        self.robot_controller.logger.info(f"[STATE: APPROACH] Moving above: {above_pos}")
        self.robot_controller.gripper_open()

        self.robot_controller.moveit2_robot0.move_to_pose(
            position=above_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Phase 2: Descend
        grasp_pos = [grasp_x, grasp_y, grasp_z]
        self.robot_controller.logger.info(f"[STATE: APPROACH] Descending to: {grasp_pos}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=grasp_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        self.robot_controller._approach_x = grasp_x
        self.robot_controller._approach_y = grasp_y
        self.robot_controller._approach_z = grasp_z
        self.robot_controller.logger.info("[STATE: APPROACH] At grasp position, ready to close")
        return 'approached'


class GraspObject(State):
    MAX_GRASP_ATTEMPTS = 3

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['grasped', 'failed'])
        self.robot_controller = robot_controller

    def _close_and_validate(self):
        """Close gripper and validate finger engagement."""
        self.robot_controller.gripper_close(position=0.035)
        close_deadline = time.time() + 3.0
        while time.time() < close_deadline:
            left_pos, _ = self.robot_controller._read_both_finger_positions()
            if left_pos is not None and left_pos > 0.008:
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] Fingers engaged: left={left_pos:.4f}"
                )
                return True
            time.sleep(0.1)
        left_pos, right_pos = self.robot_controller._read_both_finger_positions()
        self.robot_controller.logger.warn(
            f"[STATE: GRASP] Fingers not closing: left={left_pos}, right={right_pos}"
        )
        return False

    def _lift_test(self):
        """Lift and verify cube is held."""
        lift_z = self.robot_controller._approach_z + 0.15
        lift_pos = [
            self.robot_controller._approach_x,
            self.robot_controller._approach_y,
            lift_z,
        ]
        self.robot_controller.logger.info(f"[STATE: GRASP] Lifting to z_arm={lift_z:.3f}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=lift_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        time.sleep(0.3)

        left_pos, right_pos = self.robot_controller._read_both_finger_positions()
        self.robot_controller.logger.info(
            f"[STATE: GRASP] After lift: left={left_pos}, right={right_pos}"
        )
        return (
            (left_pos is not None and left_pos > 0.008) or
            (right_pos is not None and right_pos > 0.008)
        )

    def execute(self, userdata):
        for attempt in range(1, self.MAX_GRASP_ATTEMPTS + 1):
            self.robot_controller.logger.info(
                f"[STATE: GRASP] ========== ATTEMPT {attempt}/{self.MAX_GRASP_ATTEMPTS} =========="  # noqa: E501
            )

            if attempt > 1:
                # Re-open and descend slightly lower for better contact
                self.robot_controller.gripper_open()
                time.sleep(0.15)
                z_nudge = -0.005 * attempt
                readjust_pos = [
                    self.robot_controller._approach_x,
                    self.robot_controller._approach_y,
                    self.robot_controller._approach_z + z_nudge,
                ]
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] Re-descending to {readjust_pos}"
                )
                self.robot_controller.moveit2_robot0.move_to_pose(
                    position=readjust_pos,
                    quat_xyzw=[1.0, 0.0, 0.0, 0.0],
                    cartesian=True,
                    frame_id='arm2/base_link',
                )
                self.robot_controller.moveit2_robot0.wait_until_executed()

            if not self._close_and_validate():
                continue

            time.sleep(0.15)

            if self._lift_test():
                self.robot_controller.grasping = True
                self.robot_controller.logger.info(
                    f"[STATE: GRASP] ✓ GRASP SUCCESS on attempt {attempt}"
                )
                return 'grasped'

            self.robot_controller.logger.warn(
                f"[STATE: GRASP] ✗ Lift test failed on attempt {attempt}"
            )

        self.robot_controller.grasping = False
        self.robot_controller.gripper_open()
        self.robot_controller.logger.error(
            f"[STATE: GRASP] ✗ All {self.MAX_GRASP_ATTEMPTS} attempts FAILED"
        )
        return 'failed'


class PlaceObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['idle', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info("[STATE: PLACE] ========== PLACING OBJECT ==========")

        place_above = [
            self.robot_controller.PLACE_X_ARM,
            self.robot_controller.PLACE_Y_ARM,
            self.robot_controller.PLACE_Z_ARM + 0.15,
        ]
        self.robot_controller.logger.info(f"[STATE: PLACE] Moving above: {place_above}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=place_above,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        if not self.robot_controller.grasping:
            self.robot_controller.logger.error("[STATE: PLACE] ✗ Lost object!")
            return 'failed'

        place_pos = [
            self.robot_controller.PLACE_X_ARM,
            self.robot_controller.PLACE_Y_ARM,
            self.robot_controller.PLACE_Z_ARM,
        ]
        self.robot_controller.logger.info(f"[STATE: PLACE] Lowering to: {place_pos}")
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=place_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        self.robot_controller.logger.info("[STATE: PLACE] Releasing object")
        self.robot_controller.gripper_open()
        time.sleep(0.5)

        # Signal: reset own state + tell AMR pickup is done
        self.robot_controller.set_parameters([
            Parameter('state', Parameter.Type.STRING, 'idle')
        ])
        try:
            utils.call_set_parameters(
                self.robot_controller,
                '/amr1/AMRController',
                Parameter('state', Parameter.Type.STRING, 'done'),
            )
            self.robot_controller.logger.info("[STATE: PLACE] Signaled AMR to return home")
        except Exception as e:
            self.robot_controller.logger.warn(f"[STATE: PLACE] Failed to signal AMR: {e}")

        self.robot_controller.logger.info("[STATE: PLACE] ✓ Placed successfully")
        return 'idle'


class Idle(State):
    """Final state — arm2 returns to standby and idles after cycle 1."""

    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['done'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info(
            "[STATE: IDLE] ========== ARM2 CYCLE COMPLETE =========="
        )
        standby_pos = [0.3, 0.3, 0.30]
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=standby_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=False,
            frame_id='arm2/base_link',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        self.robot_controller.gripper_open()
        self.robot_controller.logger.info(
            "[STATE: IDLE] ARM2 at standby. Demo complete."
        )
        while rclpy.ok():
            time.sleep(1.0)
        return 'done'


def run_smach(client):
    client.logger.info("========================================")
    client.logger.info("=== ARM2 STARTING STATE MACHINE ===")
    client.logger.info("========================================")

    sm = StateMachine(outcomes=['succeeded', 'aborted'])
    with sm:
        StateMachine.add('SETUP', Setup(client),
                         transitions={'home': 'HOME', 'failed': 'HOME'})
        StateMachine.add('HOME', Home(client),
                         transitions={'wait': 'WAIT', 'failed': 'HOME'})
        StateMachine.add('WAIT', Wait(client),
                         transitions={'approach': 'APPROACH', 'failed': 'HOME'})
        StateMachine.add('APPROACH', ApproachObject(client),
                         transitions={'approached': 'GRASP', 'failed': 'HOME'})
        StateMachine.add('GRASP', GraspObject(client),
                         transitions={'grasped': 'PLACE', 'failed': 'HOME'})
        StateMachine.add('PLACE', PlaceObject(client),
                         transitions={'idle': 'IDLE', 'failed': 'HOME'})
        StateMachine.add('IDLE', Idle(client),
                         transitions={'done': 'succeeded'})

    client.logger.info("=== ARM2 state machine configured, starting execution ===")
    sm.execute()


def main(args=None):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)

    robot_controller = RobotController(args_without_ros)
    robot_controller.get_logger().info('ARM2 Robot Controller started')

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
