// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "FastMappingNode.h"

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    std::shared_ptr<FastMappingNode> fm = std::make_shared<FastMappingNode>();
    int returnCode = 0; // Variable to store the return code
    try {
        fm->init();
        if (!rclcpp::ok()) {
            std::cerr << "FastMapping node failed to start or was stopped by user..." << std::endl;
            returnCode = -1;
        }
        else {
            fm->start();
            rclcpp::spin(fm);
            fm->stop();
        }
    }
    catch(const std::exception& e) {
        std::cerr << e.what() << '\n';
        returnCode = -1;
    }
    rclcpp::shutdown();
    return returnCode;
}
