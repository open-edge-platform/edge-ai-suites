// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/landmark_vertex_container.h"

namespace openvslam {
namespace optimize {
namespace g2o {

landmark_vertex_container::landmark_vertex_container(const LandmarkID offset, const unsigned int num_reserve)
    : offset_(offset)
{
    vtx_container_.reserve(num_reserve);
}

landmark_vertex* landmark_vertex_container::create_vertex(const LandmarkID id, const Vec3_t& pos_w,
                                                          const bool is_constant)
{
    // vertexを作成
    const auto vtx_id = landmarkID_to_vertexID(offset_ + id);
    auto vtx = new landmark_vertex();
    vtx->setId(vtx_id);
    vtx->setEstimate(pos_w);
    vtx->setFixed(is_constant);
    vtx->setMarginalized(true);
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
