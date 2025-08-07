// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "imubias_vertex.h"

namespace openvslam {
namespace optimize {
namespace g2o {

imubias_vertex::imubias_vertex() : BaseVertex<6, Vec6_t>() {}

bool imubias_vertex::read(std::istream&) { return true; }

bool imubias_vertex::write(std::ostream& os) const { return os.good(); }

// gyrobias_vertex::gyrobias_vertex() : BaseVertex<3, Vec3_t>() {}

// bool gyrobias_vertex::read(std::istream& is) { return true; }

// bool gyrobias_vertex::write(std::ostream& os) const { return os.good(); }

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
