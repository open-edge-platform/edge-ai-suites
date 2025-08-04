// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <univloc_tracker/Tracker.h>
#include "TrackerImpl.h"

namespace univloc_tracker {
Tracker::Tracker(std::shared_ptr<Config> cfg, std::shared_ptr<rclcpp::Node> node_ptr) {
    impl_ = std::make_unique<TrackerImpl>(cfg, node_ptr);
}

Tracker::~Tracker() { impl_.reset(); }

void Tracker::start(const bool need_initialize) { impl_->start(need_initialize); }

void Tracker::shutdown() { impl_->shutdown(); }

ClientID Tracker::get_client_id() const { return impl_->get_client_id(); }

bool Tracker::connected_to_server() const { return impl_->connected_to_server(); }

void Tracker::request_reset() { impl_->request_reset(); }

void Tracker::feed_image(std::shared_ptr<ImageFrame> frame)
{
    impl_->feed_image(frame);
}

void Tracker::feed_lidar(std::shared_ptr<LidarFrame> scan)
{
    impl_->feed_lidar(scan);
}

std::shared_ptr<ImageFrame> Tracker::get_result()
{
    return impl_->get_result();
}

size_t Tracker::how_many_frames_left() const
{
    return impl_->how_many_frames_left();
}

void Tracker::feed_odom_data(double t, const Eigen::Matrix4d& odom_to_cam_pose)
{
    impl_->feed_odom_data(t, odom_to_cam_pose);
}

void Tracker::feed_imu_data(double t, const Eigen::Vector3d& accel, const Eigen::Vector3d& angular_velocity)
{
    impl_->feed_imu_data(t, accel, angular_velocity);
}

void Tracker::get_keyframes(std::vector<Eigen::Matrix4d>& poses) const { impl_->get_keyframes(poses); }

void Tracker::get_keyframes(std::vector<Eigen::Matrix4d>& covisibility_poses,
                            std::vector<Eigen::Matrix4d>& non_covisibility_poses) const
{
    impl_->get_keyframes(covisibility_poses, non_covisibility_poses);
}

void Tracker::get_landmarks(std::vector<Eigen::Vector3d>& positions) const { impl_->get_landmarks(positions); }

void Tracker::get_tracked_server_landmarks(std::vector<Eigen::Vector3d>& positions) const
{
    impl_->get_tracked_server_landmarks(positions);
}

void Tracker::get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const
{
    impl_->get_imu_estimated_poses(poses);
}

std::vector<std::pair<unsigned int, Eigen::Vector3d>> Tracker::get_server_landmarks_clientID_position() const
{
    std::vector<std::pair<unsigned int, Eigen::Vector3d>> clientID_positions;
    auto server_landmarks = impl_->get_map_database()->get_server_landmarks();

    size_t n = server_landmarks.size();
    clientID_positions.resize(n);

    for (size_t i = 0; i < n; i++) {
        clientID_positions[i] =
            std::make_pair(server_landmarks[i]->client_id_, server_landmarks[i]->get_pos_in_world());
    }

    return clientID_positions;
}

void Tracker::get_imu_status(univloc_msgs::ImuStatus& msg) const { return impl_->get_imu_status(msg); }

void Tracker::get_lidar_success_count(univloc_msgs::LidarStatus& msg) const
{
    impl_->get_lidar_success_count(msg);
}

std::vector<Eigen::Vector3d> Tracker::get_local_landmark_positions() const
{
    return impl_->get_local_landmark_positions();
}

bool Tracker::tracking_module_is_lost() const {
    return impl_->tracking_module_is_lost();
}

se::Octree<SE_FIELD_TYPE>& Tracker::get_octree() {
    return impl_->get_octree();
}

void Tracker::get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active)
{
    return impl_->get_octree_block_list(blocklist, active);
}

unsigned int Tracker::get_tracker_octree_merged_times() { return impl_->get_tracker_octree_merged_times(); }

bool Tracker::is_coordinate_aligned() const { return impl_->is_coordinate_aligned(); }

}  // namespace univloc_tracker
