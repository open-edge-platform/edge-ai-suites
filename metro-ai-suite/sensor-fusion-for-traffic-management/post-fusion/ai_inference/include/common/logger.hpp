/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_LL_LOGGER_HPP
#define HCE_AI_INF_LL_LOGGER_HPP

#include "common/common.hpp"

#include <spdlog/spdlog.h>
#include <spdlog/sinks/sink.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_sinks.h>

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC Logger{
public:
    static spdlog::logger& getInstance();

    ~Logger();

    static void init(const std::string& logDir, unsigned maxFileCount, unsigned maxFileSize, unsigned severity);

private:
    Logger();

    std::shared_ptr<spdlog::logger> m_logger;
    static std::string logDir_;
    static unsigned maxFileCount_;
    static unsigned maxFileSize_;
    static spdlog::level::level_enum severity_;
};

#define _TRC(...) Logger::getInstance().trace(__VA_ARGS__)
#define _DBG(...) Logger::getInstance().debug(__VA_ARGS__)
#define _INF(...) Logger::getInstance().info(__VA_ARGS__)
#define _WRN(...) Logger::getInstance().warn(__VA_ARGS__)
#define _ERR(...) Logger::getInstance().error(__VA_ARGS__)
#define _CRI(...) Logger::getInstance().critical(__VA_ARGS__)

}

}

}

#endif //#ifndef HCE_AI_INF_LL_LOGGER_HPP
