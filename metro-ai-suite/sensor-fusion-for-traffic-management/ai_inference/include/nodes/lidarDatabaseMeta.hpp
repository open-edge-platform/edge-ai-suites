/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#ifndef HCE_AI_INF_LIDAR_DATABASE_META_HPP
#define HCE_AI_INF_LIDAR_DATABASE_META_HPP

#include <unordered_map>
#include <vector>
#include <cstring>
#include <string>
#include <opencv2/opencv.hpp>
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "liblidar.hpp"

namespace hce {

namespace ai {

namespace inference {

typedef std::vector<float> lidarVec_t;

// Transformation matrix (4x4) using standard array
struct Transform4x4
{
    float data[16];

    Transform4x4()
    {
        memset(data, 0, sizeof(data));
        // Set as identity matrix
        data[0] = data[5] = data[10] = data[15] = 1.0f;
    }

    float &operator()(int row, int col)
    {
        return data[row * 4 + col];
    }
    const float &operator()(int row, int col) const
    {
        return data[row * 4 + col];
    }
};

typedef std::unordered_map<std::string, Transform4x4> TransformMap_t;

// Camera intrinsics matrix (3x4) and distortion parameters
struct CameraParams
{
    float intrinsics[12];  // 3x4 matrix stored row-major

    CameraParams()
    {
        memset(intrinsics, 0, sizeof(intrinsics));
    }

    float &K(int row, int col)
    {
        return intrinsics[row * 4 + col];
    }
    const float &K(int row, int col) const
    {
        return intrinsics[row * 4 + col];
    }
};

typedef std::unordered_map<std::string, CameraParams> CameraParamsMap_t;


struct CalibField_t
{
    TransformMap_t transforms;
    CameraParamsMap_t cameraParams;
};

// // 2D detection results of a single camera
// // also can be 2D detection results after multi-camera fusion
// struct CameraDetection2D
// {
//     int camera_id;  // -1 means fused camera detections
//     std::vector<cv::Rect2f> bboxes;
//     std::vector<float> scores;
//     std::vector<std::string> classes;
// };

// single 2D detection results
struct CameraDetectionObject
{
    cv::Rect2f bbox;
    float confidence;
    std::string label;

    CameraDetectionObject() : bbox(), confidence(0.0f), label("dummy") {}

    CameraDetectionObject(const cv::Rect2f &bbox_, float confidence_ = 0.0f, const std::string &label_ = "dummy")
        : bbox(bbox_), confidence(confidence_), label(label_)
    {
    }
};

typedef std::vector<CameraDetectionObject> CameraDetection2D;

// Projection result of the lidar 3D detection frame on the pixel plane
struct LidarProjectionBBox
{
    std::vector<cv::Point2f> projectedCorners;  // The coordinates of the 8 corner points of each 3D detection box on the pixel plane
    cv::Rect2f projected2DBoxes;                // 2D bbox on the pixel plane

    LidarProjectionBBox() : projectedCorners(), projected2DBoxes() {}
};

typedef std::vector<LidarProjectionBBox> LidarDetectionProjection;

struct LidarCamFusionBBox
{
    pointpillars::ObjectDetection lidarOutput;  // lidar output
    CameraDetectionObject det;                  // corresponding camera detections after fusion, no value if no corresponding camera detections
    LidarProjectionBBox lidarProjectionBBox;    // lidar projection bbox
    LidarCamFusionBBox() : lidarOutput(), det(), lidarProjectionBBox() {}
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_LIDAR_DATABASE_META_HPP
