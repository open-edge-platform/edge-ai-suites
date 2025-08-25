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

#include <memory>
#include <string>
#include <atomic>

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/point32.h>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include "test_utils.h"

int pose_num = 0;
int pose_threshold = 0;

class TrackerMonitor : public rclcpp::Node
{
public:
    TrackerMonitor()
    : Node("tracker_monitor")
    {
        pose_threshold = declare_parameter<int>("pose_threshold", 0);

        auto qos = rclcpp::SensorDataQoS();
        sub_pose_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
        "univloc_tracker_0/pose", qos, std::bind(&TrackerMonitor::pose_callback, this, std::placeholders::_1));
    }

    int get_pose_num() const
    {
        return pose_num_;
    }

private:
    void pose_callback(const geometry_msgs::msg::PoseStamped::SharedPtr msg)
    {
        if (msg->header.frame_id == "") {
            return;
        }

        univloc_tracker::robot_pose current_pose;
        geometry_msgs::msg::Point pose_position = msg->pose.position;
        geometry_msgs::msg::Quaternion pose_orientation = msg->pose.orientation;

        current_pose.position_x_ = pose_position.x;
        current_pose.position_y_ = pose_position.y;
        current_pose.position_z_ = pose_position.z;
        current_pose.orientation_x_ = pose_orientation.x;
        current_pose.orientation_y_ = pose_orientation.y;
        current_pose.orientation_z_ = pose_orientation.z;
        current_pose.orientation_w_ = pose_orientation.w;

        /*
            For a normal tracker pose, it needs to meet below 2 conditions
            1. At least one of the elements of pose matrix shouldn't be 0
            2. The current pose shouldn't be totally the same as the previous one,
               even though the robot is static, the poses can have slight differences
        */
        if (current_pose == 0.0 || current_pose == last_pose_) return;

        last_pose_ = current_pose;
        pose_num_++;
    }
    rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_pose_;
    univloc_tracker::robot_pose last_pose_;
    std::atomic_int pose_num_ = 0;
};

std::shared_ptr<TrackerMonitor> node;

void sigint_handler(int)
{
    rclcpp::shutdown();
    pose_num = node->get_pose_num();
}

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    signal(SIGINT, sigint_handler);

    node = std::make_shared<TrackerMonitor>();
    rclcpp::spin(node);

    node.reset();

    if (pose_num > pose_threshold) {
        std::cout << "Tracker total published pose num: " << pose_num << " larger than threshold: " << pose_threshold;
        exit(0);
    } else {
        std::cout << "Tracker total published pose num: " << pose_num << " smaller than threshold: " << pose_threshold;
        exit(1);
    }
}
