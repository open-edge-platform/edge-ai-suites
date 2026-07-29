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

#ifndef __CAMEAR_2CFUSION_NODE_H_
#define __CAMEAR_2CFUSION_NODE_H_

#include "inc/api/hvaPipeline.hpp"
#include "inc/util/hvaConfigStringParser.hpp"
#include "inc/util/hvaUtil.hpp"
#include "modules/inference_util/fusion/data_fusion_helper.hpp"

#define CAMERA_2CFUSION_MODULE_INPORT_NUM 3

namespace hce {

namespace ai {

namespace inference {

struct camera2CFusionInPortsInfo_t
{
    int fisrtMediaInputPort = 0;       // in port index for fisrt media input
    int secondMediaInputPort = 1;      // in port index for second media input
    int radarInputPort = 2;            // in port index for radar input
    int fisrtMediaBlobBuffIndex = 0;   // buffer index in one blob
    int secondMediaBlobBuffIndex = 0;  // buffer index in one blob
    int radarBlobBuffIndex = 0;        // buffer index in one blob
};

class Camera2CFusionNode : public hva::hvaNode_t {
  public:
    Camera2CFusionNode(std::size_t totalThreadNum);

    virtual ~Camera2CFusionNode();

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
     * Camera2CFusionNodeWorker.
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

class Camera2CFusionNodeWorker : public hva::hvaNodeWorker_t {
  public:
    Camera2CFusionNodeWorker(hva::hvaNode_t *parentNode,
                             const std::string &registrationMatrixFilePath,
                             const std::string &qMatrixFilePath,
                             const std::string &homographyMatrixFilePath,
                             const std::vector<int> &pclConstraints,
                             const int32_t &inMediaNum,
                             const camera2CFusionInPortsInfo_t &camera2CFusionInPortsInfo);

    virtual ~Camera2CFusionNodeWorker();

    void init() override;

    virtual const std::string nodeClassName() const
    {
        return "Camera2CFusionNode";
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