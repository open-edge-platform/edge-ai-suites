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
#include <any>
#include <iostream>

#include <gtest/gtest.h>

#include "std_msgs/msg/string.hpp"
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/point32.h>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include "univloc_msgs/msg/keyframe.hpp"
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include "fast_mapping_helper.h"
#include "fast_mapping_param.h"
#include "test_utils.h"

int pose_num = 0;
int pose_threshold = 0;

bool map_merge_happen = false;
bool octree_map_merge_happen = false;

int keyframes_within_remapping_region_num = 0;
int keyframes_within_remapping_region_num_threshold = 0;

int octree_within_remapping_region_num = 0;
int octree_within_remapping_region_num_threshold = 0;

class RemappingTest : public rclcpp::Node {
public:
    RemappingTest() : Node("test_remapping")
    {
        pose_threshold = declare_parameter<int>("pose_threshold", 0);
        keyframes_within_remapping_region_num_threshold = declare_parameter<int>("keyframes_threshold", 0);
        octree_within_remapping_region_num_threshold = declare_parameter<int>("voxels_threshold", 0);

        std::vector<double> remapping_descriptor;
        remapping_region_vertexes_ = declare_parameter<std::vector<double>>("remapping_region", remapping_descriptor);

        struct fast_mapping::point_2d remapping_region_vertexes[4];
        for (unsigned int i = 0; i < 4; i++) {
            remapping_region_vertexes[i].x_ = remapping_region_vertexes_[2 * i];
            remapping_region_vertexes[i].y_ = remapping_region_vertexes_[2 * i + 1];
        }
        remapping_region_ = std::make_unique<fast_mapping::remapping_region>(remapping_region_vertexes);

        // Qos with KeepAll setting means the system will store all published poses by tracker as much as
        // possible to pass the test.
        auto qos = rclcpp::QoS{rclcpp::KeepAll()};
        pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
            "univloc_tracker_0/pose", qos, std::bind(&RemappingTest::pose_callback, this, std::placeholders::_1));

        // SensorDataQoS means the system will store the latest data as soon as they are captured. And our purpose
        // is also to obtain the number of keyframes and voxels within remapping region before system exit.
        auto qos_sensor_data = rclcpp::SensorDataQoS();
        map_merge_marker_sub_ = this->create_subscription<visualization_msgs::msg::MarkerArray>(
            std::string("/univloc_server/keyframes"), qos_sensor_data,
            std::bind(&RemappingTest::keyframe_callback, this, std::placeholders::_1));

        octree_map_merge_marker_sub_ = this->create_subscription<visualization_msgs::msg::MarkerArray>(
            std::string("univloc_tracker_0/fused_map"), qos_sensor_data,
            std::bind(&RemappingTest::octree_callback, this, std::placeholders::_1));
    }

    ~RemappingTest() {}

    int get_pose_num() const { return pose_num_; }

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
            For a normal tracker pose in remapping mode, it needs to meet below 2 conditions
            1. At least one of the elements of pose matrix shouldn't be 0
            2. The current pose shouldn't be totally the same as the previous one,
               even though the robot is static, the poses can have slight differences
        */
        if (current_pose == 0.0 || current_pose == last_pose_) return;

        last_pose_ = current_pose;
        pose_num_++;
    }

    bool is_map_merge_successful() const { return is_map_merge_successful_; }

    void keyframe_callback(const visualization_msgs::msg::MarkerArray::SharedPtr msg)
    {
        keyframes_within_remapping_region_num_ = 0;
        is_map_merge_successful_ = false;

        for (auto& m : msg->markers) {
            std::string ns = m.ns;
            std::string::size_type idx_front = ns.find(map_merge_expected_marker1);
            std::string::size_type idx_rear = ns.find(map_merge_expected_marker2);

            if (idx_front != std::string::npos && idx_rear != std::string::npos) {
                is_map_merge_successful_ = true;
            }
        }

        if (!is_map_merge_successful_) {
            return;
        }

        for (auto& m : msg->markers) {
            if (m.ns == "client-0-0") {
                // We use seven points to form a rectangle to represent each keyframe in rviz on server side. The
                // starting point (1-th) and ending point (7-th) represent the position of keyframe in world
                // coordinates.
                for (unsigned long int i = 0; i < m.points.size(); i += 7) {
                    auto keyframe_coord_x = m.points[i].x;
                    auto keyframe_coord_y = m.points[i].y;
                    if (remapping_region_->within_remapping_region({keyframe_coord_x, keyframe_coord_y})) {
                        keyframes_within_remapping_region_num_++;
                    }
                }
            }
        }
    }

    bool is_octree_map_merge_successful() const { return is_octree_map_merge_successful_; }

    void octree_callback(const visualization_msgs::msg::MarkerArray::SharedPtr msg)
    {
        octree_within_remapping_region_num_ = 0;
        is_octree_map_merge_successful_ = false;

        auto m = msg->markers[0];
        std::string ns = m.ns;
        if (ns != octree_merge_expected_marker) {
            return;
        }

        is_octree_map_merge_successful_ = true;
        for (auto& i : m.points) {
            auto voxel_coord_x = i.x;
            auto voxel_coord_y = i.y;
            if (remapping_region_->within_remapping_region({voxel_coord_x, voxel_coord_y})) {
                octree_within_remapping_region_num_++;
            }
        }
    }

    int get_keyframes_within_remapping_region_num() const { return keyframes_within_remapping_region_num_; }

    int get_octree_within_remapping_region_num() const { return octree_within_remapping_region_num_; }

