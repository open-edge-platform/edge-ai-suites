// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// PointPillars Scatter — adapts the NEW PFE ONNX output layout [V, C]
// (row-major, one voxel per row) directly.
//
// Older pointpillars/scatter.cpp assumes PFE output [C, V] (channel-major,
// striding by V). With the decoupled voxelizer + new PFE ONNX we keep the
// natural PyTorch layout [V, C], avoiding a transpose.

#pragma once

#include <sycl/sycl.hpp>

namespace pointpillars {

class Scatter {
public:
    Scatter(int num_features, int grid_x, int grid_y, sycl::queue& queue);

    // Fills scattered_feature[C, grid_y, grid_x] from:
    //   coors        [max_voxels, 4] int32   — (batch=0, x_idx, y_idx, z_idx)
    //   pfe_output   [V, num_features]  float32
    //   pillar_count V (actual voxels to scatter)
    //
    // scattered_feature must be pre-zeroed by the caller.
    void run(int pillar_count,
             const int* coors,
             const float* pfe_output,
             float* scattered_feature);

private:
    int num_features_;
    int grid_x_;
    int grid_y_;
    sycl::queue& queue_;
};

}  // namespace pointpillars
