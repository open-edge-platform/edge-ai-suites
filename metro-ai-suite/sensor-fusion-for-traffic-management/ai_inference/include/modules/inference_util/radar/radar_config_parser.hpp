/*******************************************************************************
 * Copyright (C) 2020-2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

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
