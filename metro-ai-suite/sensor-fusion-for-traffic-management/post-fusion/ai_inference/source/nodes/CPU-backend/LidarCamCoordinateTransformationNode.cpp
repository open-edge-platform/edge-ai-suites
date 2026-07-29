/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
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

#include "nodes/CPU-backend/LidarCamCoordinateTransformationNode.hpp"

#include <sys/stat.h>

#include <cmath>
#include <opencv2/opencv.hpp>
#include <string>
#include <unordered_map>
#include <vector>

#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "nodes/databaseMeta.hpp"
#include "nodes/lidarDatabaseMeta.hpp"
#include "modules/inference_util/fusion/data_fusion_helper_lidar.hpp"
#include "liblidar.hpp"

namespace hce {

namespace ai {

namespace inference {

class LidarCamCoordinateTransformationNode::Impl {
  public:
    Impl(LidarCamCoordinateTransformationNode &ctx);

    ~Impl();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     * @return hva status
     */
    virtual hva::hvaStatus_t configureByString(const std::string &config);

    /**
     * @brief To validate ModelPath in configure is not none.
     * @return hva status
     */
    virtual hva::hvaStatus_t validateConfiguration() const;

    /**
     * @brief Constructs and returns a node worker instance:
     * LocalMediaInputNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarCamCoordinateTransformationNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarCamCoordinateTransformationNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    CLFusionInPortsInfo_t m_fusionInPortsInfo;
};

LidarCamCoordinateTransformationNode::Impl::Impl(LidarCamCoordinateTransformationNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarCamCoordinateTransformationNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCamCoordinateTransformationNode::Impl::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    // in port index for media/lidar input
    m_configParser.getVal<int>("MediaPort", m_fusionInPortsInfo.mediaInputPort);
    m_configParser.getVal<int>("LidarPort", m_fusionInPortsInfo.lidarInputPort);
    if (m_fusionInPortsInfo.mediaInputPort >= CL_FUSION_MODULE_INPORT_NUM || m_fusionInPortsInfo.lidarInputPort >= CL_FUSION_MODULE_INPORT_NUM) {
        HVA_ERROR("In port index must be smaller than %d!", CL_FUSION_MODULE_INPORT_NUM);
        return hva::hvaFailure;
    }
    else if (m_fusionInPortsInfo.mediaInputPort == m_fusionInPortsInfo.lidarInputPort) {
        HVA_ERROR("In ports indices must be different for media and lidar!");
        return hva::hvaFailure;
    }

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCamCoordinateTransformationNode::Impl::validateConfiguration() const
{
    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCamCoordinateTransformationNode::Impl::createNodeWorker(LidarCamCoordinateTransformationNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LidarCamCoordinateTransformationNodeWorker(parent, m_fusionInPortsInfo));
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCamCoordinateTransformationNode::LidarCamCoordinateTransformationNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(CL_FUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{
}

LidarCamCoordinateTransformationNode::~LidarCamCoordinateTransformationNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCamCoordinateTransformationNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCamCoordinateTransformationNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCamCoordinateTransformationNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarCamCoordinateTransformationNode *>(this));
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t LidarCamCoordinateTransformationNode::prepare()
{
    return m_impl->prepare();
}

class LidarCamCoordinateTransformationNodeWorker::Impl {
  public:
    Impl(LidarCamCoordinateTransformationNodeWorker &ctx, const CLFusionInPortsInfo_t &fusionInPortsInfo);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run CL coordinate
     * transformation and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    LidarCamCoordinateTransformationNodeWorker &m_ctx;
    CLFusionInPortsInfo_t m_fusionInPortsInfo;
};

LidarCamCoordinateTransformationNodeWorker::Impl::Impl(LidarCamCoordinateTransformationNodeWorker &ctx, const CLFusionInPortsInfo_t &fusionInPortsInfo)
    : m_ctx(ctx), m_fusionInPortsInfo(fusionInPortsInfo)
{
    // TODO
}

LidarCamCoordinateTransformationNodeWorker::Impl::~Impl() {}

void LidarCamCoordinateTransformationNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run coordinate transformation
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarCamCoordinateTransformationNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < CL_FUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != CL_FUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("LidarCamCoordinateTransformation node received %d inputs at node %d, but "
                      "expect to be: %d",
                      vecBlobInput.size(), batchIdx, CL_FUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob = vecBlobInput[m_fusionInPortsInfo.mediaInputPort];
        hva::hvaBlob_t::Ptr lidarBlob = vecBlobInput[m_fusionInPortsInfo.lidarInputPort];
        HVA_ASSERT(cameraBlob);
        HVA_ASSERT(lidarBlob);
        std::shared_ptr<hva::timeStampInfo> coordinateTransIn = std::make_shared<hva::timeStampInfo>(cameraBlob->frameId, "LidarCamCoordinateTransIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &coordinateTransIn);

        HVA_DEBUG("LidarCamCoordinateTransformation node %d on frameId %d at port id: %d(Media); "
                  "frameId %d at port id: %d(Lidar)",
                  batchIdx, cameraBlob->frameId, m_fusionInPortsInfo.mediaInputPort, lidarBlob->frameId, m_fusionInPortsInfo.lidarInputPort);

        /**
         * process: media
         */
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob->get(m_fusionInPortsInfo.mediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf);

        /**
         * process: lidar
         */
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrLidarBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(lidarBlob->get(m_fusionInPortsInfo.lidarBlobBuffIndex));
        HVA_ASSERT(ptrLidarBuf);

        // inherit meta data from previous input field
        std::vector<pointpillars::ObjectDetection> lidarDetections = ptrLidarBuf->get<std::vector<pointpillars::ObjectDetection>>();
        CalibField_t calibContent;
        if (ptrLidarBuf->containMeta<CalibField_t>()) {
            // success
            ptrLidarBuf->getMeta<CalibField_t>(calibContent);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of CalibField_t into hvabuf!");
        }

        hce::ai::inference::LidarTimeStamp_t lidarTimeMeta;
        if (ptrLidarBuf->containMeta<hce::ai::inference::LidarTimeStamp_t>()) {
            // success
            ptrLidarBuf->getMeta(lidarTimeMeta);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of LidarTimeStamp_t into hvabuf!");
        }

        LidarCameraFusionOutput fusionOutput(1);

        CameraDetection2D fusedDetections;
        for (const auto &roi : ptrFrameBuf->rois) {
            fusedDetections.push_back(CameraDetectionObject(cv::Rect2f(roi.x, roi.y, roi.width, roi.height), roi.confidenceDetection, roi.labelDetection));
        }

        fusionOutput.setCameraDetections(0, ptrFrameBuf->rois);
        fusionOutput.setCameraCalib(calibContent);
        fusionOutput.setLidarDetections(lidarDetections);
        fusionOutput.setfusedCameraDetections(fusedDetections);
        fusionOutput.projectLidarBoxesToCameras(lidarDetections, calibContent);

        /**
         * start processing
         */
        m_ctx.getLatencyMonitor().startRecording(cameraBlob->frameId, "cl coord transformation");
        int cameraSize = ptrFrameBuf->rois.size();
        int lidarSize = lidarDetections.size();
        HVA_DEBUG("Frame %d: cameraSize(%d), lidarSize(%d)", cameraBlob->frameId, cameraSize, lidarSize);

        ptrFrameBuf->setMeta<LidarCameraFusionOutput>(fusionOutput);
        ptrFrameBuf->setMeta<hce::ai::inference::LidarTimeStamp_t>(lidarTimeMeta);

        HVA_DEBUG("LidarCamCoordinateTransformation sending blob with frameid %u and streamid %u", cameraBlob->frameId, cameraBlob->streamId);
        m_ctx.sendOutput(cameraBlob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("LidarCamCoordinateTransformation completed sent blob with frameid %u and streamid %u", cameraBlob->frameId, cameraBlob->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob->frameId, "cl coord transformation");

        std::shared_ptr<hva::timeStampInfo> coordinateTransOut = std::make_shared<hva::timeStampInfo>(cameraBlob->frameId, "LidarCamCoordinateTransOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &coordinateTransOut);
    }
}

hva::hvaStatus_t LidarCamCoordinateTransformationNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamCoordinateTransformationNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCamCoordinateTransformationNodeWorker::LidarCamCoordinateTransformationNodeWorker(hva::hvaNode_t *parentNode,
                                                                                       const CLFusionInPortsInfo_t &fusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, fusionInPortsInfo))
{
}

LidarCamCoordinateTransformationNodeWorker::~LidarCamCoordinateTransformationNodeWorker() {}

void LidarCamCoordinateTransformationNodeWorker::init()
{
    return m_impl->init();
}

void LidarCamCoordinateTransformationNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCamCoordinateTransformationNode, LidarCamCoordinateTransformationNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce