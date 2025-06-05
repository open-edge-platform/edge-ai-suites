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

#include "nodes/CPU-backend/RadarSignalProcessingNode.hpp"
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/databaseMeta.hpp"
#include "nodes/radarDatabaseMeta.hpp"
#include "libradar.h"
#include <memory>
#ifdef ENABLE_SANITIZE
    #define ALIGN_ALLOC(align, size) malloc((size))
#else
    #define ALIGN_ALLOC(align, size) aligned_alloc((align), (size))
#endif

#ifndef ALIGN_FREE
#define ALIGN_FREE(ptr) free(ptr)
#endif
namespace hce{

namespace ai{

namespace inference{

struct AlignedDeleter {
    void operator()(void* ptr) const {
        ALIGN_FREE(ptr); // Assuming ALIGN_FREE is the corresponding free function for ALIGN_ALLOC
    }
};
class RadarSignalProcessingNode::Impl{
public:

    Impl(RadarSignalProcessingNode& ctx);

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
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarSignalProcessingNode* parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

private:
    RadarSignalProcessingNode& m_ctx;

    hva::hvaConfigStringParser_t m_configParser;

    // std::string m_modelPath;
    // std::string RadarConfPath;
    int m_numRadarFrame;  //frame id
    // int m_numInferStreams;

    RadarConfigParam  m_radar_config;


    // RadarPreProcessingNode::Ptr m_model;
};

RadarSignalProcessingNode::Impl::Impl(RadarSignalProcessingNode& ctx):m_ctx(ctx){
    m_configParser.reset();
}

RadarSignalProcessingNode::Impl::~Impl(){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t RadarSignalProcessingNode::Impl::configureByString(const std::string& config){
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
std::shared_ptr<hva::hvaNodeWorker_t> RadarSignalProcessingNode::Impl::createNodeWorker(RadarSignalProcessingNode* parent) const{
    return std::shared_ptr<hva::hvaNodeWorker_t>{new RadarSignalProcessingNodeWorker{parent, m_radar_config}};
}

hva::hvaStatus_t RadarSignalProcessingNode::Impl::rearm(){
    // to-do:
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarSignalProcessingNode::Impl::reset(){
    // to-do:
    return hva::hvaSuccess;
}

RadarSignalProcessingNode::RadarSignalProcessingNode(std::size_t totalThreadNum):hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)){
    // transitStateTo(hva::hvaState_t::configured);
}

RadarSignalProcessingNode::~RadarSignalProcessingNode(){

}

hva::hvaStatus_t RadarSignalProcessingNode::configureByString(const std::string& config){
    return m_impl->configureByString(config);
}

std::shared_ptr<hva::hvaNodeWorker_t> RadarSignalProcessingNode::createNodeWorker() const{
    return m_impl->createNodeWorker(const_cast<RadarSignalProcessingNode*>(this));
}

hva::hvaStatus_t RadarSignalProcessingNode::rearm(){
    return m_impl->rearm();
}

hva::hvaStatus_t RadarSignalProcessingNode::reset(){
    return m_impl->reset();
}



class RadarSignalProcessingNodeWorker::Impl{
public:

    Impl(RadarSignalProcessingNodeWorker& ctx, RadarConfigParam m_radar_config);

    ~Impl();
    
    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);
    RadarParam convertToLibRadarParam(RadarConfigParam &params);
    RadarDoaType ConvertToRadarDoaType(AoaEstimationType aoaType);
    RadarErrorCode radarInit();

    void init();
    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

private:

    /**
     * @brief run post processing on model outputs
     * @param layerName output layer name
     * @param ptrBlob source output data for classification model
     * @param object ClassificationObject_t, saving parsed results
     * @return boolean
    //  */
    // bool runPostproc(const std::string layerName, const InferenceEngine::Blob::Ptr &ptrBlob, ClassificationObject_t &object);

    RadarSignalProcessingNodeWorker& m_ctx;

    // float m_durationAve {0.0f};
    uint64_t m_cntFrame {0ul};

    RadarConfigParam m_radar_config; 

    // libradar param
    RadarParam m_lib_radar_param;
    std::unique_ptr<RadarTracker> m_motTracker;
    RadarHandle* m_handle =nullptr;
    void *buf =nullptr;
    // bool m_isTrackerInitialized;
    // std::shared_ptr<void> buf = nullptr;
    RadarCube rc;

};

RadarSignalProcessingNodeWorker::Impl::Impl(RadarSignalProcessingNodeWorker& ctx, RadarConfigParam m_radar_config):
        m_ctx(ctx), m_radar_config(m_radar_config) {
    // radarInit();
    HVA_DEBUG("Radar Signal Processing node init");
    m_lib_radar_param = convertToLibRadarParam(m_radar_config);
    ulong bufSize = 0;
    radarGetMemSize(&m_lib_radar_param, &bufSize);
    HVA_DEBUG("Radar Signal Processing node init bufSize %d", bufSize);
    buf = ALIGN_ALLOC(64, bufSize);
    // buf = std::shared_ptr<void>(ALIGN_ALLOC(64, bufSize), AlignedDeleter());
    // if (!buf) {
    //     HVA_ERROR("Memory allocation failed");
    // }
    RadarErrorCode t = radarInitHandle(&m_handle, &m_lib_radar_param, buf, bufSize);
    if(t != R_SUCCESS){
        HVA_ERROR("radarInitHandle failed, error %d", t);
    }
    // if(radarInitHandle(&m_handle, &m_lib_radar_param, buf, bufSize) != R_SUCCESS){
    //     HVA_ERROR("radarInitHandle failed");
    // }
    m_motTracker.reset(RadarTracker::CreateInstance(m_lib_radar_param));
    HVA_DEBUG("Radar Signal Processing node init motTracker");

    size_t trn = m_radar_config.m_radar_basic_config_.numRx * m_radar_config.m_radar_basic_config_.numTx;
    size_t cn = m_radar_config.m_radar_basic_config_.numChirps;
    size_t sn = m_radar_config.m_radar_basic_config_.adcSamples;

    //convert frame_data to radar lib buffer
    const size_t sz = trn * cn * sn * sizeof(cfloat);

    // Get RadarParam from RadarConfigParam
    m_lib_radar_param = convertToLibRadarParam(m_radar_config);
    HVA_DEBUG("m_lib_radar_param.doaType %d", m_lib_radar_param.doaType);
    // use radar lib to do radar signal processing

    // RadarCube rc;
    rc.rn = m_lib_radar_param.rn;
    rc.tn = m_lib_radar_param.tn;
    rc.sn = m_lib_radar_param.sn;
    rc.cn = m_lib_radar_param.cn;
    rc.mat =(cfloat*)ALIGN_ALLOC(64, sz);
}

RadarSignalProcessingNodeWorker::Impl::~Impl(){
    free(rc.mat);
    rc.mat = nullptr;
    buf = nullptr;
    // buf.reset(); // Ensure buffer is released
    

    if (m_handle) {
        radarDestroyHandle(m_handle); // Ensure radar handle is released
        m_handle = nullptr;  
    }
    free(buf);

    //free(m_motTracker->GetRadarTrackingResult().td);
    m_motTracker.reset();
    
}
RadarDoaType RadarSignalProcessingNodeWorker::Impl::ConvertToRadarDoaType(AoaEstimationType aoaType) {
    switch (aoaType) {
        case FFT:
            return FFT_DOA;
        case MUSIC:
            return MUSIC_DOA;
        case DBF:
            return DBF_DOA;
        case CAPON:
            return CAPON_DOA;
        default:
            throw std::invalid_argument("Unknown AoaEstimationType");
    }
}
RadarErrorCode RadarSignalProcessingNodeWorker::Impl::radarInit(){
    HVA_DEBUG("Radar Signal Processing node init");
    m_lib_radar_param = convertToLibRadarParam(m_radar_config);
    ulong bufSize = 0;
    radarGetMemSize(&m_lib_radar_param, &bufSize);
    HVA_DEBUG("Radar Signal Processing node init bufSize %d", bufSize);
    buf = ALIGN_ALLOC(64, bufSize);
    // buf = std::shared_ptr<void>(ALIGN_ALLOC(64, bufSize), AlignedDeleter());
    // if (!buf) {
    //     HVA_ERROR("Memory allocation failed");
    // }
    RadarErrorCode t = radarInitHandle(&m_handle, &m_lib_radar_param, buf, bufSize);
    if(t != R_SUCCESS){
        HVA_ERROR("radarInitHandle failed, error %d", t);
    }
    // if(radarInitHandle(&m_handle, &m_lib_radar_param, buf, bufSize) != R_SUCCESS){
    //     HVA_ERROR("radarInitHandle failed");
    // }
    m_motTracker.reset(RadarTracker::CreateInstance(m_lib_radar_param));
    HVA_DEBUG("Radar Signal Processing node init motTracker");

    size_t trn = m_radar_config.m_radar_basic_config_.numRx * m_radar_config.m_radar_basic_config_.numTx;
    size_t cn = m_radar_config.m_radar_basic_config_.numChirps;
    size_t sn = m_radar_config.m_radar_basic_config_.adcSamples;

    //convert frame_data to radar lib buffer
    const size_t sz = trn * cn * sn * sizeof(cfloat);

    // Get RadarParam from RadarConfigParam
    m_lib_radar_param = convertToLibRadarParam(m_radar_config);
    HVA_DEBUG("m_lib_radar_param.doaType %d", m_lib_radar_param.doaType);
    // use radar lib to do radar signal processing

    // RadarCube rc;
    rc.rn = m_lib_radar_param.rn;
    rc.tn = m_lib_radar_param.tn;
    rc.sn = m_lib_radar_param.sn;
    rc.cn = m_lib_radar_param.cn;
    rc.mat =(cfloat*)ALIGN_ALLOC(64, sz);

}

RadarParam RadarSignalProcessingNodeWorker::Impl::convertToLibRadarParam(RadarConfigParam &params){
    m_lib_radar_param.startFreq = params.m_radar_basic_config_.Start_frequency;
    m_lib_radar_param.idle = params.m_radar_basic_config_.idle;
    m_lib_radar_param.adcStartTime = params.m_radar_basic_config_.adcStartTime;
    m_lib_radar_param.rampEndTime = params.m_radar_basic_config_.rampEndTime;
    m_lib_radar_param.freqSlopeConst = params.m_radar_basic_config_.freqSlopeConst;
    m_lib_radar_param.adcSampleRate = params.m_radar_basic_config_.adcSampleRate;
    m_lib_radar_param.rn = params.m_radar_basic_config_.numRx;
    m_lib_radar_param.tn = params.m_radar_basic_config_.numTx;
    m_lib_radar_param.sn = params.m_radar_basic_config_.adcSamples;
    m_lib_radar_param.cn = params.m_radar_basic_config_.numChirps;
    m_lib_radar_param.fps = params.m_radar_basic_config_.fps;
    m_lib_radar_param.dFAR = params.m_radar_detection_config_.DopplerPfa;
    m_lib_radar_param.rFAR = params.m_radar_detection_config_.RangePfa;
    m_lib_radar_param.dGWL = params.m_radar_detection_config_.DopplerWinGuardLen;
    m_lib_radar_param.dTWL = params.m_radar_detection_config_.DopplerWinTrainLen;
    m_lib_radar_param.rGWL = params.m_radar_detection_config_.RangeWinGuardLen;
    m_lib_radar_param.rTWL = params.m_radar_detection_config_.RangeWinTrainLen;

    m_lib_radar_param.doaType = ConvertToRadarDoaType(params.m_radar_detection_config_.m_aoa_estimation_type_);

    m_lib_radar_param.eps = params.m_radar_clusterging_config_.eps;
    m_lib_radar_param.weight = params.m_radar_clusterging_config_.weight;
    m_lib_radar_param.mpc = params.m_radar_clusterging_config_.minPointsInCluster;
    m_lib_radar_param.mc = params.m_radar_clusterging_config_.maxClusters;
    m_lib_radar_param.mp = params.m_radar_clusterging_config_.maxPoints;

    m_lib_radar_param.tat = params.m_radar_tracking_config_.trackerAssociationThreshold;
    m_lib_radar_param.mnv = params.m_radar_tracking_config_.measurementNoiseVariance;
    m_lib_radar_param.tpf = params.m_radar_tracking_config_.timePerFrame;
    m_lib_radar_param.iff = params.m_radar_tracking_config_.iirForgetFactor;
    m_lib_radar_param.at = params.m_radar_tracking_config_.trackerActiveThreshold;
    m_lib_radar_param.ft = params.m_radar_tracking_config_.trackerForgetThreshold;
    return m_lib_radar_param;
    
}


/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarSignalProcessingNodeWorker::Impl::process(std::size_t batchIdx){

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
        HVA_DEBUG("Radar Signal Processing node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> RadarSignalProcessingIn =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarSignalProcessingIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarSignalProcessingIn);
        
        hva::hvaVideoFrameWithROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(1));
        // if (!m_isTrackerInitialized) {
        //     radarInit();
        //     m_isTrackerInitialized = true;
        // }

        unsigned tag = ptrFrameBuf->getTag();
        if (!ptrFrameBuf->drop)
        {

            HVA_DEBUG("Radar signal processing start processing %d frame with tag %d", blob->frameId, tag);

            radarVec_t frame_data = ptrFrameBuf->get<radarVec_t>();

            size_t frame_size = ptrFrameBuf->getSize(); // frame_data_size

            HVA_DEBUG("Radar signal processing on frame%d,frame[0]: real %d, imag %d", blob->frameId, (int)frame_data[0].real(), (int)frame_data[0].imag());

            size_t trn = m_radar_config.m_radar_basic_config_.numRx * m_radar_config.m_radar_basic_config_.numTx;
            size_t cn = m_radar_config.m_radar_basic_config_.numChirps;
            size_t sn = m_radar_config.m_radar_basic_config_.adcSamples;
   
            const int maxRadarPointCloudsLen	= m_radar_config.m_radar_clusterging_config_.maxPoints;
            const int maxCluster	= m_radar_config.m_radar_clusterging_config_.maxClusters;
            const int maxTrackerNum	= 64;

            RadarPointClouds rr = {
            .len	    =   0,
            .maxLen	    =   maxRadarPointCloudsLen,
            .rangeIdx   =	nullptr,//(ushort*)ALIGN_ALLOC(64, sizeof(ushort) * maxRadarPointCloudsLen),
            .speedIdx   =	nullptr,//(ushort*)ALIGN_ALLOC(64, sizeof(ushort) * maxRadarPointCloudsLen),
            .range	    =   nullptr,//(float*)ALIGN_ALLOC(64, sizeof(float) * maxRadarPointCloudsLen),
            .speed	    =   nullptr,//(float*)ALIGN_ALLOC(64, sizeof(float) * maxRadarPointCloudsLen),
            .angle	    =   nullptr,//(float*)ALIGN_ALLOC(64, sizeof(float) * maxRadarPointCloudsLen),
            .snr	    =   nullptr//(float*)ALIGN_ALLOC(64, sizeof(float) * maxRadarPointCloudsLen)
            };

            ClusterResult cr =	{
            .n	=   0,
            .idx	=   nullptr,//(int*)ALIGN_ALLOC(64, sizeof(int) * maxCluster),
            .cd	=   nullptr//(ClusterDescription*)ALIGN_ALLOC(64, sizeof(ClusterDescription) * maxCluster)
            };


            for(size_t tr = 0; tr < trn; ++tr){/* cube is organized as tr x c x s */
            for(size_t c = 0; c < cn; ++c){
                cfloat avg = {.real = 0.f, .imag = 0.f};
                for(size_t s = 0; s < sn; ++s){
                cfloat* v   = &(rc.mat[tr * cn * sn + c * sn + s]);
                cfloat* r = reinterpret_cast<cfloat*>(&frame_data[c * trn * sn + tr * sn + s]);
                memcpy(v, r, sizeof(cfloat));
                avg.real    += v->real;
                avg.imag    += v->imag;
                }
                float r = 1.f / sn;
                avg.real *= r;
                avg.imag *= r;
                for(size_t s = 0; s < sn; ++s){
                cfloat* v  = &(rc.mat[tr * cn * sn + c * sn + s]);
                v->real	   -= avg.real;
                v->imag	   -= avg.imag;
                }
            }
            }

            if(radarDetection(m_handle, &rc, &rr) != R_SUCCESS){
                HVA_ERROR("radarDetection failed");
            }

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
            
            if(radarClustering(m_handle, &rr, &cr)!= R_SUCCESS){
                HVA_ERROR("radarClustering failed");
            }

            m_motTracker->RunTracking(m_handle, cr);
            auto tr = m_motTracker->GetRadarTrackingResult();
    
            HVA_DEBUG("Radar signal processing node, point clouds output len %d", rr.len);         
            HVA_DEBUG("Radar signal processing node, clustering output len %d", cr.n);
            HVA_DEBUG("Radar signal processing node, tracking output len %d", tr.len);

            //// rpc output
            pointClouds pointClouds_;
            pointClouds_.num = rr.len;
            if(pointClouds_.num > 0){
                pointClouds_.rangeIdxArray.assign(rr.rangeIdx, rr.rangeIdx + rr.len);
                pointClouds_.rangeFloat.assign(rr.range, rr.range + rr.len);
                pointClouds_.speedIdxArray.assign(rr.speedIdx, rr.speedIdx + rr.len);
                pointClouds_.speedFloat.assign(rr.speed, rr.speed + rr.len);
                pointClouds_.SNRArray.assign(rr.snr, rr.snr + rr.len);
                pointClouds_.aoaVar.assign(rr.angle, rr.angle + rr.len);
            }else{
                HVA_DEBUG("Radar signal processing node, no point clouds output");
            }
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<pointClouds>(pointClouds_, sizeof(pointClouds_));

            // radar clustering output
            clusteringDBscanOutput clusterOutput;
            clusterOutput.numCluster = cr.n;
            clusterOutput.InputArray.assign(cr.idx, cr.idx + cr.n);
            clusterOutput.report.resize(cr.n);
            for(int i=0; i<cr.n; ++i){
                clusterOutput.report[i].numPoints = cr.cd[i].n;
                clusterOutput.report[i].xCenter = cr.cd[i].cx;
                clusterOutput.report[i].yCenter = cr.cd[i].cy;
                clusterOutput.report[i].xSize = cr.cd[i].rx;
                clusterOutput.report[i].ySize = cr.cd[i].ry;
                clusterOutput.report[i].avgVel = cr.cd[i].av;
                clusterOutput.report[i].centerRangeVar = cr.cd[i].vr;
                clusterOutput.report[i].centerAngleVar = cr.cd[i].va;
                clusterOutput.report[i].centerDopplerVar = cr.cd[i].vv;

            }

            hvabuf->setMeta<clusteringDBscanOutput>(clusterOutput);

            trackerOutput output;
            output.outputInfo.resize(tr.len);

            for(int i=0; i<tr.len; ++i){
                output.outputInfo[i].trackerID = tr.td[i].tid;
                output.outputInfo[i].S_hat[0] = tr.td[i].sHat[0];
                output.outputInfo[i].S_hat[1] = tr.td[i].sHat[1];
                output.outputInfo[i].S_hat[2] = tr.td[i].sHat[2];
                output.outputInfo[i].S_hat[3] = tr.td[i].sHat[3];
                output.outputInfo[i].xSize = tr.td[i].rx;
                output.outputInfo[i].ySize = tr.td[i].ry;
            }

            hvabuf->setMeta<trackerOutput>(output);

            hvabuf->setMeta(timeMeta);
            hvabuf->setMeta(m_radar_config);
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);

            auto radarBlob = hva::hvaBlob_t::make_blob();
   
            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);

