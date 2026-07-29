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
#include <sys/timeb.h>

#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/CPU-backend/LLResultSinkNode.hpp"
#include "common/base64.hpp"

namespace hce{

namespace ai{

namespace inference{

class HbaseManager{
public:
    static HbaseManager& getInstance(){
        static HbaseManager inst;
        return inst;
    };

    HbaseManager(const HbaseManager& ) = delete;

    HbaseManager(HbaseManager&& ) = delete;

    HbaseManager& operator=(const HbaseManager&) = delete;

    HbaseManager& operator=(HbaseManager&&) = delete;

    bool saveFeatures(const hce::storage::FeatureSet& featureSet, const std::vector<std::string>& attrib, std::vector<std::string>& retIds){
        std::lock_guard<std::mutex> lg(m_hbaseMutex);
        // put featureSets to storage(hbase) with capture_source_id
        hce::storage::StatusCode ret = m_featureClient->putFeatureVectorsWithIds("vehicle", "feature_storage", featureSet, attrib, retIds);
        if(ret == hce::storage::success){
            return true;
        }
        else{
            return false;
        }
    };

private:

    HbaseManager(){
        // build connection to feature storage client
        m_featureClient = std::unique_ptr<hce::storage::HBaseStorage>(new hce::storage::HBaseStorage());
    };

