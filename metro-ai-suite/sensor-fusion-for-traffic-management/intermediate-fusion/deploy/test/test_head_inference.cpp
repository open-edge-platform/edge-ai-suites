#include "bev_head.hpp"
#include "gpu_context_manager.hpp"
#include "test_utils.hpp"

#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

#include <sycl/sycl.hpp>

// Main function with Head inference example
int main(int argc, char* argv[]) {
    if (argc > 6) {
        std::cerr << "Usage: " << argv[0] << " [warmup] [iters] [head_model] [input_bin] [--fp32]" << std::endl;
        return -1;
    }

    // Defaults
    int warmup = 10;
    int iters = 100;
    std::string head_model = "../data/v2xfusion/pointpillars/quantized_head.xml";
    std::string input_bin = "../data/v2xfusion/dump_bins/fuser_middle_000000.bin";
    bool use_fp32 = false;

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

        if (args.size() >= 1) warmup = std::max(0, std::stoi(args[0]));
        if (args.size() >= 2) iters = std::max(1, std::stoi(args[1]));
        if (args.size() >= 3) head_model = args[2];
        if (args.size() >= 4) input_bin = args[3];

        if (args.size() < 3) {
            head_model = use_fp32 ? "../data/v2xfusion/pointpillars/head.onnx"
                                 : "../data/v2xfusion/pointpillars/quantized_head.xml";
        }
    } catch (const std::exception& e) {
        std::cerr << "Invalid args: " << e.what() << std::endl;
        std::cerr << "Usage: " << argv[0] << " [warmup] [iters] [head_model] [input_bin] [--fp32]" << std::endl;
        return -1;
    }

    sycl::queue queue = create_opencl_queue();
    auto& context_manager = GPUContextManager::getInstance();
    if (!context_manager.isInitialized()) {
        std::cout << "Initializing shared GPU context..." << std::endl;
        if (!context_manager.initialize(queue, use_fp32)) {
            std::cerr << "Failed to initialize GPU context manager" << std::endl;
            return -1;
        }
    }
    
    try {
        std::cout << "head_model: " << head_model << std::endl;
        std::cout << "input_bin: " << input_bin << std::endl;
        std::cout << "warmup:    " << warmup << std::endl;
        std::cout << "iters:     " << iters << std::endl;

        // Head pipeline
        std::cout << "\n=== Starting Head Inference ===" << std::endl;
        BEVFusionHead head(head_model, queue, true); // Use GPU inference
        
        // Print model output information
        head.printOutputInfo();
        
        // Create Head input (read fuser features from bin file)
        auto head_input = head.createHeadInputFromBin(input_bin);

        // Warmup (not timed)
        std::cout << "\nWarmup: " << warmup << " iteration(s)" << std::endl;
        for (int i = 0; i < warmup; ++i) {
            (void)head.inferHead(head_input);
            queue.wait_and_throw();
        }

        // Timed iterations
        std::cout << "\nMeasured: " << iters << " iteration(s)" << std::endl;
        std::vector<double> times_ms;
        times_ms.reserve(static_cast<size_t>(iters));

        decltype(head.inferHead(head_input)) last_results;
        for (int i = 0; i < iters; ++i) {
            const auto t0 = std::chrono::steady_clock::now();
            last_results = head.inferHead(head_input);
            queue.wait_and_throw();
            const auto t1 = std::chrono::steady_clock::now();

            const double ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t1 - t0).count();
            times_ms.push_back(ms);
        }

        // Print result information (from last iteration)
        std::cout << "\n=== Head Results (last iter) ===" << std::endl;
        std::cout << "First set outputs:" << std::endl;
        std::cout << "  Score shape: " << last_results.score_shape << std::endl;
        std::cout << "  Rot shape: " << last_results.rot_shape << std::endl;
        std::cout << "  Dim shape: " << last_results.dim_shape << std::endl;
        std::cout << "  Reg shape: " << last_results.reg_shape << std::endl;
        std::cout << "  Height shape: " << last_results.height_shape << std::endl;
        std::cout << "  Vel shape: " << last_results.vel_shape << std::endl;

        std::cout << "Second set outputs:" << std::endl;
        std::cout << "  Score2 shape: " << last_results.score2_shape << std::endl;
        std::cout << "  Rot2 shape: " << last_results.rot2_shape << std::endl;
        std::cout << "  Dim2 shape: " << last_results.dim2_shape << std::endl;
        std::cout << "  Reg2 shape: " << last_results.reg2_shape << std::endl;
        std::cout << "  Height2 shape: " << last_results.height2_shape << std::endl;
        std::cout << "  Vel2 shape: " << last_results.vel2_shape << std::endl;

        // Save Head results to bin files (once)
        saveHeadResultsToBin(last_results, "head_outputs");

        // Print some sample values
        if (!last_results.score.empty()) {
            std::cout << "\nSample score values (first 10): ";
            for (int i = 0; i < std::min(10, static_cast<int>(last_results.score.size())); ++i) {
                std::cout << last_results.score[static_cast<size_t>(i)] << " ";
            }
            std::cout << std::endl;
        }

        if (!last_results.score2.empty()) {
            std::cout << "Sample score2 values (first 10): ";
            for (int i = 0; i < std::min(10, static_cast<int>(last_results.score2.size())); ++i) {
                std::cout << last_results.score2[static_cast<size_t>(i)] << " ";
            }
            std::cout << std::endl;
        }

        std::cout << "Head inference completed successfully!" << std::endl;

        const double sum = std::accumulate(times_ms.begin(), times_ms.end(), 0.0);
        const double avg = sum / static_cast<double>(times_ms.size());
        const auto [mn_it, mx_it] = std::minmax_element(times_ms.begin(), times_ms.end());

        std::cout << "[perf] iters=" << iters
                  << ", avg=" << avg << " ms"
                  << ", min=" << *mn_it << " ms"
                  << ", max=" << *mx_it << " ms" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return -1;
    }
    
    return 0;
}