/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#ifndef __POST_FUSION_OUTPUT_NODE_H_
#define __POST_FUSION_OUTPUT_NODE_H_

#include <boost/property_tree/json_parser.hpp>
#include <string>
#include <chrono>

#include "inc/api/hvaPipeline.hpp"
#include "inc/util/hvaConfigStringParser.hpp"
#include "inc/util/hvaUtil.hpp"
#include "nodes/base/baseResponseNode.hpp"
#include "modules/inference_util/fusion/data_fusion_helper_lidar.hpp"
#include "modules/tracklet_wrap.hpp"

namespace hce {

namespace ai {

namespace inference {

class HCE_AI_DECLSPEC LidarCamFusionOutputNode : public baseResponseNode {
  public:
    LidarCamFusionOutputNode(std::size_t totalThreadNum);

    ~LidarCamFusionOutputNode() = default;

    /**
     * @brief Constructs and returns a node worker instance:
     * LidarCamFusionOutputNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    virtual const std::string nodeClassName() const override
    {
        return "LidarCamFusionOutputNode";
    };

  private:
    hva::hvaConfigStringParser_t m_configParser;
};

class HCE_AI_DECLSPEC LidarCamFusionOutputNodeWorker : public baseResponseNodeWorker {
  public:
    LidarCamFusionOutputNodeWorker(hva::hvaNode_t *parentNode);

    virtual ~LidarCamFusionOutputNodeWorker();

    /**
     * @brief Called by hva framework for each frame, Run track-to-track
     * association and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

    virtual void processByLastRun(std::size_t batchIdx) override;

  private:
    template <typename T> void putVectorToJson(boost::property_tree::ptree &jsonTree, std::vector<T> content)
    {
        for (const T val : content) {
            boost::property_tree::ptree valTree;
            valTree.put("", val);
            jsonTree.push_back(std::make_pair("", valTree));
        }
    };
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif
