/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/
#ifndef HCE_AI_INF_FE_POST_IMPL_HPP
#define HCE_AI_INF_FE_POST_IMPL_HPP

#include <mkl.h>
#include <algorithm>
#include <cmath>
#include <inc/api/hvaLogger.hpp>

#include "common/base64.hpp"
#include "nodes/databaseMeta.hpp"
#include "modules/inference_util/model_proc/json_reader.h"


namespace hce{

namespace ai{

namespace inference{


/**
 * 
 * @brief feature extraction model processing parser
*/
class FeatureModelProcParser {
public:
    /**
     * 
     * @brief classification model post-processing params
    */
    struct ModelProcParams {

        std::string layer_name = "ANY";
        std::string converter = "";
        std::string method = "";
        nlohmann::json params;
        
        ModelProcParams() {};
        ~ModelProcParams() {};
    };

public:
    FeatureModelProcParser(const std::string& confPath) : m_conf_path(confPath) {};
    ~FeatureModelProcParser() {};

    /**
     * @brief read and parse model_proc file
     * @return boolean 
    */
    bool parse() {
        try {
            // read json file contents
            readJsonFile();

            // "post_proc_output"
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
    std::map<std::string, ModelProcParams> m_proc_params;

    JsonReader m_json_reader;
    
    /**
     * @brief read json content into m_json_reader, check reuqired fields
     *        and parse basic fields: json_schema_version, description
     * @return void
    */
    void readJsonFile() {

        HVA_DEBUG("Parsing model post proc json from file: %s", m_conf_path.c_str());
        m_json_reader.read(m_conf_path);
    };

    /**
     * @brief key: layer_name, val: output post processing info
     */
    void parseOutputPostproc () {
      
        const nlohmann::json &model_proc_content = m_json_reader.content();

        auto output_postproc = model_proc_content.at("post_proc_output");
        for (const auto &proc_item : output_postproc) {

            ModelProcParams _params;
            parsePostprocItems(proc_item, _params);

            if (!JsonReader::check_item(proc_item, "converter")) {
                HVA_WARNING("The field 'converter' is not set");
            }

            m_proc_params[_params.layer_name] = _params;
        }
    };

    /**
     * @brief parse `post_proc_output` field in model_proc file
     */
    void parsePostprocItems(const nlohmann::basic_json<> &proc_item, ModelProcParams &params) {
        /*
        {
            "layer_name": "ANY",
            "converter": "embedding",
            "method": "quantization",
            "params": {
                "quantization_scale": 411.317,
                "precision": "I8"
            }
        }
        */
        std::string layer_name("ANY");
        
        std::vector<std::string> labels;
        for (nlohmann::json::const_iterator it = proc_item.begin(); it != proc_item.end(); ++it) {
            std::string key = it.key();
            auto value = it.value();
            if (key == "layer_name") {
                value.get_to(params.layer_name);
                layer_name = params.layer_name;
            }
            else if (key == "converter") {
                value.get_to(params.converter);
            }
            else if (key == "method") {
                value.get_to(params.method);
            }
            else if (key == "params") {
                value.get_to(params.params);
            }
            else {
              throw std::invalid_argument("Unexpected property key: " + key + " found in model-proc file");
            }
        }
    };

};


class FeaturePostProcessor {
    
public:
    using Ptr = std::shared_ptr<FeaturePostProcessor>;

    FeaturePostProcessor() {};
    ~FeaturePostProcessor() {};

    void init(FeatureModelProcParser::ModelProcParams& model_proc_params) {
        m_model_proc_params = model_proc_params;
    };

    std::string process(float* blob_data, std::size_t data_length) {

        if (m_model_proc_params.converter == "embedding") {
            if (m_model_proc_params.method == "quantization") {

                // do int8 quantization
                JsonReader::check_required_item(m_model_proc_params.params, "quantization_scale");
                float scale = m_model_proc_params.params["quantization_scale"].get<float>();
                auto quantized = quantizeFp32ToInt8(blob_data, data_length, scale);

                // encode int8 feature vector using base64
                std::string encoded;
                base64EncodeBufferToString(encoded, &quantized[0], data_length);
                return encoded;
            }
            else if (m_model_proc_params.method == "identity") {
                
                // directly encode float32 feature vector using base64
                std::string encoded;
                base64EncodeBufferToString(encoded, blob_data, data_length);
                return encoded;
            } 
            else {
                throw std::runtime_error("unknown method for coverter(embedding) is specified: " + m_model_proc_params.method);
            }
        } else {
            throw std::runtime_error("unknown converter is specified: " + m_model_proc_params.converter);
        }

    }

private:
    FeatureModelProcParser::ModelProcParams m_model_proc_params;

    /**
     * @brief quantization feature embedding, from `fp32` to `int8`
    */
    std::vector<int8_t> quantizeFp32ToInt8(float* src, std::size_t size, float scale) const{

        // calculate the norm of a vector
        float norm = cblas_snrm2(size, src, 1);
        if (norm != 0) {
            cblas_sscal(size, scale / norm, src, 1); // update in place
        }
        else{
            return std::vector<int8_t>(size, 0);
        }

        // clip value, with [INT8_MIN, INT8_MAX]
        std::vector<int8_t> ret(size);
        for(std::size_t i = 0; i < size; ++i){
            if(src[i] < INT8_MIN)
                ret[i] = INT8_MIN;
            else if(src[i] > INT8_MAX)
                ret[i] = INT8_MAX;
            else
                ret[i] = round(src[i]);
        }
        return ret;
    };
};



}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_FE_POST_IMPL_HPP