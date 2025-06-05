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

#include "nodes/CPU-backend/VideoDecoderNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

VideoDecoderNode::VideoDecoderNode(std::size_t totalThreadNum)
    : hva::hvaNode_t(1, 1, totalThreadNum) {
  transitStateTo(hva::hvaState_t::configured);
}

std::shared_ptr<hva::hvaNodeWorker_t> VideoDecoderNode::createNodeWorker()
    const {
  return std::shared_ptr<hva::hvaNodeWorker_t>(new VideoDecoderNodeWorker(
      (hva::hvaNode_t*)this, "VideoDecoderNodeWorkerInstance", m_waitTime));
}

std::string VideoDecoderNode::name() { return m_name; }

/**
* @brief Parse params, called by hva framework right after node instantiate.
* @param config Configure string required by this node.
*/
hva::hvaStatus_t VideoDecoderNode::configureByString(
    const std::string& config) {
  if (config.empty()) return hva::hvaFailure;

  if (!m_configParser.parse(config)) {
    HVA_ERROR("Illegal parse string!");
    return hva::hvaFailure;
  }

  float waitTime = 0;
  m_configParser.getVal<float>("WaitTime", waitTime);
  m_waitTime = waitTime;
  HVA_DEBUG("video decoder node sending frames with wait time: %f s", m_waitTime);

  transitStateTo(hva::hvaState_t::configured);
  return hva::hvaSuccess;
}

VideoDecoderNodeWorker::VideoDecoderNodeWorker(hva::hvaNode_t* parentNode,
                                             std::string name, float waitTime)
    : hva::hvaNodeWorker_t(parentNode),
      m_ctr(0u),
      m_name(name),
      m_StartFlag(false),
      m_waitTime(waitTime),
      m_workStreamId(-1) {}

VideoDecoderNodeWorker::~VideoDecoderNodeWorker() {}

hva::hvaStatus_t VideoDecoderNodeWorker::rearm() {
  HVA_DEBUG("Calling the rearm func.");
  return hva::hvaStatus_t::hvaSuccess;
}

hva::hvaStatus_t VideoDecoderNodeWorker::reset() {
  HVA_DEBUG("Calling the reset func.");
  return hva::hvaStatus_t::hvaSuccess;
}

void VideoDecoderNodeWorker::init() { 
  m_decoderManager.init();
  return; 
}

void VideoDecoderNodeWorker::deinit() { 
  m_decoderManager.deinit();
  return; 
}

/**
 * @brief Frame index increased for every coming frame, will be called at the process()
 * @param void
 */
unsigned VideoDecoderNodeWorker::fetch_increment() { return m_ctr++; }

void VideoDecoderNodeWorker::sendBlob(const hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf, 
                                      const hce::ai::inference::HceDatabaseMeta meta, unsigned streamId) {
   
    // make blob for input
    auto jpegBlob = hva::hvaBlob_t::make_blob();
    if (!jpegBlob) {
        HVA_ERROR("Video decoder make an empty blob!");
        return;
    }

    // frameIdx for blobs should always keep increasing
    jpegBlob->frameId = fetch_increment();
    jpegBlob->streamId = streamId;
    jpegBlob->push(hvabuf);

    //Set the meta attribute
    jpegBlob->get(0)->setMeta(meta);
    HVA_DEBUG("Video Decoder copied meta to next buffer, mediauri: %s",
              meta.mediaUri.c_str());

    HVA_DEBUG("Video Decoder Node sending blob with frameid %u and streamid %u", jpegBlob->frameId, jpegBlob->streamId);
    sendOutput(jpegBlob, 0, std::chrono::milliseconds(0));
    HVA_DEBUG("Video Decoder Node sent blob with frameid %u and streamid %u", jpegBlob->frameId, jpegBlob->streamId);

}

