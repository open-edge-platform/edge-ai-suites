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

#ifndef HCE_AI_INF_DETECTION_MODEL_PROC_PARSER_HPP
#define HCE_AI_INF_DETECTION_MODEL_PROC_PARSER_HPP

#include <inc/api/hvaLogger.hpp>

#include "modules/inference_util/model_proc/json_reader.h"
#include "modules/inference_util/detection/detection_helper.hpp"
#include "modules/inference_util/detection/detection_label.hpp"
#include "modules/inference_util/detection/detection_post_processor.hpp"

namespace hce{

namespace ai{

namespace inference{


// ============================================================================
//                      Detection Model Output Formatter
// ============================================================================
class DetectionOutputFormatter {
    public:
        using Ptr = std::shared_ptr<DetectionOutputFormatter>;

        DetectionOutputFormatter();
        ~DetectionOutputFormatter();

        /**
         * @brief init output formmater with json items
         * Can be scalable with optional field
         */
        void init(const nlohmann::json& format_items);

        /**
         * @brief set value to registered keys
         * @param key registered key
         * @param val runtime value
         */
        void setVal(std::string key, const std::vector<float>& val);

        /**
         * @brief reset each ptree det result
        */
        void resetOutput();

        /**
         * @brief get ptree output
        */
        boost::property_tree::ptree getOutput() {
            return m_output;
        }

        /**
         * @brief register output key from model_proc config file
        */
        std::unordered_map<std::string, std::string> getRegisterKeys() {
            return m_register_key;
        }

    private:
        std::unordered_map<std::string, std::string> m_register_key;
        boost::property_tree::ptree m_output;
};


// ============================================================================
//                      Detection Model Processing Parser
// ============================================================================
class DetectionModelProcParser {

public:
    struct _output_mapping_t {
        std::vector<int> index;     // input: {}
        std::vector<ModelOutputOperator::Ptr> ops;
    };

    struct _post_proc_output_t {

        // post process define
        std::string function_name;
        DetectionOutputFormatter::Ptr output_formatter;

        /**
         * [post-process factory]
         * @brief a list of processors
         * 
         * model_proc.json example:
         * "process": [
         *      {
         *          "name": "bbox_transform",
         *          "params": {...}
         *      },
         *      {
         *          "name": "NMS",
         *          "params": {...}
         *      },
         *      ...
         * ]
         */
        std::vector<ModelPostProcessor::Ptr> processor_factory;

        /**
         * [mapping-op factory]
         * @brief get post_proc final outputs
         *  key: mapped_key_name; val: mapping_descirptions
         * 
         * model_proc.json example:
         * "mapping": {
         *      "bbox": {
         *          ...
         *          "op": [{...}]
         *      },
         *      "label_id": {
         *          ...
         *          "op": [{...}]
         *      },
         *      ...
         * }
         */
        std::unordered_map<std::string, _output_mapping_t> mapping_factory;

        _post_proc_output_t() = default;
    };
    /**
     * 
     * @brief detection model post-processing params
    */
    class ModelProcParams {
    public:
        using Ptr = std::shared_ptr<ModelProcParams>;

        // "model_output"
        DetectionModelOutput_t model_output;

        // "post_proc_output"
        _post_proc_output_t pp_output;

        ModelProcParams() {};
        ~ModelProcParams() {};
    };

public:
    DetectionModelProcParser(std::string& confPath);
    ~DetectionModelProcParser();
    
    /**
     * @brief read and parse model_proc file
     * @return boolean 
    */
    bool parse();

    /**
     * @brief get m_proc_params
    */
    ModelProcParams getModelProcParams() {
        return m_proc_params;
    }

    /**
     * @brief get m_model_type
    */
    std::string getModelType() {
        return m_model_type;
    }

private:
    std::string m_conf_path;
    std::string m_json_schema_version;
    std::string m_model_type;
    ModelProcParams m_proc_params;

    JsonReader m_json_reader;
    
    // "labels_table"
    std::unordered_map<std::string, DetectionLabel::Ptr> m_labels_table;

    /**
     * @brief read json content into m_json_reader, check reuqired fields
     *        and parse basic fields: json_schema_version, model_type
     * @return void
    */
    void readJsonFile();

    /**
     * @brief parse `model_output` field in model_proc file
     */
    void parseModelOutput();

    /**
     * @brief parse `post_proc_output` field in model_proc file
     */
    void parsePostprocOutput();

    /**
     * @brief parse `labels_table` field in model_proc file
    */
    void parseLabelsTable();

    /**
     * @brief parse model proc item: "post_proc_output"
     */
    void parsePPOutputItems(const nlohmann::basic_json<> &proc_items, _post_proc_output_t &params);

    /**
     * @brief parse processor list from field: "post_proc_output.process"
     */
    void parseProcessorList(
        const nlohmann::basic_json<>& proc_items,
        std::vector<ModelPostProcessor::Ptr>& processor_factory);

    /**
     * @brief parse mapping items from field: "post_proc_output.mapping"
    */
    void parseMappingItems(
        const nlohmann::basic_json<>& mapping_items,
        const DetectionOutputFormatter::Ptr& output_formatter,
        std::unordered_map<std::string, _output_mapping_t>& mapping_factory);
};


}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_DETECTION_MODEL_PROC_PARSER_HPP