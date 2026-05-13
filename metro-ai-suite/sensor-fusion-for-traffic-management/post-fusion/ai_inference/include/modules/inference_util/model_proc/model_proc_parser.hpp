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

#pragma once

#include "json_reader.h"
#include "model_preproc.h"
using namespace hce::ai::inference;

class ModelProcParser {
  protected:
    void parseLayerNameAndFormat(ModelInputInfo::Ptr preprocessor, const nlohmann::json &proc_item) {
        preprocessor->layer_name = proc_item.value("layer_name", std::string("ANY"));
        preprocessor->format = proc_item.value("format", std::string("image"));
    }

  public:
    /**
     * @brief parse `model_input` field in model_proc file
     * @return void
    */
    std::vector<ModelInputInfo::Ptr> parseModelInput(const nlohmann::json &model_input_items) {
        /**
         * 
        "model_input": [
            {
                "layer_name": "ANY",
                "format": "image",
                "layout": "NCHW",
                "precision": "U8",
                "params": {
                    "resize": "no-aspect-ratio",
                    "color_space": "BGR"
                }
            }
        ],
        */
        std::vector<ModelInputInfo::Ptr> preproc_desc;
        preproc_desc.reserve(model_input_items.size());

        for (const auto &proc_item : model_input_items) {
            ModelInputInfo::Ptr preprocessor = ModelInputInfo::Ptr(new ModelInputInfo());
            parseLayerNameAndFormat(preprocessor, proc_item);

            std::vector<std::string> required_fields = {"layout"};
            JsonReader::check_required_item(proc_item, required_fields);

            preprocessor->layout = proc_item["layout"].get<std::string>();

            preprocessor->precision = (preprocessor->format == "image") ? "U8" : "FP32";
            if (proc_item.find("precision") != proc_item.cend())
                preprocessor->precision = proc_item.at("precision");

            // parse model_input.params
            preprocessor->params = proc_item.value("params", nlohmann::json());

            preproc_desc.push_back(preprocessor);
        }
        return preproc_desc;
    };
};
