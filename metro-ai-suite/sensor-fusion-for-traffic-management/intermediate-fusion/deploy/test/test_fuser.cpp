#include "bev_fuser.hpp"
#include "common.hpp"
#include "pipeline/split_pipeline_config.hpp"
#include "test_utils.hpp"
#include "gpu_context_manager.hpp"
#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

int main(int argc, char* argv[]) {
    if (argc > 7) {
        std::cerr << "Usage: " << argv[0]
                  << " [warmup] [iters] [fuser_model] [cam_bev_bin] [lidar_scatter_bin] [--fp32]" << std::endl;
        return -1;
    }

    // Defaults
    int warmup = 10;
    int iters = 100;
    std::string fuser_model = "../data/v2xfusion/pointpillars/quantized_fuser.xml";
    std::string cam_bev_bin_file = "../data/v2xfusion/dump_bins/bev_feats_000000.bin";
    std::string lidar_bin_file = "../data/v2xfusion/dump_bins/lidar_scatter_000000.bin";
    bool use_fp32 = false;
    // Pre-scan argv for --fp32 so we can pass it to initialize() before full arg parsing.
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--fp32") { use_fp32 = true; break; }
    }

    try {
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

        const bool explicit_fuser_model = args.size() >= 3;

        // CLI override order:
        //   args[0] warmup
        //   args[1] iters
        //   args[2] fuser_model
        //   args[3] cam_bev_bin
        //   args[4] lidar_scatter_bin
        if (args.size() >= 1) {
            try { warmup = std::max(0, std::stoi(args[0])); }
            catch (...) { std::cerr << "Invalid warmup value" << std::endl; return -1; }
        }
        if (args.size() >= 2) {
            try { iters = std::max(1, std::stoi(args[1])); }
            catch (...) { std::cerr << "Invalid iters value" << std::endl; return -1; }
        }
        if (args.size() >= 3) fuser_model = args[2];
        if (args.size() >= 4) cam_bev_bin_file = args[3];
        if (args.size() >= 5) lidar_bin_file = args[4];

        if (args.size() < 3) {
            fuser_model = use_fp32 ? "../data/v2xfusion/pointpillars/fuser.onnx"
                                  : "../data/v2xfusion/pointpillars/quantized_fuser.xml";
        }

        sycl::queue queue = create_opencl_queue();
        const std::string gpu_name = queue.get_device().get_info<sycl::info::device::name>();
        if (!use_fp32 && !explicit_fuser_model && bevfusion::split_pipeline_is_battlemage_gpu(gpu_name)) {
            std::cout << "Battlemage GPU (" << gpu_name
                      << "): using fuser.onnx instead of quantized_fuser.xml" << std::endl;
            fuser_model = "../data/v2xfusion/pointpillars/fuser.onnx";
        }

        auto& context_manager = GPUContextManager::getInstance();
        if (!context_manager.isInitialized()) {
            std::cout << "Initializing shared GPU context..." << std::endl;
            if (!context_manager.initialize(queue, use_fp32)) {
                std::cerr << "Failed to initialize GPU context manager" << std::endl;
                return -1;
            }
        }

        std::cout << "cam_bev_bin: " << cam_bev_bin_file << std::endl;
        std::cout << "lidar_bin:   " << lidar_bin_file << std::endl;
        std::cout << "fuser_model: " << fuser_model << std::endl;
        std::cout << "warmup:      " << warmup << std::endl;
        std::cout << "iters:       " << iters << std::endl;

        std::cout << "\n=== Reading Input Features ===" << std::endl;
        std::vector<float> camera_bev_feature = readCameraFeature(cam_bev_bin_file);
        std::vector<float> lidar_scatter_feature = readLidarFeature(lidar_bin_file);
        
        // Fuser pipeline
        std::cout << "\n=== Starting Fuser Inference ===" << std::endl;
        BEVFusionFuser fuser(fuser_model, queue, true);
        
        // Allocate device memory and copy data there to measure true inference cost
        const ov::Shape cam_shape{1, 80, 128, 128};
        const ov::Shape lidar_shape{1, 64, 128, 128};
        
        float* d_camera_bev_feature = sycl::malloc_device<float>(camera_bev_feature.size(), queue);
        float* d_lidar_scatter_feature = sycl::malloc_device<float>(lidar_scatter_feature.size(), queue);
        
        // Output device buffer
        const size_t output_size = 1 * 256 * 128 * 128; // batch * channel * height * width
        float* d_fused_output = sycl::malloc_device<float>(output_size, queue);
        
        queue.memcpy(d_camera_bev_feature, camera_bev_feature.data(), camera_bev_feature.size() * sizeof(float)).wait();
        queue.memcpy(d_lidar_scatter_feature, lidar_scatter_feature.data(), lidar_scatter_feature.size() * sizeof(float)).wait();

        auto fuser_input = fuser.createFuserInputFromPointers(
            d_camera_bev_feature,
            d_lidar_scatter_feature,
            cam_shape, 
            lidar_shape
        );
        fuser_input.fused_output_ptr = d_fused_output;

        // Warmup (not timed)
        for (int i = 0; i < warmup; ++i) {
            (void)fuser.fuseFeatures(fuser_input);
        }

        // Wait for all warmup tasks to finish
        queue.wait_and_throw();

        // Timed iterations
        std::vector<double> times_ms;
        times_ms.reserve(static_cast<size_t>(iters));

        for (int i = 0; i < iters; ++i) {
            const auto t0 = std::chrono::steady_clock::now();
            auto fused_output = fuser.fuseFeatures(fuser_input);
            queue.wait_and_throw();
            const auto t1 = std::chrono::steady_clock::now();
            const double ms = static_cast<double>(
                std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count()) / 1000.0;
            times_ms.push_back(ms);

            // One-time sanity dump (only first timed iter)
            if (i == 0) {
                const size_t fuser_size = std::accumulate(fused_output.fused_shape.begin(), fused_output.fused_shape.end(), 1ULL, std::multiplies<size_t>());
                std::vector<float> fuser_data(fuser_size);
                if (fused_output.fused_features_ptr != nullptr) {
                    queue.memcpy(fuser_data.data(), fused_output.fused_features_ptr, fuser_size * sizeof(float)).wait();
                } else if (!fused_output.fused_features.empty()) {
                    fuser_data = fused_output.fused_features;
                } else {
                    throw std::runtime_error("No fused output data available");
                }

                std::cout << "Fused output shape: " << fused_output.fused_shape << std::endl;
                std::cout << "Fused output size: " << fuser_data.size() << " floats" << std::endl;
                if (!fuser_data.empty()) {
                    std::cout << "Sample fused values (first 10): ";
                    for (int k = 0; k < std::min(10, static_cast<int>(fuser_data.size())); ++k) {
                        std::cout << fuser_data[static_cast<size_t>(k)] << " ";
                    }
                    std::cout << std::endl;
                }
            }
        }

        sycl::free(d_camera_bev_feature, queue);
        sycl::free(d_lidar_scatter_feature, queue);
        sycl::free(d_fused_output, queue);

        const double sum_ms = std::accumulate(times_ms.begin(), times_ms.end(), 0.0);
        const double avg_ms = sum_ms / static_cast<double>(times_ms.size());
        const double min_ms = *std::min_element(times_ms.begin(), times_ms.end());
        const double max_ms = *std::max_element(times_ms.begin(), times_ms.end());

        std::cout << "[perf] iters=" << iters
                  << ", avg=" << avg_ms << " ms"
                  << ", min=" << min_ms << " ms"
                  << ", max=" << max_ms << " ms" << std::endl;

        std::cout << "Fuser inference completed successfully!" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return -1;
    }
    
    return 0;
}