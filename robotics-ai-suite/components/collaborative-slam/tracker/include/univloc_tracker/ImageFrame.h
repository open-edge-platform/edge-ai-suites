// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <Eigen/Core>
#include <opencv2/core/core.hpp>

#include <any>
#include <optional>

namespace univloc_tracker {

class ImageFrame {
public:
    ImageFrame(cv::Mat image1, cv::Mat image2, double timestamp, std::any& cdata)
        : image1(image1), image2(image2), timestamp(timestamp), cdata(cdata)
    {
    }

    ImageFrame(cv::Mat image1, double timestamp, std::any& cdata)
        : image1(image1), image2(), timestamp(timestamp), cdata(cdata)
    {
    }

    cv::Mat image1;
    cv::Mat image2;
    double timestamp;
    std::any cdata;
    std::optional<Eigen::Matrix4d> maybe_pose;
    std::optional<Eigen::Matrix<double, 6, 6>> maybe_covariance;
};

}  // namespace univloc_tracker
