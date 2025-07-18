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

#include "nodes/CPU-backend/MediaRadarOutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

MediaRadarOutputNodeWorker::MediaRadarOutputNodeWorker(hva::hvaNode_t* parentNode, inPortsInfo_t inPortsInfo):hva::hvaNodeWorker_t(parentNode), 
        m_inPortsInfo(inPortsInfo){

}

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
 *                 "fusion_roi_state": [float, float, float, float],
 *                 "fusion_roi_size": [float, float]
 *             ],
 *         },
 *     ]
 * }
 * 
*/
void MediaRadarOutputNodeWorker::process(std::size_t batchIdx){

    std::vector<size_t> portIndices;
    for (size_t portId = 0; portId < MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM; portId ++) {
        portIndices.push_back(portId);
    }

    // Remember getBatchedInput() should only be called once here!!!
    // because ObjectAssociate node using `hva::hvaBatchingConfig_t::BatchingWithStream` to consequently read frames
    // once called, the expected frameid will +1
    auto vecBlobInput = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, portIndices);

    if (vecBlobInput.size() > 0) {
        if (vecBlobInput.size() != MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM) {
            HVA_ERROR("Media radar output node received %d inputs at node %d, but expect to be: %d", 
                       vecBlobInput.size(), batchIdx, MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM);
            HVA_ASSERT(false);
        }

        // TODO: hardcode on inport id
        hva::hvaBlob_t::Ptr mediaBlob = vecBlobInput[m_inPortsInfo.mediaInputPort];
        HVA_DEBUG("Media radar output node %d received media blob on frameId %d", batchIdx, mediaBlob->frameId);
        hva::hvaBlob_t::Ptr radarBlob = vecBlobInput[m_inPortsInfo.radarInputPort];
        HVA_DEBUG("Media radar output node %d received radar blob on frameId %d", batchIdx, radarBlob->frameId);
        
        boost::property_tree::ptree jsonTree;
        boost::property_tree::ptree roisTree;

        // 
        // process: media pipeline
        // 
        hva::hvaVideoFrameWithROIBuf_t::Ptr mediaBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(mediaBlob->get(0));

        jsonTree.clear();
        roisTree.clear();
        for(const auto& item: mediaBuf->rois){
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

        // 
        // process: radar pipeline
        // 
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr radarBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(radarBlob->get(0));

        hce::ai::inference::trackerOutput radarOutput;
        if (hva::hvaSuccess == radarBuf->getMeta(radarOutput)) {
            for (int i = 0; i < radarOutput.outputInfo.size(); ++i) {
                boost::property_tree::ptree roiInfoTree;

                // dummy media roi
                boost::property_tree::ptree roiBoxTree;
                std::vector<int> roiBoxVal = {0, 0, 0, 0};
                putVectorToJson<int>(roiBoxTree, roiBoxVal);

                roiInfoTree.add_child("roi", roiBoxTree);
                roiInfoTree.put("roi_class", "dummy");
                roiInfoTree.put("roi_score", 0.0);

                // dummy tracking
                roiInfoTree.put("track_id", 0.0);
                roiInfoTree.put("track_status", "dummy");

                // radar output
                boost::property_tree::ptree stateTree;
                std::vector<float> stateVal = { radarOutput.outputInfo[i].S_hat[0], 
                                                radarOutput.outputInfo[i].S_hat[1],
                                                radarOutput.outputInfo[i].S_hat[2],
                                                radarOutput.outputInfo[i].S_hat[3]};
                putVectorToJson<float>(stateTree, stateVal);
                roiInfoTree.add_child("fusion_roi_state", stateTree);

                boost::property_tree::ptree sizeTree;
                std::vector<float> sizeVal = {radarOutput.outputInfo[i].xSize, radarOutput.outputInfo[i].ySize};
                putVectorToJson<float>(sizeTree, sizeVal);
                roiInfoTree.add_child("fusion_roi_size", sizeTree);

                roisTree.push_back(std::make_pair("", roiInfoTree));
            }
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Media radar output node error to parse trackerOutput from radar pipeline at frameid %u and streamid %u", mediaBlob->frameId, mediaBlob->streamId);
        }
        
        if(roisTree.empty()){
            if(mediaBuf->drop){
                jsonTree.put("status_code", -2);
                jsonTree.put("description", "Read or decode input media failed");
            }
            else{
                jsonTree.put("status_code", 1u);
                jsonTree.put("description", "noRoiDetected");
            }
        }
        else{
            jsonTree.put("status_code", 0u);
            jsonTree.put("description", "succeeded");
            jsonTree.add_child("roi_info", roisTree);
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), mediaBuf->frameId);

        dynamic_cast<MediaRadarOutputNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);

        if(mediaBuf->getTag() == 1){
            HVA_DEBUG("Emit finish on frame id %d", mediaBuf->frameId);
            dynamic_cast<MediaRadarOutputNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
        }
    }
}

void MediaRadarOutputNodeWorker::processByLastRun(std::size_t batchIdx){
    dynamic_cast<MediaRadarOutputNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
}

MediaRadarOutputNode::MediaRadarOutputNode(std::size_t totalThreadNum)
    : baseResponseNode(MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM, 1, totalThreadNum) {

}

hva::hvaStatus_t MediaRadarOutputNode::configureByString(const std::string& config){
    
    if (config.empty()) return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    m_configParser.getVal<int>("MediaPort", m_inPortsInfo.mediaInputPort);
    m_configParser.getVal<int>("RadarPort", m_inPortsInfo.radarInputPort);
    if (m_inPortsInfo.mediaInputPort >= MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM ||
        m_inPortsInfo.radarInputPort >= MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM) {
        HVA_ERROR("In port index must be smaller than %d!", MEDIA_RADAR_OUTPUT_NODE_INPORT_NUM);
        return hva::hvaFailure;
    }
    else if (m_inPortsInfo.mediaInputPort == m_inPortsInfo.radarInputPort) {
        HVA_ERROR("In ports indices must be different for media and radar!");
        return hva::hvaFailure;
    }

    // configure streaming strategy
    auto configBatch = this->getBatchingConfig();
    configBatch.batchingPolicy = (unsigned)hva::hvaBatchingConfig_t::BatchingPolicy::BatchingWithStream;
    configBatch.streamNum = 1;
    configBatch.threadNumPerBatch = 1;
    this->configBatch(configBatch);
    HVA_DEBUG("media radar output node change batching policy to BatchingPolicy::BatchingWithStream");

    transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> MediaRadarOutputNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new MediaRadarOutputNodeWorker((hva::hvaNode_t*)this, m_inPortsInfo));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(MediaRadarOutputNode, MediaRadarOutputNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