private:
    rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr pose_sub_;
    rclcpp::Subscription<visualization_msgs::msg::MarkerArray>::SharedPtr map_merge_marker_sub_;
    rclcpp::Subscription<visualization_msgs::msg::MarkerArray>::SharedPtr octree_map_merge_marker_sub_;

    std::string map_merge_expected_marker1 = "loop";
    std::string map_merge_expected_marker2 = "MapID: 0";
    std::string octree_merge_expected_marker = "octree_map_merged";

    bool is_map_merge_successful_ = false;
    bool is_octree_map_merge_successful_ = false;

    univloc_tracker::robot_pose last_pose_;

    std::atomic_int pose_num_ = 0;
    std::atomic_int keyframes_within_remapping_region_num_ = 0;
    std::atomic_int octree_within_remapping_region_num_ = 0;

    std::unique_ptr<fast_mapping::remapping_region> remapping_region_;
    std::vector<double> remapping_region_vertexes_;
};

std::shared_ptr<RemappingTest> testRemapping;

TEST(testRemappingMode, testRemappingMode)
{
    testRemapping = std::make_shared<RemappingTest>();
    rclcpp::spin(testRemapping);

    testRemapping.reset();

    /*
        For a normal tracker and server in remapping mode, it needs to meet below 4 conditions.
        1. The number of published poses successfully tracked by tracker node should be higher than a certain threshold.
        2. Some special characters should be detected that only occur when map merge happens.
        3. The number of keyframe newly constructed in remapping region should be higher than a certain threshold.
        4. The number of voxels newly constructed in remapping region should be higher than a certainthreshold.
    */
    if (pose_num > pose_threshold) {
        std::cout << "The number of published poses successfully tracked by tracker node: " << pose_num
                  << " is larger than threshold: " << pose_threshold << std::endl;
    } else {
        std::cout << "The number of published poses successfully tracked by tracker node: " << pose_num
                  << " is smaller than threshold: " << pose_threshold << std::endl;
        FAIL();
    }

    if (map_merge_happen) {
        std::cout << "Detected \"loop\" and \"MapID: 0\" from univloc_server/keyframes topic!" << std::endl;
    } else {
        std::cout << "Didn't detected \"loop\" and \"MapID: 0\" from univloc_server/keyframes topic!" << std::endl;
        FAIL();
    }

    if (octree_map_merge_happen) {
        std::cout << "Detected \"octree_map_merged\" from univloc_tracker_0/fused_map topic!" << std::endl;
    } else {
        std::cout << "Didn't detected \"octree_map_merged\" from univloc_tracker_0/fused_map topic!" << std::endl;
        FAIL();
    }

    if (keyframes_within_remapping_region_num > keyframes_within_remapping_region_num_threshold &&
        octree_within_remapping_region_num > octree_within_remapping_region_num_threshold) {
        std::cout << "The number of keyframes newly constructed within remapping_region: "
                  << keyframes_within_remapping_region_num
                  << " is larger than threshold: " << keyframes_within_remapping_region_num_threshold << std::endl;
        std::cout << "The number of voxels newly constructed within remapping_region: "
                  << octree_within_remapping_region_num
                  << " is larger than threshold: " << octree_within_remapping_region_num_threshold << std::endl;
    } else {
        std::cout << "The number of keyframes newly constructed within remapping_region is "
                  << keyframes_within_remapping_region_num << " with threshold "
                  << keyframes_within_remapping_region_num_threshold << std::endl;
        std::cout << "The number of voxels newly constructed within remapping_region is "
                  << octree_within_remapping_region_num << " with threshold "
                  << octree_within_remapping_region_num_threshold << std::endl;
        FAIL();
    }

    SUCCEED();
}

void sigint_handler(int)
{
    rclcpp::shutdown();
    pose_num = testRemapping->get_pose_num();
    map_merge_happen = testRemapping->is_map_merge_successful();
    octree_map_merge_happen = testRemapping->is_octree_map_merge_successful();

    keyframes_within_remapping_region_num = testRemapping->get_keyframes_within_remapping_region_num();
    octree_within_remapping_region_num = testRemapping->get_octree_within_remapping_region_num();
}

int main(int argc, char* argv[])
{
    ::testing::InitGoogleTest(&argc, argv);

    rclcpp::init(argc, argv);

    signal(SIGINT, sigint_handler);

    bool all_successful = RUN_ALL_TESTS();

    return all_successful;
}
