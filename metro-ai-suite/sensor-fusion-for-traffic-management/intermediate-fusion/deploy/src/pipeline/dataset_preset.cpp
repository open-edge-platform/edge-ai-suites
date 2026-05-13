// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pipeline/dataset_preset.hpp"

namespace bevfusion {
namespace {

const DatasetPresetGeometry kV2X = {
    "v2x",
    1536, 864,
    96, 54,
    128,
    types::Float3(0.0f, 102.4f, 0.8f),
    types::Float3(-51.2f, 51.2f, 0.8f),
    types::Float3(-5.0f, 3.0f, 8.0f),
    types::Float3(-2.0f, 0.0f, 90.0f),
    {0.0f, -51.2f, -5.0f},
    {102.4f, 51.2f, 3.0f},
    {1024, 1024, 40},
    0.2f,
    4.0f,
    {0.0f, -51.2f, -5.0f},
    {102.4f, 51.2f, 3.0f},
};

const DatasetPresetGeometry kKITTI = {
    "kitti",
    1280, 384,
    80, 24,
    100,
    types::Float3(0.0f, 80.0f, 0.8f),
    types::Float3(-40.0f, 40.0f, 0.8f),
    types::Float3(-5.0f, 3.0f, 8.0f),
    types::Float3(-2.0f, 0.0f, 90.0f),
    {0.0f, -40.0f, -5.0f},
    {80.0f, 40.0f, 3.0f},
    {800, 800, 40},
    0.1f,
    8.0f,
    {0.0f, -45.0f, -5.0f},
    {85.0f, 45.0f, 3.0f},
};

}  // namespace

const DatasetPresetGeometry& dataset_preset_geometry(DatasetPreset preset)
{
    return preset == DatasetPreset::KITTI ? kKITTI : kV2X;
}

const char* dataset_preset_name(DatasetPreset preset)
{
    return dataset_preset_geometry(preset).name;
}

std::filesystem::path dataset_default_split_model_dir(DatasetPreset preset)
{
    return preset == DatasetPreset::KITTI
        ? std::filesystem::path{"../data/kitti/pointpillars"}
        : std::filesystem::path{"../data/v2xfusion/pointpillars"};
}

std::filesystem::path dataset_default_unified_model_dir(DatasetPreset preset)
{
    return preset == DatasetPreset::KITTI
        ? std::filesystem::path{"../data/kitti/second"}
        : std::filesystem::path{"../data/v2xfusion/second"};
}

bool dataset_recompute_camera_metas(DatasetPreset preset)
{
    return preset == DatasetPreset::KITTI;
}

}  // namespace bevfusion
