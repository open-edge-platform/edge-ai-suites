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

#include "modules/inference_util/fusion/data_fusion_helper.hpp"

#include <sys/stat.h>

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>
#include <cmath>

namespace hce {

namespace ai {

namespace inference {

/**
 * @brief Get the size of bin file
 *
 * @param path: the file path
 * @return size of bin file
 */
size_t getBinSize(std::string path)
{
    size_t size = 0;
    struct stat buffer;
    std::ifstream infile;
    if (0 != stat(path.c_str(), &buffer)) {
        throw std::invalid_argument("File " + path + " not exist!");
    }

    infile.open(path, std::ifstream::binary);
    if (!infile) {
        throw std::runtime_error("Open file " + path + " failed!");
    }

    infile.seekg(0, infile.end);
    size = infile.tellg();
    infile.seekg(0, infile.beg);
    infile.close();

    return size;
}

/**
 * @brief Read data from bin file.
 *
 * @param path: the file path
 * @param buf: data buffer
 * @param size: the size of bin file
 * @return 0 means success
 */
size_t readBin(std::string path, char *buf, size_t size)
{
    struct stat buffer;
    std::ifstream infile;

    if (0 != stat(path.c_str(), &buffer)) {
        throw std::invalid_argument("File " + path + " not exist!");
    }

    infile.open(path, std::ifstream::binary);
    if (!infile) {
        throw std::runtime_error("Open file " + path + " failed!");
    }

    infile.read(static_cast<char *>(buf), size);
    infile.close();
    return 0;
}

void CoordinateTransformation::setParameters(std::string registrationMatrixFilePath,
                                             std::string qMatrixFilePath,
                                             std::string homographyMatrixFilePath,
                                             std::vector<int> pclConstraints)
{
    m_registrationMatrixFilePath = registrationMatrixFilePath;
    m_qMatrixFilePath = qMatrixFilePath;
    m_homographyMatrixFilePath = homographyMatrixFilePath;
    m_pclConstraints = pclConstraints;
    if (hva::hvaFailure == getCalibrationParameters()) {
        HVA_ERROR("Get calibration parameters failed!");
    }
}

/**
 * @brief convert detections from camera(pixel coordinates) to radar coordinate
 *
 * @param rect camera detection
 * @return cv::Rect2f
 */
cv::Rect2f CoordinateTransformation::pixel2Radar(cv::Rect2i &rect)
{
    float centerX = rect.x + rect.width / 2;
    float centerY = rect.y + rect.height / 2;

    std::vector<cv::Point2f> pixelPoints;
    pixelPoints.push_back(cv::Point2f(centerX, centerY));
    std::vector<cv::Point2f> radarPoints;

    cv::perspectiveTransform(pixelPoints, radarPoints, m_homographyMatrix);

    return cv::Rect2f(radarPoints[0].x, radarPoints[0].y, 4.2, 1.7);
}

cv::Rect2f CoordinateTransformation::camera2Radar(cv::Mat &disparityMap, cv::Rect2i &rect)
{
    cv::Mat pcl;

    if (hva::hvaFailure == generatePcl(disparityMap, pcl)) {
        HVA_ERROR("generate pcl from disparity map failed!");
        return cv::Rect2f(0, 0, 0, 0);
    }
    // cv::Rect2i centerRect = getCenterBox(rect, 0.8, 0.7);
    cv::Rect2f output = pcl2Radar(pcl, rect);
    return output;
}

hva::hvaStatus_t CoordinateTransformation::generatePcl(cv::Mat &disparityMap, cv::Mat &pcl)
{
    if (disparityMap.type() != CV_32F || disparityMap.empty()) {
        HVA_ERROR("type of disparityMap is not correct or disparityMap is empty!");
        return hva::hvaFailure;
    }
    // 3-channel matrix for containing the reprojected 3D world coordinates
    pcl = cv::Mat::zeros(disparityMap.size(), CV_32FC3);

    cv::reprojectImageTo3D(disparityMap, pcl, m_qMatrix, false, CV_32F);

    for (int i = 0; i < disparityMap.rows; i++) {
        cv::Vec3f *out3DPtr = pcl.ptr<cv::Vec3f>(i);
        for (int j = 0; j < disparityMap.cols; j++) {
            cv::Vec3f &point = out3DPtr[j];
            if (point[0] < m_pclConstraints[0] || point[0] > m_pclConstraints[1]) {
                point[0] = m_pclConstraints[0];
            }
            if (point[1] < m_pclConstraints[2] || point[1] > m_pclConstraints[3]) {
                point[1] = m_pclConstraints[2];
            }
            if (point[2] < m_pclConstraints[4] || point[2] > m_pclConstraints[5]) {
                point[2] = m_pclConstraints[4];
            }
        }
    }

    // /***** reproject image to 3D, custom implement of reprojectImageTo3D *****/
    // // Getting the interesting parameters from Q, everything else is zero or one
    // float Q03 = m_qMatrix.at<float>(0, 3);
    // float Q13 = m_qMatrix.at<float>(1, 3);
    // float Q23 = m_qMatrix.at<float>(2, 3);
    // float Q32 = m_qMatrix.at<float>(3, 2);
    // float Q33 = m_qMatrix.at<float>(3, 3);
    // // Transforming a single-channel disparity map to a 3-channel image
    // // representing a 3D surface
    // for (int i = 0; i < disparityMap.rows; i++) {
    //     const float *dispPtr = disparityMap.ptr<float>(i);
    //     cv::Vec3f *out3DPtr = pcl.ptr<cv::Vec3f>(i);

    //     for (int j = 0; j < disparityMap.cols; j++) {
    //         const float pw = 1.0f / (dispPtr[j] * Q32 + Q33);
    //         cv::Vec3f &point = out3DPtr[j];
    //         point[0] = (static_cast<float>(j) + Q03) * pw;
    //         point[1] = (static_cast<float>(i) + Q13) * pw;
    //         point[2] = Q23 * pw;

    //         if (point[0] < m_pclConstraints[0] || point[0] > m_pclConstraints[1]) {
    //             point[0] = m_pclConstraints[0];
    //         }
    //         if (point[1] < m_pclConstraints[2] || point[1] > m_pclConstraints[3]) {
    //             point[1] = m_pclConstraints[2];
    //         }
    //         if (point[2] < m_pclConstraints[4] || point[2] > m_pclConstraints[5]) {
    //             point[2] = m_pclConstraints[4];
    //         }
    //     }
    // }

    return hva::hvaSuccess;
}

cv::Rect2f CoordinateTransformation::pcl2Radar(cv::Mat &pcl, cv::Rect2i &rect)
{
    cv::Mat selectedPcl;
    // for (int i = 0; i < pclRect.rows; i++) {
    //     cv::Vec3f *out3DPtr = pclRect.ptr<cv::Vec3f>(i);
    //     for (int j = 0; j < pclRect.cols; j++) {
    //         cv::Vec3f &point = out3DPtr[j];
    //         if (point[0] > m_pclConstraints[0] && point[1] >
    //         m_pclConstraints[2] && point[2] > m_pclConstraints[4]) {
    //             selectedPcl.push_back(point);
    //         }
    //     }
    // }
    for (int i = rect.y; i < rect.y + rect.height + 1; i++) {
        cv::Vec3f *out3DPtr = pcl.ptr<cv::Vec3f>(i);
        for (int j = rect.x; j < rect.x + rect.width + 1; j++) {
            cv::Vec3f &point = out3DPtr[j];
            if (point[0] > m_pclConstraints[0] && point[1] > m_pclConstraints[2] && point[2] > m_pclConstraints[4]) {
                cv::Mat temp = (cv::Mat_<float>(1, 3) << point[0], point[1], point[2]);
                selectedPcl.push_back(temp);
            }
        }
    }
    if (100 > selectedPcl.rows) {
        return cv::Rect2f(0, 0, 0, 0);
    }

    cv::Mat targetPoint = (cv::Mat_<float>(1, 4) << cv::mean(selectedPcl.col(0))[0], cv::mean(selectedPcl.col(1))[0], cv::mean(selectedPcl.col(2))[0], 1);
    cv::Mat radarCoords = targetPoint * m_registrationMatrix;
    std::cout << targetPoint << std::endl;
    std::cout << radarCoords << std::endl;
    HVA_DEBUG("lowerX(%f), lowerY(%f), upperX(%f), upperY(%f)", radarCoords.ptr<float>(0)[1], radarCoords.ptr<float>(0)[0], 4.2, 1.7);
    return cv::Rect2f(radarCoords.ptr<float>(0)[1], radarCoords.ptr<float>(0)[0], 4.2, 1.7);

    // return cv::Rect2f(cv::mean(selectedPcl.col(2))[0], cv::mean(selectedPcl.col(0))[0], 4.2, 1.7);

    // std::vector<cv::Mat> channels(3);
    // cv::Mat targetPoint2 = (cv::Mat_<float>(1, 4) << medianMat(selectedPcl.col(0)), medianMat(selectedPcl.col(1)), medianMat(selectedPcl.col(2)), 1);
    // cv::Mat radarCoords2 = targetPoint2 * m_registrationMatrix;
    // std::cout << targetPoint2 << std::endl;
    // std::cout << radarCoords2 << std::endl;
    // HVA_DEBUG("lowerX(%f), lowerY(%f), upperX(%f), upperY(%f)", radarCoords2.ptr<float>(0)[1], radarCoords2.ptr<float>(0)[0], 4.2, 1.7);
    // // return cv::Rect2f(radarCoords.ptr<float>(0)[1], radarCoords.ptr<float>(0)[0], 4.2, 1.7);

    // cv::Mat selectedPclAddOnes;
    // cv::Mat onesColumn = cv::Mat::ones(selectedPcl.rows, 1, selectedPcl.type());
    // cv::hconcat(selectedPcl, onesColumn, selectedPclAddOnes);
    // cv::Mat radarCoords3 = selectedPclAddOnes * m_registrationMatrix;

    // float lowerX, upperX;
    // cv::Scalar colFirstMean, colFirstStd;
    // cv::meanStdDev(radarCoords3.col(0), colFirstMean, colFirstStd);
    // lowerX = colFirstMean[0] - colFirstStd[0] * 1.0;
    // upperX = colFirstMean[0] + colFirstStd[0] * 1.0;

    // float lowerY, upperY;
    // cv::Scalar colSecondMean, colSecondStd;
    // cv::meanStdDev(radarCoords3.col(1), colSecondMean, colSecondStd);
    // lowerY = colSecondMean[0] - colSecondStd[0] * 1.0;
    // upperY = colSecondMean[0] + colSecondStd[0] * 1.0;
    // HVA_DEBUG("colFirstMean(%f), colSecondMean(%f)", colFirstMean, colSecondMean);
    // HVA_DEBUG("lowerX(%f), lowerY(%f), upperX(%f), upperY(%f)", lowerX, lowerY, upperX, upperY);
    // // return cv::Rect2f(lowerY, lowerX, upperY - lowerY, upperX - lowerX);

    // return cv::Rect2f(radarCoords.ptr<float>(0)[1], radarCoords.ptr<float>(0)[0], 4.2, 1.7);
}


float CoordinateTransformation::medianMat(cv::Mat channel)
{
    std::vector<float> vecFromMat;
    if (channel.isContinuous()) {
        vecFromMat.assign(channel.data, channel.data + channel.total() * channel.channels());
    }
    else {
        for (int i = 0; i < channel.rows; ++i) {
            vecFromMat.insert(vecFromMat.end(), channel.ptr<float>(i), channel.ptr<float>(i) + channel.cols * channel.channels());
        }
    }

    std::nth_element(vecFromMat.begin(), vecFromMat.begin() + vecFromMat.size() / 2, vecFromMat.end());

    return vecFromMat[vecFromMat.size() / 2];
}


/**
 * @brief get center bbox
 *
 * @param pcl input bbox
 * @param widthRatio width center ratio
 * @param heightRatio height center ratio
 * @return cv::Rect2i
 */
cv::Rect2i CoordinateTransformation::getCenterBox(cv::Rect2i &rect, float widthRatio = 0.8, float heightRatio = 0.8)
{
    float x_c = int(rect.x + rect.width / 2);
    float y_c = int(rect.y + rect.height / 2);
    float width = widthRatio * rect.width;
    float height = heightRatio * rect.height;
    return cv::Rect2i(int(x_c - width / 2), int(y_c) - height / 2, width, height);
}

/**
 * @brief read parameters from bin file
 * @param filePath file path of matrix files
 * @return success or fail
 */
hva::hvaStatus_t CoordinateTransformation::readMatrix(std::string filePath, std::string type)
{
    size_t bytes;
    size_t dataNum;
    size_t ret;

    char *buf;
    float *dataArr;

    bytes = getBinSize(filePath);
    if (0 > bytes) {
        HVA_ERROR("Read file %s failed!", filePath);
        return hva::hvaFailure;
    }
    dataNum = bytes / sizeof(float);
    buf = new char[bytes];
    ret = readBin(filePath, buf, bytes);
    if (0 > ret) {
        HVA_ERROR("Read file %s failed!", filePath);
        return hva::hvaFailure;
    }

    if ("q" == type) {
        dataArr = reinterpret_cast<float *>(buf);
        m_qMatrix = cv::Mat(4, 4, CV_32FC1, dataArr).clone();
    }
    else if ("registration" == type) {
        dataArr = reinterpret_cast<float *>(buf);
        m_registrationMatrix = cv::Mat(4, 2, CV_32FC1, dataArr).clone();
    }
    else if ("h" == type) {
        dataArr = reinterpret_cast<float *>(buf);
        m_homographyMatrix = cv::Mat(3, 3, CV_32FC1, dataArr).clone();
    }
    else {
        HVA_ERROR("Unsupported read matrix flag %s!", type);
        return hva::hvaFailure;
    }
    delete[] buf;
    return hva::hvaSuccess;
}

/**
 * @brief get calibration parameters
 * @return success or fail
 */
hva::hvaStatus_t CoordinateTransformation::getCalibrationParameters()
{
    if (hva::hvaFailure == readMatrix(m_registrationMatrixFilePath, "registration")) {
        HVA_ERROR("Read file %s failed!", m_registrationMatrixFilePath);
        return hva::hvaFailure;
    }

    if (hva::hvaFailure == readMatrix(m_qMatrixFilePath, "q")) {
        HVA_ERROR("Read file %s failed!", m_qMatrixFilePath);
        return hva::hvaFailure;
    }

    if (hva::hvaFailure == readMatrix(m_homographyMatrixFilePath, "h")) {
        HVA_ERROR("Read file %s failed!", m_homographyMatrixFilePath);
        return hva::hvaFailure;
    }

    return hva::hvaSuccess;
}

/**
 * @brief read parameters from bin file
 * @return success or fail
 */
hva::hvaStatus_t MultiCameraFuser::readMatrix(std::string &filePath, int32_t cameraID)
{
    size_t bytes;
    size_t dataNum;
    size_t ret;

    char *buf;
    float *dataArr;

    bytes = getBinSize(filePath);
    if (0 > bytes) {
        HVA_ERROR("Read file %s failed!", filePath);
        return hva::hvaFailure;
    }
    dataNum = bytes / sizeof(float);
    buf = new char[bytes];
    ret = readBin(filePath, buf, bytes);
    if (0 > ret) {
        HVA_ERROR("Read file %s failed!", filePath);
        return hva::hvaFailure;
    }

    dataArr = reinterpret_cast<float *>(buf);
    m_homographyMatrixMap[cameraID] = cv::Mat(3, 3, CV_32FC1, dataArr).clone();

    delete[] buf;
    return hva::hvaSuccess;
}

void MultiCameraFuser::setNmsThreshold(float nmsThreshold)
{
    m_nmsThreshold = nmsThreshold;
}

hva::hvaStatus_t MultiCameraFuser::setTransformParams(std::string homographyMatrixFilePath, int32_t cameraID)
{
    if (hva::hvaFailure == readMatrix(homographyMatrixFilePath, cameraID)) {
        HVA_ERROR("Read file %s failed!", homographyMatrixFilePath);
        return hva::hvaFailure;
    }

    return hva::hvaSuccess;
}

float MultiCameraFuser::computeIoU(const cv::Rect2f &a, const cv::Rect2f &b)
{
    float interArea = (a & b).area();
    float unionArea = a.area() + b.area() - interArea;

    return unionArea > 0 ? interArea / unionArea : 0;
}

DetectedObject MultiCameraFuser::transformDetection(const hva::hvaROI_t &det, int32_t cameraID)
{
    float centerX = det.x + det.width / 2;
    float centerY = det.y + det.height / 2;

    std::vector<cv::Point2f> pixelPoints;
    pixelPoints.push_back(cv::Point2f(centerX, centerY));
    std::vector<cv::Point2f> radarPoints;

    cv::perspectiveTransform(pixelPoints, radarPoints, m_homographyMatrixMap[cameraID]);

    return DetectedObject(BBox(radarPoints[0].x, radarPoints[0].y, 4.2, 1.7), det.confidenceDetection, det.labelDetection);
}

std::vector<DetectedObject> MultiCameraFuser::performClassNMerge(const std::vector<DetectedObject> &objects)
{
    if (objects.empty())
        return {};

    std::vector<DetectedObject> sortedObjs = objects;
    std::sort(sortedObjs.begin(), sortedObjs.end(), [](const DetectedObject &a, const DetectedObject &b) { return a.confidence > b.confidence; });

    std::vector<bool> keep(sortedObjs.size(), true);
    std::vector<DetectedObject> results;

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

std::vector<DetectedObject> MultiCameraFuser::fuse2Camera(const std::vector<hva::hvaROI_t> &leftDets, const std::vector<hva::hvaROI_t> &rightDets)
{
    std::vector<DetectedObject> fusedResults;

    std::vector<DetectedObject> transformedDets;
    for (const auto &det : leftDets) {
        transformedDets.push_back(transformDetection(det, 0));
    }

    for (const auto &det : rightDets) {
        transformedDets.push_back(transformDetection(det, 1));
    }

    std::unordered_map<std::string, std::vector<DetectedObject>> classBasedMap;
    for (const auto &det : transformedDets) {
        classBasedMap[det.label].push_back(det);
    }

    for (auto &[label, objects] : classBasedMap) {
        auto merged = performClassNMerge(objects);
        fusedResults.insert(fusedResults.end(), merged.begin(), merged.end());
    }

    return fusedResults;
}

std::vector<DetectedObject> MultiCameraFuser::fuse4Camera(const std::vector<hva::hvaROI_t> &firstDets,
                                                          const std::vector<hva::hvaROI_t> &secondDets,
                                                          const std::vector<hva::hvaROI_t> &thirdDets,
                                                          const std::vector<hva::hvaROI_t> &fourthDets)
{
    std::vector<DetectedObject> fusedResults;

    std::vector<DetectedObject> transformedDets;
    for (const auto &det : firstDets) {
        transformedDets.push_back(transformDetection(det, 0));
    }

    for (const auto &det : secondDets) {
        transformedDets.push_back(transformDetection(det, 1));
    }

    for (const auto &det : thirdDets) {
        transformedDets.push_back(transformDetection(det, 2));
    }

    for (const auto &det : fourthDets) {
        transformedDets.push_back(transformDetection(det, 3));
    }

    std::unordered_map<std::string, std::vector<DetectedObject>> classBasedMap;
    for (const auto &det : transformedDets) {
        classBasedMap[det.label].push_back(det);
    }

    for (auto &[label, objects] : classBasedMap) {
        auto merged = performClassNMerge(objects);
        fusedResults.insert(fusedResults.end(), merged.begin(), merged.end());
    }

    return fusedResults;
}

}  // namespace inference

}  // namespace ai

}  // namespace hce
