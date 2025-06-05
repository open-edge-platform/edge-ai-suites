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

#ifndef __BASE_IMAGE_INFERENCE_NODE_HPP__
#define __BASE_IMAGE_INFERENCE_NODE_HPP__

#include <iostream>
#include <memory>
#include <mutex>
#include <condition_variable>
#include <string>
#include <vector>
#include <unordered_map>
#include <time.h>
#include <sys/timeb.h>

#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "common/context.h"
#include "nodes/databaseMeta.hpp"
#include "inference_nodes/base/image_inference_instance.hpp"

#define DEFAULT_DEVICE "CPU"
#define DEFAULT_DEVICE_EXTENSIONS ""
#define DEFAULT_MODEL_PATH ""
#define DEFAULT_MODEL_PROC_CONFIG ""
#define DEFAULT_MODEL_PROC_LIB ""
#define DEFAULT_INFERENCE_INTERVAL 1
#define DEFAULT_NIREQ 1
#define DEFAULT_PRE_PROC_TYPE "ie"
#define DEFAULT_ALLOCATOR_NAME ""
#define DEFAULT_INFERENCE_TYPE 0
#define DEFAULT_INFERENCE_REGION_TYPE 0
#define DEFAULT_RESHAPE_MODEL_INPUT false
#define DEFAULT_BATCH_SIZE 0
#define DEFAULT_RESHAPE_WIDTH 0
#define DEFAULT_RESHAPE_HEIGHT 0

namespace hce{

namespace ai{

namespace inference{

class InputBlobsContainer {
public:
    struct BlobKey {
        unsigned streamId, frameId;

        BlobKey(unsigned streamId, unsigned frameId) : streamId(streamId), frameId(frameId) {};

        bool operator==(const BlobKey &o) const {
            return streamId == o.streamId && frameId == o.frameId;
        }
        
        struct HashFunction
        {
            unsigned operator()(const BlobKey& o) const
            {
                return o.streamId * 10000 + o.frameId;
            }
        };
    };
    
    InputBlobsContainer() = default;
    ~InputBlobsContainer() = default;

    /**
     * @brief if input is new, record it.
     * @return void
    */
    void put(hva::hvaBlob_t::Ptr input) {
        auto key = BlobKey(input->streamId, input->frameId);
        if (m_inputs.count(key) == 0) {
            m_inputs.emplace(key, input);
            m_inferenceCnt.emplace(key, 0);
        }
        m_inferenceCnt[key] ++;
    };

    bool erase(hva::hvaBlob_t::Ptr input) {
        auto key = BlobKey(input->streamId, input->frameId);
        if (m_inputs.count(key) == 0) {
            return false;
        }
        m_inputs[key].reset();
        m_inputs.erase(key);
        m_inferenceCnt.erase(key);
        return true;
    }

    /**
     * @brief clear all recorded inputs
     * @return void
    */
    void clear() {
        for (auto& input : m_inputs) {
            input.second.reset();
        }
        m_inputs.clear();
        m_inferenceCnt.clear();
    };

    bool isCompletedInference(hva::hvaBlob_t::Ptr input, size_t regionCnt) {
        auto key = BlobKey(input->streamId, input->frameId);
        if (m_inputs.count(key) > 0) {
            return m_inferenceCnt[key] == regionCnt;
        }
        return false;
    };

private:
    std::unordered_map<BlobKey, hva::hvaBlob_t::Ptr, BlobKey::HashFunction> m_inputs;
    std::unordered_map<BlobKey, size_t, BlobKey::HashFunction> m_inferenceCnt;
};

class baseImageInferenceNode : public hva::hvaNode_t{
public:
    
    baseImageInferenceNode(std::size_t totalThreadNum);

    ~baseImageInferenceNode();

    /**
    * @brief initialization of this node. Init all inference properties with default value
    * 
    * @param void
    * @return void
    * 
    */
    void init();

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    hva::hvaStatus_t configureByString(const std::string& config);

    /**
    * @brief prepare and intialize this hvaNode_t instance. Create ImageInferenceInstance
    * 
    * @param void
    * @return hvaSuccess if success
    */
    hva::hvaStatus_t prepare() override;

    /**
    * @brief To perform any necessary operations when pipeline's rearm is called
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    hva::hvaStatus_t rearm();

    /**
    * @brief reset this node
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    hva::hvaStatus_t reset();
    
    /**
    * @brief return the human-readable name of this node class
    * 
    * @param void
    * @return node class name
    */
    virtual const std::string nodeClassName() = 0;

protected:
    hva::hvaConfigStringParser_t m_configParser;

    InferenceProperty m_inferenceProperties;
    ImageInferenceInstance::Ptr m_inferenceInstance;

private:
    ImageInferenceInstance::Ptr createInferenceInstance(InferenceProperty& inferenceProperty);

    hva::hvaStatus_t releaseInferenceInstance();
};


class baseImageInferenceNodeWorker : public hva::hvaNodeWorker_t{
public:
    baseImageInferenceNodeWorker(hva::hvaNode_t* parentNode,
                            InferenceProperty inferenceProperty,
                            ImageInferenceInstance::Ptr instance);

    ~baseImageInferenceNodeWorker();

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass
     * output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    /**
    * @brief reset this node
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    virtual hva::hvaStatus_t reset();

protected:
    std::string m_nodeName;
    InputBlobsContainer m_inputBlobs;
    InferenceProperty m_inferenceProperties;
    ImageInferenceInstance::Ptr m_inferenceInstance;

    /**
     * @brief collect all inputs from each port of hvaNode. Can be overrided in the derived class nodes workers.
     * 
     * @return std::vector<std::vector<hva::hvaBlob_t::Ptr>>
    */
    virtual std::vector<std::vector<hva::hvaBlob_t::Ptr>> getInput(std::size_t batchIdx);
    
    /**
     * @brief validate input
     * @param blob current input
     * @return if process need continue 
     * 
    */
    bool validateInput(hva::hvaBlob_t::Ptr& blob);

private:
    std::unordered_map<unsigned, std::pair<int, int>> m_streamEndFlags;

    /**
     * @brief should be implemented in the derived class nodes workers. 
     *        it would be called at the end of each process() to send outputs to the downstream nodes.
     * @return void
    */
    virtual void processOutput(
        std::map<std::string, InferenceBackend::OutputBlob::Ptr> blobs,
        std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames) = 0;

    /**
     * @brief it would be called at the end of each process() to send outputs to the downstream nodes.
     * @return void
    */
    void processOutputFailed(
        std::vector<std::shared_ptr<InferenceBackend::ImageInference::IFrameBase>> frames);

    // std::unique_ptr<InferenceBackend::BufferToImageMapper> buffer_mapper;

    void updateStreamEndFlags(unsigned streamId, unsigned frameId, unsigned tag);

    bool needFlushInference(unsigned streamId);
};

} // namespace inference

} // namespace ai

} // namespace hce

#endif /*__BASE_IMAGE_INFERENCE_NODE_HPP__*/
