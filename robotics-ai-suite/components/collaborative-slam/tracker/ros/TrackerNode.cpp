// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "TrackerNode.h"
#include "file_io.h"
#include "fast_mapping_param.h"
#include "fast_mapping_helper.h"
#include "se/octree_defines.h"
#ifdef GPU_KERNEL_PATH
#include "orb_extractor.h"
#endif

#include <cv_bridge/cv_bridge.h>
#include <opencv2/core/core.hpp>

#include <algorithm>
#include <fstream>
#include <ament_index_cpp/get_package_share_directory.hpp>

#define MILLISEC_TO_SEC        1e-3
#define EPSILON                0.00001
#define MAX_NODE_SIZE          32
#define MIN_DISTANCE_TO_GROUND 0.1

const std::string TrackerNode::tracker_node_name("univloc_tracker");

TrackerNode::TrackerNode()
    : rosx::Node(TrackerNode::tracker_node_name),
          sync_policy_(10),
          image_sync_(sync_policy_),
          sync_imu_policy_(10),
          imu_sync_(sync_imu_policy_) {
    cfg_ = std::make_shared<univloc_tracker::Config>();
}

TrackerNode::~TrackerNode() {
    stop();
}

bool TrackerNode::init()
{

#ifdef USE_IMAGE_TRANSPORT
    auto subscribe_image_topic = [this](ImageSubscriberFilter &sub, std::string topic, const std::string hint = "raw") {
        rclcpp::QoS qos{rclcpp::KeepAll()};
        sub.subscribe(this, topic, hint, qos.get_rmw_qos_profile());
    };
#else
    auto subscribe_image_topic = [this](ImageSubscriberFilter &sub, std::string topic, const std::string = "raw") {
        rclcpp::QoS qos{rclcpp::KeepAll()};
        sub.subscribe(this, topic, qos.get_rmw_qos_profile());
    };
#endif

    std::string p_camera("camera");
    get_ros_param("camera", p_camera, p_camera);
    get_ros_param("image_topic", p_image_topic_, std::string(""));
    if (p_image_topic_ == "") p_image_topic_ = p_camera + "/color/image_raw";
    get_ros_param("depth_topic", p_depth_topic_, std::string(""));
    if (p_depth_topic_ == "") p_depth_topic_ = p_camera + "/aligned_depth_to_color/image_raw";
    get_ros_param("right_image_topic", p_right_image_topic_, std::string(""));
    get_ros_param("accel_measurement_scale", p_accel_measurement_scale_,
              double(1.0));  // In case of some incorrect imu in datasets

    pub_pc_ = create_publisher<sensor_msgs::msg::PointCloud>("~/pointcloud", 1);
    pub_local_map_ = create_publisher<visualization_msgs::msg::MarkerArray>("~/local_map", 10);
    pub_pose_ = create_publisher<geometry_msgs::msg::PoseStamped>("~/pose", 1);
    pub_kf_pose_ = create_publisher<geometry_msgs::msg::PoseWithCovarianceStamped>("~/kf_pose", 1);
    pub_optimized_path_ = create_publisher<nav_msgs::msg::Path>("~/optimized_path", 1);
    pub_server_landmarks_observation_ = create_publisher<visualization_msgs::msg::Marker>("~/server_landmarks_observation", 10);
    pub_imu_estimated_path_ = create_publisher<nav_msgs::msg::Path>("~/imu_estimated_path", 1);
    auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
    pub_fused_map_ = create_publisher<visualization_msgs::msg::MarkerArray>("~/fused_map", map_qos);
    pub_occupancy_map_ = create_publisher<nav_msgs::msg::OccupancyGrid>("~/map", map_qos);
    grid_template_ = std::make_shared<nav_msgs::msg::OccupancyGrid>();

    auto replace_last_subtopic = [](std::string topic, std::string replace) {
        return topic.substr(0, topic.find_last_of('/') + 1) + replace;
    };
    std::string p_camera_info_topic, p_right_camera_info_topic;
    get_ros_param("camera_info_topic", p_camera_info_topic, std::string(""));
    if (p_camera_info_topic == "") p_camera_info_topic = replace_last_subtopic(p_image_topic_, "camera_info");
    get_ros_param("right_camera_info_topic", p_right_camera_info_topic, std::string(""));
    if (p_right_camera_info_topic == "")
        p_right_camera_info_topic = replace_last_subtopic(p_right_image_topic_, "camera_info");

    get_ros_param("map_frame", p_map_frame_, std::string("map"));
    get_ros_param("publish_tf", publish_tf_, true);
    if (publish_tf_) {
        // Set ROS frames between which we should publish tf. Default: reference frame -> RGB image frame
        get_ros_param("pub_tf_parent_frame", p_parent_frame_, std::string(""));
        get_ros_param("pub_tf_child_frame", p_child_frame_, std::string(""));
    }
    get_ros_param("num_lost_frames_to_reset", num_lost_frames_to_reset_, 0);
    if (num_lost_frames_to_reset_ < 0)
        throw std::invalid_argument("num_lost_frames_to_reset should be a positive number!");
    get_ros_param("stat_log_interval", p_stat_log_interval_, float(3.0));

    get_ros_param("use_lidar", use_lidar_, false);

    std::string config_file_path;
    get_ros_param("config_file_path", config_file_path, std::string(""));

    if (config_file_path == "") {
        // Get config from ROS params
        if (!read_config_from_ros(p_camera_info_topic, p_right_camera_info_topic))
            return false;
    } else {
        ROS_ERROR("Cannot read config from yaml - not yet implemented");
        return false;
    }

    if (!rosx::ok()) {
        ROS_ERROR("ROS system not ready");
        return false;
    }

    traj_store_path_ = cfg_->traj_store_path_;

    if (traj_store_path_ != "") {
        if (check_folder_path(traj_store_path_)) {
            traj_store_path_ += "/" + std::to_string(int(rosx::now().toSec())) + ".txt";
        } else {
            ROS_ERROR("Failed to use or create %s as trajectory folder", traj_store_path_.c_str());
            return false;
        }
    }

    if (cfg_->enable_imu()) {
        get_ros_param("imu_topic", imu_topic_, std::string(""));
        auto qos = rclcpp::SensorDataQoS();
        if (imu_topic_ != "") {
            sub_imu_ = create_subscription<sensor_msgs::msg::Imu>(
                imu_topic_, qos, std::bind(&TrackerNode::imu_callback, this, std::placeholders::_1));
        } else {
            get_ros_param("accel_topic", acc_topic_, std::string(""));
            get_ros_param("gyro_topic", gyro_topic_, std::string(""));
            if (acc_topic_ == "" || gyro_topic_ == "") {
                ROS_ERROR("If IMU is enabled, provide either imu_topic, or as an alternative, \
                           accel_topic and gyro_topic");
                return false;
            }
            sub_acc_.subscribe(this, acc_topic_, qos.get_rmw_qos_profile());
            sub_gyro_.subscribe(this, gyro_topic_, qos.get_rmw_qos_profile());
            imu_sync_.connectInput(sub_acc_, sub_gyro_);
            imu_sync_.registerCallback(
                std::bind(&TrackerNode::accgyr_callback, this, std::placeholders::_1, std::placeholders::_2));
        }
        pub_imu_states_ = create_publisher<univloc_msgs::ImuStatus>("~/imu_states", 1);
    }

    if (use_lidar_) {
        cfg_->lidar_enable_ = true;
        auto default_qos = rclcpp::QoS(rclcpp::SystemDefaultsQoS());
        laser_scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
            "/scan", default_qos,
            std::bind(&TrackerNode::lidar_callback, this, std::placeholders::_1));
        pub_lidar_states_ = create_publisher<univloc_msgs::LidarStatus>("~/lidar_states", 1);
    }

    bool enable_raw_transport;
    std::string image_hint, depth_hint;
    get_ros_param("raw_transport", enable_raw_transport, bool(true));
    if (enable_raw_transport) {
        image_hint = "raw";
        depth_hint = "raw";
    } else {
        image_hint = "compressed";
        depth_hint = "compressedDepth";
    }
    if (cfg_->is_monocular()) {
        subscribe_image_topic(sub_mono_, p_image_topic_, image_hint);
        sub_mono_.registerCallback(
            std::bind(&TrackerNode::monocular_callback, this, std::placeholders::_1));
    } else if (cfg_->is_stereo()) {
        subscribe_image_topic(sub_image_, p_image_topic_, image_hint);
        subscribe_image_topic(sub_right_image_, p_right_image_topic_, image_hint);
        image_sync_.connectInput(sub_image_, sub_right_image_);
        image_sync_.registerCallback(
            std::bind(&TrackerNode::stereo_callback, this, std::placeholders::_1, std::placeholders::_2));
    } else if (cfg_->is_rgbd()) {
        subscribe_image_topic(sub_image_, p_image_topic_, image_hint);
        subscribe_image_topic(sub_depth_, p_depth_topic_, depth_hint);
        image_sync_.connectInput(sub_image_, sub_depth_);
        image_sync_.registerCallback(
            std::bind(&TrackerNode::rgbd_callback, this, std::placeholders::_1, std::placeholders::_2));
    } else {
        ROS_ERROR("Unknown camera type");
        return false;
    }

    get_ros_param("enable_fast_mapping", cfg_->enable_fast_mapping_, false);

    if (cfg_->enable_fast_mapping_ && !cfg_->is_rgbd()) {
        ROS_ERROR("Fast mapping usage is limited to RGBD cameras! Continuing without it");
        return false;
    }

    if (cfg_->enable_fast_mapping_)
    {
        // Octree parameters
        get_ros_param("depth_max_range", cfg_->depth_max_range_);
        get_ros_param("voxel_size", cfg_->voxel_size_, float(0.04));
        if (cfg_->voxel_size_ < 0) {
            ROS_ERROR("voxel_size (m) should be a positive number!");
            return false;
        }

        get_ros_param("zmin", cfg_->zmin_, -std::numeric_limits<float>::infinity());
        get_ros_param("zmax", cfg_->zmax_, std::numeric_limits<float>::infinity());
        if (cfg_->zmin_ < 0 || cfg_->zmax_ < 0 || cfg_->zmin_ > cfg_->zmax_) {
            ROS_ERROR("zmin and zmin should be a positive number and zmin cannot be set larger than zmax!");
            return false;
        }
        float voxelblock_side = BLOCK_SIDE * cfg_->voxel_size_;
        int voxelblock_num = int(cfg_->zmax_ / voxelblock_side);
        float min_acceptable_z = cfg_->zmax_ - voxelblock_side * float(voxelblock_num);
        if (min_acceptable_z < MIN_DISTANCE_TO_GROUND) {
            ROS_ERROR(
                "Please set a larger zmax: from %.2f to bigger than %.2f, or Octree map may contain floor features!",
                cfg_->zmax_, MIN_DISTANCE_TO_GROUND + voxelblock_side * float(voxelblock_num));
            return false;
        }
        if (cfg_->zmin_ < min_acceptable_z) {
            ROS_ERROR(
                "Please set a larger zmin: from %.2f to bigger than %.2f, or Octree map may contain floor features!",
                cfg_->zmin_, min_acceptable_z);
            return false;
        }

        get_ros_param("map_size", cfg_->map_size_, 256);
        if (cfg_->map_size_ <= 0) {
            ROS_ERROR("map_size (voxels) should be a positive number greater then zero");
            return false;
        }

        get_ros_param("depth_scaling_factor", cfg_->depth_scaling_factor_);
        if (cfg_->depth_scaling_factor_ <= 0) {
            ROS_ERROR("depth_scaling_factor must be a positive value greater then zero");
            return false;
        }

        get_ros_param("correction_threshold", cfg_->correction_threshold_, 4);
        if (cfg_->correction_threshold_ <= 0) {
            ROS_ERROR("correction_threshold must be a positive value greater then zero");
            return false;
        }

        get_ros_param("octree_store_path", cfg_->octree_store_path_, "");
    }

    get_ros_param("octree_load_path", cfg_->octree_load_path_, "");
    if (cfg_->mode_ == "remapping" && cfg_->octree_load_path_.empty()) {
        ROS_ERROR("option octree_load_path shouldn't be empty in remapping mode!");
        return false;
    }

    if (cfg_->mode_ == "remapping") {
        get_ros_param("remapping_region", cfg_->remapping_region_vertexes_);
        /*
            The first condition "size == 1 && vector[0] = 0.0" is the
            default value of remapping_region option in config file.
            Since we allow the tracker construct the entire Octree map
            in the two session solution, the remapping_region option is
            not mandatory currently.

            we also provide the remaping_region option on server side.
            And user can only configure the one on server side.
        */
        if (cfg_->remapping_region_vertexes_.size() != 1 || cfg_->remapping_region_vertexes_[0] > EPSILON ||
            cfg_->remapping_region_vertexes_[0] < -EPSILON) {
            if (cfg_->remapping_region_vertexes_.size() != 8) {
                ROS_ERROR("Option remapping_region should include 4 points in the format of [P1.x, P1.y, P2.x, \
                           P2.y, P3.x, P3.y, P4.x, P4.y]");
                return false;
            }

            cfg_->enable_remapping_region_ = true;
        }
    }

    // Indicate if we want to force the best effort ROS service QoS
    // For multiple robots > 2 this should be true
    get_ros_param("force_best_effort", cfg_->force_best_effort_qos_, false);

    // Create SLAM system. It initializes all system threads and gets ready to process frames.
    tracker_ = std::make_unique<univloc_tracker::Tracker>(cfg_, this->shared_from_this());
    tracker_->start();
    tracker_started_ = true;

    ROS_INFO("Successfully start tracker node!");
    return true;
}

