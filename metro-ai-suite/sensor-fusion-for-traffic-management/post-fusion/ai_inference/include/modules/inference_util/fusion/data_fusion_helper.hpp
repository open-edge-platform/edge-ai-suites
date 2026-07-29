/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2023 Intel Corporation.
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

#ifndef HCE_AI_INF_DATA_FUSION_HELPER_HPP
#define HCE_AI_INF_DATA_FUSION_HELPER_HPP

#include <cstdint>
#include <fstream>
#include <memory>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

#include "inc/api/hvaLogger.hpp"
#include "inc/util/hvaUtil.hpp"
#include "nodes/radarDatabaseMeta.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"

#define FUSION_PI (3.141592653589793f)  //!< define pi

namespace hce {

namespace ai {

namespace inference {

using track2TrackAssociationOutput = coordinateTransformationOutput;
using postFusionOutput = coordinateTransformationOutput;

/**
 * @brief Get the size of bin file
 *
 * @param path: the file path
 * @return size of bin file
 */
size_t getBinSize(std::string path);

/**
 * @brief Read data from bin file.
 *
 * @param path: the file path
 * @param buf: data buffer
 * @param size: the size of bin file
 * @return 0 means success
 */
size_t readBin(std::string path, char *buf, size_t size);

class CoordinateTransformation {
  public:
    CoordinateTransformation() {};

    CoordinateTransformation(const std::string &registrationMatrixFilePath, const std::string &qMatrixFilePath, const std::string &homographyMatrixFilePath)
        : m_registrationMatrixFilePath(registrationMatrixFilePath), m_qMatrixFilePath(qMatrixFilePath), m_homographyMatrixFilePath(homographyMatrixFilePath)
    {
        if (hva::hvaFailure == getCalibrationParameters()) {
            HVA_ERROR("Get calibration parameters failed!");
        }
    };

    ~CoordinateTransformation() {};

    void
    setParameters(std::string registrationMatrixFilePath, std::string qMatrixFilePath, std::string homographyMatrixFilePath, std::vector<int> pclConstraints);

    /**
     * @brief convert detections from camera(pixel coordinates) to radar coordinate
     *
     * @param rect camera detection
     * @return cv::Rect2f
     */
    cv::Rect2f pixel2Radar(cv::Rect2i &rect);

    /**
     * @brief convert detections from camera to radar coordinate
     *
     * @param disparityMap input disparity map
     * @param rect camera detection
     * @return cv::Rect2f
     */
    cv::Rect2f camera2Radar(cv::Mat &disparityMap, cv::Rect2i &rect);

    /**
     * @brief convert detections from camera to radar coordinate
     *
     * @param pcl input pcl
     * @param rect camera detection
     * @return cv::Rect2f
     */
    cv::Rect2f pcl2Radar(cv::Mat &pcl, cv::Rect2i &rect);

  private:
    // std::string m_sensorsParamPath;  // sensros parameters path
    std::string m_registrationMatrixFilePath;
    std::string m_qMatrixFilePath;
    std::string m_homographyMatrixFilePath;
    std::vector<int> m_hsvLowerBound;
    std::vector<int> m_hsvHigherBound;
    std::vector<int> m_pclConstraints;
    // cv::Mat_<float> m_leftMapsMatrix;      // left maps matrix
    // cv::Mat_<float> m_rightMapsMatrix;     // right maps matrix
    // cv::Mat_<float> m_projLeftMatrix;      // proj left matrix
    // cv::Mat_<float> m_projRightMatrix;     // proj right matrix
    // cv::Mat_<int32_t> m_roiLeftMatrix;     // roi left matrix
    // cv::Mat_<int32_t> m_roiRightMatrix;    // roi right matrix
    cv::Mat_<float> m_qMatrix;             // disparity to depth projection matrix
    cv::Mat_<float> m_registrationMatrix;  // camera to radar projection matrix
    cv::Mat_<float> m_homographyMatrix;    // pixel to radar homography matrix

    /**
     * @brief generate pcl from disparity map
     *
     * @param disparityMap input disparity map
     * @param pcl output pcl
     * @return hva::hvaStatus_t
     */
    hva::hvaStatus_t generatePcl(cv::Mat &disparityMap, cv::Mat &pcl);

    /**
     * @brief get the median value of input matrix
     *
     * @param channel single channel input matrix
     * @return float
     */
    float medianMat(cv::Mat channel);


    /**
     * @brief get center bbox
     *
     * @param pcl input bbox
     * @param widthRatio width center ratio
     * @param heightRatio height center ratio
     * @return cv::Rect2i
     */
    cv::Rect2i getCenterBox(cv::Rect2i &rect, float widthRatio, float heightRatio);

    /**
     * @brief read parameters from bin file
     * @param filePath file path of matrix files
     * @param type type of matrix
     * @return success or fail
     */
    hva::hvaStatus_t readMatrix(std::string filePath, std::string type);

    /**
     * @brief get calibration parameters
     * @return success or fail
     */
    hva::hvaStatus_t getCalibrationParameters();
};

class MultiCameraFuser {
  private:
    float m_nmsThreshold;

    std::unordered_map<int32_t, cv::Mat_<float>> m_homographyMatrixMap;  // pixel to radar homography matrix

    /**
     * @brief read parameters from bin file
     * @param filePath file path of matrix files
     * @return success or fail
     */
    hva::hvaStatus_t readMatrix(std::string &filePath, int32_t cameraID);

    float computeIoU(const cv::Rect2f &a, const cv::Rect2f &b);

    DetectedObject transformDetection(const hva::hvaROI_t &det, int32_t cameraID);

    std::vector<DetectedObject> performClassNMerge(const std::vector<DetectedObject> &objects);

  public:
    using Ptr = std::shared_ptr<MultiCameraFuser>;


    void setNmsThreshold(float nmsThreshold);

    /**
     * @brief set transform params
     * @return success or fail
     */
    hva::hvaStatus_t setTransformParams(std::string homographyMatrixFilePath, int32_t cameraID);

    /**
     * @brief fuse 2 Camera
     * @return camera fusion result
     */
    std::vector<DetectedObject> fuse2Camera(const std::vector<hva::hvaROI_t> &leftDets, const std::vector<hva::hvaROI_t> &rightDets);

    /**
     * @brief fuse 4 Camera
     * @return camera fusion result
     */
    std::vector<DetectedObject> fuse4Camera(const std::vector<hva::hvaROI_t> &firstDets,
                                            const std::vector<hva::hvaROI_t> &secondDets,
                                            const std::vector<hva::hvaROI_t> &thirdDets,
                                            const std::vector<hva::hvaROI_t> &fourthDets);

    MultiCameraFuser(float nmsThreshold) : m_nmsThreshold(nmsThreshold) {}

    MultiCameraFuser() : m_nmsThreshold(0.5) {}

    ~MultiCameraFuser() {}
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif