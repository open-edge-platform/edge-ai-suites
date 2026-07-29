/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_DETECTION_HELPER_HPP
#define HCE_AI_INF_DETECTION_HELPER_HPP

#include <boost/property_tree/json_parser.hpp>
#include <inc/api/hvaLogger.hpp>

#include "detection_label.hpp"
#include "modules/inference_util/model_proc/json_reader.h"

namespace hce{

namespace ai{

namespace inference{

/**
 * A struct to describe detected object
 */ 
struct DetectedObject_t {
    float x;                    // Left of bounding box
    float y;                    // Up of bounding box
    float w;                    // Width of bounding box
    float h;                    // Height of bounding box
    int class_id;               // Detection label id
    float confidence;           // Detection confidence

    DetectedObject_t() = default;
    DetectedObject_t(float x, float y, float w, float h, int class_id, float confidence, float h_scale = 1.f,
                    float w_scale = 1.f) {
        this->x = x * w_scale;  //w_scale is supposed to be scale of bounding box, not anchor scale
        this->y = y * h_scale;  //y_scale is supposed to be scale of bounding box, not anchor scale
        this->w = w * w_scale;
        this->h = h * h_scale;
        this->class_id = class_id;
        this->confidence = confidence;
    }

    bool operator<(const DetectedObject_t &other) const {
        return this->confidence < other.confidence;
    }

    bool operator>(const DetectedObject_t &other) const {
        return this->confidence > other.confidence;
    }
};

/**
 * @brief output dims layout definition
 *  > Cx: Output feature map cell_x
 *  > Cy: Output feature map cell_y
 *  > B: Predicted detection outputs, such as:
 *       [x, y, w, h, class_0, class_1, ...], e.g, 85 for coco
*/
enum class DetOutputDimsLayout_t { CxCyB, BCxCy, B };

enum class DetBBoxFormat_t{
    UNKNOWN = -1,
    CENTER_SIZE,
    CORNER_SIZE,
    CORNER
};

struct DetectionModelOutput_t {
    DetOutputDimsLayout_t layout;
    int num_classes;
    DetectionLabel::Ptr labels;
    float conf_thresh = 0.01f;
    int max_roi = 0;

    struct detection_output_t {
        bool enabled;
        int size;
        DetBBoxFormat_t bbox_format;
        std::vector<int> location_index;
        int confidence_index = -1;
        int first_class_prob_index = -1;
        int predict_label_index = -1;
        int batchid_index = -1;             // may be defined in openvino op: `DetectionOutput`
    } detection_output;

    DetectionModelOutput_t() = default;

};

}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_DETECTION_HELPER_HPP