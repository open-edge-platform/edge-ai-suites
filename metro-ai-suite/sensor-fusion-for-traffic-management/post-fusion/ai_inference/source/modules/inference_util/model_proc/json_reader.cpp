/*******************************************************************************
 * Copyright (C) 2020-2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "modules/inference_util/model_proc/json_reader.h"

namespace hce{

namespace ai{

namespace inference{

void JsonReader::read(const std::string &file_path) {
    std::ifstream input_file(file_path);
    if (not input_file)
        throw std::runtime_error("Model-proc file '" + file_path + "' was not found");

    input_file >> m_contents;
    input_file.close();
}

const nlohmann::json &JsonReader::content() const {
    return m_contents;
}

bool JsonReader::check_item(const nlohmann::json& content, std::string key) {
    auto iter = content.find(key);
    if (iter == content.end()) {
        return false;
    }
    if (iter.value() == "") {
        return false;
    }
    return true; 
}

void JsonReader::check_required_item(const nlohmann::json& content, std::string key) {
    if (!check_item(content, key)) {
        throw std::invalid_argument(
            "Required property " + key + " not found in field!");
    }
}

// override
void JsonReader::check_required_item(const nlohmann::json& content,
                                      std::vector<std::string> key_list) {
    for (auto key : key_list) {
        if (!check_item(content, key)) {
            throw std::invalid_argument(
                "Required property " + key + " not found in field!");
        }
    }
}

}   // namespace inference

}   // namespace ai

}   // namespace hce