#include <iostream>
#include <vector>
#include <memory>
#include <random>
#include <chrono>
#include <iomanip>
#include <fstream>
#include <sycl/sycl.hpp>

#include "camera-geometry.hpp"
#include "test_utils.hpp"

class CameraGeometryTester {
private:
    sycl::queue queue_;
    std::shared_ptr<bevfusion::camera::Geometry> geometry_;
    bevfusion::camera::GeometryParameter params_;
    bevfusion::camera::FusionMethod fusion_method_;

public:
    CameraGeometryTester(bevfusion::camera::FusionMethod method = bevfusion::camera::FusionMethod::BEVFUSION) 
        : fusion_method_(method) {
        // choose device
        queue_ = create_opencl_queue();
    }

    void setup_test_parameters() {

        params_.xbound = bevfusion::types::Float3(-54.0f, 54.0f, 0.3f);
        params_.ybound = bevfusion::types::Float3(-54.0f, 54.0f, 0.3f);
        params_.zbound = bevfusion::types::Float3(-10.0f, 10.0f, 20.0f);
        params_.dbound = bevfusion::types::Float3(1.0f, 60.0f, 0.5f);
        params_.geometry_dim = bevfusion::types::Int3(360, 360, 80);
        params_.feat_width = 88;
        params_.feat_height = 32;
        params_.image_width = 704;
        params_.image_height = 256;
        params_.num_camera = 6;
        params_.fusion_method = fusion_method_;

        std::cout << "Test parameters setup:" << std::endl;
        std::cout << "  X bound: [" << params_.xbound.x << ", " << params_.xbound.y << "], step: " << params_.xbound.z << std::endl;
        std::cout << "  Y bound: [" << params_.ybound.x << ", " << params_.ybound.y << "], step: " << params_.ybound.z << std::endl;
        std::cout << "  Z bound: [" << params_.zbound.x << ", " << params_.zbound.y << "], step: " << params_.zbound.z << std::endl;
        std::cout << "  D bound: [" << params_.dbound.x << ", " << params_.dbound.y << "], step: " << params_.dbound.z << std::endl;
        std::cout << "  Geometry dim: " << params_.geometry_dim.x << "x" << params_.geometry_dim.y << "x" << params_.geometry_dim.z << std::endl;
        std::cout << "  Feature size: " << params_.feat_width << "x" << params_.feat_height << std::endl;
        std::cout << "  Image size: " << params_.image_width << "x" << params_.image_height << std::endl;
        std::cout << "  Number of cameras: " << params_.num_camera << std::endl;
    }

    // only for v2xfusion
    std::vector<sycl::float3> generate_test_denorms() {
        std::vector<sycl::float3> denorms(params_.num_camera);
        for (unsigned int i = 0; i < params_.num_camera; ++i) {
            // Generate a unit normal vector (simplified to +Z here)
            denorms[i] = sycl::float3(0.0f, 0.0f, 1.0f);
        }
        return denorms;
    }

    std::vector<float> generate_test_camera2lidar_matrix(int camera_id) {
        std::vector<float> matrix(16, 0.0f);

        float angle = camera_id * 60.0f * M_PI / 180.0f; //
        
        matrix[0] = cos(angle);   matrix[1] = -sin(angle);  matrix[2] = 0;  matrix[3] = 0;
        matrix[4] = sin(angle);   matrix[5] = cos(angle);   matrix[6] = 0;  matrix[7] = 0;
        matrix[8] = 0;            matrix[9] = 0;            matrix[10] = 1; matrix[11] = 0;
        matrix[12] = 0;           matrix[13] = 0;           matrix[14] = 0; matrix[15] = 1;
        
        return matrix;
    }

    std::vector<float> generate_test_camera_intrinsics(int camera_id) {
        std::vector<float> matrix(16, 0.0f);
        
        float fx = 800.0f + camera_id * 10.0f;  
        float fy = 800.0f + camera_id * 10.0f;  
        float cx = params_.image_width / 2.0f; 
        float cy = params_.image_height / 2.0f; 
        
        matrix[0] = fx;  matrix[1] = 0;   matrix[2] = cx;  matrix[3] = 0;
        matrix[4] = 0;   matrix[5] = fy;  matrix[6] = cy;  matrix[7] = 0;
        matrix[8] = 0;   matrix[9] = 0;   matrix[10] = 1;  matrix[11] = 0;
        matrix[12] = 0;  matrix[13] = 0;  matrix[14] = 0;  matrix[15] = 1;
        
        return matrix;
    }

