// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <rclcpp/rclcpp.hpp>

#include "data/bow_database.h"
#include "data/bow_vocabulary.h"
#include "data/imu.h"
#include "data/odom.h"
#include "data/map_database.h"
#include "QueueTypes.h"
#include "tracker/Client.h"
#include "fast_mapping_module.h"
#include "feature_extraction_module.h"
#include "univloc_tracking_module.h"
#include "univloc_mapping_module.h"
#include "univloc_msgs.h"
#include "UserConfig.h"
#include "util/stereo_rectifier.h"

#include <opencv2/core/core.hpp>

#include <atomic>
#include <memory>
#include <optional>
#include <thread>

using namespace openvslam;
using namespace fast_mapping;

namespace univloc_tracker {

class TrackerImpl {
public:
    TrackerImpl(std::shared_ptr<Config> cfg, std::shared_ptr<rclcpp::Node> node_ptr);

    ~TrackerImpl();

    TrackerImpl(const TrackerImpl &) = delete;
    TrackerImpl &operator=(const TrackerImpl &) = delete;

    void start(const bool need_initialize = true);

    void shutdown();

    ClientID get_client_id() const;

    bool connected_to_server() const;

    void request_reset();

    void feed_odom_data(double t, const Eigen::Matrix4d& odom_to_cam_pose);

    void feed_imu_data(double t, const Eigen::Vector3d& accel, const Eigen::Vector3d& angular_velocity);

    void feed_image(std::shared_ptr<ImageFrame> frame);

    void feed_lidar(std::shared_ptr<LidarFrame> scan);

    std::shared_ptr<ImageFrame> get_result();

    size_t how_many_frames_left() const;

    void get_keyframes(std::vector<Eigen::Matrix4d>& poses) const;

    void get_keyframes(std::vector<Eigen::Matrix4d>& covisibility_poses,
                       std::vector<Eigen::Matrix4d>& non_covisibility_poses) const;

    void get_landmarks(std::vector<Eigen::Vector3d>& positions) const;

    void get_tracked_server_landmarks(std::vector<Eigen::Vector3d>& positions) const;

    data::map_database* get_map_database();

    void get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const;

    void get_imu_status(univloc_msgs::ImuStatus& msg) const;

    bool tracking_module_is_lost() const;

    std::vector<Eigen::Vector3d> get_local_landmark_positions() const;

    se::Octree<SE_FIELD_TYPE>& get_octree();

    void get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active);

    void get_lidar_success_count(univloc_msgs::LidarStatus& msg);

    unsigned int get_tracker_octree_merged_times();

    bool is_coordinate_aligned() const;

private:

    void setup_camera();

    void setup_rectifier();

    void check_reset_request();

    void loaded_octree_map_to_msg(struct fast_mapping::se_cfg& octree_cfg,
                                  struct fast_mapping::camera_intrinsics& intrinsics,
                                  std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree);

    std::shared_ptr<Config> cfg_;

    //! camera model
    camera::base* camera_ = nullptr;

    //! rectifier
    std::shared_ptr<openvslam::util::stereo_rectifier> rectifier_;

    //! odom data
    std::shared_ptr<data::odom> odom_data_;

    //! IMU data
    std::shared_ptr<data::IMU_data> imu_data_;

    //! camera database
    data::camera_database* cam_db_ = nullptr;

    //! map database
    data::map_database* map_db_ = nullptr;

    //! BoW vocabulary
    data::bow_vocabulary* bow_vocab_ = nullptr;

    //! BoW database
    data::bow_database* bow_db_ = nullptr;

    //! queues for communication between modules
    RequestQueue request_queue_;  // images from user to feature_extraction_module
    RequestLidarQueue request_lidar_queue_;  // lidar scans from user to feature_extraction_module
    FeatureQueue feature_queue_;  // images and features from feature_extraction_module to tracking_module
    RequestQueue result_queue_;   // images and poses from tracking_module to user
    RequestQueue reconstruction_queue_; // images and poses from tracking module to fast_mapping module

    //! feature extraction module
    feature_extraction_module* feature_extraction_module_ = nullptr;
    std::unique_ptr<std::thread> feature_extraction_thread_;

    //! tracking module
    univloc_tracking_module* tracker_ = nullptr;
    std::unique_ptr<std::thread> tracking_thread_;

    //! mapping module
    univloc_mapping_module* mapper_ = nullptr;
    std::unique_ptr<std::thread> mapping_thread_;

    //! fast mapping module
    fast_mapping_module* fast_mapping_module_ = nullptr;
    std::unique_ptr<std::thread> reconstruction_thread_;

    //! client module
    std::unique_ptr<std::thread> client_thread_;

    //! gui thread (if gui is set to true)
    std::unique_ptr<std::thread> gui_thread_;

    //! system running status flag
    std::atomic<bool> system_is_running_{false};

    //! mutex for terminate flag
    mutable std::mutex mtx_terminate_;
    //! terminate flag
    bool terminate_is_requested_ = false;

    //! mutex for flags of enable/disable mapping module
    mutable std::mutex mtx_mapping_;

    std::shared_ptr<data::IMU_data> imu_data_buf_;

    std::string traj_store_path_ = "";
};

}  // namespace univloc_tracker
