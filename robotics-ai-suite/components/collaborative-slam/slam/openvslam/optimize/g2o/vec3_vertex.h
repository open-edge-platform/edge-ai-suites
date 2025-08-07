// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_VEC3_VERTEX_H
#define OPENVSLAM_OPTIMIZER_G2O_VEC3_VERTEX_H

#include "type.h"

#include <g2o/core/base_vertex.h>

namespace openvslam {
namespace optimize {
namespace g2o {

class vec3_vertex final : public ::g2o::BaseVertex<3, Vec3_t> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    vec3_vertex();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void setToOriginImpl() override { _estimate.fill(0); }

    void oplusImpl(const double* update) override
    {
        Eigen::Map<const Vec3_t> v(update);
        _estimate += v;
    }
};

typedef vec3_vertex velocity_vertex;
typedef vec3_vertex accelbias_vertex;
typedef vec3_vertex gyrobias_vertex;

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_LANDMARK_VERTEX_H
