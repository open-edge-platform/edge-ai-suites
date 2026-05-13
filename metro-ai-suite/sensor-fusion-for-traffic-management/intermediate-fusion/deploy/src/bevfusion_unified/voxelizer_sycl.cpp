// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "bevfusion_unified/voxelizer_sycl.hpp"
#include "common/voxelizer_utils.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

namespace bevfusion_unified {

namespace {

inline float AtomicFetchAddF(float* addr, float operand) {
    sycl::atomic_ref<float, sycl::memory_order::relaxed, sycl::memory_scope::device,
                     sycl::access::address_space::global_space> a(*addr);
    return a.fetch_add(operand);
}

void MakeVoxelHistoKernel(const float* dev_points, int num_points, int point_dim,
                          int grid_x, int grid_y, int grid_z,
                          float min_x, float min_y, float min_z,
                          float vx, float vy, float vz,
                          int max_pts, int* histo, float* voxel_sum,
                          sycl::nd_item<3> item) {
    const int idx = item.get_local_id(2) + item.get_group(2) * item.get_local_range().get(2);
    if (idx >= num_points) return;

    const float px = dev_points[idx * point_dim + 0];
    const float py = dev_points[idx * point_dim + 1];
    const float pz = dev_points[idx * point_dim + 2];
    const float pi = (point_dim >= 4) ? dev_points[idx * point_dim + 3] : 0.f;

    const int xi = sycl::floor((px - min_x) / vx);
    const int yi = sycl::floor((py - min_y) / vy);
    const int zi = sycl::floor((pz - min_z) / vz);

    if (xi < 0 || xi >= grid_x || yi < 0 || yi >= grid_y || zi < 0 || zi >= grid_z) return;

    const int cell = (zi * grid_y + yi) * grid_x + xi;
    const int count = bevfusion::voxelizer::atomic_fetch_add(&histo[cell], 1);
    if (count < max_pts) {
        float* sum = voxel_sum + cell * 4;
        AtomicFetchAddF(sum + 0, px);
        AtomicFetchAddF(sum + 1, py);
        AtomicFetchAddF(sum + 2, pz);
        AtomicFetchAddF(sum + 3, pi);
    }
}

void MakeVoxelIndexKernel(const int* histo, const float* voxel_sum,
                          int grid_x, int grid_y, int grid_z,
                          int max_voxels, int max_pts,
                          int* counter, int* indices, float* features,
                          int x, int y, int z) {
    const int cell = (z * grid_y + y) * grid_x + x;
    const int raw_count = histo[cell];
    if (raw_count == 0) return;

    const int slot = bevfusion::voxelizer::atomic_fetch_add(counter, 1);
    if (slot >= max_voxels) return;

    const int clamped = (raw_count < max_pts) ? raw_count : max_pts;
    const float denom = static_cast<float>(clamped > 0 ? clamped : 1);

    indices[slot * 4 + 0] = 0;
    indices[slot * 4 + 1] = x;
    indices[slot * 4 + 2] = y;
    indices[slot * 4 + 3] = z;

    const float* sum = voxel_sum + cell * 4;
    features[slot * 4 + 0] = sum[0] / denom;
    features[slot * 4 + 1] = sum[1] / denom;
    features[slot * 4 + 2] = sum[2] / denom;
    features[slot * 4 + 3] = sum[3] / denom;
}

}  // namespace

VoxelizerSYCL::VoxelizerSYCL(sycl::queue& queue, const VoxelizeConfig& cfg)
    : queue_(queue), cfg_(cfg) {
    grid_x_ = static_cast<int>(std::round((cfg_.pc_range_max[0] - cfg_.pc_range_min[0]) / cfg_.voxel_size[0]));
    grid_y_ = static_cast<int>(std::round((cfg_.pc_range_max[1] - cfg_.pc_range_min[1]) / cfg_.voxel_size[1]));
    grid_z_ = static_cast<int>(std::round((cfg_.pc_range_max[2] - cfg_.pc_range_min[2]) / cfg_.voxel_size[2]));

    std::cout << "[VoxelizerSYCL] grid=" << grid_x_ << "x" << grid_y_ << "x" << grid_z_
              << " max_voxels=" << cfg_.max_voxels << std::endl;
    allocate_();
}

VoxelizerSYCL::~VoxelizerSYCL() {
    try { free_(); } catch (...) {}
}

void VoxelizerSYCL::allocate_() {
    const size_t num_cells = static_cast<size_t>(grid_x_) * grid_y_ * grid_z_;
    voxel_count_histo_ = sycl::malloc_device<int>(num_cells, queue_);
    voxel_sum_         = sycl::malloc_device<float>(num_cells * 4, queue_);
    voxel_features_    = sycl::malloc_device<float>(static_cast<size_t>(cfg_.max_voxels) * 4, queue_);
    voxel_indices_     = sycl::malloc_device<int>(static_cast<size_t>(cfg_.max_voxels) * 4, queue_);
    dev_counter_       = sycl::malloc_device<int>(1, queue_);
}

void VoxelizerSYCL::free_() {
    auto rel = [&](auto*& p) { if (p) { sycl::free(p, queue_); p = nullptr; } };
    rel(voxel_count_histo_); rel(voxel_sum_);
    rel(voxel_features_); rel(voxel_indices_); rel(dev_counter_);
}

int VoxelizerSYCL::run(const float* points_device, int num_points) {
    if (!points_device || num_points <= 0) { host_voxel_count_ = 0; return 0; }

    const size_t num_cells = static_cast<size_t>(grid_x_) * grid_y_ * grid_z_;

    queue_.memset(voxel_count_histo_, 0, num_cells * sizeof(int));
    queue_.memset(voxel_sum_, 0, num_cells * 4 * sizeof(float));
    queue_.memset(dev_counter_, 0, sizeof(int));

    const int block = 128;
    const int num_block = bevfusion::voxelizer::div_up(num_points, block);
    int* histo_ptr = voxel_count_histo_;
    float* sum_ptr = voxel_sum_;
    const int pd = cfg_.in_channels;
    const int gx = grid_x_, gy = grid_y_, gz = grid_z_;
    const float mx = cfg_.pc_range_min[0], my = cfg_.pc_range_min[1], mz = cfg_.pc_range_min[2];
    const float vx = cfg_.voxel_size[0], vy = cfg_.voxel_size[1], vz = cfg_.voxel_size[2];
    const int max_pts = cfg_.max_num_points;

    queue_.submit([&](sycl::handler& h) {
        h.parallel_for(sycl::nd_range<3>(sycl::range<3>(1,1,num_block)*sycl::range<3>(1,1,block),
                                         sycl::range<3>(1,1,block)),
            [=](sycl::nd_item<3> item) {
                MakeVoxelHistoKernel(points_device, num_points, pd, gx, gy, gz,
                                     mx, my, mz, vx, vy, vz, max_pts, histo_ptr, sum_ptr, item);
            });
    });

    const int max_vox = cfg_.max_voxels;
    int* cnt = dev_counter_;
    int* idx = voxel_indices_;
    float* feat = voxel_features_;

    queue_.submit([&](sycl::handler& h) {
        h.parallel_for(sycl::range<3>{static_cast<size_t>(gz), static_cast<size_t>(gy), static_cast<size_t>(gx)},
            [=](sycl::id<3> it) {
                MakeVoxelIndexKernel(histo_ptr, sum_ptr, gx, gy, gz, max_vox, max_pts,
                                     cnt, idx, feat,
                                     static_cast<int>(it[2]), static_cast<int>(it[1]), static_cast<int>(it[0]));
            });
    });

    int counter_value = 0;
    queue_.memcpy(&counter_value, dev_counter_, sizeof(int)).wait();
    host_voxel_count_ = std::min(counter_value, cfg_.max_voxels);
    return host_voxel_count_;
}

}  // namespace bevfusion_unified
