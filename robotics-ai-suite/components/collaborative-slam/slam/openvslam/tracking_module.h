// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_TRACKING_MODULE_H
#define OPENVSLAM_TRACKING_MODULE_H

#include "data/frame.h"
#include "module/frame_tracker.h"
#include "module/initializer.h"
#include "module/keyframe_inserter.h"
#include "module/relocalizer.h"
#include "type.h"
#include "UserConfig.h"
#include "LoopTimer.h"

#include <opencv2/core/core.hpp>
#include <opencv2/features2d/features2d.hpp>

#include <memory>
#include <mutex>
#include <queue>

namespace openvslam {

class mapping_module;

namespace data {
class map_database;
class bow_database;
class odom;
class IMU_data;
class IMU_Preintegration;
}  // namespace data

namespace feature {
class orb_extractor;
}  // namespace feature

// tracker state
enum class tracker_state_t { NotInitialized, Initializing, Tracking, RecentlyLost, Lost };

enum class tracker_mode_t { None, Mapping, Localization, Relocalization, Remapping };

class tracking_module {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    //! Constructor
    tracking_module(std::shared_ptr<univloc_tracker::Config> cfg, camera::base* camera,
                    data::map_database* map_db, data::bow_database* bow_db);

    //! Destructor
    virtual ~tracking_module();

    //! Set the mapping module
    void set_mapping_module(mapping_module* mapper);

#if 0
    //! Add server landmarks to cur_frame observation
    std::vector<data::landmark*> add_observed_server_landmarks();
#endif

    //-----------------------------------------
    // interfaces

    //! Check whether in initializing/lost state of monocular usage
    bool is_initializing() const;

    //! Set mapping module status
    void set_mapping_module_status(const bool mapping_is_enabled);

    //! Get mapping module status
    bool get_mapping_module_status() const;

    //! Get the keypoints of the initial frame
    std::vector<cv::KeyPoint> get_initial_keypoints() const;

    //! Get the keypoint matches between the initial frame and the current frame
    std::vector<int> get_initial_matches() const;

    //! Track a monocular frame
    //! (NOTE: distorted images are acceptable if calibrated)
    Mat44_t track_monocular_image(const cv::Mat& img, const double timestamp, const cv::Mat& mask = cv::Mat{});

    //! Track a stereo frame
    //! (Note: Left and Right images must be stereo-rectified)
    Mat44_t track_stereo_image(const cv::Mat& left_img_rect, const cv::Mat& right_img_rect, const double timestamp,
                               const cv::Mat& mask = cv::Mat{});

    //! Track an RGBD frame
    //! (Note: RGB and Depth images must be aligned)
    Mat44_t track_RGBD_image(const cv::Mat& img, const cv::Mat& depthmap, const double timestamp,
                             const cv::Mat& mask = cv::Mat{});

    //-----------------------------------------
    // management for reset process

    //! Reset the databases
    virtual void reset();

    //-----------------------------------------
    // management for pause process

    //! Request to pause the tracking module
    void request_pause();

    //! Check if the pause of the tracking module is requested or not
    bool pause_is_requested() const;

    //! Check if the tracking module is paused or not
    bool is_paused() const;

    //! Resume the tracking module
    void resume();

    //-----------------------------------------
    // variables

    //！ config
    std::shared_ptr<univloc_tracker::Config> cfg_;

    //! camera model
    camera::base* camera_;

    //! set system stat
    tracker_mode_t tracker_mode_ = tracker_mode_t::None;

    //! latest tracking state
    tracker_state_t tracking_state_ = tracker_state_t::NotInitialized;
    //! last tracking state
    tracker_state_t last_tracking_state_ = tracker_state_t::NotInitialized;

    //! current frame and its image
    std::shared_ptr<data::frame> curr_frm_;

    //! elapsed microseconds for each tracking
    double elapsed_ms_ = 0.0;

    //! use for odom tracking and optimization
    Eigen::Matrix4d first_valid_odom_ = Eigen::Matrix4d::Identity();

    //! the corresponding pose of first_valid_odom_
    Eigen::Matrix4d first_valid_pose_ = Eigen::Matrix4d::Identity();

    //-----------------------------------------
    // monocular camera relocalization
    void clear_frms_and_keyfrms_to_be_relocalized();

    void queue_frm_and_keyfrm_to_be_relocalized(data::keyframe* keyfrm, std::shared_ptr<data::frame> frm);

    bool get_frm_and_keyfrm(KeyframeID id, std::pair<data::keyframe*, std::shared_ptr<data::frame>>& frm_keyfrm);

    void monocular_initialization_using_relocalization(data::keyframe* p_keyframe, std::shared_ptr<data::frame> p_frame);

    std::deque<std::pair<data::keyframe*, std::shared_ptr<data::frame>>> frms_and_keyfrms_to_be_relocalized_;

    void get_local_keyframes_poses(std::vector<Eigen::Matrix4d>& poses, bool sort = true) const;

    void get_local_keyframes_poses(std::vector<Eigen::Matrix4d>& covisibility_poses,
                                   std::vector<Eigen::Matrix4d>& non_covisibility_poses) const;

    void get_local_landmarks_positions(std::vector<Eigen::Vector3d>& positions) const;

    void get_tracked_server_landmarks_positions(std::vector<Eigen::Vector3d>& positions) const;

    void get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const;

    void set_odom_data(std::shared_ptr<data::odom> odom_data_buf);

    void set_imu_data(std::shared_ptr<data::IMU_data> imu_data_buf);

