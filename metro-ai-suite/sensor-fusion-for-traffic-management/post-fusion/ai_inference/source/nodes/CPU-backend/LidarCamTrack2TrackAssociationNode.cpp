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

#include "nodes/CPU-backend/LidarCamTrack2TrackAssociationNode.hpp"

#include <cmath>
#include <opencv2/opencv.hpp>

#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "modules/vas/components/ot/mtt/hungarian_wrap.h"
#include "nodes/databaseMeta.hpp"
#include "nodes/lidarDatabaseMeta.hpp"
#include "modules/inference_util/fusion/data_fusion_helper_lidar.hpp"
#include "opencv2/core/types.hpp"

namespace hce {

namespace ai {

namespace inference {

const float kAssociationCostThreshold = 1.0f;
const float kRgbHistDistScale = 0.25f;
const float kNormCenterDistScale = 0.5f;
const float kNormShapeDistScale = 0.75f;

class LidarCamTrack2TrackAssociationNode::Impl {
  public:
    Impl(LidarCamTrack2TrackAssociationNode &ctx);

    ~Impl();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     */
    hva::hvaStatus_t configureByString(const std::string &config);

    /**
     * @brief do nothing in this node, place holder
     * @param void
     */
    hva::hvaStatus_t validateConfiguration() const;

