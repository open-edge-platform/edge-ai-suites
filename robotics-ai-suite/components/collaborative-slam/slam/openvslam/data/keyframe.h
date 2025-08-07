// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_DATA_KEYFRAME_H
#define OPENVSLAM_DATA_KEYFRAME_H

#include "camera/base.h"
#include "data/bow_vocabulary.h"
#include "data/graph_node.h"
#include "type.h"
#include <memory>
#include <atomic>
#include <mutex>
#include <set>

#include <g2o/types/sba/types_six_dof_expmap.h>
#include <nlohmann/json_fwd.hpp>

#ifdef USE_DBOW2
#include <DBoW2/BowVector.h>
#include <DBoW2/FeatureVector.h>
#else
#include <fbow/fbow.h>
#endif

#ifdef ENABLE_SEMANTIC_SLAM
#include <inference_engine.hpp>
#include "ros/package.h"
#endif
#include <opencv2/highgui/highgui.hpp>
#include<opencv2/imgproc/imgproc.hpp>

namespace openvslam {

namespace camera {
class base;
}  // namespace camera

namespace data {

class frame;
class landmark;
class map_database;
class bow_database;
class IMU_Preintegration;

class keyframe {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    // For multi-slam system
    double mdServerTimestamp = 0.0;
    static void initial_start_id(const KeyframeID start_id);
    void ask_for_new_server_map();
    void set_update_from_server(bool update_from_server);
    bool is_update_from_server();

    bool imu_is_initialized_ = false;

    Eigen::Matrix4d odom_ = Eigen::Matrix4d::Identity();

    keyframe* ref_keyfrm_;

    // Server part

    const ClientID client_id_;

    void change_to_new_map(data::map_database* new_map_db);

    void set_will_be_erazed(bool will_be_erazed = false);

    void set_map_id(const MapID map_id);

    MapID get_map_id() const;

    // operator overrides
    bool operator==(const keyframe& keyfrm) const { return id_ == keyfrm.id_; }
    bool operator!=(const keyframe& keyfrm) const { return !(*this == keyfrm); }
    bool operator<(const keyframe& keyfrm) const { return id_ < keyfrm.id_; }
    bool operator<=(const keyframe& keyfrm) const { return id_ <= keyfrm.id_; }
    bool operator>(const keyframe& keyfrm) const { return id_ > keyfrm.id_; }
    bool operator>=(const keyframe& keyfrm) const { return id_ >= keyfrm.id_; }


#ifdef ENABLE_SEMANTIC_SLAM
    /**
     * Constructor for building from a frame when using semantic segmentation
     */
    keyframe(frame& frm, map_database* map_db, bow_database* bow_db);
#else
    /**
     * Constructor for building from a frame
     */
    keyframe(const frame& frm, map_database* map_db, bow_database* bow_db);
#endif

    /**
     * Constructor for building from a frame
     */
    keyframe(const frame& frm, map_database* map_db, bow_database* bow_db, ClientID client_id, MapID map_id);

    /**
     * Constructor for map loading
     * (NOTE: some variables must be recomputed after the construction. See the definition.)
     */
    keyframe(const KeyframeID id, const KeyframeID src_frm_id, const double timestamp, const Mat44_t& cam_pose_cw,
             camera::base* camera, const float depth_thr, const unsigned int num_keypts,
             const std::vector<cv::KeyPoint>& keypts, const std::vector<cv::KeyPoint>& undist_keypts,
             const eigen_alloc_vector<Vec3_t>& bearings, const std::vector<float>& stereo_x_right,
             const std::vector<float>& depths, const cv::Mat& descriptors, const unsigned int num_scale_levels,
             const float scale_factor, bow_vocabulary* bow_vocab, bow_database* bow_db, map_database* map_db);

