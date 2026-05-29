/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023-2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <algorithm>
#include <cmath>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>

#include "nodes/CPU-backend/RadarDetectionNode.hpp"
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/databaseMeta.hpp"
namespace hce{

namespace ai{

namespace inference{

class RadarDetectionNode::Impl{
public:

    Impl(RadarDetectionNode& ctx);

    ~Impl();

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    hva::hvaStatus_t configureByString(const std::string& config);

    /**
    * @brief To validate ModelPath in configure is not none.
    * @param void
    */
    hva::hvaStatus_t validateConfiguration() const;

    /**
    * @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
    * @param void
    */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarDetectionNode* parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

private:
    RadarDetectionNode& m_ctx;

    hva::hvaConfigStringParser_t m_configParser;

    // std::string m_modelPath;
    // std::string RadarConfPath;
    int m_numRadarFrame;  //frame id
    // int m_numInferStreams;

    RadarConfigParam  m_radar_config;


    // RadarPreProcessingNode::Ptr m_model;
};

RadarDetectionNode::Impl::Impl(RadarDetectionNode& ctx):m_ctx(ctx){
    m_configParser.reset();
}

RadarDetectionNode::Impl::~Impl(){

}

// /**
// * @brief Parse params, called by hva framework right after node instantiate.
// * @param config Configure string required by this node.
// */
// hva::hvaStatus_t RadarDetectionNode::Impl::configureByString(const std::string& config){

//     m_ctx.transitStateTo(hva::hvaState_t::configured);

//     return hva::hvaSuccess;
// }


/**
* @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
* @param void
*/
std::shared_ptr<hva::hvaNodeWorker_t> RadarDetectionNode::Impl::createNodeWorker(RadarDetectionNode* parent) const{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new RadarDetectionNodeWorker{parent, m_radar_config}};
}

hva::hvaStatus_t RadarDetectionNode::Impl::rearm(){
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarDetectionNode::Impl::reset(){
    // to-do:
    return hva::hvaSuccess;
}

RadarDetectionNode::RadarDetectionNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)){
    transitStateTo(hva::hvaState_t::configured);
}

RadarDetectionNode::~RadarDetectionNode(){

}

// hva::hvaStatus_t RadarDetectionNode::configureByString(const std::string& config){
//     return m_impl->configureByString(config);
// }

std::shared_ptr<hva::hvaNodeWorker_t> RadarDetectionNode::createNodeWorker() const{
    return m_impl->createNodeWorker(const_cast<RadarDetectionNode*>(this));
}

hva::hvaStatus_t RadarDetectionNode::rearm(){
    return m_impl->rearm();
}

hva::hvaStatus_t RadarDetectionNode::reset(){
    return m_impl->reset();
}



class RadarDetectionNodeWorker::Impl{
public:

    Impl(RadarDetectionNodeWorker& ctx, RadarConfigParam m_radar_config);

    ~Impl();
    
    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

private:

    /**
     * @brief run post processing on model outputs
     * @param layerName output layer name
     * @param ptrBlob source output data for classification model
     * @param object ClassificationObject_t, saving parsed results
     * @return boolean
    //  */
    // bool runPostproc(const std::string layerName, const InferenceEngine::Blob::Ptr &ptrBlob, ClassificationObject_t &object);

    RadarDetectionNodeWorker& m_ctx;

    // float m_durationAve {0.0f};
    uint64_t m_cntFrame {0ul};

    RadarConfigParam m_radar_config; 

    // std::atomic<int32_t> m_cntAsyncEnd{0};
    // std::atomic<int32_t> m_cntAsyncStart{0};

    // std::string m_modelPath;
    // unsigned m_numInferReq;