void TrackerNode::stop()
{
    if (tracker_started_) {
        tracker_started_ = false;
        tracker_->shutdown();
    }
}

bool TrackerNode::read_config_from_ros(std::string camera_info_topic, std::string right_camera_info_topic)
{
    // communication parameters
    int temp_id = 0;
    get_ros_param("ID", temp_id);
    cfg_->client_id_ = static_cast<ClientID>(temp_id);
    if (temp_id < 0 || temp_id > 255)
        ROS_WARN("Tracker ID should be in [0, 255]: given %d, casted to %hhu", temp_id, cfg_->client_id_);

    // GUI parameters
    get_ros_param("gui", cfg_->gui_, false);

    // camera parameters
    get_ros_param("model_type", cfg_->model_type_str_, "Perspective");
    get_ros_param("queue_size", cfg_->queue_capacity_);
    if (cfg_->queue_capacity_ < 0)
        throw std::invalid_argument("queue_size parameter needs to be positive!");
    get_ros_param("camera_baseline", cfg_->camera_baseline_, 0.05);
    get_ros_param("camera_fps", cfg_->camera_fps_, 30.0);
    get_ros_param("camera_name", cfg_->camera_name_, "D435i");
    get_ros_param("camera_setup", cfg_->setup_type_str_, "RGBD");
    get_ros_param("camera_color_order", cfg_->color_order_str_, "RGB");
    get_ros_param("depthmap_factor", cfg_->depthmap_factor_, 1000.0);
    if (cfg_->depthmap_factor_ < EPSILON)
        throw std::invalid_argument("depthmap_factor must be greater than 0!");
    bool p_get_camera_info_from_topic = true;
    get_ros_param("get_camera_info_from_topic", p_get_camera_info_from_topic);
    get_ros_param("num_min_triangulated_pts", cfg_->init_num_min_triangulated_pts_, 50);
    if (cfg_->init_num_min_triangulated_pts_ < 0)
        throw std::invalid_argument("num_min_triangulated_pts must be greater than 0!");
    get_ros_param("tf_fix_frame", cfg_->tf_fix_frame_, "");
    get_ros_param("image_frame", cfg_->image_frame_);
    if (cfg_->image_frame_ == "")
        cfg_->image_frame_set_in_launch_file_ = false;
    else
        cfg_->image_frame_set_in_launch_file_ = true;
    if (p_get_camera_info_from_topic) {
        auto camera_info_msg = get_camera_info_msg_from_topic(camera_info_topic);
        if (!camera_info_msg) {
            return false;
        }
        cfg_->width_ = camera_info_msg->width;
        cfg_->height_ = camera_info_msg->height;
        {
            auto camera_k = camera_info_msg->k;
            auto camera_d = camera_info_msg->d;
            cfg_->fx_ = camera_k[0];
            cfg_->fy_ = camera_k[4];
            cfg_->cx_ = camera_k[2];
            cfg_->cy_ = camera_k[5];
            /*
                camera_info in ros message definition always have 5 parameters for distortion parameters,
                however, for fisheye camera, only the first 4 paramters are useful.
                therefore, we need to extract them out before feeding into the system.
                http://docs.ros.org/en/noetic/api/sensor_msgs/html/msg/CameraInfo.html
            */
            if (cfg_->model_type_str_ == "Fisheye") {
                std::vector<double> distortion_tmp;
                for (int i = 0; i < 4; ++i) distortion_tmp.push_back(camera_d[i]);
                cfg_->set_distortion_params(distortion_tmp);
            } else if (cfg_->model_type_str_ == "Perspective") {
                cfg_->set_distortion_params(camera_d);
            } else {
                ROS_ERROR("Camera model isn't supported!");
                return false;
            }
        }
        if (cfg_->image_frame_ == "") cfg_->image_frame_ = camera_info_msg->header.frame_id;
        while (cfg_->is_stereo()) {
            get_ros_param("enable_rectifier", cfg_->enable_rectifier_, true);
            if (!cfg_->enable_rectifier_) break;
            auto right_camera_info_msg = get_camera_info_msg_from_topic(right_camera_info_topic);
            if (!right_camera_info_msg) {
                return false;
            }
            get_ros_param("tf_right_camera_frame", cfg_->tf_right_camera_frame_, "");
            if (cfg_->tf_right_camera_frame_ == "") {
                std::string::size_type start_position;
                std::string::size_type id_size = camera_info_msg->header.frame_id.size();
                start_position = camera_info_msg->header.frame_id.find("infra1");

                if (start_position == std::string::npos) {
                    return false;
                }
                cfg_->tf_right_camera_frame_ = camera_info_msg->header.frame_id.substr(0, start_position) + "infra2"
                    + camera_info_msg->header.frame_id.substr(start_position+6, id_size-start_position-6);
            }
            Eigen::Matrix4d left_to_right;
            if (!get_tf_matrix(cfg_->tf_left_right_, camera_info_msg->header.frame_id,
                cfg_->tf_right_camera_frame_, rosx::Time(0))) {
                ROS_ERROR("Failed to get stereo camera extrinsics from tf");
                return false;
            }
            {
                auto &K1 = camera_info_msg->k;
                auto &D1 = camera_info_msg->d;
                auto &K2 = right_camera_info_msg->k;
                auto &D2 = right_camera_info_msg->d;
                cfg_->K1 = (cv::Mat_<double>(3, 3) << K1[0], K1[1], K1[2], K1[3], K1[4], K1[5], K1[6], K1[7], K1[8]);
                cfg_->K2 = (cv::Mat_<double>(3, 3) << K2[0], K2[1], K2[2], K2[3], K2[4], K2[5], K2[6], K2[7], K2[8]);
                cfg_->D1 = (cv::Mat_<double>(4, 1) << D1[0], D1[1], D1[2], D1[3]);
                cfg_->D2 = (cv::Mat_<double>(4, 1) << D2[0], D2[1], D2[2], D2[3]);
            }
            break;
        }
    } else {
        get_ros_param("rectifier_params_given", cfg_->rectifier_params_given_, true);
        std::vector<double> intrinsics, distortion;
        get_ros_param("camera_intrinsics", intrinsics);
        get_ros_param("camera_distortion", distortion);
        if (!cfg_->is_stereo()) {
            // now only support perspective and fisheye
            // TODO: add equirectangular
            if (intrinsics.size() != 6) {
                ROS_ERROR("Please input correct intrinsics, current size = %zu, but expected size = 6",
                          intrinsics.size());
                return false;
            }

            if ((cfg_->model_type_str_ == "Perspective" && distortion.size() != 5) ||
                (cfg_->model_type_str_ == "Fisheye" && distortion.size() != 4)) {
                ROS_ERROR("Please input correct distortion in launch file according to camera model");
                return false;
            }

            cfg_->width_ = static_cast<int>(intrinsics[0]);
            cfg_->height_ = static_cast<int>(intrinsics[1]);
            cfg_->fx_ = intrinsics[2];
            cfg_->fy_ = intrinsics[3];
            cfg_->cx_ = intrinsics[4];
            cfg_->cy_ = intrinsics[5];
            cfg_->set_distortion_params(distortion);
        } else {
            get_ros_param("enable_rectifier", cfg_->enable_rectifier_, true);
            if (cfg_->enable_rectifier_) {
                if (cfg_->rectifier_params_given_) {
                    if (intrinsics.size() != 6) {
                        ROS_ERROR("Please input correct intrinsics, current size = %zu, but expected size = 6",
                                  intrinsics.size());
                        return false;
                    }

                    if ((cfg_->model_type_str_ == "Perspective" && distortion.size() != 5) ||
                        (cfg_->model_type_str_ == "Fisheye" && distortion.size() != 4)) {
                        ROS_ERROR("Please input correct distortion in launch file according to camera model");
                        return false;
                    }
                } else {
                    // width, height, left camera (fx, fy, cx, cy, fx), right camera (fx, fy, cx, cy)
                    if (intrinsics.size() != 10) {
                        ROS_ERROR("Please input correct intrinsics, current size =%zu, but expected size = 10",
                                  intrinsics.size());
                        return false;
                    }

                    // left camera (k1, k2, p1, p2, k3), right camera (k1, k2, p1, p2, k3)
                    if (cfg_->model_type_str_ == "Perspective" && distortion.size() != 10) {
                        ROS_ERROR(
                            "Please input correct distortions, current size = %zu, but perspective camera size = 10",
                            distortion.size());
                        return false;
                    }

                    // left camera (k1, k2, k3, k4), right camera (k1, k2, k3, k4)
                    if (cfg_->model_type_str_ == "Fisheye" && distortion.size() != 8) {
                        ROS_ERROR("Please input correct distortions, current size = %zu, but fisheye camera size = 8",
                                  distortion.size());
                        return false;
                    }
                }
            } else {
                /*
                    when enable_rectifier is set to false, there could be two cases:
                    1) normal case (kitti), the intrinsic and distortion matrix would be the same for stereo camreas
                    2) special case (t265 camera), the intrinsic and distortion matrix are different
                    to both support these two cases, we need to change the input check logic as follows
                */
                if (intrinsics.size() != 10 && intrinsics.size() != 6) {
                    ROS_ERROR("Please input correct intrinsics, current size = %zu, but expected size = 10 or 6",
                              intrinsics.size());
                    return false;
                }

                if (cfg_->model_type_str_ == "Perspective" && (distortion.size() != 10 && distortion.size() != 5)) {
                    ROS_ERROR(
                        "Please input correct distortions, current size = %zu, but perspective camera size = 10 or 5",
                        distortion.size());
                    return false;
                }

                if (cfg_->model_type_str_ == "Fisheye" && (distortion.size() != 8 && distortion.size() != 4)) {
                    ROS_ERROR("Please input correct distortions, current size = %zu, but fisheye camera size = 8 or 4",
                              distortion.size());
                    return false;
                }
            }

            cfg_->width_ = static_cast<int>(intrinsics[0]);
            cfg_->height_ = static_cast<int>(intrinsics[1]);
            cfg_->fx_ = intrinsics[2];
            cfg_->fy_ = intrinsics[3];
            cfg_->cx_ = intrinsics[4];
            cfg_->cy_ = intrinsics[5];
            std::vector<double> distortion_tmp;
            int distortion_size;
            if (cfg_->model_type_str_ == "Fisheye")
                distortion_size = 4;
            else if (cfg_->model_type_str_ == "Perspective")
                distortion_size = 5;
            else {
                ROS_ERROR("Camera model isn't supported!");
                return false;
            }
            for (int i = 0; i < distortion_size; ++i) distortion_tmp.push_back(distortion[i]);
            cfg_->set_distortion_params(distortion_tmp);

            if (cfg_->enable_rectifier_) {
                if (cfg_->rectifier_params_given_) {
                    get_ros_param("focal_x_baseline", cfg_->focal_x_baseline_, 0.0);
                    std::vector<double> K_left, K_right, D_left, D_right, R_left, R_right;
                    get_ros_param("K_left", K_left);
                    get_ros_param("K_right", K_right);
                    get_ros_param("D_left", D_left);
                    get_ros_param("D_right", D_right);
                    get_ros_param("R_left", R_left);
                    get_ros_param("R_right", R_right);
                    if (K_left.size() != 9 || K_right.size() != 9 || D_left.size() != 5 || D_right.size() != 5 ||
                        R_left.size() != 9 || R_right.size() != 9) {
                        ROS_ERROR("Please provide rectifier related parameters in launch file");
                        return false;
                    }
                    cfg_->K_left_ = (cv::Mat_<double>(3, 3) << K_left[0], K_left[1], K_left[2], K_left[3], K_left[4],
                                     K_left[5], K_left[6], K_left[7], K_left[8]);
                    cfg_->K_right_ = (cv::Mat_<double>(3, 3) << K_right[0], K_right[1], K_right[2], K_right[3],
                                      K_right[4], K_right[5], K_right[6], K_right[7], K_right[8]);
                    cfg_->D_left_ = (cv::Mat_<double>(5, 1) << D_left[0], D_left[1], D_left[2], D_left[3], D_left[4]);
                    cfg_->D_right_ = (cv::Mat_<double>(5, 1) << D_right[0], D_right[1], D_right[2], D_right[3], D_right[4]);
                    cfg_->R_left_ = (cv::Mat_<double>(3, 3) << R_left[0], R_left[1], R_left[2], R_left[3], R_left[4],
                                     R_left[5], R_left[6], R_left[7], R_left[8]);
                    cfg_->R_right_ = (cv::Mat_<double>(3, 3) << R_right[0], R_right[1], R_right[2], R_right[3],
                                      R_right[4], R_right[5], R_right[6], R_right[7], R_right[8]);
                } else {
                    cfg_->K1 = (cv::Mat_<double>(3, 3) << intrinsics[2], 0, intrinsics[4], 0, intrinsics[3],
                                intrinsics[5], 0, 0, 1);
                    cfg_->K2 = (cv::Mat_<double>(3, 3) << intrinsics[6], 0, intrinsics[8], 0, intrinsics[7],
                                intrinsics[9], 0, 0, 1);
                    cfg_->D1 = (cv::Mat_<double>(4, 1) << distortion[0], distortion[1], distortion[2], distortion[3]);
                    cfg_->D2 = (cv::Mat_<double>(4, 1) << distortion[4], distortion[5], distortion[6], distortion[7]);

                    std::vector<double> T;
                    get_ros_param("left_to_right_transform", T);
                    if (T.size() != 12) {
                        ROS_ERROR("Please input correct transform from left to right in launch file");
                        return false;
                    }

                    cfg_->tf_left_right_ << T[0], T[1], T[2], T[3], T[4], T[5], T[6], T[7], T[8], T[9], T[10], T[11], 0,
                        0, 0, 1;
                }
            }
        }
    }

    // ORB parameters
    get_ros_param("max_num_keypoints", cfg_->max_num_keypoints_);
    if (cfg_->max_num_keypoints_ < 0)
        throw std::invalid_argument("max_num_keypoints should be a positive number!");
    get_ros_param("orb_scale_factor", cfg_->orb_scale_factor_);
    get_ros_param("orb_num_levels", cfg_->orb_num_levels_);
    if (cfg_->orb_num_levels_ <= 0)
        throw std::invalid_argument("orb_num_levels should be greater than 0!");
    get_ros_param("orb_ini_fast_threshold", cfg_->orb_ini_fast_threshold_);
    get_ros_param("orb_min_fast_threshold", cfg_->orb_min_fast_threshold_);
    if (cfg_->orb_ini_fast_threshold_ < 0 || cfg_->orb_min_fast_threshold_ < 0)
        throw std::invalid_argument("orb fast thresholds should be > 0!");

    get_ros_param("orb_mask_image", cfg_->mask_image_path_);
    auto exist = [](std::string filename) -> bool {
        std::ifstream fs(filename);
        return fs.good();
    };
    if (!cfg_->mask_image_path_.empty() && !exist(cfg_->mask_image_path_)) {
        ROS_ERROR("Wrong mask image file path: %s", cfg_->mask_image_path_.c_str());
        return false;
    }

    std::vector<double> mask_rects_vec;
    get_ros_param("orb_mask_rectangles", mask_rects_vec);
    if (mask_rects_vec.size() == 16) {
        cfg_->mask_rects_.resize(4);
        unsigned int index = 0;
        for (auto &rect : cfg_->mask_rects_) {
            rect.push_back(mask_rects_vec[index * 4]);
            rect.push_back(mask_rects_vec[index * 4 + 1]);
            rect.push_back(mask_rects_vec[index * 4 + 2]);
            rect.push_back(mask_rects_vec[index * 4 + 3]);
            index++;
        }
    }
#ifdef GPU_KERNEL_PATH
    ROS_INFO("GPU Kernel path: %s", ORBLZE_KERNEL_PATH_STRING);
#endif
    get_ros_param("vocabulary", cfg_->vocabulary_path_, "orb_vocab.dbow2");
    do {
        // check whether the given path is absolute or relative to the config folder
        if (exist(cfg_->vocabulary_path_)) break;
        std::string another_path = std::string(CONFIG_PATH) + cfg_->vocabulary_path_;
        if (exist(another_path)) {
            cfg_->vocabulary_path_ = another_path;
            break;
        }
        std::string package_dir = ament_index_cpp::get_package_share_directory("univloc_tracker");
        ROS_INFO("univloc tracker package dir is %s", package_dir.c_str());
        std::string alternative_path = package_dir + "/config/" + cfg_->vocabulary_path_;
        if (exist(alternative_path)) {
            cfg_->vocabulary_path_ = alternative_path;
            break;
        }
        ROS_ERROR("Wrong vocabulary path: %s", cfg_->vocabulary_path_.c_str());
        return false;
    } while (false);

    // tracking parameters
    get_ros_param("depth_threshold", cfg_->depth_threshold_);
    /*
        for stereo/RGBD input, true depth threshold equals to camera_baseline multiplied by the depth threshold factor
        for monocular input, depth threshold will not be used
    */
    if (cfg_->is_stereo() || cfg_->is_rgbd()) cfg_->depth_threshold_ = cfg_->camera_baseline_ * cfg_->depth_threshold_;
    get_ros_param("initialize_by_server", cfg_->initialize_by_server_, false);
    get_ros_param("slam_mode", cfg_->mode_, "mapping");
    get_ros_param("traj_store_path", cfg_->traj_store_path_, "");
    get_ros_param("clean_keyframe", cfg_->clean_keyframe_);
    if (cfg_->mode_ == "localization") {
        int temp_divisor;
        get_ros_param("reloc_trig_divisor", temp_divisor, 1);
        if (temp_divisor < 1) {
            ROS_ERROR("the divisor to trigger relocalization request should be positive, given %d", temp_divisor);
            return false;
        }
        cfg_->trigger_relocalization_request_divisor_ = temp_divisor;
    }
    if (cfg_->mode_ == "mapping") {
        get_ros_param("need_covariance", cfg_->need_covariance_, false);
    }

    // odom parameters
    get_ros_param("use_odom", cfg_->use_odom_);
    get_ros_param("odom_frame", cfg_->odom_frame_);
    get_ros_param("odom_tf_query_timeout", cfg_->odom_tf_query_timeout_);
    if (cfg_->odom_tf_query_timeout_ < 0)
        throw std::invalid_argument("odom_tf_query_timeout should be a positive number!");
    get_ros_param("odom_buffer_query_timeout", cfg_->odom_buffer_query_timeout_);
    if (cfg_->odom_buffer_query_timeout_ < 0)
        throw std::invalid_argument("odom_buffer_query_timeout should be a positive number!");
    if (cfg_->odom_buffer_query_timeout_ < cfg_->odom_tf_query_timeout_) {
        cfg_->odom_buffer_query_timeout_ = cfg_->odom_tf_query_timeout_;
    }
    // the transformation matrix between camera coordinate and image frame (T_ic)
    // this variable should only be used when no image_frame is provided in tf tree
    // then we will set image_frame equals to camera_link
    // and use this transform to ensure the system to work properly
    std::vector<double> T_image_to_camera = {0.0};
    get_ros_param("T_image_to_camera", T_image_to_camera);
    if (T_image_to_camera.size() == 16) {
        cfg_->T_image_to_camera_ << T_image_to_camera[0], T_image_to_camera[1], T_image_to_camera[2],
            T_image_to_camera[3], T_image_to_camera[4], T_image_to_camera[5], T_image_to_camera[6],
            T_image_to_camera[7], T_image_to_camera[8], T_image_to_camera[9], T_image_to_camera[10],
            T_image_to_camera[11], T_image_to_camera[12], T_image_to_camera[13], T_image_to_camera[14],
            T_image_to_camera[15];
    } else if (T_image_to_camera.size() != 1 || (T_image_to_camera.size() == 1 && T_image_to_camera[0] != 0.0)) {
        ROS_ERROR("The param T_image_to_camera must be a vector with 16 double floats");
        return false;
    }

    // camera extrinsics
    bool get_camera_extrin_from_tf = true;
    get_ros_param("get_camera_extrin_from_tf", get_camera_extrin_from_tf);
    bool get_camera_extrin_succeed = false;
    if (get_camera_extrin_from_tf) {
        std::string base_frame;
        get_ros_param("baselink_frame", base_frame, "base_link");
        cfg_->base_link_frame_ = base_frame;
        double camera_extrin_query_timeout;
        get_ros_param("camera_extrin_query_timeout", camera_extrin_query_timeout, 10.0);
        // in case the transformation between base_link and image frame is not statically broadcasted
        // so we need a loop to query this transformation and also a timeout parameter for default camera extrinsic parameter
        const auto query_start = std::chrono::system_clock::now();
        std::chrono::duration<float> query_duration(0.0);
        while ((get_camera_extrin_succeed = get_tf_matrix(cfg_->tf_base_camera_, base_frame, cfg_->image_frame_, rosx::Time(0))) == false) {
            const auto query_now = std::chrono::system_clock::now();
            query_duration = query_now - query_start;
            if (query_duration.count() > camera_extrin_query_timeout) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
        // cfg_->tf_base_camera_ actually means the transformation matrix between base_link and image_frame
        // typically T_image_to_camera should be identity, so it will not influence the result of tf_base_camera_
        // when T_image_to_camera is non-identity (no image_frame provided in tf tree), the value should be updated
        if (T_image_to_camera.size() == 16) {
            cfg_->tf_base_camera_ = cfg_->tf_base_camera_ * cfg_->T_image_to_camera_.inverse();
        }
    } else {
        // TODO get extrin from param
        get_camera_extrin_succeed = false;
    }
    if (!get_camera_extrin_succeed) {
        ROS_WARN("Failed to get T(base,camera). Will assume front-facing.");
        cfg_->tf_base_camera_ << 0., 0., 1., 0., -1., 0., 0., 1.2, 0., -1., 0., 0., 0., 0., 0., 1.;
    }

    // Lidar extrinsics
    if(cfg_->lidar_enable_) {
        bool get_lidar_extrin_from_tf = false;
        get_ros_param("get_lidar_extrin_from_tf", get_lidar_extrin_from_tf);
        if (get_lidar_extrin_from_tf) {
            std::string lidar_frame;
            get_ros_param("lidar_frame", lidar_frame);
            if (lidar_frame.empty()) {
                ROS_ERROR("Please specify lidar_frame in launch file");
                return false;
            }
            if (!get_tf_matrix(cfg_->tf_base_lidar_, cfg_->base_link_frame_, lidar_frame, rosx::Time(0))) {
                ROS_ERROR("Failed to get lidar extrinsics from tf");
                return false;
            }
        } else {
            std::vector<double> T_vec;
            get_ros_param("tf_base_lidar", T_vec);
            if (T_vec.size() != 7) {
                ROS_ERROR("The param tf_base_lidar must be a vector with 7 double floats");
                return false;
            }
            Eigen::Vector3d t(T_vec[0], T_vec[1], T_vec[2]);
            Eigen::Quaterniond q(T_vec[3], T_vec[4], T_vec[5], T_vec[6]);
            cfg_->tf_base_lidar_.setIdentity();
            cfg_->tf_base_lidar_.block(0, 0, 3, 3) = q.toRotationMatrix();
            cfg_->tf_base_lidar_.block(0, 3, 3, 1) = t;
            cfg_->tf_lidar_camera_ = cfg_->tf_base_lidar_.inverse() * cfg_->tf_base_camera_;
        }
    }

    if (!cfg_->enable_imu()) return true;

    // IMU extrinsics
    bool get_imu_extrin_from_tf = false;
    get_ros_param("get_imu_extrin_from_tf", get_imu_extrin_from_tf);
    if (get_imu_extrin_from_tf) {
        std::string imu_frame;
        get_ros_param("imu_frame", imu_frame);
        if (imu_frame.empty()) {
            ROS_ERROR("Please specify imu_frame in launch file");
            return false;
        }
        if (!get_tf_matrix(cfg_->tf_camera_imu_, cfg_->image_frame_, imu_frame, rosx::Time(0))) {
            ROS_ERROR("Failed to get imu extrinsics from tf");
            return false;
        }
    } else {
        std::vector<double> T_vec;
        get_ros_param("tf_camera_imu", T_vec);
        if (T_vec.size() != 7) {
            ROS_ERROR("The param tf_camera_imu must be a vector with 7 double floats");
            return false;
        }
        Eigen::Vector3d t(T_vec[0], T_vec[1], T_vec[2]);
        Eigen::Quaterniond q(T_vec[3], T_vec[4], T_vec[5], T_vec[6]);
        cfg_->tf_camera_imu_.setIdentity();
        cfg_->tf_camera_imu_.block(0, 0, 3, 3) = q.toRotationMatrix();
        cfg_->tf_camera_imu_.block(0, 3, 3, 1) = t;
    }

    // IMU intrinsics
    std::vector<double> imu_noise_vec, imu_bias_vec, imu_bias_walk_vec;
    get_ros_param("imu_frequency", cfg_->imu_frequency_, 200);
    get_ros_param("imu_noise", imu_noise_vec); // ngx, ngy, ngz, nax, nay, naz
    get_ros_param("imu_bias", imu_bias_vec);
    get_ros_param("imu_bias_walker", imu_bias_walk_vec); // wgx, wgy, wgz, wax, way, waz

    if (imu_noise_vec.size() != 6 || imu_bias_vec.size() != 6 || imu_bias_walk_vec.size() != 6) {
        ROS_ERROR("The param imu_noise/imu_bias/imu_bias_walker must be a vector with 6 double floats");
        return false;
    }
    cfg_->imu_bias_ << imu_bias_vec[0], imu_bias_vec[1], imu_bias_vec[2], imu_bias_vec[3], imu_bias_vec[4],
        imu_bias_vec[5];
    cfg_->imu_noise_ << imu_noise_vec[0], imu_noise_vec[1], imu_noise_vec[2], imu_noise_vec[3], imu_noise_vec[4],
        imu_noise_vec[5];
    cfg_->imu_bias_walk_ << imu_bias_walk_vec[0], imu_bias_walk_vec[1], imu_bias_walk_vec[2], imu_bias_walk_vec[3],
        imu_bias_walk_vec[4], imu_bias_walk_vec[5];

    return true;
}

void TrackerNode::camera_info_callback(const sensor_msgs::CameraInfoConstPtr msg)
{
    if (msg && msg->width > 0 && msg->height > 0 && msg->header.frame_id != "") {
        camera_info_msg_.reset(new sensor_msgs::CameraInfo(*msg));
        camera_info_ready_promise_.set_value();
    }
}

std_msgs::ColorRGBA TrackerNode::index_to_color(unsigned int id)
{
    struct Color {
        std::string name;
        int r;
        int g;
        int b;
    };
    static const std::vector<Color> all_colors = {
        Color{"red", 255, 0, 0}, Color{"blue", 0, 0, 255}, Color{"green", 0, 255, 0}, Color{"pink", 255, 192, 203},
        Color{"yellow", 255, 255, 0}, Color{"hot_pink", 255, 105, 180}, Color{"orange", 255, 165, 0},
        Color{"purple", 128, 0, 128}, Color{"orange_red", 255, 59, 0}, Color{"gold", 255, 215, 0},
        Color{"magenta", 255, 0, 255}, Color{"lime", 0, 128, 0},
        // Color{"cyan", 0, 255, 255},
        Color{"chocolate", 210, 105, 30},
        // Color{"brown", 165, 42, 42},
        // Color{"ghost_white", 248, 248, 255},
        // Color{"azure", 240, 255, 255},
        // Color{"black", 0, 0, 0},
        // Color{"gray", 128, 128, 128},
        // Color{"silver", 192, 192, 192}
    };

    Color color = all_colors[(id) % all_colors.size()];
    std_msgs::ColorRGBA rgba;
    rgba.r = color.r / 255.;
    rgba.g = color.g / 255.;
    rgba.b = color.b / 255.;
    rgba.a = 1.0;
    return rgba;
}

void TrackerNode::publish_local_map(const Eigen::Matrix4d &Tcw)
{
    if (rosx::getNumSubscribers(pub_local_map_) == 0) return;

    static unsigned int color_num = 13;

    std::set<unsigned int> used_color;

    auto client_id = tracker_->get_client_id();

    auto server_landmarks_clientID_position = tracker_->get_server_landmarks_clientID_position();

    static const double half_width = 0.3;
    static const double half_height = 0.24;
    const double offset = -0.08;
    static const std::vector<Eigen::Vector3d> line_strip_points = {Eigen::Vector3d(0, 0, 0),
                                                                   Eigen::Vector3d(-half_width, -half_height, offset),
                                                                   Eigen::Vector3d(-half_width, half_height, offset),
                                                                   Eigen::Vector3d(half_width, half_height, offset),
                                                                   Eigen::Vector3d(half_width, -half_height, offset),
                                                                   Eigen::Vector3d(-half_width, -half_height, offset),
                                                                   Eigen::Vector3d(0, 0, 0)};

    std_msgs::ColorRGBA camera_color, tracked_server_landmark_marker_color, covisibility_keyframes_marker_color,
        non_covisibility_keyframes_marker_color;
    visualization_msgs::MarkerArray msg;
    visualization_msgs::Marker empty_marker;
    empty_marker.header.stamp = rosx::now();
    empty_marker.id = 0;
    empty_marker.action = 0;  // add or modify
    empty_marker.pose.orientation.w = 1.0;
    empty_marker.scale.x = 0.05;
    empty_marker.scale.y = empty_marker.scale.z = 0.0;
    std::map<std::string, visualization_msgs::Marker> server_landmark_markers, local_landmark_markers;

    visualization_msgs::Marker camera_marker, tracked_server_landmark_marker, covisibility_keyframes_marker,
        non_covisibility_keyframes_marker;

    geometry_msgs::Point point;

    for (const auto& clientID_p : server_landmarks_clientID_position) {
        std::string ns = "server_landmark" + std::to_string(clientID_p.first);
        if (!server_landmark_markers.count(ns)) {
            server_landmark_markers[ns] = empty_marker;
            server_landmark_markers[ns].type = visualization_msgs::Marker::POINTS;
            server_landmark_markers[ns].header.frame_id = p_map_frame_;
            server_landmark_markers[ns].ns = ns;
            server_landmark_markers[ns].color = index_to_color(clientID_p.first);
            used_color.insert(clientID_p.first);
            server_landmark_markers[ns].scale.x = 0.1;
            server_landmark_markers[ns].scale.y = 0.1;
            server_landmark_markers[ns].scale.z = 0.1;
        }
        point.x = clientID_p.second[0];
        point.y = clientID_p.second[1];
        point.z = clientID_p.second[2];
        server_landmark_markers[ns].points.push_back(point);
    }

    camera_color = index_to_color(client_id);
    used_color.insert(client_id);

    std::string ns = "camera";
    camera_marker = empty_marker;
    camera_marker.type = visualization_msgs::Marker::LINE_STRIP;
    camera_marker.header.frame_id = p_map_frame_;
    camera_marker.ns = ns;
    camera_marker.color = camera_color;
    camera_marker.scale.x = 0.1;
    camera_marker.scale.y = 0.1;
    camera_marker.scale.z = 0.1;

    Eigen::Affine3d Twc(Tcw.inverse());
    for (const auto &pos_camera : line_strip_points) {
        Eigen::Vector3d pos = Twc * pos_camera;
        point.x = pos[0];
        point.y = pos[1];
        point.z = pos[2];
        camera_marker.points.push_back(point);
    }

    ns = "local_landmark" + std::to_string(client_id);
    local_landmark_markers[ns] = empty_marker;
    local_landmark_markers[ns].type = visualization_msgs::Marker::POINTS;
    local_landmark_markers[ns].header.frame_id = p_map_frame_;
    local_landmark_markers[ns].ns = ns;
    local_landmark_markers[ns].color = index_to_color(client_id);
    local_landmark_markers[ns].scale.x = 0.1;
    local_landmark_markers[ns].scale.y = 0.1;
    local_landmark_markers[ns].scale.z = 0.1;
    auto local_landmark_positions = tracker_->get_local_landmark_positions();
    for (const auto &p: local_landmark_positions) {
        point.x = p[0];
        point.y = p[1];
        point.z = p[2];
        local_landmark_markers[ns].points.push_back(point);
    }

    for (unsigned int i = 0; i < color_num; i++) {
        if (!used_color.count(i)) {
            used_color.insert(i);
            tracked_server_landmark_marker_color = index_to_color(i);
            break;
        }
    }

    // Publish ray of tracked server landmarks
    ns = "tracked_server_landmark";
    std::vector<Eigen::Vector3d> tracked_server_landmarks;
    tracker_->get_tracked_server_landmarks(tracked_server_landmarks);
    tracked_server_landmark_marker = empty_marker;
    tracked_server_landmark_marker.type = visualization_msgs::Marker::LINE_LIST;
    tracked_server_landmark_marker.header.frame_id = p_map_frame_;
    tracked_server_landmark_marker.ns = ns;
    tracked_server_landmark_marker.color = tracked_server_landmark_marker_color;
    tracked_server_landmark_marker.scale.x = 0.03;
    tracked_server_landmark_marker.scale.y = 0.03;
    tracked_server_landmark_marker.scale.z = 0.03;

    if (tracked_server_landmarks.size() > 2) {
        geometry_msgs::Point camera_center, pos_landmark;
        int landmark_size = tracked_server_landmarks.size() - 1;
        camera_center.x = tracked_server_landmarks.back()[0];
        camera_center.y = tracked_server_landmarks.back()[1];
        camera_center.z = tracked_server_landmarks.back()[2];

        for (int i = 0; i < landmark_size; i++) {
            pos_landmark.x = tracked_server_landmarks[i][0];
            pos_landmark.y = tracked_server_landmarks[i][1];
            pos_landmark.z = tracked_server_landmarks[i][2];
            tracked_server_landmark_marker.points.push_back(camera_center);
            tracked_server_landmark_marker.points.push_back(pos_landmark);
        }
    }

    std::vector<Eigen::Matrix4d> covisibility_poses, non_civisibility_poses;
    tracker_->get_keyframes(covisibility_poses, non_civisibility_poses);

    for (unsigned int i = 0; i < color_num; i++) {
        if (!used_color.count(i)) {
            used_color.insert(i);
            covisibility_keyframes_marker_color = index_to_color(i);
            break;
        }
    }
    ns = "covisibility_keyframes";
    covisibility_keyframes_marker = empty_marker;
    covisibility_keyframes_marker.type = visualization_msgs::Marker::LINE_STRIP;
    covisibility_keyframes_marker.header.frame_id = p_map_frame_;
    covisibility_keyframes_marker.ns = ns;
    covisibility_keyframes_marker.color = covisibility_keyframes_marker_color;
    covisibility_keyframes_marker.scale.x = 0.1;
    covisibility_keyframes_marker.scale.y = 0.1;
    covisibility_keyframes_marker.scale.z = 0.1;

    for (const auto& p : covisibility_poses) {
        Eigen::Affine3d Twc(p);
        for (const auto &pos_camera : line_strip_points) {
            Eigen::Vector3d pos = Twc * pos_camera;
            geometry_msgs::Point point;
            point.x = pos[0];
            point.y = pos[1];
            point.z = pos[2];
            covisibility_keyframes_marker.points.push_back(point);
        }
    }

    for (unsigned int i = 0; i < color_num; i++) {
        if (!used_color.count(i)) {
            used_color.insert(i);
            non_covisibility_keyframes_marker_color = index_to_color(i);
            break;
        }
    }
    ns = "non_covisibility_keyframes";
    non_covisibility_keyframes_marker = empty_marker;
    non_covisibility_keyframes_marker.type = visualization_msgs::Marker::LINE_STRIP;
    non_covisibility_keyframes_marker.header.frame_id = p_map_frame_;
    non_covisibility_keyframes_marker.ns = ns;
    non_covisibility_keyframes_marker.color = non_covisibility_keyframes_marker_color;
    non_covisibility_keyframes_marker.scale.x = 0.1;
    non_covisibility_keyframes_marker.scale.y = 0.1;
    non_covisibility_keyframes_marker.scale.z = 0.1;
    for (const auto& p : non_civisibility_poses) {
        Eigen::Affine3d Twc(p);
        for (const auto &pos_camera : line_strip_points) {
            Eigen::Vector3d pos = Twc * pos_camera;
            geometry_msgs::Point point;
            point.x = pos[0];
            point.y = pos[1];
            point.z = pos[2];
            non_covisibility_keyframes_marker.points.push_back(point);
        }
    }
    for (const auto& it : server_landmark_markers) {
        msg.markers.push_back(it.second);
    }

    for (const auto& item : local_landmark_markers) msg.markers.push_back(item.second);
    msg.markers.push_back(tracked_server_landmark_marker);
    msg.markers.push_back(camera_marker);
    msg.markers.push_back(covisibility_keyframes_marker);
    msg.markers.push_back(non_covisibility_keyframes_marker);

    pub_local_map_->publish(msg);
}

void TrackerNode::publish_occupancy_map()
{
    if (rosx::getNumSubscribers(pub_occupancy_map_) == 0) return;

    se::Octree<SE_FIELD_TYPE>& octree = tracker_->get_octree();
    const unsigned int octree_size = octree.size();
    const float octree_dim = octree.dim();
    const double voxel_dim = octree_dim / octree_size;
    const int block_side = octree.blockSide;

    const Eigen::Vector3f ov = octree.get_origin_position();
    geometry_msgs::msg::Point origin;
    origin.x = ov(0);
    origin.y = ov(1);
    origin.z = ov(2);

    // Allocate or expand the occupancy grid
    if (!grid_template_->data.size()) {

        nav_msgs::msg::OccupancyGrid &og = *grid_template_;
        og.info.resolution =  voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        uint64_t data_size = (uint64_t) og.info.width * (uint64_t) og.info.height;
        og.data.resize(data_size, fast_mapping::unknown_prob);
    }

    if (octree_size != grid_template_->info.width) {

        auto grid_template_new = std::make_shared<nav_msgs::msg::OccupancyGrid>();
        nav_msgs::msg::OccupancyGrid &og = *grid_template_new;
        og.info.resolution = voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        uint64_t data_size = (uint64_t) og.info.width * (uint64_t) og.info.height;
        og.data.resize(data_size, fast_mapping::unknown_prob);
        int dx = std::nearbyint((grid_template_->info.origin.position.x - og.info.origin.position.x) /
                                og.info.resolution);
        int dy = std::nearbyint((grid_template_->info.origin.position.y - og.info.origin.position.y) /
                                og.info.resolution);
        if (dx < 0 && dy < 0) {
            ROS_ERROR("Error: enlarged octree does not cover the old one");
            return;
        }
        for (unsigned int y = 0; y < grid_template_->info.height; ++y) {
            std::memcpy(&og.data[(y + dy) * og.info.width + dx],
                &grid_template_->data[y * grid_template_->info.width],
                grid_template_->info.width * sizeof(og.data[0]));
        }
        grid_template_ = grid_template_new;
    }

    nav_msgs::msg::OccupancyGrid og = *grid_template_;
    og.header.frame_id = std::string(p_map_frame_);
    og.header.stamp = rosx::now();

    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    tracker_->get_octree_block_list(blocks, false);

    // Iterate through the list of blocks and update occupied space.
    geometry_msgs::msg::Point center;
    for (const auto &block : blocks) {
        auto coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;
                if (vx < 0 || vy < 0) break;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;

                center.x = origin.x + (vx + 0.5) * voxel_dim;
                center.y = origin.y + (vy + 0.5) * voxel_dim;
                center.z = origin.z + (coords.z() + 0.5) * voxel_dim;

                int dataid = i + j * block->side;
                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    /*
                        temporarily extend the range for height check because during octree merge,
                        we use a larger range of (zmin, zmax) to accept input voxel, therefore,
                        here we need to align with the setting and manually extend the range
                    */
                    if (center.z >= (cfg_->zmax_ + 1.5 * block_side * voxel_dim) ||
                        center.z <= (cfg_->zmin_ - 1.5 * block_side * voxel_dim))
                        continue;

                    const size_t index = vy * og.info.width + vx;
                    if (index >= og.data.size()) break;

                    auto &ogdata = og.data[index];

                    const float prob = block->data(dataid).x;
                    if (prob > fast_mapping::unknown_upper) ogdata = fast_mapping::occupied_prob; // Occupied
                    /*
                        temporarily change the value of fast_mapping::unknown_lower to 0.0,
                        because after octree merge, we need to use newly created voxelblocks to indicate the
                        free space area, so we use the same threshold as the following LeafNode filter
                    */
                    else if (prob < fast_mapping::unknown_lower) {
                        // if unknown, mark as free space
                        if (ogdata == fast_mapping::unknown_prob) ogdata = fast_mapping::free_prob;
                    }
                }
            }
        }
    }

    // Iterate through the list of non-block leaf nodes that meet the data filter requirement
    // and update the free space of the occupancy map
    std::vector<se::LeafNode<SE_FIELD_TYPE>> nodes;
    auto filter = [](se::Node<SE_FIELD_TYPE>::value_type data)->bool { return data.x < 0; };
    octree.get_leaf_nodes(nodes, filter);

    for (const auto& node : nodes) {
        int side = node.side;
        if (side > MAX_NODE_SIZE) continue; // If node side is too coarse, skip it.

        for (int i = 0; i < side; i++) {
            for (int j = 0; j < side; j++) {
                int vx = node.coordinates(0) + i;
                int vy = node.coordinates(1) + j;
                if (vx < 0 || vy < 0) continue;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;
                const size_t index = vy * og.info.width + vx;
                if(index >= og.data.size()) break;
                auto &ogdata = og.data[index];
                // If unknown, mark as free space
                if (ogdata == fast_mapping::unknown_prob) ogdata = fast_mapping::free_prob;
            }
        }
    }
    pub_occupancy_map_->publish(og);
}

