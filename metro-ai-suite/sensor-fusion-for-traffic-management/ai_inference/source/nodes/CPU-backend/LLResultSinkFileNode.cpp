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

#include "modules/tracklet_wrap.hpp"
#include "nodes/CPU-backend/LLResultSinkFileNode.hpp"

namespace hce{

namespace ai{

namespace inference{


//
// save results as local file:  {timestamp}.csv, 
// if media_type == `video`, snapshots will be also saved to folder ./snapshot
//
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
bool LocalFileManager::saveResultsToFile(const unsigned frameId, const unsigned streamId, 
                        const std::vector<hva::hvaROI_t>& rois, HceDatabaseMeta& meta,
                        const int statusCode, const std::string description){
    std::lock_guard<std::mutex> lg(m_fileMutex);

    for (size_t idx = 0; idx < rois.size(); idx ++) {

        std::vector<std::pair<std::string, std::string>> resultSet;

        // frame-level info
        resultSet.push_back(addColumnData("mediaUri", meta.mediaUri));
        resultSet.push_back(addColumnData("mediaTimeStamp", std::to_string(meta.timeStamp)));
        resultSet.push_back(addColumnData("captureSourceId", meta.captureSourceId));
        resultSet.push_back(addColumnData("localFilePath", meta.localFilePath));
        resultSet.push_back(addColumnData("frameId", std::to_string(frameId)));
        resultSet.push_back(addColumnData("streamId", std::to_string(streamId)));

        // roi-level info
        resultSet.push_back(addColumnData("roiId", std::to_string(idx)));
        resultSet.push_back(addColumnData("x", std::to_string(rois[idx].x)));
        resultSet.push_back(addColumnData("y", std::to_string(rois[idx].y)));
        resultSet.push_back(addColumnData("width", std::to_string(rois[idx].width)));
        resultSet.push_back(addColumnData("height", std::to_string(rois[idx].height)));
        resultSet.push_back(addColumnData("labelIdDetection", std::to_string(rois[idx].labelIdDetection)));
        resultSet.push_back(addColumnData("labelDetection", rois[idx].labelDetection));
        resultSet.push_back(addColumnData("confidenceDetection", std::to_string(rois[idx].confidenceDetection)));

        // tracking
        resultSet.push_back(addColumnData("trackingId", std::to_string(rois[idx].trackingId)));
        resultSet.push_back(addColumnData("trackingStatus", vas::ot::TrackStatusToString(rois[idx].trackingStatus)));
       
        // feature dimension: hvaROI_t use labelIdClassification to record feature dimension
        resultSet.push_back(addColumnData("featureDimension", std::to_string(rois[idx].labelIdClassification)));
        resultSet.push_back(addColumnData("featureVector", rois[idx].labelClassification));

        // 
        // to-do: optimize this parsing method
        // Attributes: deal with non-fixed length of attribute model output
        //  > Step 1. extract fixed field: {"type", "color"}
        //  > Step 2. append other fields at the end of the line
        // 
        auto attrs = meta.attributeResult[idx].attr;
        std::unordered_map<std::string, std::pair<std::string, float>> attrMap;
        for (const auto& attr : attrs) {

            std::string label(attr.second.label);
            // replace special character, "," and ";" may cause one more column in the csv file
            while (label.find(",") != std::string::npos) {
                label.replace(label.rfind(","), 1, " |");
            }
            while (label.find(";") != std::string::npos) {
                label.replace(label.rfind(";"), 1, " |");
            }
            attrMap.emplace(attr.first, std::make_pair(label, attr.second.confidence));
        }
        // Attributes: "Step 1. extract fixed field: {"type", "color"}"
        std::vector<std::string> _registered_attributes = {"type", "color"};
        for (const auto& _key : _registered_attributes) {
            if (attrMap.count(_key)) {
                resultSet.push_back(addColumnData(_key, attrMap[_key].first));
                resultSet.push_back(addColumnData(_key + "_score", std::to_string(attrMap[_key].second)));
                attrMap.erase(_key);
            }
            else {
                // dummy data
                resultSet.push_back(addColumnData(_key, ""));
                resultSet.push_back(addColumnData(_key + "_score", "0"));
            }
        }

        // quality-score
        resultSet.push_back(addColumnData("quality_score", std::to_string(meta.qualityResult[idx])));

        // status code
        resultSet.push_back(addColumnData("status", std::to_string(statusCode)));
        resultSet.push_back(addColumnData("description", description));

        // Attributes: "Step 2. append other fields at the end of the line"
        for (const auto& item : attrMap) {
            std::string _key = item.first;
            resultSet.push_back(addColumnData(_key, attrMap[_key].first));
            resultSet.push_back(addColumnData(_key + "_score", std::to_string(attrMap[_key].second)));
        }

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
        auto xx = resultSet.size();
        std::vector<std::string> rowData(resultSet.size());
        for (auto &item: resultSet) {
            std::string key = item.first;

            // insert new header
            if (m_headers.count(key) == 0) {
                isHeaderUpdated = true;
                m_headers.emplace(key, m_headers.size());
            }
            rowData[m_headers[key]] = item.second;
        }
        // start wrting contents
        for (auto &val : rowData) {
            resfile << val << ",";
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
    }

    return true;
}

/**
 * @brief using opencv to save snapshots for video
*/
bool LocalFileManager::saveSnapshotsToFile(const hva::hvaVideoFrameWithROIBuf_t::Ptr& buf, HceDatabaseMeta& meta) {

    checkFolder(m_snapshotPath);

    try
    {
        cv::Mat outputMat;
        if (!tools::dumpBufferImageByCVMat(buf, meta, outputMat)) {
            HVA_ERROR("Failed to dump snapshots");
            return false;
        }
        char snapshotSavePath[1024];
        sprintf(snapshotSavePath, "%s/%06d.jpg", m_snapshotPath.c_str(), buf->frameId);
        cv::imwrite(snapshotSavePath, outputMat);
    }
    catch(std::exception& e)
    {
        // failed to decode
        HVA_ERROR("Failed to decode image from buffer at frameid: %u, error: %s", buf->frameId, e.what());
        return false;
    }

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

    m_resultPath = activeSaveFolder + "/results.csv";
    m_snapshotPath = activeSaveFolder + "/snapshots";
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

LLResultSinkFileNodeWorker::LLResultSinkFileNodeWorker(
    hva::hvaNode_t* parentNode,
    const std::string& mediaType)
    : baseResponseNodeWorker(parentNode), m_mediaType(mediaType) {
    
    m_nodeName = ((LLResultSinkFileNode*)getParentPtr())->nodeClassName();
}

/**
 * @brief Called by hva framework for each video frame, will be called only once before the usual process() being called
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LLResultSinkFileNodeWorker::processByFirstRun(std::size_t batchIdx){
    m_localFileManager.init(batchIdx);
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void LLResultSinkFileNodeWorker::process(std::size_t batchIdx){
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

        m_jsonTree.clear();
        int status_code;
        std::string description;
        
        HceDatabaseMeta meta;
        buf->getMeta(meta);

        hce::ai::inference::TimeStamp_t timeMeta;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;

        inBlob->get(0)->getMeta(timeMeta);
        startTime = timeMeta.timeStamp;
        std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
        endTime = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> latencyDuration = endTime - startTime;
        double latency = latencyDuration.count();
        HVA_DEBUG("Latency: %lf ms", latency);

        HVA_DEBUG("%s receives meta from buffer, mediauri: %s", m_nodeName.c_str(), meta.mediaUri.c_str());

        if(buf->rois.size() != 0){
            status_code = 0u;
            description = "succeeded";
            m_localFileManager.saveResultsToFile(buf->frameId, inBlob->streamId, buf->rois, meta, status_code, description);
            
            HVA_DEBUG("Saved frame %d results", buf->frameId);
        }
        else{
            if(buf->drop){
                status_code = -2;
                description = "Read or decode input media failed";
            }
            else{
                status_code = 1u;
                description = "noRoiDetected";
            }
            // saving empty roi as dummy output
            std::vector<hva::hvaROI_t> empty_roi = {hva::hvaROI_t()};
            m_localFileManager.saveResultsToFile(buf->frameId, inBlob->streamId, empty_roi, meta, status_code, description);
        }
        if (m_mediaType == "video") {
            // save snapshots
            if (!buf->drop) {
                if (!m_localFileManager.saveSnapshotsToFile(buf, meta)) {
                    HVA_ERROR("%s failed to save snapshot at framid: %u and streamid %u", m_nodeName.c_str(), inBlob->frameId, inBlob->streamId);
                }
            }
        }
        m_jsonTree.put("status_code", status_code);
        m_jsonTree.put("description", description);
        m_jsonTree.put("latency", latency);


        std::stringstream ss;
        boost::property_tree::json_parser::write_json(ss, m_jsonTree);

        baseResponseNode::Response res;
        res.status = 0;
        res.message = ss.str();

        HVA_DEBUG("Emit: %s on frameid %d and streamid %u", res.message.c_str(), inBlob->frameId, inBlob->streamId);

        dynamic_cast<LLResultSinkFileNode*>(getParentPtr())->emitOutput(res, (baseResponseNode*)getParentPtr(), nullptr);

        if(buf->getTag() == hvaBlobBufferTag::END_OF_REQUEST){
            dynamic_cast<LLResultSinkFileNode*>(getParentPtr())->addEmitFinishFlag();
            HVA_DEBUG("Receive finish flag on framid %u and streamid %u", inBlob->frameId, inBlob->streamId);
            // reset m_localFileManager for this worker
            m_localFileManager.reset();
        }
    }

    // check whether to trigger emitFinish()
    if (dynamic_cast<LLResultSinkFileNode*>(getParentPtr())->isEmitFinish()) {
        // coming batch processed done
        HVA_DEBUG("Emit finish!");
        dynamic_cast<LLResultSinkFileNode*>(getParentPtr())->emitFinish((baseResponseNode*)getParentPtr(), nullptr);
    }
}

hva::hvaStatus_t LLResultSinkFileNodeWorker::reset(){
    m_localFileManager.reset();
    return hva::hvaSuccess;
}

hva::hvaStatus_t LLResultSinkFileNodeWorker::rearm(){
    m_localFileManager.reset();
    return hva::hvaSuccess;
}

LLResultSinkFileNode::LLResultSinkFileNode(std::size_t totalThreadNum):baseResponseNode(1, 0,totalThreadNum){

}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t LLResultSinkFileNode::configureByString(const std::string& config){
    m_configParser.parse(config);

    m_mediaType = "image";
    m_configParser.getVal<std::string>("MediaType", m_mediaType);
    if (m_mediaType == "video") {
        HVA_DEBUG("resultsink file node will save snapshot for video.");
    }
    else if (m_mediaType == "image") {
        HVA_DEBUG("resultsink file node set to handle image.");
    }
    else {
        HVA_ERROR("Unrecognized media type: %s, only support: image and video currently", m_mediaType.c_str());
        return hva::hvaFailure;
    }

    // after all configures being parsed, this node should be trainsitted to `configured`
    this->transitStateTo(hva::hvaState_t::configured);
    
    return hva::hvaSuccess;
}

std::shared_ptr<hva::hvaNodeWorker_t> LLResultSinkFileNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new LLResultSinkFileNodeWorker((hva::hvaNode_t*)this, m_mediaType));
} 

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LLResultSinkFileNode, LLResultSinkFileNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}

}

}