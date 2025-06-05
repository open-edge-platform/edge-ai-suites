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

#include "nodes/CPU-backend/RadarTrackingNode.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "nodes/databaseMeta.hpp"

#include <chrono>
#include <cmath>
#include <algorithm>

#include <immintrin.h>


namespace hce {

namespace ai {

namespace inference {

void printTrackerOutput(trackerOutput *output)
{
    std::stringstream log;
    if (0 == output->outputInfo.size()) {
        log << "trackerOutput{}"<<std::endl;
    }
    else {

        log << "trackerOutput{" << output->outputInfo.size();

        for (int i = 0; i < output->outputInfo.size(); ++i) {
         
            log << output->outputInfo[i].trackerID <<",\t"<<output->outputInfo[i].state<<",\t"<<"[";

            for (int j = 0; j < 3; ++j) {
                log << output->outputInfo[i].S_hat[j] << ", ";
            }
            log << output->outputInfo[i].S_hat[3] <<"],\t" << output->outputInfo[i].xSize<<",\t"<< output->outputInfo[i].ySize; 
 
        }

        log <<"}"<< std::endl;
    }
    HVA_DEBUG("%s", log.str().c_str());
}

void printTrackInput(clusteringDBscanOutput *output)
{
    std::stringstream log;
    if (0 == output->numCluster) {
        log << "TrackerInput{}" << std::endl;
    }
    else {
        
        log << "TrackerInput{" << "[";

        for (int i = 0; i < output->InputArray.size() - 1; ++i) {
            log << output->InputArray[i]<< ", ";
        }
 
        log << output->InputArray[output->InputArray.size() - 1] << "], \t";

        for (int i = 0; i < output->numCluster; ++i) {

            log << "["<< output->report[i].numPoints <<",\t"<<output->report[i].xCenter<<",\t"<< output->report[i].yCenter<<",\t" <<output->report[i].xSize<<",\t"<< output->report[i].ySize <<output->report[i].avgVel<<",\t";
            log << output->report[i].centerRangeVar<<",\t" <<output->report[i].centerAngleVar <<",\t"<< output->report[i].centerDopplerVar<< "];";
        }

        log << "}"<< std::endl;
    }
    HVA_DEBUG("%s", log.str().c_str());
}


class RadarTrackingNode::Impl {
  public:
    Impl(RadarTrackingNode &ctx);

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
     * RadarTrackingNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarTrackingNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    RadarTrackingNode &m_ctx;
};

RadarTrackingNode::Impl::Impl(RadarTrackingNode &ctx) : m_ctx(ctx) {}

RadarTrackingNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t RadarTrackingNode::Impl::configureByString(const std::string &config)
{
    //! TODO:
    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t RadarTrackingNode::Impl::validateConfiguration() const
{
    //! TODO:
    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * RadarTrackingNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> RadarTrackingNode::Impl::createNodeWorker(RadarTrackingNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RadarTrackingNodeWorker(parent));
}

hva::hvaStatus_t RadarTrackingNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarTrackingNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarTrackingNode::Impl::reset()
{
    return hva::hvaSuccess;
}

RadarTrackingNode::RadarTrackingNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)) {}

RadarTrackingNode::~RadarTrackingNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t RadarTrackingNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t RadarTrackingNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * RadarTrackingNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> RadarTrackingNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<RadarTrackingNode *>(this));
}

hva::hvaStatus_t RadarTrackingNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t RadarTrackingNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t RadarTrackingNode::prepare()
{
    return m_impl->prepare();
}

class RadarTrackingNodeWorker::Impl {
  public:
    Impl(RadarTrackingNodeWorker &ctx);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run radar clustering and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

  private:
    RadarTrackingNodeWorker &m_ctx;

    ClusterTracker tracker;

    bool m_isTrackerInitialized;

    std::chrono::high_resolution_clock::time_point m_prevTimestamp;
};

RadarTrackingNodeWorker::Impl::Impl(RadarTrackingNodeWorker &ctx) : m_ctx(ctx), m_isTrackerInitialized(false) {}

RadarTrackingNodeWorker::Impl::~Impl() {}

void RadarTrackingNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run radar tracking
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarTrackingNodeWorker::Impl::process(std::size_t batchIdx)
{
    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        HVA_DEBUG("RadarTracking node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> RadarTrackingIn =
        std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarTrackingIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarTrackingIn);
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(blob->get(0));
        HVA_ASSERT(ptrFrameBuf);
        // inherit meta data from previous input field
        if (!ptrFrameBuf->drop) {
            RadarConfigParam radarParams;
            if (ptrFrameBuf->containMeta<RadarConfigParam>()) {
                // success
                ptrFrameBuf->getMeta(radarParams);
            }
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of RadarConfigParam into hvabuf!");
            }

            if (!m_isTrackerInitialized) {
                clusterTrackerErrorCode errorCode = tracker.clusterTrackerCreate(&radarParams.m_radar_tracking_config_);
                if (errorCode != CLUSTERTRACKER_NO_ERROR) {
                    HVA_ERROR("Create clusterTracker Instance Failed!");
                }
                m_isTrackerInitialized = true;
                m_prevTimestamp = std::chrono::high_resolution_clock::now();
            }

            trackerInput input;
            if (ptrFrameBuf->containMeta<clusteringDBscanOutput>()) {
                // success
                ptrFrameBuf->getMeta<clusteringDBscanOutput>(input);
            }
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of trackerInput into hvabuf!");
            }

            // trackerInput input = ptrFrameBuf->get<clusteringDBscanOutput>();
            // printTrackInput(&input);
            trackerOutput output;
            // output.outputInfo.resize(CT_MAX_NUM_TRACKER);

            // float dt =
            //     (float)std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - m_prevTimestamp).count() / 1000.0;

            // m_prevTimestamp = std::chrono::high_resolution_clock::now();
            float dt = (float)1000/radarParams.m_radar_tracking_config_.timePerFrame/1000;  //ms

            if (tracker.clusterTrackerRun(&input, dt, &output) != CLUSTERTRACKER_NO_ERROR)
            {
                HVA_ERROR("clusterTrackerRun Failed!");
            }

            // printTrackerOutput(&output);

            ptrFrameBuf->setMeta<trackerOutput>(output);

            HVA_DEBUG("RadarTracking node sending blob with frameid %u and streamid %u, tag %d", blob->frameId, blob->streamId, ptrFrameBuf->getTag());
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarTrackingOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarTrackingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarTrackingOut);
            HVA_DEBUG("RadarTracking node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);

            //no tracking
            // if (input.numCluster > 0)
            // {
            //     output.outputInfo.resize(1);
            //     output.outputInfo[0].state = 0;
            //     output.outputInfo[0].trackerID = 0;
            //     output.outputInfo[0].xSize = input.report[0].xSize;
            //     output.outputInfo[0].ySize = input.report[0].ySize;
            //     output.outputInfo[0].S_hat[0] = input.report[0].xCenter;
            //     output.outputInfo[0].S_hat[1] = input.report[0].yCenter;
            //     float azimuth = (float)(atan(output.outputInfo[0].S_hat[1] / output.outputInfo[0].S_hat[0]));
            //     output.outputInfo[0].S_hat[2] = input.report[0].avgVel * cos(azimuth);
            //     output.outputInfo[0].S_hat[3] = input.report[0].avgVel * sin(azimuth);

            //     printTrackerOutput(&output);

            //     ptrFrameBuf->setMeta<trackerOutput>(output);

            //     HVA_DEBUG("RadarTracking node sending blob with frameid %u and streamid %u, tag %d", blob->frameId, blob->streamId, ptrFrameBuf->getTag());
            //     m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            //     HVA_DEBUG("RadarTracking node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            // }
            // else
            // {
            //     trackerOutput output;
            //     ptrFrameBuf->setMeta<trackerOutput>(output);

            //     HVA_DEBUG("RadarTracking node sending blob with frameid %u and streamid %u, tag %d, drop is true", blob->frameId, blob->streamId,
            //               ptrFrameBuf->getTag());
            //     m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            //     HVA_DEBUG("RadarTracking node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
            // }


        }
        else {
            trackerOutput output;
            ptrFrameBuf->setMeta<trackerOutput>(output);

            HVA_DEBUG("RadarTracking node sending blob with frameid %u and streamid %u, tag %d, drop is true", blob->frameId, blob->streamId,
                      ptrFrameBuf->getTag());
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarTrackingOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarTrackingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarTrackingOut);
            HVA_DEBUG("RadarTracking node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
        }
    }
}


hva::hvaStatus_t RadarTrackingNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarTrackingNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}


RadarTrackingNodeWorker::RadarTrackingNodeWorker(hva::hvaNode_t *parentNode) : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this)) {}

RadarTrackingNodeWorker::~RadarTrackingNodeWorker() {}

void RadarTrackingNodeWorker::init()
{
    return m_impl->init();
}

void RadarTrackingNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarTrackingNode, RadarTrackingNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