void TrackerNode::publish_volumetric_map()
{

    if (rosx::getNumSubscribers(pub_fused_map_) == 0) return;

    unsigned int current_octree_merged_times = tracker_->get_tracker_octree_merged_times();

    se::Octree<SE_FIELD_TYPE> &octree = tracker_->get_octree();
    const int block_side = octree.blockSide;
    const unsigned int octree_size = octree.size();
    const float octree_dim = octree.dim();
    const double voxel_dim = octree_dim / octree_size;

    auto set_marker_scale = [](visualization_msgs::msg::Marker &marker, double scale)
    {
        marker.scale.x = marker.scale.y = marker.scale.z = scale;
    };
    auto set_marker_color = [](visualization_msgs::msg::Marker &marker, float r, float g, float b, float a = 1.0)
    {
        marker.color.r = r; marker.color.g = g; marker.color.b = b; marker.color.a = a;
    };

    visualization_msgs::msg::Marker empty_marker;
    empty_marker.header.frame_id = std::string(p_map_frame_);
    empty_marker.header.stamp = rosx::now();
    empty_marker.type = visualization_msgs::msg::Marker::CUBE_LIST;
    empty_marker.action = visualization_msgs::msg::Marker::ADD;
    empty_marker.pose.orientation.w = 1.0;
    set_marker_scale(empty_marker, voxel_dim);
    set_marker_color(empty_marker, 1.0, 1.0, 1.0, 1.0); // white

    // Fused Markers
    visualization_msgs::msg::MarkerArray msg_fused;

    /*
        We use the "ns" field to identify whether the octree map merging has happened or not. Also, the "id" field is
        used to indicate how many times the map merging operation has happened for the current tracker. Because rviz
        will preserve data with old namespace and id, we decide to set the "action" filed to value "DELETE" to make
        the marker which represents pre-merge octree map disappear after map merging.

        The octree merge times won't exceed the maximum value of an unsigned int in real scenarios. The actuall value
        will be no more than tens.
    */
    msg_fused.markers.resize(current_octree_merged_times + 1, empty_marker);
    if (current_octree_merged_times > 0) {
        for (unsigned int index = 0; index < current_octree_merged_times; ++index) {
            msg_fused.markers[index + 1].id = index;
            msg_fused.markers[index + 1].ns = (index > 0) ? "octree_map_merged" : "octree_map_premerge";
            msg_fused.markers[index + 1].action = visualization_msgs::msg::Marker::DELETE;
        }
    }
    msg_fused.markers[0].id = current_octree_merged_times;
    msg_fused.markers[0].ns = (current_octree_merged_times > 0) ? "octree_map_merged" : "octree_map_premerge";

    auto fused_marker = msg_fused.markers.begin();

    // Iterate through the list of blocks
    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    tracker_->get_octree_block_list(blocks, false);

    const Eigen::Vector3f ov = octree.get_origin_position();
    geometry_msgs::msg::Point origin;
    origin.x = ov(0);
    origin.y = ov(1);
    origin.z = ov(2);

    geometry_msgs::msg::Point center;
    for (const auto& block : blocks) {
        Eigen::Vector3i coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;

                center.x = origin.x + (vx + 0.5) * voxel_dim;
                center.y = origin.y + (vy + 0.5) * voxel_dim;
                center.z = origin.z + (coords.z() + 0.5) * voxel_dim;
                int dataid = i + j * block->side;
                if (dataid >= static_cast<int>(block->side * block->sideSq)) break;

                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    se::Node<SE_FIELD_TYPE>::value_type data = block->data(dataid);
                    const float prob = data.x;
                    if (prob > fast_mapping::unknown_upper)
                    {
                        fused_marker->points.push_back(center);
                    }
                }
            }
        }
    }

    fast_mapping::add_color_to_marker_points(*fused_marker, "z", -1., 4.);
    pub_fused_map_->publish(msg_fused);
}

