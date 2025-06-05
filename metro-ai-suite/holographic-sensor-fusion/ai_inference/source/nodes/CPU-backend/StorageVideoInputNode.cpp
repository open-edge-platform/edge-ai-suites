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

#include <dirent.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <time.h>
#include <iostream>
#include <thread>
#include <vector>

#include <inc/util/hvaConfigStringParser.hpp>

#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/CPU-backend/StorageVideoInputNode.hpp"

namespace hce {
namespace ai {

namespace inference {

StorageVideoInputNode::StorageVideoInputNode(std::size_t totalThreadNum) : baseMediaInputNode(totalThreadNum) {
    transitStateTo(hva::hvaState_t::configured);
}

/**
 * @brief Constructs and returns a node worker instance: StorageImageInputNodeWorker.
 * @param void
 */
std::shared_ptr<hva::hvaNodeWorker_t> StorageVideoInputNode::createNodeWorker() const {
  return std::shared_ptr<hva::hvaNodeWorker_t>(
      new StorageVideoInputNodeWorker((hva::hvaNode_t*)this));
}

StorageVideoInputNodeWorker::StorageVideoInputNodeWorker(
    hva::hvaNode_t* parentNode)
    : baseMediaInputNodeWorker(parentNode) {}

void StorageVideoInputNodeWorker::init() {
  m_configmapFile = "/opt/hce-configs/media_storage_configmap.json";
  m_storageClient = std::unique_ptr<hce::storage::Media_Storage>(
      new hce::storage::Media_Storage());
  m_storageClient->global_init();
  m_storageClient->init(m_configmapFile);
  HVA_DEBUG("Media storage client init using config file at %s",
            m_configmapFile.c_str());
}

/**
 * @brief to process media content from blob
 * @param buf buffer from blob, should be media_uri from video storage
 * @param content acquired media content
 * @param meta HceDatabaseMeta, can be updated
 * @param roi roi region, default be [0, 0, 0, 0]
 */
readMediaStatus_t StorageVideoInputNodeWorker::processMediaContent(const std::string& buf,
                                                       std::string& content,
                                                       HceDatabaseMeta& meta,
                                                       hva::hvaROI_t& roi, unsigned order) {
  meta.mediaUri = buf;

  // read media from storage
  m_storageClient->get_media_string_content_by_URI(buf, content);
  if (content.size() == 0) {
    HVA_ERROR("Failed to read the media content with uri %s", buf.c_str());
    return readMediaStatus_t::Failure;
  }

  // read media meta info from storage
  std::string attrib;
  m_storageClient->get_media_attributes_by_URI(m_configmapFile, buf, attrib);
  HVA_DEBUG("received mediauri attrib: %s", attrib.c_str());
  m_mediaAttribTree.clear();
  if (!attrib.empty()) {
    std::stringstream ss(attrib);
    try {
      boost::property_tree::read_json(ss, m_mediaAttribTree);
      
      /* iterJson consists of a list of values:
       *    ["media_id", "media_uri", "object_name", "media_type_id", "capture_source_id", "size",
       *    "resolution", "fps", "timestamp", "frame_index", "format", "encrypted", "ancester", "roi",
       *    "created_at"] 
       */
      const auto& valuesTree = m_mediaAttribTree.get_child("values");
      const auto& singleValueTree = valuesTree.front().second;
      auto iterJson = singleValueTree.begin();
      for (unsigned i = 0; i < 4; ++i) {
        ++iterJson;
      }
      meta.captureSourceId = iterJson->second.get_value<std::string>();
      HVA_DEBUG("capture source id read is %d", meta.captureSourceId);
      for (unsigned i = 0; i < 4; ++i) {
        ++iterJson;
      }
      meta.timeStamp = iterJson->second.get_value<uint64_t>();
      HVA_DEBUG("timestamp read is %" PRIu64 "", meta.timeStamp);

    } catch (const boost::property_tree::ptree_error& e) {
      HVA_ERROR("Failed to read json media attrib: %s",
                boost::diagnostic_information(e).c_str());
      return readMediaStatus_t::Failure;
    } catch (boost::exception& e) {
      HVA_ERROR("Failed to read json media attrib: %s",
                boost::diagnostic_information(e).c_str());
      return readMediaStatus_t::Failure;
    }

  } else {
    HVA_ERROR("Empty attrib read on mediauri %s!", buf.c_str());
    return readMediaStatus_t::Failure;
  }

  unsigned x = 0, y = 0, w = 0, h = 0;
  roi.x = x;
  roi.y = y;
  roi.width = w;
  roi.height = h;

  return readMediaStatus_t::Finish;
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(StorageVideoInputNode, StorageVideoInputNode(threadNum))
#endif  //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference
}  // namespace ai
}  // namespace hce
