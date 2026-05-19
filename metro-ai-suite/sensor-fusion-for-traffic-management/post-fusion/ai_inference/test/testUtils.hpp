/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <stdlib.h>
#include <time.h>
#include <iostream>
#include <sys/types.h>
#include <dirent.h>
#include <vector>
#include <string.h>
#include <chrono>
#include <thread>
#include <string>
#include <regex>
#include <boost/filesystem.hpp>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/api/hvaPipelineParser.hpp>
#include <common/base64.hpp>
#include <boost/property_tree/json_parser.hpp>

namespace hce{

namespace ai{

namespace inference{

/**
 * @brief construct configure string
 * @param media input vector
 * 
 * @return hva configure str
*/
std::string composeInputFileConfigString(const std::vector<std::string>& media){

    hva::hvaConfigStringParser_t composer;
    composer.setVal("Input", media);

    // serialize hvaConfigStringParser_t to string
    return composer.getConfigString();
}

/**
 * @brief construct image and the corresponding roi as json-style str
 * @param raw base64 encoded image content
 * @param x region of interest: left
 * @param y region of interest: top
 * @param w region of interest: width
 * @param h region of interest: height
 * 
 * @return json-style str for media_input_with_roi
 * description:
 * {
 *     "image": base64EncodedContent,
 *     "roi": [
 *         int,
 *         int,
 *         int,
 *         int
 *     ]
 * }
*/
std::string composeMediaInputWithROI(const std::string& raw, unsigned x, unsigned y, unsigned w, unsigned h){

    // image content
    boost::property_tree::ptree jsonTree;
    jsonTree.add("image", raw);

    boost::property_tree::ptree rois;

    // construct region-of-interest
    boost::property_tree::ptree roi;
    roi.put("", x);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", y);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", w);
    rois.push_back(std::make_pair("", roi));

    roi.clear();
    roi.put("", h);
    rois.push_back(std::make_pair("", roi));
    
    jsonTree.add_child("roi", rois);

    // serialize json-data to string
    std::stringstream ss;
    boost::property_tree::json_parser::write_json(ss, jsonTree);

    return ss.str();
}

/**
 * @brief check if filename ends with ".jpg" suffix
 * @param fileName image path
 * @param target target suffix, default: "", means no filtering
 * 
 * @return boolean on success status
*/
bool CheckPostFix(std::string fileName, std::string target = "")
{
    if (fileName.empty())
    {
        return false;
    }
    
    // check filename, directory is not supported
    int nStartPos = fileName.rfind(".");
    if (nStartPos == -1)
    {
        return false;
    }
 
    // check suffix
    std::string strPostFix = fileName.substr(fileName.rfind("."));
    if (!target.empty() || strPostFix.find(target) != std::string::npos)
    {
        return true;
    }
 
    return false;
}

/**
 * @brief read images and encode as base64 char_buffer
 * @param fileName image path
 * @param jpgStr base64 encoded image content
*/
void readJpgToCharBuffer(const std::string& fileName, std::string& jpgStr)
{
    std::fstream fs;
    fs.open(fileName.c_str(), std::fstream::in);
    if(fs)
    {
        // read image to buffer
        fs.seekg (0, fs.end);
        size_t buffLen = fs.tellg();
        fs.seekg (0, fs.beg);

        char* buff = new char [buffLen];
        fs.read (buff, buffLen);

        if (fs)
            HVA_INFO("all characters read successfully.\n");
        else
            HVA_INFO("error: only %d could be read\n", fs.gcount());

        // use base64 to encode image content
        base64EncodeBufferToString(jpgStr, buff, buffLen);

        delete[] buff;
    }

    fs.close();
}

/**
 * @brief check if path exists
 * @param path should be directory path
 * 
 * @return boolean on success status
*/
bool checkPathExist(const std::string& path) {
    boost::filesystem::path p(path);
    return boost::filesystem::exists(p);
}

/**
 * @brief check if path exists
 * @param path should be directory path
 * 
 * @return boolean on success status
*/
bool checkRegularFile(const std::string& path) {
    boost::filesystem::path p(path);
    return boost::filesystem::is_regular_file(p);
}

/**
 * @brief check if path exists
 * @param path should be directory path
 * 
 * @return boolean on success status
*/
bool checkIsFolder(const std::string& path) {
    return boost::filesystem::is_directory(path);
}

/**
 * @brief read files from directory
 * @param path should be directory path
 * @param mediaVector fed with loaded file path
 * 
 * @return boolean on success status
*/
bool getAllFiles(std::string path, std::vector<std::string>& mediaVector, std::string target = "")
{
    // check directory existence
    if (!checkPathExist(path)) {
        HVA_ERROR("path not exists: %s", path.c_str());
        return false;
    }

    // check directory accessibility
    DIR *pDir;
    if(!(pDir = opendir(path.c_str()))) {
        HVA_ERROR("can not open folder: %s", path.c_str());
        return false;
    }

    // Read files with speficic suffix from the folder, for example: ".jpg"
    // Recursive reading is not supported
    struct dirent* ptr;
    while((ptr = readdir(pDir))!=0)
    {
        if (strcmp(ptr->d_name, ".") != 0 && strcmp(ptr->d_name, "..") != 0)
        {
            if (CheckPostFix(std::string(ptr->d_name), target) == true)
            {
                std::string fileName = path + "/" + ptr->d_name;
                HVA_DEBUG("path: %s", fileName.c_str());
                mediaVector.push_back(fileName);
            }
        }   
    }
    std::sort(mediaVector.begin(), mediaVector.end());

    // remember to close the pDir handle
    closedir(pDir);

    return true;
}

}
}
}