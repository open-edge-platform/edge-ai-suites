/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <boost/exception/all.hpp>

#include "nodes/CPU-backend/MediaOutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

MediaOutputNodeWorker::MediaOutputNodeWorker(hva::hvaNode_t *parentNode, const std::string &bufType) : hva::hvaNodeWorker_t(parentNode), m_bufType(bufType) {}

/**
 * Syntax for output format in outputNode:
 * {
 *     "result": [
 *         {
 *             "status_code": int,
 *             "description": string,
 *             "roi_info": [
 *                 "roi": [int, int, int, int],
 *                 "roi_class": string,
 *                 "roi_score": float,
 *                 "track_id": int,
 *                 "track_status": string,
 *                 "media_birdview_roi": [float, float, float, float],
 *                 "fusion_roi_state": [float, float, float, float],
 *                 "fusion_roi_size": [float, float]
 *             ],
 *         },
 *     ]
 * }
 */
void MediaOutputNodeWorker::process(std::size_t batchIdx)
{
    // Remember getBatchedInput() should only be called once here!!!
    // because ObjectAssociate node using `hva::hvaBatchingConfig_t::BatchingWithStream` to consequently read frames
    // once called, the expected frameid will +1
    auto vecBlobInput = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    if (vecBlobInput.size() > 0) {
        hva::hvaBlob_t::Ptr mediaBlob = vecBlobInput[0];
        HVA_DEBUG("Media output node %d received media blob on frameId %d", batchIdx, mediaBlob->frameId);

        boost::property_tree::ptree jsonTree;
        boost::property_tree::ptree roisTree;

        //
        // process: media pipeline
        //
        hva::hvaVideoFrameWithROIBuf_t::Ptr mediaBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(mediaBlob->get(0));

        hce::ai::inference::TimeStamp_t timeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;

        mediaBlob->get(0)->getMeta(timeMeta);
        startTime = timeMeta.timeStamp;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();

        jsonTree.clear();
        roisTree.clear();
        for (const auto &item : mediaBuf->rois) {
            boost::property_tree::ptree roiInfoTree;

            // media roi
            boost::property_tree::ptree roiBoxTree;
            std::vector<int> roiBoxVal = {item.x, item.y, item.width, item.height};
            putVectorToJson<int>(roiBoxTree, roiBoxVal);

            roiInfoTree.add_child("roi", roiBoxTree);
            roiInfoTree.put("roi_class", item.labelDetection);
            roiInfoTree.put("roi_score", item.confidenceDetection);

            // tracking
            roiInfoTree.put("track_id", item.trackingId);
            roiInfoTree.put("track_status", vas::ot::TrackStatusToString(item.trackingStatus));

            // dummy media birdview roi
            boost::property_tree::ptree roiWorldBoxTree;
            std::vector<float> roiWorldBoxVal = {0.0, 0.0, 0.0, 0.0};
            putVectorToJson<float>(roiWorldBoxTree, roiWorldBoxVal);
            roiInfoTree.add_child("media_birdview_roi", roiWorldBoxTree);

            // dummy data for radar output
            boost::property_tree::ptree stateTree;
            std::vector<float> stateVal = {0.0, 0.0, 0.0, 0.0};
            putVectorToJson<float>(stateTree, stateVal);
            roiInfoTree.add_child("fusion_roi_state", stateTree);

            boost::property_tree::ptree sizeTree;
            std::vector<float> sizeVal = {0.0, 0.0};
            putVectorToJson<float>(sizeTree, sizeVal);
            roiInfoTree.add_child("fusion_roi_size", sizeTree);

            // E2E latency
            // roiInfoTree.put("latency", latency);
            // roiInfoTree.put("startTime", startTime);
            // roiInfoTree.put("endTime", endTime);

            roisTree.push_back(std::make_pair("", roiInfoTree));
        }

        if (roisTree.empty()) {
            if (mediaBuf->drop) {
                jsonTree.put("status_code", -2);
                jsonTree.put("description", "Read or decode input media failed");
                jsonTree.put("latency", latency);
            }
            else {
                jsonTree.put("status_code", 1u);
                jsonTree.put("description", "noRoiDetected");
                jsonTree.put("latency", latency);
            }
        }
        else {
            jsonTree.put("status_code", 0u);
            jsonTree.put("description", "succeeded");
            jsonTree.add_child("roi_info", roisTree);
            jsonTree.put("latency", latency);
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();
        // std::cout << res.message << std::endl;

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), mediaBuf->frameId);

        dynamic_cast<MediaOutputNode *>(getParentPtr())->emitOutput(res, (baseResponseNode *)getParentPtr(), nullptr);

        if (mediaBuf->getTag() == 1) {
            HVA_DEBUG("Emit finish on frame id %d", mediaBuf->frameId);
            dynamic_cast<MediaOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
        }
    }
}

void MediaOutputNodeWorker::processByLastRun(std::size_t batchIdx)
{
    dynamic_cast<MediaOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
}

MediaOutputNode::MediaOutputNode(std::size_t totalThreadNum) : baseResponseNode(1, 0, totalThreadNum), m_bufType("FD")
{
    transitStateTo(hva::hvaState_t::configured);
}

hva::hvaStatus_t MediaOutputNode::configureByString(const std::string &config)
{
    m_configParser.parse(config);
    m_configParser.getVal<std::string>("BufferType", m_bufType);

    if (m_bufType != "String" && m_bufType != "FD") {
        HVA_ERROR("Unrecognized buffer type: %s", m_bufType.c_str());
        m_bufType = "FD";
        return hva::hvaFailure;
    }

    auto configBatch = this->getBatchingConfig();
    configBatch.batchingPolicy = (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream;
    configBatch.streamNum = 1;
    configBatch.threadNumPerBatch = 1;
    this->configBatch(configBatch);
    HVA_DEBUG("low latency output node change batching policy to BatchingPolicy::BatchingWithStream");

    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> MediaOutputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new MediaOutputNodeWorker((hva::hvaNode_t *)this, m_bufType));
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(MediaOutputNode, MediaOutputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
