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
#include "model_proc_parser.hpp"

#include <string>

class ModelProcProvider {
  private:
    JsonReader m_json_reader;
    nlohmann::json m_content;
    std::unique_ptr<ModelProcParser> m_model_proc_parser;

    void createParser(const std::string &schema_version, const std::string &model_type) {
      // TODO: model_type
      if (schema_version == "1.2.0") {
          m_model_proc_parser = std::make_unique<ModelProcParser>();
      } else {
          throw std::invalid_argument("Parser for " + schema_version + " version not found");
      }
    }

  public:
    void readJsonFile(const std::string &file_path) {
      HVA_DEBUG("Parsing model_proc json from file: %s", file_path.c_str());

      m_json_reader.read(file_path);
      m_content = m_json_reader.content();

      std::vector<std::string> required_fields = {
          "json_schema_version",  "model_type", "model_input",  "post_proc_output"};
      JsonReader::check_required_item(m_content, required_fields);

      // json_schema_version
      std::string json_schema_version = m_content["json_schema_version"].get<std::string>();

      // model_type
      std::string model_type = m_content["model_type"].get<std::string>();
      createParser(json_schema_version, model_type);
    }

    std::vector<ModelInputInfo::Ptr> parseInputPreproc() {
      auto model_input_items = m_content.at("model_input");
      return m_model_proc_parser->parseModelInput(model_input_items);
    }

    // std::map<std::string, GstStructure *> parseOutputPostproc() {
    //   auto post_proc_items = m_content.at("post_proc_output");
    //   return m_model_proc_parser->parseModelInput(post_proc_items);
    // };
};
