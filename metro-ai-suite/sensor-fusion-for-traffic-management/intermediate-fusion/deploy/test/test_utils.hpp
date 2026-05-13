#ifndef _TEST_UTILS_HPP_
#define _TEST_UTILS_HPP_

#include <vector>
#include <string>
#include <cmath>
#include <unistd.h>
#include <cstdint>
#include "common/dtype.hpp"
#include <sycl/sycl.hpp>

// Utility functions
std::vector<float> load_matrix_from_bin(const std::string &filename);
void save_matrix_to_bin(const std::string &filename, const std::vector<float> &data);
std::vector<float> generate_test_camera2lidar_matrix(int camera_id);
std::vector<float> generate_test_camera_intrinsics(int camera_id, int image_width, int image_height);
std::vector<float> generate_test_img_aug_matrix(int camera_id);
std::vector<int> convert_intervals_to_int3(const bevfusion::types::Int3 *intervals, uint32_t num_intervals);
std::vector<uint16_t> convert_float_to_half(const std::vector<float> &input);
std::vector<float> convert_half_to_float(const std::vector<uint16_t> &input);
std::size_t ReadPointCloud(std::string const &file_name, std::vector<float> &points);
// read in intervals from binary file
std::pair<bevfusion::types::Int3*, uint32_t> load_intervals_from_bin(
    const std::string& filename, 
    sycl::queue& queue);

// read in indices from binary file
std::pair<uint32_t*, uint32_t> load_indices_from_bin(
    const std::string& filename, 
    sycl::queue& queue);
// Create OpenCL queue: prefer discrete GPU, then any OpenCL GPU, else CPU
sycl::queue create_opencl_queue();

#endif  // _TEST_UTILS_HPP_