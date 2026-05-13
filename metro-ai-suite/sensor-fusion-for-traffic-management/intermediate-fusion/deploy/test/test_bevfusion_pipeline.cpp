// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "common/dtype.hpp"
#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "pipeline/bevfusion.hpp"
#include "pipeline/split_pipeline_config.hpp"
#include "test_utils.hpp"

#include <sycl/sycl.hpp>

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Args {
    std::string dataset_path;
    bevfusion::SplitPipelinePreset preset{bevfusion::SplitPipelinePreset::V2X};
    std::filesystem::path model_dir{"../data/v2xfusion/pointpillars"};
    std::string device{GPUContextManager::gpuDeviceName()};
    int num_samples{1};
    int warmup{1};
    bool use_int8{true};
    bool model_dir_set{false};
};

void print_usage(const char* argv0)
{
    std::cerr << "Usage: " << argv0 << " <dataset_path> [--preset v2x|kitti] [--model-dir DIR] "
              << "[--num-samples N] [--warmup N] [--device DEVICE] [--int8] [--fp32]\n";
}

Args parse_args(int argc, char** argv)
{
    Args args;
    std::vector<std::string> positional;
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
        } else if (key == "--preset") {
            const std::string value = next();
            if (value == "v2x" || value == "dair-v2x" || value == "V2X") {
                args.preset = bevfusion::SplitPipelinePreset::V2X;
            } else if (value == "kitti" || value == "KITTI" || value == "kitti360" || value == "KITTI360") {
                args.preset = bevfusion::SplitPipelinePreset::KITTI;
            } else {
                throw std::runtime_error("unknown preset: " + value);
            }
        } else if (key == "--model-dir") {
            args.model_dir = next();
            args.model_dir_set = true;
        } else if (key == "--num-samples") {
            args.num_samples = std::atoi(next().c_str());
        } else if (key == "--warmup") {
            args.warmup = std::max(0, std::atoi(next().c_str()));
        } else if (key == "--device") {
            args.device = next();
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
    if (positional.size() > 1) {
        throw std::runtime_error("too many positional arguments");
    }
    args.dataset_path = positional.front();
    if (args.num_samples <= 0) {
        args.num_samples = 1;
    }
    if (!args.model_dir_set) {
        args.model_dir = bevfusion::split_pipeline_default_model_dir(args.preset);
    }
    return args;
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
        auto& context_manager = GPUContextManager::getInstance();
        if (!context_manager.isInitialized()) {
            if (!context_manager.initialize(queue, !args.use_int8)) {
                std::cerr << "Failed to initialize GPUContextManager\n";
                return 1;
            }
        }

        bevfusion::SplitPipelineConfigOptions cfg_options;
        cfg_options.preset = args.preset;
        cfg_options.model_dir = args.model_dir;
        cfg_options.device = args.device;
        cfg_options.gpu_name = queue.get_device().get_info<sycl::info::device::name>();
        cfg_options.use_int8_camera = args.use_int8;
        cfg_options.use_int8_pfe = args.use_int8;
        cfg_options.use_int8_fuser = args.use_int8;
        cfg_options.use_int8_head = args.use_int8;
        auto cfg_build = bevfusion::make_split_pipeline_config(cfg_options);
        if (cfg_build.int8_fuser_disabled_for_device) {
            std::cout << "Battlemage GPU (" << cfg_options.gpu_name
                      << "): using fuser.onnx instead of quantized_fuser.xml\n";
        }
        bevfusion::PipelineConfig cfg = cfg_build.config;
        const auto& dims = bevfusion::split_pipeline_preset_dims(args.preset);
        std::cout << "preset=" << dims.name << "\n";
        std::cout << "dataset=" << args.dataset_path << "\n";
        std::cout << "camera=" << cfg.camera.cam.model_path << "\n";
        std::cout << "pfe=" << cfg.lidar.pfe.pfe_model_file << "\n";
        std::cout << "fuser=" << cfg.fusion.fuser_model << "\n";
        std::cout << "head=" << cfg.fusion.head_model << "\n";

        bevfusion::BEVFusionPipeline pipeline(cfg, queue);
        KittiDataLoader loader(args.dataset_path, KittiDataLoader::createKittiConfig());
        auto samples = loader.getSampleList();
        if (samples.empty()) {
            throw std::runtime_error("no samples found under " + args.dataset_path);
        }
        if (static_cast<size_t>(args.num_samples) < samples.size()) {
            samples.resize(static_cast<size_t>(args.num_samples));
        }

        if (args.warmup > 0) {
            Data_t sample = loader.getData(samples.front());
            bool recompute = true;
            for (int i = 0; i < args.warmup; ++i) {
                (void)pipeline.run(sample.img, sample.lidar, sample.calib, "P2", 0.0f, recompute);
                recompute = false;
            }
        }
        pipeline.reset_perf_stats();
        pipeline.reset_latency_stats();

        bool recompute_camera_metas = true;
        bool saw_boxes = false;
        for (const auto& sample_id : samples) {
            Data_t sample = loader.getData(sample_id);
            if (sample.img.empty() || sample.lidar.empty()) {
                throw std::runtime_error("empty image or lidar for sample " + sample_id);
            }
            auto boxes = pipeline.run(sample.img, sample.lidar, sample.calib, "P2", 0.0f, recompute_camera_metas);
            recompute_camera_metas = false;
            saw_boxes = saw_boxes || !boxes.empty();
            std::cout << sample_id << ": " << boxes.size() << " boxes\n";
        }

        if (!saw_boxes) {
            throw std::runtime_error("pipeline produced no boxes for all tested samples");
        }

        pipeline.print_perf_stats();
        pipeline.lidar().print_latency_stats();
        pipeline.camera_bev().print_latency_stats();
        pipeline.fusion().print_latency_stats();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << "\n";
        return 1;
    }
}
