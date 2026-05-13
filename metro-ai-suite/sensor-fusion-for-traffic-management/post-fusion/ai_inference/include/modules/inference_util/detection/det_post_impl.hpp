/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_DET_POST_IMPL_HPP
#define HCE_AI_INF_DET_POST_IMPL_HPP

#include <cmath>
#include <vector>
#include <algorithm>
#include <boost/exception/all.hpp>

#include <inc/api/hvaLogger.hpp>

#include "inference_backend/image_inference.h"
#include "detection_helper.hpp"
#include "modules/inference_util/detection/detection_model_proc_parser.hpp"


namespace hce{

namespace ai{

namespace inference{


class DetectionPostProcessor {
    
public:
    using Ptr = std::shared_ptr<DetectionPostProcessor>;

    DetectionPostProcessor() {}
    ~DetectionPostProcessor() {}

    void init(DetectionModelProcParser::ModelProcParams& model_proc_params,
              const std::vector<std::string>& filterLabels,
              float confThresh = 0.01f, int maxROI = 0) {

        m_model_proc_params = model_proc_params;
        m_model_proc_params.model_output.conf_thresh = confThresh;
        m_model_proc_params.model_output.max_roi = maxROI;

        // set target labels
        m_filterLabels = filterLabels;
    }

    /**
     * @brief model labels
    */
    DetectionLabel::Ptr getLabels() {
        return m_model_proc_params.model_output.labels;
    }

    /**
     * @brief get confidence threshold
    */
    float getConfThreshold() {
        return m_model_proc_params.model_output.conf_thresh;
    }

    /**
     * @brief get max roi num
    */
    int getMaxROI() {
        return m_model_proc_params.model_output.max_roi;
    }

    /**
     * @brief post-proc function name
     *  > HVA_det_postproc: in-scope, can directly call postproc()
     *  > {custom_func_name}: load specified function from library
    */
    std::string getPPFunctioName()
    {
        return m_model_proc_params.pp_output.function_name;
    }

    DetectionModelProcParser::ModelProcParams getModelProcParams()
    {
        return m_model_proc_params;
    }

    /**
    * @brief determine whether the input label needs to be retained
    * @param label input label
    * @return boolean: should be keep
    */
    bool isFilterLabel(const std::string& label) {
        if (m_filterLabels.size() == 0) {
            return true;
        }
        for (auto item : m_filterLabels) {
            if (label == item) {
                return true;
            }
        }
        return false;
    }

    /**
     * @brief post-process function: HVA_det_postproc
     * @param blob_data <layer_name, inference_blob_data>
     * @param blob_length <layer_name, blob_length>
     * @return std::string, results with json format
     */
    std::string postproc(std::map<std::string, float*> blob_data,
                         std::map<std::string, size_t> blob_length,
                         size_t target_batch_id = 0) {

        // in-scope post processing function
        // for sanity, to check the existence of model_output.format.detection_output in model_proc json file
        if (!m_model_proc_params.model_output.detection_output.enabled) {
            throw std::runtime_error(
                "The field: model_output.format.detection_output should be "
                "specified in"
                "model_proc json file, but found nothing!");
        }

        // return with json string format
        std::string json_results;
        
        // 
        // fetch output buffer, and do post-processors defined in model_proc.json file
        // 
        std::vector<float*> processed_outputs;
        for (auto &blob_iter : blob_data) {
            
            std::vector<float*> blob_processed_outputs;

            // fetch blob data from output layer
            std::string layer_name = blob_iter.first;
            float *buffer = (float*)blob_iter.second;
            size_t buffer_length = blob_length[layer_name];

            // 
            // Step 1. get inputs for all processors, std::vector<std::vector<float>> should be assembled
            // Fetch data, and do some early filter objects with low confidence
            // 
            switch (m_model_proc_params.model_output.layout) {
                case DetOutputDimsLayout_t::B:
                    // simple outputs with bbox predictions
                    // no anchor transform will be needed
                    get_inputs(buffer, buffer_length, blob_processed_outputs, target_batch_id);
                    break;
                case DetOutputDimsLayout_t::BCxCy:
                case DetOutputDimsLayout_t::CxCyB:
                    get_inputs_with_anchors(buffer, buffer_length, blob_processed_outputs);
                    break;
                default:
                    throw std::runtime_error("Unknown layout!");

            }
            if (blob_processed_outputs.size() == 0) {
                // all being filtered out
                continue;
            }

            // 
            // Step 2. run layer-wise processors, data will be changed in-place
            // 
            for (auto& processor :
                 m_model_proc_params.pp_output.processor_factory) {
                if ("ANY" == processor->applyToLayer() ||
                    layer_name == processor->applyToLayer()) {
                    processor->process(blob_processed_outputs);
                }
            }
            processed_outputs.insert(processed_outputs.end(),
                                     blob_processed_outputs.begin(),
                                     blob_processed_outputs.end());
        }

        //// all layer-wise processors have being called

        if (processed_outputs.size() == 0) {
            // none objects being detected
            return json_results;
        }

        // TODO: check validation of the apply_to_layer field
        
        // 
        // Step 3. run all-in-one processors (i.e, layer-wise = false), data will be changed in-place
        //
        for (auto& processor :
             m_model_proc_params.pp_output.processor_factory) {
            if ("ALL" == processor->applyToLayer()) {
                processor->process(processed_outputs);
            }
        }

        // 
        // Step4. mapping the post-processed outputs to the formats defined in model_proc.json file
        //
        json_results = call_mapping(
            processed_outputs, m_model_proc_params.pp_output.output_formatter);

        return json_results;

    }

    /**
     * @brief format json results to std::vector<DetectedObject_t>
     */
    static bool parseHVADetFormatResult(std::string json_results, std::vector<DetectedObject_t>& objects) {

        // 
        // Parse results with json format
        // 
        if(json_results.empty()) {
            // no objects detected
            return true;
        }
        else {
            std::stringstream ss(json_results);
            try {
                boost::property_tree::ptree res_ptree;
                boost::property_tree::read_json(ss, res_ptree);

                // 
                // Convert formatted data to std::vector<DetectedObject_t>
                // 
                const auto& format_ptree = res_ptree.get_child("format");
                for (auto iter = format_ptree.begin(); iter != format_ptree.end(); iter ++) {
                    
                    DetectedObject_t object;
                    
                    const auto& obj_tree = iter->second;
                    for (auto iter_obj = obj_tree.begin(); iter_obj != obj_tree.end(); iter_obj ++) {
                        if (iter_obj->first == "bbox") {

                            std::vector<float> location(4);
                            
                            auto iter_bbox = iter_obj->second.begin();
                            for (unsigned i = 0; i < location.size(); ++i) {
                                location[i] = iter_bbox->second.get_value<float>();
                                ++ iter_bbox;
                            }
                            object.x = location[0];
                            object.y = location[1];
                            object.w = location[2];
                            object.h = location[3];
                        }
                        else if (iter_obj->first == "label_id") {
                            object.class_id = iter_obj->second.get_value<int>();
                        }
                        else if (iter_obj->first == "confidence") {
                            object.confidence = iter_obj->second.get_value<float>();
                        }
                        else {
                            // TODO: support scalable fields
                            HVA_WARNING("Unknown detection result key: %s, ignore!", iter_obj->first.c_str());
                        }
                    }

                    objects.push_back(object);
                }

                return true;
            }
            catch (const boost::property_tree::ptree_error& e){
                HVA_ERROR("Failed to read json results: %s", boost::diagnostic_information(e).c_str());
                return false;
            }
            catch (boost::exception& e){
                HVA_ERROR("Failed to read json results: %s", boost::diagnostic_information(e).c_str());
                return false;
            }
        }
    }

private:
    std::vector<std::string> m_filterLabels;
    DetectionModelProcParser::ModelProcParams m_model_proc_params;

    /**
     * @brief get processors' inputs
     * model_output layout must be DetOutputDimsLayout_t::B
     */
    void get_inputs(float* blob_data, size_t data_length, std::vector<float*>& detection_outputs, size_t target_batch_id = 0) {
        
        // for sanity
        HVA_ASSERT(m_model_proc_params.model_output.layout == DetOutputDimsLayout_t::B);

        size_t one_detection_output_size = m_model_proc_params.model_output.detection_output.size;
        std::size_t num_outputs = data_length / one_detection_output_size;
        
        int confidence_index = m_model_proc_params.model_output.detection_output.confidence_index;
        int first_class_prob_index =
            m_model_proc_params.model_output.detection_output.first_class_prob_index;
        int batchid_index =
            m_model_proc_params.model_output.detection_output.batchid_index;
            

        // TODO: not safety, if outputs did not do sigmoid?
        // early filter bboxes with low confidence
        // traverse each candidate roi and remove those boxes with smaller confidence score
        for (size_t bbox_idx = 0; bbox_idx < num_outputs; bbox_idx ++) {

            // get processors' input
            float* data = blob_data + bbox_idx * one_detection_output_size;

            // support openvino OP: DetectionOutput
            // https://docs.openvino.ai/2022.3/openvino_docs_ops_detection_DetectionOutput_1.html#doxid-openvino-docs-ops-detection-detection-output-1
            // The output tensor contains information about filtered detections described with 7 element tuples: [batch_id, class_id, confidence, x_1, y_1, x_2, y_2]. 
            // The first tuple with batch_id equal to -1 means end of output.
            if (batchid_index >= 0) {
                auto cur_batch_id = data[batchid_index];
                if (cur_batch_id == -1) {
                    break;
                }
                if (cur_batch_id != target_batch_id) {
                    continue;
                }
            }

            float confidence = 1.0;
            if (confidence_index >= 0) {
                confidence = data[confidence_index];
                if (confidence < m_model_proc_params.model_output.conf_thresh) {
                    continue;
                }
            }
            
            // obj class_prob exists
            if (first_class_prob_index >= 0) {
                int num_classes = m_model_proc_params.model_output.num_classes;
                std::vector<float> cls_confidence(
                    data + first_class_prob_index,
                    data + first_class_prob_index + num_classes);
                float max_cls_prob = *(std::max_element(cls_confidence.begin(), cls_confidence.end()));
                confidence = confidence * max_cls_prob;
                if (confidence < m_model_proc_params.model_output.conf_thresh) {
                    continue;
                }
            }

            detection_outputs.push_back(data);
        }

    }

    /**
     * @brief get processors' inputs
     * model_output layout must be DetOutputDimsLayout_t::BCxCy || DetOutputDimsLayout_t::CxCyB
     */
    void get_inputs_with_anchors(
        float* blob_data, size_t data_length,
        std::vector<float*>& detection_outputs) {
        
        // for sanity
        HVA_ASSERT(m_model_proc_params.model_output.layout ==
                       DetOutputDimsLayout_t::BCxCy ||
                   m_model_proc_params.model_output.layout ==
                       DetOutputDimsLayout_t::CxCyB);

        detection_outputs.push_back(blob_data);
    }

    /**
     * @brief call mapping and get formatted results
     * @return std::string std::stringstream(boost::property_tree::ptree)
     */
    std::string call_mapping(
        std::vector<float*>& detection_outputs,
        const DetectionOutputFormatter::Ptr& output_formatter) {

        boost::property_tree::ptree res_ptree;

        if (detection_outputs.size() == 0) {
            return "";
        }

        boost::property_tree::ptree all_rois;
        for (auto& output : detection_outputs) {

            // traverse all detection outputs, and format to pp output fields
            for (const auto &mapping_desc : m_model_proc_params.pp_output.mapping_factory) {

                // fetch input data for ops
                std::vector<int> index = mapping_desc.second.index;
                std::vector<float> vdata(index.size());
                for (size_t idx = 0; idx < index.size(); idx ++) {
                    vdata[idx] = output[index[idx]];
                }

                // call ops
                std::vector<ModelOutputOperator::Ptr> ops = mapping_desc.second.ops;
                for (const auto& op : ops) {
                    op->process(vdata);
                }

                // set val
                std::string key_name = mapping_desc.first;
                output_formatter->setVal(key_name, vdata);
            }
            
            boost::property_tree::ptree roi = output_formatter->getOutput();
            all_rois.push_back(std::make_pair("", roi));
            
            output_formatter->resetOutput();
        }

        res_ptree.add_child("format", all_rois);

        /**
         * Formatted output example:
         * {
                "format": [
                    {
                        "bbox": [
                            "0.445173234",
                            "0",
                            "0.121217772",
                            "0.0350752547"
                        ],
                        "confidence": "0.256397814",
                        "label_id": "4"
                    },
                    ...
                ]
            }
        */

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, res_ptree);

        return ss.str();
    }

};


}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_DET_POST_IMPL_HPP