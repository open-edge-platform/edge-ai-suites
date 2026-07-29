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
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>
#include "nodes/CPU-backend/RadarPreProcessingNode.hpp"
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/radarDatabaseMeta.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

class RadarPreProcessingNode::Impl{
public:

    Impl(RadarPreProcessingNode& ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarPreProcessingNode* parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

private:
    RadarPreProcessingNode& m_ctx;

    hva::hvaConfigStringParser_t m_configParser;

    // std::string m_modelPath;
    std::string RadarConfPath;
    int m_numRadarFrame;
    // int m_numInferStreams;
    boost::property_tree::ptree m_jsonTree;
    // boost::property_tree::ptree RadarConfig;
    // boost::property_tree::ptree RadarDetectionConfig;
    // boost::property_tree::ptree ClusteringConfig;
    // boost::property_tree::ptree TrackingConfig;
    RadarConfigParam  m_radar_config;


    // RadarPreProcessingNode::Ptr m_model;
};

RadarPreProcessingNode::Impl::Impl(RadarPreProcessingNode& ctx):m_ctx(ctx){
    m_configParser.reset();
}

RadarPreProcessingNode::Impl::~Impl(){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t RadarPreProcessingNode::Impl::configureByString(const std::string& config){
    //parse json file and save data to RadarConfigParam
    if(config.empty()){
        return hva::hvaFailure;
    }

    if(!m_configParser.parse(config)){
        HVA_ERROR("Illegal parse string!");
    }
    
    // models must be put in directory: "/opt/models/"
    std::string radarConfigPath;
    m_configParser.getVal<std::string>("RadarConfigPath", radarConfigPath);
    HVA_DEBUG("radarConfigPath (%s) read", radarConfigPath.c_str());

    //parser json

    // HVA_DEBUG("Parsing model_proc json from file: %s", radarConfigPath.c_str());
    JsonReader m_json_reader;
    m_json_reader.read(radarConfigPath);
    const nlohmann::json &radar_config_content = m_json_reader.content();
    std::vector<std::string> required_fields = {"RadarBasicConfig", "RadarDetectionConfig", "RadarClusteringConfig", "RadarTrackingConfig"};
    JsonReader::check_required_item(radar_config_content, required_fields);

    // read RadarBasicConfig
    auto radar_basic_config_items = radar_config_content.at("RadarBasicConfig");
    for(auto &items:radar_basic_config_items){
        m_radar_config.m_radar_basic_config_.numRx = items["numRx"].get<int>();
        m_radar_config.m_radar_basic_config_.numTx = items["numTx"].get<int>();
        m_radar_config.m_radar_basic_config_.Start_frequency = items["Start_frequency"].get<double>();
        m_radar_config.m_radar_basic_config_.idle = items["idle"].get<double>();
        m_radar_config.m_radar_basic_config_.adcStartTime = items["adcStartTime"].get<double>();
        m_radar_config.m_radar_basic_config_.rampEndTime = items["rampEndTime"].get<double>();
        m_radar_config.m_radar_basic_config_.freqSlopeConst = items["freqSlopeConst"].get<double>();
        m_radar_config.m_radar_basic_config_.adcSamples = items["adcSamples"].get<int>();
        m_radar_config.m_radar_basic_config_.adcSampleRate = items["adcSampleRate"].get<double>();
        m_radar_config.m_radar_basic_config_.numChirps = items["numChirps"].get<int>();
        m_radar_config.m_radar_basic_config_.fps = items["fps"].get<float>();

    }
   
    // read RadarDetectionConfig
    auto radar_detection_config_items = radar_config_content.at("RadarDetectionConfig");
    for(auto &items:radar_detection_config_items){
        m_radar_config.m_radar_detection_config_.m_range_win_type_ = items["RangeWinType"].get<WinType>();
        m_radar_config.m_radar_detection_config_.m_doppler_win_type_ = items["DopplerWinType"].get<WinType>();
        m_radar_config.m_radar_detection_config_.m_aoa_estimation_type_ = items["AoaEstimationType"].get<AoaEstimationType>();
        m_radar_config.m_radar_detection_config_.m_doppler_cfar_method_ = items["DopplerCfarMethod"].get<CfarMethod>();
        m_radar_config.m_radar_detection_config_.DopplerPfa = items["DopplerPfa"].get<float>();
        m_radar_config.m_radar_detection_config_.DopplerWinGuardLen = items["DopplerWinGuardLen"].get<int>();
        m_radar_config.m_radar_detection_config_.DopplerWinTrainLen = items["DopplerWinTrainLen"].get<int>();
        m_radar_config.m_radar_detection_config_.m_range_cfar_method_ = items["RangeCfarMethod"].get<CfarMethod>();
        m_radar_config.m_radar_detection_config_.RangePfa = items["RangePfa"].get<float>();
        m_radar_config.m_radar_detection_config_.RangeWinGuardLen = items["RangeWinGuardLen"].get<int>();
        m_radar_config.m_radar_detection_config_.RangeWinTrainLen = items["RangeWinTrainLen"].get<int>();
    }   

    // read RadarClusteringConfig
    auto radar_clustering_config_items = radar_config_content.at("RadarClusteringConfig");
    for(auto &items:radar_clustering_config_items){
        m_radar_config.m_radar_clusterging_config_.eps = items["eps"].get<float>();
        m_radar_config.m_radar_clusterging_config_.weight = items["weight"].get<float>();
        m_radar_config.m_radar_clusterging_config_.minPointsInCluster = items["minPointsInCluster"].get<int>();
        m_radar_config.m_radar_clusterging_config_.maxClusters = items["maxClusters"].get<int>();
        m_radar_config.m_radar_clusterging_config_.maxPoints = items["maxPoints"].get<int>();
    } 

    // read RadarTrackingConfig
    auto radar_tracking_config_items = radar_config_content.at("RadarTrackingConfig");
    for(auto &items:radar_tracking_config_items){
        m_radar_config.m_radar_tracking_config_.trackerAssociationThreshold = items["trackerAssociationThreshold"].get<float>();
        m_radar_config.m_radar_tracking_config_.measurementNoiseVariance = items["measurementNoiseVariance"].get<float>();
        m_radar_config.m_radar_tracking_config_.timePerFrame = items["timePerFrame"].get<float>();
        m_radar_config.m_radar_tracking_config_.iirForgetFactor = items["iirForgetFactor"].get<float>();
        m_radar_config.m_radar_tracking_config_.trackerActiveThreshold = items["trackerActiveThreshold"].get<int>();
        m_radar_config.m_radar_tracking_config_.trackerForgetThreshold = items["trackerForgetThreshold"].get<int>();
    } 

    // after all configures being parsed, this node should be trainsitted to `configured`
    m_ctx.transitStateTo(hva::hvaState_t::configured);

    return hva::hvaSuccess;
}


/**
* @brief Constructs and returns a node worker instance: ClassificationNodeWorker_CPU.
* @param void
*/
std::shared_ptr<hva::hvaNodeWorker_t> RadarPreProcessingNode::Impl::createNodeWorker(RadarPreProcessingNode* parent) const{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new RadarPreprocessingNodeWorker{parent, m_radar_config}};
}

hva::hvaStatus_t RadarPreProcessingNode::Impl::rearm(){
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarPreProcessingNode::Impl::reset(){
    // to-do:
    return hva::hvaSuccess;
}

RadarPreProcessingNode::RadarPreProcessingNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)){

}

RadarPreProcessingNode::~RadarPreProcessingNode(){

}

hva::hvaStatus_t RadarPreProcessingNode::configureByString(const std::string& config){
    return m_impl->configureByString(config);
}

std::shared_ptr<hva::hvaNodeWorker_t> RadarPreProcessingNode::createNodeWorker() const{
    return m_impl->createNodeWorker(const_cast<RadarPreProcessingNode*>(this));
}

hva::hvaStatus_t RadarPreProcessingNode::rearm(){
    return m_impl->rearm();
}

hva::hvaStatus_t RadarPreProcessingNode::reset(){
    return m_impl->reset();
}



class RadarPreprocessingNodeWorker::Impl{
public:

    Impl(RadarPreprocessingNodeWorker& ctx, RadarConfigParam m_radar_config);

    ~Impl();
    
    /**
     * @brief Called by hva framework for each radar frame, Run radar preprocessing and pass radar cube to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

private:

    RadarPreprocessingNodeWorker& m_ctx;

    RadarConfigParam m_radar_config;

};

RadarPreprocessingNodeWorker::Impl::Impl(RadarPreprocessingNodeWorker& ctx, RadarConfigParam m_radar_config):
        m_ctx(ctx), m_radar_config(m_radar_config) {
}

RadarPreprocessingNodeWorker::Impl::~Impl(){
    
}


/**
 * @brief Called by hva framework for each radar frame, Run radar preprocessing and pass radar cube to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarPreprocessingNodeWorker::Impl::process(std::size_t batchIdx){

    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});

        // input blob is not empty
    if (vecBlobInput.size() != 0)
    {
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
        currentTime = std::chrono::high_resolution_clock::now();
        TimeStamp_t timeMeta;
        timeMeta.timeStamp = currentTime;

        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        HVA_DEBUG("RadarPreProcessing node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> RadarPreprocessIn =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarPreprocessIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarPreprocessIn);

        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(1));

        unsigned tag = ptrFrameBuf->getTag();
        if (!ptrFrameBuf->drop)
        {
            radarVec_t frame_data = ptrFrameBuf->get<radarVec_t>();

            size_t frame_size = ptrFrameBuf->getSize(); // frame_data_size

            HVA_DEBUG("radar perform preprocessing on frame%d,frame[0]: real %d, imag %d", blob->frameId, (int)frame_data[0].real(), (int)frame_data[0].imag());
            HVA_DEBUG("radar perform preprocessing on frame%d,frame[%d]: real %d, imag %d", blob->frameId, frame_size, (int)frame_data[frame_size - 1].real(), (int)frame_data[frame_size - 1].imag());
            RadarCube *radar_cube_ = new RadarCube(frame_data.data(), frame_size, blob->frameId, this->m_radar_config.m_radar_basic_config_);

            radar_cube_->radarCube_format(frame_data.data());
            const int radar_frame_size = radar_cube_->getRadarFrameSize();

            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<ThreeDimArray<ComplexFloat>>(radar_cube_->getRadarCube(), radar_frame_size);

            hvabuf->setMeta(timeMeta);
            hvabuf->setMeta(this->m_radar_config);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);
            SendController::Ptr controllerMeta;
            if(ptrFrameBuf->getMeta(controllerMeta) == hva::hvaSuccess){
                hvabuf->setMeta(controllerMeta);
                HVA_DEBUG("Radar preprocessing node copied controller meta to next buffer");
            }

            auto radarBlob = hva::hvaBlob_t::make_blob();

            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);

            HVA_DEBUG("Radar preprocessing node sending blob with frameid %u and streamid %u, tag %d", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarPreprocessOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarPreprocessOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarPreprocessOut);
            HVA_DEBUG("Radar preprocessing node sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
            delete radar_cube_;
        }
        else
        {
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<ThreeDimArray<ComplexFloat>>(ThreeDimArray<ComplexFloat>(0, 0, 0), 0);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);
            hvabuf->drop =true;
            auto radarBlob = hva::hvaBlob_t::make_blob();

            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);
            
            HVA_DEBUG("Radar preprocessing node sending blob with frameid %u and streamid %u, tag %d, drop is true", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarPreprocessOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarPreprocessOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarPreprocessOut);
            HVA_DEBUG("Radar preprocessing node sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
        }
    }
}

void RadarPreprocessingNodeWorker::Impl::init(){
    // todo
}

RadarPreprocessingNodeWorker::RadarPreprocessingNodeWorker(hva::hvaNode_t *parentNode, RadarConfigParam m_radar_config): 
        hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, m_radar_config)) {
    
}

RadarPreprocessingNodeWorker::~RadarPreprocessingNodeWorker(){

}

void RadarPreprocessingNodeWorker::process(std::size_t batchIdx){
    m_impl->process(batchIdx);
}

void RadarPreprocessingNodeWorker::init(){
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarPreProcessingNode, RadarPreProcessingNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}

