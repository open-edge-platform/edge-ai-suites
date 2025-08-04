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

#include <gtest/gtest.h>

#include <rclcpp/rclcpp.hpp>
#include <univloc_msgs/msg/lidar_status.hpp>

int pose_failure_num = -1;
int feature_failure_num = -1;
int lidar_pose_failure_threshold = 15;
int lidar_feature_failure_threshold = 150;

class TrackerMonitor : public rclcpp::Node
{
public:
    TrackerMonitor()
    : Node("tracker_monitor")
    {
        lidar_pose_failure_threshold = declare_parameter<int>("lidar_pose_failure_threshold", 15);
        lidar_feature_failure_threshold = declare_parameter<int>("lidar_feature_failure_threshold", 150);
        auto qos = rclcpp::SensorDataQoS();
        sub_lidar_states_ = this->create_subscription<univloc_msgs::msg::LidarStatus>(
        "univloc_tracker_0/lidar_states", qos, std::bind(&TrackerMonitor::lidar_states_callback, this, std::placeholders::_1));
    }

    std::pair<int,int> get_failure_num() const
    {
        return {states_.first, states_.second};
    }

private:

    void lidar_states_callback(const univloc_msgs::msg::LidarStatus::SharedPtr msg)
    {
        int feature_failure_count = msg->feature_failure_count;
        int pose_failure_count = msg->pose_failure_count;
        states_ = {feature_failure_count, pose_failure_count};
    }
    rclcpp::Subscription<univloc_msgs::msg::LidarStatus>::SharedPtr sub_lidar_states_;
    std::pair<int, int> states_ = {-1, -1};
};

std::shared_ptr<TrackerMonitor> node;

TEST(testLidarSystem, testLidarSystem)
{
    node = std::make_shared<TrackerMonitor>();
    rclcpp::spin(node);

    node.reset();

    if (feature_failure_num > lidar_feature_failure_threshold) {
        std::cout << "Lidar feature failure num: " << feature_failure_num <<
        " which is larger than threshold: " << lidar_feature_failure_threshold;
        FAIL();
    } else if (pose_failure_num > lidar_pose_failure_threshold) {
        std::cout << "Lidar pose failure num: " << pose_failure_num <<
        " which is larger than threshold: " << lidar_pose_failure_threshold;
        FAIL();
    } else if (feature_failure_num < 0 || pose_failure_num < 0) {
        std::cout << "Test initialization failed";
        FAIL();
    } else {
        std::cout << "Lidar feature failure num: " << feature_failure_num <<
        " which is less than threshold: " << lidar_feature_failure_threshold<<std::endl;

        std::cout << "Lidar pose failure num: " << pose_failure_num <<
        " which is less than threshold: " << lidar_pose_failure_threshold<<std::endl;
    }
    SUCCEED();
}

void sigint_handler(int)
{
    rclcpp::shutdown();
    feature_failure_num = node->get_failure_num().first;
    pose_failure_num = node->get_failure_num().second;
}

int main(int argc, char * argv[])
{
    ::testing::InitGoogleTest(&argc, argv);

    rclcpp::init(argc, argv);
    signal(SIGINT, sigint_handler);

    bool all_successful = RUN_ALL_TESTS();
    return all_successful;
}