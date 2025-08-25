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

#include <condition_variable>
#include <mutex>
#include <queue>
#include <thread>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp/time.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <std_srvs/srv/empty.hpp>
#include <tf2/convert.h>
#ifdef PRE_ROS_HUMBLE
#include <tf2_eigen/tf2_eigen.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#else
#include <tf2_eigen/tf2_eigen.hpp>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#endif
#include <tf2_ros/transform_listener.h>

#include "DataQueue.h"
#include "ImageFrame.h"
#include "LoopTimer.h"
#include "MapManager.h"
#include "OctoMap.h"
#include "Subscribers.h"

class FastMappingNode : public rclcpp::Node
{
    using FrameQueue = DataQueue<std::shared_ptr<ImageFrame>>;

public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    /*
     * Constructor
     */
    FastMappingNode();
    ~FastMappingNode();

    void start();
    void stop();
    void init();

private:

    // Main worker thread
    void worker();

    // Callback function for setting the intrinsics
    void setIntrinsics(const sensor_msgs::msg::CameraInfo::ConstSharedPtr msg);

    // Function for finding a pose for a given frame at a specific timestamp
    void getPoseFromTf(std::shared_ptr<ImageFrame> currFrame);

    // prints stats
    void printStats();

    // Main worker thread and mutexes
    std::unique_ptr<std::thread> worker_thread_;

    // Mutex for integrating into the Octree
    std::mutex mapping_mutex_;

    rclcpp::Time last_stat_time_;
    LoopTimer timer_;

    // OctoMap class
    std::shared_ptr<OctoMap> octomap_;

    // MapManager
    std::unique_ptr<MapManager> map_manager_;

    // Subscribers
    std::unique_ptr<CameraSubscribers> subscribers_;

    // Queue holding the graphs of poses
    FrameQueue frame_queue_;

    // Configuration of the node
    struct NodeConfig config_;

    // Stats variables
    std::atomic_uint stat_image_, stat_pose_;
    std::atomic_uint stat_aligned_pf_, stat_processed_;

    // Mutex for publishing the stats
    std::mutex stat_mutex_;

    std::shared_ptr<tf2_ros::Buffer> tf_buffer_;
    std::shared_ptr<tf2_ros::TransformListener> tf_listener_;
};
