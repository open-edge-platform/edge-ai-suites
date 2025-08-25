// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <Eigen/Core>
#include <opencv2/core/core.hpp>  // TODO remove cv and use Eigen instead

#include <iterator>  // needed for std::ostram_iterator
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include "type.h"

namespace univloc_tracker {

template <typename T>
std::ostream& operator<<(std::ostream& out, const std::vector<T>& v)
{
    if (!v.empty()) {
        out << '[';
        std::copy(v.begin(), v.end(), std::ostream_iterator<T>(out, ", "));
        out << "\b\b]";
    }
    return out;
}

class Config {
public:
    Config() {}

    friend std::ostream& operator<<(std::ostream& os, const Config& cfg)
    {
        return os << "Camera: " << cfg.camera_name_ << "\n"
                  << "  (" << cfg.setup_type_str_ << "; " << cfg.color_order_str_ << "; " << cfg.model_type_str_
                  << ")\n"
                  << "  baseline: " << cfg.camera_baseline_ << "\n"
                  << "  Camera FPS: " << cfg.camera_fps_ << "\n"
                  << "  depth scale: " << cfg.depthmap_factor_ << "\n"
                  << "  image size: " << cfg.width_ << "x" << cfg.height_ << "\n"
                  << "  intrinsics: " << cfg.fx_ << ", " << cfg.fy_ << ", " << cfg.cx_ << ", " << cfg.cy_ << "\n"
                  << "  distortion: " << cfg.dist_params_ << "\n"
                  << "Feature: ORB\n"
                  << "  #keypoints: " << cfg.max_num_keypoints_ << "\n"
                  << "  scale factor: " << cfg.orb_scale_factor_ << "\n"
                  << "  #levels: " << cfg.orb_num_levels_ << "\n"
                  << "  ini FAST threshold: " << cfg.orb_ini_fast_threshold_ << "\n"
                  << "  min FAST threshold: " << cfg.orb_min_fast_threshold_ << "\n"
                  << "  mask image: " << cfg.mask_image_path_ << "\n"
                  << "  vocabulary: " << cfg.vocabulary_path_ << "\n"
                  << "Tracking parameters\n"
                  << "  depth threshold: " << cfg.depth_threshold_ << "\n"
                  << "  initialize using server: " << (cfg.initialize_by_server_ ? "True" : "False") << "\n"
                  << "  request frame queue capacity: " << cfg.queue_capacity_ << "\n"
                  << "  lidar request frame queue capacity: " << cfg.queue_lidar_capacity_ << "\n"
                  << "  slam_mode: " << (cfg.mode_) << "\n"
                  << "  trajectory store path: " << (cfg.traj_store_path_) << "\n"
                  << "Extrinsics"
                  << "\n"
                  << "  T(base,camera): " << cfg.tf_base_camera_ << "\n"
                  << "  T(camera,imu): " << cfg.tf_camera_imu_ << "\n"
                  << "  T(base,lidar): " << cfg.tf_base_lidar_ << "\n"
                  << "IMU parameters"
                  << "\n"
                  << "  bias: " << cfg.imu_bias_ << "\n"
                  << "  noise: " << cfg.imu_noise_ << "\n" // ngx, ngy, ngz, nax, nay, naz
                  << "  random walk: " << cfg.imu_bias_walk_ << "\n" // wgx, wgy, wgz, wax, way, waz
                  << "Visualization parameter" << "\n"
                  << "  gui: " << cfg.gui_ << "\n";
    }

    //-----------------------------------------
    // camera parameters
    std::string camera_name_;
    std::string setup_type_str_;   // options: "RGBD", "RGBD_Inertial", "Monocular", "Monocular_Inertial"
    std::string color_order_str_;  // options: "Gray", "RGB", "RGBA", "BGR", "BGRA"
    std::string model_type_str_;   // options: "Perspective", "Fisheye", "Equirectangular"
    float camera_baseline_ = 0.0;        // in meters
    float camera_fps_ = 0.0;
    float depthmap_factor_ = 0.0;
    std::string base_link_frame_ = "";

    inline bool is_monocular() const { return setup_type_str_.rfind("Monocular", 0) != std::string::npos; };
    inline bool is_stereo() const { return setup_type_str_.rfind("Stereo", 0) != std::string::npos; };
    inline bool is_rgbd() const { return setup_type_str_.rfind("RGBD", 0) != std::string::npos; };
    inline bool enable_imu() const
    {
        return setup_type_str_.find("Inertial", setup_type_str_.length() - std::string("Inertial").length()) !=
               std::string::npos;
    };

    bool lidar_enable_ = false;

    int width_ = 0, height_ = 0;
    double fx_ = 0.0, fy_ = 0.0, cx_ = 0.0, cy_ = 0.0;
    std::vector<double> dist_params_;  // distortion parameters are model-specific
    template <typename T>
    void set_distortion_params(const T& params)
    {
        size_t expected_distortion_size;
        if (model_type_str_ == "Perspective")
            expected_distortion_size = 5;
        else if (model_type_str_ == "Fisheye")
            expected_distortion_size = 4;
        else if (model_type_str_ == "Equirectangular")
            expected_distortion_size = 0;
        else
            throw std::invalid_argument("Invalid camera model type: " + model_type_str_);

        if (params.size() == expected_distortion_size) {
            for (auto d : params) dist_params_.push_back(d);
        } else if (params.size() == 0) {
            std::cout << "Warning: Got no distortion params. Will assume all zero.\n";
            dist_params_.resize(expected_distortion_size, 0);
        } else {
            throw std::invalid_argument("Expecting " + std::to_string(expected_distortion_size) +
                                        " distortion params for " + model_type_str_ + " camera but got " +
                                        std::to_string(params.size()));
        }
    }

