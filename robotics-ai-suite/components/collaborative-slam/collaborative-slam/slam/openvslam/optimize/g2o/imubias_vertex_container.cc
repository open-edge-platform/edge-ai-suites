// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "optimize/g2o/imubias_vertex_container.h"

namespace openvslam
{
namespace optimize
{
namespace g2o
{

imubias_vertex_container::imubias_vertex_container(
  const LandmarkID offset, const unsigned int num_reserve)
: offset_(offset)
{
  vtx_container_.reserve(num_reserve);
}

imubias_vertex * imubias_vertex_container::create_vertex(
  const LandmarkID id, const Vec6_t vec6, const bool is_constant)
{
  const auto vtx_id = landmarkID_to_vertexID(offset_ + id);
  auto vtx = new imubias_vertex();
  vtx->setId(vtx_id);
  vtx->setEstimate(vec6);
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
