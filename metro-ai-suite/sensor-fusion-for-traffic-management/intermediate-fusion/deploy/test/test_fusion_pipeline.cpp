#include "pipeline/fusion_backbone.hpp"

#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

#include "common.hpp"
#include "gpu_context_manager.hpp"
#include "pipeline/split_pipeline_config.hpp"
#include "test_utils.hpp"
#include <sycl/sycl.hpp>

static size_t shape_numel(const ov::Shape& s) {
    return ov::shape_size(s);
}

int main(int argc, char* argv[]) {
    std::string data_root = "../data/v2xfusion";
    bool use_host_inputs = false;
    int warmup = 1;
    int iters = 10;

    // Usage:
    //   ./test_fusion_pipeline [data_root] [warmup] [iters] [host|usm] [--fp32]
    // Examples:
    //   ./test_fusion_pipeline
    //   ./test_fusion_pipeline ../data/v2xfusion 1 10 host
    //   ./test_fusion_pipeline ../data/v2xfusion 5 50 usm
    //   ./test_fusion_pipeline ../data/v2xfusion 1 10 usm --fp32
    bool use_fp32 = false;

    std::vector<std::string> args;
    args.reserve(static_cast<size_t>(argc));
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--fp32") {
            use_fp32 = true;
            continue;
        }
        args.push_back(arg);
    }

    if (args.size() > 4) {
        std::cerr << "Usage: " << argv[0] << " [data_root] [warmup] [iters] [host|usm] [--fp32]" << std::endl;
        return -1;
    }
    if (args.size() >= 1) {
        data_root = args[0];
    }

    std::string dataset_path = data_root + "/dataset";

    sycl::queue queue = create_opencl_queue();
    const std::string gpu_name = queue.get_device().get_info<sycl::info::device::name>();

    auto& context_manager = GPUContextManager::getInstance();
    if (!context_manager.isInitialized()) {
        std::cout << "Initializing shared GPU context..." << std::endl;
        if (!context_manager.initialize(queue, use_fp32)) {
            std::cerr << "Failed to initialize GPU context manager" << std::endl;
            return -1;
        }
    }

    try {
        // Parse optional mode from last arg.
        // Then parse warmup/iters from remaining args.
        int effective_argc = static_cast<int>(args.size()) + 1;
        if (effective_argc >= 3) {
            const std::string last = args[effective_argc - 2];
            if (last == "host") {
                use_host_inputs = true;
                --effective_argc;
            } else if (last == "usm") {
                use_host_inputs = false;
                --effective_argc;
            }
        }

        // Backward compat: allow `./test_fusion_pipeline <data_root> host|usm`
        if (effective_argc == 3) {
            const std::string maybe_mode = args[1];
            if (maybe_mode == "host") {
                use_host_inputs = true;
                effective_argc = 2;
            } else if (maybe_mode == "usm") {
                use_host_inputs = false;
                effective_argc = 2;
            }
        }

        // argv[2] -> warmup, argv[3] -> iters (if present after stripping mode)
        if (effective_argc >= 3) {
            warmup = std::max(0, std::stoi(args[1]));
        }
        if (effective_argc >= 4) {
            iters = std::max(1, std::stoi(args[2]));
        }

        bevfusion::DetectionFusionConfig cfg;
        bool use_int8_fuser = !use_fp32;
        if (use_int8_fuser && bevfusion::split_pipeline_is_battlemage_gpu(gpu_name)) {
            std::cout << "Battlemage GPU (" << gpu_name
                      << "): using fuser.onnx instead of quantized_fuser.xml" << std::endl;
            use_int8_fuser = false;
        }
        cfg.fuser_model = use_int8_fuser ? (data_root + "/pointpillars/quantized_fuser.xml")
                                         : (data_root + "/pointpillars/fuser.onnx");
        cfg.head_model = use_fp32 ? (data_root + "/pointpillars/head.onnx")
                      : (data_root + "/pointpillars/quantized_head.xml");

        std::cout << "\n=== Loading Input Features ===" << std::endl;
        // const std::string cam_bev_bin = data_root + "/cam_bev_feature.bin";
        // const std::string lidar_bin = data_root + "/lidar_feature.bin";
        const std::string cam_bev_bin = data_root + "/dump_bins/bev_feats_000000.bin";
        const std::string lidar_bin = data_root + "/dump_bins/lidar_scatter_000000.bin";

        std::vector<float> cam_bev = readCameraFeature(cam_bev_bin);
        std::vector<float> lidar_bev = readLidarFeature(lidar_bin);

        const size_t cam_expected = shape_numel(cfg.camera_bev_shape);
        const size_t lidar_expected = shape_numel(cfg.lidar_bev_shape);

        if (cam_bev.size() != cam_expected) {
            throw std::runtime_error("cam_bev_feature size mismatch: got " + std::to_string(cam_bev.size()) +
                                     ", expected " + std::to_string(cam_expected));
        }
        if (lidar_bev.size() != lidar_expected) {
            throw std::runtime_error("lidar_feature size mismatch: got " + std::to_string(lidar_bev.size()) +
                                     ", expected " + std::to_string(lidar_expected));
        }

        std::cout << "Camera BEV elems: " << cam_bev.size() << ", Lidar BEV elems: " << lidar_bev.size() << std::endl;

        float* cam_dev = nullptr;
        float* lidar_dev = nullptr;

        bevfusion::TensorView cam_view;
        bevfusion::TensorView lidar_view;

        if (use_host_inputs) {
            std::cout << "\n=== Using HOST inputs (forces host-staging path) ===" << std::endl;
            cam_view = bevfusion::TensorView::FromHost(cam_bev.data(), {cfg.camera_bev_shape.begin(), cfg.camera_bev_shape.end()});
            lidar_view = bevfusion::TensorView::FromHost(lidar_bev.data(), {cfg.lidar_bev_shape.begin(), cfg.lidar_bev_shape.end()});
        } else {
            std::cout << "\n=== Using USM DEVICE inputs (zero-copy path) ===" << std::endl;
            cam_dev = sycl::malloc_device<float>(cam_bev.size(), queue);
            lidar_dev = sycl::malloc_device<float>(lidar_bev.size(), queue);
            if (!cam_dev || !lidar_dev) {
                throw std::runtime_error("Failed to allocate USM device buffers for inputs");
            }
            queue.memcpy(cam_dev, cam_bev.data(), cam_bev.size() * sizeof(float)).wait();
            queue.memcpy(lidar_dev, lidar_bev.data(), lidar_bev.size() * sizeof(float)).wait();

            // queue.memset(cam_dev, 0, cam_bev.size() * sizeof(float)).wait();  // Zero out BEV features

            cam_view = bevfusion::TensorView::FromUSM(cam_dev, {cfg.camera_bev_shape.begin(), cfg.camera_bev_shape.end()},
                                                     bevfusion::TensorView::Location::USMDevice);
            lidar_view = bevfusion::TensorView::FromUSM(lidar_dev, {cfg.lidar_bev_shape.begin(), cfg.lidar_bev_shape.end()},
                                                       bevfusion::TensorView::Location::USMDevice);
        }

        std::cout << "\n=== Initializing DetectionFusion ===" << std::endl;
        bevfusion::DetectionFusion fusion(cfg, queue);

        std::cout << "\nWarmup: " << warmup << " iteration(s)" << std::endl;
        for (int i = 0; i < warmup; ++i) {
            (void)fusion.run(cam_view, lidar_view);
        }

        // Do not include warmup in latency stats
        fusion.reset_latency_stats();

        std::cout << "\nMeasured: " << iters << " iteration(s)" << std::endl;
        std::vector<double> total_ms;
        total_ms.reserve(iters);

        size_t last_boxes = 0;
        for (int i = 0; i < iters; ++i) {
            const auto t0 = std::chrono::steady_clock::now();
            auto boxes = fusion.run(cam_view, lidar_view);
            const auto t1 = std::chrono::steady_clock::now();
            last_boxes = boxes.size();

            const double ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t1 - t0).count();
            total_ms.push_back(ms);
            std::cout << "[iter " << (i + 1) << "] total=" << ms << " ms, boxes=" << boxes.size() << std::endl;
        }

        const double sum = std::accumulate(total_ms.begin(), total_ms.end(), 0.0);
        const double avg = sum / static_cast<double>(total_ms.size());
        const auto [mn_it, mx_it] = std::minmax_element(total_ms.begin(), total_ms.end());

        std::cout << "\n=== Latency Summary ===" << std::endl;
        std::cout << "Mode: " << (use_host_inputs ? "host" : "usm") << std::endl;
        std::cout << "Iters: " << iters << ", Boxes(last): " << last_boxes << std::endl;
        std::cout << "Total latency (ms): avg=" << avg << ", min=" << *mn_it << ", max=" << *mx_it << std::endl;

        fusion.print_latency_stats();

        if (cam_dev) sycl::free(cam_dev, queue);
        if (lidar_dev) sycl::free(lidar_dev, queue);

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return -1;
    }

    return 0;
}
