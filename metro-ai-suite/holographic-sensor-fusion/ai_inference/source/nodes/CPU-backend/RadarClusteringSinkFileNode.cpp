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
#include "nodes/CPU-backend/RadarClusteringSinkFileNode.hpp"
#include "nodes/databaseMeta.hpp"
#include "modules/inference_util/radar/radar_tracking_helper.hpp"

namespace hce{

namespace ai{

namespace inference{
LocalFileManager::LocalFileManager() : m_batchIdx(0) {
}

LocalFileManager::~LocalFileManager() { 
}

void LocalFileManager::init(std::size_t batchIdx) {
    m_batchIdx = batchIdx;
    try
    {
        constructSavePath();

    }
    catch (const std::exception &e)
    {
        HVA_ERROR("Failed to build local_file manager: %s", e.what());
        HVA_ASSERT(false);
    }   
}

/**
 * save results as local file:  {timestamp}.csv
 * each column name should be consist with hvaROI_t
*/

/*  PonintClouds
    int num;
    std::vector<int> rangeIdxArray;
    std::vector<float> rangeFloat;
    std::vector<int> speedIdxArray;
    std::vector<float> speedFloat;

    std::vector<float> SNRArray;
    std::vector<float> aoaVar;

*/

bool LocalFileManager::saveResultsToFile(const unsigned frameId, const clusteringDBscanOutput& output){
                        // const int statusCode, const std::string description){
    std::lock_guard<std::mutex> lg(m_fileMutex);

    // for (size_t idx = 0; idx < rois.size(); idx ++) {
        std::vector<std::pair<std::string, std::vector<std::string>>> resultSetVec;
        // pcl info

        std::vector<std::string> frameIdx;
        std::vector<std::string> ClusteringNum;

        // information in each cluster, put all information into one vector
        std::vector<std::string> numPoints;
        std::vector<std::string> xCenters;
        std::vector<std::string> yCenters;
        std::vector<std::string> xSizes;
        std::vector<std::string> ySizes;
        std::vector<std::string> avgVels;
        std::vector<std::string> vxs;
        std::vector<std::string> vys;
        std::vector<std::string> centerRangeVars;
        std::vector<std::string> centerAngleVars;
        std::vector<std::string> centerDopplerVars;
        frameIdx.push_back(std::to_string(frameId));
        HVA_DEBUG("numCluster: %d",output.numCluster);
        ClusteringNum.push_back(std::to_string(output.numCluster));

        for(int i=0;i<output.numCluster;i++){
            float xCenter = output.report[i].xCenter;
            float yCenter = output.report[i].yCenter;
            float azimuth;
            // if(yCenter > 0){
            //     azimuth = atan(output.report[i].xCenter/output.report[i].yCenter)+ CLUSTERTRACKER_PI/2;
            // }else{
            //     azimuth = atan(output.report[i].yCenter/output.report[i].xCenter);
            // }
            // // float azimuth = atan(output.report[i].xCenter/output.report[i].yCenter);
            // float avgVel = output.report[i].avgVel;
            // float vx = avgVel*cos(azimuth);
            // float vy = avgVel*sin(azimuth);
            // if(avgVel >0){
            //     vx = -vx;
            //     vy = -vy;
            // }
            azimuth = atan2(output.report[i].yCenter,output.report[i].xCenter);
            float vx = output.report[i].avgVel*cos(azimuth);
            float vy = output.report[i].avgVel*sin(azimuth);
            numPoints.push_back(std::to_string(output.report[i].numPoints));
            xCenters.push_back(std::to_string(output.report[i].xCenter));
            yCenters.push_back(std::to_string(output.report[i].yCenter));
            xSizes.push_back(std::to_string(output.report[i].xSize));
            ySizes.push_back(std::to_string(output.report[i].ySize));
            avgVels.push_back(std::to_string(output.report[i].avgVel));
            vxs.push_back(std::to_string(vx));
            vys.push_back(std::to_string(-vy));
            centerRangeVars.push_back(std::to_string(output.report[i].centerRangeVar));
            centerAngleVars.push_back(std::to_string(output.report[i].centerAngleVar));
            centerDopplerVars.push_back(std::to_string(output.report[i].centerDopplerVar));
   
        }
        resultSetVec.push_back(addColumnDataVec("frameId", frameIdx));
        resultSetVec.push_back(addColumnDataVec("ClusteringNum", ClusteringNum));
        resultSetVec.push_back(addColumnDataVec("numPointsInClusters", numPoints));
        resultSetVec.push_back(addColumnDataVec("xCenters", xCenters));
        resultSetVec.push_back(addColumnDataVec("yCenters", yCenters));
        resultSetVec.push_back(addColumnDataVec("xSizes", xSizes));
        resultSetVec.push_back(addColumnDataVec("ySizes", ySizes));
        resultSetVec.push_back(addColumnDataVec("avgVels", avgVels));
        resultSetVec.push_back(addColumnDataVec("vxs", vxs));
        resultSetVec.push_back(addColumnDataVec("vys", vys));
        resultSetVec.push_back(addColumnDataVec("centerRangeVars", centerRangeVars));
        resultSetVec.push_back(addColumnDataVec("centerAngleVars", centerAngleVars));
        resultSetVec.push_back(addColumnDataVec("centerDopplerVars", centerDopplerVars));

        // status code
        // resultSet.push_back(addColumnData("status", std::to_string(statusCode)));
        // resultSet.push_back(addColumnData("description", description));


        // check the folder of result file for the first time
        if (m_firstLine) {
            checkPath(m_resultPath);
        }

        std::ofstream resfile;
        resfile.open(m_resultPath, std::ios::out | std::ios::app);
        if (!resfile.is_open()) {
            HVA_ERROR("Failed to open result file: %s !", m_resultPath.c_str());
            return false;
        }

        // first line: do create csv file and write headers
        if (m_firstLine) {

            // write headers
            std::vector<std::string> vecHeaders(m_headers.size());
            for (auto &item: m_headers) {
                vecHeaders[item.second] = item.first;
            }
            for (auto &header : vecHeaders) {
                resfile << header << ",";
            }
            resfile << "\n";
            m_firstLine = false;
        }

        // fomat contents to the corresponding column index
        bool isHeaderUpdated = false;

        std::vector<std::vector<std::string>> rowDataVec(resultSetVec.size());

        for (auto &item: resultSetVec) {
            std::string key = item.first;

            // insert new header
            if (m_headers.count(key) == 0) {
                isHeaderUpdated = true;
                m_headers.emplace(key, m_headers.size());
            }
            rowDataVec[m_headers[key]] = item.second;
        }
        // start wrting contents
        for (auto &val : rowDataVec) {
            // resfile << val << ",";
            for(auto &innerVal : val){
                resfile << innerVal << " ";
            }
            resfile << ",";
        }
        resfile << "\n";
        resfile.close();

        // 
        // HEADER PATCH: in case of handling non-fixed length of attributes
        // csv headers have been created, re-write first line
        // 
        if (isHeaderUpdated) {
            // generate new header line
            std::vector<std::string> vecHeaders(m_headers.size());
            for (auto &item: m_headers) {
                vecHeaders[item.second] = item.first;
            }
            std::string content;
            for (auto &header : vecHeaders) {
                content += header + ",";
            }

            try {
                // replace the first line with new header content
                replaceLineInFile(m_resultPath, content, 0);
            }
            catch (const std::exception &e)
            {
                HVA_ERROR("Failed to update header line in result file, error: %s", e.what());
                return false;
            }
            catch (...) {
                HVA_ERROR("Failed to update header line in result file: %s", m_resultPath.c_str());
                return false;
            }
        }
    // }

    return true;
}

/**
 * construct save path for each request
*/
void LocalFileManager::reset() {
    m_firstLine = true;
    m_headers.clear();
    constructSavePath();
};

std::string LocalFileManager::getSaveFolder() {
    return m_saveFolder;
};

//
// construct save path using current timestamp
//
void LocalFileManager::constructSavePath() {

    time_t now = time(0);
    tm *ltm = localtime(&now);
    HVA_ASSERT(ltm != NULL);

    auto timeStamp = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now().time_since_epoch()).count();

