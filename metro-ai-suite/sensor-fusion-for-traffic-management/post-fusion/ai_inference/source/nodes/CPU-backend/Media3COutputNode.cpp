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

#include <boost/exception/all.hpp>

#include "nodes/CPU-backend/Media3COutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

Media3COutputNodeWorker::Media3COutputNodeWorker(hva::hvaNode_t *parentNode, const std::string &bufType) : hva::hvaNodeWorker_t(parentNode), m_bufType(bufType)
{
}


void Media3COutputNodeWorker::process(std::size_t batchIdx)
{
    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < MEDIA_3C_OUTPUT_NODE_INPORT_NUM; portId++) {
        portIndices.push_back(portId);
    }

    // Remember getBatchedInput() should only be called once here!!!
    // because ObjectAssociate node using `hva::hvaBatchingConfig_t::BatchingWithStream` to consequently read frames
    // once called, the expected frameid will +1
    auto vecBlobInput = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, portIndices);

    if (vecBlobInput.size() > 0) {
        if (vecBlobInput.size() != MEDIA_3C_OUTPUT_NODE_INPORT_NUM) {
            HVA_ERROR("Media 2c output node received %d inputs at node %d, but expect to be: %d", vecBlobInput.size(), batchIdx,
                      MEDIA_3C_OUTPUT_NODE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        boost::property_tree::ptree jsonTree;
        boost::property_tree::ptree roisTree;

        hce::ai::inference::TimeStamp_t timeMeta;
        hce::ai::inference::InferenceTimeStamp_t inferenceTimeMeta;
        hce::ai::inference::VideoTimeStamp_t videoTimeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;

        jsonTree.clear();
        roisTree.clear();
        std::vector<double> latencies;
        std::vector<double> inferenceLatencies;
        std::vector<double> videoLatencies;
        endTime = std::chrono::high_resolution_clock::now();

        hva::hvaBlob_t::Ptr mediaBlob;
        hva::hvaVideoFrameWithROIBuf_t::Ptr mediaBuf;

        vecBlobInput[0]->get(0)->getMeta(timeMeta);
        std::chrono::duration<double, std::milli> latencyDuration = endTime - timeMeta.timeStamp;
        double latency = latencyDuration.count();
        double inferenceLatency = 0.0;
        double videoLatency = 0.0;

        if (vecBlobInput[0]->get(0)->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceLatency = std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        if (vecBlobInput[0]->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoLatency = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }

        for (size_t portId = 0; portId < MEDIA_3C_OUTPUT_NODE_INPORT_NUM; portId++) {
            mediaBlob = vecBlobInput[portId];
            HVA_DEBUG("Media 2c output node %d received media blob on portId %d and frameId %d", batchIdx, portId, mediaBlob->frameId);

            mediaBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(mediaBlob->get(0));

            mediaBlob->get(0)->getMeta(timeMeta);
            startTime = timeMeta.timeStamp;
            std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
            latencies.push_back(latencyDuration.count());

            mediaBlob->get(0)->getMeta(inferenceTimeMeta);
            latencyDuration = inferenceTimeMeta.endTime - inferenceTimeMeta.startTime;
            inferenceLatencies.push_back(latencyDuration.count());

            mediaBlob->get(0)->getMeta(videoTimeMeta);
            latencyDuration = videoTimeMeta.endTime - videoTimeMeta.startTime;
            videoLatencies.push_back(latencyDuration.count());

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

                // sensor source, -1 means radar
                roiInfoTree.put("sensor_source", portId);

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

                roisTree.push_back(std::make_pair("", roiInfoTree));
            }
        }

        if (roisTree.empty()) {
            if (mediaBuf->drop) {
                jsonTree.put("status_code", -2);
                jsonTree.put("description", "Read or decode input media failed");
            }
            else {
                jsonTree.put("status_code", 1u);
                jsonTree.put("description", "noRoiDetected");
            }
        }
        else {
            jsonTree.put("status_code", 0u);
            jsonTree.put("description", "succeeded");
            jsonTree.add_child("roi_info", roisTree);
        }
        jsonTree.put("inference_latency", inferenceLatency);
        jsonTree.put("latency", latency);
        jsonTree.put("video_latency", videoLatency);

        for (size_t portId = 0; portId < MEDIA_3C_OUTPUT_NODE_INPORT_NUM; portId++) {
            double latency = latencies[portId];
            double inferenceLatency = inferenceLatencies[portId];
            jsonTree.put("inference_latency" + std::to_string(portId + 1), inferenceLatency);
            jsonTree.put("latency" + std::to_string(portId + 1), latency);
            jsonTree.put("video_latency" + std::to_string(portId + 1), videoLatencies[portId]);
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();
        // std::cout << res.message << std::endl;

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), mediaBuf->frameId);

        dynamic_cast<Media3COutputNode *>(getParentPtr())->emitOutput(res, (baseResponseNode *)getParentPtr(), nullptr);

        if (mediaBuf->getTag() == 1) {
            HVA_DEBUG("Emit finish on frame id %d", mediaBuf->frameId);
            dynamic_cast<Media3COutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
        }
    }
}

void Media3COutputNodeWorker::processByLastRun(std::size_t batchIdx)
{
    dynamic_cast<Media3COutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
}

Media3COutputNode::Media3COutputNode(std::size_t totalThreadNum) : baseResponseNode(MEDIA_3C_OUTPUT_NODE_INPORT_NUM, 0, totalThreadNum), m_bufType("FD")
{
    transitStateTo(hva::hvaState_t::configured);
}

hva::hvaStatus_t Media3COutputNode::configureByString(const std::string &config)
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

std::shared_ptr<hva::hvaNodeWorker_t> Media3COutputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new Media3COutputNodeWorker((hva::hvaNode_t *)this, m_bufType));
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(Media3COutputNode, Media3COutputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
