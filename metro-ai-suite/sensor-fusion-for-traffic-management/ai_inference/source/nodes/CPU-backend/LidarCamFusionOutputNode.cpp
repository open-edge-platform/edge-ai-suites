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

#include "nodes/CPU-backend/LidarCamFusionOutputNode.hpp"

#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "nodes/databaseMeta.hpp"
#include "nodes/lidarDatabaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

LidarCamFusionOutputNode::LidarCamFusionOutputNode(std::size_t totalThreadNum) : baseResponseNode(1, 0, totalThreadNum)
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
 * LidarCamFusionOutputNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> LidarCamFusionOutputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LidarCamFusionOutputNodeWorker((hva::hvaNode_t *)this));
}

LidarCamFusionOutputNodeWorker::LidarCamFusionOutputNodeWorker(hva::hvaNode_t *parentNode) : baseResponseNodeWorker(parentNode)
{
    m_nodeName = ((LidarCamFusionOutputNode *)getParentPtr())->nodeClassName();
}

LidarCamFusionOutputNodeWorker::~LidarCamFusionOutputNodeWorker() {}

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
void LidarCamFusionOutputNodeWorker::process(std::size_t batchIdx)
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

        if (!validateStreamInput(inBlob)) {
            inBuf->drop = true;
            inBuf->rois.clear();
        }

        hce::ai::inference::LidarCameraFusionOutput fusionOutput;
        hce::ai::inference::TimeStamp_t timeMeta;
        hce::ai::inference::InferenceTimeStamp_t inferenceTimeMeta;
        hce::ai::inference::VideoTimeStamp_t videoTimeMeta;
        hce::ai::inference::LidarTimeStamp_t lidarTimeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;

        inBlob->get(0)->getMeta(timeMeta);
        startTime = timeMeta.timeStamp;

        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();
        double inferenceLatency = 0.0;
        double videoLatency = 0.0;
        double lidarLatency = 0.0;

        if (inBlob->get(0)->getMeta(inferenceTimeMeta) == hva::hvaSuccess) {
            inferenceLatency = std::chrono::duration<double, std::milli>(inferenceTimeMeta.endTime - inferenceTimeMeta.startTime).count();
        }
        if (inBlob->get(0)->getMeta(videoTimeMeta) == hva::hvaSuccess) {
            videoLatency = std::chrono::duration<double, std::milli>(videoTimeMeta.endTime - videoTimeMeta.startTime).count();
        }
        if (inBlob->get(0)->getMeta(lidarTimeMeta) == hva::hvaSuccess) {
            lidarLatency = std::chrono::duration<double, std::milli>(lidarTimeMeta.endTime - lidarTimeMeta.startTime).count();
        }

        if (hva::hvaSuccess == inBuf->getMeta(fusionOutput)) {
            getParentPtr()->emitEvent(hvaEvent_PipelineLatencyCapture, &inBuf->frameId);

            jsonTree.clear();
            roisTree.clear();
            // fusion lidar output
            for (size_t roiIdx = 0; roiIdx < fusionOutput.m_fusionBBox.size(); roiIdx++) {
                hce::ai::inference::LidarCamFusionBBox fusionBBox = fusionOutput.m_fusionBBox[roiIdx];
                boost::property_tree::ptree roiInfoTree;

                // dummy media roi
                boost::property_tree::ptree roiBoxTree;
                std::vector<int> roiBoxVal = {0, 0, 0, 0};
                putVectorToJson<int>(roiBoxTree, roiBoxVal);
                roiInfoTree.add_child("roi", roiBoxTree);

                // media birdview roi
                boost::property_tree::ptree roiWorldBoxTree;
                std::vector<float> roiWorldBoxVal = {0.0, 0.0, 0.0, 0.0};
                putVectorToJson<float>(roiWorldBoxTree, roiWorldBoxVal);
                roiInfoTree.add_child("media_birdview_roi", roiWorldBoxTree);

                // dummy & zero if no corresponding media detection
                roiInfoTree.put("roi_class", fusionBBox.det.label);
                roiInfoTree.put("roi_score", fusionBBox.det.confidence);

                // dummy tracking
                roiInfoTree.put("track_id", 0.0);
                roiInfoTree.put("track_status", "dummy");

                // sensor source, -1 means radar
                roiInfoTree.put("sensor_source", -1);

                // lidar output
                boost::property_tree::ptree stateTree;
                std::vector<float> stateVal = {fusionBBox.lidarOutput.x, fusionBBox.lidarOutput.y, fusionBBox.lidarOutput.z};
                putVectorToJson<float>(stateTree, stateVal);
                roiInfoTree.add_child("lidar_roi_state", stateTree);

                boost::property_tree::ptree sizeTree;
                std::vector<float> sizeVal = {fusionBBox.lidarOutput.length, fusionBBox.lidarOutput.width, fusionBBox.lidarOutput.height};
                putVectorToJson<float>(sizeTree, sizeVal);
                roiInfoTree.add_child("lidar_roi_size", sizeTree);

                roiInfoTree.put("yaw", fusionBBox.lidarOutput.yaw);
                roiInfoTree.put("class_id", fusionBBox.lidarOutput.class_id);
                roiInfoTree.put("likelihood", fusionBBox.lidarOutput.likelihood);

                boost::property_tree::ptree projectionSizeTree;
                std::vector<float> projectionSizeVal = {
                    fusionBBox.lidarProjectionBBox.projectedCorners[0].x, fusionBBox.lidarProjectionBBox.projectedCorners[0].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[1].x, fusionBBox.lidarProjectionBBox.projectedCorners[1].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[2].x, fusionBBox.lidarProjectionBBox.projectedCorners[2].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[3].x, fusionBBox.lidarProjectionBBox.projectedCorners[3].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[4].x, fusionBBox.lidarProjectionBBox.projectedCorners[4].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[5].x, fusionBBox.lidarProjectionBBox.projectedCorners[5].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[6].x, fusionBBox.lidarProjectionBBox.projectedCorners[6].y,
                    fusionBBox.lidarProjectionBBox.projectedCorners[7].x, fusionBBox.lidarProjectionBBox.projectedCorners[7].y};
                putVectorToJson<float>(projectionSizeTree, projectionSizeVal);
                roiInfoTree.add_child("lidar_roi_projection_size", projectionSizeTree);

                // fusion output
                boost::property_tree::ptree fusionStateTree;
                std::vector<float> fusionStateVal = {0.0, 0.0, 0.0};
                putVectorToJson<float>(fusionStateTree, fusionStateVal);
                roiInfoTree.add_child("fusion_roi_state", fusionStateTree);

                boost::property_tree::ptree fusionSizeTree;
                std::vector<float> fusionSizeVal = {0.0, 0.0, 0.0};
                putVectorToJson<float>(fusionSizeTree, fusionSizeVal);
                roiInfoTree.add_child("fusion_roi_size", fusionSizeTree);

                roisTree.push_back(std::make_pair("", roiInfoTree));
            }

            // camera detections which is not associated with lidar detections
            for (size_t roiIdx = 0; roiIdx < fusionOutput.m_fusedCameraDetections.size(); roiIdx++) {
                if (!fusionOutput.m_cameraIsAssociated[roiIdx]) {
                    hce::ai::inference::CameraDetectionObject detectedObject = fusionOutput.m_fusedCameraDetections[roiIdx];
                    boost::property_tree::ptree roiInfoTree;

                    // dummy media roi
                    boost::property_tree::ptree roiBoxTree;
                    std::vector<int> roiBoxVal = {static_cast<int>(detectedObject.bbox.x), static_cast<int>(detectedObject.bbox.y),
                                                  static_cast<int>(detectedObject.bbox.width), static_cast<int>(detectedObject.bbox.height)};
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

                    // sensor source, -1 means lidar
                    roiInfoTree.put("sensor_source", -1);

                    // lidar output
                    boost::property_tree::ptree stateTree;
                    std::vector<float> stateVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(stateTree, stateVal);
                    roiInfoTree.add_child("lidar_roi_state", stateTree);

                    boost::property_tree::ptree sizeTree;
                    std::vector<float> sizeVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(sizeTree, sizeVal);
                    roiInfoTree.add_child("lidar_roi_size", sizeTree);

                    roiInfoTree.put("yaw", 0.0);
                    roiInfoTree.put("class_id", -1.0);
                    roiInfoTree.put("likelihood", 0.0);

                    boost::property_tree::ptree projectionSizeTree;
                    std::vector<float> projectionSizeVal = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
                    putVectorToJson<float>(projectionSizeTree, projectionSizeVal);
                    roiInfoTree.add_child("lidar_roi_projection_size", projectionSizeTree);


                    // fusion output
                    boost::property_tree::ptree fusionStateTree;
                    std::vector<float> fusionStateVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(fusionStateTree, fusionStateVal);
                    roiInfoTree.add_child("fusion_roi_state", fusionStateTree);

                    boost::property_tree::ptree fusionSizeTree;
                    std::vector<float> fusionSizeVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(fusionSizeTree, fusionSizeVal);
                    roiInfoTree.add_child("fusion_roi_size", fusionSizeTree);


                    roisTree.push_back(std::make_pair("", roiInfoTree));
                }
            }

            // camera detections information
            for (size_t cameraId = 0; cameraId < fusionOutput.m_numOfCams; cameraId++) {
                std::vector<hva::hvaROI_t> cameraDetections = fusionOutput.m_cameraDetections[cameraId];

                for (size_t roiIdx = 0; roiIdx < cameraDetections.size(); roiIdx++) {
                    hva::hvaROI_t itemPixel = cameraDetections[roiIdx];
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

                    // sensor source, -1 means lidar
                    roiInfoTree.put("sensor_source", cameraId);

                    // lidar output
                    boost::property_tree::ptree stateTree;
                    std::vector<float> stateVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(stateTree, stateVal);
                    roiInfoTree.add_child("lidar_roi_state", stateTree);

                    boost::property_tree::ptree sizeTree;
                    std::vector<float> sizeVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(sizeTree, sizeVal);
                    roiInfoTree.add_child("lidar_roi_size", sizeTree);

                    roiInfoTree.put("yaw", 0.0);
                    roiInfoTree.put("class_id", -1.0);
                    roiInfoTree.put("likelihood", 0.0);

                    boost::property_tree::ptree projectionSizeTree;
                    std::vector<float> projectionSizeVal = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
                    putVectorToJson<float>(projectionSizeTree, projectionSizeVal);
                    roiInfoTree.add_child("lidar_roi_projection_size", projectionSizeTree);

                    // fusion output
                    boost::property_tree::ptree fusionStateTree;
                    std::vector<float> fusionStateVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(fusionStateTree, fusionStateVal);
                    roiInfoTree.add_child("fusion_roi_state", fusionStateTree);

                    boost::property_tree::ptree fusionSizeTree;
                    std::vector<float> fusionSizeVal = {0.0, 0.0, 0.0};
                    putVectorToJson<float>(fusionSizeTree, fusionSizeVal);
                    roiInfoTree.add_child("fusion_roi_size", fusionSizeTree);

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
        jsonTree.put("lidar_latency", lidarLatency);
        jsonTree.put("stream_id", inBlob->streamId);

        hce::ai::inference::TimeStampAll_t timeMetaAll;
        if (inBlob->get(0)->getMeta(timeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 6; i++) {
                if (timeMetaAll.timeStamp[i] != std::chrono::time_point<std::chrono::high_resolution_clock>()) {
                    latencyDuration = endTime - timeMetaAll.timeStamp[i];
                    latency = latencyDuration.count();
                    jsonTree.put("latency" + std::to_string(i + 1), latency);
                }
            }
        }

        hce::ai::inference::InferenceTimeAll_t inferenceTimeMetaAll;
        if (inBlob->get(0)->getMeta(inferenceTimeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 6; i++) {
                if (0.0 != inferenceTimeMetaAll.inferenceLatencies[i]) {
                    jsonTree.put("inference_latency" + std::to_string(i + 1), inferenceTimeMetaAll.inferenceLatencies[i]);
                }
            }
        }
        hce::ai::inference::VideoTimeAll_t videoTimeMetaAll;
        if (inBlob->get(0)->getMeta(videoTimeMetaAll) == hva::hvaSuccess) {
            for (int i = 0; i < 6; i++) {
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
        dynamic_cast<LidarCamFusionOutputNode *>(getParentPtr())->emitOutput(res, (baseResponseNode *)getParentPtr(), nullptr);

        std::shared_ptr<hva::timeStampInfo> postFusionOut = std::make_shared<hva::timeStampInfo>(inBlob->frameId, "postFusionOut");
        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &postFusionOut);

        if (inBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
            dynamic_cast<LidarCamFusionOutputNode *>(getParentPtr())->addEmitFinishFlag();
            HVA_DEBUG("Receive finish flag on framid %u and streamid %u", inBlob->frameId, inBlob->streamId);
        }
    }
    // check whether to trigger emitFinish()
    if (dynamic_cast<LidarCamFusionOutputNode *>(getParentPtr())->isEmitFinish()) {
        // coming batch processed done
        HVA_DEBUG("Emit finish!");
        dynamic_cast<LidarCamFusionOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
    }
}

void LidarCamFusionOutputNodeWorker::processByLastRun(std::size_t batchIdx)
{
    dynamic_cast<LidarCamFusionOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LidarCamFusionOutputNode, LidarCamFusionOutputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
