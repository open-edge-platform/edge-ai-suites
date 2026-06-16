#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <fstream>
#include <numeric>
#include <algorithm>
#include <sycl/sycl.hpp>
#include <thread>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include "camera-geometry.hpp"
// #include "bev_sycl.h" 
#include "bev.h"
#include "test_utils.hpp"
#include "bev_cam.hpp"
#include "gpu_context_manager.hpp"

void saveCameraBackboneOutputs(const CameraBackboneOutput& backbone_output, 
                              sycl::queue& queue,
                              const std::string& camera_filename = "camera_features.bin",
                              const std::string& depth_filename = "camera_depth_weights.bin") {
    
    std::cout << "\nSaving camera backbone outputs..." << std::endl;
    
    auto camera_shape = backbone_output.camera_shape;
    auto depth_shape = backbone_output.depth_shape;
    size_t camera_size = std::accumulate(camera_shape.begin(), camera_shape.end(), 1, std::multiplies<size_t>());
    size_t depth_size = std::accumulate(depth_shape.begin(), depth_shape.end(), 1, std::multiplies<size_t>());
    
    try {
        if (true) {
            // zero copy
            std::vector<float> camera_features_cpu(camera_size);
            std::vector<float> depth_weights_cpu(depth_size);
            
            // async copy
            auto camera_event = queue.submit([&](sycl::handler& h) {
                h.memcpy(camera_features_cpu.data(), backbone_output.camera_ptr, 
                        camera_size * sizeof(float));
            });
            
            auto depth_event = queue.submit([&](sycl::handler& h) {
                h.memcpy(depth_weights_cpu.data(), backbone_output.depth_ptr, 
                        depth_size * sizeof(float));
            });
            
            // wait until copy finish
            sycl::event::wait({camera_event, depth_event});
            
            std::ofstream camera_file(camera_filename, std::ios::binary);
            camera_file.write(reinterpret_cast<const char*>(camera_features_cpu.data()), 
                             camera_size * sizeof(float));
            camera_file.close();
            
            std::ofstream depth_file(depth_filename, std::ios::binary);
            depth_file.write(reinterpret_cast<const char*>(depth_weights_cpu.data()), 
                            depth_size * sizeof(float));
            depth_file.close();
            
        } else {
            // cpu 
            std::ofstream camera_file(camera_filename, std::ios::binary);
            camera_file.write(reinterpret_cast<const char*>(backbone_output.camera_features.data()), 
                             backbone_output.camera_features.size() * sizeof(float));
            camera_file.close();
            
            std::ofstream depth_file(depth_filename, std::ios::binary);
            depth_file.write(reinterpret_cast<const char*>(backbone_output.depth_weights.data()), 
                            backbone_output.depth_weights.size() * sizeof(float));
            depth_file.close();
        }
        
        std::cout << "✓ Camera features saved to " << camera_filename 
                  << " (" << camera_size * sizeof(float) << " bytes)" << std::endl;
        std::cout << "✓ Depth weights saved to " << depth_filename 
                  << " (" << depth_size * sizeof(float) << " bytes)" << std::endl;
        
        // check data size
        std::ifstream check_camera(camera_filename, std::ios::binary | std::ios::ate);
        std::ifstream check_depth(depth_filename, std::ios::binary | std::ios::ate);
        
        if (check_camera.is_open()) {
            size_t camera_file_size = check_camera.tellg();
            std::cout << "  Camera file size verification: " << camera_file_size 
                      << " bytes (expected: " << camera_size * sizeof(float) << ")" << std::endl;
        }
        
        if (check_depth.is_open()) {
            size_t depth_file_size = check_depth.tellg();
            std::cout << "  Depth file size verification: " << depth_file_size 
                      << " bytes (expected: " << depth_size * sizeof(float) << ")" << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "❌ Error saving camera backbone outputs: " << e.what() << std::endl;
    }
}

int main(int argc, char* argv[]) {
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

    if (args.size() < 1 || args.size() > 4) {
        std::cerr << "Usage: " << argv[0] << " <image_path> [model_path] [warmup] [iters] [--fp32]" << std::endl;
        return -1;
    }
    
    std::string image_path = args[0];
    std::string model_path = "../data/v2xfusion/pointpillars/quantized_camera.xml";
    if (args.size() >= 2) {
        model_path = args[1];
    } else {
        model_path = use_fp32 ? "../data/v2xfusion/pointpillars/camera.backbone.onnx"
                      : "../data/v2xfusion/pointpillars/quantized_camera.xml";
    }

    int warmup = 10;
    int iters = 100;
    try {
        if (args.size() >= 3) warmup = std::max(0, std::stoi(args[2]));
        if (args.size() >= 4) iters = std::max(1, std::stoi(args[3]));
    } catch (const std::exception& e) {
        std::cerr << "Invalid args: " << e.what() << std::endl;
        std::cerr << "Usage: " << argv[0] << " <image_path> [model_path] [warmup] [iters] [--fp32]" << std::endl;
        return -1;
    }
    
    try {
        // Initialize SYCL queue
        sycl::queue queue = create_opencl_queue();

        // Initialize shared OpenVINO/OpenCL context
        auto& context_manager = GPUContextManager::getInstance();
        if (!context_manager.initialize(queue, use_fp32)) {
            std::cerr << "Failed to initialize GPU context manager" << std::endl;
            return -1;
        }

        // Load image
        std::cout << "\nLoading image: " << image_path << std::endl;
        cv::Mat image = cv::imread(image_path);
        if (image.empty()) {
            std::cerr << "Failed to load image: " << image_path << std::endl;
            return -1;
        }
        std::cout << "Image loaded successfully: " << image.cols << "x" << image.rows << std::endl;
        
        // Initialize camera backbone pipeline using shared context
        std::cout << "\nInitializing camera backbone..." << std::endl;
        BEVFusionCam pipeline(model_path, queue, true);

        // Run camera backbone once to get output shapes (and optionally dump outputs).
        std::cout << "\nExtracting camera features and depth weights (shape probe)..." << std::endl;
        CameraBackboneOutput backbone_output = pipeline.processImage(image);
        queue.wait_and_throw();

        saveCameraBackboneOutputs(backbone_output, queue);

        auto camera_shape = backbone_output.camera_shape;
        auto depth_shape = backbone_output.depth_shape;

        int camera_channels = camera_shape[1];  // 80
        int camera_height = camera_shape[2];    // 54
        int camera_width = camera_shape[3];     // 96

        int depth_channels = depth_shape[1];    // 90
        int depth_height = depth_shape[2];      // 54
        int depth_width = depth_shape[3];       // 96
        
        std::cout << "Camera feature shape: [" << camera_channels << ", " 
                  << camera_height << ", " << camera_width << "]" << std::endl;
        std::cout << "Camera depth weights shape: [" << depth_channels << ", " 
                  << depth_height << ", " << depth_width << "]" << std::endl;
        
        // Set up geometry parameters
        std::cout << "\nSetting up camera geometry..." << std::endl;
        
        auto params = bevfusion::camera::make_v2xfusion_geometry_parameter(static_cast<unsigned int>(camera_width),
                                           static_cast<unsigned int>(camera_height));
        
        std::cout << "Geometry parameters:" << std::endl;
        std::cout << "  X bound: [" << params.xbound.x << ", " << params.xbound.y << "], step: " << params.xbound.z << std::endl;
        std::cout << "  Y bound: [" << params.ybound.x << ", " << params.ybound.y << "], step: " << params.ybound.z << std::endl;
        std::cout << "  Z bound: [" << params.zbound.x << ", " << params.zbound.y << "], step: " << params.zbound.z << std::endl;
        std::cout << "  D bound: [" << params.dbound.x << ", " << params.dbound.y << "], step: " << params.dbound.z << std::endl;
        std::cout << "  Geometry dim: " << params.geometry_dim.x << "x" << params.geometry_dim.y << "x" << params.geometry_dim.z << std::endl;
        std::cout << "  Feature size: " << params.feat_width << "x" << params.feat_height << std::endl;
        std::cout << "  Image size: " << params.image_width << "x" << params.image_height << std::endl;
        std::cout << "  Number of cameras: " << params.num_camera << std::endl;
        
        // Create geometry object
        std::cout << "\nCreating geometry object..." << std::endl;
        auto geometry = bevfusion::camera::create_geometry(params, queue);
        if (!geometry) {
            std::cerr << "Failed to create geometry object" << std::endl;
            return -1;
        }
        std::cout << "Geometry object created successfully" << std::endl;
        
        // 7. Prepare camera matrix data
        std::cout << "\nPreparing camera matrices..." << std::endl;
        
        std::vector<float> camera2lidar_all;
        std::vector<float> camera_intrinsics_all;
        std::vector<float> img_aug_matrix_all;
        std::vector<float> denorms_all;
        
        // Try to load from bin files, generate test data if failed
        try {
            camera2lidar_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera2lidar.bin");
            camera_intrinsics_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera_intrinsics.bin");
            img_aug_matrix_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/img_aug_matrix.bin");
            denorms_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/denorms.bin");
            std::cout << "Loaded camera matrices from bin files" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "Failed to load from bin files, generating test data: " << e.what() << std::endl;
            
            // Generate test data
            camera2lidar_all.resize(params.num_camera * 16);
            camera_intrinsics_all.resize(params.num_camera * 16);
            img_aug_matrix_all.resize(params.num_camera * 16);
            denorms_all.resize(params.num_camera * 4); // Assume each camera has 4 denorm values
            
            for (unsigned int i = 0; i < params.num_camera; ++i) {
                auto c2l = generate_test_camera2lidar_matrix(i);
                auto intrinsics = generate_test_camera_intrinsics(i, params.image_width, params.image_height);
                auto aug = generate_test_img_aug_matrix(i);
                
                std::copy(c2l.begin(), c2l.end(), camera2lidar_all.begin() + i * 16);
                std::copy(intrinsics.begin(), intrinsics.end(), camera_intrinsics_all.begin() + i * 16);
                std::copy(aug.begin(), aug.end(), img_aug_matrix_all.begin() + i * 16);
            }
            std::cout << "Generated test camera matrices" << std::endl;
        }
        
        // Update geometry matrices (compute once)
        std::cout << "\nUpdating geometry matrices..." << std::endl;
        queue.wait();

        auto start = std::chrono::high_resolution_clock::now();
        geometry->update(camera2lidar_all.data(),
                        camera_intrinsics_all.data(),
                        img_aug_matrix_all.data(),
                        denorms_all.data(),
                        &queue);
        queue.wait_and_throw();
        auto end = std::chrono::high_resolution_clock::now();
        
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        std::cout << "Geometry update completed in " << duration.count() << " ms" << std::endl;
        
        // Get indices and intervals
        unsigned int num_intervals = geometry->num_intervals();
        unsigned int num_indices = geometry->num_indices();
        
        std::cout << "Geometry computed successfully:" << std::endl;
        std::cout << "  - Number of intervals: " << num_intervals << std::endl;
        std::cout << "  - Number of indices: " << num_indices << std::endl;
        
        if (num_intervals == 0 || num_indices == 0) {
            std::cerr << "No valid geometry generated" << std::endl;
            return -1;
        }
        
        auto indices_ptr = geometry->indices();
        auto intervals_ptr = geometry->intervals();

        queue.wait_and_throw();

        std::cout << "Loaded geometry data:" << std::endl;
        std::cout << "  - Number of intervals: " << num_intervals << std::endl;
        std::cout << "  - Number of indices: " << num_indices << std::endl;
        
        if (num_intervals == 0 || num_indices == 0) {
            std::cerr << "No valid geometry data loaded" << std::endl;
            return -1;
        }
        // Execute BEVPool operation (using camera features and depth weights)
        std::cout << "\nExecuting end-to-end camera backbone + BEVPool..." << std::endl;


        
        start = std::chrono::high_resolution_clock::now();
        std::cout << "\nInitializing BEV object..." << std::endl;

        Bound xBound = {params.xbound.x, params.xbound.y, params.xbound.z};
        Bound yBound = {params.ybound.x, params.ybound.y, params.ybound.z};
        Bound zBound = {params.zbound.x, params.zbound.y, params.zbound.z};
        Bound dBound = {params.dbound.x, params.dbound.y, params.dbound.z};
        
        Bev bev_processor(queue,  // sycl queue
                        camera_channels,  // inputChannels
                        camera_channels,  // outputChannels
                        params.image_width,   // imageWidth
                        params.image_height,  // imageHeight
                        camera_width,     // featureWidth
                        camera_height,    // featureHeight
                        xBound, yBound, zBound, dBound);

        std::cout << "BEV object initialized successfully" << std::endl;

        // BEVPool parameters
        uint32_t n = 1;  // batch size
        uint32_t c = camera_channels;  // 80
        uint32_t d = depth_channels;   // 90
        uint32_t h = camera_height;    // 54
        uint32_t w = camera_width;     // 96
        uint32_t bevWidth = params.geometry_dim.x;   // 128
        uint32_t bevHeight = params.geometry_dim.y;  // 128

        uint32_t bev_output_size = camera_channels * bevWidth * bevHeight;
        float* gpu_bev_features = sycl::malloc_device<float>(bev_output_size, queue);

        std::cout << "BEVPool parameters:" << std::endl;
        std::cout << "  - Input shape: [" << n << ", " << c << ", " << h << ", " << w << "]" << std::endl;
        std::cout << "  - Depth shape: [" << n << ", " << d << ", " << h << ", " << w << "]" << std::endl;
        std::cout << "  - Output shape: [" << c << ", " << bevHeight << ", " << bevWidth << "]" << std::endl;
        std::cout << "  - Number of intervals: " << num_intervals << std::endl;
        std::cout << "  - Number of indices: " << num_indices << std::endl;

        std::cout << "\nWarmup: " << warmup << " iteration(s)" << std::endl;
        for (int i = 0; i < warmup; ++i) {
            auto bo = pipeline.processImage(image);
            queue.wait_and_throw();
            float* gpu_camera_features = bo.camera_ptr;
            float* gpu_depth_weights = bo.depth_ptr;
            if (!gpu_camera_features || !gpu_depth_weights) {
                throw std::runtime_error("Camera backbone returned null pointers");
            }

            queue.memset(gpu_bev_features, 0, static_cast<size_t>(bev_output_size) * sizeof(float)).wait();
            (void)bev_processor.bevPool(
                gpu_camera_features,
                gpu_depth_weights,
                indices_ptr,
                intervals_ptr,
                gpu_bev_features,
                num_intervals,
                n, c, d, h, w,
                bevWidth, bevHeight);
            queue.wait_and_throw();
        }

        std::cout << "\nMeasured: " << iters << " iteration(s)" << std::endl;
        std::vector<double> times_ms;
        times_ms.reserve(static_cast<size_t>(iters));

        for (int i = 0; i < iters; ++i) {
            const auto t0 = std::chrono::steady_clock::now();

            auto bo = pipeline.processImage(image);
            queue.wait_and_throw();
            float* gpu_camera_features = bo.camera_ptr;
            float* gpu_depth_weights = bo.depth_ptr;
            if (!gpu_camera_features || !gpu_depth_weights) {
                throw std::runtime_error("Camera backbone returned null pointers");
            }

            queue.memset(gpu_bev_features, 0, static_cast<size_t>(bev_output_size) * sizeof(float)).wait();
            uint32_t result = bev_processor.bevPool(
                gpu_camera_features,
                gpu_depth_weights,
                indices_ptr,
                intervals_ptr,
                gpu_bev_features,
                num_intervals,
                n, c, d, h, w,
                bevWidth, bevHeight);
            queue.wait_and_throw();
            const auto t1 = std::chrono::steady_clock::now();

            if (result != 0) {
                std::cerr << "BEVPool execution failed with error code: " << result << std::endl;
                return -1;
            }

            const double ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t1 - t0).count();
            times_ms.push_back(ms);
        }

        std::cout << "\nConverting output data..." << std::endl;
        std::vector<float> bev_features(bev_output_size);
        queue.memcpy(bev_features.data(), gpu_bev_features, bev_output_size * sizeof(float)).wait();

        std::cout << "BEV features generated successfully!" << std::endl;
        std::cout << "BEV feature size: " << bev_features.size() << std::endl;
        std::cout << "BEV feature shape: [" << c << ", " << bevHeight << ", " << bevWidth << "]" << std::endl;
        
        // Save results
        std::cout << "\nSaving results..." << std::endl;
        
        // Save BEV features
        std::ofstream bev_file("bev_camera_features.bin", std::ios::binary);
        bev_file.write(reinterpret_cast<const char*>(bev_features.data()), 
                      bev_features.size() * sizeof(float));
        bev_file.close();
        
        // // Save camera features
        // std::ofstream camera_file("camera_features.bin", std::ios::binary);
        // camera_file.write(reinterpret_cast<const char*>(backbone_output.camera_features.data()), 
        //                  backbone_output.camera_features.size() * sizeof(float));
        // camera_file.close();
        
        // // Save depth weights
        // std::ofstream depth_file("camera_depth_weights.bin", std::ios::binary);
        // depth_file.write(reinterpret_cast<const char*>(backbone_output.depth_weights.data()), 
        //                 backbone_output.depth_weights.size() * sizeof(float));
        // depth_file.close();
        
        // Save indices and intervals
        // Copy indices from GPU to CPU
        std::vector<unsigned int> indices_cpu(num_indices);
        queue.memcpy(indices_cpu.data(), indices_ptr, num_indices * sizeof(unsigned int)).wait();

        // Copy intervals from GPU to CPU
        std::vector<bevfusion::types::Int3> intervals_cpu(num_intervals);
        queue.memcpy(intervals_cpu.data(), intervals_ptr, num_intervals * sizeof(bevfusion::types::Int3)).wait();
        std::ofstream indices_file("indices_output.bin", std::ios::binary);
        indices_file.write(reinterpret_cast<const char*>(indices_cpu.data()), 
                          num_indices * sizeof(unsigned int));
        indices_file.close();
        
        std::ofstream intervals_file("intervals_output.bin", std::ios::binary);
        intervals_file.write(reinterpret_cast<const char*>(intervals_cpu.data()), 
                            num_intervals * sizeof(bevfusion::types::Int3));
        intervals_file.close();
        
        std::cout << "Results saved:" << std::endl;
        std::cout << "  - BEV features: bev_camera_features.bin" << std::endl;
        std::cout << "  - Camera features: camera_features.bin" << std::endl;
        std::cout << "  - Camera depth weights: camera_depth_weights.bin" << std::endl;
        std::cout << "  - Indices: indices_output.bin" << std::endl;
        std::cout << "  - Intervals: intervals_output.bin" << std::endl;
        
        // Simple validation
        if (!bev_features.empty()) {
            float min_val = *std::min_element(bev_features.begin(), bev_features.end());
            float max_val = *std::max_element(bev_features.begin(), bev_features.end());
            float sum = std::accumulate(bev_features.begin(), bev_features.end(), 0.0f);
            float mean = sum / bev_features.size();
            
            std::cout << "\nResult validation:" << std::endl;
            std::cout << "  - BEV features min: " << min_val << std::endl;
            std::cout << "  - BEV features max: " << max_val << std::endl;
            std::cout << "  - BEV features mean: " << mean << std::endl;
        }

        {
            const double sum_ms = std::accumulate(times_ms.begin(), times_ms.end(), 0.0);
            const double avg_ms = sum_ms / static_cast<double>(times_ms.size());
            const auto [mn_it, mx_it] = std::minmax_element(times_ms.begin(), times_ms.end());
            std::cout << "[perf] iters=" << iters
                      << ", avg=" << avg_ms << " ms"
                      << ", min=" << *mn_it << " ms"
                      << ", max=" << *mx_it << " ms" << std::endl;
        }
  
        std::cout << "\n🎉 BEVFusion camera pipeline test completed successfully!" << std::endl;
        sycl::free(gpu_bev_features, queue);        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return -1;
    }
    
    return 0;
}