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

#include "FastMappingNode.h"

FastMappingNode::FastMappingNode() : Node("fast_mapping_node")
{
}

void FastMappingNode::init()
{
    config_.p_map_frame_ = declare_parameter<std::string>("map_frame", "map");

    config_.p_projection_min_z_ = declare_parameter<float>("projection_min_z", float(0.1));
    config_.p_projection_max_z_ = declare_parameter<float>("projection_max_z", float(1));
    config_.p_depth_max_range_ = declare_parameter<float>("max_depth_range", float(3.0));
    config_.p_map_resolution_  = declare_parameter<float>("voxel_size", float(0.04));
    config_.p_robot_radius_ = declare_parameter<float>("robot_radius", float(0.2));
    config_.p_noise_factor_ = declare_parameter<float>("noise_factor", float(0.02));
    config_.p_zmin_ = declare_parameter<float>("zmin", -std::numeric_limits<float>::infinity());
    config_.p_zmax_ = declare_parameter<float>("zmax", std::numeric_limits<float>::infinity());
    config_.p_tf_delay_ = declare_parameter<float>("tf_delay", float(.7));

    tf_buffer_ = std::make_shared<tf2_ros::Buffer>(get_clock());
    tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);

    OctoMap::OctreeConfiguration se_config;
    se_config.compute_size_ratio = config_.p_depth_scale_ratio_;
    se_config.depth_max_range = config_.p_depth_max_range_;
    se_config.voxel_per_side = config_.p_map_size_;
    se_config.volume_size_meter = config_.p_map_resolution_ * config_.p_map_size_;
    se_config.noise_factor = config_.p_noise_factor_;
    se_config.logodds_lower = -5.;
    se_config.logodds_upper = 10.;
    se_config.zmin = config_.p_zmin_;
    se_config.zmax = config_.p_zmax_;

    octomap_.reset(new OctoMap(se_config));

    map_manager_.reset(new MapManager(octomap_, config_));

    subscribers_.reset(new CameraSubscribers(
        this->shared_from_this(),
        frame_queue_,
        std::bind(&FastMappingNode::setIntrinsics,
            this,
            std::placeholders::_1)));

    stat_image_ = 0;
    stat_aligned_pf_ = stat_processed_ = 0;
}

FastMappingNode::~FastMappingNode()
{
}

void FastMappingNode::start()
{
    map_manager_->clearMarkers();
    this->worker_thread_.reset(new std::thread(&FastMappingNode::worker, this));
    last_stat_time_ = this->now();
}

void FastMappingNode::stop()
{
    RCLCPP_INFO(get_logger(), "Stopping FastMapping");
    frame_queue_.close();
    this->worker_thread_->join();
}

void FastMappingNode::setIntrinsics(const sensor_msgs::msg::CameraInfo::ConstSharedPtr msg)
{
    octomap_->setIntrinsics(
        msg->height,
        msg->width,
        msg->k[2],
        msg->k[5],
        msg->k[0],
        msg->k[4]);
}

void FastMappingNode::getPoseFromTf(std::shared_ptr<ImageFrame> currFrame)
{
    stat_image_++;
    const auto header = std::any_cast<std_msgs::msg::Header>(currFrame->cdata);
    geometry_msgs::msg::TransformStamped transform;
    try
    {
        transform = tf_buffer_->lookupTransform(config_.p_map_frame_, header.frame_id,
                                                tf2::TimePointZero, tf2::durationFromSec(config_.p_tf_delay_));
    }
    catch (tf2::TransformException &e)
    {
        std::string errstr(e.what());
        RCLCPP_ERROR(get_logger(), "Failed to get transform from %s to %s: %s",
            header.frame_id.c_str(), config_.p_map_frame_.c_str(), errstr.c_str());
        return;
    }

    stat_aligned_pf_++;
    currFrame->maybe_pose = tf2::transformToEigen(transform).matrix();
}

void FastMappingNode::worker()
{
    timer_.start();
    RCLCPP_INFO(get_logger(), "fast_mapping is waiting for new frames...");

    std::shared_ptr<ImageFrame> currFrame;

    while(rclcpp::ok())
    {
        timer_.startFirstProc("wait for a new frame");

        if(!frame_queue_.wait_pop(currFrame)) break;

        getPoseFromTf(currFrame);

        timer_.startNextProc("Preprocess frame");

        octomap_->integrate(currFrame);

        timer_.startNextProc("Octree integrate");

        map_manager_->publish_maps(currFrame);

        timer_.startNextProc("Publish voxels");

        stat_processed_++;
        printStats();

        timer_.endCycle();
    }
    timer_.finish();
    std::cout << timer_.result();
}

void FastMappingNode::printStats()
{
    if (config_.p_stat_log_interval_ <= 0) {
        return;
    }

    rclcpp::Duration interval(config_.p_stat_log_interval_, 0);
    stat_mutex_.lock();
    rclcpp::Time tnow = this->now();
    rclcpp::Duration dur = tnow - last_stat_time_;
    if (dur > interval) {
        last_stat_time_ = tnow;
        stat_mutex_.unlock();
        unsigned int nimage = stat_image_.exchange(0);
        unsigned int aligned_pf = stat_aligned_pf_.exchange(0);
        unsigned int processed = stat_processed_.exchange(0);
        std::unique_lock<std::mutex> lk(mapping_mutex_);
        size_t queue_length = frame_queue_.size();
        
        RCLCPP_INFO(get_logger(), "fast_mapping got %d images in %.1fs. Aligned %d. Processed %d (%.2lf Hz). %ld left in queue",
                  nimage,
                  dur.seconds(),
                  aligned_pf, processed, processed / dur.seconds(), queue_length);
    }
    else {
        stat_mutex_.unlock();
    }
}
