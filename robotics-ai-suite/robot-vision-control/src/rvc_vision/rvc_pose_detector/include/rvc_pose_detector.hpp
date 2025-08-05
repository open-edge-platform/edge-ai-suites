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

#pragma once


#include <cmath>
#include <deque>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "rclcpp/rclcpp.hpp"

#include "rvc_messages/msg/pose_stamped_list.hpp"
#include "rvc_vision_messages/msg/rotated_bb.hpp"
#include "rvc_vision_messages/msg/rotated_bb_list.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "rvc_messages/msg/pose_stamped.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"

#include <message_filters/subscriber.h>
#include <message_filters/synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <message_filters/sync_policies/exact_time.h>

#include <pcl_conversions/pcl_conversions.h>

#include <tf2_eigen/tf2_eigen.hpp>
#include "matcher.hpp"

namespace RVC
{
struct MatchOperation
{
    rvc_vision_messages::msg::RotatedBBList::SharedPtr rotated_bb_list;
    sensor_msgs::msg::PointCloud2::UniquePtr cloud;
};

class PoseDetector : public rclcpp::Node
{
private:

    message_filters::Subscriber<rvc_vision_messages::msg::RotatedBBList> m_rotated_bb_list_sub;
    message_filters::Subscriber<sensor_msgs::msg::PointCloud2> m_pcl_sub;
    //typedef message_filters::sync_policies::ExactTime<rvc_messages::msg::RoiList, sensor_msgs::msg::PointCloud2> RVCSyncPolicy;
    typedef message_filters::sync_policies::ApproximateTime<sensor_msgs::msg::PointCloud2,
            rvc_vision_messages::msg::RotatedBBList> RVCSyncPolicy;

    typedef message_filters::Synchronizer<RVCSyncPolicy> MySync;
    std::shared_ptr<MySync> synchronizer;

    rclcpp::Publisher<rvc_messages::msg::PoseStampedList>::SharedPtr m_pub_poses;
    rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr m_pub_cloud;

    // per-object matcher data
    std::map<std::string, ObjectMatcher> m_matchers;

    // object classes
    std::vector<std::string> m_obj_classes;

    std::deque<std::string> classIds;
    rclcpp::CallbackGroup::SharedPtr my_callback_group;

private:
    // methods
    std::string mostFrequentClass(std::deque<std::string> dq);
    void SynchronizedCallback(
        const sensor_msgs::msg::PointCloud2::ConstSharedPtr m_last_cloud,
        rvc_vision_messages::msg::RotatedBBList::ConstSharedPtr m_rotated_bb_msg);
    geometry_msgs::msg::Pose mat44_to_pose(const Eigen::Matrix4f & mat);

public:
    explicit PoseDetector(const rclcpp::NodeOptions & options);
    ~PoseDetector()
    {
    }

};
}