void TrackerNode::publish_imu_states()
{
    if (pub_imu_states_ && rosx::getNumSubscribers(pub_imu_states_) > 0) {
        univloc_msgs::ImuStatus msg;
        tracker_->get_imu_status(msg);
        pub_imu_states_->publish(msg);
    }
}

void TrackerNode::publish_lidar_states()
{
    if (pub_lidar_states_ && rosx::getNumSubscribers(pub_lidar_states_) > 0) {
        univloc_msgs::LidarStatus msg;
        tracker_->get_lidar_success_count(msg);
        pub_lidar_states_->publish(msg);
    }
}

sensor_msgs::CameraInfoPtr TrackerNode::get_camera_info_msg_from_topic(std::string camera_info_topic)
{
    camera_info_msg_.reset();
    // use a temporal subscriber to get the camera info
    rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::ConstSharedPtr subscription_;
    rclcpp::QoS qos(10);
    subscription_ = create_subscription<sensor_msgs::msg::CameraInfo>(
        camera_info_topic, qos, std::bind(&TrackerNode::camera_info_callback, this, std::placeholders::_1));
    std::shared_future<void> camera_info_ready_future(camera_info_ready_promise_.get_future());
    ROS_INFO("Waiting for camera info from %s", camera_info_topic.c_str());
    if (rclcpp::spin_until_future_complete(shared_from_this(), camera_info_ready_future)
        != rclcpp::FutureReturnCode::SUCCESS) {
        ROS_ERROR("Failed to get camera info");
    } else {
        camera_info_ready_promise_ = std::promise<void>();
        ROS_INFO("Get camera info from %s successfully", camera_info_topic.c_str());
    }
    return camera_info_msg_;
}

