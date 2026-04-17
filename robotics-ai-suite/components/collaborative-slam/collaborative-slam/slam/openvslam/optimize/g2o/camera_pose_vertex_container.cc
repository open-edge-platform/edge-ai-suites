// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "camera_pose_vertex_container.h"

namespace openvslam
{
namespace optimize
{
namespace g2o
{

camera_pose_vertex_container::camera_pose_vertex_container(
  const KeyframeID offset, const unsigned int num_reserve)
: offset_(offset)
{
  vtx_container_.reserve(num_reserve);
}

camera_pose_vertex * camera_pose_vertex_container::create_vertex(
  const KeyframeID id, const Mat44_t T, const bool is_constant)
{
  // vertex
  const auto vtx_id = keyframeID_to_vertexID(offset_ + id);
  auto vtx = new camera_pose_vertex();
  vtx->setId(vtx_id);
  vtx->setEstimate(T);
  vtx->setFixed(is_constant);
  vtx->setMarginalized(false);
  // database
  vtx_container_[id] = vtx;
  // max ID
  if (max_vtx_id_ < vtx_id) {
    max_vtx_id_ = vtx_id;
  }

  return vtx;
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
