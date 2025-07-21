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

#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>
#include "modules/inference_util/radar/radar_detection_helper.hpp"
#include "nodes/CPU-backend/RadarDetectionOutputNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

RadarDetectionOutputNodeWorker::RadarDetectionOutputNodeWorker(hva::hvaNode_t* parentNode, const std::string& bufType):hva::hvaNodeWorker_t(parentNode), 
        m_bufType(bufType){

}

void RadarDetectionOutputNodeWorker::process(std::size_t batchIdx){
    std::vector<hva::hvaBlob_t::Ptr> ret = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t> {0});
    
    if(ret.size()){
        hva::hvaBlob_t::Ptr inBlob = ret[0];
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(inBlob->get(0));
        unsigned tag = buf->getTag();
        HVA_DEBUG("Radar output start processing %d frame with tag %d", inBlob->frameId, tag);
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
        int status_code;
        std::string description;
        

        if (buf->get<pointClouds>().num >0)
        {
            HVA_DEBUG("pcl number: %d", buf->get<pointClouds>().num);
            m_jsonTree.put("status_code", 0u);
            m_jsonTree.put("description", "succeeded");
            // description = "succeeded";
            m_jsonTree.put("frameId", buf->frameId);
            m_jsonTree.put("num", buf->get<pointClouds>().num);


            boost::property_tree::ptree pcls;
            for(int i=0;i<buf->get<pointClouds>().num;i++){
                boost::property_tree::ptree pcl;
                pcl.put("rangeIdxArray", buf->get<pointClouds>().rangeIdxArray[i]);
                pcl.put("rangeFloat", buf->get<pointClouds>().rangeFloat[i]);
                pcl.put("speedIdxArray", buf->get<pointClouds>().speedIdxArray[i]);
                pcl.put("speedFloat", buf->get<pointClouds>().speedFloat[i]);
                pcl.put("SNRArray", buf->get<pointClouds>().SNRArray[i]);
                pcl.put("aoaVar", buf->get<pointClouds>().aoaVar[i]);
                pcls.push_back(std::make_pair("", pcl));
            }
            m_jsonTree.put("latency", latency);
            m_jsonTree.add_child("pcl", pcls);
        }
        else{
            m_jsonTree.put("status_code", -2);
            m_jsonTree.put("description", "failed");
            m_jsonTree.put("latency", latency);
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, m_jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), buf->frameId);

        dynamic_cast<RadarDetectionOutputNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);
        
        HVA_DEBUG("Emit: on frame id %d tag %d",  buf->frameId, buf->getTag());

        if(buf->getTag() == 1){
            HVA_DEBUG("Emit finish on frame id %d", buf->frameId);
            dynamic_cast<RadarDetectionOutputNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
        }
        
    }
}

void RadarDetectionOutputNodeWorker::processByLastRun(std::size_t batchIdx){
    dynamic_cast<RadarDetectionOutputNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
}

RadarDetectionOutputNode::RadarDetectionOutputNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum), m_bufType("FD"){
    transitStateTo(hva::hvaState_t::configured);

}

hva::hvaStatus_t RadarDetectionOutputNode::configureByString(const std::string& config){
    m_configParser.parse(config);
    m_configParser.getVal<std::string>("BufferType", m_bufType);

    if(m_bufType != "String" && m_bufType != "FD"){
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

std::shared_ptr<hva::hvaNodeWorker_t> RadarDetectionOutputNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RadarDetectionOutputNodeWorker((hva::hvaNode_t*)this, m_bufType));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarDetectionOutputNode, RadarDetectionOutputNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
