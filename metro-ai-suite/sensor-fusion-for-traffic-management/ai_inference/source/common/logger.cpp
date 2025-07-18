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

#include "common/logger.hpp"

namespace hce{

namespace ai{

namespace inference{

// default values:
std::string Logger::logDir_ = "0";
unsigned Logger::maxFileCount_ = 8;
unsigned Logger::maxFileSize_ = 16777216;
spdlog::level::level_enum Logger::severity_ = spdlog::level::trace;

void Logger::init(const std::string& logDir, unsigned maxFileCount, unsigned maxFileSize, unsigned severity){
    static spdlog::level::level_enum logLvl[6] = {spdlog::level::trace, spdlog::level::debug, spdlog::level::info,
            spdlog::level::warn, spdlog::level::err, spdlog::level::critical}; 
    Logger::logDir_ = logDir;
    Logger::maxFileCount_ = maxFileCount;
    Logger::maxFileSize_ = maxFileSize;
    if (severity > 5) {
        severity = 0;
        std::cout << "Unknown log severity received, change to: spdlog::level::trace" << std::endl;
    }
    Logger::severity_ = logLvl[severity];
}

Logger::Logger(){
    char buf[1024];
    sprintf(buf, "%s/HceAIInferenceService", Logger::logDir_.c_str());
    spdlog::set_pattern("%Y-%m-%d %H:%M:%S.%e [%t] [%l] %v");
    
    spdlog::sinks_init_list sink_list = { std::make_shared<spdlog::sinks::rotating_file_sink_mt>(buf, Logger::maxFileSize_, Logger::maxFileCount_),
                    std::make_shared<spdlog::sinks::stdout_sink_mt>() };
    m_logger = std::make_shared<spdlog::logger>("DualSinks", sink_list.begin(), sink_list.end());
    // spdlog::set_level(spdlog::level::trace);
    m_logger->set_level(Logger::severity_);
}

Logger::~Logger(){

}

spdlog::logger& Logger::getInstance(){
    static Logger inst;
    return *inst.m_logger;
}

}

}

}