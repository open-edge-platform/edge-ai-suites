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

#ifndef HCE_AI_INF_DETECTION_POST_PROCESSOR_HPP
#define HCE_AI_INF_DETECTION_POST_PROCESSOR_HPP

#include <inc/api/hvaLogger.hpp>

#include "modules/inference_util/model_proc/json_reader.h"
#include "modules/inference_util/detection/detection_helper.hpp"

namespace hce{

namespace ai{

namespace inference{

// ============================================================================
//                          Model Post-Processor
// ============================================================================
class ModelPostProcessor {

public:
    using Ptr = std::shared_ptr<ModelPostProcessor>;
    
    ModelPostProcessor();
    ~ModelPostProcessor();
    
    virtual void process(std::vector<float*>& inputs) = 0;

    /**
     * create new post-processor instance
     * @param processor_name
     * @param params
     * @return processor instance
     */
    static ModelPostProcessor::Ptr CreateInstance(
        const DetectionModelOutput_t& model_output_cfg, std::string processor_name,
        const nlohmann::json& params);

    /**
     * @brief Processor name
     */
    virtual const std::string ProcessorName() const = 0;

    /**
     * @brief supported processors description
     */
    static std::string supportedProcessors() {
        std::vector<std::string> _supported = {"bbox_transform", "anchor_transform", "NMS"};
        std::string desc = "[";
        for (auto item : _supported) {
            desc += item + ", ";
        }
        desc += "]";
        return desc;
    };

    /**
     * @brief some processors are required to be called at layer-wise
     */
    std::string applyToLayer() {
        return m_apply_to_layer;
    };

protected:
    // all processors should be set as "ANY" by default
    std::string m_apply_to_layer = "ANY";

    /**
     * @brief clip val range [0, 1]
    */
    float clipNormalizedVal(float val);
};


class BBoxTransformProcessor final: public ModelPostProcessor {
public:

    /**
     * @brief parse required parameters for this Processor
     */
    BBoxTransformProcessor(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~BBoxTransformProcessor();

    /**
     * @brief process with specified Processor instance
     * @param input
     */
    virtual void process(std::vector<float*>& inputs);

    /**
     * @brief Processor name
     */
    virtual const std::string ProcessorName() const {
        return "bbox_transform";
    }

private:
    std::unordered_map<std::string, DetBBoxFormat_t> m_supported = {
        {"CENTER_SIZE", DetBBoxFormat_t::CENTER_SIZE},
        {"CORNER_SIZE", DetBBoxFormat_t::CORNER_SIZE},
        {"CORNER", DetBBoxFormat_t::CORNER}};

    DetectionModelOutput_t m_model_output_cfg;
    DetBBoxFormat_t m_target_type;
    float m_bbox_scale_h = 1.0f;
    float m_bbox_scale_w = 1.0f;
    bool m_clip_normalized_rect = false;

    /**
     * @brief check bbox format, convert to enum DetBBoxFormat_t {}
     */
    DetBBoxFormat_t checkBBoxFormat(std::string in_format);

    /**
     * @brief supported formats description
     */
    std::string supportedFormats();
};

/**
 * @brief Predict bounding boxes based on anchor boxes with predicted offsets 
 * 
 */
class AnchorTransformProcessor final : public ModelPostProcessor {
public:
    /**
     * @brief parse required parameters for this Processor
     */
    AnchorTransformProcessor(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~AnchorTransformProcessor();
    
    /**
     * @brief process with specified Processor instance
     * @param input
     */
    virtual void process(std::vector<float*>& inputs);

    /**
     * @brief Processor name
     */
    virtual const std::string ProcessorName() const { 
        return "anchor_transform"; 
    }

private:

    enum class TransfromFunction_t {
        UNKNOWN = -1,
        EXPONENTIAL,
        SQUARE
    };
    std::unordered_map<std::string, TransfromFunction_t> m_supportedFuncs = {
        {"exp", TransfromFunction_t::EXPONENTIAL},
        {"exponential", TransfromFunction_t::EXPONENTIAL},
        {"square", TransfromFunction_t::SQUARE}};

    struct bbox_prediction_t {

        struct pred_bbox_xy_t {
            float factor;
            float grid_offset;
            float scale_w;
            float scale_h;
        } pred_bbox_xy;

        struct pred_bbox_wh_t {
            float factor;
            TransfromFunction_t function;
            float scale_w;
            float scale_h;
        } pred_bbox_wh;
    };

    DetectionModelOutput_t m_model_output_cfg;
    bool m_output_sigmoid_activation = false;               // whether to do output activation
    std::pair<float, float> m_out_feature;                  // output feature size: (w, h)
    std::vector<std::pair<float, float>> m_anchors;         // prior anchors size: (w, h)
    bbox_prediction_t m_bbox_predition;                     // bbox prediction coefficients
    bool m_clip_normalized_rect = false;
    
    /**
     * @brief supported transform function
     */
    std::string supportedTransformFuncs();

    /**
     * @brief check transform function, convert to enum TransfromFunction_t {}
     */
    TransfromFunction_t checkFunctions(std::string func_name);
    
    /**
     * @brief get output index in blob data
     * @param index  index of detection output field, such as: [x, y, w, h, class_0, class_1, ...]
     *
    */
    size_t getIndex(size_t index, size_t anchor_index, size_t cell_index_x, size_t cell_index_y);

    /**
     * @brief sigmoid(x) if m_output_sigmoid_activation = true
    */
    float trySigmoid(float x);

    /**
     * @brief transform function apply on x according to the function type
    */
    float tryTransform(float x);

    // /**
    //  * @brief convert DetOutputDimsLayout_t::BCxCy to DetOutputDimsLayout_t::CxCyB
    // */
    // void tryConvertLayout(float* data) {
    //     float feature_w = m_out_feature.first;
    //     float feature_h = m_out_feature.second;
    //     size_t dets = m_anchors.size() * m_model_output_cfg.detection_output.size;
    //     // B*Cx*Cy
    //     size_t one_blob_size = dets * feature_w * feature_h;

    //     std::vector<float> vdata(data, data + one_blob_size);
    //     if (m_model_output_cfg.layout == DetOutputDimsLayout_t::BCxCy) {
            
    //         // BCxCy to CxCyB
    //         for (size_t d = 0; d < dets; d ++) {
    //             for (size_t cx = 0; cx < feature_w; cx ++) {
    //                 for (size_t cy = 0; cy < feature_h; cy ++) {
    //                     data[cx * feature_h * dets + cy * dets + d] = vdata[d * feature_w * feature_h + cx * feature_h + cy];
    //                 }
    //             }
    //         }
    //     }
    // };
};


class NMSProcessor final: public ModelPostProcessor {

public:
    /**
     * @brief parse required parameters for this Processor
     */
    NMSProcessor(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~NMSProcessor();
    
    /**
     * @brief process with specified Processor instance
     * @param input
     */
    virtual void process(std::vector<float*>& inputs);
    
    /**
     * @brief Processor name
     */
    virtual const std::string ProcessorName() const { 
        return "NMS";
    }

private:
    struct NMSRect {
        float x;                        // Left of bounding box
        float y;                        // Up of bounding box
        float w;                        // Width of bounding box
        float h;                        // Height of bounding box
        float confidence = 1.0;         // Detection confidence
        int origin_index;               // origin proposal index in model_output
    };

    /**
    * @brief Do Non Maximum Suppression on a set of proposals wirh pre-defined iou_threshold
    * @param candidates a set of detected objects
    * @return objects after NMS
    */
    void runNMS(std::vector<NMSRect>& objects);

    float m_iou_threshold;
    bool m_class_agnostic;
    DetectionModelOutput_t m_model_output_cfg;
};


// ============================================================================
//                          Model Output Operater
// ============================================================================
class ModelOutputOperator {
public:
    using Ptr = std::shared_ptr<ModelOutputOperator>;