void TrackerNode::rgbd_callback(const sensor_msgs::ImageConstPtr msgRGB, const sensor_msgs::ImageConstPtr msgD)
{
    if (msgRGB->header.frame_id == "" || msgRGB->width == 0 || msgRGB->height == 0
        || msgD->header.frame_id == "" || msgD->width == 0 || msgD->height == 0) {
        ROS_WARN("Received invalid frame!");
        return;
    }

    if (msgRGB->width != (unsigned int)cfg_->width_ || msgRGB->height != (unsigned int)cfg_->height_) {
        ROS_WARN(
            "The resolution of the input RGB image is %d * %d! But expected resolution is %d * %d, skip this frame!",
            msgRGB->width, msgRGB->height, cfg_->width_, cfg_->height_);
        return;
    } else if (msgD->width != (unsigned int)cfg_->width_ || msgD->height != (unsigned int)cfg_->height_) {
        ROS_WARN(
            "The resolution of the input Depth image is %d * %d! But expected resolution is %d * %d, skip this frame!",
            msgD->width, msgD->height, cfg_->width_, cfg_->height_);
        return;
    }

    cv_bridge::CvImageConstPtr cv_ptrRGB;

    try {
        cv_ptrRGB = cv_bridge::toCvCopy(msgRGB);
    } catch (cv_bridge::Exception &e) {
        ROS_ERROR("cv_bridge exception: %s", e.what());
        return;
    }

    cv_bridge::CvImageConstPtr cv_ptrD;

    try {
        cv_ptrD = cv_bridge::toCvCopy(msgD);  //, sensor_msgs::image_encodings::TYPE_16UC1
    } catch (cv_bridge::Exception &e) {
        ROS_ERROR("cv_bridge exception: %s", e.what());
        return;
    }

    if (cfg_->use_odom_) {
        odom_pose(cv_ptrRGB->header.stamp);
    }

    stat_received_++;
    std::any cdata = msgRGB->header;
    double stamp = rosx::Time(msgRGB->header.stamp).seconds();
    std::shared_ptr<FrameData> frame = std::make_shared<FrameData>(cv_ptrRGB->image, cv_ptrD->image, stamp, cdata);
    tracker_->feed_image(frame);
}

