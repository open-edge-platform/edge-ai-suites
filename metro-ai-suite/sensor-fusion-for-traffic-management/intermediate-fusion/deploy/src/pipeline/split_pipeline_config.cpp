// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pipeline/split_pipeline_config.hpp"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <stdexcept>
#include <vector>

namespace bevfusion {
namespace {

std::string to_lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

void require_model_file(const std::filesystem::path& path, const char* role)
{
    if (!std::filesystem::exists(path)) {
        throw std::runtime_error(std::string("Missing ") + role + " model: " + path.string());
    }
    if (path.extension() == ".xml") {
        auto bin_path = path;
        bin_path.replace_extension(".bin");
        if (!std::filesystem::exists(bin_path)) {
            throw std::runtime_error(std::string("Missing ") + role + " model weights: " + bin_path.string());
        }
    }
}

struct PFEModelChoice {
    std::filesystem::path path;
    int max_voxels;
};

PFEModelChoice default_int8_pfe_model(const std::filesystem::path& model_dir, SplitPipelinePreset preset)
{
    (void)preset;
    return {model_dir / "quantized_lidar_pfe.xml", 7000};
}

std::vector<PFEModelChoice> default_fp32_pfe_candidates(const std::filesystem::path& model_dir)
{
    return {{model_dir / "lidar_pfe_v7000.onnx", 7000}, {model_dir / "lidar_pfe_v6000.onnx", 6000}};
}

}  // namespace

const SplitPipelinePresetDims& split_pipeline_preset_dims(SplitPipelinePreset preset)
{
    return dataset_preset_geometry(preset);
}

std::filesystem::path split_pipeline_default_model_dir(SplitPipelinePreset preset)
{
    return dataset_default_split_model_dir(preset);
}

bool split_pipeline_recompute_camera_metas(SplitPipelinePreset preset)
{
    return dataset_recompute_camera_metas(preset);
}

bool split_pipeline_is_battlemage_gpu(const std::string& gpu_name)
{
    const std::string lower = to_lower(gpu_name);
    return lower.find("b580") != std::string::npos ||
           lower.find("e20b") != std::string::npos ||
           lower.find("b60") != std::string::npos ||
           lower.find("e211") != std::string::npos;
}

SplitPipelineConfigBuild make_split_pipeline_config(const SplitPipelineConfigOptions& options)
{
    SplitPipelineConfigBuild build;
    PipelineConfig& cfg = build.config;
    const SplitPipelinePresetDims& dims = split_pipeline_preset_dims(options.preset);
    const std::filesystem::path model_dir = options.model_dir.empty()
        ? split_pipeline_default_model_dir(options.preset)
        : options.model_dir;
    if (!std::filesystem::is_directory(model_dir)) {
        throw std::runtime_error("Missing split-model directory: " + model_dir.string());
    }

    const char* camera_name = options.use_int8_camera ? "quantized_camera.xml" : "camera.backbone.onnx";
    const std::filesystem::path camera_path = model_dir / camera_name;
    require_model_file(camera_path, "camera");
    cfg.camera.cam.model_path = camera_path.string();
    cfg.camera.cam.use_gpu = true;
    // Always enable zero-copy. The camera export emits f32 [1,80,54,96] for
    // both FP32 and INT8 paths, so the USM remote-tensor binding is valid in
    // either case. Gating on !use_int8_camera forced a GPU→host→GPU round
    // trip of ~7 MB per frame (~1.5 ms PCIe + heap alloc). bev_cam.cpp has a
    // dtype guard that falls back to host-copy if a future xml emits non-f32.
    cfg.camera.cam.zero_copy_outputs = true;
    cfg.camera.geom.xbound = dims.xbound;
    cfg.camera.geom.ybound = dims.ybound;
    cfg.camera.geom.zbound = dims.zbound;
    cfg.camera.geom.dbound = dims.dbound;
    cfg.camera.geom.geometry_dim = types::Int3(dims.bev_side, dims.bev_side, 80);
    cfg.camera.geom.feat_width = dims.feat_width;
    cfg.camera.geom.feat_height = dims.feat_height;
    cfg.camera.geom.image_width = dims.image_width;
    cfg.camera.geom.image_height = dims.image_height;
    cfg.camera.geom.num_camera = 1;
    cfg.camera.camera_channels = 80;
    cfg.camera.depth_channels = 90;
    cfg.camera.feature_h = dims.feat_height;
    cfg.camera.feature_w = dims.feat_width;
    cfg.camera.bev_width = dims.bev_side;
    cfg.camera.bev_height = dims.bev_side;

    if (!options.device.empty()) {
        cfg.lidar.device = options.device;
    }
    const auto int8_pfe = default_int8_pfe_model(model_dir, options.preset);
    if (options.use_int8_pfe && std::filesystem::exists(int8_pfe.path)) {
        require_model_file(int8_pfe.path, "lidar PFE");
        cfg.lidar.pfe.pfe_model_file = int8_pfe.path.string();
        cfg.lidar.pfe.max_voxels = int8_pfe.max_voxels;
    } else {
        bool found_pfe = false;
        for (const auto& candidate : default_fp32_pfe_candidates(model_dir)) {
            if (!std::filesystem::exists(candidate.path)) {
                continue;
            }
            require_model_file(candidate.path, "lidar PFE");
            cfg.lidar.pfe.pfe_model_file = candidate.path.string();
            cfg.lidar.pfe.max_voxels = candidate.max_voxels;
            found_pfe = true;
            break;
        }
        if (!found_pfe) {
            throw std::runtime_error("Missing lidar PFE model under " + model_dir.string() +
                                     ": expected quantized_lidar_pfe.xml, lidar_pfe_v7000.onnx, or lidar_pfe_v6000.onnx");
        }
    }
    cfg.lidar.pfe.pc_range[0] = dims.pc_range_min[0];
    cfg.lidar.pfe.pc_range[1] = dims.pc_range_min[1];
    cfg.lidar.pfe.pc_range[2] = dims.pc_range_min[2];
    cfg.lidar.pfe.pc_range[3] = dims.pc_range_max[0];
    cfg.lidar.pfe.pc_range[4] = dims.pc_range_max[1];
    cfg.lidar.pfe.pc_range[5] = dims.pc_range_max[2];
    cfg.lidar.pfe.voxel_size[0] = 0.8f;
    cfg.lidar.pfe.voxel_size[1] = 0.8f;
    cfg.lidar.pfe.voxel_size[2] = 8.0f;
    cfg.lidar.pfe.max_num_points_per_voxel = 100;
    cfg.lidar.pfe.grid_x = dims.bev_side;
    cfg.lidar.pfe.grid_y = dims.bev_side;
    cfg.lidar.pfe.grid_z = 1;
    cfg.lidar.pfe.num_features = 64;

    build.effective_int8_fuser = options.use_int8_fuser;
    if (build.effective_int8_fuser && split_pipeline_is_battlemage_gpu(options.gpu_name)) {
        build.effective_int8_fuser = false;
        build.int8_fuser_disabled_for_device = true;
    }
    const char* fuser_name = build.effective_int8_fuser ? "quantized_fuser.xml" : "fuser.onnx";
    const char* head_name = options.use_int8_head ? "quantized_head.xml" : "head.onnx";
    const std::filesystem::path fuser_path = model_dir / fuser_name;
    const std::filesystem::path head_path = model_dir / head_name;
    require_model_file(fuser_path, "fuser");
    require_model_file(head_path, "head");
    cfg.fusion.fuser_model = fuser_path.string();
    cfg.fusion.head_model = head_path.string();
    cfg.fusion.camera_bev_shape = ov::Shape{1, 80, static_cast<size_t>(dims.bev_side), static_cast<size_t>(dims.bev_side)};
    cfg.fusion.lidar_bev_shape = ov::Shape{1, 64, static_cast<size_t>(dims.bev_side), static_cast<size_t>(dims.bev_side)};
    cfg.fusion.channels = {2, 1, 3, 2, 2, 5};
    cfg.fusion.filter_labels = options.filter_labels;
    cfg.fusion.post_params = PostProcessParams::bevfusionDefaults();
    cfg.fusion.post_params.voxel_size[0] = dims.split_post_voxel_size;
    cfg.fusion.post_params.voxel_size[1] = dims.split_post_voxel_size;
    cfg.fusion.post_params.out_size_factor = dims.split_post_out_size_factor;
    cfg.fusion.post_params.pc_range_min = dims.pc_range_min;
    cfg.fusion.post_params.pc_range_max = dims.pc_range_max;
    cfg.fusion.post_params.post_center_limit_range[0] = dims.post_center_min[0];
    cfg.fusion.post_params.post_center_limit_range[1] = dims.post_center_min[1];
    cfg.fusion.post_params.post_center_limit_range[2] = dims.post_center_min[2];
    cfg.fusion.post_params.post_center_limit_range[3] = dims.post_center_max[0];
    cfg.fusion.post_params.post_center_limit_range[4] = dims.post_center_max[1];
    cfg.fusion.post_params.post_center_limit_range[5] = dims.post_center_max[2];
    cfg.fusion.post_params.pre_max_size = 200;
    return build;
}

}  // namespace bevfusion
