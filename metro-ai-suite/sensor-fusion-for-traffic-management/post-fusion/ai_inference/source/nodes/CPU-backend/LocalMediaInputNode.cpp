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

#include <dirent.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <iostream>
#include <thread>
#include <vector>

#include <inc/util/hvaConfigStringParser.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include <boost/exception/all.hpp>

#include "common/base64.hpp"
#include "nodes/CPU-backend/LocalMediaInputNode.hpp"

namespace hce {
namespace ai {

namespace inference {


MediaReader::MediaReader() {
}

MediaReader::~MediaReader() {
  reset();
}

bool MediaReader::init(const std::string& fileName, const std::string& type, const int readBufferSize) {

  m_fileName = fileName;
  m_type = type;
  m_readLength = 0;
  m_bufferSize = readBufferSize;

  HVA_DEBUG("Start reading media buffer from file: %s", m_fileName.c_str());

  // open file
  m_fs.open(m_fileName.c_str(), std::fstream::in);

  if (m_fs) {
    // get length of file
    m_fs.seekg(0, m_fs.end);            // move to end
    m_length = m_fs.tellg();
    m_fs.seekg(0, m_fs.beg);            // move to begin
    return true;
  }
  else {
    HVA_ERROR("fail to open file: %s", m_fileName.c_str());
    return false;
  }
}

void MediaReader::reset() {

  // close file
  if (!m_fileName.empty()) {
    HVA_DEBUG("Close file: %s", m_fileName.c_str());
    m_fs.close();
    m_fileName.clear();
  }
  m_readLength = 0;
    
}

readMediaStatus_t MediaReader::readBufferFromFile(std::string& mediaStr) {
  
  size_t readSize;
  unsigned pos;
  if (m_type == "image" || m_bufferSize < 0) {
    // read the whole file
    readSize = m_length;
    pos = 0;
  }
  else {
    readSize = m_bufferSize;
    pos = m_readLength;
  }

  m_fs.seekg(pos);
  if (m_fs) {

    char* buff = new char[readSize];
    m_fs.read(buff, readSize);
    m_readLength += m_fs.gcount();
    HVA_DEBUG("%d characters read successfully, currently read: %d / %d.", m_fs.gcount(), m_readLength, m_length);

    mediaStr.assign((char*)buff, (char*)buff + m_fs.gcount());

    delete[] buff;
    
    if (m_readLength == m_length) {
      return readMediaStatus_t::Finish;
    }
    else {
      return readMediaStatus_t::Success;
    }
  }
  else {
    if (m_readLength == m_length) {
      // read to the end of file
      return readMediaStatus_t::Finish;
    }
    else {
      // unable to read
      HVA_ERROR("failed to read characters from file: %s, at pos: %d.", m_fileName.c_str(), pos);
      return readMediaStatus_t::Failure;
    }
  }
}


LocalMediaInputNode::LocalMediaInputNode(std::size_t totalThreadNum) : baseMediaInputNode(totalThreadNum) {
}

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t LocalMediaInputNode::configureByString(
    const std::string& config) {
  if (config.empty()) return hva::hvaFailure;

  if (!m_configParser.parse(config)) {
    HVA_ERROR("Illegal parse string!");
    return hva::hvaFailure;
  }

  std::string mediaType;
  m_configParser.getVal<std::string>("MediaType", mediaType);
  if (mediaType.empty()) {
    HVA_ERROR("Must define the media type in config!");
    return hva::hvaFailure;
  }

  int readBufferSize = -1;
  m_configParser.getVal<int>("ReadBufferSize", readBufferSize);

  std::string dataSource = "vehicle";
  m_configParser.getVal<std::string>("DataSource", dataSource);

  m_mediaType = mediaType;
  m_dataSource = dataSource;
  m_readBufferSize = readBufferSize;

  transitStateTo(hva::hvaState_t::configured);
  return hva::hvaSuccess;
}

/**
* @brief Constructs and returns a node worker instance: LocalMediaInputNodeWorker.
* @param void
*/
std::shared_ptr<hva::hvaNodeWorker_t> LocalMediaInputNode::createNodeWorker()
    const {
  return std::shared_ptr<hva::hvaNodeWorker_t>(new LocalMediaInputNodeWorker(
      (hva::hvaNode_t*)this, m_mediaType, m_dataSource, m_readBufferSize));
}

LocalMediaInputNodeWorker::LocalMediaInputNodeWorker(
    hva::hvaNode_t* parentNode, const std::string& mediaType,
    const std::string& dataSource, const int readBufferSize)
    : baseMediaInputNodeWorker(parentNode),
      m_mediaType(mediaType),
      m_dataSource(dataSource),
      m_readBufferSize(readBufferSize) {}

void LocalMediaInputNodeWorker::init() {
  return;
}

/**
 * @brief to process media content from blob
 * @param buf buffer from blob, should be local path
 * @param content acquired media content
 * @param meta HceDatabaseMeta, can be updated
 * @param roi roi region, default be [0, 0, 0, 0]
 */
readMediaStatus_t LocalMediaInputNodeWorker::processMediaContent(const std::string& buf,
                                                    std::string& content,
                                                    HceDatabaseMeta& meta,
                                                    TimeStamp_t& timeMeta,
                                                    hva::hvaROI_t& roi, unsigned order) {
  meta.localFilePath = buf;
  // **Timestamp** is the unix timestamp in ms
  meta.timeStamp = baseMediaInputNodeWorker::generateCurTimeStamp();
  HVA_DEBUG("Success to generate timeStamp: %ld", meta.timeStamp);
  // **Media URI** is the URI of media for structuring.
  if (baseMediaInputNodeWorker::generateMediaURI(m_mediaType, m_dataSource, buf,
                                                 meta.mediaUri)) {
    HVA_DEBUG("Success to generate media URI: %s", meta.mediaUri.c_str());
  }

  // // in LocalFile image mode, string input is: /path/to/image
  // if (!readMediaToBuf(buf, content)) {
  //   HVA_ERROR("LocalFile: %s does not exist!", buf.c_str());
  //   return readMediaStatus_t::Failure;
  // }
  if (order == 0) {
    if (!m_reader.init(buf, m_mediaType, m_readBufferSize)) {
      return readMediaStatus_t::Failure;
    }
  }
  readMediaStatus_t sts = m_reader.readBufferFromFile(content);
  
  unsigned x = 0, y = 0, w = 0, h = 0;
  roi.x = x;
  roi.y = y;
  roi.width = w;
  roi.height = h;

  if (sts == readMediaStatus_t::Finish || sts == readMediaStatus_t::Failure) {
    m_reader.reset();
  }
  return sts;
}
  
/**
 * @brief read media buffer from local file, local file can be image or video, specified by m_mediaType
 * @param fileName local file path
 * @param mediaStr media buffer
*/
bool LocalMediaInputNodeWorker::readMediaToBuf(const std::string& fileName,
                                               std::string& mediaStr) {
  std::fstream fs;
  fs.open(fileName.c_str(), std::fstream::in);
  if (fs) {
    fs.seekg(0, fs.end);
    size_t buffLen = fs.tellg();
    fs.seekg(0, fs.beg);

    char* buff = new char[buffLen];
    fs.read(buff, buffLen);

    if (fs)
      HVA_INFO("all characters read successfully.\n");
    else
      HVA_INFO("error: only %d could be read\n", fs.gcount());

    mediaStr.assign((char*)buff, (char*)buff + buffLen);

    delete[] buff;
  } else {
    fs.close();
    return false;
  }

  fs.close();
  return true;
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(LocalMediaInputNode, LocalMediaInputNode(threadNum))
#endif  //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference
}  // namespace ai
}  // namespace hce
