// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Standalone SYCL voxelizer for PointPillars-based BEVFusion.
//
// Output tensors are locked by PillarFeatureNet.forward(features, num_voxels,
// coors) from the training repo
//   mmdet3d/models/backbones/pillar_encoder.py:188-230
//
//   features   [max_voxels, max_num_points_per_voxel, point_dim]  float32
//   num_voxels [max_voxels]                                       int32
//   coors      [max_voxels, 4]                                    int32
//              layout: (batch_idx=0, x_idx, y_idx, z_idx)
//
// IMPORTANT: coors layout is (batch, x, y, z), NOT (batch, z, y, x) like the
// CenterPoint voxelizer. This matches mmdet3d Voxelization + F.pad((1,0)).
// See bev_0422_dev.md §29.4 for the experimental verification.

#pragma once

#include <array>
#include <sycl/sycl.hpp>

namespace pointpillars {

struct VoxelizerConfig {
    // Physical extents:
    //   pc_range = [x_min, y_min, z_min, x_max, y_max, z_max]
    std::array<float, 6> pc_range    = {0.0f, -51.2f, -5.0f, 102.4f, 51.2f, 3.0f};
    std::array<float, 3> voxel_size  = {0.8f, 0.8f, 8.0f};
    int max_num_points_per_voxel      = 100;
    int max_voxels                    = 12000;
    int point_dim                     = 4;  // (x, y, z, intensity)
};

class Voxelizer {
public:
    Voxelizer(sycl::queue& queue, const VoxelizerConfig& config);
    ~Voxelizer();

    Voxelizer(const Voxelizer&) = delete;
    Voxelizer& operator=(const Voxelizer&) = delete;

    // Runs the voxelizer on a raw point cloud (device USM buffer).
    // Returns the actual number of voxels V (V <= max_voxels).
    // After this call, features_device / num_voxels_device / coors_device
    // are populated with V valid rows and zero-padded above V.
    int run(const float* points_device, int num_points);

    // Tensor accessors — names match the ONNX input tensor names so the
    // pipeline layer can bind them 1:1:
    //   req.set_tensor("features",   voxelizer.features_device_tensor());
    //   req.set_tensor("num_voxels", voxelizer.num_voxels_device_tensor());
    //   req.set_tensor("coors",      voxelizer.coors_device_tensor());
    float* features_device()  const { return features_; }   // [max_voxels, N, C]
    int*   num_voxels_device() const { return num_voxels_; } // [max_voxels]
    int*   coors_device()     const { return coors_; }       // [max_voxels, 4]

    int num_voxels() const { return host_voxel_count_; }
    int max_voxels() const { return config_.max_voxels; }
    int max_num_points_per_voxel() const { return config_.max_num_points_per_voxel; }
    int point_dim() const { return config_.point_dim; }

private:
    void allocate_();
    void free_();

    sycl::queue& queue_;
    VoxelizerConfig config_;

    int grid_x_{0}, grid_y_{0}, grid_z_{0};

    // Scratch: dense grid-sized buffers.
    //   pillar_buffer_ [num_cells, N, C]  float32 — accumulated raw points per cell
    //   pillar_count_  [num_cells]        int32   — point count per cell
    float* pillar_buffer_{nullptr};
    int*   pillar_count_{nullptr};

    // Output (compacted) buffers. All sized to max_voxels.
    float* features_{nullptr};   // [max_voxels, N, C]
    int*   num_voxels_{nullptr};  // [max_voxels]
    int*   coors_{nullptr};       // [max_voxels, 4]

    int*   dev_counter_{nullptr};  // single int — atomic sparse slot counter
    int    host_voxel_count_{0};
};

}  // namespace pointpillars
