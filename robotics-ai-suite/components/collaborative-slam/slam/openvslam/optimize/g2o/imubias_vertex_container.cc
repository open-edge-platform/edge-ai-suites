// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/imubias_vertex_container.h"

namespace openvslam {
namespace optimize {
namespace g2o {

imubias_vertex_container::imubias_vertex_container(const LandmarkID offset, const unsigned int num_reserve)
    : offset_(offset)
{
    vtx_container_.reserve(num_reserve);
}

imubias_vertex* imubias_vertex_container::create_vertex(const LandmarkID id, const Vec6_t vec6,
                                                        const bool is_constant)
{
    // vertexを作成
    const auto vtx_id = landmarkID_to_vertexID(offset_ + id);
    auto vtx = new imubias_vertex();
    vtx->setId(vtx_id);
    vtx->setEstimate(vec6);
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