    void align_state_to_inertial_frame(const Eigen::Matrix3d R_inertial_c0, const double scale);

    std::vector<Eigen::Vector3d> get_local_landmark_positions() const;

    unsigned int get_num_tracked_lms() const;

protected:
    //-----------------------------------------
    // tracking processes

    bool get_odom_data();

    void get_relative_transform_from_odom(Mat44_t& relative_transform_from_odom);

    //! Try to initialize with the current frame
    virtual bool initialize();

    //! Track the current frame
    virtual bool track_current_frame();

    //! Update the motion model using the current and last frames
    void update_motion_model();

    //! Replace the landmarks if the `replaced` member has the valid pointer
    void apply_landmark_replace();

    //! Update the camera pose of the last frame
    void update_last_frame();

    //! Optimize the camera pose of the current frame
    bool optimize_current_frame_with_local_map();

    //! Acquire more 2D-3D matches using initial camera pose estimation
    bool search_local_landmarks();

    bool search_all_landmarks();

    //! Check the new keyframe is needed or not
    bool new_keyframe_is_needed() const;

    //! Insert the new keyframe derived from the current frame
    void insert_new_keyframe();

    data::keyframe* create_map_for_stereo(data::frame& frame);

    void predict_camerapose_from_imu();

    //! mapping module
    mapping_module* mapper_ = nullptr;

    float depthmap_factor_ = 0.0;

    // ORB extractors
    //! ORB extractor for left/monocular image
    orb_extractor* extractor_left_ = nullptr;
    //! ORB extractor for right image
    orb_extractor* extractor_right_ = nullptr;
    //! ORB extractor only when used in initializing
    orb_extractor* ini_extractor_left_ = nullptr;

    //! map_database
    data::map_database* map_db_ = nullptr;

    // Bag of Words
    //! BoW database
    data::bow_database* bow_db_ = nullptr;

    //! last successfully queried odometry pose 
    Eigen::Matrix4d last_odom_pose_;

    //! initializer
    module::initializer initializer_;

    //! frame tracker for current frame
    const module::frame_tracker frame_tracker_;

    //! relocalizer
    module::relocalizer relocalizer_;

    //! pose optimizer
    const optimize::pose_optimizer pose_optimizer_;

    //! keyframe inserter
    module::keyframe_inserter keyfrm_inserter_;

    //! reference keyframe
    data::keyframe* ref_keyfrm_ = nullptr;

    data::keyframe* last_keyfrm_ = nullptr;  // Used for imu constraints

    //! local keyframes
    std::vector<data::keyframe*> local_keyfrms_;
    //! local landmarks
    std::vector<data::landmark*> local_landmarks_;

    //! the number of tracked local landmarks in the current keyframe
    unsigned int num_tracked_lms_ = 0;

    //! the number of tracked server landmarks in the current keyframe, part of them existed in the local map dataset,
    //! part exist in the server map dataset
    unsigned int num_tracked_server_lms_ = 0;

    //! last frame
    std::shared_ptr<data::frame> last_frm_;

    //! latest frame ID which succeeded in relocalization
    KeyframeID last_reloc_frm_id_ = 0;

    //! motion model
    Mat44_t velocity_;
    //! motion model is valid or not
    bool velocity_is_valid_ = false;

    //! current camera pose from reference keyframe
    //! (to update last camera pose at the beginning of each tracking)
    Mat44_t last_cam_pose_from_ref_keyfrm_;

    //-----------------------------------------
    // mapping module status

    //! mutex for mapping module status
    mutable std::mutex mtx_mapping_;

    //! mapping module is enabled or not
    bool mapping_is_enabled_ = true;

    //-----------------------------------------
    // management for pause process

    //! mutex for pause process
    mutable std::mutex mtx_pause_;

    //! Check the request frame and pause the tracking module
    bool check_and_execute_pause();

    //! the tracking module is paused or not
    bool is_paused_ = false;

    //! Pause of the tracking module is requested or not
    bool pause_is_requested_ = false;

    //! Predicted velocity by using constant motion model
    Eigen::Matrix4d predicted_velocity_;

    //! Tracked server landmarks position, just for visualization
    std::vector<Eigen::Vector3d> tracked_server_landmarks_position_;

    //! Relocalization
    std::mutex mtx_frm_and_keyfrm_;

    //! For storing odom data
    std::shared_ptr<data::odom> odom_data_buf_;

    //! For storing IMU data
    std::shared_ptr<data::IMU_data> imu_data_buf_;

    //! IMU pre-integration
    std::shared_ptr<data::IMU_Preintegration> imu_preintegration_;

    //! For exacting IMU data between consecutive keyframes
    std::vector<std::pair<double, Eigen::VectorXd>> imu_mearsurement_vec_;

    //! Predicted IMU velocity from IMU data
    Eigen::Vector3d predicted_imu_velocity_;

    //! Predicted camera pose from IMU data
    Eigen::Matrix4d imu_predicted_camera_pose_cw_;

    std::vector<Eigen::Matrix4d> imu_estimated_poses_;

    MapID relocal_map_id_ = -1;

    int success_num_ = 0, lost_num_ = 0, relocal_num_ = 0, relocal_fail_num_ = 0;

    LoopTimer timer_;

    float camera_setup_type_margin_ = 0.0;

    unsigned int min_matched_num_thr_ = 0;
};

}  // namespace openvslam

#endif  // OPENVSLAM_TRACKING_MODULE_H