void TrackerNode::stereo_callback(const sensor_msgs::ImageConstPtr msg_left,
                                  const sensor_msgs::ImageConstPtr msg_right)
{
    if (msg_left->header.frame_id == "" || msg_left->width == 0 || msg_left->height == 0
        || msg_right->header.frame_id == "" || msg_right->width == 0 || msg_right->height == 0) {
        ROS_WARN("Received invalid frame!");
        return;
    }

    if (msg_left->width != (unsigned int)cfg_->width_ || msg_left->height != (unsigned int)cfg_->height_) {
        ROS_WARN(
            "The resolution of the input stereo left image is %d * %d! But expected resolution is %d * %d, skip this "
            "frame!",
            msg_left->width, msg_left->height, cfg_->width_, cfg_->height_);
        return;
    } else if (msg_right->width != (unsigned int)cfg_->width_ || msg_right->height != (unsigned int)cfg_->height_) {
        ROS_WARN(
            "The resolution of the input stereo right image is %d * %d! But expected resolution is %d * %d, skip this "
            "frame!",
            msg_right->width, msg_right->height, cfg_->width_, cfg_->height_);
        return;
    }

    cv_bridge::CvImageConstPtr cv_ptr_l, cv_ptr_r;
    try {
        cv_ptr_l = cv_bridge::toCvCopy(msg_left);
        cv_ptr_r = cv_bridge::toCvCopy(msg_right);
    } catch (cv_bridge::Exception &e) {
        ROS_ERROR("cv_bridge exception: %s", e.what());
        return;
    }

    if (cfg_->use_odom_) {
        odom_pose(cv_ptr_l->header.stamp);
    }

    stat_received_++;
    std::any cdata = msg_left->header;
    double stamp = rosx::Time(msg_left->header.stamp).seconds();
    std::shared_ptr<FrameData> frame = std::make_shared<FrameData>(cv_ptr_l->image, cv_ptr_r->image, stamp, cdata);
    tracker_->feed_image(frame);
}

