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

#ifndef HCE_AI_INF_LL_HTTP_PIPELINE_MANAGER_HPP
#define HCE_AI_INF_LL_HTTP_PIPELINE_MANAGER_HPP

#include <vector>
#include <unordered_map>

#include "common/common.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "low_latency_server/pipelineManager.hpp"
#include "low_latency_server/http_server/lowLatencyServer.hpp"

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC HttpPipelineManager: public PipelineManager{
public:
    using Handle = uint32_t;

    ~HttpPipelineManager();

    HttpPipelineManager(const HttpPipelineManager&) = delete;

    HttpPipelineManager(HttpPipelineManager&&) = delete;

    HttpPipelineManager& operator=(const HttpPipelineManager&) = delete;

    HttpPipelineManager& operator=(HttpPipelineManager&&) = delete;

    /**
    * @brief Get a reference to pipeline manager instance
    * 
    * @param void
    * @return reference to the singleton
    * 
    */
    static HttpPipelineManager& getInstance();

    /**
    * @brief start the pipeline manager
    * 
    * @param void
    * @return hceAiSuccess upon success
    * 
    */
    virtual hceAiStatus_t start(unsigned pipelineManagerPoolSize);

    /**
    * @brief Stop the processing routine
    * 
    * @param void
    * @return hceAiSuccess upon success
    * 
    */
    virtual hceAiStatus_t stop();

    /**
    * @brief Submit a pipeline request in a non-blocking manner
    * 
    * @param param the media inputs
    * @param pipelineConfig the serialized pipeline string in form of json
    * @param jobHandle a handle returned to caller to be used for later call
    * @param suggestedWeight an integer to indicate the weight of workload. If 0 is specified this will automatically 
    *     set to equal to number of input files
    * @param streamNum: An unsigned integer value to enable cross-stream inference on the workload of the pipeline submitted. 
    *                  default as 1, this would degrade to the default configuration: one pipeline for one stream.
    * @return hceAiSuccess upon success
    * 
    */
    hceAiStatus_t submitLoadPipeline(const std::string& pipelineConfig, HttpServerLowLatency::ClientDes commHandle, Handle& jobHandle, unsigned suggestedWeight = 0, unsigned streamNum = 1);

    /**
     * @brief register coming task as Task::TASK_RUN, an existing pipeline is expected
     * @param mediaUris inputs to process
     * @param jobHandle jobHandle to identify an existing pipeline
     * @param commHandle coming tcp connection handle
    */
    hceAiStatus_t submitRun(const std::vector<std::string>& mediaUris, Handle jobHandle, HttpServerLowLatency::ClientDes commHandle);

    /**
     * @brief register coming task as Task::TASK_UNLOAD, to destroy an existing pipeline
     * @param jobHandle jobHandle to identify an existing pipeline
     * @param commHandle coming tcp connection handle
     * @param streamNum: An unsigned integer value to enable cross-stream inference on the workload of the pipeline submitted. 
     *                  default as 1, this would degrade to the default configuration: one pipeline for one stream.
    */
    hceAiStatus_t submitAutoRun(const std::vector<std::string>& mediaUris, const std::string& pipelineConfig, HttpServerLowLatency::ClientDes commHandle, unsigned suggestedWeight = 0, unsigned streamNum = 1);

    /**
     * @brief register coming task as Task::TASK_AUTO_RUN
     * auto load new pipeline when resources enough (< MaxConcurrentWorkload), or else reuse an existing pipeline with same pipelineConfig
     * @param mediaUris inputs to process
     * @param pipelineConfig ai inference pipeline description
     * @param commHandle coming tcp connection handle
     * @param suggestedWeight task weight
    */
    hceAiStatus_t submitUnloadPipeline(Handle jobHandle, HttpServerLowLatency::ClientDes commHandle);
    
private:

    HttpPipelineManager();

    using hvaPipelinePtr = std::shared_ptr<::hva::hvaPipeline_t>;

    class PipelineInfo: public PipelineInfoHolderBase_t{
    public:
        using Ptr = std::shared_ptr<PipelineInfo>;
        using WeakPtr = std::weak_ptr<PipelineInfo>;
        PipelineInfo() = default;

        ~PipelineInfo() = default;

        std::list<HttpServerLowLatency::ClientDes> commHandle;
    };

    class LoadTaskInfo: public Task{
    public:
        using Ptr = std::shared_ptr<LoadTaskInfo>;
        LoadTaskInfo():jobHandle(0u), suggestedWeight(0u){

        };

        virtual ~LoadTaskInfo() override{

        };

        std::string pipelineConfig;
        Handle jobHandle;
        unsigned suggestedWeight;
        unsigned streamNum;

        HttpServerLowLatency::ClientDes commHandle;
    };

    class RunTaskInfo: public Task{
    public:
        using Ptr = std::shared_ptr<RunTaskInfo>;
        RunTaskInfo():jobHandle(0u){

        };

        virtual ~RunTaskInfo(){

        };

        std::vector<std::string> mediaUris;
        Handle jobHandle;

        HttpServerLowLatency::ClientDes commHandle;
    };

    class UnloadTaskInfo: public Task{
    public:
        using Ptr = std::shared_ptr<UnloadTaskInfo>;
        UnloadTaskInfo():jobHandle(0u){

        };

        virtual ~UnloadTaskInfo() override{

        };

        Handle jobHandle;
        
        HttpServerLowLatency::ClientDes commHandle;
    };

    class AutoRunTaskInfo: public Task{
    public:
        using Ptr = std::shared_ptr<AutoRunTaskInfo>;
        AutoRunTaskInfo():suggestedWeight(0u){

        };

        virtual ~AutoRunTaskInfo(){

        };

        std::vector<std::string> mediaUris;
        std::string pipelineConfig;
        unsigned suggestedWeight;
        unsigned streamNum;
        
        HttpServerLowLatency::ClientDes commHandle;
    };

    /**
     * @brief register listener to reply http server
     * key functions:
     *  > onEmit: write response body for each processed frame.
     *  > onFinish: reply to client after request frames all finished processing.
    */
    class _restReplyListener: public baseResponseNode::EmitListener{
    public:
        _restReplyListener(PipelineInfo::WeakPtr plInfo)
                :baseResponseNode::EmitListener(), m_plInfo(plInfo){ };

        virtual ~_restReplyListener() override{
            if(auto sp = m_plInfo.lock()){

                if(!sp->commHandle.empty()){
                    _WRN("Making timeout response to remaining connections on pipeline with handle {}!", sp->jobHandle);
                    auto iter = sp->commHandle.begin();
                    while(iter != sp->commHandle.end()){
                        HttpServerLowLatency::getInstance().reply(*iter, 408, "{\n    \"result\": [\n        {\n            \"status_code\": \"-5\",\n            \"description\": \"Pipeline timeout\"\n        }\n    ]\n}");
                        iter = sp->commHandle.erase(iter);
                    }
                }
            }
            else{
                _WRN("Pipeline no longer exists at reply listener destruction");
            }
            _TRC("rest reply listener destroyed");
        };
        
        /**
         * @brief write response body for each processed frame.
         * @param res response body
         * @param node outputNode who sends response here
        */
        virtual void onEmit(baseResponseNode::Response res, const baseResponseNode* node, void* data) override{

            std::unique_lock<std::mutex> lk(m_mutex);

            if(auto sp = m_plInfo.lock()){
                sp->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                boost::property_tree::ptree res_frame;
                std::stringstream ss(res.message); 
                boost::property_tree::read_json(ss, res_frame);
                m_frames.push_back(std::make_pair("", res_frame));
            }
            else{
                _WRN("Pipeline no longer exists at response emit");
            }
        };

        /**
         * @brief  reply to client after request frames all finished processing.
         * @param node outputNode who sends response here
        */
        virtual void onFinish(const baseResponseNode* node, void* data) override{
            
            std::unique_lock<std::mutex> lk(m_mutex);

            if(auto sp = m_plInfo.lock()){

                sp->heartbeat = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                m_jsonTree.add_child("result", m_frames);

                std::stringstream ss;
                boost::property_tree::json_parser::write_json(ss, m_jsonTree);

                if(sp->commHandle.empty()){
                    _ERR("Pipeline with handle {} has no comm handle!", sp->jobHandle);
                }
                HttpServerLowLatency::getInstance().reply(sp->commHandle.back(), 200, ss.str());
                sp->commHandle.pop_back();
            }
            else{
                _WRN("Pipeline no longer exists at response emit");
            }
            m_frames.clear();
            m_jsonTree.clear();
        };

    private:
        PipelineInfo::WeakPtr m_plInfo;
        boost::property_tree::ptree m_jsonTree;
        boost::property_tree::ptree m_frames;
        std::mutex m_mutex;                         // thread-safe
    };
    
    /**
     * @brief watch lifetime for m_workList
    */
    virtual void watch();

    /**
     * @brief keep processing tasks in waitingQueue, until pipeline state transisted to Stopped
    */
    hceAiStatus_t loop();

    /**
     * @brief start running a pipeline
     * step1. construct pipeline using parseFromString(pipelionConfig)
     * step2. register emit listener in output node
     * step3. pl->prepare();
     * step4. pl->start();
    */
    hvaPipelinePtr run(PipelineInfo::Ptr plInfo, const std::string& pipelionConfig);

    /**
     * @brief reply for request: load_pipeline
     * @param client coming tcp connection handle
     * @param code response code
     * @param description response description
     * @param jobHandle jobHandle to identify an existing pipeline
    */
    void replyLoadPipeline(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle);

    /**
     * @brief reply for request: unload_pipeline
     * @param client coming tcp connection handle
     * @param code response code
     * @param description response description
     * @param jobHandle jobHandle to identify an existing pipeline
    */
    void replyUnloadPipeline(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle);
    
    /**
     * @brief reply `error` state for request: run
     * @param client coming tcp connection handle
     * @param code response code
     * @param description response description
     * @param jobHandle jobHandle to identify an existing pipeline
    */
    void replyRunError(HttpServerLowLatency::ClientDes client, unsigned code, const std::string& description, Handle jobHandle);

    boost::object_pool<PipelineInfo> m_plInfoPool;
    boost::object_pool<_restReplyListener> m_rrlPool;
    
    boost::object_pool<LoadTaskInfo> m_ltiPool;
    boost::object_pool<RunTaskInfo> m_rtiPool;
    boost::object_pool<UnloadTaskInfo> m_utiPool;
    boost::object_pool<AutoRunTaskInfo> m_artiPool;
    
    std::unordered_map<Handle, PipelineInfo::Ptr, std::hash<Handle>, std::equal_to<Handle>, 
            boost::fast_pool_allocator<std::pair<Handle, PipelineInfo::Ptr>>> m_workList;

};

}

}

}

#endif //#ifndef HCE_AI_INF_LL_HTTP_PIPELINE_MANAGER_HPP
