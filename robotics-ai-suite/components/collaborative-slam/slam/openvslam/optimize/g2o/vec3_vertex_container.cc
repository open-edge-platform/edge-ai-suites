// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "optimize/g2o/vec3_vertex_container.h"

namespace openvslam
{
namespace optimize
{
namespace g2o
{

vec3_vertex_container::vec3_vertex_container(
  const LandmarkID offset, const unsigned int num_reserve)
: offset_(offset)
{
  vtx_container_.reserve(num_reserve);
}

vec3_vertex * vec3_vertex_container::create_vertex(
  const LandmarkID id, const Vec3_t vec3, const bool is_constant)
{
  // vertex
  const auto vtx_id = landmarkID_to_vertexID(offset_ + id);
  auto vtx = new vec3_vertex();
  vtx->setId(vtx_id);
  vtx->setEstimate(vec3);
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
