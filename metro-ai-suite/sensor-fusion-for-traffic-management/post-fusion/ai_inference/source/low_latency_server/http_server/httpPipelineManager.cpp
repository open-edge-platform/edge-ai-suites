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

#include "low_latency_server/http_server/httpPipelineManager.hpp"


namespace hce{

namespace ai{

namespace inference{

HttpPipelineManager::HttpPipelineManager(): PipelineManager(), m_plInfoPool(PIPELINE_INFO_POOL_INIT_COUNT, 0),
        m_rrlPool(PIPELINE_POOL_INIT_COUNT, 0), m_ltiPool(PIPELINE_POOL_INIT_COUNT, 0u), 
        m_utiPool(PIPELINE_POOL_INIT_COUNT, 0u), m_rtiPool(PIPELINE_POOL_INIT_COUNT, 0u), m_artiPool(PIPELINE_POOL_INIT_COUNT, 0u){

}

HttpPipelineManager::~HttpPipelineManager(){

}

HttpPipelineManager& HttpPipelineManager::getInstance(){
    static HttpPipelineManager instance; // Guaranteed to be destroyed, Instantiated on first use.
    return instance;
}

/**
 * @brief register uvWorkload and uvloop
*/
hceAiStatus_t HttpPipelineManager::start(unsigned pipelineManagerPoolSize){
    static std::once_flag flag;
    std::call_once(flag, [&](){
        HCE_AI_ASSERT(m_state == Stopped);

        m_state = Running;

        m_uvThread = std::thread(&HttpPipelineManager::uvWorkload, this);

        _INF("Pipeline Manager pool size sets to {}", pipelineManagerPoolSize);
        m_loopThreadPool.reserve(pipelineManagerPoolSize);
        for (size_t i = 0; i < pipelineManagerPoolSize; i ++) {
            std::thread t = std::thread(&HttpPipelineManager::loop, this);
            m_loopThreadPool.push_back(std::move(t));
        }
        // m_thread = std::thread(&HttpPipelineManager::loop, this);
        
    });
    return hceAiSuccess;
}


/**
 * @brief stop all pipeline in workList, then waiting for all thread job finished.
*/
hceAiStatus_t HttpPipelineManager::stop(){
    m_state = Stopped;
    m_waitingQueue.clear();
    for(auto& item: m_workList){
        item.second->pipeline->stop();
    }
    m_workList.clear();

    m_waitingQueueCv.notify_all(); // wakeup the thread
    // m_thread.join();
    for(auto& item: m_loopThreadPool){
        item.join();
    }
    m_uvThread.join();
    return hceAiSuccess;
}

/**
 * @brief watch lifetime for m_workList
*/
void HttpPipelineManager::watch(){

    // update watchdog value
    ++m_watchdogVal;

    // looping the queue, check lifetime and stop if lifetime exceeds
    // heartbeat use milliseconds to get more accurate value
    uint64_t heartbeatThresh = 1000 * (std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count() - m_maxPipelineLifetime);
    std::lock_guard<std::mutex> lg(m_workListMutex);
    auto iter = m_workList.begin();
    while(iter != m_workList.end()){
        if(iter->second->heartbeat <= heartbeatThresh){
            _TRC("Pipeline with handle {} exceeds max pipeline lifetime ({}s). stopping", iter->second->jobHandle, m_maxPipelineLifetime);
            iter->second->pipeline->stop();
            // to-do: if we need a wait here?
            releaseResourceByWorkloadWeight(iter->second->suggestedWeight);
            iter = m_workList.erase(iter);
            _TRC("Pipeline removed");
        }
        else{
            ++iter;
        }
    }
}

/**
 * @brief keep processing tasks in waitingQueue, until pipeline state been transisted to Stopped
*/
hceAiStatus_t HttpPipelineManager::loop(){
    std::unique_lock<std::mutex> lk(m_waitingQueueMutex, std::defer_lock);
    while(m_state != Stopped){
        lk.lock();
        if(m_waitingQueue.size() == 0){
            // no element in waiting queue
            m_waitingQueueCv.wait(lk, [&](){return m_waitingQueue.size() != 0 || m_state == Stopped;});
        }
        
        // loop through items in waiting queue to run the first that have enough resource
        for(auto iter = m_waitingQueue.begin(); iter != m_waitingQueue.end(); ){
            
            // current task
            auto curTask = *iter;

            /*
            There may be multiple threads for loop(),
            so we should erase this task temporally, so that other thread will not access it duplicatedly.
            */
            m_waitingQueue.erase(iter);

            /*
            We should unlock the conditional_varialble: m_waitingQueueMutex, because:
                - [1]. Creating new workload takes too long, so that it won't block the insertion of incoming tasks in onRead()
                        which also infect the response latency between client-server!!!
                - [2]. Other threads will not be blocked when reading task in m_waitingQueue.
            */
            lk.unlock();

            // mark the process_status, leave the iterator to the end where we should lock `m_waitingQueueMutex` again
            bool erase_flag = false;

            //
            // processing TASK_LOAD: construct a new pipeline using PipelineConfig
            //  > if resources is enough, construct pipeline immediately
            //  > else do nothing, and leave the task still in m_waitingQueue
            //
            if((curTask)->taskType == Task::TASK_LOAD){
                LoadTaskInfo::Ptr ptr = std::dynamic_pointer_cast<LoadTaskInfo>(curTask);
                _TRC("Pipeline manager starts to process on a load task with handle {}", ptr->jobHandle);

                // to-do: check release
                if(acquireResourceByWorkloadWeight(ptr->suggestedWeight)){
                    PipelineInfo::Ptr plInfo = PipelineInfo::Ptr(m_plInfoPool.construct(), [this](PipelineInfo* ptr){
                            m_plInfoPool.destroy(ptr);});
                    HCE_AI_ASSERT(plInfo);
                    plInfo->jobHandle = ptr->jobHandle;
                    plInfo->suggestedWeight = ptr->suggestedWeight;
                    plInfo->streamNum = ptr->streamNum;
                    plInfo->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                    plInfo->pipelineConfig = ptr->pipelineConfig;
                    plInfo->pipeline = run(plInfo, ptr->pipelineConfig);
                    if(!plInfo->pipeline){
                        _WRN("Pipeline manager unable to constuct the pipeline with handle {}", plInfo->jobHandle);
                        releaseResourceByWorkloadWeight(plInfo->suggestedWeight);
                        replyLoadPipeline(ptr->commHandle, 500, "Unable to construct the specified pipeline", ptr->jobHandle);
                        
                        // erase the element in waiting queue
                        // iter = m_waitingQueue.erase(iter);
                        erase_flag = true;
                    }
                    else{
                        _TRC("Pipeline manager constucted the pipeline with handle {}", plInfo->jobHandle);
                        {
                            std::lock_guard<std::mutex> lg(m_workListMutex);
                            m_workList.emplace(plInfo->jobHandle, plInfo);
                        }
                        m_workListCv.notify_all();

                        replyLoadPipeline(ptr->commHandle, 200, "Success", ptr->jobHandle);

                        // erase the element in waiting queue
                        // iter = m_waitingQueue.erase(iter);

                        // we break here to release the mutex, as pipeline construction might takes long
                        // break;

                        erase_flag = true;
                    }
                }
                else{
                    _TRC("load task with handle {} delayed due to workload constrains", ptr->jobHandle);
                    // ++iter;
                    erase_flag = false;
                }
            }
            //
            // processing TASK_RUN: do not construct a new pipeline, reuse existing pipeline identified by jobHandle.
            //  > if jobHandle not exists in current m_workList, return error code
            //
            else if((curTask)->taskType == Task::TASK_RUN){
                RunTaskInfo::Ptr ptr = std::dynamic_pointer_cast<RunTaskInfo>(curTask);
                _TRC("Pipeline manager starts to process on a run task with handle {}", ptr->jobHandle);

                std::lock_guard<std::mutex> lg(m_workListMutex);
                auto item = m_workList.find(ptr->jobHandle);
                if(item == m_workList.end()){
                    _TRC("No such handle {} exists in worklist", ptr->jobHandle);
                    replyRunError(ptr->commHandle, 400, "Handle does not exist", ptr->jobHandle);
                    
                    // erase the element in waiting queue
                    // iter = m_waitingQueue.erase(iter);
                    erase_flag = true;
                }
                else{
                    item->second->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                    item->second->commHandle.push_front(ptr->commHandle);

                    // support cross-stream style pipeline config
                    unsigned streamNum = item->second->streamNum;
                    int segNum = std::floor(ptr->mediaUris.size() / streamNum);
                    for (unsigned streamId = 0; streamId < streamNum; ++streamId) {
                        
                        // get piece for cur streamId
                        int beginIndex = (int)streamId * segNum;
                        int endIndex = streamId == (streamNum - 1) ? (int)ptr->mediaUris.size() : beginIndex + segNum;
                        std::vector<std::string> mediaUris(ptr->mediaUris.begin() + beginIndex, ptr->mediaUris.begin() + endIndex);

                        auto blob = hva::hvaBlob_t::make_blob();
                        blob->streamId = streamId;
                        blob->emplace<hva::hvaBuf_t>(mediaUris, sizeof(mediaUris));
                        item->second->pipeline->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                    }

                    // erase the element in waiting queue
                    // iter = m_waitingQueue.erase(iter);
                    erase_flag = true;
                }
            }
            //
            // processing TASK_UNLOAD: destroy an existing pipeline, reuse existing pipeline identified by jobHandle.
            //  > if jobHandle not exists in current m_workList, return error code
            //
            else if((curTask)->taskType == Task::TASK_UNLOAD){
                UnloadTaskInfo::Ptr ptr = std::dynamic_pointer_cast<UnloadTaskInfo>(curTask);
                _TRC("Pipeline manager starts to process on a unload task with handle {}", ptr->jobHandle);
                
                std::lock_guard<std::mutex> lg(m_workListMutex);
                auto item = m_workList.find(ptr->jobHandle);
                if(item == m_workList.end()){
                    _TRC("No such handle {} exists in worklist", ptr->jobHandle);
                    replyUnloadPipeline(ptr->commHandle, 200, "handle no longer exists", ptr->jobHandle);
                    
                    // erase the element in waiting queue
                    // iter = m_waitingQueue.erase(iter);
                    erase_flag = true;
                }
                else{
                    item->second->pipeline->stop();
                    // to-do: if we need a wait here?
                    m_workList.erase(ptr->jobHandle);
                    replyUnloadPipeline(ptr->commHandle, 200, "Success", ptr->jobHandle);
                    releaseResourceByWorkloadWeight(item->second->suggestedWeight);
                    
                    // erase the element in waiting queue
                    // iter = m_waitingQueue.erase(iter);
                    erase_flag = true;
                }
                
            }
            //
            // processing TASK_AUTO_RUN: auto load new pipeline when resources enough (< MaxConcurrentWorkload), 
            // or else reuse an existing pipeline with same pipelineConfig
            //
            else if((curTask)->taskType == Task::TASK_AUTO_RUN){
                AutoRunTaskInfo::Ptr ptr = std::dynamic_pointer_cast<AutoRunTaskInfo>(curTask);
                _TRC("Pipeline manager starts to process on a auto run task");

                // to-do: check release
                if(acquireResourceByWorkloadWeight(ptr->suggestedWeight)){
                    // in case we have resource to create workload
                    PipelineInfo::Ptr plInfo = PipelineInfo::Ptr(m_plInfoPool.construct(), [this](PipelineInfo* ptr){
                            m_plInfoPool.destroy(ptr);});
                    HCE_AI_ASSERT(plInfo);
                    plInfo->jobHandle = fetchIncrementHandleIndex();
                    plInfo->suggestedWeight = ptr->suggestedWeight;
                    plInfo->streamNum = ptr->streamNum;
                    plInfo->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                    plInfo->pipelineConfig = ptr->pipelineConfig;
                    plInfo->pipeline = run(plInfo, ptr->pipelineConfig);
                    if(!plInfo->pipeline){
                        _WRN("Pipeline manager unable to constuct the pipeline with handle {}", plInfo->jobHandle);
                        releaseResourceByWorkloadWeight(plInfo->suggestedWeight);
                        replyRunError(ptr->commHandle, 500, "Unable to construct the specified pipeline", 0);
                        
                        // erase the element in waiting queue
                        // iter = m_waitingQueue.erase(iter);
                        erase_flag = true;
                    }
                    else{
                        plInfo->commHandle.push_front(ptr->commHandle);

                        // support cross-stream style pipeline config
                        int segNum = std::floor(ptr->mediaUris.size() / ptr->streamNum);
                        for (unsigned streamId = 0; streamId < ptr->streamNum; ++streamId) {

                            // get piece for cur streamId
                            int beginIndex = (int)streamId * segNum;
                            int endIndex = streamId == (ptr->streamNum - 1) ? (int)ptr->mediaUris.size() : beginIndex + segNum;
                            std::vector<std::string> mediaUris(ptr->mediaUris.begin() + beginIndex, ptr->mediaUris.begin() + endIndex);

                            auto blob = hva::hvaBlob_t::make_blob();
                            blob->streamId = streamId;
                            blob->emplace<hva::hvaBuf_t>(mediaUris, sizeof(mediaUris));
                            plInfo->pipeline->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                        }

                        _TRC("Pipeline manager constucted the pipeline with handle {}", plInfo->jobHandle);
                        {
                            std::lock_guard<std::mutex> lg(m_workListMutex);
                            m_workList.emplace(plInfo->jobHandle, plInfo);
                        }
                        m_workListCv.notify_all();

                        // erase the element in waiting queue
                        // iter = m_waitingQueue.erase(iter);

                        // we break here to release the mutex, as pipeline construction might takes long
                        // break;

                        erase_flag = true;

                    }
                }
                else{
                    std::lock_guard<std::mutex> lg(m_workListMutex);
                    Handle eldestHandle;
                    volatile uint64_t eldestHb = UINT64_MAX;
                    for(const auto& item: m_workList){
                        if(item.second->pipelineConfig == ptr->pipelineConfig){
                            if(item.second->heartbeat < eldestHb){
                                eldestHb = item.second->heartbeat;
                                eldestHandle = item.first;
                            }
                        }
                    }
                    if(eldestHb == UINT64_MAX){
                        _TRC("auto run task delays as no resource nor similar pipeline");
                        // ++iter;
                        erase_flag = false;
                    }
                    else{
                        _TRC("auto run task schedules to use existing pipeline with handle {}", eldestHandle);

                        m_workList[eldestHandle]->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                        m_workList[eldestHandle]->commHandle.push_front(ptr->commHandle);
                        
                        // support cross-stream style pipeline config
                        int segNum = std::floor(ptr->mediaUris.size() / ptr->streamNum);
                        for (unsigned streamId = 0; streamId < ptr->streamNum; ++streamId) {
                            
                            // get piece for cur streamId
                            int beginIndex = (int)streamId * segNum;
                            int endIndex = streamId == (ptr->streamNum - 1) ? (int)ptr->mediaUris.size() : beginIndex + segNum;
                            std::vector<std::string> mediaUris(ptr->mediaUris.begin() + beginIndex, ptr->mediaUris.begin() + endIndex);
                            
                            auto blob = hva::hvaBlob_t::make_blob();
                            blob->streamId = streamId;
                            blob->emplace<hva::hvaBuf_t>(mediaUris, sizeof(mediaUris));
                            m_workList[eldestHandle]->pipeline->sendToPort(blob, "Input", 0, std::chrono::milliseconds(0));
                        }
                        
                        // erase the element in waiting queue
                        // iter = m_waitingQueue.erase(iter);
                        erase_flag = true;
                    }
                }
            }
            else{
                // should not happen
                _ERR("Unknow task type!");
                HCE_AI_ASSERT(false);
            }
            
            lk.lock();
            if (!erase_flag) {
                // push curTask to waitingQueue again, wait for next polling
                m_waitingQueue.push_back(curTask);
                m_waitingQueueCv.notify_all(); // wakeup the thread
            }
            if (iter == m_waitingQueue.end()) {
                break;
            }
            iter = m_waitingQueue.begin();

        }

        lk.unlock();
    }

    // where the state has transfered to stopped

    // discard all elements in waiting queue
    lk.lock();
    m_waitingQueue.clear();
    lk.unlock();

    // stop all working items in working list
    {
        std::lock_guard<std::mutex> lg(m_workListMutex);
        for(const auto& item: m_workList){
            if(item.second->pipeline->getState() != ::hva::hvaState_t::stop){
                item.second->pipeline->stop();
            }
        }
        m_workList.clear();
    }
    return hceAiSuccess;
}

/**
 * @brief register coming task as Task::TASK_LOAD, to load a new pipeline
 * @param pipelineConfig ai inference pipeline description
 * @param commHandle coming tcp connection handle
 * @param jobHandle will be generated using fetchIncrementHandleIndex()
 * @param suggestedWeight task weight
*/
hceAiStatus_t HttpPipelineManager::submitLoadPipeline(
    const std::string& pipelineConfig,
    HttpServerLowLatency::ClientDes commHandle, Handle& jobHandle,
    unsigned suggestedWeight, unsigned streamNum) {

    HCE_AI_ASSERT(commHandle);
    HCE_AI_ASSERT(!pipelineConfig.empty());

    jobHandle = fetchIncrementHandleIndex();
    _TRC("Pipeline manager received a request with handle {}", jobHandle);

    // to-do: modify the magic default weight 1
    suggestedWeight = suggestedWeight == 0 ? 1 : suggestedWeight;

    {
        LoadTaskInfo::Ptr pendingTask = std::shared_ptr<LoadTaskInfo>(
            m_ltiPool.construct(),
            [this](LoadTaskInfo* ptr) { m_ltiPool.destroy(ptr); });
        HCE_AI_ASSERT(pendingTask);
        pendingTask->taskType = Task::TASK_LOAD;
        pendingTask->commHandle = commHandle;
        pendingTask->pipelineConfig = pipelineConfig;
        pendingTask->jobHandle = jobHandle;
        pendingTask->suggestedWeight = suggestedWeight;
        pendingTask->streamNum = streamNum;

        std::lock_guard<std::mutex> lg(m_waitingQueueMutex);

        m_waitingQueue.push_back(pendingTask);
    }
    m_waitingQueueCv.notify_all();
    return hceAiSuccess;
}

/**
 * @brief register coming task as Task::TASK_RUN, an existing pipeline is expected
 * @param mediaUris inputs to process
 * @param jobHandle jobHandle to identify an existing pipeline
 * @param commHandle coming tcp connection handle
*/
hceAiStatus_t HttpPipelineManager::submitRun(
    const std::vector<std::string>& mediaUris, Handle jobHandle,
    HttpServerLowLatency::ClientDes commHandle) {
    HCE_AI_ASSERT(commHandle);
    HCE_AI_ASSERT(mediaUris.size() != 0);

    {
        RunTaskInfo::Ptr pendingTask = std::shared_ptr<RunTaskInfo>(
            m_rtiPool.construct(),
            [this](RunTaskInfo* ptr) { m_rtiPool.destroy(ptr); });
        HCE_AI_ASSERT(pendingTask);
        pendingTask->taskType = Task::TASK_RUN;
        pendingTask->commHandle = commHandle;
        pendingTask->mediaUris = mediaUris;
        pendingTask->jobHandle = jobHandle;

        std::lock_guard<std::mutex> lg(m_waitingQueueMutex);

        m_waitingQueue.push_back(std::move(pendingTask));
    }
    m_waitingQueueCv.notify_all();
    return hceAiSuccess;
}

/**
 * @brief register coming task as Task::TASK_AUTO_RUN
 * auto load new pipeline when resources enough (< MaxConcurrentWorkload), or else reuse an existing pipeline with same pipelineConfig
 * @param mediaUris inputs to process
 * @param pipelineConfig ai inference pipeline description
 * @param commHandle coming tcp connection handle
 * @param suggestedWeight task weight
*/
hceAiStatus_t HttpPipelineManager::submitAutoRun(
    const std::vector<std::string>& mediaUris,
    const std::string& pipelineConfig,
    HttpServerLowLatency::ClientDes commHandle, unsigned suggestedWeight,
    unsigned streamNum) {

    HCE_AI_ASSERT(commHandle);
    HCE_AI_ASSERT(mediaUris.size() != 0);

    // to-do: modify the magic default weight 1
    suggestedWeight = suggestedWeight == 0 ? 1 : suggestedWeight;

    {
        AutoRunTaskInfo::Ptr pendingTask = std::shared_ptr<AutoRunTaskInfo>(
            m_artiPool.construct(),
            [this](AutoRunTaskInfo* ptr) { m_artiPool.destroy(ptr); });
        HCE_AI_ASSERT(pendingTask);
        pendingTask->taskType = Task::TASK_AUTO_RUN;
        pendingTask->commHandle = commHandle;
        pendingTask->mediaUris = mediaUris;
        pendingTask->pipelineConfig = pipelineConfig;
        pendingTask->suggestedWeight = suggestedWeight;
        pendingTask->streamNum = streamNum;

        std::lock_guard<std::mutex> lg(m_waitingQueueMutex);

        m_waitingQueue.push_back(std::move(pendingTask));
    }
    m_waitingQueueCv.notify_all();
    return hceAiSuccess;
}

/**
 * @brief register coming task as Task::TASK_UNLOAD, to destroy an existing pipeline
 * @param jobHandle jobHandle to identify an existing pipeline
 * @param commHandle coming tcp connection handle
*/
hceAiStatus_t HttpPipelineManager::submitUnloadPipeline(Handle jobHandle, HttpServerLowLatency::ClientDes commHandle){
    {
        UnloadTaskInfo::Ptr pendingTask = std::shared_ptr<UnloadTaskInfo>(m_utiPool.construct(), 
                [this](UnloadTaskInfo* ptr){ m_utiPool.destroy(ptr);});
        HCE_AI_ASSERT(pendingTask);
        pendingTask->taskType = Task::TASK_UNLOAD;
        pendingTask->commHandle = commHandle;
        pendingTask->jobHandle = jobHandle;

        std::lock_guard<std::mutex> lg(m_waitingQueueMutex);
        
        m_waitingQueue.push_back(std::move(pendingTask));
    }
    m_waitingQueueCv.notify_all();
    return hceAiSuccess;
}

/**
 * @brief start running a pipeline
 * step1. construct pipeline using parseFromString(pipelionConfig)
 * step2. register emit listener in output node
 * step3. pl->prepare();
 * step4. pl->start();
*/
HttpPipelineManager::hvaPipelinePtr HttpPipelineManager::run(PipelineInfo::Ptr plInfo, const std::string& pipelionConfig){
    HCE_AI_CHECK_RETURN_IF_FAIL((!pipelionConfig.empty()), hvaPipelinePtr());

    hva::hvaPipelineParser_t parser;
    hvaPipelinePtr pl(m_pipelinePool.construct(), [this](hva::hvaPipeline_t* ptr){m_pipelinePool.destroy(ptr);});
    HCE_AI_ASSERT(pl);

    if(parser.parseFromString(pipelionConfig, *pl) != hva::hvaSuccess){
        return hvaPipelinePtr();
    }

    std::shared_ptr<_restReplyListener> listener(m_rrlPool.construct(plInfo), 
            [this](_restReplyListener* ptr){m_rrlPool.destroy(ptr);});

    HCE_AI_ASSERT(listener);
    dynamic_cast<baseResponseNode&>(pl->getNodeHandle("Output")).registerEmitListener(std::move(listener));

    pl->prepare();

    pl->start();

    return pl;
}

void HttpPipelineManager::replyLoadPipeline(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle){
    boost::property_tree::ptree jsonTree;
    
    jsonTree.put("description", description);
    jsonTree.put("request", "load_pipeline");
    jsonTree.put("handle", jobHandle);

    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);

    HttpServerLowLatency::getInstance().reply(client, code, ss.str());
}

/**
 * @brief reply for request: unload_pipeline
 * @param client coming tcp connection handle
 * @param code response code
 * @param description response description
 * @param jobHandle jobHandle to identify an existing pipeline
*/
void HttpPipelineManager::replyUnloadPipeline(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle){
    boost::property_tree::ptree jsonTree;
    
    jsonTree.put("description", description);
    jsonTree.put("request", "unload_pipeline");
    jsonTree.put("handle", jobHandle);

    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);

    HttpServerLowLatency::getInstance().reply(client, code, ss.str());
}

/**
 * @brief reply `error` state for request: run
 * @param client coming tcp connection handle
 * @param code response code
 * @param description response description
 * @param jobHandle jobHandle to identify an existing pipeline
*/
void HttpPipelineManager::replyRunError(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle){
    boost::property_tree::ptree jsonTree;
    
    jsonTree.put("description", description);
    jsonTree.put("request", "run");
    jsonTree.put("handle", jobHandle);

    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);

    HttpServerLowLatency::getInstance().reply(client, code, ss.str());
}

}

}

}
