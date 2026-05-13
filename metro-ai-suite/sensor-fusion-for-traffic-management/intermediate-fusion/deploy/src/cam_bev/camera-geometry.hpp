/*
 * SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#ifndef __CAMERA_GEOMETRY_HPP__
#define __CAMERA_GEOMETRY_HPP__

#include <memory>
#include <sycl/sycl.hpp>
#include "common/dtype.hpp"
#include "fstream"
#include <cmath>
#include <algorithm>
namespace bevfusion {
namespace camera {

enum class FusionMethod{
  BEVFUSION  = 0,
  V2XFUSION  = 1
};
struct GeometryParameter {
  types::Float3 xbound;
  types::Float3 ybound;
  types::Float3 zbound;
  types::Float3 dbound;
  types::Int3 geometry_dim;  // w(x 128), h(y 128), c(z 80)
  unsigned int feat_width;
  unsigned int feat_height;
  unsigned int image_width;
  unsigned int image_height;
  unsigned int num_camera;

  FusionMethod fusion_method = FusionMethod::V2XFUSION; //default
};

inline GeometryParameter make_v2xfusion_geometry_parameter(unsigned int feat_width = 96,
                                                           unsigned int feat_height = 54,
                                                           unsigned int image_width = 1536,
                                                           unsigned int image_height = 864,
                                                           unsigned int num_camera = 1) {
  GeometryParameter param{};
  param.xbound = types::Float3(0.0f, 102.4f, 0.8f);
  param.ybound = types::Float3(-51.2f, 51.2f, 0.8f);
  param.zbound = types::Float3(-5.0f, 3.0f, 8.0f);
  param.dbound = types::Float3(-2.0f, 0.0f, 90.0f);
  param.geometry_dim = types::Int3(128, 128, 80);
  param.feat_width = feat_width;
  param.feat_height = feat_height;
  param.image_width = image_width;
  param.image_height = image_height;
  param.num_camera = num_camera;
  param.fusion_method = FusionMethod::V2XFUSION;
  return param;
}

class Geometry {
 public:
  virtual ~Geometry() = default;
  virtual types::Int3* intervals() = 0;
  virtual unsigned int num_intervals() = 0;

  virtual unsigned int* indices() = 0;
  virtual unsigned int num_indices() = 0;

  // You can call this function if you need to update the matrix
  // All matrix pointers must be on the host
  // img_aug_matrix is num_camera x 4 x 4 matrix on host
  // lidar2image    is num_camera x 4 x 4 matrix on host
  virtual void update(const float* camera2lidar, const float* camera_intrinsics, const float* img_aug_matrix,const float* denorms = nullptr,
                      sycl::queue* q = nullptr) = 0;

  // Consider releasing excess memory if you don't need to update the matrix
  // After freeing the memory, the update function call will raise a logical exception.
  virtual void free_excess_memory() = 0;
};

std::shared_ptr<Geometry> create_geometry(GeometryParameter param, sycl::queue& q);

};  // namespace camera
};  // namespace bevfusion

#endif  // __CAMERA_GEOMETRY_HPP__