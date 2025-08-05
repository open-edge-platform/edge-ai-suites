// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/se3/shot_vertex_container.h"
#include "util/converter.h"

namespace openvslam {
namespace optimize {
namespace g2o {
namespace se3 {

shot_vertex_container::shot_vertex_container(const KeyframeID offset, const unsigned int num_reserve)
    : offset_(offset)
{
    vtx_container_.reserve(num_reserve);
}

shot_vertex* shot_vertex_container::create_vertex(const KeyframeID id, const Mat44_t& cam_pose_cw,
                                                  const bool is_constant)
{
    // vertexを作成
    const auto vtx_id = keyframeID_to_vertexID(offset_ + id);
    auto vtx = new shot_vertex();
    vtx->setId(vtx_id);
    vtx->setEstimate(util::converter::to_g2o_SE3(cam_pose_cw));
    vtx->setFixed(is_constant);
    // databaseに登録
    vtx_container_[id] = vtx;
    // max IDを更新
    if (max_vtx_id_ < vtx_id) {
        max_vtx_id_ = vtx_id;
    }
    // 作成したvertexをreturn
    return vtx;
}

}  // namespace se3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