void TrackerNode::monocular_callback(const sensor_msgs::ImageConstPtr msgRGB)
{
    if (msgRGB->header.frame_id == "" || msgRGB->width == 0 || msgRGB->height == 0) {
        ROS_WARN("Received invalid frame!");
        return;
    }

    if (msgRGB->width != (unsigned int)cfg_->width_ || msgRGB->height != (unsigned int)cfg_->height_) {
        ROS_WARN(
            "The resolution of the input image is %d * %d! But expected resolution is %d * %d, skip this "
            "frame!",
            msgRGB->width, msgRGB->height, cfg_->width_, cfg_->height_);
        return;
    }

    cv_bridge::CvImageConstPtr cv_ptrRGB;
    try {
        cv_ptrRGB = cv_bridge::toCvCopy(msgRGB);
    } catch (cv_bridge::Exception &e) {
        ROS_ERROR("cv_bridge exception: %s", e.what());
        return;
    }

    if (cfg_->use_odom_) {
        odom_pose(cv_ptrRGB->header.stamp);
    }

    stat_received_++;
    std::any cdata = msgRGB->header;
    double stamp = rosx::Time(msgRGB->header.stamp).seconds();
    std::shared_ptr<FrameData> frame = std::make_shared<FrameData>(cv_ptrRGB->image, stamp, cdata);
    tracker_->feed_image(frame);
}

 void TrackerNode::lidar_callback(const sensor_msgs::msg::LaserScan::ConstSharedPtr laser_scan)
 {
    if (laser_scan->header.frame_id == "") {
        ROS_WARN("Received invalid laser scan!");
        return;
    }

    std::any cdata = laser_scan->header;
    double stamp = rosx::Time(laser_scan->header.stamp).seconds();
    // convert ranges to 2d cartesian coordinate
    std::vector<cv::Point2d> points;
    for(unsigned int i = 0; i < laser_scan->ranges.size(); i++){
        float th = laser_scan->range_min + (i * laser_scan->angle_increment);
        float x = laser_scan->ranges[i] * sin(th);
        float y = laser_scan->ranges[i] * cos(th);
        points.push_back({x, y});
    }

    std::shared_ptr<LidarData> frame = std::make_shared<LidarData>(laser_scan->angle_min,
                                                                   laser_scan->angle_max,
                                                                   laser_scan->angle_increment,
                                                                   laser_scan->time_increment,
                                                                   laser_scan->scan_time,
                                                                   laser_scan->range_min,
                                                                   laser_scan->range_max,
                                                                   laser_scan->ranges,
                                                                   laser_scan->intensities,
                                                                   points,
                                                                   stamp);
    tracker_->feed_lidar(frame);
 }

void TrackerNode::accgyr_callback(const sensor_msgs::ImuConstPtr acc_msg, const sensor_msgs::ImuConstPtr gyr_msg)
{
    if (acc_msg->header.frame_id == "" || gyr_msg->header.frame_id == "")
        return;

    double t_acc = rosx::Time(acc_msg->header.stamp).seconds();
    double t_gyr = rosx::Time(gyr_msg->header.stamp).seconds();
    double t = (t_acc < t_gyr) ? t_acc : t_gyr;
    if (t < EPSILON)
        ROS_ERROR("timestamp of IMU data should not equal to 0!");
    double ax = acc_msg->linear_acceleration.x * p_accel_measurement_scale_;
    double ay = acc_msg->linear_acceleration.y * p_accel_measurement_scale_;
    double az = acc_msg->linear_acceleration.z * p_accel_measurement_scale_;
    double gx = gyr_msg->angular_velocity.x;
    double gy = gyr_msg->angular_velocity.y;
    double gz = gyr_msg->angular_velocity.z;
    Eigen::Vector3d acc(ax, ay, az);
    Eigen::Vector3d gyr(gx, gy, gz);
    tracker_->feed_imu_data(t, acc, gyr);
}

void TrackerNode::imu_callback(const sensor_msgs::ImuConstPtr imu_msg)
{
    if (imu_msg->header.frame_id == "")
        return;

    double t = rosx::Time(imu_msg->header.stamp).seconds();
    if (t < EPSILON)
        ROS_ERROR("timestamp of IMU data should not equal to 0!");
    double ax = imu_msg->linear_acceleration.x * p_accel_measurement_scale_;
    double ay = imu_msg->linear_acceleration.y * p_accel_measurement_scale_;
    double az = imu_msg->linear_acceleration.z * p_accel_measurement_scale_;
    double gx = imu_msg->angular_velocity.x;
    double gy = imu_msg->angular_velocity.y;
    double gz = imu_msg->angular_velocity.z;
    Eigen::Vector3d acc(ax, ay, az);
    Eigen::Vector3d gyr(gx, gy, gz);
    tracker_->feed_imu_data(t, acc, gyr);
}

void TrackerNode::main_loop()
{
    int lost_frames = 0;
    bool initialized = false;
    if (p_stat_log_interval_ > 0) {
        check_timer_ = rclcpp::create_timer(this, this->get_clock(), tf2::durationFromSec(p_stat_log_interval_),
                                            std::bind(&TrackerNode::periodically_print_stats, this));
    }

    std::shared_ptr<FrameData> result;
    std::optional<Eigen::Matrix4d> last_maybe_Tcw = std::nullopt;
    std::optional<Eigen::Matrix<double, 6, 6>> maybe_covariance = std::nullopt;
    std_msgs::Header header;
    while (rosx::ok()) {
        result = tracker_->get_result();
        if (!result) break;
        stat_processed_++;

        std::optional<Eigen::Matrix4d> maybe_Tcw = result->maybe_pose;
        if (cfg_->need_covariance_) maybe_covariance = result->maybe_covariance;
        header = std::any_cast<std_msgs::Header>(result->cdata);

        if (!maybe_Tcw) {
            // accumulate lost frames only if initialization has been succeeded
            // (to avoid consecutive resetting)
            if (initialized && num_lost_frames_to_reset_ > 0 && ++lost_frames >= num_lost_frames_to_reset_) {
                ROS_WARN("Tracking lost for %d frames. Will reset and start with a new map.", lost_frames);
                tracker_->request_reset();
                initialized = false;
                lost_frames = 0;
            }

            // continue to publish the previous map -> odom TF when tracking lost
            if (tracker_->tracking_module_is_lost() && last_maybe_Tcw) {
                // Use current time to publish pose, optimized_path and TF transform
                publish_pose(*last_maybe_Tcw, header, *maybe_covariance, true);
                ROS_DEBUG("Use the last successfully tracking pose to publish map -> odom TF.");
            }
            continue;
        }

        stat_localized_++;
        // update the pose of last successfully tracking
        last_maybe_Tcw = maybe_Tcw;
        publish_imu_states();
        if (use_lidar_) publish_lidar_states();

        initialized = true;
        lost_frames = 0;
        publish_pose(*maybe_Tcw, header, *maybe_covariance);
        publish_local_landmarks();
        publish_tracked_server_landmarks();
        publish_imu_estimated_trajectory();
        publish_local_map(*maybe_Tcw);

        if (cfg_->enable_fast_mapping_) {
            publish_volumetric_map();
            publish_occupancy_map();
        }

        if (traj_store_path_ != "")
            save_trajectory_to_file((*maybe_Tcw).inverse(), header.stamp);
    }
}

void TrackerNode::publish_tracked_server_landmarks()
{
    if (rosx::getNumSubscribers(pub_server_landmarks_observation_) == 0) return;
    std::vector<Eigen::Vector3d> tracked_server_landmarks;
    tracker_->get_tracked_server_landmarks(tracked_server_landmarks);

    visualization_msgs::Marker observation_lines;
    observation_lines.type = visualization_msgs::Marker::LINE_LIST;
    observation_lines.color.g = 1.0;
    observation_lines.color.a = 1.0;
    observation_lines.scale.x = 0.02;
    observation_lines.header.frame_id = p_map_frame_;
    observation_lines.header.stamp = rosx::now();
    if (tracked_server_landmarks.size() > 2) {
        geometry_msgs::Point camera_center, pos_landmark;
        int landmark_size = tracked_server_landmarks.size() - 1;
        camera_center.x = tracked_server_landmarks.back()[0];
        camera_center.y = tracked_server_landmarks.back()[1];
        camera_center.z = tracked_server_landmarks.back()[2];

        for (int i = 0; i < landmark_size; i++) {
            pos_landmark.x = tracked_server_landmarks[i][0];
            pos_landmark.y = tracked_server_landmarks[i][1];
            pos_landmark.z = tracked_server_landmarks[i][2];
            observation_lines.points.push_back(camera_center);
            observation_lines.points.push_back(pos_landmark);
        }
    }
    pub_server_landmarks_observation_->publish(observation_lines);
    ROS_DEBUG("Pub %ld tracked server landmarks for observation!", tracked_server_landmarks.size());
}

