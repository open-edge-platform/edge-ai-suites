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

#include "nodes/CPU-backend/LidarCam6CFusionNode.hpp"

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

class LidarCam6CFusionNode::Impl {
  public:
    Impl(LidarCam6CFusionNode &ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarCam6CFusionNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarCam6CFusionNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    lidarCamera6CFusionInPortsInfo_t m_lidarCamera6CFusionInPortsInfo;
    int32_t m_inMediaNum;
};

LidarCam6CFusionNode::Impl::Impl(LidarCam6CFusionNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarCam6CFusionNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam6CFusionNode::Impl::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    int inMediaNum = 6;
    m_configParser.getVal<int>("InMediaNum", inMediaNum);
    m_inMediaNum = inMediaNum;

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate Parameters in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam6CFusionNode::Impl::validateConfiguration() const
{
    if (6 != m_inMediaNum) {
        HVA_ERROR("Error inMediaNum, need values 6!");
        return hva::hvaFailure;
    }

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam6CFusionNode::Impl::createNodeWorker(LidarCam6CFusionNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LidarCam6CFusionNodeWorker(parent, m_inMediaNum, m_lidarCamera6CFusionInPortsInfo));
}

hva::hvaStatus_t LidarCam6CFusionNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam6CFusionNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam6CFusionNode::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam6CFusionNode::LidarCam6CFusionNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{
}

LidarCam6CFusionNode::~LidarCam6CFusionNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam6CFusionNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam6CFusionNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam6CFusionNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarCam6CFusionNode *>(this));
}

hva::hvaStatus_t LidarCam6CFusionNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarCam6CFusionNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t LidarCam6CFusionNode::prepare()
{
    return m_impl->prepare();
}

class LidarCam6CFusionNodeWorker::Impl {
  public:
    Impl(LidarCam6CFusionNodeWorker &ctx, const int32_t &inMediaNum, const lidarCamera6CFusionInPortsInfo_t &lidarCamera6CFusionInPortsInfo);

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
    LidarCam6CFusionNodeWorker &m_ctx;
    lidarCamera6CFusionInPortsInfo_t m_lidarCamera6CFusionInPortsInfo;
};

LidarCam6CFusionNodeWorker::Impl::Impl(LidarCam6CFusionNodeWorker &ctx,
                                       const int32_t &inMediaNum,
                                       const lidarCamera6CFusionInPortsInfo_t &lidarCamera6CFusionInPortsInfo)
    : m_ctx(ctx), m_lidarCamera6CFusionInPortsInfo(lidarCamera6CFusionInPortsInfo)
{
    m_multiCameraFuser.setNmsThreshold(0.5);
}

LidarCam6CFusionNodeWorker::Impl::~Impl() {}

