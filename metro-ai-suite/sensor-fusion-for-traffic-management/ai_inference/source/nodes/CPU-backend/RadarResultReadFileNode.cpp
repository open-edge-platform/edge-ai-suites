/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023 Intel Corporation.
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
#include "nodes/CPU-backend/RadarResultReadFileNode.hpp"
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/radarDatabaseMeta.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

class RadarResultReadFileNode::Impl{
public:

    Impl(RadarResultReadFileNode& ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarResultReadFileNode* parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

private:
    RadarResultReadFileNode& m_ctx;

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


    // RadarResultReadFileNode::Ptr m_model;
};

RadarResultReadFileNode::Impl::Impl(RadarResultReadFileNode& ctx):m_ctx(ctx){
    m_configParser.reset();
}

RadarResultReadFileNode::Impl::~Impl(){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t RadarResultReadFileNode::Impl::configureByString(const std::string& config){
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

    std::string csvFilePath;
    m_configParser.getVal<std::string>("RadarDataFilePath", csvFilePath);
    HVA_DEBUG("CSV file path (%s) read", csvFilePath.c_str());

    m_radar_config.CSVFilePath = csvFilePath;

    int dataRepeatsNum =1;
    m_configParser.getVal<int>("DataRepeatsNum", dataRepeatsNum);
    HVA_DEBUG("DataRepeatsNum (%d) read", dataRepeatsNum);
    m_radar_config.csvRepeatNum = dataRepeatsNum;

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
std::shared_ptr<hva::hvaNodeWorker_t> RadarResultReadFileNode::Impl::createNodeWorker(RadarResultReadFileNode* parent) const{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new RadarResultReadFileNodeWorker{parent, m_radar_config}};
}

hva::hvaStatus_t RadarResultReadFileNode::Impl::rearm(){
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarResultReadFileNode::Impl::reset(){
    // to-do:
    return hva::hvaSuccess;
}

RadarResultReadFileNode::RadarResultReadFileNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)){

}

RadarResultReadFileNode::~RadarResultReadFileNode(){

}

hva::hvaStatus_t RadarResultReadFileNode::configureByString(const std::string& config){
    return m_impl->configureByString(config);
}

std::shared_ptr<hva::hvaNodeWorker_t> RadarResultReadFileNode::createNodeWorker() const{
    return m_impl->createNodeWorker(const_cast<RadarResultReadFileNode*>(this));
}

hva::hvaStatus_t RadarResultReadFileNode::rearm(){
    return m_impl->rearm();
}

hva::hvaStatus_t RadarResultReadFileNode::reset(){
    return m_impl->reset();
}



class RadarResultReadFileNodeWorker::Impl{
public:

    Impl(RadarResultReadFileNodeWorker& ctx, RadarConfigParam m_radar_config);

    ~Impl();
    
    /**
     * @brief Called by hva framework for each radar frame, Run radar preprocessing and pass radar cube to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    bool readRadarDataFromCSV(const std::string& csvFilePath, trackerOutput& content, unsigned int targetFrameId);
    void sendEmptyBuf(hva::hvaBlob_t::Ptr inBlob, int tag);

    /**
     * @brief Frame index increased for every coming frame, will be called at the process()
     * @param void
     */
    unsigned fetch_increment();

private:

    RadarResultReadFileNodeWorker& m_ctx;

    RadarConfigParam m_radar_config;
    int m_workStreamId;
    std::atomic<unsigned> m_ctr;
    //std::string CSVFilePath;

};

RadarResultReadFileNodeWorker::Impl::Impl(RadarResultReadFileNodeWorker& ctx, RadarConfigParam m_radar_config):
        m_ctx(ctx), m_radar_config(m_radar_config), m_workStreamId(-1) {
}

RadarResultReadFileNodeWorker::Impl::~Impl(){
    
}
void RadarResultReadFileNodeWorker::Impl::sendEmptyBuf(hva::hvaBlob_t::Ptr inBlob, int tag){
    inBlob->vBuf.clear();
    auto RadarHvaBuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<std::string>(
        std::string(), 0);
    size_t numTrackers = 0;
    trackerOutput output;
    output.outputInfo.resize(1);
    output.outputInfo[0].state = 0;
    output.outputInfo[0].trackerID = 0;
    output.outputInfo[0].xSize = 0;
    output.outputInfo[0].ySize = 0;
    output.outputInfo[0].S_hat[0] = 0;
    output.outputInfo[0].S_hat[1] = 0;
    float azimuth = 0;
    output.outputInfo[0].S_hat[2] = 0;
    output.outputInfo[0].S_hat[3] = 0;


    // drop mark as true for empty blob
    RadarHvaBuf->drop = true;
    RadarHvaBuf->setMeta<trackerOutput>(output);

    if (tag == 1) {
        // last one in the batch. Mark it
        HVA_DEBUG("Set tag 1 on frame %d", inBlob->frameId);
        RadarHvaBuf->tagAs(1);
    } else {
        RadarHvaBuf->tagAs(0);
    }

    inBlob->push(RadarHvaBuf);
    m_ctx.sendOutput(inBlob, 0, std::chrono::milliseconds(0));
}

void RadarResultReadFileNodeWorker::Impl::process(std::size_t batchIdx) {
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    for (const auto& inBlob : vecBlobInput) {

        HVA_DEBUG("Radar result read node %d on frameId %u and streamid %u", batchIdx, inBlob->frameId, inBlob->streamId);
        hva::hvaBuf_t::Ptr buf = inBlob->get(0);

        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        int streamId = (int)inBlob->streamId;
        if (m_workStreamId >= 0 && streamId != m_workStreamId) {
        HVA_ERROR(
            "Radar result read worker should work on streamId: %d, but received "
            "data from invalid streamId: %d!",
            m_workStreamId, streamId);
        // send output
        sendEmptyBuf(inBlob, 1);
        return;
        } else {
        // the first coming stream decides the workStreamId for this worker
        m_workStreamId = streamId;
        }

        std::string csvFilePath = m_radar_config.CSVFilePath;
        
        for (unsigned int repeat = 0; repeat < m_radar_config.csvRepeatNum; ++repeat) {
            std::ifstream file(csvFilePath);

            if (!file.is_open()) {
                HVA_ERROR("Failed to open CSV file: %s", csvFilePath.c_str());
                return;
            }

            std::string line;
            
            if (!std::getline(file, line)) {
                HVA_ERROR("Failed to read header from CSV file: %s", csvFilePath.c_str());
                return;
            }

            while (std::getline(file, line)) {
                std::istringstream lineStream(line);
                std::string cell;

                // Get frameId
                std::getline(lineStream, cell, ',');
                // unsigned int frameId = std::stoul(cell);
                unsigned int frameId = fetch_increment();
                std::shared_ptr<hva::timeStampInfo> RadarReaderIn =
                std::make_shared<hva::timeStampInfo>(frameId, "RadarReaderIn");
                m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarReaderIn);
                std::vector<float> radarRoiValues;
                std::vector<float> radarSizeValues;
                std::vector<int> radarStateValues;
                std::vector<int> radarIDValues;

                std::getline(lineStream, cell, ',');
                std::istringstream radarRoiStream(cell);
                while (radarRoiStream >> cell) {
                    radarRoiValues.push_back(std::stof(cell));
                }

                std::getline(lineStream, cell, ',');
                std::istringstream radarSizeStream(cell);
                while (radarSizeStream >> cell) {
                    radarSizeValues.push_back(std::stof(cell));
                }

                std::getline(lineStream, cell, ',');
                std::istringstream radarStateStream(cell);
                while (radarStateStream >> cell) {
                    radarStateValues.push_back(std::stoi(cell));
                }

                std::getline(lineStream, cell, ',');
                std::istringstream radarIDStream(cell);
                while (radarIDStream >> cell) {
                    radarIDValues.push_back(std::stoi(cell));
                }

                size_t numTrackers = radarIDValues.size();
                if (radarRoiValues.size() / 4 != numTrackers || radarSizeValues.size() / 2 != numTrackers || radarStateValues.size() != numTrackers) {
                    HVA_ERROR("Data mismatch in CSV file: %s", csvFilePath.c_str());
                    continue;
                }

                trackerOutput trackerData;
                for (size_t i = 0; i < numTrackers; ++i) {
                    trackerOutputDataType outputData;
                    outputData.trackerID = radarIDValues[i];
                    outputData.state = radarStateValues[i];
                    for (int j = 0; j < 4; ++j) {
                        outputData.S_hat[j] = radarRoiValues[i * 4 + j];
                    }
                    outputData.xSize = radarSizeValues[i * 2];
                    outputData.ySize = radarSizeValues[i * 2 + 1];
                    trackerData.outputInfo.push_back(outputData);
                }

                // Create and send blob
                auto radarBlob = hva::hvaBlob_t::make_blob();
                radarBlob->frameId = frameId;
                radarBlob->streamId = m_workStreamId;

                hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<ThreeDimArray<ComplexFloat>>(ThreeDimArray<ComplexFloat>(0, 0, 0), 0);
                hvabuf->setMeta<trackerOutput>(trackerData);
                hvabuf->frameId = frameId;
                hvabuf->tagAs(0); // Tag as regular data

                radarBlob->push(hvabuf);
                
                std::shared_ptr<hva::timeStampInfo> RadarReaderOut =
                std::make_shared<hva::timeStampInfo>(radarBlob->frameId, "RadarReaderOut");
                m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarReaderOut);                
                // sent blob
                m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
                HVA_DEBUG("Radar result node sent blob with frameid %u", radarBlob->frameId);

            }

            file.close();
        }

    }
}

/**
 * @brief Frame index increased for every coming frame, will be called at the process()
 * @param void
 */
unsigned RadarResultReadFileNodeWorker::Impl::fetch_increment() { return m_ctr++; }

void RadarResultReadFileNodeWorker::Impl::init(){
    // todo
}

RadarResultReadFileNodeWorker::RadarResultReadFileNodeWorker(hva::hvaNode_t *parentNode, RadarConfigParam m_radar_config): 
        hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, m_radar_config)) {
    
}

RadarResultReadFileNodeWorker::~RadarResultReadFileNodeWorker(){

}

void RadarResultReadFileNodeWorker::process(std::size_t batchIdx){
    m_impl->process(batchIdx);
}

void RadarResultReadFileNodeWorker::init(){
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarResultReadFileNode, RadarResultReadFileNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}

