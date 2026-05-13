// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// PointPillars: decoupled voxelization + PFE ONNX.
//
// Pipeline:
//   raw point cloud  [N, 4]
//     → Voxelizer.run()
//     → (features[V,100,4], num_voxels[V], coors[V,4])
//     → PFE ONNX or IR from data/<dataset>/pointpillars/
//     → pillar_features [V, 64]
//     → Scatter
//     → scattered_feature [C=64, grid_y, grid_x]
//
// The public Detect* API returns the same BEV scatter tensor consumed by the
// split BEVFusion fuser.

#pragma once

#include <memory>
#include <string>
#include <sycl/sycl.hpp>
#include <openvino/openvino.hpp>

#include "pointpillars/voxelizer.hpp"
#include "pointpillars/scatter.hpp"
#include "latency_stats.hpp"

namespace pointpillars {

struct PointPillarsConfig {
    // Decoupled PFE model with inputs: features, num_voxels, coors.
    std::string pfe_model_file{"../data/v2xfusion/pointpillars/lidar_pfe_v7000.onnx"};

    // Geometry — must match training config (camera+pointpillar/resnet34/default.yaml).
    float pc_range[6] = {0.0f, -51.2f, -5.0f, 102.4f, 51.2f, 3.0f};
    float voxel_size[3] = {0.8f, 0.8f, 8.0f};

    int max_voxels = 12000;
    int max_num_points_per_voxel = 100;
    int point_dim = 4;

    int num_features = 64;  // PFE output channels
    int grid_x = 128;
    int grid_y = 128;
    int grid_z = 1;
};

struct PointPillarsTiming {
    double preprocess_ms{0.0};
    double pfe_ms{0.0};
    double scatter_ms{0.0};

    double total_ms() const {
        return preprocess_ms + pfe_ms + scatter_ms;
    }
};

class PointPillars {
public:
    PointPillars(const PointPillarsConfig& config,
                 const std::string& device,
                 sycl::queue& queue);
    ~PointPillars();

    PointPillars(const PointPillars&) = delete;
    PointPillars& operator=(const PointPillars&) = delete;

    // End-to-end detect. scattered_feature is a host buffer;
    // timing receives this call's [preprocess, pfe, scatter] timings.
    void Detect(const float* in_points_array, int in_num_points,
                float* scattered_feature, PointPillarsTiming* timing = nullptr);
    void Detect(const float* in_points_array, int in_num_points,
                float* scattered_feature, size_t* dur);

    // Same as Detect but returns the device pointer of the scattered_feature,
    // without copying back to host (used when the downstream fuser/head also
    // run on the same device).
    float* DetectAndGetPointer(const float* in_points_array, int in_num_points,
                               PointPillarsTiming* timing = nullptr);
    float* DetectAndGetPointer(const float* in_points_array, int in_num_points,
                               size_t* dur);

    void reset_latency_stats() { latency_.reset(); }
    const perfstats::LidarLatencyStats& latency_stats() const { return latency_; }
    void print_latency_stats(std::ostream& os = std::cout,
                             const std::string& label = "lidar") const {
        latency_.print(os, label);
    }

    sycl::queue& getSYCLQueue() { return queue_; }
    float* getGPUScatteredFeaturePtr() { return dev_scattered_feature_; }
    size_t getScatteredFeatureSize() const {
        return static_cast<size_t>(cfg_.num_features)
             * cfg_.grid_y * cfg_.grid_x;
    }
    ov::Shape getScatteredFeatureShape() const {
        return ov::Shape{1, static_cast<size_t>(cfg_.num_features),
                            static_cast<size_t>(cfg_.grid_y),
                            static_cast<size_t>(cfg_.grid_x)};
    }

private:
    PointPillarsConfig cfg_;
    const std::string device_;
    sycl::queue& queue_;

    std::unique_ptr<Voxelizer> voxelizer_;
    std::unique_ptr<Scatter> scatter_;

    // Raw point-cloud device buffer (reused across frames, grown on demand).
    float* dev_points_{nullptr};
    int    dev_points_capacity_{0};

    // PFE output buffer — sized for max_voxels for allocation, reshaped per frame.
    float* pfe_output_{nullptr};  // [max_voxels, num_features]

    // Scatter BEV buffer [num_features, grid_y, grid_x].
    float* dev_scattered_feature_{nullptr};

    // OpenVINO state.
    ov::CompiledModel pfe_compiled_;
    ov::InferRequest  pfe_request_;
    // When true, the PFE ONNX has fully static input shapes (V == max_voxels);
    // tensors are bound once in the ctor and reused. When false, each frame
    // does set_tensor() with the actual V.
    bool pfe_is_static_{false};
    int  pfe_static_V_{0};

    perfstats::LidarLatencyStats latency_;

    void allocate_();
    void free_();
    void setup_pfe_network_();
    void bind_static_tensors_();
    void run_pfe_(int V);
};

}  // namespace pointpillars
