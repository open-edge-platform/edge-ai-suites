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

#include "nodes/CPU-backend/Camera2CFusionNode.hpp"

#include <sys/stat.h>

#include <cmath>
#include <opencv2/opencv.hpp>
#include <string>
#include <unordered_map>
#include <vector>

#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

class Camera2CFusionNode::Impl {
  public:
    Impl(Camera2CFusionNode &ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(Camera2CFusionNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    Camera2CFusionNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    std::string m_registrationMatrixFilePath;
    std::string m_qMatrixFilePath;
    std::string m_homographyMatrixFilePath;
    std::vector<int> m_pclConstraints;
    camera2CFusionInPortsInfo_t m_camera2CFusionInPortsInfo;
    int32_t m_inMediaNum;
};

Camera2CFusionNode::Impl::Impl(Camera2CFusionNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

Camera2CFusionNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t Camera2CFusionNode::Impl::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    std::string registrationMatrixFilePath;
    m_configParser.getVal<std::string>("registrationMatrixFilePath", registrationMatrixFilePath);
    if (registrationMatrixFilePath.empty()) {
        HVA_ERROR("Must define the registration matrix file path in config!");
        return hva::hvaFailure;
    }

    std::string qMatrixFilePath;
    m_configParser.getVal<std::string>("qMatrixFilePath", qMatrixFilePath);
    if (qMatrixFilePath.empty()) {
        HVA_ERROR("Must define the q matrix file path in config!");
        return hva::hvaFailure;
    }

    std::string homographyMatrixFilePath;
    m_configParser.getVal<std::string>("homographyMatrixFilePath", homographyMatrixFilePath);
    if (homographyMatrixFilePath.empty()) {
        HVA_ERROR("Must define the homography matrix file path in config!");
        return hva::hvaFailure;
    }

    std::vector<int> pclConstraints;
    m_configParser.getVal<std::vector<int>>("pclConstraints", pclConstraints);
    if (pclConstraints.empty()) {
        HVA_ERROR("Must define the hsv lower bound in config!");
        return hva::hvaFailure;
    }

    int inMediaNum = 2;
    m_configParser.getVal<int>("InMediaNum", inMediaNum);

    m_registrationMatrixFilePath = registrationMatrixFilePath;
    m_qMatrixFilePath = qMatrixFilePath;
    m_homographyMatrixFilePath = homographyMatrixFilePath;
    m_pclConstraints = pclConstraints;
    m_inMediaNum = inMediaNum;

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate Parameters in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t Camera2CFusionNode::Impl::validateConfiguration() const
{
    if (m_registrationMatrixFilePath.empty()) {
        HVA_ERROR("Empty registration matrix file path!");
        return hva::hvaFailure;
    }

    if (m_qMatrixFilePath.empty()) {
        HVA_ERROR("Empty Q matrix file path!");
        return hva::hvaFailure;
    }

    if (m_homographyMatrixFilePath.empty()) {
        HVA_ERROR("Empty homography matrix file path!");
        return hva::hvaFailure;
    }

    if (6 != m_pclConstraints.size()) {
        HVA_ERROR("Error pcl constraints, need 6 values(format [x_min, x_max, y_min, "
                  "y_max, z_min, z_max])!");
        return hva::hvaFailure;
    }

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
std::shared_ptr<hva::hvaNodeWorker_t> Camera2CFusionNode::Impl::createNodeWorker(Camera2CFusionNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new Camera2CFusionNodeWorker(
        parent, m_registrationMatrixFilePath, m_qMatrixFilePath, m_homographyMatrixFilePath, m_pclConstraints, m_inMediaNum, m_camera2CFusionInPortsInfo));
}

hva::hvaStatus_t Camera2CFusionNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t Camera2CFusionNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t Camera2CFusionNode::Impl::reset()
{
    return hva::hvaSuccess;
}

Camera2CFusionNode::Camera2CFusionNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(CAMERA_2CFUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{
}

Camera2CFusionNode::~Camera2CFusionNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t Camera2CFusionNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t Camera2CFusionNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> Camera2CFusionNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<Camera2CFusionNode *>(this));
}

hva::hvaStatus_t Camera2CFusionNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t Camera2CFusionNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t Camera2CFusionNode::prepare()
{
    return m_impl->prepare();
}

class Camera2CFusionNodeWorker::Impl {
  public:
    Impl(Camera2CFusionNodeWorker &ctx,
         const std::string &registrationMatrixFilePath,
         const std::string &qMatrixFilePath,
         const std::string &homographyMatrixFilePath,
         const std::vector<int> &pclConstraints,
         const int32_t &inMediaNum,
         const camera2CFusionInPortsInfo_t &camera2CFusionInPortsInfo);

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
    CoordinateTransformation m_coordsTrans;
    MultiCameraFuser m_multiCameraFuser;
    // std::unordered_map<unsigned, cv::Rect2f> historyBBox;
    Camera2CFusionNodeWorker &m_ctx;
    camera2CFusionInPortsInfo_t m_camera2CFusionInPortsInfo;
};

Camera2CFusionNodeWorker::Impl::Impl(Camera2CFusionNodeWorker &ctx,
                                     const std::string &registrationMatrixFilePath,
                                     const std::string &qMatrixFilePath,
                                     const std::string &homographyMatrixFilePath,
                                     const std::vector<int> &pclConstraints,
                                     const int32_t &inMediaNum,
                                     const camera2CFusionInPortsInfo_t &camera2CFusionInPortsInfo)
    : m_ctx(ctx), m_camera2CFusionInPortsInfo(camera2CFusionInPortsInfo)
{
    m_coordsTrans.setParameters(registrationMatrixFilePath, qMatrixFilePath, homographyMatrixFilePath, pclConstraints);
    m_multiCameraFuser.setNmsThreshold(0.5);
    for (int i = 0; i < inMediaNum; ++i) {
        m_multiCameraFuser.setTransformParams(homographyMatrixFilePath, i);
    }
}

Camera2CFusionNodeWorker::Impl::~Impl() {}

void Camera2CFusionNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run camera 2C fusion
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void Camera2CFusionNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < CAMERA_2CFUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != CAMERA_2CFUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("Camera2CFusion node received %d inputs at node %d, but expect to be: %d", vecBlobInput.size(), batchIdx,
                      CAMERA_2CFUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob1 = vecBlobInput[m_camera2CFusionInPortsInfo.fisrtMediaInputPort];
        hva::hvaBlob_t::Ptr cameraBlob2 = vecBlobInput[m_camera2CFusionInPortsInfo.secondMediaInputPort];
        hva::hvaBlob_t::Ptr radarBlob = vecBlobInput[m_camera2CFusionInPortsInfo.radarInputPort];
        HVA_ASSERT(cameraBlob1);
        HVA_ASSERT(cameraBlob2);
        HVA_ASSERT(radarBlob);

        std::shared_ptr<hva::timeStampInfo> camera2CFusionIn = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera2CFusionIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera2CFusionIn);

        HVA_DEBUG("Camera2CFusion node %d on frameId %d at port id: %d(Media 1); frameId %d at port id: %d(Media 2); frameId %d at port id: %d(Radar)",
                  batchIdx, cameraBlob1->frameId, m_camera2CFusionInPortsInfo.fisrtMediaInputPort, cameraBlob2->frameId,
                  m_camera2CFusionInPortsInfo.secondMediaInputPort, radarBlob->frameId, m_camera2CFusionInPortsInfo.radarInputPort);

        /**
         * process: media
         */
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf1 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob1->get(m_camera2CFusionInPortsInfo.fisrtMediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf1);
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf2 =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob2->get(m_camera2CFusionInPortsInfo.secondMediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf2);

        /**
         * process: radar
         */
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrRadarBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(radarBlob->get(m_camera2CFusionInPortsInfo.radarBlobBuffIndex));
        HVA_ASSERT(ptrRadarBuf);
        trackerOutput radarOutput;
        if (ptrRadarBuf->containMeta<trackerOutput>()) {
            // success
            ptrRadarBuf->getMeta<trackerOutput>(radarOutput);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of trackerOutput into hvabuf!");
        }

        // radarOutput contains all zero tracking results, filter it
        std::vector<trackerOutputDataType> filteredRadarOutput;
        for (const auto &item : radarOutput.outputInfo) {
            if (0 == item.S_hat[0] && 0 == item.S_hat[1] && 0 == item.xSize && 0 == item.ySize) {
                // all zero, useless data
            }
            else {
                filteredRadarOutput.push_back(item);
            }
        }

        /**
         * start processing
         */
        m_ctx.getLatencyMonitor().startRecording(cameraBlob1->frameId, "camera 2C fusion");
        int cameraSize1 = ptrFrameBuf1->rois.size();
        int cameraSize2 = ptrFrameBuf2->rois.size();
        int radarSize = filteredRadarOutput.size();
        HVA_DEBUG("Frame %d: cameraSize1(%d), cameraSize2(%d), radarSize(%d)", cameraBlob1->frameId, cameraSize1, cameraSize2, radarSize);


        HVA_DEBUG("fusion perform camera 2C fusion on frame%d", cameraBlob1->frameId);
        FusionOutput fusionOutput(2);

        // add radar output
        fusionOutput.setRadarOutput(filteredRadarOutput);

        // add camera output
        std::vector<BBox> cameraRadarCoords;
        for (const auto &item : ptrFrameBuf1->rois) {
            cv::Rect2i rect = cv::Rect2i(item.x, item.y, item.width, item.height);
            cv::Rect2f radarCoords = m_coordsTrans.pixel2Radar(rect);
            cameraRadarCoords.push_back(BBox(radarCoords.x, radarCoords.y, radarCoords.width, radarCoords.height));
        }
        fusionOutput.addCameraROI(0, ptrFrameBuf1->rois, cameraRadarCoords);

        std::vector<BBox>().swap(cameraRadarCoords);
        for (const auto &item : ptrFrameBuf2->rois) {
            cv::Rect2i rect = cv::Rect2i(item.x, item.y, item.width, item.height);
            cv::Rect2f radarCoords = m_coordsTrans.pixel2Radar(rect);
            cameraRadarCoords.push_back(BBox(radarCoords.x, radarCoords.y, radarCoords.width, radarCoords.height));
        }
        fusionOutput.addCameraROI(1, ptrFrameBuf2->rois, cameraRadarCoords);

        // add camera fusion result (in radar coordinate)
        std::vector<DetectedObject> fusionResult = m_multiCameraFuser.fuse2Camera(ptrFrameBuf1->rois, ptrFrameBuf2->rois);
        fusionOutput.setCameraFusionRadarCoords(fusionResult);

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

        ptrFrameBuf1->setMeta<FusionOutput>(fusionOutput);
        HVA_DEBUG("Camera2CFusionNode sending blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.sendOutput(cameraBlob1, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("Camera2CFusionNode completed sent blob with frameid %u and streamid %u", cameraBlob1->frameId, cameraBlob1->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob1->frameId, "camera 2C fusion");

        std::shared_ptr<hva::timeStampInfo> camera2CFusionOut = std::make_shared<hva::timeStampInfo>(cameraBlob1->frameId, "camera2CFusionOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &camera2CFusionOut);
    }
}

hva::hvaStatus_t Camera2CFusionNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t Camera2CFusionNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

Camera2CFusionNodeWorker::Camera2CFusionNodeWorker(hva::hvaNode_t *parentNode,
                                                   const std::string &registrationMatrixFilePath,
                                                   const std::string &qMatrixFilePath,
                                                   const std::string &homographyMatrixFilePath,
                                                   const std::vector<int> &pclConstraints,
                                                   const int32_t &inMediaNum,
                                                   const camera2CFusionInPortsInfo_t &camera2CFusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode),
      m_impl(new Impl(*this, registrationMatrixFilePath, qMatrixFilePath, homographyMatrixFilePath, pclConstraints, inMediaNum, camera2CFusionInPortsInfo))
{
}

Camera2CFusionNodeWorker::~Camera2CFusionNodeWorker() {}

void Camera2CFusionNodeWorker::init()
{
    return m_impl->init();
}

void Camera2CFusionNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(Camera2CFusionNode, Camera2CFusionNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce