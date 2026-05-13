/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include "modules/quality.hpp"

namespace hce{

namespace ai{

namespace inference{

/**
 * @brief init QualityPredictor
 * @param mode quality mode
 * @param image_size dst resize for laplacian
 * @return sucess status
 */
hva::hvaStatus_t QualityPredictor::init(unsigned mode, const int image_size)
{
    m_mode = mode;
    m_image_size = image_size;
    return hva::hvaSuccess;
}

/**
* @brief make infer request pool
* @return sucess status
*/
hva::hvaStatus_t QualityPredictor::prepare() {
    return hva::hvaSuccess;
}


/**
* @brief predict quality score for input image
* @param image OpenCV Mat
* @return quality score
*/
float QualityPredictor::predict(const cv::Mat& image) {

    if (m_mode == QualityModeType_e::QUALITY_MODE_RANDOM) {
        HVA_DEBUG("Quality assess on image with w: %d, h:%d, mode: random", image.size().width, image.size().height);
        return 1.0 * rand() / RAND_MAX;
    }
    else if (m_mode == QualityModeType_e::QUALITY_MODE_BLUR) {
        HVA_DEBUG("Quality assess on image with w: %d, h:%d, mode: blur", image.size().width, image.size().height);
        float quality_score = laplacianVariance(image);
        return quality_score;
    }
    else {
        HVA_ERROR("Unsupported quality mode: %u", (QualityModeType_e)m_mode);
        HVA_ASSERT(false);
    }
}


/**
 * @brief calculate laplacian variace
 * @param image OpenCV Mat
 * @return laplacian variance
 */
float QualityPredictor::laplacianVariance(const cv::Mat& image) {

    // resize
    cv::Mat resized_image(image);
    if (m_image_size != image.size().width || m_image_size != image.size().height) {
        cv::resize(image, resized_image, cv::Size(m_image_size, m_image_size));
    }

    // convert gray
    cv::Mat gray_image;
    cv::cvtColor(resized_image, gray_image, cv::COLOR_BGR2GRAY);

    // laplacian transform
    cv::Mat lap_image;
    cv::Laplacian(gray_image, lap_image, CV_32F);

    // const unsigned char *dst_ptr = lap_image.data;
    cv::Scalar mean, stddev; // 0:1st channel, 1:2nd channel and 2:3rd channel
    cv::meanStdDev(lap_image, mean, stddev, cv::Mat());
    float variance = stddev.val[0] * stddev.val[0];

    return variance;
}

}

}

}
