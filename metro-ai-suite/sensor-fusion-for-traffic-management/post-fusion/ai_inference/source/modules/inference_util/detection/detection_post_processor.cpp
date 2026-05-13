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

#include "modules/inference_util/detection/detection_post_processor.hpp"


namespace hce{

namespace ai{

namespace inference{

// ============================================================================
//                          Model Post-Processor
// ============================================================================

ModelPostProcessor::ModelPostProcessor() {

}

ModelPostProcessor::~ModelPostProcessor() {

}

/**
 * create new post-processor instance
 * @param processor_name
 * @param params
 * @return processor instance
 */
ModelPostProcessor::Ptr ModelPostProcessor::CreateInstance(
    const DetectionModelOutput_t& model_output_cfg,
    std::string processor_name, const nlohmann::json& params) {

    ModelPostProcessor* processor = nullptr;
    if (processor_name == "bbox_transform") {
        processor = new BBoxTransformProcessor(model_output_cfg, params);
    }
    else if (processor_name == "anchor_transform") {
        processor = new AnchorTransformProcessor(model_output_cfg, params);
    }
    else if (processor_name == "NMS") {
        processor = new NMSProcessor(model_output_cfg, params);
    }
    else {
        throw std::invalid_argument(
            "Unknown model post processor is specified in model_proc: " +
            processor_name + "supported: " + supportedProcessors());
    }

    return ModelPostProcessor::Ptr(processor);
}

float ModelPostProcessor::clipNormalizedVal(float val) {
    if(val < 0.0f)
    {
        val = 0.0f;
    }
    if(val > 1.0f)
    {
        val = 1.0f;
    }
    return val;
}

/**
 * @brief parse required parameters for this Processor
 */
BBoxTransformProcessor::BBoxTransformProcessor(
    const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {

    // for sanity: check required field
    std::vector<std::string> required_fields = {"target_type"};
    JsonReader::check_required_item(params, required_fields);

    // target_type
    auto iter = params.find("target_type");
    m_target_type = checkBBoxFormat(iter.value());

    // optional: scale_h
    if (JsonReader::check_item(params, "scale_h")) {
        iter = params.find("scale_h");
        iter.value().get_to(m_bbox_scale_h);
    }

    // optional: scale_w
    if (JsonReader::check_item(params, "scale_w")) {
        iter = params.find("scale_w");
        iter.value().get_to(m_bbox_scale_w);
    }

    // optional: m_clip_normalized_rect
    if (JsonReader::check_item(params, "clip_normalized_rect")) {
        iter = params.find("clip_normalized_rect");
        iter.value().get_to(m_clip_normalized_rect);
    }

    // optional: apply_to_layer
    if (JsonReader::check_item(params, "apply_to_layer")) {
        iter = params.find("apply_to_layer");
        iter.value().get_to(m_apply_to_layer);
    }
}

BBoxTransformProcessor::~BBoxTransformProcessor() {

}


/**
 * @brief check bbox format, convert to enum DetBBoxFormat_t {}
 */
DetBBoxFormat_t BBoxTransformProcessor::checkBBoxFormat(std::string in_format) {
    for (auto& item : m_supported) {
        if (item.first == in_format) {
            return item.second;
        }
    }
    throw std::invalid_argument(
        "Unknown model output bbox_forma is specified in model_proc: " +
        in_format + "supported: " + supportedFormats());
}

/**
 * @brief supported formats description
 */
std::string BBoxTransformProcessor::supportedFormats() {
    std::string desc = "[";
    for (auto& item : m_supported) {
        desc += item.first + ", ";
    }
    desc += "]";
    return desc;
}

/**
 * @brief process with specified Processor instance
 * @param data
 */
void BBoxTransformProcessor::process(std::vector<float*>& inputs) {

    if(inputs.size() == 0) {
        return;
    }

    std::vector<int> location_index = m_model_output_cfg.detection_output.location_index;
    DetBBoxFormat_t in_format = m_model_output_cfg.detection_output.bbox_format;
    
    // traverse each detection_output
    for (auto& data : inputs) {
        /**
         * @brief bbox format transform, first convert all to CORNER_SIZE, then convert them to m_target_type
         */
        // Step1. scale all bboxes to 0~1
        data[location_index[0]] /= m_bbox_scale_w;
        data[location_index[1]] /= m_bbox_scale_h;
        data[location_index[2]] /= m_bbox_scale_w;
        data[location_index[3]] /= m_bbox_scale_h;

        // input format == target format, no need to do Step2 & Step3
        if (in_format == m_target_type) {
            HVA_DEBUG("Model output bbox format is same as target type: %d", m_target_type);
            continue;
        } 
        else {
            // Step2. convert all to CORNER_SIZE
            switch (in_format) {
                case DetBBoxFormat_t::CENTER_SIZE:
                    // x_center, y_center, w, h
                    data[location_index[0]] = (data[location_index[0]] - data[location_index[2]] / 2);   // to: x_min
                    data[location_index[1]] = (data[location_index[1]] - data[location_index[3]] / 2);   // to: y_min
                    break;
                case DetBBoxFormat_t::CORNER_SIZE:
                    // do nothing
                    break;
                case DetBBoxFormat_t::CORNER:
                    // x_min, y_min, x_max, y_max
                    data[location_index[2]] = data[location_index[2]] - data[location_index[0]];   // to: w
                    data[location_index[3]] = data[location_index[3]] - data[location_index[1]];   // to: h
                    break;
                default:
                    {
                        char log[512];
                        sprintf(log, "Unknown bbox format: DetBBoxFormat_t %d", (int)in_format);
                        throw std::invalid_argument(log);
                    }
                    break;
            }
            // 
            // Step3. convert CORNER_SIZE to m_target_type
            // NOW `data` format: x_min, y_min, w, h
            // 
            switch (m_target_type) {
                case DetBBoxFormat_t::CENTER_SIZE:
                    data[location_index[0]] = (data[location_index[0]] + data[location_index[2]] / 2);   // to: x_center
                    data[location_index[1]] = (data[location_index[1]] + data[location_index[3]] / 2);   // to: y_center
                    break;
                case DetBBoxFormat_t::CORNER_SIZE:
                    // do nothing
                    break;
                case DetBBoxFormat_t::CORNER:
                    data[location_index[2]] = data[location_index[0]] + data[location_index[2]];   // to: x_max
                    data[location_index[3]] = data[location_index[1]] + data[location_index[3]];   // to: y_max
                    break;
                default:
                    {
                        char log[512];
                        sprintf(log, "Unknown bbox format: DetBBoxFormat_t %d", (int)in_format);
                        throw std::invalid_argument(log);
                    }
                    break;
            }
    
        }

        // Step4. clip out-bounded bbox, set coordinates to value 0.0 ~ 1.0
        if (m_clip_normalized_rect) {
            for (size_t i = 0; i < location_index.size(); i ++)
                data[location_index[i]] = clipNormalizedVal(data[location_index[i]]);
        }
    }
}


/**
 * @brief parse required parameters for this Processor
 */
AnchorTransformProcessor::AnchorTransformProcessor(
    const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    
    // 
    // params
    // 
    std::vector<std::string> required_fields = {"anchors", "bbox_prediction"};
    JsonReader::check_required_item(params, required_fields);
    
    // optional: apply_to_layer
    if (JsonReader::check_item(params, "apply_to_layer")) {
        auto iter = params.find("apply_to_layer");
        iter.value().get_to(m_apply_to_layer);
    }

    // optional: params.output_sigmoid_activation
    if (JsonReader::check_item(params, "output_sigmoid_activation")) {
        m_output_sigmoid_activation = params["output_sigmoid_activation"].get<bool>();
    }

    // params.out_feature
    std::vector<float> out_feature = params["out_feature"].get<std::vector<float>>();
    if (out_feature.size() != 2) {
        throw std::invalid_argument(
            "Invalid out_feature size found in model_proc file, it should be "
            "2, but got: " +
            out_feature.size());
    }
    m_out_feature = std::make_pair(out_feature[0], out_feature[1]);

    // params.anchors:  [w1, h1, w2, h2, ...]
    std::vector<float> anchors = params["anchors"].get<std::vector<float>>();
    if (anchors.size() % 2 != 0) {
        throw std::invalid_argument(
            "Invalid anchors size found in model_proc file, it should be even, "
            "but got: " +
            anchors.size());
    }
    for (size_t i = 0; i < anchors.size() / 2; i ++) {
        m_anchors.push_back(std::make_pair(anchors[i * 2], anchors[i * 2 + 1]));
    }

    // optional: clip_normalized_rect
    if (JsonReader::check_item(params, "clip_normalized_rect")) {
        m_clip_normalized_rect = params["clip_normalized_rect"].get<bool>();
    }

    // 
    // params.bbox_prediction
    // 
    auto bbox_prediction_items = params.at("bbox_prediction");
    required_fields = {"pred_bbox_xy", "pred_bbox_wh"};
    JsonReader::check_required_item(bbox_prediction_items, required_fields);

    // 
    // params.bbox_prediction.pred_bbox_xy
    // 
    auto pred_bbox_xy_items = bbox_prediction_items.at("pred_bbox_xy");
    required_fields = {"factor", "grid_offset"};
    JsonReader::check_required_item(pred_bbox_xy_items, required_fields);

    // params.bbox_prediction.pred_bbox_xy.factor
    m_bbox_predition.pred_bbox_xy.factor = pred_bbox_xy_items["factor"].get<float>();

    // params.bbox_prediction.pred_bbox_xy.grid_offset
    m_bbox_predition.pred_bbox_xy.grid_offset = pred_bbox_xy_items["grid_offset"].get<float>();

    // optional: params.bbox_prediction.pred_bbox_xy.scale_w
    // default: pred_bbox_xy.scale_w should be equal to feature_w by default
    if (JsonReader::check_item(pred_bbox_xy_items, "scale_w")) {
        m_bbox_predition.pred_bbox_xy.scale_w = pred_bbox_xy_items["scale_w"].get<float>();
    }
    else {
        m_bbox_predition.pred_bbox_xy.scale_w = m_out_feature.first;
    }
    
    // optional: params.bbox_prediction.pred_bbox_xy.scale_h
    // default: pred_bbox_xy.scale_h should be equal to feature_h by default
    if (JsonReader::check_item(pred_bbox_xy_items, "scale_h")) {
        m_bbox_predition.pred_bbox_xy.scale_h = pred_bbox_xy_items["scale_h"].get<float>();
    }
    else {
        m_bbox_predition.pred_bbox_xy.scale_h = m_out_feature.second;
    }

    // 
    // params.bbox_prediction.pred_bbox_wh
    // 
    auto pred_bbox_wh_items = bbox_prediction_items.at("pred_bbox_wh");
    required_fields = {"factor", "transform", "scale_w", "scale_h"};
    JsonReader::check_required_item(pred_bbox_wh_items, required_fields);

    // params.bbox_prediction.pred_bbox_wh.factor
    m_bbox_predition.pred_bbox_wh.factor = pred_bbox_wh_items["factor"].get<float>();

    // params.bbox_prediction.pred_bbox_wh.transform
    std::string func_name = pred_bbox_wh_items["transform"].get<std::string>();
    m_bbox_predition.pred_bbox_wh.function = checkFunctions(func_name);

    // params.bbox_prediction.pred_bbox_wh.scale_w
    m_bbox_predition.pred_bbox_wh.scale_w = pred_bbox_wh_items["scale_w"].get<float>();

    // params.bbox_prediction.pred_bbox_wh.scale_h
    m_bbox_predition.pred_bbox_wh.scale_h = pred_bbox_wh_items["scale_h"].get<float>();
}

AnchorTransformProcessor::~AnchorTransformProcessor() {

}

/**
 * @brief process with specified Processor instance
 * @param input
 */
void AnchorTransformProcessor::process(std::vector<float*>& inputs) {

    if(inputs.size() == 0) {
        return;
    }
    std::vector<std::vector<float>> voutputs;
    std::vector<float*> outputs;
    
    std::vector<int> location_index = m_model_output_cfg.detection_output.location_index;
    int confidence_index = m_model_output_cfg.detection_output.confidence_index;
    int first_class_prob_index =
        m_model_output_cfg.detection_output.first_class_prob_index;
    
    // for sanity
    HVA_ASSERT(confidence_index >= 0 || first_class_prob_index >= 0);

    int num_classes = m_model_output_cfg.num_classes;
    int detection_output_size = m_model_output_cfg.detection_output.size;

    // for sanity
    if (m_model_output_cfg.detection_output.bbox_format != DetBBoxFormat_t::CENTER_SIZE) {
        throw std::invalid_argument(
            "AnchorTransform only support for detection_output.bbox_format with CENTER_SIZE!");
    }

    // parse data in  output layer to bounding boxes
    for (auto& data : inputs) {
        for (size_t anchor_index = 0; anchor_index < m_anchors.size(); ++anchor_index) {
            const float anchor_scale_w = m_anchors[anchor_index].first;
            const float anchor_scale_h = m_anchors[anchor_index].second;

            for (size_t cell_index_x = 0; cell_index_x < m_out_feature.first; ++cell_index_x) {
                for (size_t cell_index_y = 0; cell_index_y < m_out_feature.second; ++cell_index_y) {
                    
                    float confidence = 1.0;
                    if (confidence_index >= 0) {
                        confidence = trySigmoid(data[getIndex(confidence_index, anchor_index, cell_index_x, cell_index_y)]);
                        // early filter bboxes with low confidence
                        if (confidence < m_model_output_cfg.conf_thresh) {
                            continue;
                        }
                    }

                    // obj class_prob exists, update confidence witho bbox_conf * class_prob
                    if (first_class_prob_index >= 0) {
                        float max_cls_prob = data[getIndex(first_class_prob_index, anchor_index, cell_index_x, cell_index_y)];
                        for (size_t cls_idx = 1; cls_idx < num_classes; cls_idx ++) {
                            
                            const float bbox_class_prob = data[getIndex(first_class_prob_index + cls_idx, anchor_index, cell_index_x, cell_index_y)];
                            max_cls_prob = bbox_class_prob > max_cls_prob ? bbox_class_prob : max_cls_prob;
                        }
                        confidence = confidence * trySigmoid(max_cls_prob);
                        // early filter bboxes with low confidence
                        if (confidence < m_model_output_cfg.conf_thresh) {
                            continue;
                        }
                    }

                    // 
                    // @brief anchor transform for yolo series
                    // > (x, y) - coordinates of box center
                    // > (h, w) - height and width of box, apply exponential function and multiply them by 
                    //          the corresponding anchors to get the absolute height and width values 
                    // 
                    
                    // get raw data from output blob
                    float raw_x_center = trySigmoid(data[getIndex(location_index[0], anchor_index, cell_index_x, cell_index_y)]);
                    float raw_y_center = trySigmoid(data[getIndex(location_index[1], anchor_index, cell_index_x, cell_index_y)]);
                    float raw_w = trySigmoid(data[getIndex(location_index[2], anchor_index, cell_index_x, cell_index_y)]);
                    float raw_h = trySigmoid(data[getIndex(location_index[3], anchor_index, cell_index_x, cell_index_y)]);

                    // grid offset, i.e. y = factor * x + grid_offset
                    // in YoloV2/V3, factor = 1.0, grid_offset = 0
                    // in YoloV5, factor = 2.0, grid_offset = -0.5
                    auto pred_bbox_xy = m_bbox_predition.pred_bbox_xy;
                    const float bbox_x_center =
                        (cell_index_x + raw_x_center * pred_bbox_xy.factor +
                        pred_bbox_xy.grid_offset) /
                        pred_bbox_xy.scale_w;
                    const float bbox_y_center =
                        (cell_index_y + raw_y_center * pred_bbox_xy.factor +
                        pred_bbox_xy.grid_offset) /
                        pred_bbox_xy.scale_h;
                        
                    // in YoloV2/V3, factor = 1.0, transform function is exponential
                    // in YoloV5, factor = 2.0, transform function is square
                    auto pred_bbox_wh = m_bbox_predition.pred_bbox_wh;
                    const float bbox_w = (tryTransform(raw_w * pred_bbox_wh.factor) * anchor_scale_w) / pred_bbox_wh.scale_w;
                    const float bbox_h = (tryTransform(raw_h * pred_bbox_wh.factor) * anchor_scale_h) / pred_bbox_wh.scale_h;

                    // center to corner
                    const float bbox_x = bbox_x_center - bbox_w / 2;
                    const float bbox_y = bbox_y_center - bbox_h / 2;

                    // assemble pure detection_outputs
                    std::vector<float> vdata(detection_output_size);
                    for (size_t det_idx = 0; det_idx < detection_output_size; det_idx ++) {

                        // update bbox predictions
                        if (det_idx == location_index[0]) {
                            vdata[det_idx] = m_clip_normalized_rect ? clipNormalizedVal(bbox_x) : bbox_x;
                        }
                        else if (det_idx == location_index[1]) {
                            vdata[det_idx] = m_clip_normalized_rect ? clipNormalizedVal(bbox_y) : bbox_y;
                        }
                        else if (det_idx == location_index[2]) {
                            vdata[det_idx] = m_clip_normalized_rect ? clipNormalizedVal(bbox_w) : bbox_w;
                        }
                        else if (det_idx == location_index[3]) {
                            vdata[det_idx] = m_clip_normalized_rect ? clipNormalizedVal(bbox_h) : bbox_h;
                        }
                        else {
                            // sigmoid (if need) other fields in detection_outputs
                            vdata[det_idx] = trySigmoid(data[getIndex(det_idx, anchor_index, cell_index_x, cell_index_y)]);
                        }
                    }
                    voutputs.push_back(vdata);
                }
                int a = 0;
            }
        }

        // reuse the data pointer to save processed detection_outputs 
        for (size_t idx = 0; idx < voutputs.size(); idx ++) {
            
            size_t offset = idx * detection_output_size;
            memset(data + offset, 0, detection_output_size * sizeof(data[0]));
            memcpy(data + offset, voutputs[idx].data(), detection_output_size * sizeof(data[0]));

            outputs.push_back(data + offset);
        }
    }
    inputs = outputs;
}

/**
 * @brief supported transform function
 */
std::string AnchorTransformProcessor::supportedTransformFuncs() {
    std::string desc = "[";
    for (auto& item : m_supportedFuncs) {
        desc += item.first + ", ";
    }
    desc += "]";
    return desc;
}

/**
 * @brief check bbox format, convert to enum TransfromFunction_t {}
 */
AnchorTransformProcessor::TransfromFunction_t
AnchorTransformProcessor::checkFunctions(std::string func_name) {
    if (m_supportedFuncs.count(func_name) > 0) {
        return m_supportedFuncs[func_name];
    }

    throw std::invalid_argument(
        "Unknown bbox transform function is specified in model_proc: " +
        func_name + "supported: " + supportedTransformFuncs());
}


/**
 * @brief get output index in blob data
 * @param index  index of detection output field, such as: [x, y, w, h, class_0, class_1, ...]
 *
*/
size_t AnchorTransformProcessor::getIndex(size_t index, size_t anchor_index, size_t cell_index_x, size_t cell_index_y) {

    size_t feature_w = m_out_feature.first;
    size_t feature_h = m_out_feature.second;
    size_t feature_size = feature_w * feature_h;                        // e.g, 13*13
    size_t box_size = m_model_output_cfg.detection_output.size;         // e.g, len([x, y, w, h, class_0, class_1, ...]) = 85
    size_t num_anchors = m_anchors.size();                              // num anchors

    switch (m_model_output_cfg.layout) {
        case DetOutputDimsLayout_t::BCxCy:
            {
                // offset for each proposal
                size_t offset = anchor_index * box_size * feature_size + cell_index_y * feature_w + cell_index_x;
                return index * feature_size + offset;
            }
        case DetOutputDimsLayout_t::CxCyB:
            {
                // offset for each proposal
                size_t offset = (cell_index_y * feature_w + cell_index_x) * num_anchors * box_size + anchor_index * box_size;
                return offset + index;
            }
            default: {
                char log[512];
                sprintf(log,
                        "Invalid model_output layput: DetOutputDimsLayout_t %d "
                        "recieved for processor: %s",
                        (int)m_model_output_cfg.layout, ProcessorName().c_str());
                throw std::invalid_argument(log);
            } break;
    }
}

/**
     * @brief sigmoid(x) if m_output_sigmoid_activation = true
    */
float AnchorTransformProcessor::trySigmoid(float x) {
    if (m_output_sigmoid_activation)
        return 1 / (1 + std::exp(-x));
    else
        return x;
}

/**
 * @brief transform function apply on x according to the function type
*/
float AnchorTransformProcessor::tryTransform(float x) {
    switch (m_bbox_predition.pred_bbox_wh.function) {
        case TransfromFunction_t::EXPONENTIAL:
            return std::exp(x);
        case TransfromFunction_t::SQUARE:
            return std::pow(x, 2);
        default:
            throw std::invalid_argument(
                "Unknown bbox transform function is specified in model_proc, "
                "supported: " +
                supportedTransformFuncs());
    }
}

/**
 * @brief parse required parameters for this Processor
 */
NMSProcessor::NMSProcessor(
    const DetectionModelOutput_t& model_output_cfg, const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {

    // for sanity: check required field
    std::vector<std::string> required_fields = {"iou_threshold"};
    JsonReader::check_required_item(params, required_fields);

    // iou_threshold
    auto iter = params.find("iou_threshold");
    iter.value().get_to(m_iou_threshold);

    // class_agnostic
    if (JsonReader::check_item(params, "class_agnostic")) {
        iter = params.find("class_agnostic");
        iter.value().get_to(m_class_agnostic);
    }
    else {
        m_class_agnostic = false;
    }

    // optional: apply_to_layer
    if (JsonReader::check_item(params, "apply_to_layer")) {
        iter = params.find("apply_to_layer");
        iter.value().get_to(m_apply_to_layer);
    }

}

NMSProcessor::~NMSProcessor() {

}

/**
 * @brief process with specified Processor instance
 *  Step1. format inputs to std::vector<NMSRect>
 *  Step2. carry out NMS (depends on class_agnostic)
 * @param input
 */
void NMSProcessor::process(std::vector<float*>& inputs) {

    // no need to run NMS
    if(inputs.size() <= 1) {
        return;
    }

    // // TODO: check real input bbox_format
    // if (m_model_output_cfg.detection_output.bbox_format != DetBBoxFormat_t::CORNER_SIZE) {
    //     throw std::invalid_argument(
    //         "NMS do not support for bbox_format: CORNER_SIZE, please transform bboxes at previous!");
    // }

    std::vector<float*> outputs;
    
    std::vector<int> location_index = m_model_output_cfg.detection_output.location_index;
    int confidence_index = m_model_output_cfg.detection_output.confidence_index;
    int first_class_prob_index =
        m_model_output_cfg.detection_output.first_class_prob_index;

    // for sanity
    HVA_ASSERT(confidence_index >= 0 || first_class_prob_index >= 0);

    int num_classes = m_model_output_cfg.num_classes;

    if (m_class_agnostic) {
        // carry out class-agnostic NMS

        std::vector<NMSRect> objects;
        // traverse each detection_output
        for (size_t input_index = 0; input_index < inputs.size(); input_index ++) {

            auto data = inputs[input_index];

            NMSRect rect;
            rect.x = data[location_index[0]];
            rect.y = data[location_index[1]];
            rect.w = data[location_index[2]];
            rect.h = data[location_index[3]];
            rect.origin_index = input_index;

            if (confidence_index >= 0) {
                rect.confidence = data[confidence_index];
            }

            // obj class_prob exists, update confidence witho bbox_conf * class_prob
            if (first_class_prob_index >= 0) {
                std::vector<float> cls_confidence(
                    data + first_class_prob_index,
                    data + first_class_prob_index + num_classes);
                float max_cls_prob = *(std::max_element(cls_confidence.begin(), cls_confidence.end()));
                rect.confidence = rect.confidence * max_cls_prob;
            }

            objects.push_back(rect);
        }

        runNMS(objects);
        for (auto& obj : objects) {
            outputs.push_back(inputs[obj.origin_index]);
        }
        inputs = outputs;
    }
    else {

        // some model outputs with predicted label_id, but some are not.
        int predict_label_index =
            m_model_output_cfg.detection_output.predict_label_index;

        // 
        // splits inputs into groups according to predicted label
        //

        // key: label_id, val: objects before nms
        std::unordered_map<int, std::vector<NMSRect>> class_aware_objects;
        
        if (predict_label_index >= 0) {
            // predict_label exists in model_output

            std::vector<NMSRect> objects;
            for (size_t input_index = 0; input_index < inputs.size(); input_index ++) {

                auto data = inputs[input_index];

                NMSRect rect;
                rect.x = data[location_index[0]];
                rect.y = data[location_index[1]];
                rect.w = data[location_index[2]];
                rect.h = data[location_index[3]];
                rect.origin_index = input_index;

                if (confidence_index >= 0) {
                    rect.confidence = data[confidence_index];
                }
                else {
                    // use obj class_prob
                    rect.confidence = data[first_class_prob_index + predict_label_index];
                }

                int label_id = (int)data[predict_label_index];
                if (class_aware_objects.count(label_id) == 0) {
                  class_aware_objects.emplace(label_id, std::vector<NMSRect>());
                }
                class_aware_objects[label_id].push_back(rect);
            }
        } else if (first_class_prob_index >= 0) {
            // class-agnostic confidence score exists in model_output

            std::vector<NMSRect> objects;
            for (size_t input_index = 0; input_index < inputs.size(); input_index ++) {

                auto data = inputs[input_index];

                NMSRect rect;
                rect.x = data[location_index[0]];
                rect.y = data[location_index[1]];
                rect.w = data[location_index[2]];
                rect.h = data[location_index[3]];
                rect.origin_index = input_index;

                if (confidence_index >= 0) {
                    rect.confidence = data[confidence_index];
                }

                std::vector<float> cls_confidence(
                    data + first_class_prob_index,
                    data + first_class_prob_index + num_classes);
                int label_id = ModelOutputOperator::argmax(cls_confidence);
                float max_cls_prob = data[first_class_prob_index + label_id];
                rect.confidence = rect.confidence * max_cls_prob;

                // create category key
                if (class_aware_objects.count(label_id) == 0) {
                  class_aware_objects.emplace(label_id, std::vector<NMSRect>());
                }
                class_aware_objects[label_id].push_back(rect);
            }
        } else {
            // None class-aware information exists in model_output
            // NMS only can be processed with "class_agnostic" = false
            throw std::invalid_argument(
                "None class-aware information exists in model_output, NMS only "
                "can be processed with class_agnostic = false");
        }

        // carry out class-aware NMS
        for (auto& item : class_aware_objects) {
            auto objects = item.second;
            runNMS(objects);
            for (auto& obj : objects) {
                outputs.push_back(inputs[obj.origin_index]);
            }
        }
        inputs = outputs;
    }

}

/**
* @brief Do Non Maximum Suppression on a set of proposals wirh pre-defined iou_threshold
* @param candidates a set of detected objects
* @return objects after NMS
*/
void NMSProcessor::runNMS(std::vector<NMSRect>& candidates) {

    std::sort(candidates.begin(), candidates.end(), [&](const NMSRect a, const NMSRect b) {
        return a.confidence > b.confidence;
    });

    for (auto p_first_candidate = candidates.begin(); p_first_candidate != candidates.end(); ++p_first_candidate) {
        const auto &first_candidate = *p_first_candidate;
        double first_candidate_area = first_candidate.w * first_candidate.h;

        for (auto p_candidate = p_first_candidate + 1; p_candidate != candidates.end();) {

            const auto &candidate = *p_candidate;

            double inter_width = std::min(first_candidate.x + first_candidate.w, candidate.x + candidate.w) -
                                std::max(first_candidate.x, candidate.x);
            double inter_height = std::min(first_candidate.y + first_candidate.h, candidate.y + candidate.h) -
                                std::max(first_candidate.y, candidate.y);
            if (inter_width <= 0.0 || inter_height <= 0.0) {
                ++p_candidate;
                continue;
            }

            double inter_area = inter_width * inter_height;
            double candidate_area = candidate.w * candidate.h;

            double overlap = inter_area / (candidate_area + first_candidate_area - inter_area);
            if (overlap > m_iou_threshold)
                p_candidate = candidates.erase(p_candidate);
            else
                ++p_candidate;
        }
    }
}


// ============================================================================
//                          Model Output Operater
// ============================================================================

ModelOutputOperator::ModelOutputOperator() {

}

ModelOutputOperator::~ModelOutputOperator() {

}

/**
 * @brief create new op instance
 * @param op_name operater name
 * @param params parameters, stored in nlohmann::json
 * @return op instance
 */
ModelOutputOperator::Ptr ModelOutputOperator::CreateInstance(
    const DetectionModelOutput_t& model_output_cfg,
    std::string op_name, const nlohmann::json& params) {
    
    ModelOutputOperator *operater = nullptr;
    if (op_name == "identity") {
        operater = new IdentityOP(model_output_cfg, params);
    }
    else if (op_name == "sigmoid") {
        operater = new SigmoidOP(model_output_cfg, params);
    }
    else if (op_name == "yolo_multiply") {
        operater = new YoloMultiplyOP(model_output_cfg, params);
    }
    else if (op_name == "argmax") {
        operater = new ArgmaxOP(model_output_cfg, params);
    }
    else if (op_name == "argmin") {
        operater = new ArgminOP(model_output_cfg, params);
    }
    else if (op_name == "max") {
        operater = new MaxOP(model_output_cfg, params);
    }
    else if (op_name == "min") {
        operater = new MinOP(model_output_cfg, params);
    }
    else {
        throw std::invalid_argument(
            "Unknown model output operator is specified in model_proc: " +
            op_name + "supported: " + supportedOPs());
    }

    return ModelOutputOperator::Ptr(operater);
}

/**
 * @brief parse required parameters for this OP
 */
IdentityOP::IdentityOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

IdentityOP::~IdentityOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void IdentityOP::process(std::vector<float>& input) {
    
    // do nothing
    return;
}

/**
 * @brief parse required parameters for this OP
 */
SigmoidOP::SigmoidOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

SigmoidOP::~SigmoidOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void SigmoidOP::process(std::vector<float>& input) {
    // modify value in-place
    for (size_t idx = 0; idx < input.size(); idx ++) {
        input[idx] = 1 / (1 + std::exp(-input[idx]));
    }
}


/**
 * @brief parse required parameters for this OP
 */
YoloMultiplyOP::YoloMultiplyOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

YoloMultiplyOP::~YoloMultiplyOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void YoloMultiplyOP::process(std::vector<float>& input) {
    float bbox_confidence = input[0];
    std::vector<float> cls_confidence(input.begin() + 1, input.end());

    float max_cls_prob = *(std::max_element(cls_confidence.begin(), cls_confidence.end()));
    float predict_score = bbox_confidence * max_cls_prob;
    
    input.clear();
    input.push_back(predict_score);
}


/**
 * @brief parse required parameters for this OP
 */
ArgmaxOP::ArgmaxOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

ArgmaxOP::~ArgmaxOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void ArgmaxOP::process(std::vector<float>& input) {
    
    int idx = argmax(input);

    input.clear();
    input.push_back((float)idx);
}

/**
 * @brief parse required parameters for this OP
 */
ArgminOP::ArgminOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

ArgminOP::~ArgminOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void ArgminOP::process(std::vector<float>& input) {
    
    int idx = argmin(input);

    input.clear();
    input.push_back((float)idx);
}

/**
 * @brief parse required parameters for this OP
 */
MaxOP::MaxOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

MaxOP::~MaxOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void MaxOP::process(std::vector<float>& input) {
    
    float max_val = *(std::max_element(input.begin(), input.end()));

    input.clear();
    input.push_back(max_val);
}

/**
 * @brief parse required parameters for this OP
 */
MinOP::MinOP(const DetectionModelOutput_t& model_output_cfg,
                       const nlohmann::json& params)
    : m_model_output_cfg(model_output_cfg) {
    if (params.size() > 0) {
        HVA_WARNING("OP: %s will ignore all parameters!", OPName().c_str());
    }
}

MinOP::~MinOP() {

}

/**
 * @brief process with specified OP instance
 * @param input
 */
void MinOP::process(std::vector<float>& input) {
    
    float min_val = *(std::min_element(input.begin(), input.end()));

    input.clear();
    input.push_back(min_val);
}

}   // namespace inference

}   // namespace ai

}   // namespace hce