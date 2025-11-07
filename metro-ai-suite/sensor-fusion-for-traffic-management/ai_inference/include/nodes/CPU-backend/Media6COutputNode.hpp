/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#ifndef HCE_AI_INF_MEDIA_6C_OUTPUT_NODE_HPP
#define HCE_AI_INF_MEDIA_6C_OUTPUT_NODE_HPP

#include <string>

#include <boost/property_tree/json_parser.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>

#include "nodes/radarDatabaseMeta.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "modules/tracklet_wrap.hpp"

#define MEDIA_6C_OUTPUT_NODE_INPORT_NUM 6

namespace hce {

namespace ai {

namespace inference {

class HCE_AI_DECLSPEC Media6COutputNodeWorker : public hva::hvaNodeWorker_t {
  public:
    Media6COutputNodeWorker(hva::hvaNode_t *parentNode, const std::string &bufType);

    virtual void process(std::size_t batchIdx) override;

    virtual void processByLastRun(std::size_t batchIdx) override;

  private:
    std::string m_bufType;

    template <typename T> void putVectorToJson(boost::property_tree::ptree &jsonTree, std::vector<T> content)
    {
        for (const T val : content) {
            boost::property_tree::ptree valTree;
            valTree.put("", val);
            jsonTree.push_back(std::make_pair("", valTree));
        }
    };
};

class HCE_AI_DECLSPEC Media6COutputNode : public baseResponseNode {
  public:
    Media6COutputNode(std::size_t totalThreadNum);

    ~Media6COutputNode() = default;

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    virtual hva::hvaStatus_t configureByString(const std::string &config) override;

    virtual const std::string nodeClassName() const override
    {
        return "Media2COutputNode";
    };

  private:
    std::string m_bufType;

    hva::hvaConfigStringParser_t m_configParser;
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_MEDIA_6C_OUTPUT_NODE_HPP