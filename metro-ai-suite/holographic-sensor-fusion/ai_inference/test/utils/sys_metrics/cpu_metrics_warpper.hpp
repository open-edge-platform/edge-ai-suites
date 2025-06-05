/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef CPU_METRICS_WRAPPER_HPP
#define CPU_METRICS_WRAPPER_HPP

#include <iostream>
#include <iomanip>
#include <chrono>
#include <unistd.h>

#include "cpu-top.h"

namespace hce{

namespace ai{

namespace inference{

class CPUMetrics {
public:

    CPUMetrics() {};

    ~CPUMetrics() {};

    /**
     * @brief initialize device context
     */
    void init() {
        cpu_top_init(&m_cpu);
        cpu_top_update(&m_cpu, m_pid);
    };

    /**
     * @brief initialize device context with specific process name
     */
    void init(std::string process_name) {
        // get pid by progress name, e.g., "HceAILLInfServer"
        m_pid = find_pid(process_name.c_str());
        cpu_top_init(&m_cpu);
        cpu_top_update(&m_cpu, m_pid);
    };

    /**
     * @brief cpu utilization (%)
     * @return in percentage
     */
    int cpuUtilization() {
        int sts = cpu_top_update(&m_cpu, m_pid);
        if (sts != 0) {
            throw std::runtime_error("Error to update cpu top!");
        }
        return (int)m_cpu.busy * cpuThreads();
    };

    /**
     * @brief cpu total threads
     */
    int cpuThreads() {
        return (int)m_cpu.nr_cpu;
    };

     /**
      * @brief CPU model name
      * @return model name, e.g: 
      *             12th Gen Intel(R) Core(TM) i5-12500TE
      */
    std::string modelName() {
        char model_name[128];
        if (cpu_model_name(model_name) == 0) {
            m_model_name = std::string(model_name);
        }
        else {
            m_model_name = "unknown";
        }

        if (m_model_name.back() == '\n') {
            m_model_name.pop_back();
        }

        return m_model_name;
    }


    /**
     * @brief report cpu utilization description
     */
    std::string report() {

        char cpuStr[1024];
        sprintf(cpuStr, "[CPU] %s: %d%%", modelName().c_str(), cpuUtilization());
          
        return std::string(cpuStr);
    }

private:
    pid_t m_pid = -1;
    struct cpu_top m_cpu;
    std::string m_model_name;

};


}
}
}
#endif /* CPU_METRICS_WRAPPER_HPP */