    // ClassificationModel::Ptr m_clsNet;
};

RadarDetectionNodeWorker::Impl::Impl(RadarDetectionNodeWorker& ctx, RadarConfigParam m_radar_config):
        m_ctx(ctx) {
}

RadarDetectionNodeWorker::Impl::~Impl(){
    
}


/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarDetectionNodeWorker::Impl::process(std::size_t batchIdx){

    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

        // input blob is not empty
    if (vecBlobInput.size() != 0)
    {
        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        HVA_DEBUG("RadarDetection node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> RadarDetectionIn =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarDetectionIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarDetectionIn);
        
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(blob->get(0));
        RadarConfigParam params;
        ptrFrameBuf->getMeta(params);

        unsigned tag = ptrFrameBuf->getTag();
        if (!ptrFrameBuf->drop)
        {

            HVA_DEBUG("Radar detection start processing %d frame with tag %d", blob->frameId, tag);

            ThreeDimArray<ComplexFloat> frame_data = ptrFrameBuf->get<ThreeDimArray<ComplexFloat>>();

            size_t frame_size = ptrFrameBuf->getSize(); // frame_data_size

            HVA_DEBUG("Radar detection on frame %d, test frame data[0]: real%f, imag%f", blob->frameId, (float)frame_data.at(0, 0, 0).real(), (float)frame_data.at(0, 0, 0).imag());

            RadarDetection *radar_detection = new RadarDetection(frame_data, blob->frameId, frame_size, params.m_radar_basic_config_, params.m_radar_detection_config_);
            radar_detection->runDetection();

            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<pointClouds>(*radar_detection->getPCL(), sizeof(radar_detection->getPCL()));

            TimeStamp_t time_meta;
            if (ptrFrameBuf->getMeta(time_meta) == hva::hvaSuccess) {
                hvabuf->setMeta(time_meta);
                HVA_DEBUG("Radar detection node copied time_meta to next buffer");
            } 
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of TimeStamp_t into hvabuf!");
            }
            hvabuf->setMeta(params);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);

            SendController::Ptr controllerMeta;
            if(ptrFrameBuf->getMeta(controllerMeta) == hva::hvaSuccess){
                if (("Radar" == controllerMeta->controlType) && (0 < controllerMeta->capacity)) {
                    std::unique_lock<std::mutex> lock(controllerMeta->mtx);
                    (controllerMeta->count)--;
                    if (controllerMeta->count % controllerMeta->stride == 0) {
                        (controllerMeta->notFull).notify_all();
                    }
                    lock.unlock();
                }
            }

            auto radarBlob = hva::hvaBlob_t::make_blob();
   
            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);

            HVA_DEBUG("RadarDetection node sending blob with frameid %u and streamid %u, tag %d", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarDetectionOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarDetectionOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarDetectionOut);
            HVA_DEBUG("RadarDetection node completed sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
            delete radar_detection;
        }
        else
        {
            pointClouds pcl;
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<pointClouds>(pcl, 0);
            TimeStamp_t time_meta;
            if (ptrFrameBuf->getMeta(time_meta) == hva::hvaSuccess) {
                hvabuf->setMeta(time_meta);
                HVA_DEBUG("Radar detection node copied time_meta to next buffer");
            } 
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of TimeStamp_t into hvabuf!");
            }
            hvabuf->setMeta(params);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);
            hvabuf->drop = true;
            auto radarBlob = hva::hvaBlob_t::make_blob();

            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);
            
            HVA_DEBUG("RadarDetection node sending blob with frameid %u and streamid %u, tag %d, drop is true", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarDetectionOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarDetectionOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarDetectionOut);
            HVA_DEBUG("RadarDetection node sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
        }
    }
  
}

void RadarDetectionNodeWorker::Impl::init(){
    // todo
}

RadarDetectionNodeWorker::RadarDetectionNodeWorker(hva::hvaNode_t *parentNode, RadarConfigParam m_radar_config): 
        hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, m_radar_config)) {
    
}

RadarDetectionNodeWorker::~RadarDetectionNodeWorker(){

}

void RadarDetectionNodeWorker::process(std::size_t batchIdx){
    m_impl->process(batchIdx);
}

void RadarDetectionNodeWorker::init(){
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarDetectionNode, RadarDetectionNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
