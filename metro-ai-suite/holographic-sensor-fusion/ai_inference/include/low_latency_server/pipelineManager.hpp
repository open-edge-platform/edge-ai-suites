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

#ifndef HCE_AI_INF_LL_PIPELINE_MANAGER_HPP
#define HCE_AI_INF_LL_PIPELINE_MANAGER_HPP

#include <thread>
#include <mutex>
#include <map>
#include <atomic>
#include <cstdint>
#include <functional>
#include <algorithm>
#include <chrono>
#include <uv.h>
#include <vector>
#include <unordered_map>

#include <boost/pool/object_pool.hpp>
#include <boost/pool/pool_alloc.hpp>
#include <boost/property_tree/json_parser.hpp>

#include <inc/api/hvaPipeline.hpp>
#include <inc/api/hvaPipelineParser.hpp>
#include "common/logger.hpp"
#include "common/common.hpp"

#define HANDLE_START_INDEX 0x80000000
// #define MAX_PIPELINE_LIFETIME 30

#define PIPELINE_INFO_POOL_INIT_COUNT 32
#define PIPELINE_POOL_INIT_COUNT 24

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC PipelineManager{
public:
    using Handle = uint32_t;

    ~PipelineManager();

    PipelineManager();

    PipelineManager(const PipelineManager&) = delete;

    PipelineManager(PipelineManager&&) = delete;

    PipelineManager& operator=(const PipelineManager&) = delete;

    PipelineManager& operator=(PipelineManager&&) = delete;

    /**
    * @brief Perform initialization
    * 
    * @param void
    * @return hceAiSuccess upon success
    * 
    */
    hceAiStatus_t init(unsigned maxConcurrentWorkload, unsigned maxPipelineLifetime, unsigned severity = 0);

    /**
    * @brief start the pipeline manager
    * 
    * @param void
    * @return hceAiSuccess upon success
    * 
    */
    virtual hceAiStatus_t start(unsigned pipelineManagerPoolSize) = 0;

    /**
    * @brief Stop the processing routine
    * 
    * @param void
    * @return hceAiSuccess upon success
    * 
    */
    virtual hceAiStatus_t stop() = 0;

    uint64_t healthCheck() const;

protected:

    #define _HCE_AI_PIPE_MA_CALLBACK_WRAPPER_NAME(func) func##_wrapper

    #define _HCE_AI_PIPE_MA_CALLBACK_WRAPPER_DEF(func,signature,args...) \
        static void _HCE_AI_PIPE_MA_CALLBACK_WRAPPER_NAME(func)signature { \
            PipelineManager* thisPtr = reinterpret_cast<PipelineManager*>(handle->data); \
            thisPtr->func(args);\
        }

    enum State{
        Stopped = 0,
        Running
    };
    using hvaPipelinePtr = std::shared_ptr<::hva::hvaPipeline_t>;

    class PipelineInfoHolderBase_t{
    public:
        using Ptr = std::shared_ptr<PipelineInfoHolderBase_t>;
        using WeakPtr = std::weak_ptr<PipelineInfoHolderBase_t>;
        PipelineInfoHolderBase_t(){ };

        virtual ~PipelineInfoHolderBase_t(){ };

        unsigned suggestedWeight;
        unsigned streamNum;
        Handle jobHandle;
        hvaPipelinePtr pipeline;
        uint64_t heartbeat;  // using std::chrono::milliseconds
        std::string pipelineConfig;
    };

    class Task{
    public:
        using Ptr = std::shared_ptr<Task>;
        enum TaskType{
            TASK_LOAD,
            TASK_RUN,
            TASK_UNLOAD,
            TASK_AUTO_RUN
        };

        Task(){

        };

        virtual ~Task(){

        };

        TaskType taskType;
    };
    
    // std::thread m_thread;
    std::vector<std::thread> m_loopThreadPool;
    std::thread m_uvThread;
    State m_state;

    unsigned m_maxConcurrentWorkload;
    unsigned m_pipelineManagerPoolSize;
    unsigned m_maxPipelineLifetime;

    std::mutex m_waitingQueueMutex;
    std::condition_variable m_waitingQueueCv;

    boost::object_pool<hva::hvaPipeline_t> m_pipelinePool;
    std::list<Task::Ptr, boost::fast_pool_allocator<Task::Ptr>> m_waitingQueue;

    // std::unordered_map<Handle, PipelineInfoHolderBase_t::Ptr, std::hash<Handle>, std::equal_to<Handle>, 
    //         boost::fast_pool_allocator<std::pair<Handle, PipelineInfoHolderBase_t::Ptr>>> m_workList;
    std::mutex m_workListMutex;
    std::condition_variable m_workListCv;

    std::atomic<Handle> m_handleCtr;

    std::atomic<int> m_currentWorkloadWeight;

    std::atomic<uint64_t> m_watchdogVal;

    uv_loop_t m_uvLoop;
    uv_timer_t m_timer;

    void uvWorkload();

    /**
     * @brief  stop and destroy pipeline who exceeds max lifetime (m_maxPipelineLifetime), and release the resources
     * pipeline's heartbeat is used
    */
    void onTimeUp(uv_timer_t* handle);
    _HCE_AI_PIPE_MA_CALLBACK_WRAPPER_DEF(onTimeUp, (uv_timer_t* handle), handle);

    /**
     * @brief watch lifetime for m_workList
    */
    virtual void watch() = 0;

    /**
     * @brief to generate jobHandle for each constructed pipeline
    */
    Handle fetchIncrementHandleIndex();

    /**
     * @brief release resources after pipeline destroyed
    */
    void releaseResourceByWorkloadWeight(unsigned weightToAcquire);

    /**
     * @brief acquire resources for constructing pipeline
     * if reources (existing workload <m_mMaxConcurrentWorkload) enough, return true
    */
    bool acquireResourceByWorkloadWeight(unsigned weightToAcquire);

};


}

}

}

#endif //#ifndef HCE_AI_INF_LL_PIPELINE_MANAGER_HPP
