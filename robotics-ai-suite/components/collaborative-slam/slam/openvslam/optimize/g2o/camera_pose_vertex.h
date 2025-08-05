// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef CAMERA_POSE_VERTEX_H
#define CAMERA_POSE_VERTEX_H

#include "type.h"
#include <g2o/core/base_vertex.h>
#include <unsupported/Eigen/MatrixFunctions>

namespace openvslam {
namespace optimize {
namespace g2o {

// Parameterize the camera pose with rotation matrix and position, instead of SE(3), which is meant for fusion imu
class camera_pose_vertex final : public ::g2o::BaseVertex<6, Mat44_t> {
    int updated_times_ = 0;

public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    camera_pose_vertex();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void setToOriginImpl() override { _estimate.fill(0); }

    void oplusImpl(const double* update) override;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_LANDMARK_VERTEX_H
