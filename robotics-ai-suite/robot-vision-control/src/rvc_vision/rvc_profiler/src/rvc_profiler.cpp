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

#include <cmath>
#include <thread>
#include <deque>
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "rclcpp/rclcpp.hpp"

#include "rvc_messages/msg/pose_stamped_list.hpp"
#include "rvc_vision_messages/msg/rotated_bb.hpp"
#include "rvc_vision_messages/msg/rotated_bb_list.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "rvc_messages/msg/pose_stamped.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"

#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include <image_transport/image_transport.hpp>
#include <std_msgs/msg/u_int64_multi_array.hpp>
#include <std_msgs/msg/u_int64.hpp>

using std::placeholders::_1;
using json = nlohmann::json;


namespace RVC
{
class Profiler : public rclcpp::Node
{
private: // member data


    rclcpp::Subscription<rvc_vision_messages::msg::RotatedBBList>::SharedPtr m_rotated_bb_list_sub;
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr m_rs_pcl_sub;
    rclcpp::Subscription<rvc_messages::msg::PoseStampedList>::SharedPtr m_object_pose_stamped_list_msg;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr m_image_raw_sub;

    rvc_vision_messages::msg::RotatedBBList::SharedPtr m_rotated_bb_list_msg;

    sensor_msgs::msg::PointCloud2::UniquePtr m_last_cloud;
    rclcpp::TimerBase::SharedPtr profile_timer;
    image_transport::Subscriber m_image_sub;
    rclcpp::Subscription<std_msgs::msg::UInt64MultiArray>::SharedPtr m_sub_rtloop;

    struct ProfileDataStruct
    {
        unsigned long m_roi_count, rs_pcl_count, object_poses_count, inference_count, second_count, rs_rgb;
        unsigned long m_roi_count_total, rs_pcl_count_total, object_poses_count_total, inference_count_total, second_count_total, rs_rgb_total;
        unsigned long successful_object_detection_count, successful_object_detection_count_total;
        unsigned long long inversekinematics_failed, inversekinematics_total;
        unsigned long long deadline_failed, deadline_total;
    };

    struct ProfileDataStruct profileData;

    int pipe_fd[2];

private: // methods

    void handle_roi(const rvc_vision_messages::msg::RotatedBBList::SharedPtr msg)
    {
        profileData.m_roi_count ++;
        profileData.m_roi_count_total ++;
    }

    void handle_rs_pointcloud(sensor_msgs::msg::PointCloud2::UniquePtr msg)
    {
        profileData.rs_pcl_count ++;
        profileData.rs_pcl_count_total++;
    }

    void handle_object_poses(rvc_messages::msg::PoseStampedList::UniquePtr msg)
    {
        if (msg->poses.size() < 1)
            return;
        profileData.object_poses_count ++;
        profileData.object_poses_count_total++;
        if (msg->poses.front().obj_type !="none")
        {
            profileData.successful_object_detection_count++;
            profileData.successful_object_detection_count_total++;
        }
    }
    void handle_image_raw( sensor_msgs::msg::Image::UniquePtr msg)
    {
        profileData.rs_rgb++;
        profileData.rs_rgb_total++;
    }

    void handle_inference(const sensor_msgs::msg::Image::ConstSharedPtr msg)
    {
        profileData.inference_count ++;
        profileData.inference_count_total ++;
    }

    void handle_rtloop(const std_msgs::msg::UInt64MultiArray::UniquePtr msg)
    {
        profileData.inversekinematics_failed = msg->data[0];
        profileData.inversekinematics_total = msg->data[1];
        profileData.deadline_failed = msg->data[2];
        profileData.deadline_total = msg->data[3];
    }

    void handleTimer ( void )
    {
        if (profileData.second_count != 0)
            RCLCPP_INFO(rclcpp::get_logger("p"), "roi %ld rsrgb %ld rspcl %ld objPoses %ld inference %ld succlRecgn %ld [invKinFailed %lld total %lld deadlineFailed %lld total %lld] alltimeavrg: %ld %ld %ld %ld %ld)",
                        profileData.m_roi_count, profileData.rs_rgb, profileData.rs_pcl_count, profileData.object_poses_count, profileData.inference_count, profileData.successful_object_detection_count,
                        profileData.inversekinematics_failed, profileData.inversekinematics_total, profileData.deadline_failed, profileData.deadline_total,
                        profileData.m_roi_count_total/profileData.second_count, profileData.rs_pcl_count_total/profileData.second_count, profileData.object_poses_count_total/profileData.second_count,
                        profileData.inference_count_total/profileData.second_count, profileData.successful_object_detection_count_total/profileData.second_count);

        profileData.m_roi_count = profileData.rs_pcl_count = profileData.inference_count = profileData.object_poses_count = profileData.successful_object_detection_count = profileData.rs_rgb = 0;
        profileData.second_count++;
    }


public:
    explicit Profiler( const rclcpp::NodeOptions & options)
        : Node("rvc_profiler", options)
    {
        memset(&profileData,0,sizeof(profileData));

#ifndef BUILD_SENSOR_DATA
        auto rmw_qos_profile = rmw_qos_profile_default;
#else
        auto rmw_qos_profile = rmw_qos_profile_sensor_data;
#endif
        auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(rmw_qos_profile ), rmw_qos_profile);

        // TODO: factor out topic names
        m_rotated_bb_list_sub = this->create_subscription<rvc_vision_messages::msg::RotatedBBList>(
                         "detections",
                         qos,
                         std::bind(&Profiler::handle_roi, this, _1)
                     );

	std::string ns = this->get_namespace();
        std::string topic_prefix = std::string ("camera/camera") + ns.substr(1, ns.size() - 1) + std::string("/");
        m_rs_pcl_sub = this->create_subscription<sensor_msgs::msg::PointCloud2>(
                           topic_prefix + std::string("depth/color/points"),
                           qos,
                           std::bind(&Profiler::handle_rs_pointcloud, this, _1)
                       );

        m_object_pose_stamped_list_msg = this->create_subscription<rvc_messages::msg::PoseStampedList>(
                                 "object_poses",
                                 qos,
                                 std::bind(&Profiler::handle_object_poses, this, _1)
                             );

        const std::string transport = "compressed";

        m_image_sub = image_transport::create_subscription ( this,
                      "annotated_image",
                      std::bind(&Profiler::handle_inference, this, _1),
                      transport,
                      rmw_qos_profile);

        m_image_raw_sub = this->create_subscription<sensor_msgs::msg::Image> (
                              topic_prefix + std::string("color/image_raw"),
			      qos, std::bind(&Profiler::handle_image_raw, this, _1)
                          );

        m_sub_rtloop = this->create_subscription<std_msgs::msg::UInt64MultiArray>(
                           "rvc/rtloopprofiling",
                           qos,
                           std::bind(&Profiler::handle_rtloop, this, _1)
                       );

        RCLCPP_INFO(this->get_logger(), "==============> creating timer ...");
        profile_timer= create_wall_timer (
                           std::chrono::milliseconds ( 1000 ),
                           std::bind ( &Profiler::handleTimer, this ) );
        RCLCPP_INFO_STREAM(get_logger(), "Intra-Process is " << ( this->get_node_options().use_intra_process_comms() ? "ON" : "OFF" ) );

    }

};
}

#include "rclcpp_components/register_node_macro.hpp"

// Register the component with class_loader.
// This acts as a sort of entry point, allowing the component to be discoverable when its library
// is being loaded into a running process.
RCLCPP_COMPONENTS_REGISTER_NODE(RVC::Profiler)

