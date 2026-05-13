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

#include <fstream>
#include <nlohmann/json.hpp>
#include <string>

namespace hce{

namespace ai{

namespace inference{


class JsonReader {
  private:
    nlohmann::json m_contents;

  public:
    void read(const std::string &file_path);
    const nlohmann::json &content() const;

    static bool check_item(const nlohmann::json& content, std::string key);
    static void check_required_item(const nlohmann::json& content, std::string key);
    static void check_required_item(const nlohmann::json& content, std::vector<std::string> key_list);
};

}   // namespace inference

}   // namespace ai

}   // namespace hce
