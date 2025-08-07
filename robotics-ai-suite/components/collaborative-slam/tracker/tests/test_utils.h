// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef TEST_UTILS_H
#define TEST_UTILS_H

#include <memory>
#include <string>
#include <atomic>

#define EPSILON 0.00001

namespace univloc_tracker {

struct robot_pose {
    double position_x_ = 0.0;
    double position_y_ = 0.0;
    double position_z_ = 0.0;

    double orientation_x_ = 0.0;
    double orientation_y_ = 0.0;
    double orientation_z_ = 0.0;
    double orientation_w_ = 0.0;

    bool operator==(robot_pose& pose) const
    {
        if (std::abs(position_x_ - pose.position_x_) > EPSILON) return false;
        if (std::abs(position_y_ - pose.position_y_) > EPSILON) return false;
        if (std::abs(position_z_ - pose.position_z_) > EPSILON) return false;

        if (std::abs(orientation_x_ - pose.orientation_x_) > EPSILON) return false;
        if (std::abs(orientation_y_ - pose.orientation_y_) > EPSILON) return false;
        if (std::abs(orientation_z_ - pose.orientation_z_) > EPSILON) return false;
        if (std::abs(orientation_w_ - pose.orientation_w_) > EPSILON) return false;

        return true;
    }

    bool operator==(const double& value) const
    {
        if (std::abs(position_x_ - value) > EPSILON) return false;
        if (std::abs(position_y_ - value) > EPSILON) return false;
        if (std::abs(position_z_ - value) > EPSILON) return false;

        if (std::abs(orientation_x_ - value) > EPSILON) return false;
        if (std::abs(orientation_y_ - value) > EPSILON) return false;
        if (std::abs(orientation_z_ - value) > EPSILON) return false;
        if (std::abs(orientation_w_ - value) > EPSILON) return false;

        return true;
    }
};

}  // namespace univloc_tracker

#endif
