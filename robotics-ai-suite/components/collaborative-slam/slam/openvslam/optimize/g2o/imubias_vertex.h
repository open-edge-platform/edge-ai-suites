// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_IMUBIAS_VERTEX_H
#define OPENVSLAM_OPTIMIZER_G2O_IMUBIAS_VERTEX_H

#include "type.h"

#include <g2o/core/base_vertex.h>

namespace openvslam {
namespace optimize {
namespace g2o {

class imubias_vertex final : public ::g2o::BaseVertex<6, Vec6_t> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    imubias_vertex();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void setToOriginImpl() override { _estimate.fill(0); }

    void oplusImpl(const double* update) override
    {
        Eigen::Map<const Vec6_t> v(update);
        _estimate += v;
    }
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_LANDMARK_VERTEX_H
