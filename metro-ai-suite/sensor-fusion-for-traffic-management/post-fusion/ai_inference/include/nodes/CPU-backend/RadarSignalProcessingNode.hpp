/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef __RADAR_SIGNAL_PROCESSING_NODE_H_
#define __RADAR_SIGNAL_PROCESSING_NODE_H_

#include <iostream>
#include <memory>
#include <mutex>
#include <condition_variable>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <boost/property_tree/json_parser.hpp>
#include "modules/inference_util/radar/radar_config_parser.hpp"
#include "modules/inference_util/radar/libradar_helper.hpp"
namespace hce{

namespace ai{

namespace inference{

struct RadarConfigParam;
class RadarSignalProcessingNode : public hva::hvaNode_t{
public:

    RadarSignalProcessingNode(std::size_t totalThreadNum);

    virtual ~RadarSignalProcessingNode() override;
    
    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief To validate ModelPath in configure is not none.
    * @param void
    */
    // virtual hva::hvaStatus_t validateConfiguration() const override;

    /**
    * @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual hva::hvaStatus_t rearm() override;

    virtual hva::hvaStatus_t reset() override;

    // virtual hva::hvaStatus_t prepare();

private: 

    class Impl;
    std::unique_ptr<Impl> m_impl;
};

class RadarSignalProcessingNodeWorker : public hva::hvaNodeWorker_t{
public:
    RadarSignalProcessingNodeWorker(hva::hvaNode_t* parentNode, RadarConfigParam m_radar_config);

    virtual ~RadarSignalProcessingNodeWorker() override;

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

    virtual void init() override;

private:

    class Impl;
    std::unique_ptr<Impl> m_impl;
};



}

}

}
#endif /*__RADAR_SIGNAL_PROCESSING_NODE_H_*/
