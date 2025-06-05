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

#include <algorithm>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <opencv2/imgcodecs.hpp>

#include "nodes/CPU-backend/SimpleJpegDecOpenCV.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

SimpleJpegDecOpenCV::SimpleJpegDecOpenCV(std::size_t totalThreadNum)
:hva::hvaNode_t(1, 1, totalThreadNum)
{
    transitStateTo(hva::hvaState_t::configured); 
}

std::shared_ptr<hva::hvaNodeWorker_t> SimpleJpegDecOpenCV::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new SimpleJpegDecOpenCVWorker((hva::hvaNode_t*)this));
}

SimpleJpegDecOpenCVWorker::SimpleJpegDecOpenCVWorker(hva::hvaNode_t* parentNode)
:hva::hvaNodeWorker_t(parentNode)
{
    
}

SimpleJpegDecOpenCVWorker::~SimpleJpegDecOpenCVWorker()
{
    
}

void SimpleJpegDecOpenCVWorker::processByFirstRun(std::size_t batchIdx)
{

}

void SimpleJpegDecOpenCVWorker::processByLastRun(std::size_t batchIdx)
{

}

hva::hvaStatus_t SimpleJpegDecOpenCVWorker::rearm()
{
    //TODO:e.g. reset m_StartFlag or any change on gstreamer state etc.
    HVA_DEBUG("Calling the rearm func.");
    return hva::hvaStatus_t::hvaSuccess;
}

hva::hvaStatus_t SimpleJpegDecOpenCVWorker::reset()
{
    //TODO:e.g. reset m_StartFlag or any change on gstreamer state etc.
    HVA_DEBUG("Calling the reset func.");
    return hva::hvaStatus_t::hvaSuccess;    
}

void SimpleJpegDecOpenCVWorker::init()
{
    return;
}

void SimpleJpegDecOpenCVWorker::deinit()
{
    return;
}

void SimpleJpegDecOpenCVWorker::process(std::size_t batchIdx)
{
    std::vector<std::shared_ptr<hva::hvaBlob_t>> ret = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t> {0});
    if(ret.size() != 0){
        for (const auto& pBlob : ret) {
            unsigned frameIdx = pBlob->frameId;
            // auto buf = pBlob->get(0);
            hva::hvaVideoFrameWithROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(pBlob->get(0));
            unsigned tag = buf->getTag();
            
            HVA_DEBUG(
                "Simple jpeg decoder node %d on blob frameId %u and streamid %u with tag %d",
                batchIdx, pBlob->frameId, pBlob->streamId, buf->getTag());
            std::string tmpJpgStrData = buf->get<std::string>();

            auto jpegBlob = hva::hvaBlob_t::make_blob();

            if(!tmpJpgStrData.empty()){
                std::vector<hva::hvaROI_t> rois;
                if(!buf->rois.empty()){
                    rois = buf->rois;
                    HVA_DEBUG("Jpeg decoder receives a buffer with rois of size %d", buf->rois.size());
                }

                HVA_DEBUG("Jpeg decoder prepares to feed to opencv");
                cv::Mat rawData( 1, tmpJpgStrData.size(), CV_8UC1, (void*)tmpJpgStrData.c_str() );
                cv::Mat decodedImage  =  imdecode( rawData, cv::ImreadModes::IMREAD_COLOR);
                HVA_DEBUG("Jpeg decoder feeding opencv done");

                unsigned width = decodedImage.size().width;
                unsigned height = decodedImage.size().height;
                unsigned channel = decodedImage.channels();

                HVA_DEBUG("Decoded image at width: %d, height: %d and channel: %d", width, height, channel);
                std::string toSend((char*)decodedImage.data, width*height*channel);
                hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf =
                        hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(
                            (uint8_t *)toSend.c_str(), toSend.size());
                hvabuf->frameId = frameIdx;
                hvabuf->width = width;
                hvabuf->height = height;
                hvabuf->stride[0] = channel * width;
                hvabuf->drop = false;
                hvabuf->rois = rois;
                hvabuf->setMeta<uint64_t>(0);
                hvabuf->tagAs(tag);
                jpegBlob->frameId = frameIdx;
                jpegBlob->push(hvabuf);
                
            }
            else{
                HVA_DEBUG("Jpeg decoder receives an empty buf on frame %d", frameIdx);
                hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(NULL, 0);
                hvabuf->frameId = frameIdx;
                hvabuf->width = 0;
                hvabuf->height = 0;
                hvabuf->drop = true;
                hvabuf->setMeta<uint64_t>(0);
                hvabuf->tagAs(tag);
                jpegBlob->frameId = frameIdx;
                jpegBlob->push(hvabuf);
            }
            

            HceDatabaseMeta meta;
            if(buf->getMeta(meta) == hva::hvaSuccess){
                jpegBlob->get(0)->setMeta(meta);
                HVA_DEBUG("Jpeg Decoder copied meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
            }
            
            sendOutput(jpegBlob, 0, std::chrono::milliseconds(0));
        }
    }
    else{
        HVA_WARNING("size got is 0");
    }
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(SimpleJpegDecOpenCV, SimpleJpegDecOpenCV(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}
}
}