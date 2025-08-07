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

#include <gtest/gtest.h>

#include <geometry_msgs/msg/pose.hpp>
#include <tf2/LinearMath/Quaternion.h>

#include "oriented_grasp/oriented_grasp.hpp"

using namespace RVCControl;
class TestableOrientedGrasp : public OrientedGrasp
{
public:
   using OrientedGrasp::Axis;
   using OrientedGrasp::getRotatedPose;
};

TEST(OrientedGraspTest, TestGetRotatedPoseX)
{
   TestableOrientedGrasp grasp;
   geometry_msgs::msg::Pose basePose;
   basePose.position.x = 1.0;
   basePose.position.y = 2.0;
   basePose.position.z = 3.0;
   tf2::Quaternion q;
   q.setRPY(0, 0, 0);  // Set initial orientation to be zero rotation
   basePose.orientation = tf2::toMsg(q);
   // Act: Rotate by 90 degrees on the X axis
   auto rotatedPose = grasp.getRotatedPose(basePose, TestableOrientedGrasp::Axis::X, M_PI/2);

   // Assert: Position must be unchanged
   EXPECT_DOUBLE_EQ(rotatedPose.position.x, basePose.position.x);
   EXPECT_DOUBLE_EQ(rotatedPose.position.y, basePose.position.y);
   EXPECT_DOUBLE_EQ(rotatedPose.position.z, basePose.position.z);

   // Assert: Positive rotation by 90 degrees only on the X-axis
   tf2::Quaternion rotatedOrientation;
   tf2::fromMsg(rotatedPose.orientation, rotatedOrientation);
   tf2::Matrix3x3 rotationMatrix(rotatedOrientation);
   double roll, pitch, yaw;
   rotationMatrix.getRPY(roll, pitch, yaw);
   EXPECT_DOUBLE_EQ(roll, M_PI/2);
   EXPECT_DOUBLE_EQ(pitch, 0);
   EXPECT_DOUBLE_EQ(yaw, 0);
}

int main(int argc, char** argv)
{
   testing::InitGoogleTest(&argc, argv);

   // initialize ROS
   rclcpp::init(argc, argv);

   bool all_successful = RUN_ALL_TESTS();

   // shutdown ROS
   rclcpp::shutdown();

   return all_successful;
}