    std::vector<float> generate_test_img_aug_matrix(int camera_id) {
        std::vector<float> matrix(16, 0.0f);
        
        float scale = 1.0f + camera_id * 0.01f;
        
        matrix[0] = scale; matrix[1] = 0;     matrix[2] = 0;  matrix[3] = 0;
        matrix[4] = 0;     matrix[5] = scale; matrix[6] = 0;  matrix[7] = 0;
        matrix[8] = 0;     matrix[9] = 0;     matrix[10] = 1; matrix[11] = 0;
        matrix[12] = 0;    matrix[13] = 0;    matrix[14] = 0; matrix[15] = 1;
        
        return matrix;
    }

    bool test_initialization() {
        std::cout << "\n=== Testing Initialization ===" << std::endl;
        
        try {
            geometry_ = bevfusion::camera::create_geometry(params_, queue_);
            if (!geometry_) {
                std::cout << "❌ Failed to create geometry object" << std::endl;
                return false;
            }
            std::cout << "✅ Geometry object created successfully" << std::endl;
            return true;
        } catch (const std::exception& e) {
            std::cout << "❌ Exception during initialization: " << e.what() << std::endl;
            return false;
        }
    }

    bool test_matrix_update() {
        std::cout << "\n=== Testing Matrix Update (from bin) ===" << std::endl;
        try {
            
            std::vector<float> camera2lidar_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera2lidar.bin");
            std::vector<float> camera_intrinsics_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera_intrinsics.bin");
            std::vector<float> img_aug_matrix_all = load_matrix_from_bin("../data/v2xfusion/dump_bins/img_aug_matrix.bin");


            auto start = std::chrono::high_resolution_clock::now();
            if (fusion_method_ == bevfusion::camera::FusionMethod::V2XFUSION) {
                auto denorms = generate_test_denorms();
                geometry_->update(camera2lidar_all.data(),
                                camera_intrinsics_all.data(),
                                img_aug_matrix_all.data(),
                                reinterpret_cast<const float*>(denorms.data()),
                                &queue_);
            } else {

                geometry_->update(camera2lidar_all.data(),
                                camera_intrinsics_all.data(),
                                img_aug_matrix_all.data(),
                                nullptr,
                                &queue_);
            }
            auto end = std::chrono::high_resolution_clock::now();

            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
            std::cout << "✅ Matrix update completed in " << duration.count() << " ms" << std::endl;

            unsigned int num_intervals = geometry_->num_intervals();
            unsigned int num_indices = geometry_->num_indices();

            std::cout << "  Number of intervals: " << num_intervals << std::endl;
            std::cout << "  Number of indices: " << num_indices << std::endl;


            auto indices_ptr = geometry_->indices();
            auto intervals_ptr = geometry_->intervals();

            queue_.wait();


            try {
                // copy indices data to host
                std::vector<unsigned int> indices_cpu(num_indices);
                queue_.memcpy(indices_cpu.data(), indices_ptr, num_indices * sizeof(unsigned int)).wait();
                
                // check data
                std::cout << "✅ Indices copied successfully" << std::endl;
                std::cout << "  First 5 indices: ";
                for (int i = 0; i < std::min(5u, num_indices); ++i) {
                    std::cout << indices_cpu[i] << " ";
                }
                std::cout << std::endl;

                // save indices to bin file
                std::ofstream f_indices("indices_output.bin", std::ios::binary);
                if (f_indices.is_open()) {
                    f_indices.write(reinterpret_cast<const char*>(indices_cpu.data()), 
                                num_indices * sizeof(unsigned int));
                    f_indices.close();
                    
                    // check file size
                    std::ifstream check_indices("indices_output.bin", std::ios::binary | std::ios::ate);
                    size_t indices_file_size = check_indices.tellg();
                    std::cout << "  indices_output.bin saved: " << indices_file_size 
                            << " bytes (expected: " << num_indices * sizeof(unsigned int) << ")" << std::endl;
                    check_indices.close();
                } else {
                    std::cout << "❌ Failed to open indices_output.bin for writing" << std::endl;
                }

                // 2. Copy intervals data to host and save
                // Note: Confirm the actual data type pointed to by intervals_ptr
                // If it's sycl::int3, adjust accordingly
                std::vector<bevfusion::types::Int3> intervals_cpu(num_intervals);
                queue_.memcpy(intervals_cpu.data(), intervals_ptr, num_intervals * sizeof(bevfusion::types::Int3)).wait();
                
                std::cout << "✅ Intervals copied successfully" << std::endl;
                std::cout << "  First 3 intervals:" << std::endl;
                for (int i = 0; i < std::min(3u, num_intervals); ++i) {
                    std::cout << "    [" << i << "]: (" << intervals_cpu[i].x 
                            << ", " << intervals_cpu[i].y 
                            << ", " << intervals_cpu[i].z << ")" << std::endl;
                }

                // save intervals to bin file
                std::ofstream f_intervals("intervals_output.bin", std::ios::binary);
                if (f_intervals.is_open()) {
                    f_intervals.write(reinterpret_cast<const char*>(intervals_cpu.data()), 
                            num_intervals * sizeof(bevfusion::types::Int3));
                    f_intervals.close();
                    
                    // check file size
                    std::ifstream check_intervals("intervals_output.bin", std::ios::binary | std::ios::ate);
                    size_t intervals_file_size = check_intervals.tellg();
                    std::cout << "  intervals_output.bin saved: " << intervals_file_size 
                        << " bytes (expected: " << num_intervals * sizeof(bevfusion::types::Int3) << ")" << std::endl;
                    check_intervals.close();
                } else {
                    std::cout << "❌ Failed to open intervals_output.bin for writing" << std::endl;
                }

            } catch (const std::exception& e) {
                std::cout << "❌ Error during data copy/save: " << e.what() << std::endl;
                return false;
            }
            return true;
        } catch (const std::exception& e) {
            std::cout << "❌ Exception during matrix update: " << e.what() << std::endl;
            return false;
        }
    }

