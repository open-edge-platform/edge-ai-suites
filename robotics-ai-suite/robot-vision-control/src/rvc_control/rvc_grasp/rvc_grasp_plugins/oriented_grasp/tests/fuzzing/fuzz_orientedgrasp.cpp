// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "oriented_grasp/oriented_grasp.hpp"

#include "gtest/gtest.h"
#include "fuzztest/fuzztest.h"

using namespace RVCControl;

void testOnMessageReceive(double positionX, double positionY, double positionZ,
                          double orientationX, double orientationY, double orientationZ, double orientationW,
                          bool isWorldFrame)
{
   // initialize ROS
   int argc = 0;
   char** argv = nullptr;
   rclcpp::init(argc, argv);

   OrientedGrasp orientedGrasp;
   rclcpp::Node::SharedPtr fuzzNode = rclcpp::Node::make_shared("fuzzNode");
   orientedGrasp.init(fuzzNode);

   geometry_msgs::msg::Pose pose;
   pose.position.x = positionX;
   pose.position.y = positionY;
   pose.position.z = positionZ;
   pose.orientation.x = orientationX;
   pose.orientation.y = orientationY;
   pose.orientation.z = orientationZ;
   pose.orientation.w = orientationW;

   // Create a list of messages containing only one message (the others are discarded by the code)
   auto message = std::make_shared<rvc_messages::msg::PoseStampedList>();
   rvc_messages::msg::PoseStamped poseStamped;
   // Only cube is currently supported
   poseStamped.obj_type = "cube";
   if (isWorldFrame)
      poseStamped.pose_stamped.header.frame_id = "world";
   else
      poseStamped.pose_stamped.header.frame_id = "non_world";
   poseStamped.pose_stamped.pose = pose;
   message->poses.push_back(poseStamped);

   orientedGrasp.OnMessageReceive(message);

   // shutdown ROS
   rclcpp::shutdown();
}
FUZZ_TEST(ReceiverTest, testOnMessageReceive);