    char tmp[1024];
    sprintf(tmp, "%s/pipeline_%lu_results_%d-%d-%d-%d:%02d:%02d_%ld", m_saveFolder.c_str(),
            m_batchIdx, 1900 + ltm->tm_year, 1 + ltm->tm_mon, ltm->tm_mday,
            ltm->tm_hour, ltm->tm_min, ltm->tm_sec, timeStamp);

    std::string activeSaveFolder = tmp;

    m_resultPath = activeSaveFolder + "/radarResults.csv";
    HVA_DEBUG("resultPath: %s", m_resultPath.c_str());
    // m_snapshotPath = activeSaveFolder + "/snapshots";
    HVA_INFO("Results for next request will be saved in: %s", activeSaveFolder.c_str());
}

/**
 * @brief check filepath
 * if filepath not exist, check the folder
 * if folder not exist, make the dir
*/
void LocalFileManager::checkPath(const std::string& path) {
    boost::filesystem::path p(path);
    boost::filesystem::path folder = p.parent_path();
    if (!boost::filesystem::exists(folder)) {
        HVA_INFO("Folder not exists, create: %s", folder.c_str());
        boost::filesystem::create_directories(folder.c_str());
    }
}

/**
 * @brief check folder
 * if folder not exist, make the dir
*/
void LocalFileManager::checkFolder(const std::string& path) {
    if (!boost::filesystem::exists(path)) {
        HVA_INFO("Folder not exists, create: %s", path.c_str());
        boost::filesystem::create_directories(path.c_str());
    }
}

/**
 * @brief add new colum data, also add new key into m_headers at the first time (i.e. m_firstLine == true)
 */
std::pair<std::string, std::string> LocalFileManager::addColumnData(std::string key, std::string val) {
    std::pair<std::string, std::string> data = std::make_pair(key, val);
    if (m_firstLine && m_headers.count(key) == 0) {
        m_headers.emplace(key, m_headers.size());
    }
    return data;
}

std::pair<std::string, std::vector<std::string>> LocalFileManager::addColumnDataVec(std::string key, std::vector<std::string> valVec) {
    std::pair<std::string, std::vector<std::string>> data = std::make_pair(key, valVec);
    if (m_firstLine && m_headers.count(key) == 0) {
        m_headers.emplace(key, m_headers.size());
    }
    return data;
}


/**
 * @brief replace a specific line, default as the first line
 * @param filepath the file to be modified
 * @param content the dst line content
 * @param lineIndex index for the line to be replaced
 */
void LocalFileManager::replaceLineInFile(std::string filepath, std::string content, int lineIndex) {
    std::ifstream infile(filepath);
    std::vector<std::string> lines;
    std::string input;
    while (std::getline(infile, input))
        lines.push_back(input);
    infile.close();

    if (lineIndex >= lines.size() || lineIndex < 0) {
        char msg[256];
        sprintf(msg,
                "Failed to replace file at line: %d, total lines: %ld, file "
                "path: %s",
                lineIndex, lines.size(), filepath.c_str());
        throw std::runtime_error(msg);
    }
    lines[lineIndex] = content;

    // replace the original contents
    std::ofstream outfile(filepath, std::ios::trunc);
    for (auto const& line : lines)
        outfile << line << '\n';
    outfile.close();
}

RadarClusteringSinkFileNodeWorker::RadarClusteringSinkFileNodeWorker(hva::hvaNode_t* parentNode, const std::string& bufType):hva::hvaNodeWorker_t(parentNode), 
        m_bufType(bufType){

}

void RadarClusteringSinkFileNodeWorker::process(std::size_t batchIdx){
    std::vector<hva::hvaBlob_t::Ptr> ret = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t> {0});
    
    if(ret.size()){
        HVA_DEBUG("Got ret size.");
        hva::hvaBlob_t::Ptr inBlob = ret[0];
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(inBlob->get(0));

        unsigned tag = buf->getTag();
        HVA_DEBUG("Radar output start processing %d frame with tag %d", inBlob->frameId, tag);
        // inherit meta data from previous input field
        clusteringDBscanOutput output;
        if (buf->containMeta<hce::ai::inference::clusteringDBscanOutput>()) {
            // success
            buf->getMeta(output);
        }
        else {
            // previous node not ever put this type of meta into hvabuf
            HVA_ERROR("Previous node not ever put this type of clusteringDBscanOutput into hvabuf!");
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

        int status_code;
        std::string description;
       
        HVA_DEBUG("output size %d", output.numCluster);

        // if(m_bufType == "String" && buf->get<pointClouds>()){
        if (output.numCluster >0)
        {
            HVA_DEBUG("clusters number: %d", output.numCluster);
            
            // boost::property_tree::ptree clusters;

            m_jsonTree.put("status_code", 0u);
            m_jsonTree.put("description", "succeeded");
            // description = "succeeded";
            m_jsonTree.put("frameId", buf->frameId);
            m_jsonTree.put("num", output.numCluster);

            boost::property_tree::ptree clusters;
            for(int i=0;i<output.numCluster;i++){
                boost::property_tree::ptree cluster;
                cluster.put("numPoints", output.report[i].numPoints);
                cluster.put("xCenter", output.report[i].xCenter);
                cluster.put("yCenter", output.report[i].yCenter);
                cluster.put("xSize", output.report[i].xSize);
                cluster.put("ySize", output.report[i].ySize);
                cluster.put("avgVel", output.report[i].avgVel);
                cluster.put("centerRangeVar", output.report[i].centerRangeVar);
                cluster.put("centerAngleVar", output.report[i].centerAngleVar);
                cluster.put("centerDopplerVar", output.report[i].centerDopplerVar);
                clusters.push_back(std::make_pair("", cluster));

            }
            m_jsonTree.put("latency", latency);
            m_jsonTree.add_child("clusters", clusters);

            m_localFileManager.saveResultsToFile(buf->frameId, output);

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

        dynamic_cast<RadarClusteringSinkFileNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);
        
        HVA_DEBUG("Emit: on frame id %d tag %d",  buf->frameId, buf->getTag());

        if(buf->getTag() == 1){
            HVA_DEBUG("Emit finish on frame id %d", buf->frameId);
            dynamic_cast<RadarClusteringSinkFileNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
        }
        
    }
}

/**
 * @brief Called by hva framework for each video frame, will be called only once before the usual process() being called
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarClusteringSinkFileNodeWorker::processByFirstRun(std::size_t batchIdx){
    m_localFileManager.init(batchIdx);
}


void RadarClusteringSinkFileNodeWorker::processByLastRun(std::size_t batchIdx){
    dynamic_cast<RadarClusteringSinkFileNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
}

RadarClusteringSinkFileNode::RadarClusteringSinkFileNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum), m_bufType("FD"){
    transitStateTo(hva::hvaState_t::configured);

}

hva::hvaStatus_t RadarClusteringSinkFileNode::configureByString(const std::string& config){
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

std::shared_ptr<hva::hvaNodeWorker_t> RadarClusteringSinkFileNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RadarClusteringSinkFileNodeWorker((hva::hvaNode_t*)this, m_bufType));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarClusteringSinkFileNode, RadarClusteringSinkFileNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}
