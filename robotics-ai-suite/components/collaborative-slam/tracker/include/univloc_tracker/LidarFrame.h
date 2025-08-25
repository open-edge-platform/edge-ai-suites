// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <Eigen/Core>
#include <opencv2/core/core.hpp>

#include <any>
#include <optional>
#include <vector>

namespace univloc_tracker {

class LidarFrame {
public:
    LidarFrame(float angle_min, float angle_max, float angle_increment,
               float time_increment, float scan_time, float range_min, float range_max,
               const std::vector<float> &ranges, const std::vector<float> &intensities, 
               const std::vector<cv::Point2d> &points2d, double timestamp)
        : timestamp(timestamp),
          angle_min(angle_min),
          angle_max(angle_max),
          angle_increment(angle_increment),
          time_increment(time_increment),
          scan_time(scan_time),
          range_min(range_min),
          range_max(range_max),
          ranges(ranges),
          intensities(intensities),
          points2d(points2d)
    {
    }
    double timestamp;
    float angle_min;
    float angle_max;
    float angle_increment;
    float time_increment;
    float scan_time;
    float range_min;
    float range_max;
    std::vector<float> ranges;
    std::vector<float> intensities;
    std::vector<cv::Point2d> points2d;
};

}  // namespace univloc_tracker
