#include "test_utils.hpp"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <iostream>
#include <cmath>
#include <boost/filesystem.hpp>

sycl::queue create_opencl_queue()
{
    sycl::queue queue;
    bool found = false;

    // Prefer discrete OpenCL GPU (heuristic: no unified memory)
    for (auto &plt : sycl::platform::get_platforms()) {
        for (auto &dev : plt.get_devices()) {
            if (!dev.is_gpu()) continue;
            if (dev.get_backend() != sycl::backend::opencl) continue;
            if (dev.get_info<sycl::info::device::host_unified_memory>()) continue;
            queue = sycl::queue(dev, sycl::property::queue::in_order{});
            found = true;
            std::cout << "Using discrete OpenCL GPU (in-order queue): "
                      << dev.get_info<sycl::info::device::name>() << std::endl;
            auto max_alloc = dev.get_info<sycl::info::device::max_mem_alloc_size>();
            auto global_mem = dev.get_info<sycl::info::device::global_mem_size>();
            std::cout << "Device max single alloc: " << (max_alloc / (1024 * 1024))
                      << " MB, total global: " << (global_mem / (1024 * 1024)) << " MB" << std::endl;
            break;
        }
        if (found) break;
    }

    // If no discrete GPU, try any OpenCL GPU (likely integrated)
    if (!found) {
        for (auto &plt : sycl::platform::get_platforms()) {
            for (auto &dev : plt.get_devices()) {
                if (!dev.is_gpu()) continue;
                if (dev.get_backend() != sycl::backend::opencl) continue;
                queue = sycl::queue(dev, sycl::property::queue::in_order{});
                found = true;
                std::cout << "Using OpenCL GPU (in-order queue): "
                          << dev.get_info<sycl::info::device::name>() << std::endl;
                auto max_alloc = dev.get_info<sycl::info::device::max_mem_alloc_size>();
                auto global_mem = dev.get_info<sycl::info::device::global_mem_size>();
                std::cout << "Device max single alloc: " << (max_alloc / (1024 * 1024))
                          << " MB, total global: " << (global_mem / (1024 * 1024)) << " MB" << std::endl;
                break;
            }
            if (found) break;
        }
    }

    // Final fallback to CPU
    if (!found) {
        std::cout << "No OpenCL GPU found, using CPU (in-order)" << std::endl;
        queue = sycl::queue(sycl::cpu_selector_v, sycl::property::queue::in_order{});
    }

    return queue;
}

// Utility functions implementation
std::vector<float> load_matrix_from_bin(const std::string &filename)
{
    std::ifstream fin(filename, std::ios::binary);
    if (!fin) {
        throw std::runtime_error("Cannot open file: " + filename);
    }
    fin.seekg(0, std::ios::end);
    size_t num_bytes = fin.tellg();
    fin.seekg(0, std::ios::beg);
    size_t num_floats = num_bytes / sizeof(float);
    std::vector<float> data(num_floats);
    fin.read(reinterpret_cast<char *>(data.data()), num_bytes);
    fin.close();
    return data;
}

void save_matrix_to_bin(const std::string& filename, const std::vector<float>& data)
{
    std::filesystem::path p(filename);
    if (p.has_parent_path()) {
        std::error_code ec;
        std::filesystem::create_directories(p.parent_path(), ec);
    }

    std::ofstream fout(filename, std::ios::binary);
    if (!fout) {
        throw std::runtime_error("Cannot open file for writing: " + filename);
    }
    fout.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size() * sizeof(float)));
    fout.close();
}

std::vector<float> generate_test_camera2lidar_matrix(int camera_id)
{
    std::vector<float> matrix(16, 0.0f);
    float angle = camera_id * 60.0f * M_PI / 180.0f;

    matrix[0] = cos(angle);
    matrix[1] = -sin(angle);
    matrix[2] = 0;
    matrix[3] = 0;
    matrix[4] = sin(angle);
    matrix[5] = cos(angle);
    matrix[6] = 0;
    matrix[7] = 0;
    matrix[8] = 0;
    matrix[9] = 0;
    matrix[10] = 1;
    matrix[11] = 0;
    matrix[12] = 0;
    matrix[13] = 0;
    matrix[14] = 0;
    matrix[15] = 1;

    return matrix;
}

std::vector<float> generate_test_camera_intrinsics(int camera_id, int image_width, int image_height)
{
    std::vector<float> matrix(16, 0.0f);

    float fx = 800.0f + camera_id * 10.0f;
    float fy = 800.0f + camera_id * 10.0f;
    float cx = image_width / 2.0f;
    float cy = image_height / 2.0f;

    matrix[0] = fx;
    matrix[1] = 0;
    matrix[2] = cx;
    matrix[3] = 0;
    matrix[4] = 0;
    matrix[5] = fy;
    matrix[6] = cy;
    matrix[7] = 0;
    matrix[8] = 0;
    matrix[9] = 0;
    matrix[10] = 1;
    matrix[11] = 0;
    matrix[12] = 0;
    matrix[13] = 0;
    matrix[14] = 0;
    matrix[15] = 1;

    return matrix;
}

