// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <rclcpp/rclcpp.hpp>

#include "UserConfig.h"
#include "ImageFrame.h"
#include "LidarFrame.h"

#include <univloc_msgs/msg/imu_status.hpp>
#include <univloc_msgs/msg/lidar_status.hpp>

namespace univloc_msgs{
                        typedef msg::ImuStatus ImuStatus;
                        typedef msg::ImuStatus::ConstSharedPtr ImuStatusConstPtr;
                        typedef msg::LidarStatus LidarStatus;
}

#include <Eigen/Core>
#include <opencv2/core/core.hpp>
#include <map>
#include <memory>
#include <optional>
#include <vector>

#include <se/volume_traits.hpp>
#include <se/octree.hpp>

namespace univloc_tracker {

class TrackerImpl;

class Tracker {
public:
    Tracker(std::shared_ptr<Config> cfg, std::shared_ptr<rclcpp::Node> node_ptr);

    ~Tracker();

    void start(const bool need_initialize = true);

    void shutdown();

    ClientID get_client_id() const;

    bool connected_to_server() const;

    void request_reset();

    //-----------------------------------------
    // data feeding methods

    void feed_image(std::shared_ptr<ImageFrame> frame);

    void feed_odom_data(double t, const Eigen::Matrix4d& odom_to_cam_pose);

    void feed_imu_data(double t, const Eigen::Vector3d& accel, const Eigen::Vector3d& angular_velocity);

    void feed_lidar(std::shared_ptr<LidarFrame> scan);

    //-----------------------------------------
    // query methods

    //! A blocking call to wait and get the estimated pose for a feeded image frame
    std::shared_ptr<ImageFrame> get_result();

    //! How many frames are waiting for processing; the currently processing frames (can be 0-2) are not counted
    size_t how_many_frames_left() const;

    void get_keyframes(std::vector<Eigen::Matrix4d>& poses) const;

    void get_keyframes(std::vector<Eigen::Matrix4d>& covisibility_poses,
                       std::vector<Eigen::Matrix4d>& non_covisibility_poses) const;

    void get_landmarks(std::vector<Eigen::Vector3d>& positions) const;

    void get_tracked_server_landmarks(std::vector<Eigen::Vector3d>& positions) const;

    std::vector<std::pair<unsigned int, Eigen::Vector3d>> get_server_landmarks_clientID_position() const;

    void get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const;

    void get_imu_status(univloc_msgs::ImuStatus& msg) const;

    bool tracking_module_is_lost() const;

    std::vector<Eigen::Vector3d> get_local_landmark_positions() const;

    se::Octree<SE_FIELD_TYPE>& get_octree();

    void get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active);

    void get_lidar_success_count(univloc_msgs::LidarStatus& msg) const;

    unsigned int get_tracker_octree_merged_times();

    bool is_coordinate_aligned() const;

private:
    std::unique_ptr<TrackerImpl> impl_;
};
}  // namespace univloc_tracker
