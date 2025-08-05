// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_SO3_SHOT_VERTEX_H
#define OPENVSLAM_OPTIMIZER_G2O_SO3_SHOT_VERTEX_H

#include "type.h"

#include <g2o/core/base_vertex.h>
#include <unsupported/Eigen/MatrixFunctions>
#include <iostream>
namespace openvslam {
namespace optimize {
namespace g2o {
namespace so3 {

class so3_vertex final : public ::g2o::BaseVertex<3, Mat33_t> {
    int updated_times_;

public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    so3_vertex();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void setToOriginImpl() override { _estimate = Mat33_t::Identity(); }

    void oplusImpl(const double* update_) override;
};

}  // namespace so3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_SE3_SHOT_VERTEX_H