std::vector<float> generate_test_img_aug_matrix(int camera_id)
{
    std::vector<float> matrix(16, 0.0f);

    float scale = 1.0f + camera_id * 0.01f;

    matrix[0] = scale;
    matrix[1] = 0;
    matrix[2] = 0;
    matrix[3] = 0;
    matrix[4] = 0;
    matrix[5] = scale;
    matrix[6] = 0;
    matrix[7] = 0;
    matrix[8] = 0;
    matrix[9] = 0;
    matrix[10] = 1;
    matrix[11] = 0;
    matrix[12] = 0;
    matrix[13] = 0;
    matrix[14] = 0;
    matrix[15] = 1;

    return matrix;
}

std::vector<int> convert_intervals_to_int3(const bevfusion::types::Int3 *intervals, uint32_t num_intervals)
{
    std::vector<int> result(num_intervals * 3);
    for (uint32_t i = 0; i < num_intervals; ++i) {
        result[i * 3 + 0] = intervals[i].x;
        result[i * 3 + 1] = intervals[i].y;
        result[i * 3 + 2] = intervals[i].z;
    }
    return result;
}

std::vector<uint16_t> convert_float_to_half(const std::vector<float> &input)
{
    std::vector<uint16_t> result(input.size());
    for (size_t i = 0; i < input.size(); ++i) {
        sycl::half h = static_cast<sycl::half>(input[i]);
        result[i] = *reinterpret_cast<uint16_t *>(&h);
    }
    return result;
}

std::vector<float> convert_half_to_float(const std::vector<uint16_t> &input)
{
    std::vector<float> result(input.size());
    for (size_t i = 0; i < input.size(); ++i) {
        sycl::half h = *reinterpret_cast<const sycl::half *>(&input[i]);
        result[i] = static_cast<float>(h);
    }
    return result;
}

std::size_t ReadPointCloud(std::string const &file_name, std::vector<float> &points)
{
    if (!boost::filesystem::exists(file_name) || file_name.empty()) {
        return 0;
    }

    std::size_t number_of_points = 0;
    std::ifstream in(file_name);
    std::string line;
    bool parse_data = false;

    while (std::getline(in, line) && points.size() <= 4 * number_of_points) {
        if (parse_data) {
            std::istringstream iss(line);
            float x, y, z, intensity;
            double timestamp;

            if (!(iss >> x >> y >> z >> intensity >> timestamp)) {
                return 0;
            }

            points.push_back(x);
            points.push_back(y);
            points.push_back(z);
            points.push_back(intensity);
        }
        else if (line.find("POINTS") != std::string::npos) {
            number_of_points = atoll(line.substr(7).c_str());
        }
        else if (line.find("DATA") != std::string::npos) {
            parse_data = true;
        }
    }

    return number_of_points;
}

std::pair<bevfusion::types::Int3*, uint32_t> load_intervals_from_bin(
    const std::string& filename, 
    sycl::queue& queue) {
    
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open intervals file: " + filename);
    }

    uint32_t num_intervals;
    file.read(reinterpret_cast<char*>(&num_intervals), sizeof(uint32_t));
    
    std::cout << "Loading " << num_intervals << " intervals from " << filename << std::endl;
    
    std::vector<bevfusion::types::Int3> intervals_cpu(num_intervals);
    for (uint32_t i = 0; i < num_intervals; ++i) {
        int32_t x, y, z;
        file.read(reinterpret_cast<char*>(&x), sizeof(int32_t));
        file.read(reinterpret_cast<char*>(&y), sizeof(int32_t));
        file.read(reinterpret_cast<char*>(&z), sizeof(int32_t));
        
        intervals_cpu[i] = bevfusion::types::Int3{x, y, z};
        
        if (i < 5) {
            std::cout << "  Interval[" << i << "]: start=" << x 
                      << ", end=" << y << ", bev_rank=" << z << std::endl;
        }
    }
    file.close();
    
    bevfusion::types::Int3* gpu_intervals = sycl::malloc_device<bevfusion::types::Int3>(num_intervals, queue);
    queue.memcpy(gpu_intervals, intervals_cpu.data(), 
                 num_intervals * sizeof(bevfusion::types::Int3)).wait();
    
    std::cout << "Intervals loaded successfully to GPU" << std::endl;
    return std::make_pair(gpu_intervals, num_intervals);
}

std::pair<uint32_t*, uint32_t> load_indices_from_bin(
    const std::string& filename, 
    sycl::queue& queue) {
    
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open indices file: " + filename);
    }

    uint32_t num_indices;
    file.read(reinterpret_cast<char*>(&num_indices), sizeof(uint32_t));
    
    std::cout << "Loading " << num_indices << " indices from " << filename << std::endl;
    
    std::vector<uint32_t> indices_cpu(num_indices);
    file.read(reinterpret_cast<char*>(indices_cpu.data()), 
              num_indices * sizeof(uint32_t));
    file.close();
    
    uint32_t* gpu_indices = sycl::malloc_device<uint32_t>(num_indices, queue);
    queue.memcpy(gpu_indices, indices_cpu.data(), 
                 num_indices * sizeof(uint32_t)).wait();
    
    std::cout << "Indices loaded successfully to GPU" << std::endl;
    return std::make_pair(gpu_indices, num_indices);
}