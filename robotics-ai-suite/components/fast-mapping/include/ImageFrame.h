// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <Eigen/Core>
#include <any>
#include <opencv2/core/core.hpp>
#include <optional>

class ImageFrame
{
public:
  ImageFrame(cv::Mat image1, cv::Mat image2, double timestamp)
  : image1(image1), image2(image2), timestamp(timestamp)
  {
  }

  ImageFrame(cv::Mat image2, double timestamp, std::any & cdata)
  : image1(), image2(image2), timestamp(timestamp), cdata(cdata)
  {
  }

  cv::Mat image1;
  cv::Mat image2;
  double timestamp;
  std::any cdata;
  std::optional<Eigen::Matrix4d> maybe_pose;
};
