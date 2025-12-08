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
import threading
import time
from copy import deepcopy

# Third-Party Library Imports
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.logging import LoggingSeverity
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import Bool
from moveit2 import MoveIt2
from smach import State, StateMachine
from rclpy.parameter import Parameter

# Custom Module Imports
from robot_config import utils
from picknplace.msg import BoxState
from robots import ur5 as robot


class RobotController(Node):
    def __init__(self, args):
        super().__init__('ARM1Controller')
        self.last_pose = None
        self.declare_parameter('state', 'run')
        self.setup_qos_and_groups()

        self.setup_logging()
        self.logger.info("robot controller constructor")
        self.moveit2_robot0 = self.setup_moveit()

        self.grasping = False
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
            joint_names=robot.joint_names(),
            base_link_name=robot.base_link_name(),
            end_effector_name=robot.end_effector_name(),
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
        self.object_subscription_arm1 = self.create_subscription(
            BoxState,
            '/object_location',
            self.object_location_cb,
            callback_group=self.callback_group0,
            qos_profile=self.qos_profile,
        )

        # Change from service to subscription for vacuum gripper
        self.vacuum_grasping_subscription = self.create_subscription(
            Bool,
            '/arm1/vacuum_gripper/grasping',  # Changed topic name
            self.object_grasping,
            callback_group=self.client_cb_group0,
            qos_profile=self.qos_profile,
        )

        # Change from service to publisher for vacuum gripper
        self.vacuum_enable_publisher = self.create_publisher(
            Bool,
            '/arm1/vacuum_gripper/enable',  # Changed topic name
            10
        )

    def object_location_cb(self, pose):
        if self.last_pose == None:
            self.last_pose = deepcopy(pose)

    def object_grasping(self, msg):
        self.grasping = msg.data

    def gripper_on(self):
        self.grasping = False
        msg = Bool()
        msg.data = True
        self.vacuum_enable_publisher.publish(msg)
        self.logger.info("Vacuum gripper enabled")

    def gripper_off(self):
        msg = Bool()
        msg.data = False
        self.vacuum_enable_publisher.publish(msg)
        self.logger.info("Vacuum gripper disabled")


class Setup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.gripper_off()
        intermediat_stage = [0.5, 0.5, 0.055]
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=intermediat_stage,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True,
            frame_id='world',
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        return 'home'


class Home(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['wait', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.gripper_off()
        home_pos = [0.5, -0.5, 0.055]
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=home_pos, quat_xyzw=[1.0, 0.0, 0.0, 0.0], cartesian=True, frame_id='world'
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        return 'wait'


class Wait(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approach', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.last_pose = None
        while (
            self.robot_controller.get_parameter('state').value == 'wait'
            or self.robot_controller.last_pose is None
        ):
            time.sleep(0.1)

        return 'approach'


class ApproachObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['approached', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        target_pos = [self.robot_controller.last_pose.pose.position.x - 0.18, -0.4, 0.055]
        quat_xyzw = [1.0, 0.0, 0.0, 0.0]
        self.robot_controller.logger.info(
            f'Execution going to  {target_pos}, {self.robot_controller.last_pose.pose.position.y}'
        )
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=target_pos, quat_xyzw=quat_xyzw, cartesian=True
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()
        return 'approached'


class GraspObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['grasped', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        self.robot_controller.logger.info('Before grasp')
        self.robot_controller.gripper_on()

        pose = self.robot_controller.last_pose
        timeout = 5.0  # 5 sekund timeout
        start_time = time.time()

        while (
            self.robot_controller.grasping == False
            and pose.name == self.robot_controller.last_pose.name
            and (time.time() - start_time) < timeout
        ):
            time.sleep(0.1)

        if self.robot_controller.grasping:
            self.robot_controller.logger.info("Object successfully grasped!")
            return 'grasped'
        else:
            self.robot_controller.logger.warn("Failed to grasp object - timeout or object moved")
            return 'failed'


class PlaceObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['placed', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        # Code to place the object
        pos1 = utils.entity_location(self.robot_controller, 'amr1', 'arm1')
        self.turtlebot_pos = [pos1.position.x, pos1.position.y, 0.20]

        # First move to the target location
        above_pos = [pos1.position.x, pos1.position.y, 0.35]
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=above_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Check if we are still holding the object
        if not self.robot_controller.grasping:
            self.robot_controller.logger.error("Lost object during transport!")
            return 'failed'

        # Place the object on target location
        self.robot_controller.moveit2_robot0.move_to_pose(
            position=self.turtlebot_pos,
            quat_xyzw=[1.0, 0.0, 0.0, 0.0],
            cartesian=True
        )
        self.robot_controller.moveit2_robot0.wait_until_executed()

        # Turn off vacuum
        time.sleep(0.5)
        self.robot_controller.gripper_off()
        time.sleep(1.0)

        self.robot_controller.logger.info("Object placed and vacuum disabled")
        return 'placed'


class TransferObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home', 'failed'])
        self.robot_controller = robot_controller

    def execute(self, userdata):
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('point_x', Parameter.Type.DOUBLE, -6.7),
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('point_y', Parameter.Type.DOUBLE, 1.0),
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('object_name', Parameter.Type.STRING, self.robot_controller.last_pose.name),
        )
        utils.call_set_parameters(
            self.robot_controller,
            '/amr1/AMRController',
            Parameter('state', Parameter.Type.STRING, 'goto'),
        )
        self.robot_controller.set_parameters([Parameter('state', Parameter.Type.STRING, 'wait')])
        return 'home'


def run_smach(client):
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
            'TRANSFER', TransferObject(client), transitions={'home': 'HOME', 'failed': 'HOME'}
        )

    # Execute SMACH plan
    sm.execute()


def main(args=None):
    rclpy.init(args=args)
    args_without_ros = rclpy.utilities.remove_ros_args(args)

    robot_controller = RobotController(args_without_ros)
    robot_controller.get_logger().info('Robot Controller started')
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
