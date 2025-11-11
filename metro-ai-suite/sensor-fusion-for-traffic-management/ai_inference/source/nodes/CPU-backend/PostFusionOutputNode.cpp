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

#include "nodes/CPU-backend/PostFusionOutputNode.hpp"

#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

PostFusionOutputNode::PostFusionOutputNode(std::size_t totalThreadNum) : baseResponseNode(1, 0, totalThreadNum)
{
    auto configBatch = this->getBatchingConfig();
    if (configBatch.batchingPolicy != (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream) {
        if (this->getTotalThreadNum() == 1) {
            // set default parameters
            // configure streaming strategy
            configBatch.batchingPolicy = (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream;
            configBatch.streamNum = 1;
            configBatch.threadNumPerBatch = 1;
            configBatch.batchSize = 1;
            this->configBatch(configBatch);
            HVA_DEBUG("resultsink node change batching policy to BatchingPolicy::BatchingWithStream");
        }
        else {
            HVA_ERROR("resultsink node should use batching policy: BatchingPolicy::BatchingWithStream");
        }
    }

    // return hva::hvaSuccess;

    transitStateTo(hva::hvaState_t::configured);
}

/**
 * @brief Constructs and returns a node worker instance:
 * PostFusionOutputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> PostFusionOutputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new PostFusionOutputNodeWorker((hva::hvaNode_t *)this));
}

PostFusionOutputNodeWorker::PostFusionOutputNodeWorker(hva::hvaNode_t *parentNode) : baseResponseNodeWorker(parentNode)
{
    m_nodeName = ((PostFusionOutputNode *)getParentPtr())->nodeClassName();
}

PostFusionOutputNodeWorker::~PostFusionOutputNodeWorker() {}

/**
 * @brief Called by hva framework for each frame, Run track-to-track association
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
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
 *                 "fusion_roi_size": [float, float],
 *                 "latency": int64_t
 *                 "startTime": std::chrono::time_point<std::chrono::high_resolution_clock>;
 *                 "endTime": std::chrono::time_point<std::chrono::high_resolution_clock>;
 *             ],
 *         },
 *     ]
 * }
 */
void PostFusionOutputNodeWorker::process(std::size_t batchIdx)
{
    std::vector<hva::hvaBlob_t::Ptr> ret = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

    if (ret.size()) {
        hva::hvaBlob_t::Ptr inBlob = ret[0];
        std::shared_ptr<hva::timeStampInfo> postFusionIn = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "postFusionIn");
        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &postFusionIn);

        boost::property_tree::ptree jsonTree;
        boost::property_tree::ptree roisTree;

        //
        // process: media-radar fusion pipeline
        //
        hva::hvaVideoFrameWithROIBuf_t::Ptr inBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(inBlob->get(0));
        HVA_DEBUG("%s %d on frameId %d and streamid %u with tag %d", m_nodeName.c_str(), batchIdx, inBlob->frameId, inBlob->streamId, inBuf->getTag());

        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        // int streamId = (int)inBlob->streamId;
        // if (m_workStreamId >= 0 && streamId != m_workStreamId) {
        //     HVA_ERROR(
        //         "%s worker should work on streamId: %d, but received "
        //         "data from invalid streamId: %d!", m_nodeName.c_str(), m_workStreamId, streamId);
        //     inBuf->drop = true;
        //     inBuf->rois.clear();
        //     return;
        // } else {
        //     // the first coming stream decides the workStreamId for this worker
        //     m_workStreamId = streamId;
        // }
        if (!validateStreamInput(inBlob)) {
            inBuf->drop = true;
            inBuf->rois.clear();
        }

        hce::ai::inference::FusionOutput fusionOutput;
        hce::ai::inference::TimeStamp_t timeMeta;
        hce::ai::inference::InferenceTimeStamp_t inferenceTimeMeta;
        hce::ai::inference::VideoTimeStamp_t videoTimeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;

        inBlob->get(0)->getMeta(timeMeta);
        startTime = timeMeta.timeStamp;

        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();
        double inferenceLatency = 0.0;
        double videoLatency = 0.0;

        if (inBlob->get(0)->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceLatency = std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        if (inBlob->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoLatency = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }

        if (hva::hvaSuccess == inBuf->getMeta(fusionOutput)) {
            getParentPtr()->emitEvent(hvaEvent_PipelineLatencyCapture, &inBuf->frameId);

            jsonTree.clear();
            roisTree.clear();
            // fusion radar output
            for (size_t roiIdx = 0; roiIdx < fusionOutput.m_fusionBBox.size(); roiIdx++) {
                hce::ai::inference::FusionBBox fusionBBox = fusionOutput.m_fusionBBox[roiIdx];
                boost::property_tree::ptree roiInfoTree;

                // dummy media roi
                boost::property_tree::ptree roiBoxTree;
                std::vector<int> roiBoxVal = {0, 0, 0, 0};
                putVectorToJson<int>(roiBoxTree, roiBoxVal);
                roiInfoTree.add_child("roi", roiBoxTree);

                // media birdview roi
                boost::property_tree::ptree roiRadarBoxTree;
                std::vector<float> roiRadarBoxVal = {0.0, 0.0, 0.0, 0.0};
                putVectorToJson<float>(roiRadarBoxTree, roiRadarBoxVal);
                roiInfoTree.add_child("media_birdview_roi", roiRadarBoxTree);

                // dummy & zero if no corresponding media detection
                roiInfoTree.put("roi_class", fusionBBox.det.label);
                roiInfoTree.put("roi_score", fusionBBox.det.confidence);

                // dummy tracking
                roiInfoTree.put("track_id", 0.0);
                roiInfoTree.put("track_status", "dummy");

                // sensor source, -1 means radar
                roiInfoTree.put("sensor_source", -1);

                // radar output
                boost::property_tree::ptree stateTree;
                std::vector<float> stateVal = {fusionBBox.radarOutput.S_hat[0], fusionBBox.radarOutput.S_hat[1], fusionBBox.radarOutput.S_hat[2],
                                               fusionBBox.radarOutput.S_hat[3]};
                putVectorToJson<float>(stateTree, stateVal);
                roiInfoTree.add_child("fusion_roi_state", stateTree);

                boost::property_tree::ptree sizeTree;
                std::vector<float> sizeVal = {fusionBBox.radarOutput.xSize, fusionBBox.radarOutput.ySize};
                putVectorToJson<float>(sizeTree, sizeVal);
                roiInfoTree.add_child("fusion_roi_size", sizeTree);

                roisTree.push_back(std::make_pair("", roiInfoTree));
            }

            // camera detections which is not associated with radar detections
            for (size_t roiIdx = 0; roiIdx < fusionOutput.m_cameraFusionRadarCoords.size(); roiIdx++) {
                if (!fusionOutput.m_cameraFusionRadarCoordsIsAssociated[roiIdx]) {
                    hce::ai::inference::DetectedObject detectedObject = fusionOutput.m_cameraFusionRadarCoords[roiIdx];
                    boost::property_tree::ptree roiInfoTree;

                    // dummy media roi
                    boost::property_tree::ptree roiBoxTree;
                    std::vector<int> roiBoxVal = {0, 0, 0, 0};
                    putVectorToJson<int>(roiBoxTree, roiBoxVal);
                    roiInfoTree.add_child("roi", roiBoxTree);

                    // media birdview roi
                    boost::property_tree::ptree roiRadarBoxTree;
                    std::vector<float> roiRadarBoxVal = {detectedObject.bbox.x, detectedObject.bbox.y, detectedObject.bbox.width, detectedObject.bbox.height};
                    putVectorToJson<float>(roiRadarBoxTree, roiRadarBoxVal);
                    roiInfoTree.add_child("media_birdview_roi", roiRadarBoxTree);

                    // dummy & zero if no corresponding media detection
                    roiInfoTree.put("roi_class", detectedObject.label);
                    roiInfoTree.put("roi_score", detectedObject.confidence);

                    // dummy tracking
                    roiInfoTree.put("track_id", 0.0);
                    roiInfoTree.put("track_status", "dummy");

                    // sensor source, -1 means radar
                    roiInfoTree.put("sensor_source", -1);

                    // radar output
                    // radar output
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

            // camera detections information
            for (size_t cameraId = 0; cameraId < fusionOutput.m_numOfCams; cameraId++) {
                std::vector<hva::hvaROI_t> cameraDetections = fusionOutput.m_cameraRois[cameraId];
                std::vector<BBox> cameraDetectionsRadarCoords = fusionOutput.m_cameraRadarCoords[cameraId];

                for (size_t roiIdx = 0; roiIdx < cameraDetections.size(); roiIdx++) {
                    hva::hvaROI_t itemPixel = cameraDetections[roiIdx];
                    BBox itemRoiRadar = cameraDetectionsRadarCoords[roiIdx];
                    boost::property_tree::ptree roiInfoTree;

                    // media roi
                    boost::property_tree::ptree roiBoxTree;
                    std::vector<int> roiBoxVal = {itemPixel.x, itemPixel.y, itemPixel.width, itemPixel.height};
                    putVectorToJson<int>(roiBoxTree, roiBoxVal);
                    roiInfoTree.add_child("roi", roiBoxTree);

                    // media birdview roi
                    boost::property_tree::ptree roiRadarBoxTree;
                    std::vector<float> roiRadarBoxVal = {0, 0, 0, 0};
                    putVectorToJson<float>(roiRadarBoxTree, roiRadarBoxVal);
                    roiInfoTree.add_child("media_birdview_roi", roiRadarBoxTree);

                    roiInfoTree.put("roi_class", itemPixel.labelDetection);
                    roiInfoTree.put("roi_score", itemPixel.confidenceDetection);

                    // tracking
                    roiInfoTree.put("track_id", itemPixel.trackingId);
                    roiInfoTree.put("track_status", vas::ot::TrackStatusToString(itemPixel.trackingStatus));

                    // sensor source, -1 means radar
                    roiInfoTree.put("sensor_source", cameraId);

                    // radar output
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
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Post fusion output node error to parse trackerOutput from radar "
                      "pipeline at frameid %u and streamid %u",
                      inBlob->frameId, inBlob->streamId);
        }

        if (roisTree.empty()) {
            if (inBuf->drop) {
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
        jsonTree.put("stream_id", inBlob->streamId);

        hce::ai::inference::TimeStampAll_t timeMetaAll;
        if (inBlob->get(0)->getMeta(timeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 4; i++) {
                if (timeMetaAll.timeStamp[i] != std::chrono::time_point<std::chrono::high_resolution_clock>()) {
                    latencyDuration = endTime - timeMetaAll.timeStamp[i];
                    latency = latencyDuration.count();
                    jsonTree.put("latency" + std::to_string(i + 1), latency);
                }
            }
        }

        hce::ai::inference::InferenceTimeAll_t inferenceTimeMetaAll;
        if (inBlob->get(0)->getMeta(inferenceTimeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 4; i++) {
                if (0.0 != inferenceTimeMetaAll.inferenceLatencies[i]) {
                    jsonTree.put("inference_latency" + std::to_string(i + 1), inferenceTimeMetaAll.inferenceLatencies[i]);
                }
            }
        }
        hce::ai::inference::VideoTimeAll_t videoTimeMetaAll;
        if (inBlob->get(0)->getMeta(videoTimeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 4; i++) {
                if (0.0 != videoTimeMetaAll.videoLatencies[i]) {
                    jsonTree.put("video_latency" + std::to_string(i + 1), videoTimeMetaAll.videoLatencies[i]);
                }
            }
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), inBuf->frameId);
        // auto now = std::chrono::high_resolution_clock::now();
        // auto epoch = now.time_since_epoch();
        // auto milliseconds =
        // std::chrono::duration_cast<std::chrono::milliseconds>(epoch).count();
        HVA_DEBUG("Emit on frame id %d", inBuf->frameId);
        // HVA_INFO("Emit on frame id %d with time %d", inBuf->frameId, milliseconds
        // );
        dynamic_cast<PostFusionOutputNode *>(getParentPtr())->emitOutput(res, (baseResponseNode *)getParentPtr(), nullptr);

        std::shared_ptr<hva::timeStampInfo> postFusionOut = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "postFusionOut");
        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &postFusionOut);
        // hce::ai::inference::TimeStamp_t timeMeta;
        // std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        // std::chrono::time_point<std::chrono::high_resolution_clock> endTime;

        // inBlob->get(0)->getMeta(timeMeta);
        // startTime = timeMeta.timeStamp;

        // endTime = std::chrono::high_resolution_clock::now();
        // auto latencyDuration = endTime - startTime;
        // auto latency = std::chrono::duration_cast<std::chrono::milliseconds>(latencyDuration).count();

        // if (inBuf->getTag() == 1) {
        //     // auto now = std::chrono::high_resolution_clock::now();
        //     // auto epoch = now.time_since_epoch();
        //     // auto milliseconds =
        //     // std::chrono::duration_cast<std::chrono::milliseconds>(epoch).count();
        //     HVA_DEBUG("Emit finish on frame id %d", inBuf->frameId);
        //     // HVA_INFO("Emit finish on frame id %d with time %d", inBuf->frameId,
        //     // milliseconds );
        //     dynamic_cast<PostFusionOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
        // }
        if (inBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
            dynamic_cast<PostFusionOutputNode *>(getParentPtr())->addEmitFinishFlag();
            HVA_DEBUG("Receive finish flag on framid %u and streamid %u", inBlob->frameId, inBlob->streamId);
        }
    }
    // check whether to trigger emitFinish()
    if (dynamic_cast<PostFusionOutputNode *>(getParentPtr())->isEmitFinish()) {
        // coming batch processed done
        HVA_DEBUG("Emit finish!");
        dynamic_cast<PostFusionOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
    }
}

void PostFusionOutputNodeWorker::processByLastRun(std::size_t batchIdx)
{
    dynamic_cast<PostFusionOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(PostFusionOutputNode, PostFusionOutputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
