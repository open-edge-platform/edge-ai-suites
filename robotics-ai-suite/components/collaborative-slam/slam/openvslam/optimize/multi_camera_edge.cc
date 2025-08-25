// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "multi_camera_edge.h"
#include <g2o/types/slam3d/isometry3d_mappings.h>
#include <g2o/types/slam3d/vertex_se3.h>
#include "optimize/g2o/sim3/shot_vertex.h"
#include <iostream>
#include <spdlog/spdlog.h>
#include <map>
namespace openvslam {
namespace optimize {

namespace g2o {

EdgeMultiCamera::EdgeMultiCamera() : ::g2o::BaseMultiEdge<7, ::g2o::Sim3>() { resize(3); }

void EdgeMultiCamera::computeError()
{
    const sim3::shot_vertex* v1 = static_cast<const sim3::shot_vertex*>(_vertices[0]);
    const sim3::shot_vertex* v2 = static_cast<const sim3::shot_vertex*>(_vertices[1]);
    const sim3::shot_vertex* camera_extrinsic = static_cast<const sim3::shot_vertex*>(_vertices[2]);

    const ::g2o::Sim3 C(_measurement);
    const ::g2o::Sim3 error_ = v2->estimate() * v1->estimate().inverse() * C * camera_extrinsic->estimate();

    _error = error_.log();
}

// Use for record this edge parameter, this function is called when we want to save th pose graph
bool EdgeMultiCamera::write(std::ostream& os) const
{
    (void)os;
    return false;
}

bool EdgeMultiCamera::read(std::istream& is)
{
    (void)is;
    return false;
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