    /**
     * Constructor for map loading - server side
     * (NOTE: some variables must be recomputed after the construction. See the definition.)
     */
    keyframe(const KeyframeID id, const KeyframeID src_frm_id, const double timestamp, const Mat44_t& cam_pose_cw,
             camera::base* camera, const float depth_thr, const unsigned int num_keypts,
             const std::vector<cv::KeyPoint>& keypts, const std::vector<cv::KeyPoint>& undist_keypts,
             const eigen_alloc_vector<Vec3_t>& bearings, const std::vector<float>& stereo_x_right,
             const std::vector<float>& depths, const cv::Mat& descriptors, const unsigned int num_scale_levels,
             const float scale_factor, bow_vocabulary* bow_vocab, bow_database* bow_db, map_database* map_db,
             ClientID client_id, MapID map_id);

    bool new_created_ = true;

    bool being_sliding_out_ = false;

    bool is_new_created();

    void set_not_new_created();

    mutable std::mutex mtx_newcreated_;

    /**
     * Encode this keyframe information as JSON
     */
    nlohmann::json to_json() const;

    nlohmann::json to_json_tracker() const;

    nlohmann::json to_json_server() const;

    bool can_observe(const landmark* lm) const;

    //-----------------------------------------
    // camera pose

    /**
     * Set camera pose
     */
    void set_cam_pose(const Mat44_t& cam_pose_cw);

    /**
     * Set camera pose
     */
    void set_cam_pose(const g2o::SE3Quat& cam_pose_cw);

    /**
     * Get the camera pose
     */
    Mat44_t get_cam_pose() const;

    /**
     * Get the inverse of the camera pose
     */
    Mat44_t get_cam_pose_inv() const;

    /**
     * Get the camera center
     */
    Vec3_t get_cam_center() const;

    /**
     * Get the rotation of the camera pose
     */
    Mat33_t get_rotation() const;

    /**
     * Get the translation of the camera pose
     */
    Vec3_t get_translation() const;

    //-----------------------------------------
    // features and observations

    /**
     * Compute BoW representation
     */
    void compute_bow();

    /**
     * Add a landmark observed by myself at keypoint idx
     */
    void add_landmark(landmark* lm, const unsigned int idx);

    /**
     * Erase a landmark observed by myself at keypoint idx
     */
    void erase_landmark_with_index(const unsigned int idx);

    /**
     * Erase a landmark
     */
    void erase_landmark(landmark* lm);

    /**
     * Replace the landmark
     */
    void replace_landmark(landmark* lm, const unsigned int idx);

    /**
     * Get all of the landmarks
     * (NOTE: including nullptr)
     */
    std::vector<landmark*> get_landmarks() const;

    size_t get_num_landmarks() const;

    /**
     * Get the valid landmarks
     */
    std::set<landmark*> get_valid_landmarks() const;

    /**
     * Get the number of tracked landmarks which have observers equal to or greater than the threshold
     */
    unsigned int get_num_tracked_landmarks(const unsigned int min_num_obs_thr) const;

    /**
     * Get the landmark associated keypoint idx
     */
    landmark* get_landmark(const unsigned int idx) const;

    /**
     * Get the keypoint indices in the cell which reference point is located
     */
    std::vector<unsigned int> get_keypoints_in_cell(const float ref_x, const float ref_y, const float margin) const;

    /**
     * Triangulate the keypoint using the disparity
     */
    Vec3_t triangulate_stereo(const unsigned int idx) const;

    /**
     * Compute median of depths
     */
    float compute_median_depth(const bool abs = false) const;

    /**
     * Get the bow_vocab_
     */
    bow_vocabulary* get_bow_vocab() const;

    //-----------------------------------------
    // flags

    /**
     * Set this keyframe as non-erasable
     */
    void set_not_to_be_erased();

    /**
     * Set this keyframe as erasable
     */
    void set_to_be_erased();

    /**
     * Erase this keyframe
     */
    void prepare_for_erasing(bool is_redundant, bool is_server);

    void prepare_for_erasing();

    void prepare_for_erasing_remapping(); // Only used to remove within remapping region, also includes
                                          // loop edges and origin keyframes

    /**
     * Whether this keyframe will be erased shortly or not
     */
    void set_will_be_erased();

    bool will_be_erased();

    void set_origin();

    void clear_origin();