    bool test_multiple_updates() {
        std::cout << "\n=== Testing Multiple Updates ===" << std::endl;
        
        const int num_updates = 5;
        std::vector<double> update_times;
        
        for (int i = 0; i < num_updates; ++i) {

            std::vector<float> camera2lidar_all(params_.num_camera * 16);
            std::vector<float> camera_intrinsics_all(params_.num_camera * 16);
            std::vector<float> img_aug_matrix_all(params_.num_camera * 16);
            
            for (unsigned int j = 0; j < params_.num_camera; ++j) {
                auto c2l = generate_test_camera2lidar_matrix(j + i);  
                auto intrinsics = generate_test_camera_intrinsics(j);
                auto aug = generate_test_img_aug_matrix(j);
                
                std::copy(c2l.begin(), c2l.end(), camera2lidar_all.begin() + j * 16);
                std::copy(intrinsics.begin(), intrinsics.end(), camera_intrinsics_all.begin() + j * 16);
                std::copy(aug.begin(), aug.end(), img_aug_matrix_all.begin() + j * 16);
            }
            
            auto start = std::chrono::high_resolution_clock::now();
            geometry_->update(camera2lidar_all.data(), 
                            camera_intrinsics_all.data(), 
                            img_aug_matrix_all.data(), 
                            nullptr,
                            &queue_);
            auto end = std::chrono::high_resolution_clock::now();
            
            auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
            update_times.push_back(duration.count() / 1000.0);  
            
            std::cout << "  Update " << i + 1 << ": " << std::fixed << std::setprecision(2) 
                      << update_times.back() << " ms" << std::endl;
        }

        double avg_time = 0.0;
        for (double time : update_times) {
            avg_time += time;
        }
        avg_time /= update_times.size();
        
        std::cout << "✅ Average update time: " << std::fixed << std::setprecision(2) 
                  << avg_time << " ms" << std::endl;
        
        return true;
    }

