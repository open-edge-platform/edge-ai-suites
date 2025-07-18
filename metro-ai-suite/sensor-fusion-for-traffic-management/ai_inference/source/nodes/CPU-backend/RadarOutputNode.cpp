/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2024 Intel Corporation.
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

#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>
#include "modules/inference_util/radar/radar_detection_helper.hpp"
#include "nodes/CPU-backend/RadarOutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

RadarOutputNodeWorker::RadarOutputNodeWorker(hva::hvaNode_t *parentNode, const std::string &bufType) : hva::hvaNodeWorker_t(parentNode), m_bufType(bufType) {}

void printTrackerOutput(trackerOutput *output)
{
    std::stringstream log;
    if (0 == output->outputInfo.size()) {
        log << "trackerOutput{}" << std::endl;
    }
    else {
        log << "trackerOutput{" << output->outputInfo.size();

        for (int i = 0; i < output->outputInfo.size(); ++i) {
            log << output->outputInfo[i].trackerID << ",\t" << output->outputInfo[i].state << ",\t"
                << "[";

            for (int j = 0; j < 3; ++j) {
                log << output->outputInfo[i].S_hat[j] << ", ";
            }
            log << output->outputInfo[i].S_hat[3] << "],\t" << output->outputInfo[i].xSize << ",\t" << output->outputInfo[i].ySize;
        }

        log << "}" << std::endl;
    }
    HVA_DEBUG("%s", log.str().c_str());
}


void RadarOutputNodeWorker::process(std::size_t batchIdx)
{
    HVA_DEBUG("Radar Output Node.");
    std::vector<hva::hvaBlob_t::Ptr> ret = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    HVA_DEBUG("Get the radar output ret size is %d", ret.size());

    if (ret.size() != 0) {
        HVA_DEBUG("Got ret size.");
        hva::hvaBlob_t::Ptr inBlob = ret[0];
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(inBlob->get(0));

        // inherit meta data from previous input field
        trackerOutput output;
        if (buf->containMeta<hce::ai::inference::trackerOutput>()) {
            // success
            buf->getMeta(output);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of trackerOutput into hvabuf!");
        }

        // printTrackerOutput(&output);

        unsigned tag = buf->getTag();
        HVA_DEBUG("Radar output start processing %d frame with tag %d", inBlob->frameId, tag);

        boost::property_tree::ptree jsonTree;
        boost::property_tree::ptree roisTree;

        hce::ai::inference::TimeStamp_t timeMeta;
        if (buf->containMeta<hce::ai::inference::TimeStamp_t>()) {
            // success
            buf->getMeta(timeMeta);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of TimeStamp_t into hvabuf!");
        }
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        startTime = timeMeta.timeStamp;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();

        jsonTree.clear();
        roisTree.clear();

        int roi_idx = 0;
        for (const auto &item : output.outputInfo) {
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

            // dummy media birdview roi
            boost::property_tree::ptree roiWorldBoxTree;
            std::vector<float> roiWorldBoxVal = {0.0, 0.0, 0.0, 0.0};
            putVectorToJson<float>(roiWorldBoxTree, roiWorldBoxVal);
            roiInfoTree.add_child("media_birdview_roi", roiWorldBoxTree);

            // radar output
            boost::property_tree::ptree stateTree;
            std::vector<float> stateVal = {item.S_hat[0], item.S_hat[1], item.S_hat[2], item.S_hat[3]};
            putVectorToJson<float>(stateTree, stateVal);
            roiInfoTree.add_child("fusion_roi_state", stateTree);

            boost::property_tree::ptree sizeTree;
            std::vector<float> sizeVal = {item.xSize, item.ySize};
            putVectorToJson<float>(sizeTree, sizeVal);
            roiInfoTree.add_child("fusion_roi_size", sizeTree);

            // E2E latency
            // roiInfoTree.put("latency", latency);

            roisTree.push_back(std::make_pair("", roiInfoTree));
        }

        // if(m_bufType == "String" && buf->get<pointClouds>()){
        if (output.outputInfo.size() > 0) {
            jsonTree.put("status_code", 0u);
            jsonTree.put("description", "succeeded");
            jsonTree.add_child("roi_info", roisTree);
            jsonTree.put("latency", latency);
        }
        else {
            jsonTree.put("status_code", -2);
            jsonTree.put("description", "failed");
            jsonTree.put("latency", latency);
        }
        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        // res.message = "Success!";
        res.message = ss.str();

        HVA_INFO("Emit: %s on frame id %d", res.message.c_str(), buf->frameId);

        dynamic_cast<RadarOutputNode *>(getParentPtr())->emitOutput(res, (baseResponseNode *)getParentPtr(), nullptr);
        HVA_DEBUG("output tag: %d", buf->getTag());
        if (buf->getTag() == 1) {
            HVA_INFO("Emit finish on frame id %d", buf->frameId);
            dynamic_cast<RadarOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
        }

        HVA_DEBUG("Radar Output node done.");
    }
}

void RadarOutputNodeWorker::processByLastRun(std::size_t batchIdx)
{
    dynamic_cast<RadarOutputNode *>(getParentPtr())->emitFinish((baseResponseNode *)getParentPtr(), nullptr);
}

RadarOutputNode::RadarOutputNode(std::size_t totalThreadNum) : baseResponseNode(1, 0, totalThreadNum), m_bufType("FD")
{
    transitStateTo(hva::hvaState_t::configured);
}

hva::hvaStatus_t RadarOutputNode::configureByString(const std::string &config)
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

std::shared_ptr<hva::hvaNodeWorker_t> RadarOutputNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RadarOutputNodeWorker((hva::hvaNode_t *)this, m_bufType));
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarOutputNode, RadarOutputNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce
