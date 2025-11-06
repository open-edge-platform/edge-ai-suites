/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include "modules/inference_util/lidar/kitti_loader.hpp"
#include <iostream>
#include <fstream>
#include <sstream>

namespace hce {

namespace ai {

namespace inference {

bool getPointCloudFromPath(const std::string &file_path, lidarVec_t &output)
{
    std::ifstream file(file_path, std::fstream::in | std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Failed to open point cloud file: " << file_path << std::endl;
        return false;
    }

    // Get file size
    file.seekg(0, std::ios::end);
    size_t file_size = file.tellg();
    file.seekg(0, std::ios::beg);

    // KITTI point cloud format: 4 float values per point (x, y, z, intensity)
    size_t num_points = file_size / (4 * sizeof(float));
    size_t total_floats = num_points * 4;

    output.clear();
    output.resize(total_floats);

    file.read(reinterpret_cast<char *>(output.data()), file_size);

    return !output.empty();
}

bool getImageFromPath(const std::string &file_path, std::string &imageContent, size_t &imageSize)
{
    // Load encoded binary data directly
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Failed to open encoded image file: " << file_path << std::endl;
        return false;
    }

    // Get file size and read entire file
    file.seekg(0, std::ios::end);
    size_t file_size = file.tellg();
    file.seekg(0, std::ios::beg);

    char *buff = new char[file_size];
    file.read(buff, file_size);

    imageContent.assign((char *)buff, (char *)buff + file.gcount());
    imageSize = file.gcount();
    delete[] buff;


    return !imageContent.empty();
}

bool getCalibrationFromPath(const std::string &file_path, TransformMap_t &transforms, CameraParamsMap_t &cameraParams)
{
    std::ifstream file(file_path);
    if (!file.is_open()) {
        std::cerr << "Failed to open calibration file: " << file_path << std::endl;
        return false;
    }

    transforms.clear();
    cameraParams.clear();

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream iss(line);
        std::string key;
        iss >> key;

        if (key.substr(0, 2) == "P0" || key.substr(0, 2) == "P1" || key.substr(0, 2) == "P2" || key.substr(0, 2) == "P3") {
            // Camera projection matrix
            CameraParams params;
            float p[12];
            for (int i = 0; i < 12; ++i) {
                iss >> p[i];
            }

            // Extract intrinsics from projection matrix
            for (int i = 0; i < 12; ++i) {
                params.intrinsics[i] = p[i];
            }

            cameraParams[key.substr(0, 2)] = params;
        }
        else if (key == "R0_rect:") {
            // Rectification rotation matrix
            Transform4x4 transform;
            for (int i = 0; i < 9; ++i) {
                float val;
                iss >> val;
                int row = i / 3;
                int col = i % 3;
                transform(row, col) = val;
            }
            transform(3, 3) = 1.0f;
            transforms["R0_rect"] = transform;
        }
        else if (key == "Tr_velo_to_cam:") {
            // LiDAR to camera transformation
            Transform4x4 transform;
            for (int i = 0; i < 12; ++i) {
                iss >> transform.data[i];
            }
            transform.data[12] = 0;
            transform.data[13] = 0;
            transform.data[14] = 0;
            transform.data[15] = 1;
            transforms["lidar_to_camera"] = transform;
            transforms["Tr_velo_to_cam"] = transform;
        }
        else if (key == "Tr_imu_to_velo:") {
            // IMU to LiDAR transformation
            Transform4x4 transform;
            for (int i = 0; i < 12; ++i) {
                iss >> transform.data[i];
            }
            transform.data[12] = 0;
            transform.data[13] = 0;
            transform.data[14] = 0;
            transform.data[15] = 1;
            transforms["imu_to_lidar"] = transform;
            transforms["Tr_imu_to_velo"] = transform;
        }
    }

    return true;
}

}  // namespace inference

}  // namespace ai

}  // namespace hce
