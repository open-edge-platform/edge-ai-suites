/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include "low_latency_server/pipelineManager.hpp"

namespace hce{

namespace ai{

namespace inference{

PipelineManager::PipelineManager(): m_state(Stopped), m_handleCtr(HANDLE_START_INDEX), m_currentWorkloadWeight(0),
        m_pipelinePool(PIPELINE_POOL_INIT_COUNT, 0), m_maxConcurrentWorkload(0u), m_maxPipelineLifetime(30u) {
    hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
    hvaLogger.enableProfiling();
    hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

    m_watchdogVal = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
}

PipelineManager::~PipelineManager(){

}

uint64_t PipelineManager::healthCheck() const{
    return m_watchdogVal.load(std::memory_order_acquire);
}

/**
 * @brief initialize pipeline_manager with MaxConcurrentWorkload
 * @param MaxConcurrentWorkload
*/
hceAiStatus_t PipelineManager::init(unsigned maxConcurrentWorkload, unsigned maxPipelineLifetime, unsigned logSeverity){
    HCE_AI_ASSERT(m_state == Stopped);

    // 
    // set hvaLogger level
    // logLvl here is set to be compatible with spdlog
    // 
    static hva::hvaLogger_t::LogLevel logLvl[6] = {hva::hvaLogger_t::LogLevel::DEBUG, hva::hvaLogger_t::LogLevel::DEBUG, hva::hvaLogger_t::LogLevel::INFO,
            hva::hvaLogger_t::LogLevel::WARNING, hva::hvaLogger_t::LogLevel::ERROR, hva::hvaLogger_t::LogLevel::ERROR}; 

    if (logSeverity > 5) {
        logSeverity = 0;
        std::cout << "Unknown log severity received, change to: hva::hvaLogger_t::LogLevel::DEBUG !" << std::endl;
    }
    hvaLogger.setLogLevel(logLvl[logSeverity]);

    m_maxConcurrentWorkload = maxConcurrentWorkload;
    _INF("MaxConcurrentWorkload sets to {}", m_maxConcurrentWorkload);
    m_maxPipelineLifetime = maxPipelineLifetime;
    _INF("MaxPipelineLifeTime sets to {}s", m_maxPipelineLifetime);
    return hceAiSuccess;
}

void PipelineManager::uvWorkload(){

    uv_loop_init(&m_uvLoop);
    uv_timer_init(&m_uvLoop, &m_timer);
    m_timer.data = reinterpret_cast<void*>(this);
    uv_timer_start(&m_timer, _HCE_AI_PIPE_MA_CALLBACK_WRAPPER_NAME(onTimeUp), 5000, 5000);

    uv_run(&m_uvLoop, UV_RUN_DEFAULT);
}

/**
 * @brief  stop and destroy pipeline who exceeds max lifetime (m_maxPipelineLifetime), and release the resources
 * pipeline's heartbeat wiil be used
*/
void PipelineManager::onTimeUp(uv_timer_t* handle){
    if(Stopped == m_state){
        uv_timer_stop(handle);
        uv_stop(&m_uvLoop);
    }
    else{
        watch();
    }
}

/**
 * @brief to generate jobHandle for each constructed pipeline
*/
PipelineManager::Handle PipelineManager::fetchIncrementHandleIndex(){

    Handle handle = m_handleCtr++;
    while(handle < HANDLE_START_INDEX){
        handle += HANDLE_START_INDEX;
    }

    Handle prevVal = m_handleCtr;
    Handle expected = prevVal;
    while(expected < HANDLE_START_INDEX){
        expected += HANDLE_START_INDEX;
    }
    while(!m_handleCtr.compare_exchange_weak(prevVal, expected)){
        expected = prevVal;
        while(expected < HANDLE_START_INDEX){
            expected += HANDLE_START_INDEX;
        }
    }
    return handle;
}

/**
 * @brief acquire resources for constructing pipeline
 * if reources (existing workload <m_mMaxConcurrentWorkload) enough, return true
*/
bool PipelineManager::acquireResourceByWorkloadWeight(unsigned weightToAcquire){

    int prevVal = m_currentWorkloadWeight.fetch_add(weightToAcquire);
    int newVal = prevVal + weightToAcquire;
    if(newVal > m_maxConcurrentWorkload){
        int restoreVal = m_currentWorkloadWeight;
        while(!m_currentWorkloadWeight.compare_exchange_weak(restoreVal, restoreVal-weightToAcquire, std::memory_order_relaxed)){
            restoreVal = m_currentWorkloadWeight;
        }
        return false;
    }
    else{
        _DBG("Acquired workload resource by {}. Now {}", weightToAcquire, m_currentWorkloadWeight);
        return true;
    }
}

/**
 * @brief release resources after pipeline destroyed
*/
void PipelineManager::releaseResourceByWorkloadWeight(unsigned weightToRelease){
    m_currentWorkloadWeight.fetch_sub(weightToRelease);
    HVA_ASSERT(m_currentWorkloadWeight >= 0);
    m_waitingQueueCv.notify_all(); // notify cv so that those blocked by few of resource can try again
    _DBG("Released workload resource by {}. Now {}", weightToRelease, m_currentWorkloadWeight);
}

}

}

}
