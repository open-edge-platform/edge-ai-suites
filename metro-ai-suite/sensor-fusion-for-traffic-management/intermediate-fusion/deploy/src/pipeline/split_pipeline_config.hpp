// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "pipeline/bevfusion.hpp"
#include "pipeline/dataset_preset.hpp"

#include <filesystem>
#include <string>
#include <vector>

namespace bevfusion {

using SplitPipelinePreset = DatasetPreset;
using SplitPipelinePresetDims = DatasetPresetGeometry;

struct SplitPipelineConfigOptions {
    SplitPipelinePreset preset{SplitPipelinePreset::V2X};
    std::filesystem::path model_dir;
    std::string device;
    std::string gpu_name;
    bool use_int8_camera{false};
    bool use_int8_pfe{false};
    bool use_int8_fuser{false};
    bool use_int8_head{false};
    std::vector<int> filter_labels{7, 8};
};

struct SplitPipelineConfigBuild {
    PipelineConfig config{};
    bool effective_int8_fuser{false};
    bool int8_fuser_disabled_for_device{false};
};

const SplitPipelinePresetDims& split_pipeline_preset_dims(SplitPipelinePreset preset);
std::filesystem::path split_pipeline_default_model_dir(SplitPipelinePreset preset);
bool split_pipeline_recompute_camera_metas(SplitPipelinePreset preset);
bool split_pipeline_is_battlemage_gpu(const std::string& gpu_name);
SplitPipelineConfigBuild make_split_pipeline_config(const SplitPipelineConfigOptions& options);

}  // namespace bevfusion
