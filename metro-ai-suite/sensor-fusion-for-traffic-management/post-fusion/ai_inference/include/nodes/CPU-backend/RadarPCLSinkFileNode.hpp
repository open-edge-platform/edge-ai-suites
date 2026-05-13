/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_RADAR_PCL_SINK_FILE_NODE_HPP
#define HCE_AI_INF_RADAR_PCL_SINK_FILE_NODE_HPP

#include <string>

#include <mutex>
#include <ctime>
#include <cstdio>
#include <map>
#include <fstream>
#include <boost/filesystem.hpp>
#include <boost/exception/all.hpp>
#include <boost/filesystem.hpp>
#include <boost/property_tree/json_parser.hpp>

#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

// #include "nodes/databaseMeta.hpp"
#include "common/base64.hpp"

#include <boost/property_tree/json_parser.hpp>

#include <inc/util/hvaConfigStringParser.hpp>

#include "nodes/base/baseResponseNode.hpp"
#include "modules/inference_util/radar/radar_detection_helper.hpp"

namespace hce{

namespace ai{

namespace inference{

class LocalRadarPCLFileManager{
public:
    LocalRadarPCLFileManager();

    ~LocalRadarPCLFileManager();

    void init(std::size_t batchIdx);

    /**
     * save results as local file:  {timestamp}.csv
     * each column name should be consist with hvaROI_t
    */
    bool saveResultsToFile(const unsigned frameId, const struct pointClouds& pcl);

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
    std::pair<std::string, std::vector<std::string>> addColumnDataVec(std::string key, std::vector<std::string> valVec);
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

class HCE_AI_DECLSPEC RadarPCLSinkFileNodeWorker : public hva::hvaNodeWorker_t{
public:
    RadarPCLSinkFileNodeWorker(hva::hvaNode_t* parentNode, const std::string& bufType);

    virtual void process(std::size_t batchIdx) override;

    virtual void processByFirstRun(std::size_t batchIdx) override;

    virtual void processByLastRun(std::size_t batchIdx) override;
private:
    boost::property_tree::ptree m_jsonTree;
    boost::property_tree::ptree m_roi, m_rois;
    boost::property_tree::ptree m_roiData;
    boost::property_tree::ptree m_x, m_y, m_w, m_h;
    LocalRadarPCLFileManager m_localFileManager;
    std::string m_bufType;
};

class HCE_AI_DECLSPEC RadarPCLSinkFileNode : public baseResponseNode{
public:

    RadarPCLSinkFileNode(std::size_t totalThreadNum);

    ~RadarPCLSinkFileNode() = default;

    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override; 

    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    virtual const std::string nodeClassName() const override{ return "RadarPCLSinkFileNode";};

private: 
    std::string m_bufType;

    hva::hvaConfigStringParser_t m_configParser;
};

}

}

}

#endif //#ifndef HCE_AI_INF_RADAR_PCL_SINK_FILE_NODE_HPP