    //-----------------------------------------
    // rectifier parameters
    bool enable_rectifier_ = false;
    bool rectifier_params_given_ = true;
    std::string tf_right_camera_frame_ = "";
    cv::Mat K1, D1, K2, D2;
    cv::Mat K_left_, D_left_, R_left_, K_right_, D_right_, R_right_;
    double focal_x_baseline_ = 0.0;

    //-----------------------------------------
    // feature extraction parameters
    int max_num_keypoints_ = 1000;
    float orb_scale_factor_ = 1.2;
    int orb_num_levels_ = 8;
    int orb_ini_fast_threshold_ = 20;
    int orb_min_fast_threshold_ = 7;
    std::vector<std::vector<float>> mask_rects_;
    std::string mask_image_path_;
    std::string vocabulary_path_;

    //-----------------------------------------
    // initializer parameters
    int init_num_ransac_iterations_ = 100;
    int init_num_min_triangulated_pts_ = 50;
    float init_parallax_deg_threshold_ = 1.0;
    float init_reprojection_error_threshold_ = 4.0;
    int init_num_ba_iterations_ = 20;
    float init_scaling_factor_ = 1.0;

    //-----------------------------------------
    // tracking parameters
    float depth_threshold_ = 6.;  // in meters
    bool initialize_by_server_ = false;
    int queue_capacity_ = 1;  // capacity of the request frame queue
                              // 0 means unlimited, to process every frame one by one (for benchmarking usage)
                              // 1 is default, to process only latest frame and drop outdated (for real-time usage)
    int queue_lidar_capacity_ = 1;  // capacity of the lidar request frame queue
                              // 0 means unlimited, to process every frame one by one (for benchmarking usage)
                              // 1 is default, to process only latest frame and drop outdated (for real-time usage)
    std::string mode_ = "";
    std::string traj_store_path_ = "";
    std::string octree_store_path_ = "";
    std::string octree_load_path_ = "";
    bool enable_remapping_region_ = false;            // Only for internal usage, not expose to the user!
    std::vector<double> remapping_region_vertexes_;   // In the two-sessions remapping solution, the tracker
                                                      // coordinate only aligns with server coordinate after merging
                                                      // happens; but to support one-session remapping solution, the
                                                      // tracker doesn't have the coordinates alignment issue any
                                                      // more, so this option can highly increase the performance of
                                                      // creating Octree map since the tracker doesn't need to build
                                                      // Octree map outside the remapping region
    int trigger_relocalization_request_divisor_ = 1;  // The threshold of frames to trigger relocalization request
                                                      // default to trigger relocalization per each frame needed
    bool need_covariance_ = false;                    // Calculate covariance matrix of estimated pose and
                                                      // publish new topic of pose with covariance

    //-----------------------------------------
    // extrinsics
    Eigen::Matrix4d tf_base_camera_;  // base-camera transformation; for deciding world frame
    Eigen::Matrix4d tf_camera_imu_;   // camera-imu transformation
    Eigen::Matrix4d tf_left_right_;   // left camera to right camera for stereo setup
    std::string tf_fix_frame_ = "";   // the frame ID in TF tree that does not change over time
    Eigen::Matrix4d tf_base_lidar_;   // base to lidar transformation
    Eigen::Matrix4d tf_lidar_camera_ = Eigen::Matrix4d::Identity();   // lidar to camera transformation

    //-----------------------------------------
    // Image frame parameters
    std::string image_frame_;
    bool image_frame_set_in_launch_file_ = false;

    //-----------------------------------------
    // whether clean redundant keyframe, default is true
    bool clean_keyframe_ = true;

    //-----------------------------------------
    // Odom parameters
    bool use_odom_ = false;
    std::string odom_frame_;
    Eigen::Matrix4d T_image_to_camera_ = Eigen::Matrix4d::Identity();
    float odom_tf_query_timeout_ = 0.0; //odometry querying timeout in image callback function
    float odom_buffer_query_timeout_ = 0.0; // odometry querying timeout in tracking module

    //-----------------------------------------
    // IMU parameters
    Eigen::Matrix<double, 6, 1> imu_bias_, imu_noise_, imu_bias_walk_;
    float imu_frequency_ = 0.0;

    // ------------------------------------------
    // Fast Mapping Octree parameters
    bool enable_fast_mapping_ = false;
    float depth_max_range_ = 3.0; // range of the ray
    float voxel_size_ = 0.04;  // Size of the voxel
    float zmin_ = -std::numeric_limits<float>::infinity();  // Z Min and Max for the 3D map
    float zmax_ = std::numeric_limits<float>::infinity();
    int map_size_ = 256; // Size of the volumetric map
    int depth_scaling_factor_ = 1; // Scaling factor of the depth image
    int correction_threshold_ = 1; // Correction threshold in voxels for triggering a map reconstruction

    //-----------------------------------------
    // communication parameters
    ClientID client_id_ = 0;
    int min_keyframes_before_informing_server_ = 5;

    bool gui_ = false;

    bool force_best_effort_qos_ = false;

    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
};

typedef std::shared_ptr<Config> ConfigPtr;
typedef std::shared_ptr<const Config> ConfigConstPtr;

}  // namespace univloc_tracker
