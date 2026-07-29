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

#ifndef __LIDAR_CAM_FUSION_INPUT_NODE_H_
#define __LIDAR_CAM_FUSION_INPUT_NODE_H_

#include <string>

// #include <boost/filesystem.hpp>
#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include <unordered_map>

#include "nodes/databaseMeta.hpp"
#include "nodes/lidarDatabaseMeta.hpp"

#define DEFAULT_MULTI_SENSOR_INPUT_NUM 3

namespace hce {

namespace ai {

namespace inference {

struct MultiSensorField_t
{
    std::string imageContent;
    size_t imageSize = 0;
    lidarVec_t lidarContent;
    size_t lidarSize = 0;
};

class LidarCamFusionInputNode : public hva::hvaNode_t {
  public:
    struct InpustSensorIndices_t
    {
        int mediaIndex = -1;  // output port index for media input
        int lidarIndex = -1;  // output port index for lidar input
        int calibIndex = -1;  // output port index for calib input
    };

    LidarCamFusionInputNode(std::size_t totalThreadNum);

    ~LidarCamFusionInputNode() = default;

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     */
    virtual hva::hvaStatus_t configureByString(const std::string &config) override;

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    virtual const std::string nodeClassName() const override
    {
        return "LidarCamFusionInputNode";
    };

  private:
    hva::hvaConfigStringParser_t m_configParser;
    std::string m_dataSource;

    InpustSensorIndices_t m_sensorIndices;
    size_t m_inputCapacity;
    size_t m_stride;
    float m_frameRate;
    std::string m_controlType;
    std::string m_sensorType;
};

class LidarCamFusionInputNodeWorker : public hva::hvaNodeWorker_t {
  public:
    LidarCamFusionInputNodeWorker(hva::hvaNode_t *parentNode,
                                  const LidarCamFusionInputNode::InpustSensorIndices_t &sensorIndices,
                                  const size_t &inputCapacity,
                                  const size_t &stride,
                                  const float &frameRate,
                                  const std::string &controlType,
                                  const std::string &sensorType);

    virtual void process(std::size_t batchIdx) override;

    /**
     * @brief Frame index increased for every coming frame, will be called at the process()
     * @param void
     */
    unsigned fetch_increment();

    /**
     * @brief Send empty buf for blob
     * @param blob input blob data with empty buf
     * @param isEnd flag for coming request
     * @param meta databaseMeta
     */
    void sendEmptyBlob(hva::hvaBlob_t::Ptr blob, bool isEnd, const HceDatabaseMeta &meta);

  private:
    LidarCamFusionInputNode::InpustSensorIndices_t m_sensorIndices;
    size_t m_inputCapacity;
    size_t m_stride;
    std::atomic<unsigned> m_ctr;
    std::unordered_map<int, SendController::Ptr> m_controllerMap;
    float m_frameRate;
    std::string m_controlType;
    std::string m_sensorType;
    int m_workStreamId;
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef __LIDAR_CAM_FUSION_INPUT_NODE_H_
