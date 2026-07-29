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

#ifndef HCE_AI_INF_LL_RESULT_SINK_FILE_NODE_HPP
#define HCE_AI_INF_LL_RESULT_SINK_FILE_NODE_HPP

#include <mutex>
#include <ctime>
#include <cstdio>
#include <map>
#include <fstream>
#include <boost/filesystem.hpp>
#include <opencv2/imgcodecs.hpp>
#include <boost/exception/all.hpp>
#include <boost/filesystem.hpp>
#include <boost/property_tree/json_parser.hpp>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "nodes/databaseMeta.hpp"
#include "modules/tools/dumper/buffer_dumper.hpp"
#include "common/base64.hpp"
#include "nodes/base/baseResponseNode.hpp"

namespace hce{

namespace ai{

namespace inference{



//
// save results as local file:  {timestamp}.csv, 
// if media_type == `video`, snapshots will be also saved to folder ./snapshot
//
class LocalFileManager{
public:
    LocalFileManager();

    ~LocalFileManager();

    void init(std::size_t batchIdx);

    /**
     * save results as local file:  {timestamp}.csv
     * each column name should be consist with hvaROI_t
    */
    bool saveResultsToFile(const unsigned frameId, const unsigned streamId, 
                           const std::vector<hva::hvaROI_t>& rois, HceDatabaseMeta& meta,
                           const int statusCode, const std::string description);

    /**
     * @brief using opencv to save snapshots for video
    */
    bool saveSnapshotsToFile(const hva::hvaVideoFrameWithROIBuf_t::Ptr& buf, HceDatabaseMeta& meta);

    /**
     * construct save path for each request
    */
    void reset();

    std::string getSaveFolder();

private:

    //
    // construct save path using current timestamp
    //
    void constructSavePath();

    /**
     * @brief check filepath
     * if filepath not exist, check the folder
     * if folder not exist, make the dir
    */
    void checkPath(const std::string& path);

    /**
     * @brief check folder
     * if folder not exist, make the dir
    */
    void checkFolder(const std::string& path);

    /**
     * @brief add new colum data
     */
    std::pair<std::string, std::string> addColumnData(std::string key, std::string val);

    /**
     * @brief replace a specific line, default as the first line
     * @param filepath the file to be modified
     * @param content the dst line content
     * @param lineIndex index for the line to be replaced
     */
    void replaceLineInFile(std::string filepath, std::string content, int lineIndex);

    std::string m_saveFolder = "/opt/hce-core/output_logs/resultsink";

    // to-do: make it configurable
    /**
     * local_storage_configmap.json
     * {
     *      "version": 1,
     *      "saveFolder": "/opt/hce-core/output_logs/resultsink"
     * }
    */
    // const std::string m_configFilePath = "/opt/hce-configs/local_storage_configmap.json";

    std::string m_resultPath;
    std::string m_snapshotPath;
    std::size_t m_batchIdx;

    std::string m_mediaType;

    bool m_firstLine = true;                    // is this first line
    std::mutex m_fileMutex;

    std::unordered_map<std::string, int> m_headers;       // header mapper: {key, column_idx}
};

class HCE_AI_DECLSPEC LLResultSinkFileNodeWorker : public baseResponseNodeWorker{
public:
    LLResultSinkFileNodeWorker(hva::hvaNode_t* parentNode, const std::string& mediaType);

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    virtual void process(std::size_t batchIdx) override;

    /**
    * @brief Called by hva framework for each video frame, will be called only once before the usual process() being called
    * @param batchIdx Internal parameter handled by hvaframework
    */
    virtual void processByFirstRun(std::size_t batchIdx) override;

    hva::hvaStatus_t rearm() override;

    hva::hvaStatus_t reset() override;
private:

    boost::property_tree::ptree m_jsonTree;
    std::string m_mediaType;
    LocalFileManager m_localFileManager;
};

class HCE_AI_DECLSPEC LLResultSinkFileNode : public baseResponseNode{
public:

    LLResultSinkFileNode(std::size_t totalThreadNum);

    ~LLResultSinkFileNode() = default;

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief Constructs and returns a node worker instance: LLResultSinkFileNodeWorker.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual const std::string nodeClassName() const override{ return "LLResultSinkFileNode";};

private: 
    hva::hvaConfigStringParser_t m_configParser;
    std::string m_mediaType;
    
};

}

}

}

#endif //#ifndef HCE_AI_INF_LL_RESULT_SINK_FILE_NODE_HPP