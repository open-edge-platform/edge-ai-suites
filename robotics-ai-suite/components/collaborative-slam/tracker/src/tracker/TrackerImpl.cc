// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <cstdlib>
#include "TrackerImpl.h"
#include "rclcpp/rclcpp.hpp"
#include "camera/fisheye.h"
#include "camera/perspective.h"
#include "data/bow_database.h"
#include "data/camera_database.h"
#include "data/imu.h"
#include "data/odom.h"
#include "data/map_database.h"
#include "io/map_database_io.h"
#include "io/trajectory_io.h"
#include "util/image_converter.h"
#include "util/stereo_rectifier.h"
#include "fast_mapping_helper.h"

#include <opencv2/calib3d/calib3d.hpp>
#include <opencv2/calib3d/calib3d_c.h>
#include <spdlog/spdlog.h>
#if defined(SPDLOG_VERSION) && (SPDLOG_VERSION >= 10600)
#include <spdlog/cfg/env.h>  // exist in spdlog v1.6+
#define SPDLOG_SUPPORT_ENV
#endif

#include <thread>
bool is_server_node;

namespace univloc_tracker {

TrackerImpl::TrackerImpl(std::shared_ptr<Config> cfg, std::shared_ptr<rclcpp::Node> node_ptr)
    : cfg_(cfg),
      // The request queue has a user-specified capacity to allow trade-off between frame drop and latency
      request_queue_(cfg->queue_capacity_),
      // The request queue has a user-specified capacity to allow trade-off between frame drop and latency
      request_lidar_queue_(cfg->queue_lidar_capacity_),
      // The feature queue has a limited capacity to avoid extracting too many features for the tracking module to process
      feature_queue_(1),
      // The result queue has an unlimited capacity to give users result for every processed frame
      result_queue_(0),
      // The reconstruction queue has limited capacity to avoid old poses being integrated into the octree
      reconstruction_queue_(1)
{
#ifdef SPDLOG_SUPPORT_ENV
    is_server_node = false;
    spdlog::cfg::load_env_levels();
#else
    char *loglevel = getenv("SPDLOG_LEVEL");
    if (loglevel)
        spdlog::set_level(spdlog::level::from_str(loglevel));
#endif
    // show configuration
    std::cout << *cfg_ << std::endl;

    // load ORB vocabulary
    spdlog::info("loading ORB vocabulary: {}", cfg_->vocabulary_path_);
#ifdef USE_DBOW2
    bow_vocab_ = new data::bow_vocabulary();
    try {
        bow_vocab_->loadFromBinaryFile(cfg_->vocabulary_path_);
    } catch (const std::string& e) {
        spdlog::critical("wrong path to vocabulary");
        delete bow_vocab_;
        bow_vocab_ = nullptr;
        exit(EXIT_FAILURE);
    }
#else
    bow_vocab_ = new fbow::Vocabulary();
    bow_vocab_->readFromFile(cfg_->vocabulary_path_);
    if (!bow_vocab_->isValid()) {
        spdlog::critical("wrong path to vocabulary");
        delete bow_vocab_;
        bow_vocab_ = nullptr;
        exit(EXIT_FAILURE);
    }
#endif

    // camera
    setup_camera();

    if (cfg_->is_stereo() && cfg_->enable_rectifier_) {
        setup_rectifier();
    }

    // database
    cam_db_ = new data::camera_database(camera_);
    if (!cam_db_)
        throw std::runtime_error("Failed to create camera database!");
    bow_db_ = new data::bow_database(bow_vocab_);
    if (!bow_db_)
        throw std::runtime_error("Failed to create bow database!");
    map_db_ = new data::map_database();
    if (!map_db_)
        throw std::runtime_error("Failed to create map database!");

    // feature extraction module
    if (cfg_->lidar_enable_){
        feature_extraction_module_ = new feature_extraction_module(cfg_, camera_, bow_vocab_, request_queue_,
                                         &request_lidar_queue_, feature_queue_, rectifier_);
    } else {
        feature_extraction_module_ = new feature_extraction_module(cfg_, camera_, bow_vocab_, request_queue_,
                                         feature_queue_, rectifier_);
    }
    // tracking module
    tracker_ = new univloc_tracking_module(cfg_, camera_, cfg_->client_id_, map_db_, bow_db_, feature_queue_,
                                           result_queue_, reconstruction_queue_);
    // mapping module
    mapper_ = new univloc_mapping_module(map_db_, bow_db_, cfg_->is_monocular(), cfg_->use_odom_,
                                         cfg->clean_keyframe_);
    // fast mapping module
    if (cfg_->enable_fast_mapping_) {
        fast_mapping_module_ = new fast_mapping_module(cfg_, reconstruction_queue_);
    }
    // client module
    univloc_tracker::Client::get_instance().initialize(cfg_, map_db_, camera_, bow_vocab_, bow_db_, node_ptr);

    // load pre-constructed octree map in localization and remapping modes if needed
    auto is_able_to_open = [](std::string path) -> bool {
        std::ifstream ifs(path, std::ios::in | std::ios::binary);
        if (!ifs.is_open()) return false;
        return true;
    };
    bool is_able_to_load_octree_map = false;
    struct fast_mapping::se_cfg loaded_octree_cfg;
    struct fast_mapping::camera_intrinsics loaded_intrinsics;
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> loaded_octree;
    if (cfg_->mode_ == "localization" && !cfg_->octree_load_path_.empty()) {
        if (is_able_to_open(cfg_->octree_load_path_)) {
            spdlog::info("Loading octree map from file " + cfg_->octree_load_path_ + "...............");
            fast_mapping::load_octree_map(cfg_->octree_load_path_, loaded_intrinsics, loaded_octree_cfg, loaded_octree);
            is_able_to_load_octree_map = true;
        } else {
            spdlog::info("Failed to load octree map from file " + cfg_->octree_load_path_);
        }
    } else if (cfg_->mode_ == "remapping") {
        if (cfg_->octree_load_path_.empty() || !is_able_to_open(cfg_->octree_load_path_)) {
            throw std::runtime_error("Failed to load octree map from file " + cfg_->octree_load_path_);
        } else {
            spdlog::info("Loading octree map from file " + cfg_->octree_load_path_ + "...............");
            fast_mapping::load_octree_map(cfg_->octree_load_path_, loaded_intrinsics, loaded_octree_cfg, loaded_octree);
            is_able_to_load_octree_map = true;
        }
    }

    // connect modules with each other 
    tracker_->set_mapping_module(mapper_);
    feature_extraction_module_->set_tracking_module(tracker_);
    mapper_->set_tracking_module(tracker_);
    univloc_tracker::Client::get_instance().set_tracking_module(tracker_);
    univloc_tracker::Client::get_instance().set_mapping_module(mapper_);
    if (cfg_->enable_fast_mapping_)
        univloc_tracker::Client::get_instance().set_fast_mapping_module(fast_mapping_module_);

    /*
        several pre-proccesing before execute start() function
    */
    if (is_able_to_load_octree_map) {
        loaded_octree_map_to_msg(loaded_octree_cfg, loaded_intrinsics, loaded_octree);
    }

    if (cfg_->mode_ == "remapping") {
        if (!cfg_->enable_fast_mapping_)
            throw std::runtime_error("Fast mapping module must be enabled in remapping mode!");

        if (cfg_->enable_remapping_region_)
            fast_mapping_module_->construct_remapping_region(cfg_->remapping_region_vertexes_);
    }

    // use odometry data in tracker
    if (cfg_->use_odom_) {
        odom_data_ = std::make_shared<data::odom>(cfg_->T_image_to_camera_);
        tracker_->set_odom_data(odom_data_);
        mapper_->set_odom_data(odom_data_);
    }

    // initialize IMU Intrinsic!
    if (cfg_->enable_imu()) {
        data::IMU_Preintegration::initialize(cfg_);
        imu_data_ = std::make_shared<data::IMU_data>();
        tracker_->set_imu_data(imu_data_);
    }
    traj_store_path_ = cfg_->traj_store_path_;
}

TrackerImpl::~TrackerImpl()
{
    shutdown();

    delete feature_extraction_module_;
    delete mapper_;
    if (cfg_->enable_fast_mapping_) {
        delete fast_mapping_module_;
    }
    delete tracker_;

    delete bow_db_;
    delete map_db_;
    delete cam_db_;
    delete bow_vocab_;

    spdlog::debug("DESTRUCT: system");
}

void TrackerImpl::setup_camera()
{
    double focal_x_baseline =
        (cfg_->focal_x_baseline_ != 0) ? cfg_->focal_x_baseline_ : (cfg_->fx_ * cfg_->camera_baseline_);
    const auto camera_model_type = camera::base::load_model_type(cfg_->model_type_str_);
    try {
        switch (camera_model_type) {
            case camera::model_type_t::Perspective: {
                camera_ = new camera::perspective(
                    cfg_->camera_name_, camera::base::load_setup_type(cfg_->setup_type_str_),
                    camera::base::load_color_order(cfg_->color_order_str_), cfg_->width_, cfg_->height_,
                    cfg_->camera_fps_, cfg_->fx_, cfg_->fy_, cfg_->cx_, cfg_->cy_, cfg_->dist_params_[0],
                    cfg_->dist_params_[1], cfg_->dist_params_[2], cfg_->dist_params_[3], cfg_->dist_params_[4],
                    focal_x_baseline);
                break;
            }
            case camera::model_type_t::Fisheye: {
                camera_ =
                    new camera::fisheye(cfg_->camera_name_, camera::base::load_setup_type(cfg_->setup_type_str_),
                                        camera::base::load_color_order(cfg_->color_order_str_), cfg_->width_,
                                        cfg_->height_, cfg_->camera_fps_, cfg_->fx_, cfg_->fy_, cfg_->cx_, cfg_->cy_,
                                        cfg_->dist_params_[0], cfg_->dist_params_[1], cfg_->dist_params_[2],
                                        cfg_->dist_params_[3], focal_x_baseline);
                break;
            }
            case camera::model_type_t::Equirectangular: {
                throw std::invalid_argument("Equirectangular camera not yet supported");
                break;
            }
        }
    } catch (const std::exception& e) {
        spdlog::debug("failed in loading camera model parameters: {}", e.what());
        if (camera_) {
            delete camera_;
            camera_ = nullptr;
        }
        throw;
    }
}

void TrackerImpl::setup_rectifier()
{
    if (cfg_->rectifier_params_given_) {
        rectifier_ = std::make_shared<openvslam::util::stereo_rectifier>(
            camera_, cfg_->K_left_, cfg_->D_left_, cfg_->R_left_, cfg_->K_right_, cfg_->D_right_, cfg_->R_right_);
        return;
    }

    /*
        For public datasets, the recitifier params are given, therefore no need to do extra work here.
        However, for self-recorded datasets, typically we need to obtain the recitifier params on our own.
        Below code tries to obtain the params but currently the performance is not guaranteed. Will need
        further investigation to verify.
    */
    cfg_->K1.at<double>(0, 2) = cfg_->width_ * 0.5;
    cfg_->K1.at<double>(1, 2) = cfg_->height_ * 0.5;
    cfg_->K2.at<double>(0, 2) = cfg_->width_ * 0.5;
    cfg_->K2.at<double>(1, 2) = cfg_->height_ * 0.5;

    Eigen::Matrix3d R = cfg_->tf_left_right_.topLeftCorner<3, 3>();
    cv::Mat matR =
        (cv::Mat_<double>(3, 3) << R(0, 0), R(0, 1), R(0, 2), R(1, 0), R(1, 1), R(1, 2), R(2, 0), R(2, 1), R(2, 2));
    cv::Mat matt =
        (cv::Mat_<double>(3, 1) << cfg_->tf_left_right_(0, 3), cfg_->tf_left_right_(1, 3), cfg_->tf_left_right_(2, 3));
    // TODO remove cout logs
    std::cout << "left_to_right_camera \n R: " << matR << "\n t:" << matt << std::endl;
    spdlog::info("Start stereoRectify!");
    cv::Mat R1, R2, P1, P2, Q;
    cv::Size image_size(cfg_->width_, cfg_->height_), new_size(cfg_->width_, cfg_->height_);
    std::cout << "K1 \n" << cfg_->K1 << "\n";
    std::cout << "K2 \n" << cfg_->K2 << "\n";
    std::cout << "mD1 \n" << cfg_->D1 << "\n";
    std::cout << "mD2 \n" << cfg_->D2 << "\n";
    std::cout << "matR \n" << matR << "\n";
    std::cout << "matt \n" << matt << "\n";
    std::cout << "image_size \n" << image_size << "\n";

    const auto camera_model_type = camera::base::load_model_type(cfg_->model_type_str_);
    if (camera_model_type == camera::model_type_t::Perspective)
        cv::fisheye::stereoRectify(cfg_->K1, cfg_->D1, cfg_->K2, cfg_->D2, image_size, matR, matt, R1, R2, P1, P2, Q,
                                   CV_CALIB_ZERO_DISPARITY, image_size);
    else if (camera_model_type == camera::model_type_t::Fisheye)
        cv::stereoRectify(cfg_->K1, cfg_->D1, cfg_->K2, cfg_->D2, image_size, matR, matt, R1, R2, P1, P2, Q,
                          CV_CALIB_ZERO_DISPARITY, -1, image_size);
    else
        spdlog::error("Equirectangular camera not yet supported, or wrong input camera model type!");
    std::cout << "P1 \n" << P1 << "\n";
    std::cout << "P2 \n" << P2 << "\n";
    std::cout << "R1 \n" << R1 << "\n";
    std::cout << "R2 \n" << R2 << "\n";
    std::cout << "Q \n" << Q << "\n";
    std::cout << "new_size \n" << new_size << "\n";

    double rectifitated_fx = P1.at<double>(0, 0), rectifitated_fy = P1.at<double>(1, 1),
           rectifitated_cx = P1.at<double>(0, 2), rectifitated_cy = P1.at<double>(1, 2);
    double focal_x_baseline = P2.at<double>(0, 3);
    cfg_->fx_ = rectifitated_fx;
    cfg_->fy_ = rectifitated_fy;
    cfg_->cx_ = rectifitated_cx;
    cfg_->cy_ = rectifitated_cy;
    cfg_->camera_baseline_ = focal_x_baseline / rectifitated_fx;
    cfg_->focal_x_baseline_ = focal_x_baseline;
    for (auto& v : cfg_->dist_params_) v = 0.0;

    // update params in camera db
    camera_->set_cv_cam_matrix(cfg_->fx_, cfg_->fy_, cfg_->cx_, cfg_->cy_);
    camera_->focal_x_baseline_ = focal_x_baseline;
    // true_baseline_ is initialized using focal_x_baseline divided by fx during base ctor
    camera_->true_baseline_ = cfg_->camera_baseline_;

    rectifier_ = std::make_shared<openvslam::util::stereo_rectifier>(camera_, cfg_->K1, cfg_->D1, R1, cfg_->K2,
                                                                     cfg_->D2, R2);
}

void TrackerImpl::loaded_octree_map_to_msg(struct fast_mapping::se_cfg& octree_cfg,
                                           struct fast_mapping::camera_intrinsics& intrinsics,
                                           std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree)
{
    univloc_tracker::Client::get_instance().octree_param_msg_ = std::make_shared<univloc_msgs::OctreeParam>();
    univloc_msgs::OctreeParamPtr octree_param_msg;
    octree_param_msg = univloc_tracker::Client::get_instance().octree_param_msg_;

    // camera intrinsics for Octree usage
    octree_param_msg->width = intrinsics.width;
    octree_param_msg->height = intrinsics.height;
    octree_param_msg->cx = intrinsics.cx;
    octree_param_msg->cy = intrinsics.cy;
    octree_param_msg->fx = intrinsics.fx;
    octree_param_msg->fy = intrinsics.fy;

    // Octree configuration
    octree_param_msg->compute_size_ratio = octree_cfg.compute_size_ratio;
    octree_param_msg->voxel_per_side = octree_cfg.voxel_per_side;
    octree_param_msg->volume_size_meter = octree_cfg.volume_size_meter;
    octree_param_msg->noise_factor = octree_cfg.noise_factor;
    octree_param_msg->logodds_lower = octree_cfg.logodds_lower;
    octree_param_msg->logodds_upper = octree_cfg.logodds_upper;
    octree_param_msg->zmin = octree_cfg.zmin;
    octree_param_msg->zmax = octree_cfg.zmax;
    octree_param_msg->depth_max_range = octree_cfg.depth_max_range;
    octree_param_msg->correction_threshold = octree_cfg.correction_threshold;

    // Octree map
    univloc_tracker::Client::get_instance().octree_map_msg_ = std::make_shared<univloc_msgs::Octree>();
    univloc_msgs::OctreePtr octree_map_msg;
    octree_map_msg = univloc_tracker::Client::get_instance().octree_map_msg_;
    octree->toROSMsg(*octree_map_msg);
}

void TrackerImpl::start(const bool need_initialize)
{
    spdlog::info("startup SLAM system");
    if (system_is_running_) {
        spdlog::error("SLAM system already started, but start() is called again");
        return;
    }
    system_is_running_ = true;

    if (!need_initialize) {
        tracker_->tracking_state_ = tracker_state_t::Lost;
    }

    feature_extraction_thread_ = std::make_unique<std::thread>(&openvslam::feature_extraction_module::run, feature_extraction_module_);
    tracking_thread_ = std::make_unique<std::thread>(&openvslam::univloc_tracking_module::run, tracker_);
    mapping_thread_ = std::make_unique<std::thread>(&openvslam::univloc_mapping_module::run, mapper_);
    client_thread_ = std::make_unique<std::thread>(&univloc_tracker::Client::run, &univloc_tracker::Client::get_instance());
    if (cfg_->enable_fast_mapping_)
        reconstruction_thread_ = std::make_unique<std::thread>(&fast_mapping::fast_mapping_module::run, fast_mapping_module_);
    if (cfg_->gui_)
        gui_thread_ = std::make_unique<std::thread>(&openvslam::univloc_tracking_module::visualize_keypoints, tracker_);
}

void TrackerImpl::shutdown()
{
    if (!system_is_running_)
        return;
    system_is_running_ = false;
    spdlog::debug("shutting down...");
    if (traj_store_path_ != "") {
        traj_store_path_ = traj_store_path_ + "relocal.txt";
        spdlog::info("save relocal result in " + traj_store_path_);
        std::ofstream traj_file(traj_store_path_);
        while (true) {
            auto reloc_result = univloc_tracker::Client::get_instance().get_relocalization_results();
            if (!reloc_result) break;
            assert(reloc_result->keyframes.size() == 1);

            auto keyframe_msg = reloc_result->keyframes[0];
            // process pose data
            Eigen::Matrix4d cam_pose_cw;
            for (int idx = 0; idx < cam_pose_cw.rows(); ++idx)
                for (int idy = 0; idy < cam_pose_cw.cols(); ++idy)
                    cam_pose_cw(idx, idy) = keyframe_msg.mv_pose[idx * cam_pose_cw.rows() + idy];

            Eigen::Matrix4d pose = cam_pose_cw.inverse();
            Eigen::Matrix3d R = pose.block(0, 0, 3, 3);
            Eigen::Quaterniond q(R);
            traj_file << std::setprecision(15) << keyframe_msg.md_timestamp << std::setprecision(9) << " " << pose(0, 3)
                      << " " << pose(1, 3) << " " << pose(2, 3) << " " << q.x() << " " << q.y() << " " << q.z() << " "
                      << q.w() << "\n";
        }
    }
    // terminate the other threads
    univloc_tracker::Client::get_instance().terminate();
    mapper_->request_terminate();
    // wait until they stop
    while (!mapper_->is_terminated()) {
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    }

    request_queue_.close();
    request_lidar_queue_.close();
    feature_queue_.close();
    result_queue_.close();
    reconstruction_queue_.close();
    spdlog::debug("closed queues");

    // wait until the threads stop
    feature_extraction_thread_->join();
    spdlog::debug("feature thread exited");
    tracking_thread_->join();
    spdlog::debug("tracking thread exited");
    client_thread_->join();
    spdlog::debug("client thread exited");
    mapping_thread_->join();
    spdlog::debug("mapping thread exited");
    if (cfg_->enable_fast_mapping_) {
        reconstruction_thread_->join();
        spdlog::debug("reconstruction thread exited");
        if (!cfg_->octree_store_path_.empty()) {
            fast_mapping::save_octree_map(cfg_->octree_store_path_, fast_mapping_module_->get_camera_intrinsics(),
                                          fast_mapping_module_->get_octree_cfg(), fast_mapping_module_->get_octree());
            spdlog::info("finish saving octree map");
        }
    }
    if (cfg_->gui_) {
        gui_thread_->join();
        spdlog::debug("tracking visualization thread exited");
    }

    spdlog::info("shutdown SLAM system");
}

std::vector<Eigen::Vector3d> TrackerImpl::get_local_landmark_positions() const
{
    return tracker_->get_local_landmark_positions();
}

ClientID TrackerImpl::get_client_id() const
{
    return univloc_tracker::Client::get_instance().get_client_id();
}

bool TrackerImpl::connected_to_server() const
{
    return univloc_tracker::Client::get_instance().connected();
}

#if false
void TrackerImpl::save_frame_trajectory(const std::string& path, const std::string& format) const
{
    pause_other_threads();
    io::trajectory_io trajectory_io(map_db_);
    trajectory_io.save_frame_trajectory(path, format);
    resume_other_threads();
}

void TrackerImpl::save_keyframe_trajectory(const std::string& path, const std::string& format) const
{
    pause_other_threads();
    io::trajectory_io trajectory_io(map_db_);
    trajectory_io.save_keyframe_trajectory(path, format);
    resume_other_threads();
}

void TrackerImpl::load_map_database(const std::string& path) const
{
    pause_other_threads();
    io::map_database_io map_db_io(cam_db_, map_db_, bow_db_, bow_vocab_);
    map_db_io.load_message_pack(path);
    resume_other_threads();
}

void TrackerImpl::save_map_database(const std::string& path) const
{
    pause_other_threads();
    io::map_database_io map_db_io(cam_db_, map_db_, bow_db_, bow_vocab_);
    map_db_io.save_message_pack(path);
    resume_other_threads();
}

void TrackerImpl::enable_mapping_module()
{
    std::lock_guard<std::mutex> lock(mtx_mapping_);
    if (!system_is_running_) {
        spdlog::critical("please call TrackerImpl::enable_mapping_module() after TrackerImpl::startup()");
    }
    // resume the mapping module
    mapper_->resume();
    // inform to the tracking module
    tracker_->set_mapping_module_status(true);
}

void TrackerImpl::disable_mapping_module()
{
    std::lock_guard<std::mutex> lock(mtx_mapping_);
    if (!system_is_running_) {
        spdlog::critical("please call TrackerImpl::disable_mapping_module() after TrackerImpl::startup()");
    }
    // pause the mapping module
    mapper_->request_pause();
    // wait until it stops
    while (!mapper_->is_paused()) {
        std::this_thread::sleep_for(std::chrono::microseconds(1000));
    }
    // inform to the tracking module
    tracker_->set_mapping_module_status(false);
}

bool TrackerImpl::mapping_module_is_enabled() const { return !mapper_->is_paused(); }
#endif

void TrackerImpl::feed_image(std::shared_ptr<ImageFrame> frame)
{
    check_reset_request();
    request_queue_.force_push(frame);
}

void TrackerImpl::feed_lidar(std::shared_ptr<LidarFrame> scan)
{
    request_lidar_queue_.force_push(scan);
}

size_t TrackerImpl::how_many_frames_left() const
{
    return request_queue_.size();
}

std::shared_ptr<ImageFrame> TrackerImpl::get_result()
{
    std::shared_ptr<ImageFrame> ret;
    if (!result_queue_.wait_pop(ret)) return nullptr;
    return ret;
}

void TrackerImpl::feed_odom_data(double t, const Eigen::Matrix4d& odom_to_cam_pose)
{
    odom_data_->input_odom(t, odom_to_cam_pose);
}

void TrackerImpl::feed_imu_data(double t, const Eigen::Vector3d& accel, const Eigen::Vector3d& angular_velocity)
{
    imu_data_->input_IMU(t, accel, angular_velocity);
}

void TrackerImpl::get_keyframes(std::vector<Eigen::Matrix4d>& poses) const
{
    tracker_->get_local_keyframes_poses(poses);
}

void TrackerImpl::get_keyframes(std::vector<Eigen::Matrix4d>& covisibility_poses,
                                std::vector<Eigen::Matrix4d>& non_covisibility_poses) const
{
    tracker_->get_local_keyframes_poses(covisibility_poses, non_covisibility_poses);
}

void TrackerImpl::get_landmarks(std::vector<Eigen::Vector3d>& positions) const
{
    tracker_->get_local_landmarks_positions(positions);
}

void TrackerImpl::get_tracked_server_landmarks(std::vector<Eigen::Vector3d>& positions) const
{
    tracker_->get_tracked_server_landmarks_positions(positions);
}

void TrackerImpl::get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const
{
    tracker_->get_imu_estimated_poses(poses);
}

void TrackerImpl::get_imu_status(univloc_msgs::ImuStatus& msg) const
{
    msg.header.stamp = rclcpp::Time(rclcpp::Clock().now().seconds());
    msg.duration = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_duration_);
    msg.vec_r[0] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_R_[0]);
    msg.vec_r[1] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_R_[1]);
    msg.vec_r[2] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_R_[2]);
    msg.vec_p[0] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_P_[0]);
    msg.vec_p[1] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_P_[1]);
    msg.vec_p[2] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_P_[2]);
    msg.vec_v[0] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_V_[0]);
    msg.vec_v[1] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_V_[1]);
    msg.vec_v[2] = static_cast<float>(openvslam::data::IMU_Preintegration::IMU_States_.preintegration_V_[2]);
    msg.initialize_times = openvslam::data::IMU_Preintegration::IMU_States_.initialize_times_;
}

