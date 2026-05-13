/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_OBJECT_SELECT_NODE_HPP
#define HCE_AI_INF_OBJECT_SELECT_NODE_HPP

#include <string>
#include <memory>
#include <limits.h>

#include <inc/api/hvaPipeline.hpp>

namespace hce{

namespace ai{

namespace inference{

enum struct ObjectSelectStrategy_t {
    ALL_IN_BEST_OUT = 0,        // In this mode, selection node will store all objects
                                    // within one selection interval (e.g, frameInterval = 30),
                                    // and send the topK ones to the downstream nodes.
    FIRST_IN_FIRST_OUT,         // In this mode, selection node will immediately send
                                    // the selected objects to the downstream nodes until
                                    // the topK is reached within one selection interval
                                    // (e.g, frameInterval = 30).
};

struct ObjectSelectParam_t {
    
    ObjectSelectStrategy_t strategy;          // selection strategy
    int32_t frameInterval;                  // every certain number of frames, start to select the high-quality object
    int32_t topK;                           // topK objects with highest quality will be selected
    bool trackletAware;                     // whether topK apply to each tracklet or not?
};

class ObjectSelectNode : public hva::hvaNode_t{
public:

    ObjectSelectNode(std::size_t totalThreadNum);

    virtual ~ObjectSelectNode() override;

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief validate configuration
    * @return sucess status
    */
    virtual hva::hvaStatus_t validateConfiguration() const override;

    /**
    * @brief Constructs and returns a node worker instance: ObjectSelectNodeWorker .
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    /**
     * @brief hvaframework: rearm
     * @return sucess status
     */
    virtual hva::hvaStatus_t rearm() override;

    /**
     * @brief hvaframework: reset
     * @return sucess status
     */
    virtual hva::hvaStatus_t reset() override;

    /**
     * @brief hvaframework: prepare
     * @return sucess status
     */
    virtual hva::hvaStatus_t prepare();

private: 

    class Impl;
    std::unique_ptr<Impl> m_impl;
};

class ObjectSelectNodeWorker : public hva::hvaNodeWorker_t{
public:
    ObjectSelectNodeWorker(hva::hvaNode_t* parentNode, const ObjectSelectParam_t& selectParams);

    virtual ~ObjectSelectNodeWorker() override;

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

    /**
     * @brief hvaframework: init
     */
    virtual void init() override;

private:

    class Impl;
    std::unique_ptr<Impl> m_impl;
};

}

}

}

#endif //#ifndef HCE_AI_INF_OBJECT_SELECT_NODE_HPP