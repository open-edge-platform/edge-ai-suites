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

#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/CPU-backend/LLOutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

LLOutputNodeWorker::LLOutputNodeWorker(hva::hvaNode_t* parentNode):baseResponseNodeWorker(parentNode){
    
    m_nodeName = ((LLOutputNode*)getParentPtr())->nodeClassName();
}

void LLOutputNodeWorker::process(std::size_t batchIdx){
    std::vector<hva::hvaBlob_t::Ptr> vecBlobInput =
        getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    
    if (vecBlobInput.empty())
        return;
    
    for (const auto& inBlob : vecBlobInput) {
        hva::hvaVideoFrameWithROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(inBlob->get(0));
        
        HVA_DEBUG("%s %d on frameId %d and streamid %u with tag %d", 
                   m_nodeName.c_str(), batchIdx, inBlob->frameId, inBlob->streamId, buf->getTag());

        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        if (!validateStreamInput(inBlob)) {
            buf->drop = true;
            buf->rois.clear();
        }

        hce::ai::inference::HceDatabaseMeta videoMeta;
        inBlob->get(0)->getMeta(videoMeta);

        hce::ai::inference::TimeStamp_t timeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;

        inBlob->get(0)->getMeta(timeMeta);
        startTime = timeMeta.timeStamp;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();

        m_jsonTree.clear();
        m_rois.clear();
        int roi_idx = 0;
        for(const auto& item: buf->rois){
            m_x.clear();
            m_y.clear();
            m_w.clear();
            m_h.clear();
            m_roiData.clear();
            m_roi.clear();

            m_x.put("", item.x);
            m_y.put("", item.y);
            m_w.put("", item.width);
            m_h.put("", item.height);

            m_roiData.push_back(std::make_pair("", m_x));
            m_roiData.push_back(std::make_pair("", m_y));
            m_roiData.push_back(std::make_pair("", m_w));
            m_roiData.push_back(std::make_pair("", m_h));

            m_roi.add_child("roi", m_roiData);
            m_roi.put("feature_vector", item.labelClassification);

            m_roi.put("roi_class", item.labelDetection);
            m_roi.put("roi_score", item.confidenceDetection);

            boost::property_tree::ptree m_roiAttrData;
            auto attrs = videoMeta.attributeResult[roi_idx].attr;
            for (const auto& attr : attrs) {
                boost::property_tree::ptree label, conf;
                label.put("", attr.second.label);
                conf.put("", attr.second.confidence);
                m_roiAttrData.push_back(std::make_pair(attr.first, label));
                m_roiAttrData.push_back(std::make_pair(attr.first + "_score", conf));
            }
            m_roi.add_child("attribute", m_roiAttrData);

            m_rois.push_back(std::make_pair("", m_roi));

            roi_idx ++;
        }
        if(m_rois.empty()){
            if(buf->drop){
                m_jsonTree.put("status_code", -2);
                m_jsonTree.put("description", "Read or decode input media failed");
                m_jsonTree.put("latency", latency);
            }
            else{
                m_jsonTree.put("status_code", 1u);
                m_jsonTree.put("description", "noRoiDetected");
                m_jsonTree.put("latency", latency);
            }
        }
        else{
            m_jsonTree.put("status_code", 0u);
            m_jsonTree.put("description", "succeeded");
            m_jsonTree.add_child("roi_info", m_rois);
            m_jsonTree.put("latency", latency);
        }
        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, m_jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), buf->frameId);

        dynamic_cast<LLOutputNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);

        if(buf->getTag() == hvaBlobBufferTag::END_OF_REQUEST){
            HVA_DEBUG("Emit finish on frame id %d", buf->frameId);
            dynamic_cast<LLOutputNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
        }
    }
}


LLOutputNode::LLOutputNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum){

}

hva::hvaStatus_t LLOutputNode::configureByString(const std::string& config){
    m_configParser.parse(config);

    // after all configures being parsed, this node should be trainsitted to `configured`
    this->transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}

hva::hvaStatus_t LLOutputNode::prepare() {

    // check streaming strategy: frames will be fetched in order
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
            HVA_DEBUG("low latency output node change batching policy to BatchingPolicy::BatchingWithStream");
        }
        else {
            HVA_ERROR("low latency output node should use batching policy: BatchingPolicy::BatchingWithStream");
            return hva::hvaFailure;
        }
    }

    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> LLOutputNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LLOutputNodeWorker((hva::hvaNode_t*)this));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LLOutputNode, LLOutputNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}