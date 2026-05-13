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

#include "nodes/CPU-backend/LidarCam4CFusionNode.hpp"

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

class LidarCam4CFusionNode::Impl {
  public:
    Impl(LidarCam4CFusionNode &ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarCam4CFusionNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarCam4CFusionNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    lidarCamera4CFusionInPortsInfo_t m_lidarCamera4CFusionInPortsInfo;
    int32_t m_inMediaNum;
};

LidarCam4CFusionNode::Impl::Impl(LidarCam4CFusionNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarCam4CFusionNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam4CFusionNode::Impl::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    int inMediaNum = 4;
    m_configParser.getVal<int>("InMediaNum", inMediaNum);
    m_inMediaNum = inMediaNum;

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate Parameters in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam4CFusionNode::Impl::validateConfiguration() const
{
    if (4 != m_inMediaNum) {
        HVA_ERROR("Error inMediaNum, need values 4!");
        return hva::hvaFailure;
    }

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam4CFusionNode::Impl::createNodeWorker(LidarCam4CFusionNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LidarCam4CFusionNodeWorker(parent, m_inMediaNum, m_lidarCamera4CFusionInPortsInfo));
}

hva::hvaStatus_t LidarCam4CFusionNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam4CFusionNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam4CFusionNode::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam4CFusionNode::LidarCam4CFusionNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{
}

LidarCam4CFusionNode::~LidarCam4CFusionNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t LidarCam4CFusionNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t LidarCam4CFusionNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCam4CFusionNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarCam4CFusionNode *>(this));
}

hva::hvaStatus_t LidarCam4CFusionNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarCam4CFusionNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t LidarCam4CFusionNode::prepare()
{
    return m_impl->prepare();
}

class LidarCam4CFusionNodeWorker::Impl {
  public:
    Impl(LidarCam4CFusionNodeWorker &ctx, const int32_t &inMediaNum, const lidarCamera4CFusionInPortsInfo_t &lidarCamera4CFusionInPortsInfo);

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
    LidarCam4CFusionNodeWorker &m_ctx;
    lidarCamera4CFusionInPortsInfo_t m_lidarCamera4CFusionInPortsInfo;
};

LidarCam4CFusionNodeWorker::Impl::Impl(LidarCam4CFusionNodeWorker &ctx,
                                       const int32_t &inMediaNum,
                                       const lidarCamera4CFusionInPortsInfo_t &lidarCamera4CFusionInPortsInfo)
    : m_ctx(ctx), m_lidarCamera4CFusionInPortsInfo(lidarCamera4CFusionInPortsInfo)
{
    m_multiCameraFuser.setNmsThreshold(0.5);
}

LidarCam4CFusionNodeWorker::Impl::~Impl() {}

void LidarCam4CFusionNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run camera 3C fusion
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarCam4CFusionNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("Camera3CFusion node received %d inputs at node %d, but expect to be: %d", vecBlobInput.size(), batchIdx,
                      LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob1 = vecBlobInput[m_lidarCamera4CFusionInPortsInfo.mediaInputPorts[0]];
        hva::hvaBlob_t::Ptr lidarBlob = vecBlobInput[m_lidarCamera4CFusionInPortsInfo.lidarInputPort];
        HVA_ASSERT(cameraBlob1);
        HVA_ASSERT(lidarBlob);

        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf1 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob1->get(m_lidarCamera4CFusionInPortsInfo.mediaBlobBuffIndex[0]));
        HVA_ASSERT(ptrFrameBuf1);

        std::shared_ptr<hva::timeStampInfo> camera3CFusionIn = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera3CFusionIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera3CFusionIn);


        /**
         * start processing
         */
        m_ctx.getLatencyMonitor().startRecording(cameraBlob1->frameId, "camera 3C fusion");

        LidarCameraFusionOutput fusionOutput(LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM - 1);
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

        for (int i = 1; i < LIDAR_CAMERA_4CFUSION_MODULE_INPORT_NUM - 1; i++) {
            hva::hvaBlob_t::Ptr cameraBlob = vecBlobInput[m_lidarCamera4CFusionInPortsInfo.mediaInputPorts[i]];
            HVA_ASSERT(cameraBlob);
            HVA_DEBUG("LidarCamera4CFusion node %d on frameId %d at port id: %d(Media %d)", batchIdx, cameraBlob->frameId,
                      m_lidarCamera4CFusionInPortsInfo.mediaInputPorts[i], i + 1);

            /**
             * process: media
             */
            hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf =
                std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob->get(m_lidarCamera4CFusionInPortsInfo.mediaBlobBuffIndex[i]));
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
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(lidarBlob->get(m_lidarCamera4CFusionInPortsInfo.lidarBlobBuffIndex));
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

        HVA_DEBUG("fusion perform camera 3C fusion on frame%d", cameraBlob1->frameId);
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

        HVA_DEBUG("LidarCam4CFusionNode sending blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.sendOutput(cameraBlob1, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("LidarCam4CFusionNode completed sent blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob1->frameId, "camera 3C fusion");

        std::shared_ptr<hva::timeStampInfo> camera3CFusionOut = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera3CFusionOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera3CFusionOut);
    }
}

hva::hvaStatus_t LidarCam4CFusionNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCam4CFusionNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

LidarCam4CFusionNodeWorker::LidarCam4CFusionNodeWorker(hva::hvaNode_t *parentNode,
                                                       const int32_t &inMediaNum,
                                                       const lidarCamera4CFusionInPortsInfo_t &lidarCamera4CFusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, inMediaNum, lidarCamera4CFusionInPortsInfo))
{
}

LidarCam4CFusionNodeWorker::~LidarCam4CFusionNodeWorker() {}

void LidarCam4CFusionNodeWorker::init()
{
    return m_impl->init();
}

void LidarCam4CFusionNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCam4CFusionNode, LidarCam4CFusionNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce