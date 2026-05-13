#include "common.hpp"

std::vector<float> readFeatureWithShape(const std::string& bin_file, 
                                       const std::vector<int>& expected_shape) {
    std::vector<float> data = readBinFile(bin_file);
    
    if (!validateShape(data, expected_shape)) {
        std::cerr << "Warning: Feature shape mismatch for file: " << bin_file << std::endl;
    }
    
    return data;
}

std::vector<float> readCameraFeature(const std::string& bin_file) {
    std::vector<float> data = readBinFile(bin_file);
    std::vector<int> expected_shape = {1, 80, 128, 128}; // 1 * 80 * 128 * 128 = 1,310,720
    
    if (!validateShape(data, expected_shape)) {
        std::cerr << "Warning: Camera feature shape mismatch!" << std::endl;
    }
    
    return data;
}

std::vector<float> readLidarFeature(const std::string& bin_file) {
    std::vector<float> data = readBinFile(bin_file);
    std::vector<int> expected_shape = {1, 64, 128, 128}; // 1 * 64 * 128 * 128 = 1,048,576
    
    if (!validateShape(data, expected_shape)) {
        std::cerr << "Warning: Lidar feature shape mismatch!" << std::endl;
    }
    
    return data;
}
bool validateShape(const std::vector<float>& data, const std::vector<int>& expected_shape) {
    size_t expected_size = 1;
    for (int dim : expected_shape) {
        expected_size *= dim;
    }
    
    bool is_valid = (data.size() == expected_size);
    
    std::cout << "Expected size: " << expected_size << ", Actual size: " << data.size();
    if (is_valid) {
        std::cout << " ✓" << std::endl;
    } else {
        std::cout << " ✗" << std::endl;
    }
    
    return is_valid;
}

// Utility functions implementation
std::vector<float> readBinFile(const std::string& bin_file) {
    std::ifstream file(bin_file, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + bin_file);
    }
    
    file.seekg(0, std::ios::end);
    std::streamsize file_size = file.tellg();
    file.seekg(0, std::ios::beg);
    
    size_t num_floats = file_size / sizeof(float);

    std::vector<float> data(num_floats);
    file.read(reinterpret_cast<char*>(data.data()), file_size);
    
    if (!file) {
        throw std::runtime_error("Error reading file: " + bin_file);
    }
    
    file.close();
    
    std::cout << "Read " << num_floats << " floats from " << bin_file << std::endl;
    return data;
}