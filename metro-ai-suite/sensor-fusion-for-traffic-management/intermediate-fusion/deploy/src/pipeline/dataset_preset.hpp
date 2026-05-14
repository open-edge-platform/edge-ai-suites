// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "common/dtype.hpp"

#include <array>
#include <filesystem>

namespace bevfusion {

enum class DatasetPreset { V2X, KITTI };

struct DatasetPresetGeometry {
    const char* name;
    int image_width;
    int image_height;
    int feat_width;
    int feat_height;
    int bev_side;
    types::Float3 xbound;
    types::Float3 ybound;
    types::Float3 zbound;
    types::Float3 dbound;
    std::array<float, 3> pc_range_min;
    std::array<float, 3> pc_range_max;
    std::array<int, 3> unified_grid_size;
    float split_post_voxel_size;
    float split_post_out_size_factor;
    std::array<float, 3> post_center_min;
    std::array<float, 3> post_center_max;
};

const DatasetPresetGeometry& dataset_preset_geometry(DatasetPreset preset);
const char* dataset_preset_name(DatasetPreset preset);
std::filesystem::path dataset_default_split_model_dir(DatasetPreset preset);
std::filesystem::path dataset_default_unified_model_dir(DatasetPreset preset);
bool dataset_recompute_camera_metas(DatasetPreset preset);

}  // namespace bevfusion