void VideoDecoderNodeWorker::process(std::size_t batchIdx) {
  HVA_DEBUG("Start to video decoder node process");
  std::vector<std::shared_ptr<hva::hvaBlob_t>> vecBlobInput =
      hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx,
                                                       std::vector<size_t>{0});
  HVA_DEBUG("Get the vecBlobInput size is %d", vecBlobInput.size());
  for (const auto& pBlob : vecBlobInput) {

    hva::hvaVideoFrameWithROIBuf_t::Ptr videoBuf =
        std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(pBlob->get(0));

    HVA_DEBUG(
        "Video decoder node %d on blob frameId %u and streamid %u with tag %d",
        batchIdx, pBlob->frameId, pBlob->streamId, videoBuf->getTag());

    // for sanity: check the consistency of streamId, each worker should work on one streamId.
    int streamId = (int)pBlob->streamId;
    if (m_workStreamId >= 0 && streamId != m_workStreamId) {
        HVA_ERROR(
            "Video decoder worker should work on streamId: %d, but received "
            "data from invalid streamId: %d!",
            m_workStreamId, streamId);
        // send output
        videoBuf->drop = true;
        videoBuf->rois.clear();
        HVA_DEBUG("Video decoder sending blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
        sendOutput(pBlob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("Video decoder completed sent blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
        continue;
    } else {
        // the first coming stream decides the workStreamId for this worker
        m_workStreamId = streamId;
    }

    HceDatabaseMeta videoMeta;
    if (videoBuf->getMeta(videoMeta) == hva::hvaSuccess) {
      HVA_DEBUG("Video decoder received meta, mediauri: %s", videoMeta.mediaUri.c_str());
    }

    // Get the video buffer
    std::string tmpVideoStrData = videoBuf->get<std::string>();

    HVA_DEBUG("tmpVideoStrData size is %d", tmpVideoStrData.size());
    if (!tmpVideoStrData.empty()) {
      std::vector<hva::hvaROI_t> rois;
      // Use the origin rois
      if (!videoBuf->rois.empty()) {
        rois = videoBuf->rois;
        HVA_DEBUG("Video decoder receives a buffer with rois of size %d",
                  videoBuf->rois.size());
      }

      // 
      // Use ffmpeg to decode h264
      // 
      HVA_DEBUG("Video decoder prepares to feed to ffmpeg");
      // process start
      HVA_DEBUG("Video decoder start decoding");
      if (!m_decoderManager.startDecode(tmpVideoStrData)) {
          HVA_ASSERT(false);
      }
      
      int decodedCnt = 0;
      int status = 0;
      while (status == 0) {

        // 
        // decode next frame and save to hva::hvaVideoFrameWithROIBuf_t
        //
        hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf = NULL;
        status = m_decoderManager.decodeNext(hvabuf);
        if (hvabuf == NULL) {
            // skip if we can get empty decoded frame but buffer is not end
            continue;
        }
        decodedCnt ++;

        //
        // hvaframework requires frameId starts from 0
        //  different with blob->frameId, frameId for hvabuf in video pipeline, 
        //  it's the relative frame number in one video.
        //              
        hvabuf->rois = rois;
        hvabuf->setMeta<uint64_t>(0);

        // decide buffer tag
        unsigned tag;
        if (status == 1 && videoBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
          // the end of video buffer
          tag = (unsigned)hvaBlobBufferTag::END_OF_REQUEST;
        }
        else {
          tag = (unsigned)hvaBlobBufferTag::NORMAL;
        }
        hvabuf->tagAs(tag);

        // send decoded frame
        videoMeta.bufType = HceDataMetaBufType::BUFTYPE_UINT8;
        sendBlob(hvabuf, videoMeta, pBlob->streamId);
        HVA_DEBUG("This is %d frame, it's status is %d", hvabuf->frameId,
                  hvabuf->getTag());
        
        // Slow down the decode to prevent queue blocking
        sleep(m_waitTime);

      } // is still going

      // Coming the end of video buffer, manage decoder's status
      if (videoBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
            // transit DECODER_BUFFER_EOS -> DECODER_VIDEO_EOS
            m_decoderManager.setState(decodeStatus_t::DECODER_VIDEO_EOS);
            m_decoderManager.deinitDecoder();
            HVA_DEBUG("Video decoder node %d processed %d frames", batchIdx, decodedCnt);
            return;
      }
    } // if (!tmpVideoStrData.empty())
    else {

      HVA_DEBUG("Video decoder receives an empty buf on frame %d", pBlob->frameId);
      hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf =
          hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(NULL, 0);
      hvabuf->frameId = 0;
      hvabuf->width = 0;
      hvabuf->height = 0;
      hvabuf->drop = true;
      hvabuf->setMeta<uint64_t>(0);
      hvabuf->tagAs(videoBuf->getTag());
      HVA_WARNING("Video decoder send empty buffer as the last frame.");

      // send empty blob
      sendBlob(hvabuf, videoMeta, pBlob->streamId);
    }
  }
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(VideoDecoderNode, VideoDecoderNode(threadNum))
#endif  //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference
}  // namespace ai
}  // namespace hce