    ModelOutputOperator();
    ~ModelOutputOperator();
    /**
     * @brief create new op instance
     * @param op_name operater name
     * @param params parameters, stored in nlohmann::json
     * @return op instance
     */
    static ModelOutputOperator::Ptr CreateInstance(
        const DetectionModelOutput_t& model_params, std::string op_name,
        const nlohmann::json& params);

    /**
     * @brief process with specified OP instance
     * @param input
     */
    // TODO
    // template <typename T1, typename T2>
    virtual void process(std::vector<float>& input) = 0;

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const = 0;

    template <typename T, typename A>
    static std::vector<int> argsort(std::vector<T, A> const& vec) {
        
        std::vector<int> sort_indices(vec.size());
        // fills the range [first, last) with sequentially increasing indices
        std::iota(sort_indices.begin(), sort_indices.end(), 0);
        std::sort(sort_indices.begin(), sort_indices.end(), [&](int i, int j) {
            return vec[i] > vec[j];
        });

        return sort_indices;
    }

    template <typename T, typename A>
    static int argmax(std::vector<T, A> const& vec) {
        return static_cast<int>(std::distance(vec.begin(), max_element(vec.begin(), vec.end())));
    }

    template <typename T, typename A>
    static int argmin(std::vector<T, A> const& vec) {
        return static_cast<int>(std::distance(vec.begin(), min_element(vec.begin(), vec.end())));
    }

    /**
     * @brief supported OP description
     */
    static std::string supportedOPs() {
        std::vector<std::string> _supported = {
            "identity", "sigmoid", "yolo_multiply", "argmax", "argmin",
            "max",      "min"};
        std::string desc = "[";
        for (auto item : _supported) {
            desc += item + ", ";
        }
        desc += "]";
        return desc;
    }
};

class IdentityOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    IdentityOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~IdentityOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "identity";
    }

private:
    DetectionModelOutput_t m_model_output_cfg;

};

class SigmoidOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    SigmoidOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~SigmoidOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "sigmoid";
    }

private:
    DetectionModelOutput_t m_model_output_cfg;
};

class YoloMultiplyOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    YoloMultiplyOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~YoloMultiplyOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "yolo_multiply";
    }
    
private:
    DetectionModelOutput_t m_model_output_cfg;
};

class ArgmaxOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    ArgmaxOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~ArgmaxOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "argmax";
    }
    
private:
    DetectionModelOutput_t m_model_output_cfg;
};

class ArgminOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    ArgminOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~ArgminOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "argmin";
    }
    
private:
    DetectionModelOutput_t m_model_output_cfg;
};

class MaxOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    MaxOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~MaxOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "max";
    }
    
private:
    DetectionModelOutput_t m_model_output_cfg;
};

class MinOP final: public ModelOutputOperator {
public:

    /**
     * @brief parse required parameters for this OP
     */
    MinOP(const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params);

    ~MinOP();

    /**
     * @brief process with specified OP instance
     * @param input
     */
    virtual void process(std::vector<float>& input);

    /**
     * @brief OP name
     */
    virtual const std::string OPName() const {
        return "min";
    }
    
private:
    DetectionModelOutput_t m_model_output_cfg;
};


}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_DETECTION_POST_PROCESSOR_HPP