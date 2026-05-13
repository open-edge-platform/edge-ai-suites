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

#ifndef __TRACK2TRACK_ASSOCIATION_NODE_H_
#define __TRACK2TRACK_ASSOCIATION_NODE_H_

#include "inc/api/hvaPipeline.hpp"
#include "inc/util/hvaConfigStringParser.hpp"
#include "inc/util/hvaUtil.hpp"

namespace hce {

namespace ai {

namespace inference {

class Track2TrackAssociationNode : public hva::hvaNode_t {
  public:
    Track2TrackAssociationNode(std::size_t totalThreadNum);

    virtual ~Track2TrackAssociationNode();

    /**
     * @brief Constructs and returns a node worker instance:
     * Track2TrackAssociationNodeWorker.
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

class Track2TrackAssociationNodeWorker : public hva::hvaNodeWorker_t {
  public:
    Track2TrackAssociationNodeWorker(hva::hvaNode_t *parentNode);

    virtual ~Track2TrackAssociationNodeWorker();

    void init() override;

    virtual const std::string nodeClassName() const
    {
        return "Track2TrackAssociationNode";
    };

    /**
     * @brief Called by hva framework for each frame, Run track-to-track
     * association and pass output to following node
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