// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <string>
#include <filesystem>
#include <system_error>

inline bool check_folder_path(std::string &path)
{
    bool path_valid = false;
    if (path != "") {
        if (std::filesystem::exists(path)) {
            if (std::filesystem::is_directory(path))
                path_valid = true;
        } else {
            std::error_code ec;
            if (std::filesystem::create_directories(path, ec))
                path_valid = true;
        }
    }
    return path_valid;
}
