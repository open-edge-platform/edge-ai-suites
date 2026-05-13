// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "pointpillars/pointpillars.hpp"
#include "test_utils.hpp"

#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Args {
    std::string dataset_path{"../data/v2xfusion/dataset"};
    std::string sample_id;
    std::string points_path;
    int num_points{0};
    std::filesystem::path model_dir{"../data/v2xfusion/pointpillars"};
    std::filesystem::path pfe_path;
    std::filesystem::path out_dir{"/tmp/pointpillars_out"};
    std::string device{GPUContextManager::gpuDeviceName()};
    bool dump_outputs{false};
    bool use_int8{true};
    bool pfe_path_set{false};
    int max_voxels{0};
};

void print_usage(const char* argv0)
{
    std::cerr << "Usage: " << argv0 << " [--dataset DATASET] [--sample ID] "
              << "[--points POINTS.bin --num N] [--model-dir DIR] [--pfe MODEL] "
              << "[--int8] [--device DEVICE] [--max-voxels N] [--dump] [--out-dir DIR]\n";
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
        } else if (key == "--dataset") {
            args.dataset_path = next();
        } else if (key == "--sample") {
            args.sample_id = next();
        } else if (key == "--points") {
            args.points_path = next();
        } else if (key == "--num") {
            args.num_points = std::atoi(next().c_str());
        } else if (key == "--model-dir") {
            args.model_dir = next();
        } else if (key == "--pfe") {
            args.pfe_path = next();
            args.pfe_path_set = true;
        } else if (key == "--out-dir") {
            args.out_dir = next();
            args.dump_outputs = true;
        } else if (key == "--dump") {
            args.dump_outputs = true;
        } else if (key == "--device") {
            args.device = next();
        } else if (key == "--int8") {
            args.use_int8 = true;
        } else if (key == "--fp32") {
            args.use_int8 = false;
        } else if (key == "--max-voxels") {
            args.max_voxels = std::atoi(next().c_str());
        } else {
            throw std::runtime_error("Unknown arg: " + key);
        }
    }

    if (!args.points_path.empty() && args.num_points <= 0) {
        throw std::runtime_error("--points mode requires --num");
    }
    args.pfe_path = choose_pfe_model(args);
    return args;
}

std::vector<float> load_points_bin(const std::string& path, int num_points, int point_dim)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("cannot open " + path);
    }
    std::vector<float> points(static_cast<size_t>(num_points) * point_dim);
    file.read(reinterpret_cast<char*>(points.data()),
              static_cast<std::streamsize>(points.size() * sizeof(float)));
    if (!file) {
        throw std::runtime_error("short read on " + path);
    }
    return points;
}

std::vector<float> load_points_dataset(const Args& args)
{
    KittiDataLoader loader(args.dataset_path, KittiDataLoader::createKittiConfig());
    std::string sample_id = args.sample_id;
    if (sample_id.empty()) {
        auto samples = loader.getSampleList();
        if (samples.empty()) {
            throw std::runtime_error("no samples found under " + args.dataset_path);
        }
        sample_id = samples.front();
    }

    auto points = loader.getPointCloud(sample_id);
    if (points.empty()) {
        throw std::runtime_error("empty point cloud for sample " + sample_id);
    }
    std::cout << "Loaded sample " << sample_id << " with " << (points.size() / 4) << " points\n";
    return points;
}

void dump_bin(const std::filesystem::path& path, const std::vector<float>& values)
{
    std::ofstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("cannot write " + path.string());
    }
    file.write(reinterpret_cast<const char*>(values.data()),
               static_cast<std::streamsize>(values.size() * sizeof(float)));
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
        std::cout << "SYCL device: "
                  << queue.get_device().get_info<sycl::info::device::name>() << "\n";

        const std::string pfe_string = args.pfe_path.string();
        const bool use_fp32_context = !args.use_int8 && has_suffix(pfe_string, ".onnx");
        auto& ctx = GPUContextManager::getInstance();
        if (!ctx.isInitialized()) {
            if (!ctx.initialize(queue, use_fp32_context)) {
                std::cerr << "Failed to initialize GPUContextManager\n";
                return 1;
            }
        }

        pointpillars::PointPillarsConfig cfg;
        cfg.pfe_model_file = pfe_string;
        if (args.max_voxels > 0) {
            cfg.max_voxels = args.max_voxels;
        } else {
            const int inferred_max_voxels = infer_max_voxels_from_pfe_path(pfe_string);
            if (inferred_max_voxels > 0) {
                cfg.max_voxels = inferred_max_voxels;
            }
        }

        std::cout << "PFE model: " << cfg.pfe_model_file << "\n";
        pointpillars::PointPillars pointpillars(cfg, args.device, queue);

        std::vector<float> points = args.points_path.empty()
            ? load_points_dataset(args)
            : load_points_bin(args.points_path, args.num_points, cfg.point_dim);
        const int num_points = static_cast<int>(points.size() / cfg.point_dim);

        const size_t canvas_size = static_cast<size_t>(cfg.num_features) * cfg.grid_x * cfg.grid_y;
        std::vector<float> scattered(canvas_size, 0.0f);

        pointpillars::PointPillarsTiming timing;
        const auto t0 = std::chrono::steady_clock::now();
        pointpillars.Detect(points.data(), num_points, scattered.data(), &timing);
        const auto t1 = std::chrono::steady_clock::now();
        const double total_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

        const bool all_finite = std::all_of(scattered.begin(), scattered.end(), [](float value) {
            return std::isfinite(value);
        });
        const size_t non_zero = static_cast<size_t>(std::count_if(scattered.begin(), scattered.end(), [](float value) {
            return std::fabs(value) > 1e-7f;
        }));
        if (!all_finite) {
            throw std::runtime_error("scattered feature contains NaN or Inf");
        }
        if (non_zero == 0) {
            throw std::runtime_error("scattered feature is all zero");
        }

        std::cout << "timing: pre=" << timing.preprocess_ms << "ms pfe=" << timing.pfe_ms
              << "ms scatter=" << timing.scatter_ms << "ms\n";
        std::cout << "non_zero=" << non_zero << " / " << scattered.size() << "\n";
        std::cout << "[perf] frames=1, avg_lidar=" << total_ms << " ms\n";
        pointpillars.print_latency_stats();

        if (args.dump_outputs) {
            std::filesystem::create_directories(args.out_dir);
            dump_bin(args.out_dir / "scattered_feature.bin", scattered);
            std::ofstream meta(args.out_dir / "meta.txt");
            meta << "shape=1," << cfg.num_features << "," << cfg.grid_y << "," << cfg.grid_x << "\n";
            meta << "layout=NCHW\n";
            std::cout << "Wrote " << scattered.size() * sizeof(float)
                      << " bytes to " << (args.out_dir / "scattered_feature.bin").string() << "\n";
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << "\n";
        return 1;
    }
}
