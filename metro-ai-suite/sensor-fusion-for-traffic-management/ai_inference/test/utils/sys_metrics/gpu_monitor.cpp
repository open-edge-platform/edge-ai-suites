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

void runIntelGpuTop(const std::string &command, int interval)
{
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
                /*
                some version  may have more than one [unknown] engine, like:
                "[unknown]/1": {
                        "busy": 0.000000,
                        "sema": 0.000000,
                        "wait": 0.000000,
                        "unit": "%"
                },
                "[unknown]/2": {
                        "busy": 0.000000,
                        "sema": 0.000000,
                        "wait": 0.000000,
                        "unit": "%"
                },
                "[unknown]/3": {
                        "busy": 0.000000,
                        "sema": 0.000000,
                        "wait": 0.000000,
                        "unit": "%"
                }
                */
                newBusyValue = pt.get<float>("engines.[unknown]/0.busy");
                int cnt = 1;
                if (pt.get_optional<float>("engines.[unknown]/1.busy")) {
                    newBusyValue += pt.get<float>("engines.[unknown]/1.busy");
                    ++cnt;
                }
                if (pt.get_optional<float>("engines.[unknown]/2.busy")) {
                    newBusyValue += pt.get<float>("engines.[unknown]/2.busy");
                    ++cnt;
                }
                if (pt.get_optional<float>("engines.[unknown]/3.busy")) {
                    newBusyValue += pt.get<float>("engines.[unknown]/3.busy");
                    ++cnt;
                }
                newBusyValue /= cnt;  // average value
            }
            else {
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
        }
        catch (const boost::property_tree::json_parser_error &e) {
            std::cerr << "JSON parsing error: " << e.what() << std::endl;
            gpuBusyValue.store(-1.0);
        }

        std::this_thread::sleep_for(std::chrono::seconds(interval));
    }
}


void runXpuSmi(const std::string &command, int interval)
{
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

        try {
            std::istringstream jsonStream(result);
            boost::property_tree::ptree pt;
            boost::property_tree::read_json(jsonStream, pt);

            /*
            {
                "device_id": 0,
                "device_level": [
                    {
                        "metrics_type": "XPUM_STATS_POWER",
                        "value": 44.69
                    },
                    {
                        "metrics_type": "XPUM_STATS_GPU_FREQUENCY",
                        "value": 1550
                    },
                    {
                        "metrics_type": "XPUM_STATS_GPU_CORE_TEMPERATURE",
                        "value": 53.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_USED",
                        "value": 229.1875
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_UTILIZATION",
                        "value": 1.87
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_BANDWIDTH",
                        "value": 0
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_READ_THROUGHPUT",
                        "value": 0
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_WRITE_THROUGHPUT",
                        "value": 0
                    },
                    {
                        "metrics_type": "XPUM_STATS_GPU_UTILIZATION",
                        "value": 0.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_ENGINE_GROUP_COMPUTE_ALL_UTILIZATION",
                        "value": 0.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_ENGINE_GROUP_MEDIA_ALL_UTILIZATION",
                        "value": 0.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_ENGINE_GROUP_COPY_ALL_UTILIZATION",
                        "value": 0.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_ENGINE_GROUP_RENDER_ALL_UTILIZATION",
                        "value": 0.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEMORY_TEMPERATURE",
                        "value": 58.0
                    },
                    {
                        "metrics_type": "XPUM_STATS_MEDIA_ENGINE_FREQUENCY",
                        "value": 1200
                    }
                ],
                "engine_util": {
                    "3d": [],
                    "compute": [
                        {
                            "engine_id": 0,
                            "value": 0.0
                        }
                    ],
                    "copy": [
                        {
                            "engine_id": 0,
                            "value": 0.0
                        }
                    ],
                    "decoder": [
                        {
                            "engine_id": 0,
                            "value": 0.0
                        },
                        {
                            "engine_id": 1,
                            "value": 0.0
                        }
                    ],
                    "encoder": [
                        {
                            "engine_id": 0,
                            "value": 0.0
                        },
                        {
                            "engine_id": 1,
                            "value": 0.0
                        }
                    ],
                    "media_enhancement": [
                        {
                            "engine_id": 1,
                            "value": 0.0
                        },
                        {
                            "engine_id": 0,
                            "value": 0.0
                        }
                    ],
                    "render": [
                        {
                            "engine_id": 0,
                            "value": 0.0
                        }
                    ]
                }
            }
            */
            float newBusyValue = 0.0;
            auto computeArray = pt.get_child("engine_util.compute");
            for (const auto &item : computeArray) {
                newBusyValue = newBusyValue > item.second.get<float>("value", 0.0f) ? newBusyValue : item.second.get<float>("value", 0.0f);
            }

            std::lock_guard<std::mutex> lock(gpu_utilization_mtx);
            gpuBusyValue.store(newBusyValue);
        }
        catch (const boost::property_tree::json_parser_error &e) {
            std::cerr << "JSON parsing error: " << e.what() << std::endl;
            gpuBusyValue.store(-1.0);
        }

        std::this_thread::sleep_for(std::chrono::seconds(interval));
    }
}
