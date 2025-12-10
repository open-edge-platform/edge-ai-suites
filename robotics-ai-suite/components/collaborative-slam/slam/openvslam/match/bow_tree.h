/*
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef OPENVSLAM_MATCH_BOW_TREE_H
#define OPENVSLAM_MATCH_BOW_TREE_H

#include "match/base.h"

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

class bow_tree final : public base
{
public:
  explicit bow_tree(const float lowe_ratio = 0.6, const bool check_orientation = true)
  : base(lowe_ratio, check_orientation)
  {
  }

  ~bow_tree() final = default;

  unsigned int match_frame_and_keyframe(
    data::keyframe * keyfrm, data::frame & frm,
    std::vector<data::landmark *> & matched_lms_in_frm) const;

  unsigned int match_keyframes(
    data::keyframe * keyfrm_1, data::keyframe * keyfrm_2,
    std::vector<data::landmark *> & matched_lms_in_keyfrm_1) const;
};

}  // namespace match
}  // namespace openvslam

#endif  // OPENVSLAM_MATCH_BOW_TREE_H