void LidarCam6CFusionNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run camera 6C fusion
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarCam6CFusionNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("Camera6CFusion node received %d inputs at node %d, but expect to be: %d", vecBlobInput.size(), batchIdx,
                      LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob1 = vecBlobInput[m_lidarCamera6CFusionInPortsInfo.mediaInputPorts[0]];
        hva::hvaBlob_t::Ptr lidarBlob = vecBlobInput[m_lidarCamera6CFusionInPortsInfo.lidarInputPort];
        HVA_ASSERT(cameraBlob1);
        HVA_ASSERT(lidarBlob);

        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf1 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob1->get(m_lidarCamera6CFusionInPortsInfo.mediaBlobBuffIndex[0]));
        HVA_ASSERT(ptrFrameBuf1);

        std::shared_ptr<hva::timeStampInfo> camera6CFusionIn = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera6CFusionIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera6CFusionIn);


        /**
         * start processing
         */
        m_ctx.getLatencyMonitor().startRecording(cameraBlob1->frameId, "camera 6C fusion");

        LidarCameraFusionOutput fusionOutput(LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM - 1);
        std::vector<std::vector<hva::hvaROI_t>> allDets;
        CameraDetection2D fusedDetections;
        TimeStampAll_t timeMetaAll;
        TimeStamp_t timeMeta;
        InferenceTimeStamp_t inferenceTimeMeta;
        InferenceTimeAll_t inferenceTimeMetaAll;
        VideoTimeStamp_t videoTimeMeta;
        VideoTimeAll_t videoTimeMetaAll;


        allDets.push_back(ptrFrameBuf1->rois);
        fusionOutput.setCameraDetections(0, ptrFrameBuf1->rois);
        if (ptrFrameBuf1->getMeta(timeMeta) == hva::hvaSuccess) {
            timeMetaAll.timeStamp[0] = timeMeta.timeStamp;
        }
        if (ptrFrameBuf1->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceTimeMetaAll.inferenceLatencies[0] =
                std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        if (ptrFrameBuf1->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoTimeMetaAll.videoLatencies[0] = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }

        for (int i = 1; i < LIDAR_CAMERA_6CFUSION_MODULE_INPORT_NUM - 1; i++) {
            hva::hvaBlob_t::Ptr cameraBlob = vecBlobInput[m_lidarCamera6CFusionInPortsInfo.mediaInputPorts[i]];
            HVA_ASSERT(cameraBlob);
            HVA_DEBUG("LidarCamera6CFusion node %d on frameId %d at port id: %d(Media %d)", batchIdx, cameraBlob->frameId,
                      m_lidarCamera6CFusionInPortsInfo.mediaInputPorts[i], i + 1);

            /**
             * process: media
             */
            hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf =
                std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob->get(m_lidarCamera6CFusionInPortsInfo.mediaBlobBuffIndex[i]));
            int cameraSize = ptrFrameBuf->rois.size();
            HVA_DEBUG("Frame %d: cameraSize(%d)", cameraBlob->frameId, cameraSize);

            allDets.push_back(ptrFrameBuf->rois);
            fusionOutput.setCameraDetections(i, ptrFrameBuf->rois);

            if (ptrFrameBuf->getMeta(timeMeta) == hva::hvaSuccess) {
                timeMetaAll.timeStamp[i] = timeMeta.timeStamp;
            }
            if (ptrFrameBuf->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
                inferenceTimeMetaAll.inferenceLatencies[i] =
                    std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
            }
            if (ptrFrameBuf->getMeta(videoTimeMeta) == hva::hvaSuccess) {
                videoTimeMetaAll.videoLatencies[i] = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
            }
        }


        /**
         * process: lidar
         */
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrLidarBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(lidarBlob->get(m_lidarCamera6CFusionInPortsInfo.lidarBlobBuffIndex));
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

        HVA_DEBUG("fusion perform camera 6C fusion on frame%d", cameraBlob1->frameId);
        fusedDetections = m_multiCameraFuser.fuseCameraDetections(allDets);
        fusionOutput.setCameraCalib(calibContent);
        fusionOutput.setLidarDetections(lidarDetections);
        fusionOutput.setfusedCameraDetections(fusedDetections);
        fusionOutput.projectLidarBoxesToCameras(lidarDetections, calibContent);

        ptrFrameBuf1->setMeta<TimeStampAll_t>(timeMetaAll);
        ptrFrameBuf1->setMeta<InferenceTimeAll_t>(inferenceTimeMetaAll);
        ptrFrameBuf1->setMeta<VideoTimeAll_t>(videoTimeMetaAll);
        ptrFrameBuf1->setMeta<LidarCameraFusionOutput>(fusionOutput);
        ptrFrameBuf1->setMeta<hce::ai::inference::LidarTimeStamp_t>(lidarTimeMeta);

        HVA_DEBUG("LidarCam6CFusionNode sending blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.sendOutput(cameraBlob1, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("LidarCam6CFusionNode completed sent blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob1->frameId, "camera 6C fusion");

        std::shared_ptr<hva::timeStampInfo> camera6CFusionOut = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera6CFusionOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera6CFusionOut);
    }
}

hva::hvaStatus_t LidarCam6CFusionNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam6CFusionNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam6CFusionNodeWorker::LidarCam6CFusionNodeWorker(hva::hvaNode_t *parentNode,
                                                       const int32_t &inMediaNum,
                                                       const lidarCamera6CFusionInPortsInfo_t &lidarCamera6CFusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, inMediaNum, lidarCamera6CFusionInPortsInfo))
{
}

LidarCam6CFusionNodeWorker::~LidarCam6CFusionNodeWorker() {}

void LidarCam6CFusionNodeWorker::init()
{
    return m_impl->init();
}

void LidarCam6CFusionNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCam6CFusionNode, LidarCam6CFusionNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce