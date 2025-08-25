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

# Desc:  Utility routines 


import math
import time
import rclpy
import random
import string
from rclpy.node import Node
from rcl_interfaces.srv import SetParameters, GetParameters
from gazebo_msgs.srv import GetEntityState
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from geometry_msgs.msg import Pose
from std_msgs.msg import String
import subprocess

# Generate a random name
def generate_name():
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(4))

# Sets Node parameter value.
# Parameters:
#     self_node : Node to be used to send request
#     node_name : Target node name
#     parameter : Parameter object
# Usage: 
#     utils.call_set_parameters(node, Target_Node_Name, Parameter('state', Parameter.Type.STRING, 'move'))

def call_set_parameters(self_node, node_name, parameter):
    try:
        use_async=False
        if self_node is None:
            self_node = Node(f"get_param_{generate_name()}")
            use_async = True
        # create client
        client = self_node.create_client(
            SetParameters, f'{node_name}/set_parameters')

        # call as soon as ready
        ready = client.wait_for_service(timeout_sec=30.0)
        if not ready:
            raise RuntimeError('Wait for service timed out')

        request = SetParameters.Request()
        request.parameters = [parameter.to_parameter_msg()]
        if use_async == True:
            future = client.call_async(request)
            rclpy.spin_until_future_complete(self_node, future)
            return future.result()
        else:
            result = client.call(request)

    except Exception as e:
        self_node.get_logger().error(f"Exception occured: {e} - {node_name}")


# Returns target node parameter
def call_get_parameters(self_node, node_name, param_name, sync=False):
    try:
        use_async=False
        if self_node is None:
            self_node = Node(f"get_param_{generate_name()}")
            use_async = True

        client = self_node.create_client(
            GetParameters, f'{node_name}/get_parameters')

        # call as soon as ready
        ready = client.wait_for_service(timeout_sec=30.0)
        
        if not ready:
            raise RuntimeError('Wait for service timed out')
        
        while True:
            request = GetParameters.Request()
            request.names = [param_name]
            #future  = client.call(request)
            if use_async == True:
                future  = client.call_async(request)
                rclpy.spin_until_future_complete(self_node, future)            
                if future.result().values[0].type != 0 or sync==False:
                    self_node.destroy_node()
                    return future.result()
                
            else:
                result = client.call(request)
                if result.values[0].type != 0 or sync==False:
                    return result

            time.sleep(1)
            self_node.get_logger().info(f'Waiting for {param_name} to appear on {node_name}...')

    except Exception as e:
        self_node.get_logger().error(f"Exception occured: {e} - {node_name}")

# Utility function providing synchronization through ros2 tool.
# Subscribes to a topic and waits for atleast one message is received.
def wait_for_event(name):
    cmd = f"ros2 topic echo --once --qos-reliability  reliable /event_{name} std_msgs/msg/Empty"
    process = subprocess.Popen(cmd, shell=True)
    process.wait()

# Utility function providing synchronization through ros2 tool.
# Publishes a topic and waits until atleast one client available.
def set_event(name):
    cmd = f"ros2 topic pub --once -w 1 --qos-reliability reliable  /event_{name} std_msgs/msg/Empty"
    process = subprocess.Popen(cmd, shell=True)
    process.wait()
    
# Waits for ROS2 interface (topic, service, action) to become available
# Issues: Also returns true if client is created first before publisher or server.
def wait_for_interface(self_node, interface_type, interface_name):
        
        node_del = False
        if self_node is None:
            self_node = Node(f"wait_intf_{generate_name()}")
            node_del = True

        self_node.get_logger().info(f'Going to wait for If {interface_type} {interface_name}')
        counter = 0
        while rclpy.ok():
            if interface_type == 'topic':
                # get_topic_names_and_types returns a list of tuples, where each tuple contains a topic name and a list of topic types
                interface_list = self_node.get_topic_names_and_types()

            elif interface_type == 'service' or interface_type == 'action':
                # get_service_names_and_types returns a list of tuples, where each tuple contains a service name and a list of service types
                interface_list = self_node.get_service_names_and_types()

            for interface, _ in interface_list:
                if interface_type == 'action':
                    if interface_name in interface and '_action' in interface:
                        self_node.get_logger().info(f'{interface_type.capitalize()} {interface_name} is up and running.')
                        if node_del == True:
                            self_node.destroy_node()
                        return
                    
                if interface == interface_name:
                    self_node.get_logger().info(f'{interface_type.capitalize()} {interface_name} is up and running.')
                    if node_del == True:
                            self_node.destroy_node()
                    return
            time.sleep(1)        

            if counter ==  0:
                self_node.get_logger().info(f'Waiting for {interface_type} {interface_name}...')
            
            counter = (counter + 1) % 6

# Returns Gazebo model entity location in the world.  Uses /get_entity_state service
def entity_location(self_node, entity_name, reference_frame='world'):
    try:
        # create client
        client = self_node.create_client(
            GetEntityState, '/get_entity_state', callback_group=MutuallyExclusiveCallbackGroup())

        # call as soon as ready
        ready = client.wait_for_service(timeout_sec=5.0)
        if not ready:
            raise RuntimeError('Wait for service timed out')

        req = GetEntityState.Request()
        req.name = entity_name
        req.reference_frame = reference_frame
        srv_call = client.call(req)
        if srv_call.success == False:
            self_node.get_logger().error(f'{entity_name} not found')
        return srv_call.state.pose
    except Exception as e:
        self_node.get_logger().error(f"Exception occured: {e} - {entity_name}")

# Return True if point is within a rectangular area
def pointInRect(pose, rect):
    x1, y1, x2, y2 = rect[0], rect[1], rect[2], rect[3]

    if (pose.position.x >= x1 and pose.position.x <= x2):
        if (pose.position.y >= y1 and pose.position.y <= y2):
            return True
    return False

# Returns Quaternion from Euler coordinates.
def quaternion_from_euler(roll, pitch, yaw):
    qx = math.sin(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) - math.cos(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)
    qy = math.cos(roll/2) * math.sin(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.cos(pitch/2) * math.sin(yaw/2)
    qz = math.cos(roll/2) * math.cos(pitch/2) * math.sin(yaw/2) - math.sin(roll/2) * math.sin(pitch/2) * math.cos(yaw/2)
    qw = math.cos(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)

    return qx, qy, qz, qw
