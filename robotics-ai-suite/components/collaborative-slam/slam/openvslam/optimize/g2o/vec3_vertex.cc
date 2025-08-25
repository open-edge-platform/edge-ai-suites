// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "vec3_vertex.h"

namespace openvslam {
namespace optimize {
namespace g2o {

vec3_vertex::vec3_vertex() : BaseVertex<3, Vec3_t>() {}

bool vec3_vertex::read(std::istream& is)
{
    Vec3_t lv;
    for (unsigned int i = 0; i < 3; ++i) {
        is >> _estimate(i);
    }
    return true;
}

bool vec3_vertex::write(std::ostream& os) const
{
    const Vec3_t pos_w = estimate();
    for (unsigned int i = 0; i < 3; ++i) {
        os << pos_w(i) << " ";
    }
    return os.good();
}


}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
