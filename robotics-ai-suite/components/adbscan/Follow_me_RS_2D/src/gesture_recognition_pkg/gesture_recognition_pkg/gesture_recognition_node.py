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

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from follow_me_interfaces.msg import GestureCategory

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
from cv_bridge import CvBridge
import os
from ament_index_python.packages import get_package_share_directory
import time

class gesture_recognizer(Node):
    def __init__(self):
        super().__init__("gesture_recognizer_node")
        self.count_ = 0
        self.get_logger().info("gesture_recognizer_node has been started")
        # declare parameters
        self.declare_parameter("Camera_topic", "/camera/color/image_raw")
        self.declare_parameter("simulated_camera_topic", "/sim_camera")
        self.simulation_mode_ = self.get_parameter('use_sim_time').value
        if self.simulation_mode_:
            self.camera_topic_name_ = self.get_parameter("simulated_camera_topic").value
        else:
            self.camera_topic_name_ = self.get_parameter("Camera_topic").value
        # self.model_file_ = self.get_parameter("model_file_location").value
        self.model_file_ = os.path.join(get_package_share_directory('gesture_recognition_pkg'), 'config','gesture_recognizer.task')
        if not os.path.isfile(self.model_file_):
            self.get_logger().error("The model file does not exist. Please provide a valid filename as model_file_location parameter")
        self.image_subscriber_ = self.create_subscription(Image, self.camera_topic_name_, self.camera_topic_callback, 10)
        self.gesture_publisher_ = self.create_publisher(GestureCategory, "gesture", 10)
        

    def camera_topic_callback(self, msg):
        self.get_logger().info("Subscribed to camera topic")
        start = time.time()
        # Create an GestureRecognizer object.
        VisionRunningMode = mp.tasks.vision.RunningMode
        base_options = python.BaseOptions(model_asset_path=self.model_file_)
        options = vision.GestureRecognizerOptions(base_options=base_options, running_mode=VisionRunningMode.IMAGE)
        recognizer = vision.GestureRecognizer.create_from_options(options)
        # Load the input image.
        bridge = CvBridge()
        cv_image = bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        # convert cv_image from BGR to RGB image
        # img1 = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        if self.simulation_mode_:
            # convert cv_image from BGR to RGB image
            img1 = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        else:
            img1 = cv_image

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img1)
        # Perform gesture recognition on the provided single image.
        # The gesture recognizer must be created with the image mode.
        recognition_result = recognizer.recognize(mp_image)
        if len(recognition_result.gestures) == 0:
            category_name = "No_Action"
        else:
            top_gesture = recognition_result.gestures[0][0]
            category_name = top_gesture.category_name

        self.publish_gesture(category_name)
        gesture_pub_time = (time.time() - start)*1000
        self.get_logger().info("Gesture publishing time = {} ms".format(str(gesture_pub_time)))


    def publish_gesture(self, gesture_category):
        gesture_msg = GestureCategory()
        gesture_msg.gesture_category = gesture_category
        self.gesture_publisher_.publish(gesture_msg)
        self.get_logger().info("Publishing gesture msg: {}".format(gesture_category))

def main(args=None):
    rclpy.init(args= args)
    node = gesture_recognizer()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()

    