    /**
     * @brief Constructs and returns a node worker instance:
     * LidarCamTrack2TrackAssociationNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(LidarCamTrack2TrackAssociationNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    LidarCamTrack2TrackAssociationNode &m_ctx;
    hva::hvaConfigStringParser_t m_configParser;
};

LidarCamTrack2TrackAssociationNode::Impl::Impl(LidarCamTrack2TrackAssociationNode &ctx) : m_ctx(ctx)
{
    m_configParser.reset();
}

LidarCamTrack2TrackAssociationNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::Impl::configureByString(const std::string &config)
{
    // m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::Impl::validateConfiguration() const
{
    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> LidarCamTrack2TrackAssociationNode::Impl::createNodeWorker(LidarCamTrack2TrackAssociationNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new LidarCamTrack2TrackAssociationNodeWorker{parent}};
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::Impl::prepare()
{
    // TO-DO
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::Impl::rearm()
{
    // TO-DO
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::Impl::reset()
{
    // TO-DO
    return hva::hvaSuccess;
}

LidarCamTrack2TrackAssociationNode::LidarCamTrack2TrackAssociationNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this))
{
    transitStateTo(hva::hvaState_t::configured);
}

LidarCamTrack2TrackAssociationNode::~LidarCamTrack2TrackAssociationNode() {}

/**
 * @brief Constructs and returns a node worker instance:
 * LidarCamTrack2TrackAssociationNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCamTrack2TrackAssociationNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<LidarCamTrack2TrackAssociationNode *>(this));
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNode::prepare()
{
    return m_impl->prepare();
}

class LidarCamTrack2TrackAssociationNodeWorker::Impl {
  public:
    Impl(LidarCamTrack2TrackAssociationNodeWorker &ctx);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run track-to-track
     * association and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    LidarCamTrack2TrackAssociationNodeWorker &m_ctx;

    static float normalizedCenterDistance(const cv::Rect2f &r1, const cv::Rect2f &r2);

    static float normalizedShapeDistance(const cv::Rect2f &r1, const cv::Rect2f &r2);

    static float computeIoU(const cv::Rect2f &r1, const cv::Rect2f &r2);

    static float computeDifferentIoU(const cv::Rect2f &r1, const cv::Rect2f &r2, bool GIou = false, bool DIoU = false, bool CIoU = false, bool EIoU = false);
};

LidarCamTrack2TrackAssociationNodeWorker::Impl::Impl(LidarCamTrack2TrackAssociationNodeWorker &ctx) : m_ctx(ctx) {}

LidarCamTrack2TrackAssociationNodeWorker::Impl::~Impl() {}

void LidarCamTrack2TrackAssociationNodeWorker::Impl::init()
{
    return;
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t LidarCamTrack2TrackAssociationNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

/**
 * @brief Called by hva framework for each frame, Run track-to-track association
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LidarCamTrack2TrackAssociationNodeWorker::Impl::process(std::size_t batchIdx)
{
    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());
    if (vecBlobInput.size() != 0) {
        // input blob is not empty
        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        std::shared_ptr<hva::timeStampInfo> track2trackIn = std::make_shared<hva::timeStampInfo>(blob->frameId, "track2trackIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &track2trackIn);
        HVA_DEBUG("LidarCam Track-to-Track Association node %d on frameId %d", batchIdx, blob->frameId);
        // frame id: blob->frameId

        // read input buf from current blob
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
        HVA_ASSERT(ptrFrameBuf);

        m_ctx.getLatencyMonitor().startRecording(blob->frameId, "Track2Track");

        // inherit meta data from previous input field
        LidarCameraFusionOutput fusionOutput;
        if (ptrFrameBuf->containMeta<LidarCameraFusionOutput>()) {
            // success
            ptrFrameBuf->getMeta(fusionOutput);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of LidarCameraFusionOutput into hvabuf!");
        }

        if (0 == fusionOutput.m_lidarDetections.size()) {
            HVA_DEBUG("LidarCam Track-to-Track Association sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            HVA_INFO("LidarCam Track-to-Track Association completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            std::shared_ptr<hva::timeStampInfo> track2trackOut = std::make_shared<hva::timeStampInfo>(blob->frameId, "track2trackOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &track2trackOut);
            return;
        }

        int32_t nLidarDetections = static_cast<int32_t>(fusionOutput.m_lidarDetections.size());
        int32_t nCameraDetections = static_cast<int32_t>(fusionOutput.m_fusedCameraDetections.size());

        std::vector<cv::Rect2f> cameraDetections;
        std::vector<cv::Rect2f> lidarDetections;
        for (int32_t c = 0; c < nCameraDetections; ++c) {
            cameraDetections.push_back(fusionOutput.m_fusedCameraDetections[c].bbox);
        }
        for (int32_t r = 0; r < nLidarDetections; ++r) {
            lidarDetections.push_back(fusionOutput.m_lidarBoxProjections[r].projected2DBoxes);
        }
        cv::Mat_<float> r2c_cost_table;
        r2c_cost_table.create(nLidarDetections, nCameraDetections + nLidarDetections);
        r2c_cost_table = 2.0f;
        for (int32_t r = 0; r < nLidarDetections; ++r) {
            for (int32_t c = 0; c < nCameraDetections; ++c) {
                r2c_cost_table(r, c) = 1.0 - computeDifferentIoU(lidarDetections[r], cameraDetections[c], false, false, true, false);
            }
        }

        vas::ot::HungarianAlgo hungarian(r2c_cost_table);
        cv::Mat_<uint8_t> r2c_assign_table = hungarian.Solve();

        for (int32_t r = 0; r < nLidarDetections; ++r) {
            bool isAssociated = false;
            LidarCamFusionBBox fusionBBox;
            fusionBBox.lidarProjectionBBox = fusionOutput.m_lidarBoxProjections[r];
            fusionBBox.lidarOutput = fusionOutput.m_lidarDetections[r];
            for (int32_t c = 0; c < nCameraDetections; ++c) {
                if (r2c_assign_table(r, c) && r2c_cost_table(r, c) < 1.60) {
                    fusionBBox.det = fusionOutput.m_fusedCameraDetections[c];
                    fusionOutput.m_cameraIsAssociated[c] = 1;
                    isAssociated = true;
                    break;
                }
            }
            if (!isAssociated) {
                fusionBBox.det = CameraDetectionObject();
            }
            fusionOutput.addLidarFusionBBox(fusionBBox);
        }

        ptrFrameBuf->setMeta<LidarCameraFusionOutput>(fusionOutput);
        HVA_DEBUG("LidarCam Track-to-Track Association sending blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
        m_ctx.getLatencyMonitor().stopRecording(blob->frameId, "Track2Track");
        m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_INFO("LidarCam Track-to-Track Association completed sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);

        std::shared_ptr<hva::timeStampInfo> track2trackOut = std::make_shared<hva::timeStampInfo>(blob->frameId, "track2trackOut");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &track2trackOut);
    }
}

float LidarCamTrack2TrackAssociationNodeWorker::Impl::normalizedCenterDistance(const cv::Rect2f &r1, const cv::Rect2f &r2)
{
    float normalizer = std::min(0.5f * (r1.width + r1.height), 0.5f * (r2.width + r2.height));

    float r1x = r1.x + 0.5f * r1.width;
    float r1y = r1.y + 0.5f * r1.height;
    float r2x = r2.x + 0.5f * r2.width;
    float r2y = r2.y + 0.5f * r2.height;
    float dx = (r2x - r1x) / normalizer;
    float dy = (r2y - r1y) / normalizer;
    return std::sqrt(dx * dx + dy * dy);
}

float LidarCamTrack2TrackAssociationNodeWorker::Impl::normalizedShapeDistance(const cv::Rect2f &r1, const cv::Rect2f &r2)
{
    int32_t normalize_w = r1.width;
    int32_t normalize_h = r1.height;

    if (r2.width + r2.height < r1.width + r1.height) {
        normalize_w = r2.width;
        normalize_h = r2.height;
    }

    float dw = (r2.width - r1.width) / normalize_w;
    float dh = (r2.height - r1.height) / normalize_h;
    return std::sqrt(dw * dw + dh * dh);
}

float LidarCamTrack2TrackAssociationNodeWorker::Impl::computeIoU(const cv::Rect2f &r1, const cv::Rect2f &r2)
{
    cv::Rect2f a = r1 | r2;
    cv::Rect2f u = r1 & r2;

    return u.area() * 1.0 / a.area();
}

float LidarCamTrack2TrackAssociationNodeWorker::Impl::computeDifferentIoU(const cv::Rect2f &r1,
                                                                          const cv::Rect2f &r2,
                                                                          bool GIou,
                                                                          bool DIoU,
                                                                          bool CIoU,
                                                                          bool EIoU)
{
    cv::Rect2f unionBox = r1 | r2;
    cv::Rect2f interBox = r1 & r2;
    float eps = 1e-9;
    float interArea = interBox.area();
    float unionArea = unionBox.area();
    float iou = interArea * 1.0 / (unionArea + eps);

    if (GIou || DIoU || CIoU || EIoU) {
        if (CIoU || DIoU || EIoU) {
            // Calculate the diagonal length of the smallest bounding rectangle of two
            // BOX
            float c2 = std::pow(unionBox.width, 2) + std::pow(unionBox.height, 2) + eps;
            // Calculate the center point distance, the center point coordinates:
            // x+width/2, y+height/2, as the Euclidean distance, get the square value
            // centerDist
            float centerDist = std::pow(r1.x + r1.width / 2.0 - r2.x - r2.width / 2.0, 2) + std::pow(r1.y + r1.height / 2.0 - r2.y - r2.height / 2.0, 2);
            if (DIoU) {
                return iou - centerDist / 2;
            }
            else if (CIoU) {
                // DIoU only considers the coverage area and center point distance,
                // so CIOU adds the factor of aspect ratio to DIoU
                float v = (4 / std::pow(M_PI, 2)) * std::pow(std::atan(r1.width / r1.height) - std::atan(r2.width / r2.height), 2);
                float alpha = v / (1 - iou + v + eps);
                return iou - (centerDist / c2 + v * alpha);
            }
            else {
                // EIoU
                float wDist = std::pow(r1.width - r2.width, 2);
                float hDist = std::pow(r1.height - r2.height, 2);
                float cw2 = std::pow(unionBox.width, 2) + eps;
                float ch2 = std::pow(unionBox.height, 2) + eps;
                return iou - (centerDist / c2 + wDist / cw2 + hDist / ch2);
            }
        }
        else {
            // GIoU
            return iou - (interArea - unionArea) / interArea;
        }
    }
    else {
        return iou;
    }
}

LidarCamTrack2TrackAssociationNodeWorker::LidarCamTrack2TrackAssociationNodeWorker(hva::hvaNode_t *parentNode)
    : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this))
{
}

LidarCamTrack2TrackAssociationNodeWorker::~LidarCamTrack2TrackAssociationNodeWorker() {}

void LidarCamTrack2TrackAssociationNodeWorker::init()
{
    return m_impl->init();
}

void LidarCamTrack2TrackAssociationNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCamTrack2TrackAssociationNode, LidarCamTrack2TrackAssociationNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