void TrackerNode::publish_pose(const Eigen::Matrix4d &Tcw, const std_msgs::Header &image_header,
                               const Eigen::Matrix<double, 6, 6> &covariance, bool skip_query_transform)
{
    // Publish 3D pose
    // x right, y down, z forward
    Eigen::Matrix4d T_wc = Tcw.inverse();

    Eigen::Matrix<double, 3, 3> eigm(T_wc.block(0, 0, 3, 3));
    // For rviz, the arrows will point in the X direction of each Pose
    // Since we uses the transformation between image_frame and base_link to represent pose
    // the X direction of pose is within the image plane rather than heading the movement direction.
    // Thus we need to transform from T_wi to T_wc to let the X direction point to the movement direction
    // Here we take tf_base_camera_ as the transformation between image_frame and camera_link
    // since there is no rotation between camera_link and world (base_link) plane
    // NOTE: disabled right due to issue it produces to actual pose
    // eigm = eigm * cfg_->tf_base_camera_.inverse().block(0, 0, 3, 3);
    Eigen::Quaterniond eigq(eigm);
    eigq.normalize();

    geometry_msgs::PoseStamped msg;
    msg.header.frame_id = p_map_frame_;
    msg.header.stamp = image_header.stamp;
    msg.pose.position.x = T_wc(0, 3);
    msg.pose.position.y = T_wc(1, 3);
    msg.pose.position.z = T_wc(2, 3);
    msg.pose.orientation.x = eigq.x();
    msg.pose.orientation.y = eigq.y();
    msg.pose.orientation.z = eigq.z();
    msg.pose.orientation.w = eigq.w();
    pub_pose_->publish(msg);

    // Publish path
    optimized_path_.header = msg.header;
    optimized_path_.poses.push_back(msg);
    pub_optimized_path_->publish(optimized_path_);

    if (cfg_->need_covariance_ && tracker_->is_coordinate_aligned()) {
        // Publish map -> base_link transform for Kalman Filter as the pose input
        Eigen::Matrix4d T_wb = T_wc * cfg_->tf_base_camera_.inverse();
        Eigen::Matrix<double, 3, 3> eigm_new(T_wb.block(0, 0, 3, 3));
        Eigen::Quaterniond eigq_new(eigm_new);
        eigq_new.normalize();

        geometry_msgs::PoseWithCovarianceStamped msg_new;
        msg_new.header.frame_id = p_map_frame_;
        msg_new.header.stamp = image_header.stamp;
        msg_new.pose.pose.position.x = T_wb(0, 3);
        msg_new.pose.pose.position.y = T_wb(1, 3);
        msg_new.pose.pose.position.z = T_wb(2, 3);
        msg_new.pose.pose.orientation.x = eigq_new.x();
        msg_new.pose.pose.orientation.y = eigq_new.y();
        msg_new.pose.pose.orientation.z = eigq_new.z();
        msg_new.pose.pose.orientation.w = eigq_new.w();
        memcpy(&msg_new.pose.covariance, covariance.data(), covariance.size() * sizeof(double));
        pub_kf_pose_->publish(msg_new);
    }

    if (publish_tf_) {
        // Publish tf
        tf2::Transform T_world_image;
        tf2::Stamped<tf2::Transform> T_parent_world, T_child_image;
        tf2::fromMsg(msg.pose, T_world_image);

        std::string image_frame = cfg_->image_frame_ == "" ? image_header.frame_id : cfg_->image_frame_;
        std::string parent_frame = p_parent_frame_.empty() ? p_map_frame_ : p_parent_frame_;
        std::string child_frame = p_child_frame_.empty() ? image_frame : p_child_frame_;

        if (skip_query_transform) {
            ROS_DEBUG("Skip query transform in tf buffer on timestamp %f, use last transform to publish tf.",
                      rosx::Time(msg.header.stamp).toSec());
            publish_transform(last_T_parent_child_, msg.header.stamp, parent_frame, child_frame);
            return;
        }

        bool get_tf_succeed = true;
        if (p_parent_frame_.empty()) {
            T_parent_world.setIdentity();
        } else {
            get_tf_succeed &= get_transform(T_parent_world, parent_frame, p_map_frame_, msg.header.stamp);
        }
        if (p_child_frame_.empty()) {
            T_child_image.setIdentity();
        } else {
            get_tf_succeed &= get_transform(T_child_image, child_frame, image_frame, msg.header.stamp);
        }
        if (get_tf_succeed) {
            tf2::Transform T_parent_child(T_parent_world * T_world_image * T_child_image.inverse());
            publish_transform(T_parent_child, msg.header.stamp, parent_frame, child_frame);
            last_T_parent_child_ = T_parent_child;
        }
    }
}

void TrackerNode::publish_local_landmarks()
{
    if (rosx::getNumSubscribers(pub_pc_) == 0) return;

    std::vector<Eigen::Vector3d> local_landmarks;
    tracker_->get_landmarks(local_landmarks);

    sensor_msgs::PointCloud local_pc;
    auto client_id = tracker_->get_client_id();
    uint32_t color_32t = static_cast<uint32_t>(10 * (client_id + 1)) << 16 |
                         static_cast<uint32_t>(15 * (client_id + 2)) << 8 |
                         static_cast<uint32_t>(20 * (client_id + 3));
    float color = (float)color_32t;
    size_t num = local_landmarks.size();
    local_pc.points.resize(num);
    local_pc.header.frame_id = p_map_frame_;
    local_pc.header.stamp = rosx::now();
    local_pc.channels.resize(1);
    local_pc.channels[0].name = "rgb";
    local_pc.channels[0].values.assign(num, color);

    for (size_t i = 0; i < num; i++) {
        auto position = local_landmarks[i];
        local_pc.points[i].x = position[0];
        local_pc.points[i].y = position[1];
        local_pc.points[i].z = position[2];
    }
    pub_pc_->publish(local_pc);
}

void TrackerNode::publish_imu_estimated_trajectory()
{
    if (rosx::getNumSubscribers(pub_imu_estimated_path_) == 0) return;

    std::vector<Eigen::Matrix4d> poses;
    tracker_->get_imu_estimated_poses(poses);

    nav_msgs::Path imu_estimated_trajectory;
    for (auto &pose : poses) {
        Eigen::Matrix<double, 3, 3> eigm(pose.block(0, 0, 3, 3));
        Eigen::Quaterniond eigq(eigm);
        eigq.normalize();
        geometry_msgs::PoseStamped msg;
        msg.header.frame_id = p_map_frame_;
        msg.header.stamp = rosx::now();
        msg.pose.position.x = pose(0, 3);
        msg.pose.position.y = pose(1, 3);
        msg.pose.position.z = pose(2, 3);
        msg.pose.orientation.x = eigq.x();
        msg.pose.orientation.y = eigq.y();
        msg.pose.orientation.z = eigq.z();
        msg.pose.orientation.w = eigq.w();
        imu_estimated_trajectory.header = msg.header;
        imu_estimated_trajectory.poses.push_back(msg);
    }
    pub_imu_estimated_path_->publish(imu_estimated_trajectory);
}

void TrackerNode::periodically_print_stats()
{
    static rosx::Time last_stat_time = rosx::Time(0);
    if (last_stat_time == rosx::Time(0)) {
        last_stat_time = rosx::now();
        return;
    }
    rosx::Time tnow = rosx::now();
    rosx::Duration dur = tnow - last_stat_time;
    last_stat_time = tnow;

    unsigned int nreceived = stat_received_.exchange(0);
    unsigned int nprocessed = stat_processed_.exchange(0);
    unsigned int nlocalized = stat_localized_.exchange(0);
    stat_total_processed_ += nprocessed;
    stat_total_localized_ += nlocalized;
    size_t queue_size = tracker_->how_many_frames_left();

    ROS_INFO("UnivLoc%s got %d images in past %.1fs. Localized/processed %d/%d (%.2lf Hz). Totally %d/%d (%.2f%%).%s",
             tracker_->connected_to_server() ? " (connected)" : " (unconnected)",
             nreceived,
             dur.toSec(),
             nlocalized,
             nprocessed,
             nprocessed / dur.toSec(),
             stat_total_localized_,
             stat_total_processed_,
             (stat_total_localized_ != 0) ? 100.f * stat_total_localized_ / stat_total_processed_ : 0,
             queue_size > 1 ? (" " + std::to_string(queue_size) + " left in queue.").c_str() : "");
}

void TrackerNode::save_trajectory_to_file(const Eigen::Matrix4d pose, rosx::Time time_stamp) const
{
    static std::ofstream of_write(traj_store_path_);
    Eigen::Matrix3d R = pose.block(0, 0, 3, 3);
    Eigen::Quaterniond q(R);
    of_write << std::fixed << time_stamp.toSec()
                           << " " << pose(0, 3) << " " << pose(1, 3) << " " << pose(2, 3)
                           << " " << q.x() << " " << q.y() << " " << q.z() << " " << q.w()
                           << std::endl;
}

void TrackerNode::odom_pose(rosx::Time stamp)
{
    if (cfg_->image_frame_ == "") {
        ROS_DEBUG("Image frame not found, skip odom pose transform!");
        return;
    }

    Eigen::Matrix4d odom_to_camera_pose;
    rosx::Duration timeout(cfg_->odom_tf_query_timeout_ * MILLISEC_TO_SEC);

    rosx::TfLookupResult ret = get_tf_matrix(odom_to_camera_pose, cfg_->image_frame_, cfg_->odom_frame_, stamp,
                                            timeout);
    if (ret) {
        ROS_DEBUG("Found aligned odom pose, timestamp is %f", stamp.toSec());
        tracker_->feed_odom_data(stamp.toSec(), odom_to_camera_pose);
    } else {
        ROS_INFO("Drop odom pose transform for frame of timestamp %f: %s", stamp.toSec(), ret.error().c_str());
    }
}

rosx::TfLookupResult TrackerNode::get_tf_matrix(Eigen::Matrix4d &pose, std::string target, std::string source,
                                                rosx::Time stamp, rosx::Duration timeout)
{
    tf2::Stamped<tf2::Transform> transform;
    rosx::Time s_stamp = stamp - timeout;
    // TF lookup time duration: | (stamp-timeout) ------ (stamp) ------ (stamp+timeout) |
    // Apply 10% timeline overlap since TF itself needs some time cost
    rosx::TfLookupResult ret = get_transform(transform, target, source, stamp, timeout);
    if (!ret && cfg_->tf_fix_frame_ != "") {
        ret = get_transform(transform, target, stamp, source, s_stamp, cfg_->tf_fix_frame_, timeout * 1.1);
    }
    if (ret) {
        auto rot = transform.getBasis();
        auto trans = transform.getOrigin();
        pose << rot[0].x(), rot[0].y(), rot[0].z(), trans.x(),
                rot[1].x(), rot[1].y(), rot[1].z(), trans.y(),
                rot[2].x(), rot[2].y(), rot[2].z(), trans.z(),
                0.0, 0.0, 0.0, 1.0;
    }
    return ret;
}

uint32_t TrackerNode::getReceivedFramesCount() const {
    return this->stat_received_;
}
