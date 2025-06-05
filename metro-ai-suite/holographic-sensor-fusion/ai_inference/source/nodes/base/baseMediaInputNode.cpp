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
#include "nodes/base/baseMediaInputNode.hpp"

namespace hce {
namespace ai {

namespace inference {

baseMediaInputNode::baseMediaInputNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum) {}

baseMediaInputNode::~baseMediaInputNode() {}

hva::hvaStatus_t baseMediaInputNode::rearm() {
  return hva::hvaSuccess;
}

hva::hvaStatus_t baseMediaInputNode::reset() {
  return hva::hvaSuccess;
}

baseMediaInputNodeWorker::baseMediaInputNodeWorker(hva::hvaNode_t* parentNode)
    : hva::hvaNodeWorker_t(parentNode), m_ctr(0u), m_workStreamId(-1) {}

void baseMediaInputNodeWorker::init() { return; }

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void baseMediaInputNodeWorker::process(std::size_t batchIdx) {
  // get input blob from port0
  auto vecBlobInput = getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
  for (const auto& inBlob : vecBlobInput) {
    HVA_DEBUG("Input node %d on frameId %u and streamid %u", batchIdx, inBlob->frameId, inBlob->streamId);
    hva::hvaBuf_t::Ptr buf = inBlob->get(0);

    // for sanity: check the consistency of streamId, each worker should work on one streamId.
    int streamId = (int)inBlob->streamId;
    if (m_workStreamId >= 0 && streamId != m_workStreamId) {
      HVA_ERROR(
          "Input worker should work on streamId: %d, but received "
          "data from invalid streamId: %d!",
          m_workStreamId, streamId);
      // send output
      sendEmptyBuf(inBlob, 1);
      return;
    } else {
      // the first coming stream decides the workStreamId for this worker
      m_workStreamId = streamId;
    }
    
    auto comingMedias = buf->get<BatchedMedias>();

    // processing multiple coming medias, each send as one blob
    for (auto iter = comingMedias.begin(); iter != comingMedias.end();) {

      // the last request input will be tag as end
      bool isEnd = (iter == comingMedias.end() - 1);

      /**
       * process media content
       */
      readMediaStatus_t sts = readMediaStatus_t::Success;
      unsigned order = 0;
      // read buffers may be read piece by piece
      while (sts == readMediaStatus_t::Success) {

        // new blobs
        auto blob = hva::hvaBlob_t::make_blob();
        blob->streamId = inBlob->streamId;    // inherit
        blob->frameId = fetch_increment();
        HVA_DEBUG("Input node %d generate frameId %u and streamid %u", batchIdx, blob->frameId, blob->streamId);

        std::string mediaContent;
        HceDatabaseMeta meta;
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
        currentTime = std::chrono::high_resolution_clock::now();
        TimeStamp_t timeMeta;
        timeMeta.timeStamp = currentTime;
        hva::hvaROI_t roi;

        sts = processMediaContent(*iter, mediaContent, meta, timeMeta,roi, order);
        if (sts == readMediaStatus_t::Failure) {
          HVA_ERROR("Failed to read the media content with input_buf: %s",
                    iter->c_str());
          sendEmptyBuf(blob, isEnd, meta);
          continue;
        }
        order += 1;

        std::size_t mediaSize = mediaContent.size();
        if (mediaSize == 0 && order == 0) {
          HVA_ERROR("Failed to read the media content with input_buf: %s",
                    iter->c_str());
          sendEmptyBuf(blob, isEnd, meta);
          continue;
        }

        HVA_DEBUG("media content size is : %d on frameid %d streamid %d",
                  mediaSize, blob->frameId, blob->streamId);
        HVA_DEBUG("specified is : [%d, %d, %d, %d], on frameid %d streamid %d",
                  roi.x, roi.y, roi.width, roi.height, blob->frameId,
                  blob->streamId);

        auto jpgHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<std::string>(
            mediaContent, mediaSize);
        jpgHvaBuf->rois.push_back(std::move(roi));

        // decide buffer tag
        unsigned tag;
        if (isEnd && sts == readMediaStatus_t::Finish) {
          // last one in the batch. Mark it
          tag = (unsigned)hvaBlobBufferTag::END_OF_REQUEST;
          HVA_DEBUG("Set tag %s on frame %d", buffertag_to_string(tag).c_str(), blob->frameId);
        } else {
          tag = (unsigned)hvaBlobBufferTag::NORMAL;
        }
        meta.bufType = HceDataMetaBufType::BUFTYPE_STRING;
        jpgHvaBuf->tagAs(tag);
        jpgHvaBuf->setMeta(meta);
        jpgHvaBuf->setMeta(timeMeta);
        HVA_DEBUG("Media input source node sets meta to buffer");

        blob->push(jpgHvaBuf);
        sendOutput(blob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("Push the %d th jpeg data to blob", blob->frameId);

      } // while (sts == readMediaStatus_t::Success)

      iter = comingMedias.erase(iter);
    }

    // never fire a EOS in HCE usecase!
  }
}

/**
 * @brief Send empty buf to next node
 * @param blob input blob data with empty buf
 * @param isEnd flag for coming request
 * @param meta databaseMeta
 */
void baseMediaInputNodeWorker::sendEmptyBuf(hva::hvaBlob_t::Ptr blob,
                                            bool isEnd,
                                            const HceDatabaseMeta& meta) {
  blob->vBuf.clear();
  auto jpgHvaBuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<std::string>(
      std::string(), 0);

  // drop mark as true for empty blob
  jpgHvaBuf->drop = true;
  jpgHvaBuf->setMeta(meta);

  if (isEnd) {
    // last one in the batch. Mark it
    HVA_DEBUG("Set tag 1 on frame %d", blob->frameId);
    jpgHvaBuf->tagAs(1);
  } else {
    jpgHvaBuf->tagAs(0);
  }

  blob->push(jpgHvaBuf);
  sendOutput(blob, 0, std::chrono::milliseconds(0));
}
/**
 * @brief Frame index increased for every coming frame, will be called at the process()
 * @param void
 */
unsigned baseMediaInputNodeWorker::fetch_increment() { return m_ctr++; }

hva::hvaStatus_t baseMediaInputNodeWorker::rearm() {
  // TODO:e.g. reset m_StartFlag or any change on gstreamer state etc.
  HVA_DEBUG("Calling the rearm func.");
  return hva::hvaStatus_t::hvaSuccess;
}

hva::hvaStatus_t baseMediaInputNodeWorker::reset() {
  // TODO:e.g. reset m_StartFlag or any change on gstreamer state etc.
  HVA_DEBUG("Calling the reset func.");
  return hva::hvaStatus_t::hvaSuccess;
}

/**
 * @brief generate media_uri with respect to `media_type` and `data_source`
 * @param mediaType video or image
 * @param dataSource vehicle
 * @param URI generated uri, schema: Hash(media_type,4) + Hash(data_source,4) + content(32)
 */
bool baseMediaInputNodeWorker::generateMediaURI(const std::string& mediaType,
                                                const std::string& datasource,
                                                const std::string& content,
                                                std::string& URI) {
  // schema: Hash(media_type,4) + Hash(data_source,4) + content(32)
  try {
    std::hash<std::string> str_hash;
    URI = (std::to_string(str_hash(mediaType)).substr(0, 4) +
           std::to_string(str_hash(datasource)).substr(0, 4));

    std::string content_hash = std::to_string(str_hash(content));
    URI +=
        (content_hash + std::to_string(str_hash(content_hash))).substr(0, 32);
  } catch (const std::exception& e) {
    HVA_ERROR("Failed to generate media URI: %s", e.what());
    return false;
  }
  return true;
}
/**
 * Timestamp is the unix timestamp in ms
 */
uint64_t baseMediaInputNodeWorker::generateCurTimeStamp() {
  timeb t;
  ftime(&t);
  uint64_t timeStamp = t.time * 1000 + t.millitm;
  return timeStamp;
}

}  // namespace inference
}  // namespace ai
}  // namespace hce
