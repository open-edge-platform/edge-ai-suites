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

#ifndef __RADAR_CLUSTERING_NODE_H_
#define __RADAR_CLUSTERING_NODE_H_

#include "inc/api/hvaPipeline.hpp"
#include "inc/util/hvaConfigStringParser.hpp"
#include "inc/util/hvaUtil.hpp"
#include "modules/inference_util/radar/radar_clustering_helper.hpp"
// #include "modules/inference_util/radar/radar_detection_helper.hpp"

namespace hce {

namespace ai {

namespace inference {

class RadarClusteringNode : public hva::hvaNode_t {
  public:
    RadarClusteringNode(std::size_t totalThreadNum);

    virtual ~RadarClusteringNode();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     * @return hva status
     */
    virtual hva::hvaStatus_t configureByString(const std::string &config) override;

    /**
     * @brief To validate ModelPath in configure is not none.
     * @return hva status
     */
    virtual hva::hvaStatus_t validateConfiguration() const override;

    /**
     * @brief Constructs and returns a node worker instance:
     * RadarClusteringNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    virtual hva::hvaStatus_t rearm() override;

    virtual hva::hvaStatus_t reset() override;

    virtual hva::hvaStatus_t prepare() override;

  private:
    class Impl;
    std::unique_ptr<Impl> m_impl;
};

class RadarClusteringNodeWorker : public hva::hvaNodeWorker_t {
  public:
    RadarClusteringNodeWorker(hva::hvaNode_t *parentNode);

    virtual ~RadarClusteringNodeWorker();

    void init() override;

    virtual const std::string nodeClassName() const
    {
        return "RadarClusteringNodeWorker";
    };

    /**
     * @brief Called by hva framework for each frame, Run radar clustering and
     * pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

  private:
    class Impl;
    std::unique_ptr<Impl> m_impl;
};


}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif