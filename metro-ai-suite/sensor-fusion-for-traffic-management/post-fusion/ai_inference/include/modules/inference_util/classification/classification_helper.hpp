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
#ifndef HCE_AI_INF_CLASSIFICATION_HELPER_HPP
#define HCE_AI_INF_CLASSIFICATION_HELPER_HPP

#include <algorithm>
#include <cmath>
#include <inc/api/hvaLogger.hpp>

#include "classification_label.hpp"
#include "modules/inference_util/model_proc/json_reader.h"
#include "modules/inference_util/model_proc/input_model_preproc.h"

namespace hce{

namespace ai{

namespace inference{

/**
 * 
 * @brief classification model processing parser
*/
class ClsModelProcParser {
public:
    /**
     * 
     * @brief classification model post-processing params
    */
    struct ModelProcParams {

        std::string layer_name = "ANY";
        std::string attribute_name = "classification";
        ClassificationLabel_t labels;

        std::string converter = "";
        std::string activation = "";
        std::string method = "";
        
        ModelProcParams() {};
        ~ModelProcParams() {};
    };

public:
    ClsModelProcParser(const std::string& confPath) : m_conf_path(confPath) {};
    ~ClsModelProcParser() {};

    /**
     * @brief read and parse model_proc file
     * @return boolean 
    */
    bool parse() {
        try {
            // read json file contents
            readJsonFile();

            // "shared_postproc" or "output_postproc"
            parseOutputPostproc();
        }
        catch (std::exception &e) {
            HVA_ERROR("Parsing model_proc json content failed, error: %s!", e.what());
            return false;
        }
        catch (...) {
            HVA_ERROR("Parsing model_proc json content failed!");
            return false;
        }
        
        return true;
    }
    
    /**
     * @brief get m_proc_params
    */
    std::map<std::string, ModelProcParams> getModelProcParams() {
        return m_proc_params;
    }

private:
    std::string m_conf_path;
    std::string m_json_schema_version;
    std::string m_description;
    std::map<std::string, ModelProcParams> m_proc_params;

    JsonReader m_json_reader;
    
    /**
     * @brief read json content into m_json_reader, check reuqired fields
     *        and parse basic fields: json_schema_version, description
     * @return void
    */
    void readJsonFile() {

        HVA_DEBUG("Parsing model_proc json from file: %s", m_conf_path.c_str());
        m_json_reader.read(m_conf_path);

        const nlohmann::json &model_proc_content = m_json_reader.content();
        std::vector<std::string> required_fields = {"json_schema_version", "description"};
        JsonReader::check_required_item(model_proc_content, required_fields);

        // json_schema_version
        m_json_schema_version = model_proc_content["json_schema_version"].get<std::string>();

        // description
        m_description = model_proc_content["description"].get<std::string>();
    };

    std::vector<ModelInputProcessorInfo::Ptr> parseInputPreproc () {
        std::vector<ModelInputProcessorInfo::Ptr> _pre_procs;
        throw std::invalid_argument("NotImplemented Error!");
        
        return _pre_procs;
    };

    /**
     * @brief key: layer_name, val: output post processing info
     */
    void parseOutputPostproc () {
      
        const nlohmann::json &model_proc_content = m_json_reader.content();

        // check if "converter" is specified in config file
        bool flag = false;

        ModelProcParams _shared_params;
        if (JsonReader::check_item(model_proc_content, "shared_postproc")) {

            auto shared_postproc = model_proc_content.at("shared_postproc");
            parsePostprocItems(shared_postproc, _shared_params);

            flag = JsonReader::check_item(shared_postproc, "converter");
        }

        auto output_postproc = model_proc_content.at("output_postproc");
        for (const auto &proc_item : output_postproc) {

            // Inherit from shared params and override
            ModelProcParams _params = _shared_params;
            parsePostprocItems(proc_item, _params);

            flag = flag ? flag : JsonReader::check_item(proc_item, "converter");
            if (!flag) {
                HVA_WARNING("The field 'converter' is not set");
            }

            m_proc_params[_params.layer_name] = _params;
        }
    };

    /**
     * @brief parse `shared_postproc` or `output_postproc` field in model_proc file
     */
    void parsePostprocItems(const nlohmann::basic_json<> &proc_item, ModelProcParams &params) {
        /*
        {
            "converter": "label",
            "method": "max"
            "layer_name": "color",
            "attribute_name": "color",
            "labels": [
                "white",
                "gray",
                "yellow",
                "red",
                "green",
                "blue",
                "black"
            ]
        }
        */
        std::string layer_name("ANY");
        
        std::vector<std::string> labels;
        for (nlohmann::json::const_iterator it = proc_item.begin(); it != proc_item.end(); ++it) {
            std::string key = it.key();
            auto value = it.value();
            if (key == "attribute_name") {
                value.get_to(params.attribute_name);
            }
            else if (key == "layer_name") {
                value.get_to(params.layer_name);
                layer_name = params.layer_name;
            }
            else if (key == "converter") {
                value.get_to(params.converter);
            }
            else if (key == "activation") {
                value.get_to(params.activation);
            }
            else if (key == "method") {
                value.get_to(params.method);
            }
            else if (key == "labels") {
                value.get_to(labels);
            }
            else {
              throw std::invalid_argument("Unexpected property key: " + key + " found in model-proc file");
            }
        }
        if (labels.size() > 0) {
            params.labels.init(params.attribute_name, labels);
        }
    };

};

}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_CLASSIFICATION_HELPER_HPP
/*
Example:
vehicle-attributes-recognition-barrier-0039.model_proc.json
{
    "json_schema_version": "1.0.0",
    "description": "vehicle_attribute",
    "shared_postproc": {
      "converter": "label",
      "method": "max"
    },
    "output_postproc": [
        {
          "layer_name": "color",
          "attribute_name": "color",
          "labels": [
            "white",
            "gray",
            "yellow",
            "red",
            "green",
            "blue",
            "black"
          ]
        },
        {
          "layer_name": "type",
          "attribute_name": "type",
          "labels": [
            "car",
            "bus",
            "truck",
            "van"
          ]
        }
    ]
}

*/