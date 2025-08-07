// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/vec3_vertex_container.h"

namespace openvslam {
namespace optimize {
namespace g2o {

vec3_vertex_container::vec3_vertex_container(const LandmarkID offset, const unsigned int num_reserve)
    : offset_(offset)
{
    vtx_container_.reserve(num_reserve);
}

vec3_vertex* vec3_vertex_container::create_vertex(const LandmarkID id, const Vec3_t vec3, const bool is_constant)
{
    // vertexを作成
    const auto vtx_id = landmarkID_to_vertexID(offset_ + id);
    auto vtx = new vec3_vertex();
    vtx->setId(vtx_id);
    vtx->setEstimate(vec3);
    vtx->setFixed(is_constant);
    vtx->setMarginalized(false);
    // databaseに登録
    vtx_container_[id] = vtx;
    // max IDを更新
    if (max_vtx_id_ < vtx_id) {
        max_vtx_id_ = vtx_id;
    }
    // 作成したvertexをreturn
    return vtx;
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
