// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_SOLVE_UTIL_H
#define OPENVSLAM_SOLVE_UTIL_H

#include "type.h"

#include <vector>

#include <opencv2/core.hpp>

namespace openvslam {
namespace solve {

void normalize(const std::vector<cv::KeyPoint>& keypts, std::vector<cv::Point2f>& normalized_pts, Mat33_t& transform);

} // namespace solve
} // namespace openvslam

#endif // OPENVSLAM_SOLVE_UTIL_H
