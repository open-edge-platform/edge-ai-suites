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

#ifndef HCE_AI_INF_MEDIA_RADAR_OUTPUT_NODE_HPP
#define HCE_AI_INF_MEDIA_RADAR_OUTPUT_NODE_HPP

#include <string>

#include <boost/property_tree/json_parser.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>

#include "nodes/radarDatabaseMeta.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "modules/tracklet_wrap.hpp"

#define MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM 2

namespace hce{

namespace ai{

namespace inference{

struct inPortsInfo_t {
    int mediaInputPort = 0;     // in port index for media input
    int radarInputPort = 1;     // in port index for radar input
};

class HCE_AI_DECLSPEC MediaRadarOutputNodeWorker : public hva::hvaNodeWorker_t{
public:
    MediaRadarOutputNodeWorker(hva::hvaNode_t* parentNode, inPortsInfo_t inPortsInfo);

    virtual void process(std::size_t batchIdx) override;

    virtual void processByLastRun(std::size_t batchIdx) override;

private:
    inPortsInfo_t m_inPortsInfo;
    template <typename T>
    void putVectorToJson(boost::property_tree::ptree& jsonTree, std::vector<T> content) {
        for (const T val : content) {
            boost::property_tree::ptree valTree;
            valTree.put("", val);
            jsonTree.push_back(std::make_pair("", valTree));
        }
    };
};

class HCE_AI_DECLSPEC MediaRadarOutputNode : public baseResponseNode{
public:

    MediaRadarOutputNode(std::size_t totalThreadNum);

    ~MediaRadarOutputNode() = default;

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    virtual const std::string nodeClassName() const override{ return "MediaRadarOutputNode";};

private:

    hva::hvaConfigStringParser_t m_configParser;
    inPortsInfo_t m_inPortsInfo;
};

}

}

}

#endif //#ifndef HCE_AI_INF_MEDIA_RADAR_OUTPUT_NODE_HPP