void TrackerImpl::get_lidar_success_count(univloc_msgs::LidarStatus& msg)
{
    msg.header.stamp = rclcpp::Time(rclcpp::Clock().now().seconds());
    msg.feature_failure_count = feature_extraction_module_->get_lidar_feature_failure_count();
    msg.pose_failure_count = tracker_->get_lidar_pose_failure_count();
}

bool TrackerImpl::tracking_module_is_lost() const {
    return (tracker_->tracking_state_ == tracker_state_t::Lost);
}

data::map_database* TrackerImpl::get_map_database() { return map_db_; }

void TrackerImpl::request_reset() {
    tracker_->set_reset_requested(true);
}

void TrackerImpl::check_reset_request()
{
    if (tracker_->reset_requested()) {
        tracker_->reset();
        tracker_->set_reset_requested(false);
    }
}

se::Octree<SE_FIELD_TYPE>& TrackerImpl::get_octree() { return fast_mapping_module_->get_octree(); }

void TrackerImpl::get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active)
{
    return fast_mapping_module_->get_octree_block_list(blocklist, active);
}

unsigned int TrackerImpl::get_tracker_octree_merged_times()
{
    return fast_mapping_module_->get_tracker_octree_merged_times();
}

bool TrackerImpl::is_coordinate_aligned() const { return tracker_->is_coordinate_aligned(); }

#if false
void TrackerImpl::pause_tracker() { tracker_->request_pause(); }

bool TrackerImpl::tracker_is_paused() const { return tracker_->is_paused(); }

void TrackerImpl::resume_tracker() { tracker_->resume(); }

void TrackerImpl::request_terminate()
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    terminate_is_requested_ = true;
}

bool TrackerImpl::terminate_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    return terminate_is_requested_;
}

void TrackerImpl::pause_other_threads() const
{
    // pause the mapping module
    if (mapper_ && !mapper_->is_terminated()) {
        mapper_->request_pause();
        while (!mapper_->is_paused() && !mapper_->is_terminated()) {
            std::this_thread::sleep_for(std::chrono::microseconds(5000));
        }
    }
}

void TrackerImpl::resume_other_threads() const
{
    // resume the mapping module
    if (mapper_) {
        mapper_->resume();
    }
}
#endif

}  // namespace univloc_tracker
