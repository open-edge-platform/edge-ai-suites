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
#ifndef HCE_AI_INF_CLS_POST_IMPL_HPP
#define HCE_AI_INF_CLS_POST_IMPL_HPP

#include <algorithm>
#include <cmath>
#include <inc/api/hvaLogger.hpp>

#include "nodes/databaseMeta.hpp"
#include "modules/inference_util/model_proc/json_reader.h"
#include "modules/inference_util/classification/classification_label.hpp"


namespace hce{

namespace ai{

namespace inference{


/**
 * 
 * @brief classification model processing parser
*/
class ClassificationModelProcParser {
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
    ClassificationModelProcParser(const std::string& confPath) : m_conf_path(confPath) {};
    ~ClassificationModelProcParser() {};

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


class ClassificationPostProcessor {
    
public:
    using Ptr = std::shared_ptr<ClassificationPostProcessor>;

    ClassificationPostProcessor() {};
    ~ClassificationPostProcessor() {};

    void init(ClassificationModelProcParser::ModelProcParams& model_proc_params) {

        m_model_proc_params = model_proc_params;

        // get parameters
        m_labels = m_model_proc_params.labels;
        m_num_classes = m_labels.num_classes();
        m_activation = m_model_proc_params.activation;
        m_method = m_model_proc_params.method;
    };
    
    const std::string getConverterName() {
        return m_model_proc_params.converter;
    };
    
    const std::string getAttributeName() {
        return m_model_proc_params.attribute_name;
    };

    ClassificationLabel_t getLabels() {
        return m_labels;
    }

    ClassificationObject_t process(float* blob_data, size_t data_length) {

        if (data_length != m_num_classes) {
          throw std::runtime_error("invalid data length vs. num classes: " +
                                   std::to_string(data_length) + " vs. " +
                                   std::to_string(m_num_classes));
        }

        if (m_activation == "sigmoid") {
            this->_sigmoid(blob_data, m_num_classes);
        } else if (m_activation == "softmax") {
            this->_softmax(blob_data, m_num_classes);
        } else if (m_activation == "") {
            // do nothing
        } else {
            throw std::runtime_error("unknown activation function is specified: " + m_activation);
        }
        // this->_softmax(blob_data, m_num_classes);

        // get predicted results
        int pred_score_idx = -1;
        float pred_score;
        for (size_t classIdx = 0; classIdx < m_num_classes; ++classIdx) {
            float score = blob_data[classIdx];

            if (m_method == "max") {
            if (pred_score_idx < 0 || score > pred_score) {
                pred_score = score;
                pred_score_idx = classIdx;
            }
            } else if (m_method == "min") {
            if (pred_score_idx < 0 || score < pred_score) {
                pred_score = score;
                pred_score_idx = classIdx;
            }
            } else {
                throw std::runtime_error("unknown method is specified: " + m_method);
            }
        }

        ClassificationObject_t object(pred_score_idx, pred_score);

        return object;
    }

private:
    ClassificationModelProcParser::ModelProcParams m_model_proc_params;
    size_t m_num_classes;
    std::string m_method;
    std::string m_activation;
    ClassificationLabel_t m_labels;

    static void _softmax(float *x, int cnt)
    {
        const float t0 = -100.0f;
        float max = x[0], min = x[0];
        for (int i = 1; i < cnt; i++)
        {
            if (min > x[i])
                min = x[i];
            if (max < x[i])
                max = x[i];
        }

        for (int i = 0; i < cnt; i++)
        {
            x[i] -= max;
        }

        if (min < t0)
        {
            for (int i = 0; i < cnt; i++)
                x[i] = x[i] / min * t0;
        }

        // normalize as probabilities
        float expsum = 0;
        for (int i = 0; i < cnt; i++)
        {
            x[i] = exp(x[i]);
            expsum += x[i];
        }
        for (int i = 0; i < cnt; i++)
        {
            x[i] = x[i] / expsum;
        }
    }
    
    static void _sigmoid(float *x, int cnt) {
        for (int i = 0; i < cnt; i++) {
            x[i] = 1 / (1 + std::exp(-x[i]));
        }
    }
};



}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_CLS_POST_IMPL_HPP