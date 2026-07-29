// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <sycl/sycl.hpp>
#include <vector>

#include "gpu_context_manager.hpp"
#include "latency_stats.hpp"
#include "pipeline/tensor_view.hpp"
#include "pointpillars/pointpillars.hpp"

namespace bevfusion {

struct LidarConfig
{
    pointpillars::PointPillarsConfig pfe{};
    std::string device{GPUContextManager::gpuDeviceName()};
};

struct LidarOutputs
{
    TensorView scatter;
    int num_points{0};
};

class LidarBackbone {
public:
    LidarBackbone(const LidarConfig& config, sycl::queue& queue)
        : config_(config), queue_(queue), impl_(config.pfe, config.device, queue_),
          scatter_shape_{1,
                         static_cast<size_t>(config.pfe.num_features),
                         static_cast<size_t>(config.pfe.grid_y),
                         static_cast<size_t>(config.pfe.grid_x)}
    {
    }

    ~LidarBackbone() = default;

    LidarOutputs run(const std::vector<float>& points)
    {
        if (points.empty()) {
            throw std::runtime_error("LidarBackbone::run received empty point cloud");
        }

        float* scatter_dev = impl_.DetectAndGetPointer(
            points.data(),
            static_cast<int>(points.size() / 4));
        queue_.wait_and_throw();
        if (!scatter_dev) {
            throw std::runtime_error("PointPillars::DetectAndGetPointer returned null");
        }

        LidarOutputs out;
        out.num_points = static_cast<int>(points.size() / 4);
        out.scatter = TensorView::FromUSM(scatter_dev, scatter_shape_, TensorView::Location::USMDevice);
        return out;
    }

    const std::vector<size_t>& scatter_shape() const { return scatter_shape_; }
    void reset_latency_stats() { impl_.reset_latency_stats(); }
    const perfstats::LidarLatencyStats& latency_stats() const { return impl_.latency_stats(); }
    void print_latency_stats(std::ostream& os = std::cout, const std::string& label = "lidar") const
    {
        impl_.print_latency_stats(os, label);
    }

private:
    LidarConfig config_;
    sycl::queue& queue_;
    pointpillars::PointPillars impl_;
    std::vector<size_t> scatter_shape_;
};

}  // namespace bevfusion
