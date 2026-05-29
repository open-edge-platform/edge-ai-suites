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

#ifndef HCE_AI_INF_DATA_FUSION_HELPER_LIDAR_HPP
#define HCE_AI_INF_DATA_FUSION_HELPER_LIDAR_HPP

#include <cstdint>
#include <fstream>
#include <memory>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

#include "inc/api/hvaLogger.hpp"
#include "inc/util/hvaUtil.hpp"
#include "nodes/lidarDatabaseMeta.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"

#include "liblidar.hpp"

#define FUSION_PI (3.141592653589793f)  //!< define pi

namespace hce {

namespace ai {

namespace inference {

class LidarCameraMultiCameraFuser {
  private:
    float m_nmsThreshold;

    std::unordered_map<int32_t, cv::Mat_<float>> m_projectionMatrixMap;  // projection matrix, interface reserved for future use

    float computeIoU(const cv::Rect2f &a, const cv::Rect2f &b);

    CameraDetection2D transformDetection(const std::vector<hva::hvaROI_t> &dets, int32_t cameraID);

    CameraDetection2D performClassNMerge(const CameraDetection2D &objects);

  public:
    using Ptr = std::shared_ptr<LidarCameraMultiCameraFuser>;


    void setNmsThreshold(float nmsThreshold);

    /**
     * @brief set transform params
     * @return success or fail
     */
    hva::hvaStatus_t setTransformParams(std::string homographyMatrixFilePath, int32_t cameraID);

    /**
     * @brief fuse Camera Detections
     * @return camera fusion result
     */
    CameraDetection2D fuseCameraDetections(const std::vector<std::vector<hva::hvaROI_t>> &allDets);

    LidarCameraMultiCameraFuser(float nmsThreshold) : m_nmsThreshold(nmsThreshold) {}

    LidarCameraMultiCameraFuser() : m_nmsThreshold(0.5) {}

    ~LidarCameraMultiCameraFuser() {}
};


// Fusion output main structure
class LidarCameraFusionOutput {
  public:
    int32_t m_numOfCams;

    std::vector<std::vector<hva::hvaROI_t>> m_cameraDetections;    // origin camera detections
    std::vector<pointpillars::ObjectDetection> m_lidarDetections;  // origin lidar detections
    CalibField_t m_cameraCalibParams;                              // camera calibration parameters

    LidarDetectionProjection m_lidarBoxProjections;  // lidar projection results
    CameraDetection2D m_fusedCameraDetections;       // fused camera detections or single camera detections
    std::vector<int8_t> m_cameraIsAssociated;        // whether the fusion camera detections is associated with lidar
    std::vector<LidarCamFusionBBox> m_fusionBBox;    // final lidar&camera fusion results

  public:
    void setCameraDetections(int camera_id, std::vector<hva::hvaROI_t> &rois);

    void setCameraCalib(const CalibField_t &calib);

    void setLidarDetections(const std::vector<pointpillars::ObjectDetection> &lidarDets);

    void setfusedCameraDetections(const CameraDetection2D &fusedDetections);

    void addLidarFusionBBox(LidarCamFusionBBox &fusionBBox);

    LidarDetectionProjection projectLidarBoxesToCameras(const std::vector<pointpillars::ObjectDetection> &lidarDets, CalibField_t &calib);

  public:
    using Ptr = std::shared_ptr<LidarCameraFusionOutput>;

    LidarCameraFusionOutput(int32_t numOfCams) : m_numOfCams(numOfCams)
    {
        m_cameraDetections.resize(m_numOfCams);
    }

    LidarCameraFusionOutput() : m_numOfCams(1)
    {
        m_cameraDetections.resize(m_numOfCams);
    }

    ~LidarCameraFusionOutput() {}

  private:
    std::vector<cv::Point2f> project3DBoxTo2D(const pointpillars::ObjectDetection &box, CalibField_t &calib);
    cv::Mat get3DBoxCorners(const pointpillars::ObjectDetection &box);
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif