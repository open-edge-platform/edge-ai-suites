// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "pipeline/lidar_backbone.hpp"
#include "test_utils.hpp"

#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Args {
    std::string dataset_path;
    std::filesystem::path model_dir{"../data/v2xfusion/pointpillars"};
    std::filesystem::path pfe_path;
    std::string device{GPUContextManager::gpuDeviceName()};
    int warmup{1};
    int num_samples{-1};
    bool use_int8{true};
    bool pfe_path_set{false};
};

void print_usage(const char* argv0)
{
    std::cerr << "Usage: " << argv0 << " <dataset_path> [pfe_model] [warmup] "
              << "[--model-dir DIR] [--pfe MODEL] [--device DEVICE] "
              << "[--num-samples N] [--int8] [--fp32]\n";
}

bool has_suffix(const std::string& value, const std::string& suffix)
{
    return value.size() >= suffix.size() &&
           value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

std::filesystem::path choose_pfe_model(const Args& args)
{
    if (args.pfe_path_set) {
        return args.pfe_path;
    }
    if (args.use_int8) {
        const auto int8_path = args.model_dir / "quantized_lidar_pfe.xml";
        if (std::filesystem::exists(int8_path)) {
            return int8_path;
        }
    }
    for (const auto& candidate : {args.model_dir / "lidar_pfe_v7000.onnx", args.model_dir / "lidar_pfe_v6000.onnx"}) {
        if (std::filesystem::exists(candidate)) {
            return candidate;
        }
    }
    throw std::runtime_error("Missing lidar PFE model under " + args.model_dir.string());
}

int infer_max_voxels_from_pfe_path(const std::string& pfe_path)
{
    if (pfe_path.find("v6000") != std::string::npos) {
        return 6000;
    }
    if (pfe_path.find("v7000") != std::string::npos) {
        return 7000;
    }
    if (pfe_path.find("quantized_lidar_pfe") != std::string::npos) {
        return 7000;
    }
    return 0;
}

Args parse_args(int argc, char** argv)
{
    Args args;
    std::vector<std::string> positional;
    positional.reserve(static_cast<size_t>(argc));
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error(key + " requires a value");
            }
            return argv[++i];
        };

        if (key == "--help" || key == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else if (key == "--model-dir") {
            args.model_dir = next();
        } else if (key == "--pfe") {
            args.pfe_path = next();
            args.pfe_path_set = true;
        } else if (key == "--device") {
            args.device = next();
        } else if (key == "--num-samples") {
            args.num_samples = std::atoi(next().c_str());
        } else if (key == "--int8") {
            args.use_int8 = true;
        } else if (key == "--fp32") {
            args.use_int8 = false;
        } else {
            positional.push_back(key);
        }
    }

    if (positional.empty()) {
        throw std::runtime_error("dataset_path is required");
    }
    if (positional.size() > 3) {
        throw std::runtime_error("too many positional arguments");
    }
    args.dataset_path = positional[0];
    if (positional.size() >= 2) {
        args.pfe_path = positional[1];
        args.pfe_path_set = true;
    }
    if (positional.size() >= 3) {
        args.warmup = std::max(0, std::atoi(positional[2].c_str()));
    }
    args.pfe_path = choose_pfe_model(args);
    return args;
}

void validate_scatter(const std::vector<float>& scatter)
{
    const bool all_finite = std::all_of(scatter.begin(), scatter.end(), [](float value) {
        return std::isfinite(value);
    });
    if (!all_finite) {
        throw std::runtime_error("scatter contains NaN or Inf");
    }
    const size_t non_zero = static_cast<size_t>(std::count_if(scatter.begin(), scatter.end(), [](float value) {
        return std::fabs(value) > 1e-7f;
    }));
    if (non_zero == 0) {
        throw std::runtime_error("scatter is all zero");
    }
    std::cout << "scatter non_zero=" << non_zero << " / " << scatter.size() << "\n";
}

}  // namespace

int main(int argc, char** argv)
{
    Args args;
    try {
        args = parse_args(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        print_usage(argv[0]);
        return 2;
    }

    try {
        sycl::queue queue = create_opencl_queue();
        const std::string pfe_string = args.pfe_path.string();
        const bool use_fp32_context = !args.use_int8 && has_suffix(pfe_string, ".onnx");
        auto& context_manager = GPUContextManager::getInstance();
        if (!context_manager.isInitialized()) {
            if (!context_manager.initialize(queue, use_fp32_context)) {
                std::cerr << "Failed to initialize GPUContextManager\n";
                return 1;
            }
        }

        bevfusion::LidarConfig config;
        config.device = args.device;
        config.pfe.pfe_model_file = pfe_string;
        const int inferred_max_voxels = infer_max_voxels_from_pfe_path(pfe_string);
        if (inferred_max_voxels > 0) {
            config.pfe.max_voxels = inferred_max_voxels;
        }

        std::cout << "Config: dataset='" << args.dataset_path << "' pfe='"
                  << config.pfe.pfe_model_file << "' warmup=" << args.warmup << "\n";
        bevfusion::LidarBackbone lidar(config, queue);

        KittiDataLoader loader(args.dataset_path, KittiDataLoader::createKittiConfig());
        auto samples = loader.getSampleList();
        if (samples.empty()) {
            throw std::runtime_error("no samples found under " + args.dataset_path);
        }
        if (args.num_samples > 0 && static_cast<size_t>(args.num_samples) < samples.size()) {
            samples.resize(static_cast<size_t>(args.num_samples));
        }

        if (args.warmup > 0) {
            auto warmup_points = loader.getPointCloud(samples.front());
            for (int i = 0; i < args.warmup; ++i) {
                (void)lidar.run(warmup_points);
            }
        }
        lidar.reset_latency_stats();

        std::vector<double> times_ms;
        times_ms.reserve(samples.size());
        bool validated = false;
        for (const auto& sample_id : samples) {
            auto points = loader.getPointCloud(sample_id);
            if (points.empty()) {
                std::cerr << "Empty point cloud for " << sample_id << "\n";
                continue;
            }

            const auto t0 = std::chrono::steady_clock::now();
            auto output = lidar.run(points);
            const auto t1 = std::chrono::steady_clock::now();
            times_ms.push_back(std::chrono::duration<double, std::milli>(t1 - t0).count());
            std::cout << "sample=" << sample_id << " points=" << output.num_points
                      << " scatter_numel=" << output.scatter.numel() << "\n";

            if (!validated) {
                validate_scatter(output.scatter.to_host(&queue));
                validated = true;
            }
        }

        if (times_ms.empty()) {
            std::cout << "[perf] frames=0\n";
            return 0;
        }

        const double sum = std::accumulate(times_ms.begin(), times_ms.end(), 0.0);
        const auto [min_it, max_it] = std::minmax_element(times_ms.begin(), times_ms.end());
        std::cout << "[perf] frames=" << times_ms.size()
                  << ", avg_lidar=" << (sum / static_cast<double>(times_ms.size()))
                  << " ms, min=" << *min_it << " ms, max=" << *max_it << " ms\n";
        lidar.print_latency_stats();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << "\n";
        return 1;
    }
}
