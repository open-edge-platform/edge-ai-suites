/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2025 Intel Corporation.
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

#include "nodes/CPU-backend/CoordinateTransformationNode.hpp"

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

class CoordinateTransformationNode::Impl {
  public:
    Impl(CoordinateTransformationNode &ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(CoordinateTransformationNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    CoordinateTransformationNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
    std::string m_registrationMatrixFilePath;
    std::string m_qMatrixFilePath;
    std::string m_homographyMatrixFilePath;
    std::vector<int> m_pclConstraints;
    fusionInPortsInfo_t m_fusionInPortsInfo;
};

CoordinateTransformationNode::Impl::Impl(CoordinateTransformationNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

CoordinateTransformationNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t CoordinateTransformationNode::Impl::configureByString(const std::string &config)
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

    // in port index for media/radar input
    m_configParser.getVal<int>("MediaPort", m_fusionInPortsInfo.mediaInputPort);
    m_configParser.getVal<int>("RadarPort", m_fusionInPortsInfo.radarInputPort);
    if (m_fusionInPortsInfo.mediaInputPort >= FUSION_MODULE_INPORT_NUM || m_fusionInPortsInfo.radarInputPort >= FUSION_MODULE_INPORT_NUM) {
        HVA_ERROR("In port index must be smaller than %d!", FUSION_MODULE_INPORT_NUM);
        return hva::hvaFailure;
    }
    else if (m_fusionInPortsInfo.mediaInputPort == m_fusionInPortsInfo.radarInputPort) {
        HVA_ERROR("In ports indices must be different for media and radar!");
        return hva::hvaFailure;
    }

    // buffer index for each media/radar blob
    // m_configParser.getVal<int>("MediaBlobBuffIndex", m_fusionInPortsInfo.mediaBlobBuffIndex);
    // m_configParser.getVal<int>("RadarBlobBuffIndex", m_fusionInPortsInfo.radarBlobBuffIndex);

    m_registrationMatrixFilePath = registrationMatrixFilePath;
    m_qMatrixFilePath = qMatrixFilePath;
    m_homographyMatrixFilePath = homographyMatrixFilePath;
    m_pclConstraints = pclConstraints;

    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t CoordinateTransformationNode::Impl::validateConfiguration() const
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

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> CoordinateTransformationNode::Impl::createNodeWorker(CoordinateTransformationNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new CoordinateTransformationNodeWorker(parent, m_registrationMatrixFilePath, m_qMatrixFilePath,
                                                                                        m_homographyMatrixFilePath, m_pclConstraints, m_fusionInPortsInfo));
}

hva::hvaStatus_t CoordinateTransformationNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t CoordinateTransformationNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t CoordinateTransformationNode::Impl::reset()
{
    return hva::hvaSuccess;
}

CoordinateTransformationNode::CoordinateTransformationNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(FUSION_MODULE_INPORT_NUM, 1, totalThreadNum), m_impl(new Impl(*this))
{}

CoordinateTransformationNode::~CoordinateTransformationNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t CoordinateTransformationNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t CoordinateTransformationNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * LocalMediaInputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> CoordinateTransformationNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<CoordinateTransformationNode *>(this));
}

hva::hvaStatus_t CoordinateTransformationNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t CoordinateTransformationNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t CoordinateTransformationNode::prepare()
{
    return m_impl->prepare();
}

class CoordinateTransformationNodeWorker::Impl {
  public:
    Impl(CoordinateTransformationNodeWorker &ctx,
         const std::string &registrationMatrixFilePath,
         const std::string &qMatrixFilePath,
         const std::string &homographyMatrixFilePath,
         const std::vector<int> &pclConstraints,
         const fusionInPortsInfo_t &fusionInPortsInfo);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run coordinate
     * transformation and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    CoordinateTransformation m_coordsTrans;
    // std::unordered_map<unsigned, cv::Rect2f> historyBBox;
    CoordinateTransformationNodeWorker &m_ctx;
    fusionInPortsInfo_t m_fusionInPortsInfo;
};

CoordinateTransformationNodeWorker::Impl::Impl(CoordinateTransformationNodeWorker &ctx,
                                               const std::string &registrationMatrixFilePath,
                                               const std::string &qMatrixFilePath,
                                               const std::string &homographyMatrixFilePath,
                                               const std::vector<int> &pclConstraints,
                                               const fusionInPortsInfo_t &fusionInPortsInfo)
    : m_ctx(ctx), m_fusionInPortsInfo(fusionInPortsInfo)
{
    m_coordsTrans.setParameters(registrationMatrixFilePath, qMatrixFilePath, homographyMatrixFilePath, pclConstraints);
}

CoordinateTransformationNodeWorker::Impl::~Impl() {}

void CoordinateTransformationNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run coordinate transformation
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void CoordinateTransformationNodeWorker::Impl::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < FUSION_MODULE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, portIndices);
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        if (vecBlobInput.size() != FUSION_MODULE_INPORT_NUM) {
            HVA_ERROR("CoordinateTransformation node received %d inputs at node %d, but "
                      "expect to be: %d",
                      vecBlobInput.size(), batchIdx, FUSION_MODULE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        hva::hvaBlob_t::Ptr cameraBlob = vecBlobInput[m_fusionInPortsInfo.mediaInputPort];
        hva::hvaBlob_t::Ptr radarBlob = vecBlobInput[m_fusionInPortsInfo.radarInputPort];
        HVA_ASSERT(cameraBlob);
        HVA_ASSERT(radarBlob);
        std::shared_ptr<hva::timeStampInfo> coordinateTransIn = std::make_shared<hva::timeStampInfo>(cameraBlob->frameId, "coordinateTransIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &coordinateTransIn);

        HVA_DEBUG("CoordinateTransformation node %d on frameId %d at port id: %d(Media); "
                  "frameId %d at port id: %d(Radar)",
                  batchIdx, cameraBlob->frameId, m_fusionInPortsInfo.mediaInputPort, radarBlob->frameId, m_fusionInPortsInfo.radarInputPort);

        /**
         * process: media
         */
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(cameraBlob->get(m_fusionInPortsInfo.mediaBlobBuffIndex));
        HVA_ASSERT(ptrFrameBuf);

        /**
         * process: radar
         */
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrRadarBuf =
            std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(radarBlob->get(m_fusionInPortsInfo.radarBlobBuffIndex));
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
        m_ctx.getLatencyMonitor().startRecording(cameraBlob->frameId, "coord transformation");
        int cameraSize = ptrFrameBuf->rois.size();
        int radarSize = filteredRadarOutput.size();
        HVA_DEBUG("Frame %d: cameraSize(%d), radarSize(%d)", cameraBlob->frameId, cameraSize, radarSize);

        HVA_DEBUG("fusion perform coordinate transformation on frame%d", cameraBlob->frameId);
        FusionOutput fusionOutput(1);

        // add radar output
        fusionOutput.setRadarOutput(filteredRadarOutput);
        // add camera output
        std::vector<BBox> cameraRadarCoords;
        std::vector<DetectedObject> fusionResult;
        for (const auto &item : ptrFrameBuf->rois) {
            cv::Rect2i rect = cv::Rect2i(item.x, item.y, item.width, item.height);
            cv::Rect2f radarCoords = m_coordsTrans.pixel2Radar(rect);
            cameraRadarCoords.push_back(BBox(radarCoords.x, radarCoords.y, radarCoords.width, radarCoords.height));
            fusionResult.push_back(DetectedObject(BBox(radarCoords.x, radarCoords.y, 4.2, 1.7), item.confidenceDetection, item.labelDetection));
        }
        fusionOutput.addCameraROI(0, ptrFrameBuf->rois, cameraRadarCoords);

        // add camera fusion result (in radar coordinate), actually is camera detections in radar coordinate, for only 1 camera here
        fusionOutput.setCameraFusionRadarCoords(fusionResult);

        ptrFrameBuf->setMeta<FusionOutput>(fusionOutput);
        HVA_DEBUG("CoordinateTransformation sending blob with frameid %u and streamid %u", cameraBlob->frameId, cameraBlob->streamId);
        m_ctx.sendOutput(cameraBlob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("CoordinateTransformation completed sent blob with frameid %u and streamid %u", cameraBlob->frameId, cameraBlob->streamId);
        m_ctx.getLatencyMonitor().stopRecording(cameraBlob->frameId, "coord transformation");

        std::shared_ptr<hva::timeStampInfo> coordinateTransOut = std::make_shared<hva::timeStampInfo>(cameraBlob->frameId, "coordinateTransOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &coordinateTransOut);
    }
}

hva::hvaStatus_t CoordinateTransformationNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t CoordinateTransformationNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

CoordinateTransformationNodeWorker::CoordinateTransformationNodeWorker(hva::hvaNode_t *parentNode,
                                                                       const std::string &registrationMatrixFilePath,
                                                                       const std::string &qMatrixFilePath,
                                                                       const std::string &homographyMatrixFilePath,
                                                                       const std::vector<int> &pclConstraints,
                                                                       const fusionInPortsInfo_t &fusionInPortsInfo)
    : hva::hvaNodeWorker_t(parentNode),
      m_impl(new Impl(*this, registrationMatrixFilePath, qMatrixFilePath, homographyMatrixFilePath, pclConstraints, fusionInPortsInfo))
{}

CoordinateTransformationNodeWorker::~CoordinateTransformationNodeWorker() {}

void CoordinateTransformationNodeWorker::init()
{
    return m_impl->init();
}

void CoordinateTransformationNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(CoordinateTransformationNode, CoordinateTransformationNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce