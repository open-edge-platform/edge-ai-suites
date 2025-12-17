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

#include "nodes/CPU-backend/LidarCam2CFusionNode.hpp"

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

namespace hce {

namespace ai {

namespace inference {

class LidarCam2CFusionNode::Impl {
  public:
    Impl(LidarCam2CFusionNode &ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarCam2CFusionNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarCam2CFusionNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    lidarCamera2CFusionInPortsInfo_t m_lidarCamera2CFusionInPortsInfo;
    int32_t m_inMediaNum;
};

LidarCam2CFusionNode::Impl::Impl(LidarCam2CFusionNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarCam2CFusionNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam2CFusionNode::Impl::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    int inMediaNum = 2;
    m_configParser.getVal<int>("InMediaNum", inMediaNum);
    m_inMediaNum = inMediaNum;

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate Parameters in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam2CFusionNode::Impl::validateConfiguration() const
{
    if (2 > m_inMediaNum || 4 < m_inMediaNum) {
        HVA_ERROR("Error inMediaNum, need values 2, 3, or 4!");
        return hva::hvaFailure;
    }

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam2CFusionNode::Impl::createNodeWorker(LidarCam2CFusionNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LidarCam2CFusionNodeWorker(parent, m_inMediaNum, m_lidarCamera2CFusionInPortsInfo));
}

hva::hvaStatus_t LidarCam2CFusionNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam2CFusionNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam2CFusionNode::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam2CFusionNode::LidarCam2CFusionNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(LIDAR_CAMERA_2CFUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{
}

LidarCam2CFusionNode::~LidarCam2CFusionNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam2CFusionNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam2CFusionNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam2CFusionNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarCam2CFusionNode *>(this));
}

hva::hvaStatus_t LidarCam2CFusionNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarCam2CFusionNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t LidarCam2CFusionNode::prepare()
{
    return m_impl->prepare();
}

class LidarCam2CFusionNodeWorker::Impl {
  public:
    Impl(LidarCam2CFusionNodeWorker &ctx, const int32_t &inMediaNum, const lidarCamera2CFusionInPortsInfo_t &lidarCamera2CFusionInPortsInfo);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run camera
     * fusion and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    LidarCameraMultiCameraFuser m_multiCameraFuser;
    LidarCam2CFusionNodeWorker &m_ctx;
    lidarCamera2CFusionInPortsInfo_t m_lidarCamera2CFusionInPortsInfo;
};

LidarCam2CFusionNodeWorker::Impl::Impl(LidarCam2CFusionNodeWorker &ctx,
                                       const int32_t &inMediaNum,
                                       const lidarCamera2CFusionInPortsInfo_t &lidarCamera2CFusionInPortsInfo)
    : m_ctx(ctx), m_lidarCamera2CFusionInPortsInfo(lidarCamera2CFusionInPortsInfo)
{
    m_multiCameraFuser.setNmsThreshold(0.5);
}

LidarCam2CFusionNodeWorker::Impl::~Impl() {}

void LidarCam2CFusionNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run camera 2C fusion
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarCam2CFusionNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < LIDAR_CAMERA_2CFUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != LIDAR_CAMERA_2CFUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("Camera2CFusion node received %d inputs at node %d, but expect to be: %d", vecBlobInput.size(), batchIdx,
                      LIDAR_CAMERA_2CFUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob1 = vecBlobInput[m_lidarCamera2CFusionInPortsInfo.firstMediaInputPort];
        hva::hvaBlob_t::Ptr cameraBlob2 = vecBlobInput[m_lidarCamera2CFusionInPortsInfo.secondMediaInputPort];
        hva::hvaBlob_t::Ptr lidarBlob = vecBlobInput[m_lidarCamera2CFusionInPortsInfo.lidarInputPort];
        HVA_ASSERT(cameraBlob1);
        HVA_ASSERT(cameraBlob2);
        HVA_ASSERT(lidarBlob);

        std::shared_ptr<hva::timeStampInfo> camera2CFusionIn = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera2CFusionIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera2CFusionIn);

        HVA_DEBUG("LidarCamera2CFusion node %d on frameId %d at port id: %d(Media 1); frameId %d at port id: %d(Media 2); frameId %d at port id: %d(Lidar)",
                  batchIdx, cameraBlob1->frameId, m_lidarCamera2CFusionInPortsInfo.firstMediaInputPort, cameraBlob2->frameId,
                  m_lidarCamera2CFusionInPortsInfo.secondMediaInputPort, lidarBlob->frameId, m_lidarCamera2CFusionInPortsInfo.lidarInputPort);

        /**
         * process: media
         */
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf1 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob1->get(m_lidarCamera2CFusionInPortsInfo.firstMediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf1);
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf2 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob2->get(m_lidarCamera2CFusionInPortsInfo.secondMediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf2);

        /**
         * process: lidar
         */
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrLidarBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(lidarBlob->get(m_lidarCamera2CFusionInPortsInfo.lidarBlobBuffIndex));
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

        /**
         * start processing
         */
        m_ctx.getLatencyMonitor().startRecording(cameraBlob1->frameId, "camera 2C fusion");
        int cameraSize1 = ptrFrameBuf1->rois.size();
        int cameraSize2 = ptrFrameBuf2->rois.size();
        int lidarSize = lidarDetections.size();
        HVA_DEBUG("Frame %d: cameraSize1(%d), cameraSize2(%d), lidarSize(%d)", cameraBlob1->frameId, cameraSize1, cameraSize2, lidarSize);


        HVA_DEBUG("fusion perform camera 2C fusion on frame%d", cameraBlob1->frameId);
        LidarCameraFusionOutput fusionOutput(LIDAR_CAMERA_2CFUSION_MODULE_INPORT_NUM - 1);

        CameraDetection2D fusedDetections;
        std::vector<std::vector<hva::hvaROI_t>> allDets;
        allDets.push_back(ptrFrameBuf1->rois);
        allDets.push_back(ptrFrameBuf2->rois);
        fusedDetections = m_multiCameraFuser.fuseCameraDetections(allDets);

        fusionOutput.setCameraDetections(0, ptrFrameBuf1->rois);
        fusionOutput.setCameraDetections(1, ptrFrameBuf2->rois);
        fusionOutput.setCameraCalib(calibContent);
        fusionOutput.setLidarDetections(lidarDetections);
        fusionOutput.setfusedCameraDetections(fusedDetections);
        fusionOutput.projectLidarBoxesToCameras(lidarDetections, calibContent);


        TimeStampAll_t timeMetaAll;
        TimeStamp_t timeMeta;
        if (ptrFrameBuf1->getMeta(timeMeta) == hva::hvaSuccess) {
            timeMetaAll.timeStamp[0] = timeMeta.timeStamp;
        }
        if (ptrFrameBuf2->getMeta(timeMeta) == hva::hvaSuccess) {
            timeMetaAll.timeStamp[1] = timeMeta.timeStamp;
        }
        ptrFrameBuf1->setMeta<TimeStampAll_t>(timeMetaAll);

        InferenceTimeStamp_t inferenceTimeMeta;
        InferenceTimeAll_t inferenceTimeMetaAll;
        if (ptrFrameBuf1->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceTimeMetaAll.inferenceLatencies[0] =
                std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        if (ptrFrameBuf2->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceTimeMetaAll.inferenceLatencies[1] =
                std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        ptrFrameBuf1->setMeta<InferenceTimeAll_t>(inferenceTimeMetaAll);

        VideoTimeStamp_t videoTimeMeta;
        VideoTimeAll_t videoTimeMetaAll;
        if (ptrFrameBuf1->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoTimeMetaAll.videoLatencies[0] = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }
        if (ptrFrameBuf2->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoTimeMetaAll.videoLatencies[1] = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }
        ptrFrameBuf1->setMeta<VideoTimeAll_t>(videoTimeMetaAll);

        ptrFrameBuf1->setMeta<LidarCameraFusionOutput>(fusionOutput);
        ptrFrameBuf1->setMeta<hce::ai::inference::LidarTimeStamp_t>(lidarTimeMeta);

        HVA_DEBUG("LidarCam2CFusionNode sending blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.sendOutput(cameraBlob1, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("LidarCam2CFusionNode completed sent blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob1->frameId, "camera 2C fusion");

        std::shared_ptr<hva::timeStampInfo> camera2CFusionOut = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera2CFusionOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera2CFusionOut);
    }
}

hva::hvaStatus_t LidarCam2CFusionNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam2CFusionNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam2CFusionNodeWorker::LidarCam2CFusionNodeWorker(hva::hvaNode_t *parentNode,
                                                       const int32_t &inMediaNum,
                                                       const lidarCamera2CFusionInPortsInfo_t &lidarCamera2CFusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, inMediaNum, lidarCamera2CFusionInPortsInfo))
{
}

LidarCam2CFusionNodeWorker::~LidarCam2CFusionNodeWorker() {}

void LidarCam2CFusionNodeWorker::init()
{
    return m_impl->init();
}

void LidarCam2CFusionNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCam2CFusionNode, LidarCam2CFusionNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce