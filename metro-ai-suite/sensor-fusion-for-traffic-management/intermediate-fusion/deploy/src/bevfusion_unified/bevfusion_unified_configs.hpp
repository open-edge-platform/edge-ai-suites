// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// V2XFusion-specific configuration structures.  Common types (BBox3D,
// Transform4x4, CalibField_t, PostProcessParams, etc.) are reused from
// the shared configs.hpp.

#pragma once

#include "configs.hpp"
#include "gpu_context_manager.hpp"

#include <array>
#include <string>

namespace bevfusion_unified {

struct VoxelizeConfig {
    float voxel_size[3] = {0.1f, 0.1f, 0.2f};
    float pc_range_min[3] = {0.0f, -51.2f, -5.0f};
    float pc_range_max[3] = {102.4f, 51.2f, 3.0f};
    int   grid_size[3]    = {1024, 1024, 40};
    int   max_num_points  = 10;
    int   max_voxels      = 160000;
    bool  reduce_mean     = true;
    int   in_channels     = 4;
};

struct ImagePreprocessConfig {
    int target_h = 864;
    int target_w = 1536;
    float mean[3]  = {123.675f, 116.28f,  103.53f};
    float std_[3]  = {58.395f,  57.12f,   57.375f};
    bool  bgr_to_rgb = true;
    bool  do_normalize = true;
    bool  use_ov_preprocess = false;
};

struct BevPoolV2Config {
    int max_intervals = 10499;
    int max_geometry  = 1086935;
    float xbound[3] = {0.0f, 102.4f, 0.8f};
    float ybound[3] = {-51.2f, 51.2f, 0.8f};
    float zbound[3] = {-5.0f, 3.0f, 8.0f};
    float dbound[3] = {-2.0f, 0.0f, 90.0f};
    int feat_width  = 96;
    int feat_height = 54;
    int image_width  = 1536;
    int image_height = 864;
    int geom_dim[3]  = {128, 128, 80};
    int num_camera   = 1;
};

struct RunnerConfig {
    std::string onnx_path;
    std::string device{GPUContextManager::gpuDeviceName()};
    bool use_fp32_inference = false;
    bool enable_profiling = false;

    VoxelizeConfig voxelize;
    ImagePreprocessConfig image;
    BevPoolV2Config bevpool;
    PostProcessParams post;

    RunnerConfig() {
        post = PostProcessParams::bevfusionDefaults();
    }
};

}  // namespace bevfusion_unified
