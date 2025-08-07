// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_DATA_LIDAR_LANDMARK_H
#define OPENVSLAM_DATA_LIDAR_LANDMARK_H

#include <opencv2/core.hpp>
#include <vector>

namespace openvslam {
namespace data {

class lidar_landmark {
public:
    std::vector<cv::Point2d> points2d;
    std::vector<unsigned int> lidar_lm_ID;
    std::vector<cv::Point2d> lidar_lm_pos_w_;
    float timestamp;
    bool updated = false;
};

}  // namespace data
}  // namespace openvslam

#endif  // OPENVSLAM_DATA_LIDAR_LANDMARK_H