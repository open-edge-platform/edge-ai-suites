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

#ifndef HCE_AI_INF_MODULE_QUALITY_HPP
#define HCE_AI_INF_MODULE_QUALITY_HPP

#include <random>
#include <inc/api/hvaPipeline.hpp>

#include <opencv2/opencv.hpp>

namespace hce{

namespace ai{

namespace inference{


/// @brief describe object quality assessment results
struct QualityObject_t {
    float blur = 0.f;                   /** blur score | the higher, the better quality */
    float qa_model = 0.f;               /** quality assess model output score | the higher, the better quality */
    float quality_summary = 0.f;        /** quality ensemble */
};

class QualityPredictor {

    public:
        using Ptr = std::shared_ptr<QualityPredictor>;

        /// @brief object quality selection mode
        enum QualityModeType_e : unsigned{
            QUALITY_MODE_RANDOM = 0,                                        /**  Default quality mode: random */
            QUALITY_MODE_BLUR = (1 << 0),                                   /**  only use blur score */
            QUALITY_MODE_QAMODEL = (1 << 1),                                /**  use quality assess model output score */
        };

        QualityPredictor() {};

        ~QualityPredictor() {};

        /**
         * @brief init QualityPredictor, for mode: QUALITY_MODE_RANDOM || QUALITY_MODE_BLUR
         * @param mode quality mode
         * @param image_size dst resize for laplacian
         * @return sucess status
         */
        hva::hvaStatus_t init(unsigned mode, const int image_size = 320);

        /**
        * @brief make infer request pool
        * @return sucess status
        */
        hva::hvaStatus_t prepare();
        
        /**
        * @brief predict quality score for input image
        * @param image OpenCV Mat
        * @return quality score
        */
        float predict(const cv::Mat& image);
        
        /**
        * @brief get quality mode
        * @return sucess status
        */
        unsigned getMode() {
            return m_mode;
        };

    private:
        unsigned m_mode;
        int m_image_size;

        float m_durationAve {0.0f};

        std::atomic<int32_t> m_cntAsyncEnd{0};
        std::atomic<int32_t> m_cntAsyncStart{0};

        /**
         * @brief calculate laplacian variace
         * @param image OpenCV Mat
         * @return laplacian variance
         */
        float laplacianVariance(const cv::Mat& image);
};


}

}

}

#endif //#ifndef HCE_AI_INF_MODULE_QUALITY_HPP