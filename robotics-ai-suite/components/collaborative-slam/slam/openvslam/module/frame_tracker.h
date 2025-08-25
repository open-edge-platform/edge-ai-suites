// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_FRAME_TRACKER_H
#define OPENVSLAM_MODULE_FRAME_TRACKER_H

#include "type.h"
#include "optimize/pose_optimizer.h"

namespace openvslam {

namespace camera {
class base;
class map_database;
}  // namespace camera

namespace data {
class frame;
class keyframe;
}  // namespace data

namespace module {

class frame_tracker {
public:
    explicit frame_tracker(camera::base* camera, const unsigned int num_matches_thr = 20, bool use_odom = false,
                           bool is_localization = false, data::map_database* map_db = nullptr);

    bool motion_based_track(data::frame& curr_frm, const data::frame& last_frm, const Mat44_t& velocity) const;

    bool lidar_based_track(data::frame& curr_frm, const data::frame& last_frm, const Mat44_t& velocity, data::frame& last_lidar_frame, Eigen::Matrix4d& tf_lidar_camera) const;

    bool bow_match_based_track(data::frame& curr_frm, const data::frame& last_frm, data::keyframe* ref_keyfrm) const;

    bool robust_match_based_track(data::frame& curr_frm, const data::frame& last_frm, data::keyframe* ref_keyfrm) const;

    bool imu_based_track(data::frame& curr_frm, const data::frame& last_frm,
                         const Mat44_t predicted_pose_from_imu) const;

    bool odom_based_track(data::frame& curr_frm, const data::frame& last_frm,
                          const Mat44_t& predicted_pose_from_odom) const;

    bool is_localization_;

        private : unsigned int discard_outliers(data::frame& curr_frm) const;

    data::map_database* map_db_ = nullptr;
    const camera::base* camera_;
    const unsigned int num_matches_thr_;

    const optimize::pose_optimizer pose_optimizer_;
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_FRAME_TRACKER_H
