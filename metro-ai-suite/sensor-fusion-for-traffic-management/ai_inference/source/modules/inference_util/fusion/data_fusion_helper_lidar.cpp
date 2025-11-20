/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#include "modules/inference_util/fusion/data_fusion_helper_lidar.hpp"

#include <sys/stat.h>

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>
#include <cmath>

namespace hce {

namespace ai {

namespace inference {

void LidarCameraMultiCameraFuser::setNmsThreshold(float nmsThreshold)
{
    m_nmsThreshold = nmsThreshold;
}

hva::hvaStatus_t LidarCameraMultiCameraFuser::setTransformParams(std::string projectionMatrixFilePath, int32_t cameraID)
{
    // TODO: set projection matrix if need to project pixel to other coordinate
    return hva::hvaSuccess;
}

float LidarCameraMultiCameraFuser::computeIoU(const cv::Rect2f &a, const cv::Rect2f &b)
{
    float interArea = (a & b).area();
    float unionArea = a.area() + b.area() - interArea;

    return unionArea > 0 ? interArea / unionArea : 0;
}

CameraDetection2D LidarCameraMultiCameraFuser::transformDetection(const std::vector<hva::hvaROI_t> &dets, int32_t cameraID)
{
    CameraDetection2D result;
    for (const auto &det : dets) {
        result.push_back(CameraDetectionObject(cv::Rect2f(det.x, det.y, det.width, det.height), det.confidenceDetection, det.labelDetection));
    }
    return result;
}

CameraDetection2D LidarCameraMultiCameraFuser::performClassNMerge(const CameraDetection2D &objects)
{
    if (objects.empty())
        return {};

    CameraDetection2D sortedObjs = objects;
    std::sort(sortedObjs.begin(), sortedObjs.end(), [](const CameraDetectionObject &a, const CameraDetectionObject &b) { return a.confidence > b.confidence; });

    std::vector<bool> keep(sortedObjs.size(), true);
    CameraDetection2D results;

    for (size_t i = 0; i < sortedObjs.size(); ++i) {
        if (!keep[i])
            continue;

        results.push_back(sortedObjs[i]);

        for (size_t j = i + 1; j < sortedObjs.size(); ++j) {
            if (!keep[j])
                continue;

            float iou = computeIoU(cv::Rect2f(sortedObjs[i].bbox.x, sortedObjs[i].bbox.y, sortedObjs[i].bbox.width, sortedObjs[i].bbox.height),
                                   cv::Rect2f(sortedObjs[j].bbox.x, sortedObjs[j].bbox.y, sortedObjs[j].bbox.width, sortedObjs[j].bbox.height));
            if (iou > m_nmsThreshold) {
                keep[j] = false;
            }
        }
    }

    return results;
}

CameraDetection2D LidarCameraMultiCameraFuser::fuseCameraDetections(const std::vector<std::vector<hva::hvaROI_t>> &allDets)
{
    CameraDetection2D fusedResults;

    int camID = 0;
    CameraDetection2D transformedDets;
    for (const auto &dets : allDets) {
        CameraDetection2D temp = transformDetection(dets, camID);
        transformedDets.insert(transformedDets.end(), temp.begin(), temp.end());
        camID++;
    }

    std::unordered_map<std::string, CameraDetection2D> classBasedMap;
    for (const auto &det : transformedDets) {
        classBasedMap[det.label].push_back(det);
    }

    for (auto &[label, objects] : classBasedMap) {
        auto merged = performClassNMerge(objects);
        fusedResults.insert(fusedResults.end(), merged.begin(), merged.end());
    }

    return fusedResults;
}


void LidarCameraFusionOutput::setCameraDetections(int camera_id, std::vector<hva::hvaROI_t> &rois)
{
    if (camera_id >= m_numOfCams || camera_id >= m_cameraDetections.size()) {
        HVA_ERROR("camera_id is out of range!");
        return;
    }
    m_cameraDetections[camera_id] = rois;
}

void LidarCameraFusionOutput::setCameraCalib(const CalibField_t &calib)
{
    m_cameraCalibParams = calib;
}

void LidarCameraFusionOutput::setLidarDetections(const std::vector<pointpillars::ObjectDetection> &lidarDets)
{
    m_lidarDetections = lidarDets;
}

void LidarCameraFusionOutput::setfusedCameraDetections(const CameraDetection2D &fusedDetections)
{
    m_fusedCameraDetections = fusedDetections;
    m_cameraIsAssociated.resize(fusedDetections.size());
    for (int32_t i = 0; i < fusedDetections.size(); ++i) {
        m_cameraIsAssociated[i] = 0;
    }
}

void LidarCameraFusionOutput::addLidarFusionBBox(LidarCamFusionBBox &fusionBBox)
{
    m_fusionBBox.push_back(fusionBBox);
}

LidarDetectionProjection LidarCameraFusionOutput::projectLidarBoxesToCameras(const std::vector<pointpillars::ObjectDetection> &lidarDets, CalibField_t &calib)
{
    LidarDetectionProjection projection;

    for (const auto &box : lidarDets) {
        LidarProjectionBBox bbox;
        bbox.projectedCorners = project3DBoxTo2D(box, calib);
        bbox.projected2DBoxes = cv::boundingRect(bbox.projectedCorners);

        projection.push_back(bbox);
    }

    m_lidarBoxProjections = projection;

    return projection;
}

std::vector<cv::Point2f> LidarCameraFusionOutput::project3DBoxTo2D(const pointpillars::ObjectDetection &box, CalibField_t &calib)
{
    std::vector<cv::Point2f> projected;
    cv::Mat_<float> P2 = cv::Mat(3, 4, CV_32FC1, calib.cameraParams.at("P2").intrinsics).clone();                  // 3x4
    cv::Mat_<float> R0_rect = cv::Mat(4, 4, CV_32FC1, calib.transforms.at("R0_rect").data).clone();                // 4x4
    cv::Mat_<float> Tr_velo_to_cam = cv::Mat(4, 4, CV_32FC1, calib.transforms.at("Tr_velo_to_cam").data).clone();  // 4x4

    cv::Mat corner3D = get3DBoxCorners(box);                       // 3x8
    cv::Mat corner3D_homogeneous = cv::Mat::ones(4, 8, CV_32FC1);  // 4x8
    corner3D.copyTo(corner3D_homogeneous(cv::Rect(0, 0, 8, 3)));

    cv::Mat corner3D_camera_homogeneous_unrect = Tr_velo_to_cam * corner3D_homogeneous;       // 4x8
    cv::Mat corner3D_camera_homogeneous_rect = R0_rect * corner3D_camera_homogeneous_unrect;  // 4x8
    cv::Mat corner3D_image = (P2 * corner3D_camera_homogeneous_rect).t();                     // 8x3

    for (int i = 0; i < corner3D_image.rows; i++) {
        float x = corner3D_image.at<float>(i, 0);
        float y = corner3D_image.at<float>(i, 1);
        float z = corner3D_image.at<float>(i, 2);
        projected.emplace_back(x / z, y / z);
    }
    return projected;
}

cv::Mat LidarCameraFusionOutput::get3DBoxCorners(const pointpillars::ObjectDetection &box)
{
    // float x = box.x, y = box.y, z = box.z;
    // float l = box.length, w = box.width, h = box.height;
    // float yaw = box.yaw;

    // // 8 corners in local box coordinate
    // std::vector<cv::Point3f> corners;
    // std::vector<cv::Point3f> bbox_corners = {{x - l / 2, y - w / 2, z - h / 2}, {x + l / 2, y - w / 2, z - h / 2}, {x + l / 2, y - w / 2, z + h / 2},
    //                                          {x - l / 2, y - w / 2, z + h / 2}, {x - l / 2, y + w / 2, z - h / 2}, {x + l / 2, y + w / 2, z - h / 2},
    //                                          {x + l / 2, y + w / 2, z + h / 2}, {x - l / 2, y + w / 2, z + h / 2}};

    // // rotation
    // float cos_yaw = std::cos(yaw);
    // float sin_yaw = std::sin(yaw);
    // cv::Matx33f R_yaw(cos_yaw, -sin_yaw, 0, sin_yaw, cos_yaw, 0, 0, 0, 1);
    // for (const auto &pt : bbox_corners) {
    //     cv::Vec3f centered(pt.x - x, pt.y - y, pt.z - z);
    //     cv::Vec3f rotated = R_yaw * centered;
    //     corners.emplace_back(rotated[0] + x, rotated[1] + y, rotated[2] + z);
    // }

    // cv::Mat mat_corners(3, corners.size(), CV_32FC1);
    // for (size_t i = 0; i < corners.size(); ++i) {
    //     mat_corners.at<float>(0, i) = corners[i].x;
    //     mat_corners.at<float>(1, i) = corners[i].y;
    //     mat_corners.at<float>(2, i) = corners[i].z;
    // }

    // return mat_corners;

    // std::vector<cv::Point3f> points;
    float x = box.x, y = box.y, z = box.z;
    z -= 1;
    float w = box.length, l = box.width, h = box.height;
    float yaw = box.yaw;

    // 8 corners in local box coordinate
    std::vector<float> dataArr = {
        -l / 2, -w / 2, -h / 2,  // 0: rear-bottom-right
        l / 2,  -w / 2, -h / 2,  // 1: front-bottom-right
        l / 2,  w / 2,  -h / 2,  // 2: front-bottom-left
        -l / 2, w / 2,  -h / 2,  // 3: rear-bottom-left
        -l / 2, -w / 2, h / 2,   // 4: rear-top-right
        l / 2,  -w / 2, h / 2,   // 5: front-top-right
        l / 2,  w / 2,  h / 2,   // 6: front-top-left
        -l / 2, w / 2,  h / 2    // 7: rear-top-left
    };

    cv::Mat_<float> bbox_corners = cv::Mat(8, 3, CV_32FC1, dataArr.data()).clone().t();  // 3x8


    // Rotation matrix (around Z axis)
    float cos_yaw = std::cos(yaw);
    float sin_yaw = std::sin(yaw);
    cv::Matx33f R_yaw(cos_yaw, -sin_yaw, 0, sin_yaw, cos_yaw, 0, 0, 0, 1);  // 3x3

    cv::Mat corners_rotated = R_yaw * bbox_corners;  // 3x8

    cv::Mat corners = corners_rotated + (cv::Mat_<float>(3, 1) << x, y, z) * cv::Mat_<float>::ones(1, 8);  // 3x8

    return corners;
}

}  // namespace inference

}  // namespace ai

}  // namespace hce
