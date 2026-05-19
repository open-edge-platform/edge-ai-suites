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

#ifndef HCE_AI_INF_TRACKER_NODE_CPU_HPP
#define HCE_AI_INF_TRACKER_NODE_CPU_HPP

#include <string>
#include <memory>
#include <limits.h>

#include <inc/api/hvaPipeline.hpp>

#include "modules/tracker.hpp"
#include "nodes/databaseMeta.hpp"

// #ifdef ENABLE_VAAPI
//     #include "modules/vaapi/utils.hpp"
// #endif

namespace hce{

namespace ai{

namespace inference{

class TrackerNode_CPU : public hva::hvaNode_t{
public:

    TrackerNode_CPU(std::size_t totalThreadNum);

    virtual ~TrackerNode_CPU() override;

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
    * @brief Constructs and returns a node worker instance: TrackerNodeWorker_CPU .
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

class TrackerNodeWorker_CPU : public hva::hvaNodeWorker_t{
public:
    TrackerNodeWorker_CPU(hva::hvaNode_t* parentNode, const vas::ot::Tracker::InitParameters& tracker_param);

    virtual ~TrackerNodeWorker_CPU() override;

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

#endif //#ifndef HCE_AI_INF_TRACKER_NODE_CPU_HPP