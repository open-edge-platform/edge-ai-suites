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

# Desc: Controller program for AMR
import sys
import threading
import time
from copy import deepcopy

# Third-Party Library Imports
import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.logging import LoggingSeverity
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import Bool
from std_srvs.srv import SetBool
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from smach import State, StateMachine
from rclpy.parameter import Parameter

# Custom Module Imports
from robot_config import utils
from picknplace.msg import BoxState
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

class RobotController(Node):
    def __init__(self, args):
        super().__init__('AMRController')
        
        self.declare_parameter('state', 'wait')
        self.declare_parameter('point_x', 0.0)
        self.declare_parameter('point_y', 0.0)
        self.declare_parameter('object_name', '')

        self.setup_qos_and_groups()

        self.navigator = BasicNavigator()
        self.setup_logging()

        self.grasping = False
        self.setup_subscriptions_and_services()

    def setup_qos_and_groups(self):
        self.qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.callback_group0 = MutuallyExclusiveCallbackGroup()
        self.gripper_group0 = MutuallyExclusiveCallbackGroup()
        self.client_cb_group0 = MutuallyExclusiveCallbackGroup()
        self.moveit_callback_group0 = MutuallyExclusiveCallbackGroup()
        time.sleep(1)


    def setup_logging(self):
        self.logger = self.get_logger()
        self.logger.set_level(LoggingSeverity.INFO)

    def setup_subscriptions_and_services(self):
        return

    def object_location_cb(self, pose):
        self.last_pose = deepcopy(pose)

    def object_grasping(self, msg):
        self.grasping = msg.data

    def amr_goto_pose(self, x, y, z):
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'map'
        goal_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        goal_pose.pose.position.x = x
        goal_pose.pose.position.y = y
        goal_pose.pose.orientation.z = z
        goal_pose.pose.orientation.w = 1.0
        self.navigator.goToPose(goal_pose)

class Setup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['wait','failed'])
        self.robot_controller=robot_controller

    def execute(self, userdata):
        return 'wait'
      
class Home(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['wait','failed'])
        self.robot_controller=robot_controller

    def execute(self, userdata):
        self.robot_controller.amr_goto_pose(-0.1, -.3, 0.004)
        return 'wait'
    
class Wait(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['transfer','failed'])
        self.robot_controller=robot_controller

    def execute(self, userdata):
        self.robot_controller.last_pose = None
        while self.robot_controller.get_parameter('state').value == 'wait':
            time.sleep(0.5)

        return 'transfer'
    
class TransferObject(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['transferred', 'failed'])
        self.robot_controller=robot_controller

    def execute(self, userdata):
        x = float(self.robot_controller.get_parameter('point_x').value)
        y = float(self.robot_controller.get_parameter('point_y').value)
        print(f"Going to {x}, {y}")
        self.robot_controller.amr_goto_pose(x,y,0.004)
        while not self.robot_controller.navigator.isTaskComplete():
                time.sleep(0.5)

        return 'transferred'

class WaitForPickup(State):
    def __init__(self, robot_controller):
        State.__init__(self, outcomes=['home','failed'])
        self.robot_controller=robot_controller

    def execute(self, userdata):
        self.robot_controller.set_parameters([
            Parameter('state', Parameter.Type.STRING, 'wait')            
        ])

        utils.call_set_parameters(self.robot_controller, "/ARM2Controller", Parameter('object_name', Parameter.Type.STRING, self.robot_controller.get_parameter('object_name').value))

        utils.call_set_parameters(self.robot_controller, "/ARM2Controller", Parameter('state', Parameter.Type.STRING, 'move'))

        while self.robot_controller.get_parameter('state').value == 'wait':
            time.sleep(0.5)

        return 'home'
    
def run_smach(client):
    # Create the top level SMACH state machine
    sm = StateMachine(outcomes=['succeeded', 'aborted'])
    with sm:
            StateMachine.add('SETUP', Setup(client), transitions={'wait':'WAIT', 'failed':'WAIT'})
            StateMachine.add('HOME', Home(client), transitions={'wait':'WAIT', 'failed':'HOME'})
            StateMachine.add('WAIT', Wait(client), transitions={'transfer':'TRANSFER', 'failed':'HOME'})
            StateMachine.add('TRANSFER', TransferObject(client), transitions={'transferred':'WAITFORPICKUP', 'failed':'HOME'})
            StateMachine.add('WAITFORPICKUP', WaitForPickup(client), transitions={'home':'HOME', 'failed':'HOME'})

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