            HVA_DEBUG("Radar signal processing node sending blob with frameid %u and streamid %u, tag %d", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarSignalProcessingOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarSignalProcessingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarSignalProcessingOut);
            HVA_DEBUG("Radar signal processing node completed sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
      
        }
        else
        {
            pointClouds pcl;
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<pointClouds>(pcl, 0);
            
            clusteringDBscanOutput clusterOutput;
            ptrFrameBuf->setMeta<clusteringDBscanOutput>(clusterOutput);

            trackerOutput output;
            ptrFrameBuf->setMeta<trackerOutput>(output);            
            
            TimeStamp_t time_meta;
            if (ptrFrameBuf->getMeta(time_meta) == hva::hvaSuccess) {
                hvabuf->setMeta(time_meta);
                HVA_DEBUG("Radar signal processing node copied time_meta to next buffer");
            } 
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of TimeStamp_t into hvabuf!");
            }
            hvabuf->frameId = blob->frameId;
            hvabuf->tagAs(tag);
            hvabuf->drop = true;
            auto radarBlob = hva::hvaBlob_t::make_blob();

            radarBlob->frameId = blob->frameId;
            radarBlob->push(hvabuf);
            
            HVA_DEBUG("Radar signal processing node sending blob with frameid %u and streamid %u, tag %d, drop is true", radarBlob->frameId, radarBlob->streamId, hvabuf->getTag());
            m_ctx.sendOutput(radarBlob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarSignalProcessingOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarSignalProcessingOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarSignalProcessingOut);
            HVA_DEBUG("Radar signal processing node sent blob with frameid %u and streamid %u", radarBlob->frameId, radarBlob->streamId);
        }

    }
  
}

void RadarSignalProcessingNodeWorker::Impl::init(){

}

hva::hvaStatus_t RadarSignalProcessingNodeWorker::Impl::rearm(){
    m_motTracker->Reset();
    return hva::hvaSuccess;
}
hva::hvaStatus_t RadarSignalProcessingNodeWorker::Impl::reset(){
    m_motTracker->Reset();
    return hva::hvaSuccess;
}

RadarSignalProcessingNodeWorker::RadarSignalProcessingNodeWorker(hva::hvaNode_t *parentNode, RadarConfigParam m_radar_config): 
        hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this, m_radar_config)) {
    
}

RadarSignalProcessingNodeWorker::~RadarSignalProcessingNodeWorker(){

}

void RadarSignalProcessingNodeWorker::process(std::size_t batchIdx){
    m_impl->process(batchIdx);
}

void RadarSignalProcessingNodeWorker::init(){
    m_impl->init();
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarSignalProcessingNode, RadarSignalProcessingNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
