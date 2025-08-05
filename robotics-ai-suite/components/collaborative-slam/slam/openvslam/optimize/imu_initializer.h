// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef IMU_INITIALIZER_H
#define IMU_INITIALIZER_H

#include <Eigen/Core>
#include <queue>
#include <stdio.h>
#include <utility>
#include <mutex>
#include <memory>
#include "tracking_module.h"

namespace openvslam {

namespace data {
class keyframe;
class map_database;
class IMU_Preintegration;
}  // namespace data

namespace optimize {

void inertial_only_optimize(std::vector<data::keyframe*>& keyframes, KeyframeID max_keyfrm_id, Mat33_t& Rwi,
                                 double& scale, Vec3_t& ba, Vec3_t& bg, bool is_monocular, double& acc_weight,
                                 double& gyro_weight);

void inertial_only_optimize(data::map_database* map_db, KeyframeID max_keyfrm_id, Mat33_t& Rwi,
                                 double& scale);

void visual_inertial_optimize(data::map_database* map_db, KeyframeID max_keyfrm_id, int iterations,
                                   bool is_monocular, bool is_gyro_acc_init, double acc_weight = 1.0e6,
                                   double gyro_weight = 1.0e2);
}  // namespace optimize
}  // namespace openvslam

#endif
