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

#ifndef HCE_AI_INF_RADAR_DETECTION_OUTPUT_NODE_HPP
#define HCE_AI_INF_RADAR_DETECTION_OUTPUT_NODE_HPP

#include <string>

#include <boost/property_tree/json_parser.hpp>

#include <inc/util/hvaConfigStringParser.hpp>

#include "nodes/base/baseResponseNode.hpp"
#include "modules/inference_util/radar/radar_detection_helper.hpp"

namespace hce{

namespace ai{

namespace inference{

class HCE_AI_DECLSPEC RadarDetectionOutputNodeWorker : public hva::hvaNodeWorker_t{
public:
    RadarDetectionOutputNodeWorker(hva::hvaNode_t* parentNode, const std::string& bufType);

    virtual void process(std::size_t batchIdx) override;

    virtual void processByLastRun(std::size_t batchIdx) override;
private:
    boost::property_tree::ptree m_jsonTree;
    boost::property_tree::ptree m_roi, m_rois;
    boost::property_tree::ptree m_roiData;
    boost::property_tree::ptree m_x, m_y, m_w, m_h;

    std::string m_bufType;
};

class HCE_AI_DECLSPEC RadarDetectionOutputNode : public baseResponseNode{
public:

    RadarDetectionOutputNode(std::size_t totalThreadNum);

    ~RadarDetectionOutputNode() = default;

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    virtual const std::string nodeClassName() const override{ return "RadarDetectionOutputNode";};

private: 
    std::string m_bufType;

    hva::hvaConfigStringParser_t m_configParser;
};

}

}

}

#endif //#ifndef HCE_AI_INF_RADAR_DETECTION_OUTPUT_NODE_HPP