    bool test_memory_management() {
        std::cout << "\n=== Testing Memory Management ===" << std::endl;
        
        try {

            geometry_->free_excess_memory();
            std::cout << "✅ Excess memory freed successfully" << std::endl;
            

            std::vector<float> dummy_matrix(params_.num_camera * 16, 1.0f);
            
            try {
                geometry_->update(dummy_matrix.data(), dummy_matrix.data(), dummy_matrix.data(), nullptr, &queue_);
                std::cout << "❌ Update after free_excess_memory should have failed" << std::endl;
                return false;
            } catch (const std::exception& e) {
                std::cout << "✅ Correctly caught exception after memory free: " << e.what() << std::endl;
            }
            
            return true;
        } catch (const std::exception& e) {
            std::cout << "❌ Exception during memory management test: " << e.what() << std::endl;
            return false;
        }
    }

    bool test_performance_benchmark() {
        std::cout << "\n=== Performance Benchmark ===" << std::endl;
        

        geometry_ = bevfusion::camera::create_geometry(params_, queue_);
        if (!geometry_) {
            std::cout << "❌ Failed to recreate geometry object for benchmark" << std::endl;
            return false;
        }
        

        std::vector<float> camera2lidar_all(params_.num_camera * 16);
        std::vector<float> camera_intrinsics_all(params_.num_camera * 16);
        std::vector<float> img_aug_matrix_all(params_.num_camera * 16);
        
        for (unsigned int i = 0; i < params_.num_camera; ++i) {
            auto c2l = generate_test_camera2lidar_matrix(i);
            auto intrinsics = generate_test_camera_intrinsics(i);
            auto aug = generate_test_img_aug_matrix(i);
            
            std::copy(c2l.begin(), c2l.end(), camera2lidar_all.begin() + i * 16);
            std::copy(intrinsics.begin(), intrinsics.end(), camera_intrinsics_all.begin() + i * 16);
            std::copy(aug.begin(), aug.end(), img_aug_matrix_all.begin() + i * 16);
        }
        

        for (int i = 0; i < 3; ++i) {
            geometry_->update(camera2lidar_all.data(), 
                            camera_intrinsics_all.data(), 
                            img_aug_matrix_all.data(), 
                            nullptr,
                            &queue_);
        }
        

        const int benchmark_iterations = 10;
        auto start = std::chrono::high_resolution_clock::now();
        
        for (int i = 0; i < benchmark_iterations; ++i) {
            geometry_->update(camera2lidar_all.data(), 
                            camera_intrinsics_all.data(), 
                            img_aug_matrix_all.data(), 
                            nullptr,
                            &queue_);
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto total_duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
        double avg_time = total_duration.count() / (1000.0 * benchmark_iterations);  // ms
        
        std::cout << "✅ Benchmark completed:" << std::endl;
        std::cout << "  Iterations: " << benchmark_iterations << std::endl;
        std::cout << "  Average time per update: " << std::fixed << std::setprecision(3) 
                  << avg_time << " ms" << std::endl;
        std::cout << "  Throughput: " << std::fixed << std::setprecision(1) 
                  << 1000.0 / avg_time << " updates/second" << std::endl;
        
        return true;
    }

    void run_all_tests() {
        std::cout << "Starting Camera Geometry Tests..." << std::endl;
        std::cout << "Device: " << queue_.get_device().get_info<sycl::info::device::name>() << std::endl;
        
        setup_test_parameters();
        
        bool all_passed = true;
        
        all_passed &= test_initialization();
        all_passed &= test_matrix_update();
        all_passed &= test_multiple_updates();
        all_passed &= test_performance_benchmark();
        all_passed &= test_memory_management();
        
        std::cout << "\n=== Test Summary ===" << std::endl;
        if (all_passed) {
            std::cout << "🎉 All tests passed!" << std::endl;
        } else {
            std::cout << "❌ Some tests failed!" << std::endl;
        }
    }
};

int main() {
    try {

        bevfusion::camera::FusionMethod method = bevfusion::camera::FusionMethod::BEVFUSION;
        CameraGeometryTester tester(method);
        tester.run_all_tests();
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }
}