/*
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef OPENVSLAM_MATCH_FUSE_H
#define OPENVSLAM_MATCH_FUSE_H

#include "type.h"
#include "match/base.h"

namespace openvslam
{

namespace data
{
class keyframe;
class landmark;
}  // namespace data

namespace match
{

class fuse final : public base
{
public:
  explicit fuse(const float lowe_ratio = 0.6) : base(lowe_ratio, true) {}

  ~fuse() final = default;

  //! NOTE: landmarks_to_check.size() == duplicated_lms_in_keyfrm.size()
  unsigned int detect_duplication(
    data::keyframe * keyfrm, const Mat44_t & Sim3_cw,
    const std::vector<data::landmark *> & landmarks_to_check, const float margin,
    std::vector<data::landmark *> & duplicated_lms_in_keyfrm);

  template <typename T>
  unsigned int replace_duplication(
    data::keyframe * keyfrm, const T & landmarks_to_check, const float margin = 3.0);
};

}  // namespace match
}  // namespace openvslam

#endif  // OPENVSLAM_MATCH_FUSE_H
