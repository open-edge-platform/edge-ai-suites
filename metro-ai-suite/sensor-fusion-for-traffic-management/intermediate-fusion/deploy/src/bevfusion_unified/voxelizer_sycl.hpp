// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Histogram-based SYCL voxelizer for V2XFusion (ported from bev_latest).
// Two-kernel pipeline: histogram accumulation + sparse compaction.
// All outputs stay in device USM for zero-copy OV inference.

#pragma once

#include "bevfusion_unified/bevfusion_unified_configs.hpp"
#include <sycl/sycl.hpp>

namespace bevfusion_unified {

class VoxelizerSYCL {
public:
    VoxelizerSYCL(sycl::queue& queue, const VoxelizeConfig& cfg);
    ~VoxelizerSYCL();

    VoxelizerSYCL(const VoxelizerSYCL&) = delete;
    VoxelizerSYCL& operator=(const VoxelizerSYCL&) = delete;

    int run(const float* points_device, int num_points);

    float* voxel_features_device() const { return voxel_features_; }
    int*   voxel_indices_device()  const { return voxel_indices_; }
    int    num_voxels() const { return host_voxel_count_; }

private:
    void allocate_();
    void free_();

    sycl::queue& queue_;
    VoxelizeConfig cfg_;

    int grid_x_{0}, grid_y_{0}, grid_z_{0};

    int*   voxel_count_histo_{nullptr};
    float* voxel_sum_{nullptr};
    float* voxel_features_{nullptr};
    int*   voxel_indices_{nullptr};
    int*   dev_counter_{nullptr};
    int    host_voxel_count_{0};
};

}  // namespace bevfusion_unified
