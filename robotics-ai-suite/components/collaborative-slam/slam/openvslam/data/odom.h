// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef ODOM_H
#define ODOM_H

#include <Eigen/Core>

#include <iostream>
#include <stdio.h>
#include <mutex>
#include <memory>
#include <map>
#include <spdlog/spdlog.h>
#include "type.h"

namespace openvslam {
namespace data {
class odom {
    std::map<double, Eigen::Matrix4d> odom_buf_;
    std::mutex mtx_odom_buf_;

public:
    odom(Eigen::Matrix4d T_image_to_camera = Eigen::Matrix4d::Identity());
    void input_odom(double t, const Eigen::Matrix4d& cam_to_odom_pose);
    int get_odom(double t, Eigen::Matrix4d& cam_to_odom_pose);

private:
    void interpolation(const Eigen::Matrix4d& prev_pose, const Eigen::Matrix4d& post_pose, double prev_t, double pose_t,
                       double t, Eigen::Matrix4d& pose);
    Eigen::Matrix4d T_image_to_camera_;
};
}  // namespace data
}  // namespace openvslam

#endif