    bool is_origin();

    //-----------------------------------------
    // for imu-related

    Mat33_t get_imu_rotation() const;

    Vec3_t get_imu_position() const;

    void set_imu_constraint(data::keyframe* ref_keyframe, std::shared_ptr<data::IMU_Preintegration> imu_constraint);

    std::pair<data::keyframe*, std::shared_ptr<IMU_Preintegration>> get_imu_constraint() const;

    // for vio, please use this func to set new imu bias
    void set_new_imu_bias(const Eigen::VectorXd imu_bias);

    Eigen::VectorXd get_imu_bias() const;

    void set_imu_velocity(const Eigen::Vector3d& v);

    Eigen::Vector3d get_imu_velocity() const;

    void update_imu_link();

    //-----------------------------------------
    // For imu reset
    bool bad_imu_to_reset_ = false;

    //-----------------------------------------
    // For multi slam
    bool update_from_server_ = false;

    //-----------------------------------------
    // for local map update

    //! identifier for local map update
    KeyframeID local_map_update_identifier = 0;

    //-----------------------------------------
    // for loop BA

    //! identifier for loop BA
    KeyframeID loop_BA_identifier_ = 0;
    //! camera pose AFTER loop BA
    Mat44_t cam_pose_cw_after_loop_BA_;
    //! camera pose BEFORE loop BA
    Mat44_t cam_pose_cw_before_BA_;

    // For updating pose from server
    Mat44_t cam_pose_wc_before_replacing_;

    //-----------------------------------------
    // meta information

    //! keyframe ID
    KeyframeID id_;
    //! next keyframe ID
    static std::atomic<KeyframeID> next_id_;

    //! source frame ID
    const KeyframeID src_frm_id_;

    //! timestamp in seconds
    const double timestamp_;

    //-----------------------------------------
    // flags used in one optimization,
    // will reset at the end of optimization

    //! if considered (add to container)
    bool is_considered_;

    //! if fixed in optimizer
    bool is_fixed_;

    //-----------------------------------------
    // camera parameters

    //! camera model
    camera::base* camera_;
    //! depth threshold
    const float depth_thr_;

    //-----------------------------------------
    // constant observations

    //! number of keypoints
    const unsigned int num_keypts_;

    //! keypoints of monocular or stereo left image
    const std::vector<cv::KeyPoint> keypts_;
    //! undistorted keypoints of monocular or stereo left image
    const std::vector<cv::KeyPoint> undist_keypts_;
    //! bearing vectors
    const eigen_alloc_vector<Vec3_t> bearings_;

    //! keypoint indices in each of the cells
    const std::vector<std::vector<std::vector<unsigned int>>> keypt_indices_in_cells_;

    //! disparities
    const std::vector<float> stereo_x_right_;
    //! depths
    const std::vector<float> depths_;

    //! descriptors
    const cv::Mat descriptors_;

    //! BoW features (DBoW2 or FBoW)
#ifdef USE_DBOW2
    DBoW2::BowVector bow_vec_;
    DBoW2::FeatureVector bow_feat_vec_;
#else
    fbow::BoWVector bow_vec_;
    fbow::BoWFeatVector bow_feat_vec_;
#endif

    //-----------------------------------------
    // covisibility graph

    //! graph node
    const std::unique_ptr<graph_node> graph_node_ = nullptr;

    //-----------------------------------------
    // ORB scale pyramid information

    //! number of scale levels
    const unsigned int num_scale_levels_;
    //! scale factor
    const float scale_factor_;
    //! log scale factor
    const float log_scale_factor_;
    //! list of scale factors
    const std::vector<float> scale_factors_;
    //! list of sigma^2 (sigma=1.0 at scale=0) for optimization
    const std::vector<float> level_sigma_sq_;
    //! list of 1 / sigma^2 for optimization
    const std::vector<float> inv_level_sigma_sq_;

    bool in_cur_covisibility_window_ = false;

    bool should_be_fixed_in_optimization_;

    bool execute_front_rear_camera_constraint_ = false;

