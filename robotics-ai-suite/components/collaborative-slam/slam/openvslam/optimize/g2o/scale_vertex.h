// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_SCALE_VERTEX_H
#define OPENVSLAM_OPTIMIZER_G2O_SCALE_VERTEX_H

#include "type.h"
#include <math.h>
#include <g2o/core/base_vertex.h>

namespace openvslam {
namespace optimize {
namespace g2o {

class scale_vertex final : public ::g2o::BaseVertex<1, double> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    scale_vertex();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void setToOriginImpl() override { _estimate = 1.0; }

    void oplusImpl(const double* update) override { _estimate *= std::exp(*update); }
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_LANDMARK_VERTEX_H
