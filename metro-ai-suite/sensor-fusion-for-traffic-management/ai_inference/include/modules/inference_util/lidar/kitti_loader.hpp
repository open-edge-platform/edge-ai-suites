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

#ifndef HCE_AI_INF_KITTI_LOADER_HPP
#define HCE_AI_INF_KITTI_LOADER_HPP

#include <string>

#include "nodes/lidarDatabaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

bool getPointCloudFromPath(const std::string &file_path, lidarVec_t &output);
bool getImageFromPath(const std::string &file_path, std::string &imageContent, size_t &imageSize);
bool getCalibrationFromPath(const std::string &file_path, TransformMap_t &transforms, CameraParamsMap_t &cameraParams);


}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_KITTI_LOADER_HPP
