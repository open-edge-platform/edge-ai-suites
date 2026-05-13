// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pointpillars/voxelizer.hpp"
#include "common/voxelizer_utils.hpp"

#include <cmath>
#include <cstdio>
#include <iostream>
#include <stdexcept>

namespace pointpillars {

namespace {

// Kernel 1: scatter each point into the cell's per-pillar buffer.
//   pillar_count[cell]         — running count of points in the cell
//   pillar_buffer[cell][n][c]  — raw (x, y, z, i) copied in order of arrival
// Points beyond max_num_points_per_voxel are dropped (matches mmdet3d).
void ScatterPointsKernel(const float* pts, int num_points, int point_dim,
                         int grid_x, int grid_y, int grid_z,
                         float min_x, float min_y, float min_z,
                         float vx, float vy, float vz,
                         int max_pts_per_voxel,
                         int* pillar_count, float* pillar_buffer,
                         sycl::nd_item<3> item) {
    const int idx = item.get_local_id(2)
                  + item.get_group(2) * item.get_local_range().get(2);
    if (idx >= num_points) return;

    const float px = pts[idx * point_dim + 0];
    const float py = pts[idx * point_dim + 1];
    const float pz = pts[idx * point_dim + 2];

    const int xi = static_cast<int>(sycl::floor((px - min_x) / vx));
    const int yi = static_cast<int>(sycl::floor((py - min_y) / vy));
    const int zi = static_cast<int>(sycl::floor((pz - min_z) / vz));

    if (xi < 0 || xi >= grid_x ||
        yi < 0 || yi >= grid_y ||
        zi < 0 || zi >= grid_z) return;

    // cell index — order doesn't matter for correctness as long as it's
    // consistent with the compact kernel below.
    const int cell = (zi * grid_y + yi) * grid_x + xi;

    // Reserve a slot in the dense pillar buffer.
    const int slot = bevfusion::voxelizer::atomic_fetch_add(&pillar_count[cell], 1);
    if (slot >= max_pts_per_voxel) return;

    // Copy raw point (x, y, z, intensity) into pillar_buffer[cell][slot]
    float* dst = pillar_buffer + (static_cast<size_t>(cell) * max_pts_per_voxel + slot) * point_dim;
    dst[0] = px;
    dst[1] = py;
    dst[2] = pz;
    if (point_dim >= 4) {
        dst[3] = pts[idx * point_dim + 3];
    }
    for (int k = 4; k < point_dim; ++k) {
        dst[k] = pts[idx * point_dim + k];
    }
}

// Kernel 2: compact active cells into a sparse voxel list.
//   coors[slot] = (0, x_idx, y_idx, z_idx)   ← NOTE: (batch, x, y, z)
//                                              matching mmdet3d Voxelization
//                                              + F.pad((1,0), value=batch).
//                                              See bev_0422_dev.md §29.4.
//   num_voxels[slot] = min(count, max_pts_per_voxel)
//   features[slot]   = pillar_buffer[cell]   (copied as-is; pad zero)
void CompactPillarsKernel(const int* pillar_count, const float* pillar_buffer,
                          int grid_x, int grid_y,
                          int max_voxels, int max_pts_per_voxel, int point_dim,
                          int* counter,
                          float* features, int* num_voxels, int* coors,
                          int x_idx, int y_idx, int z_idx) {
    const int cell = (z_idx * grid_y + y_idx) * grid_x + x_idx;
    const int raw_count = pillar_count[cell];
    if (raw_count == 0) return;

    const int slot = bevfusion::voxelizer::atomic_fetch_add(counter, 1);
    if (slot >= max_voxels) return;

    const int clamped = (raw_count < max_pts_per_voxel) ? raw_count : max_pts_per_voxel;

    // coors layout (batch=0, x_idx, y_idx, z_idx)
    coors[slot * 4 + 0] = 0;
    coors[slot * 4 + 1] = x_idx;
    coors[slot * 4 + 2] = y_idx;
    coors[slot * 4 + 3] = z_idx;

    num_voxels[slot] = clamped;

    const float* src = pillar_buffer
                     + (static_cast<size_t>(cell) * max_pts_per_voxel) * point_dim;
    float* dst = features
               + (static_cast<size_t>(slot) * max_pts_per_voxel) * point_dim;
    // Copy the used pillar points; padding region stays zeroed from memset.
    for (int n = 0; n < clamped; ++n) {
        const float* s = src + n * point_dim;
        float* d = dst + n * point_dim;
        for (int c = 0; c < point_dim; ++c) {
            d[c] = s[c];
        }
    }
}

}  // namespace

Voxelizer::Voxelizer(sycl::queue& queue, const VoxelizerConfig& config)
    : queue_(queue), config_(config) {
    const float range_x = config_.pc_range[3] - config_.pc_range[0];
    const float range_y = config_.pc_range[4] - config_.pc_range[1];
    const float range_z = config_.pc_range[5] - config_.pc_range[2];

    grid_x_ = static_cast<int>(std::round(range_x / config_.voxel_size[0]));
    grid_y_ = static_cast<int>(std::round(range_y / config_.voxel_size[1]));
    grid_z_ = static_cast<int>(std::round(range_z / config_.voxel_size[2]));

    if (grid_x_ <= 0 || grid_y_ <= 0 || grid_z_ <= 0) {
        throw std::runtime_error("Voxelizer: invalid grid size");
    }
    if (config_.point_dim < 3) {
        throw std::runtime_error("Voxelizer: point_dim must be >= 3");
    }

    std::cout << "[Voxelizer] pc_range=[" << config_.pc_range[0] << ","
              << config_.pc_range[1] << "," << config_.pc_range[2] << " -> "
              << config_.pc_range[3] << "," << config_.pc_range[4] << ","
              << config_.pc_range[5] << "] voxel_size=[" << config_.voxel_size[0]
              << "," << config_.voxel_size[1] << "," << config_.voxel_size[2]
              << "] grid=" << grid_x_ << "x" << grid_y_ << "x" << grid_z_
              << " max_voxels=" << config_.max_voxels
              << " max_pts_per_voxel=" << config_.max_num_points_per_voxel
              << " point_dim=" << config_.point_dim << std::endl;

    allocate_();
}

Voxelizer::~Voxelizer() {
    try { free_(); } catch (...) {}
}

void Voxelizer::allocate_() {
    const size_t num_cells = static_cast<size_t>(grid_x_) * grid_y_ * grid_z_;
    const size_t N = config_.max_num_points_per_voxel;
    const size_t C = config_.point_dim;
    const size_t V_max = config_.max_voxels;

    pillar_buffer_ = sycl::malloc_device<float>(num_cells * N * C, queue_);
    pillar_count_  = sycl::malloc_device<int>(num_cells, queue_);

    features_   = sycl::malloc_device<float>(V_max * N * C, queue_);
    num_voxels_ = sycl::malloc_device<int>(V_max, queue_);
    coors_      = sycl::malloc_device<int>(V_max * 4, queue_);

    dev_counter_ = sycl::malloc_device<int>(1, queue_);
}

void Voxelizer::free_() {
    auto rel = [&](auto*& p) { if (p) { sycl::free(p, queue_); p = nullptr; } };
    rel(pillar_buffer_); rel(pillar_count_);
    rel(features_); rel(num_voxels_); rel(coors_);
    rel(dev_counter_);
}

int Voxelizer::run(const float* points_device, int num_points) {
    if (!points_device || num_points <= 0) {
        host_voxel_count_ = 0;
        return 0;
    }

    const size_t num_cells = static_cast<size_t>(grid_x_) * grid_y_ * grid_z_;
    const size_t N = config_.max_num_points_per_voxel;
    const size_t C = config_.point_dim;
    const size_t V_max = config_.max_voxels;

    // Reset counters and output buffers. pillar_buffer_ stores scratch slots
    // that are rewritten before compaction, while features_ stays zero-padded
    // for the static PFE input contract.
    queue_.memset(pillar_count_, 0, num_cells * sizeof(int));
    queue_.memset(dev_counter_, 0, sizeof(int));
    queue_.memset(features_, 0, V_max * N * C * sizeof(float));
    queue_.memset(num_voxels_, 0, V_max * sizeof(int));
    queue_.memset(coors_, 0, V_max * 4 * sizeof(int));

    // Kernel 1: scatter points → pillar_buffer
    const int block = 128;
    const int num_block = bevfusion::voxelizer::div_up(num_points, block);
    const int point_dim = config_.point_dim;
    const int gx = grid_x_, gy = grid_y_, gz = grid_z_;
    const float mx = config_.pc_range[0], my = config_.pc_range[1], mz = config_.pc_range[2];
    const float vx = config_.voxel_size[0], vy = config_.voxel_size[1], vz = config_.voxel_size[2];
    const int max_pts = config_.max_num_points_per_voxel;
    int* pc_ptr = pillar_count_;
    float* pb_ptr = pillar_buffer_;

    queue_.submit([&](sycl::handler& h) {
        h.parallel_for(
            sycl::nd_range<3>(
                sycl::range<3>(1, 1, num_block) * sycl::range<3>(1, 1, block),
                sycl::range<3>(1, 1, block)),
            [=](sycl::nd_item<3> item) {
                ScatterPointsKernel(points_device, num_points, point_dim,
                                    gx, gy, gz, mx, my, mz, vx, vy, vz,
                                    max_pts, pc_ptr, pb_ptr, item);
            });
    });

    // Kernel 2: compact non-empty cells → features / num_voxels / coors
    const int V_max_int = config_.max_voxels;
    int* cnt = dev_counter_;
    float* feat = features_;
    int* nv = num_voxels_;
    int* idx = coors_;

    queue_.submit([&](sycl::handler& h) {
        h.parallel_for(
            sycl::range<3>{static_cast<size_t>(gz),
                           static_cast<size_t>(gy),
                           static_cast<size_t>(gx)},
            [=](sycl::id<3> it) {
                CompactPillarsKernel(pc_ptr, pb_ptr, gx, gy,
                                     V_max_int, max_pts, point_dim,
                                     cnt, feat, nv, idx,
                                     /*x_idx=*/static_cast<int>(it[2]),
                                     /*y_idx=*/static_cast<int>(it[1]),
                                     /*z_idx=*/static_cast<int>(it[0]));
            });
    });

    int counter_value = 0;
    queue_.memcpy(&counter_value, dev_counter_, sizeof(int)).wait();
    host_voxel_count_ = (counter_value < config_.max_voxels)
                            ? counter_value : config_.max_voxels;
    return host_voxel_count_;
}

}  // namespace pointpillars
