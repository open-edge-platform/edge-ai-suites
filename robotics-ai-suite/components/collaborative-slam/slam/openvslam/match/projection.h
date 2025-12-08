/*
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef OPENVSLAM_MATCH_PROJECTION_H
#define OPENVSLAM_MATCH_PROJECTION_H

#include "type.h"
#include "match/base.h"

#include <set>

namespace openvslam
{

namespace data
{
class frame;
class keyframe;
class landmark;
}  // namespace data

namespace match
{

class projection final : public base
{
public:
  explicit projection(const float lowe_ratio = 0.6, const bool check_orientation = true)
  : base(lowe_ratio, check_orientation)
  {
  }

  ~projection() final = default;

  unsigned int match_frame_and_landmarks(
    data::frame & frm, const std::vector<data::landmark *> & local_landmarks,
    const float margin = 5.0) const;

  unsigned int match_frame_and_server_landmarks(
    data::frame & frm, const std::vector<data::landmark *> & server_landmarks,
    const float margin) const;

  unsigned int match_frame_and_local_landmarks(
    data::frame & frm, const std::vector<data::landmark *> & local_landmarks,
    const float margin) const;

  unsigned int match_current_and_last_frames(
    data::frame & curr_frm, const data::frame & last_frm, const float margin) const;

  unsigned int match_frame_and_keyframe(
    data::frame & curr_frm, data::keyframe * keyfrm,
    const std::set<data::landmark *> & already_matched_lms, const float margin,
    const unsigned int hamm_dist_thr) const;

  unsigned int match_by_Sim3_transform(
    data::keyframe * keyfrm, const Mat44_t & Sim3_cw,
    const std::vector<data::landmark *> & landmarks,
    std::vector<data::landmark *> & matched_lms_in_keyfrm, const float margin) const;

  unsigned int match_keyframes_mutually(
    data::keyframe * keyfrm_1, data::keyframe * keyfrm_2,
    std::vector<data::landmark *> & matched_lms_in_keyfrm_1, const float & s_12,
    const Mat33_t & rot_12, const Vec3_t & trans_12, const float margin) const;
};

}  // namespace match
}  // namespace openvslam

#endif  // OPENVSLAM_MATCH_PROJECTION_H