    unsigned int visualization_time_ = 0;

    float window_distance_ = 0;

    //! whether client has finished update after server optim
    //  if true, the keyframe can trigger loop detection and server optim
    bool available_for_loop_detector_ = true;

    data::keyframe *next_keyframe_ = nullptr, *pre_keyframe_ = nullptr;

    unsigned int out_of_local_map_times_ = 0;

#ifdef ENABLE_SEMANTIC_SLAM
    void segment_video_init();

    void segment_video_frame(const cv::Mat& img);

    void update_keypoint(data::frame& curr_frm);
    
    std::string network_path;
    cv::Mat segment_mask;
  
    InferenceEngine::Core ie;
    InferenceEngine::CNNNetwork network; 
    InferenceEngine::ICNNNetwork::InputShapes inputShapes;
    
    InferenceEngine::SizeVector inSizeVector;
    InferenceEngine::InputInfo inputInfo;
    InferenceEngine::OutputsDataMap outputsDataMap;
    //std::string outName;
    //InferenceEngine::Data data_IE;
    InferenceEngine::SizeVector outSizeVector;
    //int outChannels, outHeight, outWidth; 
    InferenceEngine::ExecutableNetwork executableNetwork ;
    static InferenceEngine::InferRequest inferRequest;
    static int outChannels;
    static int outHeight;
    static int outWidth;
    static std::string inName;
    static std::string outName;

    // Known colors for training classes from the Cityscapes dataset
    std::vector<cv::Vec3b> colors {
                                    { 128, 64,  128 },
                                    { 232, 35,  244 },
                                    { 70,  70,  70 },
                                    { 156, 102, 102 },
                                    { 153, 153, 190 },
                                    { 153, 153, 153 },
                                    { 30,  170, 250 },
                                    { 0,   220, 220 },
                                    { 35,  142, 107 },
                                    { 152, 251, 152 },
                                    { 180, 130, 70 },
                                    { 60,  20,  220 },
                                    { 0,   0,   255 },
                                    { 142, 0,   0 },
                                    { 70,  0,   0 },
                                    { 100, 60,  0 },
                                    { 90,  0,   0 },
                                    { 230, 0,   0 },
                                    { 32,  11,  119 },
                                    { 0,   74,  111 },
                                    { 81,  0,   81 }
                                  };
#endif

private:
    //-----------------------------------------
    // find candidate for the current origin keyframe in remapping mode
    void replace_origin_with_other_candidate();

    //-----------------------------------------
    // camera pose

    //! need mutex for access to poses
    mutable std::mutex mtx_pose_;
    //! camera pose from the world to the current
    Mat44_t cam_pose_cw_;
    //! camera pose from the current to the world
    Mat44_t cam_pose_wc_;
    //! camera center
    Vec3_t cam_center_;

    //-----------------------------------------
    // observations

    //! need mutex for access to observations
    mutable std::mutex mtx_observations_;
    //! observed landmarks
    std::vector<landmark*> landmarks_;

    //-----------------------------------------
    // databases

    //! need mutex for access to bow_vocab_
    mutable std::mutex mtx_bow_;

    //! map database
    map_database* map_db_;
    //! BoW database
    bow_database* bow_db_;
    //! BoW vocabulary
    bow_vocabulary* bow_vocab_;

    //-----------------------------------------
    // imu-related
    Eigen::VectorXd imu_bias_;

    Eigen::Vector3d imu_velocity_;

    std::pair<data::keyframe*, std::shared_ptr<IMU_Preintegration>> imu_constraint_;

    //-----------------------------------------
    // flags

    //! flag which indicates this keyframe is erasable or not
    std::atomic<bool> cannot_be_erased_{false};

    //! flag which indicates this keyframe will be erased
    std::atomic<bool> will_be_erased_{false};

    MapID map_id_;

    std::atomic<bool> is_origin_;
};

typedef std::shared_ptr<keyframe> keyframe_ptr;

}  // namespace data
}  // namespace openvslam

#endif  // OPENVSLAM_DATA_KEYFRAME_H
