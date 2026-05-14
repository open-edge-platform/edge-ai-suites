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

#include "nodes/base/baseResponseNode.hpp"

namespace hce{

namespace ai{

namespace inference{

class baseResponseNode::Impl{
public:

    Impl(baseResponseNode& ctx);

    ~Impl();

    void registerEmitListener(std::shared_ptr<EmitListener> listner);

    void clearAllEmitListener();

    bool emitOutput(Response res, const baseResponseNode* node, void* data);

    bool emitFinish(const baseResponseNode* node, void* data);

    /**
     * @brief maintain finish-flag counter
     * 
    */
    void addEmitFinishFlag();

    /**
     * @brief check whether to trigger emitFinish()
     * 
    */
    bool isEmitFinish();

private: 
    baseResponseNode& m_ctx;
    std::vector<std::shared_ptr<EmitListener>> m_listeners;
    std::atomic<int> m_emitFinishFlag{0};
    
};

baseResponseNode::Impl::Impl(baseResponseNode& ctx):m_ctx(ctx){

}

baseResponseNode::Impl::~Impl(){
    clearAllEmitListener();
}

void baseResponseNode::Impl::registerEmitListener(std::shared_ptr<EmitListener> listner){
    m_listeners.push_back(std::move(listner));
}

void baseResponseNode::Impl::clearAllEmitListener(){
    m_listeners.clear();
}

bool baseResponseNode::Impl::emitOutput(Response res, const baseResponseNode* node, void* data){
    for(const auto& item: m_listeners){
        item->onEmit(std::move(res), node, data);
    }
    return true;
}

bool baseResponseNode::Impl::emitFinish(const baseResponseNode* node, void* data){
    for(const auto& item: m_listeners){
        item->onFinish(node, data);
    }
    return true;
}

/**
 * @brief maintain finish-flag counter
 * 
*/
void baseResponseNode::Impl::addEmitFinishFlag() {
    m_emitFinishFlag ++;
}

/**
 * @brief check whether to trigger emitFinish()
 * 
*/
bool baseResponseNode::Impl::isEmitFinish() {
    auto batchCfg = m_ctx.getBatchingConfig();
    if (m_emitFinishFlag == batchCfg.streamNum) {
        // collect finish-flags from all streams, can trigger emitFinish() now
        m_emitFinishFlag = 0;
        return true;
    }
    else {
        return false;
    }
}

baseResponseNode::EmitListener::EmitListener(){

}

baseResponseNode::EmitListener::~EmitListener(){
    
}


baseResponseNode::baseResponseNode(std::size_t inPortNum, std::size_t outPortNum, std::size_t totalThreadNum)
        :hva::hvaNode_t(inPortNum, outPortNum, totalThreadNum), m_impl(new Impl(*this)){

}

baseResponseNode::~baseResponseNode(){

}

/**
* @brief prepare and intialize this hvaNode_t instance
* 
* @param void
* @return hvaSuccess if success
*/
hva::hvaStatus_t baseResponseNode::prepare() {

    // check streaming strategy: frames will be fetched in order
    auto configBatch = this->getBatchingConfig();
    if (configBatch.batchingPolicy != (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream) {
        if (this->getTotalThreadNum() == 1) {
            // set default parameters
            // configure streaming strategy
            configBatch.batchingPolicy = (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream;
            configBatch.streamNum = 1;
            configBatch.threadNumPerBatch = 1;
            configBatch.batchSize = 1;
            this->configBatch(configBatch);
            HVA_DEBUG("%s change batching policy to BatchingPolicy::BatchingWithStream", nodeClassName().c_str());
        }
        else {
            HVA_ERROR("%s should use batching policy: BatchingPolicy::BatchingWithStream", nodeClassName().c_str());
            return hva::hvaFailure;
        }
    }

    return hva::hvaSuccess;
}

void baseResponseNode::registerEmitListener(std::shared_ptr<EmitListener> listner){
    m_impl->registerEmitListener(std::move(listner));
}

void baseResponseNode::clearAllEmitListener(){
    m_impl->clearAllEmitListener();
}

bool baseResponseNode::emitOutput(Response res, const baseResponseNode* node, void* data){
    return m_impl->emitOutput(std::move(res), node, data);
}

bool baseResponseNode::emitFinish(const baseResponseNode* node, void* data){
    return m_impl->emitFinish(node, data);
}

void baseResponseNode::addEmitFinishFlag() {
    m_impl->addEmitFinishFlag();
}

bool baseResponseNode::isEmitFinish() {
    return m_impl->isEmitFinish();
}

baseResponseNodeWorker::baseResponseNodeWorker(hva::hvaNode_t* parentNode)
    : hva::hvaNodeWorker_t(parentNode), m_workStreamId(-1) {
}

/**
 * @brief validate input: output node workers should be stream-aware, i.e., each worker works on a specific streamId.
 * @param blob current input
 * @return boolean
 * 
*/
bool baseResponseNodeWorker::validateStreamInput(const hva::hvaBlob_t::Ptr& blob) {

    // for sanity: check the consistency of streamId, each worker should work on one streamId.
    int streamId = (int)blob->streamId;
    if (m_workStreamId >= 0 && streamId != m_workStreamId) {
        HVA_ERROR(
            "%s worker should work on streamId: %d, but received "
            "data from invalid streamId: %d!", m_nodeName.c_str(), m_workStreamId, streamId);
        return false;
    } else {
        // the first coming stream decides the workStreamId for this worker
        m_workStreamId = streamId;
    }
    return true;
}

}

}

}