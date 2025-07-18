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
#include <thread>
#include <inttypes.h>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/CPU-backend/RawImageInputNode.hpp"

namespace hce{
namespace ai{

namespace inference{

RawImageInputNode::RawImageInputNode(std::size_t totalThreadNum) : baseMediaInputNode(totalThreadNum) {
    transitStateTo(hva::hvaState_t::configured);
}

/**
 * @brief Constructs and returns a node worker instance: RawImageInputNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> RawImageInputNode::createNodeWorker() const {
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RawImageInputNodeWorker((hva::hvaNode_t*)this));
}

RawImageInputNodeWorker::RawImageInputNodeWorker(hva::hvaNode_t* parentNode)
        :baseMediaInputNodeWorker(parentNode){
}

void RawImageInputNodeWorker::init(){
    return;
}

/**
 * @brief to process media content from blob
 * @param buf buffer from blob, should be raw image string
 * @param content acquired media content
 * @param meta HceDatabaseMeta, can be updated
 * @param roi roi region, default be [0, 0, 0, 0]
 */
readMediaStatus_t RawImageInputNodeWorker::processMediaContent(const std::string& buf, std::string& content, 
                                                     HceDatabaseMeta& meta, TimeStamp_t& timeMeta, hva::hvaROI_t& roi, unsigned order)
{
    unsigned x = 0, y = 0, w = 0, h = 0;

    // in raw image mode, string input is a struct of raw image + rois
    boost::property_tree::ptree jsonTree;

    std::stringstream ss(buf);
    try {
        boost::property_tree::read_json(ss, jsonTree);
    } catch (const boost::property_tree::ptree_error& e){
        HVA_ERROR("Failed to read json message: %s", boost::diagnostic_information(e).c_str());
        return readMediaStatus_t::Failure;
    } catch (boost::exception& e){
        HVA_ERROR("Failed to read json message: %s", boost::diagnostic_information(e).c_str());
        return readMediaStatus_t::Failure;
    }

    std::string base64Image;

    try{
        base64Image = jsonTree.get<std::string>("image");
        auto roiTree = jsonTree.get_child("roi");

        auto iterROI = roiTree.begin();
        x = iterROI->second.get_value<unsigned>();
        ++iterROI;
        y = iterROI->second.get_value<unsigned>();
        ++iterROI;
        w = iterROI->second.get_value<unsigned>();
        ++iterROI;
        h = iterROI->second.get_value<unsigned>();

    } catch (const boost::property_tree::ptree_error& e){
        HVA_ERROR("Failed to read json message: %s", boost::diagnostic_information(e).c_str());
        return readMediaStatus_t::Failure;
    } catch (boost::exception& e){
        HVA_ERROR("Failed to read json message: %s", boost::diagnostic_information(e).c_str());
        return readMediaStatus_t::Failure;
    }

    try{
        content = base64DecodeStrToStr(base64Image);
    }
    catch (boost::exception& e){
        HVA_ERROR("Failed to decoder image: %s", boost::diagnostic_information(e).c_str());
        return readMediaStatus_t::Failure;
    }
    catch (...){
        HVA_ERROR("Attempt to decode a value not in base64 char set!");
        return readMediaStatus_t::Failure;
    }

    roi.x = x;
    roi.y = y;
    roi.width = w;
    roi.height = h;

    return readMediaStatus_t::Finish;
}


#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RawImageInputNode, RawImageInputNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}
}
}
