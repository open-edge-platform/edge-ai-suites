// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "scale_vertex.h"

namespace openvslam {
namespace optimize {
namespace g2o {

scale_vertex::scale_vertex() : BaseVertex<1, double>() {}

bool scale_vertex::read(std::istream& is)
{
    is >> _estimate;
    return true;
}

bool scale_vertex::write(std::ostream& os) const
{
    const double scale = estimate();
    os << scale << " ";
    return os.good();
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
