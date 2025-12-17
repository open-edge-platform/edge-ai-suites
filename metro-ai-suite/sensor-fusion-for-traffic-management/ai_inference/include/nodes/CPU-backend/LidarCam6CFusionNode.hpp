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

#ifndef __LIDAR_CAMERA_6CFUSION_NODE_H_
#define __LIDAR_CAMERA_6CFUSION_NODE_H_

#include "inc/api/hvaPipeline.hpp"
#include "inc/util/hvaConfigStringParser.hpp"
#include "inc/util/hvaUtil.hpp"
#include "modules/inference_util/fusion/data_fusion_helper_lidar.hpp"

#define LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM 7

namespace hce {

namespace ai {

namespace inference {

struct lidarCamera6CFusionInPortsInfo_t
{
    int mediaInputPorts[6] = {0, 1, 2, 3, 4, 5};     // in port index for media input
    int lidarInputPort = 6;                          // in port index for lidar input
    int mediaBlobBuffIndex[6] = {0, 0, 0, 0, 0, 0};  // buffer index for media blob
    int lidarBlobBuffIndex = 0;                      // buffer index for lidar blob
};

class LidarCam6CFusionNode : public hva::hvaNode_t {
  public:
    LidarCam6CFusionNode(std::size_t totalThreadNum);

    virtual ~LidarCam6CFusionNode();

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
     * LidarCam6CFusionNodeWorker.
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

class LidarCam6CFusionNodeWorker : public hva::hvaNodeWorker_t {
  public:
    LidarCam6CFusionNodeWorker(hva::hvaNode_t *parentNode, const int32_t &inMediaNum, const lidarCamera6CFusionInPortsInfo_t &lidarCamera6CFusionInPortsInfo);

    virtual ~LidarCam6CFusionNodeWorker();

    void init() override;

    virtual const std::string nodeClassName() const
    {
        return "LidarCam6CFusionNode";
    };

    /**
     * @brief Called by hva framework for each frame, Run camera
     * fusion and pass output to following node
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