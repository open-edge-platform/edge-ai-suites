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

#include <iostream>
#include <cstdio>
#include <array>
#include <sstream>
#include <boost/property_tree/ptree.hpp>
#include <boost/property_tree/json_parser.hpp>
#include "gpu_monitor.h"

std::atomic<float> gpuBusyValue(0.0);
std::mutex gpu_utilization_mtx;

void runIntelGpuTop(const std::string& command, int interval) {
    while (true) {
        std::array<char, 128> buffer;
        std::string result;
        std::shared_ptr<FILE> pipe(popen(command.c_str(), "r"), pclose);
        if (!pipe) {
            std::cerr << "popen() failed!" << std::endl;
            gpuBusyValue.store(-1.0);
        }
        while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
            result += buffer.data();
        }

        if ('[' == result[0]) {
            // in ubnuntu24, result may have an extra '[' at the beginning, causing the following JSON parsing error
            result.erase(0, 1);
        }

        try {
            std::istringstream jsonStream(result);
            boost::property_tree::ptree pt;
            boost::property_tree::read_json(jsonStream, pt);

            float newBusyValue = 0.0;
            if (pt.get_optional<float>("engines.[unknown]/0.busy")) {
                // in ubuntu22 system with lower version of intel_gpu_top 
                /*
                "engines": {
                    "Render/3D/0": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Blitter/0": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Video/0": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Video/1": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "VideoEnhance/0": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "[unknown]/0": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    }
                }
                */
                newBusyValue = pt.get<float>("engines.[unknown]/0.busy");
            } else {
                // in ubnuntu24 system with higher version of intel_gpu_top:
                /*
                "engines": {
                    "Render/3D": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Blitter": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Video": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "VideoEnhance": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    },
                    "Compute": {
                            "busy": 0.000000,
                            "sema": 0.000000,
                            "wait": 0.000000,
                            "unit": "%"
                    }
                },
                */
                newBusyValue = pt.get<float>("engines.Compute.busy");
            }

            std::lock_guard<std::mutex> lock(gpu_utilization_mtx);
            gpuBusyValue.store(newBusyValue);
        } catch (const boost::property_tree::json_parser_error& e) {
            std::cerr << "JSON parsing error: " << e.what() << std::endl;
            gpuBusyValue.store(-1.0);
        }

        std::this_thread::sleep_for(std::chrono::seconds(interval));
    }
}