    std::unique_ptr<hce::storage::FeatureStorage> m_featureClient;
    std::mutex m_hbaseMutex;
};

LLResultSinkNodeWorker::LLResultSinkNodeWorker(hva::hvaNode_t* parentNode)
    : baseResponseNodeWorker(parentNode) {
    
    m_nodeName = ((LLResultSinkNode*)getParentPtr())->nodeClassName();
}

/**
 * @brief Called by hva framework for each video frame, will be called only once before the usual process() being called
 * make instance for LocalFileManager
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LLResultSinkNodeWorker::processByFirstRun(std::size_t batchIdx){
    HbaseManager::getInstance(); //dummy to trigger init
}

/**
 * @brief construct feature set, to put hvaROI_t to featureSet the format defined by storage API
*/
void LLResultSinkNodeWorker::constructFeatureSet(const std::vector<hva::hvaROI_t>& rois, HceDatabaseMeta& meta,
                                                 hce::storage::FeatureSet& featureSet){
    // mediaUri, timestamp, capture_source_ids: each roi share the same meta-info with jpeg-level's
    const std::size_t roiCount = rois.size();
    // for sanity
    if (roiCount == 0) {
        return;
    }
    featureSet.mediaUri = std::vector<std::string>(roiCount);
    for(auto& item: featureSet.mediaUri){
        item = meta.mediaUri;
    }
    featureSet.timestamp = std::vector<long>(roiCount);
    for(auto& item: featureSet.timestamp){
        item = (long)meta.timeStamp;
    }
    featureSet.capture_source_ids = std::vector<std::string>(roiCount);
    for(auto& item: featureSet.capture_source_ids){
        item = meta.captureSourceId;
    }

    for(const auto& item: rois){
        featureSet.roi.push_back({item.x, item.y, item.height, item.width});
    }

    // decode feature vector to buffer
    // feature dimension: hvaROI_t use labelIdClassification to record feature dimension
    int featureLength = rois[0].labelIdClassification;
    std::shared_ptr<uint8_t> buf(new uint8_t[roiCount * featureLength]);
    for (std::size_t i = 0; i < roiCount; ++i) {
        hce::ai::inference::base64DecodeStringToBuffer(
            const_cast<std::string&>(rois[i].labelClassification),
            buf.get() + i * featureLength);
    }
    featureSet.featureBuffer = std::move(buf);

    featureSet.metadataOffset = 0;
    featureSet.metadataLength = 0;
    featureSet.featureOffset = 0;
    featureSet.featureLength = featureLength;
    featureSet.recordLength = featureLength;
    featureSet.dataType = 0; // 0 =int 8
    featureSet.dimension = featureLength;
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LLResultSinkNodeWorker::process(std::size_t batchIdx){
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

        HceDatabaseMeta meta;
        inBlob->get(0)->getMeta(meta);

        m_jsonTree.clear();

        std::vector<hva::hvaROI_t> collectedROIs;
        std::vector<std::string> attribs;
        // processing all coming rois
        for(size_t roiId = 0; roiId < buf->rois.size(); ++roiId){
            if (meta.ignoreFlags.count(roiId) > 0 && meta.ignoreFlags[roiId] == true) {
                // should be ignored in this node
                // do nothing
            }
            else {
                // collect valid rois
                hva::hvaROI_t roi = buf->rois[roiId];
                collectedROIs.push_back(roi);

                //
                // collect valid attribute results
                //
                boost::property_tree::ptree attr_json;

                // roi: [x, y, width, height]
                std::string roi_str = vectorToString<int>(std::vector<int>{roi.x, roi.y, roi.width, roi.height});
                attr_json.put("roi", roi_str);
                // parsing attribute results from HceDatabaseMeta
                auto attrs = meta.attributeResult[roiId].attr;
                if (attrs.count("color") > 0) {
                    attr_json.put("color", attrs["color"].label);
                }
                if (attrs.count("type") > 0) {
                    attr_json.put("vehicle_type", attrs["type"].label);
                }
                attr_json.put("license_plate", meta.lprResult[roiId]);

                std::stringstream ss;
                boost::property_tree::json_parser::write_json(ss, attr_json);
                attribs.push_back(ss.str());
            }
        }

        if(collectedROIs.size() != 0){

            // put hvaROI_t to featureSet the format defined by storage API
            hce::storage::FeatureSet featureSet;
            HVA_DEBUG("%s receives meta from buffer, mediauri: %s", m_nodeName.c_str(), meta.mediaUri.c_str());
            LLResultSinkNodeWorker::constructFeatureSet(collectedROIs, meta, featureSet);

            // save features to hbase database
            // save attributes to greenplum databse
            std::vector<std::string> retIds;
            if (HbaseManager::getInstance().saveFeatures(featureSet, attribs, retIds)) {

                HVA_DEBUG("RETID: %s", base64EncodeStrToStr(retIds[0]).c_str());
                HVA_DEBUG("Saved frame %d features with %d returned ids", buf->frameId, retIds.size());

                m_jsonTree.put("status_code", 0u);
                m_jsonTree.put("description", "succeeded");
            }
            else {
                HVA_DEBUG("Fail to save features for: %s", base64EncodeStrToStr(retIds[0]).c_str());
                m_jsonTree.put("status_code", -3);
                m_jsonTree.put("description", "Save results to database failed");
            }


        }
        else{
            if(buf->drop){
                m_jsonTree.put("status_code", -2);
                m_jsonTree.put("description", "Read or decode input media failed");
            }
            else{
                m_jsonTree.put("status_code", 1u);
                m_jsonTree.put("description", "noRoiDetected");
            }
        }

        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, m_jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frame id %d", res.message.c_str(), buf->frameId);

        dynamic_cast<LLResultSinkNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);

        if(buf->getTag() == hvaBlobBufferTag::END_OF_REQUEST){
            dynamic_cast<LLResultSinkNode*>(getParentPtr())->addEmitFinishFlag();
            HVA_DEBUG("Receive finish flag on framid %u and streamid %u", inBlob->frameId, inBlob->streamId);
        }
    }

    // check whether to trigger emitFinish()
    if (dynamic_cast<LLResultSinkNode*>(getParentPtr())->isEmitFinish()) {
        // coming batch processed done
        HVA_DEBUG("Emit finish!");
        dynamic_cast<LLResultSinkNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
    }
}

LLResultSinkNode::LLResultSinkNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum){
    
}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t LLResultSinkNode::configureByString(const std::string& config){
    m_configParser.parse(config);

    // after all configures being parsed, this node should be trainsitted to `configured`
    this->transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}

/**
* @brief prepare and intialize this hvaNode_t instance
* 
* @param void
* @return hvaSuccess if success
*/
hva::hvaStatus_t LLResultSinkNode::prepare() {

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
            HVA_DEBUG("resultsink node change batching policy to BatchingPolicy::BatchingWithStream");
        }
        else {
            HVA_ERROR("resultsink node should use batching policy: BatchingPolicy::BatchingWithStream");
            return hva::hvaFailure;
        }
    }

    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance: LLResultSinkNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> LLResultSinkNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LLResultSinkNodeWorker((hva::hvaNode_t*)this));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LLResultSinkNode, LLResultSinkNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}