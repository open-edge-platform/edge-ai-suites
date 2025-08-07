// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef UNIVLOC_TRACKING_MODULE_H
#define UNIVLOC_TRACKING_MODULE_H

#include "data/frame.h"
#include "tracker/QueueTypes.h"
#include "univloc_msgs.h"
#include "tracking_module.h"

#include <memory>
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


class univloc_tracking_module: public tracking_module {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    //! Constructor
    univloc_tracking_module(std::shared_ptr<univloc_tracker::Config> cfg, camera::base* camera,
                    const ClientID client_id, data::map_database* map_db, data::bow_database* bow_db,
                    FeatureQueue& feature_queue, RequestQueue& result_queue, RequestQueue& reconstruction_queue);

    //! Destructor
    ~univloc_tracking_module();

    //! Main loop
    void run();

    //! Reset the databases
    void reset() override;

    void visualize_keypoints();

    bool reset_requested() const;

    void set_reset_requested(bool val);

    int get_lidar_pose_failure_count();

    bool is_coordinate_aligned() const;

    void set_coordinate_aligned(bool val);

protected:
    //-----------------------------------------
    // tracking processes

    std::shared_ptr<data::frame> last_lidar_frm_;

    int lidar_pose_failure_count_ = 0;

    void process_current_frame();

    //! Main stream of the tracking module
    void track();

    void localization_track();

    void relocalization_mode();

    void request_relocalization_from_server();

    //! Try to initialize with the current frame
    bool initialize() override;

    //! Update the local map
    void update_local_map();

    void update_map_database();

    //! Update the local keyframes
    void update_local_keyframes();

    //! Update the local landmarks
    void update_local_landmarks();

    void remove_untracked_server_landmarks();

    void reset_last_tracked_server_landmarks_state();

    void send_relocalization_request_to_server(data::keyframe* keyfrm_to_be_relocalized);

    bool retrieve_relocalization_result();

    bool track_server_map();
    bool track_server_map_with_odom();

    bool optimize_current_frame_with_server_map();
    //! Optimize the camera pose of the current frame
    bool optimize_current_frame_with_all_map();

    bool search_server_landmarks();

    bool track_current_frame() override;

    void count_valid_tracked_server_landmarks();

    void update_frm_and_keyfrm_using_relocalization(data::keyframe* p_keyframe, std::shared_ptr<data::frame> p_frame,
                                                    univloc_msgs::MapConstPtr map_msg_ptr);


    std::any predict_current_pose_with_imu(data::frame& frame);

    void localizing_new_keyframe(data::frame& frame,
                                 std::pair<std::shared_ptr<data::IMU_Preintegration>, Vec3_t> predict_info);

    bool is_motion_enough_for_stereo_or_rgbd_input();

    //! input queue to get frame data with features
    FeatureQueue& feature_queue_;

    //! output queue to give frame data with poses
    RequestQueue& result_queue_;

    //! output queue to give frame data with poses to the 3D reconstruction module
    RequestQueue& reconstruction_queue_;

    void queue_visualization_frames();

    cv::Mat combine_images(cv::Mat img1, cv::Mat img2);

    std::unordered_map<unsigned int, std::shared_ptr<data::landmark>> tracked_server_landmarks_;

    //! gui frame queue to render frames in separate thread
    std::unique_ptr<VisualizationFrameQueue> gui_queue_;

    std::atomic<bool> reset_requested_ = false;

    uint32_t num_tracked_lms_thr_ = 0;

    const ClientID client_id_;

    typedef void(univloc_tracking_module::*tracker_exec_mode)();
    tracker_exec_mode tracker_func_mode_ = &univloc_tracking_module::track;
    double timestamp_recently_lost_;

    //! tracker state transition function used in track()
    tracker_state_t track_trans_state_basic(bool is_succeeded, std::any& anydata);

    tracker_state_t track_trans_state_odom(bool is_succeeded, std::any& anydata);

    tracker_state_t track_trans_state_imu(bool is_succeeded, std::any& anydata);

    tracker_state_t localization_track_trans_state_basic(bool is_succeeded, std::any& anydata);

    tracker_state_t localization_track_trans_state_odom(bool is_succeeded, std::any& anydata);

    typedef tracker_state_t (univloc_tracking_module::*track_trans_state_mode)(bool is_succeeded, std::any& pre_info);
    track_trans_state_mode track_trans_state_func_ = nullptr;

    typedef bool (univloc_tracking_module::*track_localization)();
    track_localization track_server_localization_ = nullptr;

    //! in relocalization mode, it is used to count the relocaliation request sent to server
    //! in localization mode, it is also used to trigger relocalization request at a lower frequency
    uint32_t frms_sent_for_relocalization_ = 0;

    //! For Kalman Filter, it is used to avoid publishing pose when tracker resets and haven't merged with global map
    std::atomic<bool> coordinate_aligned_{true};
};

}  // namespace openvslam

#endif  // UNIVLOC_TRACKING_MODULE_H
