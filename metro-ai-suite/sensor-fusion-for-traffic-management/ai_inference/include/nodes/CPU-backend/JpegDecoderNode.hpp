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

#ifndef _JPEG_DECODER_NODE_H_
#define _JPEG_DECODER_NODE_H_

#include <iostream>
#include <memory>
#include <thread>
#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaUtil.hpp>

extern "C"
{
#include <libavutil/opt.h>
#include "libavutil/imgutils.h"
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswscale/swscale.h>
};

namespace hce{

namespace ai{

namespace inference{

class JpegDecoderNode : public hva::hvaNode_t{
public:
    JpegDecoderNode(std::size_t totalThreadNum);
    
    /**
    * @brief Constructs and returns a node worker instance: JpegDecoderNodeWorker.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    std::string name();

private:
    std::string m_name;
};

class JpegDecoderNodeWorker : public hva::hvaNodeWorker_t{
public:
    enum encodeType {
        BGR = 1,
        YUV
    };
    JpegDecoderNodeWorker(hva::hvaNode_t* parentNode, std::string name);
    ~JpegDecoderNodeWorker();

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx) override;

    /**
     * @brief to decode images from string buffer
     * @param imageData string buffer
     * @param dst decoded image
     * @param dstWidth decoded image width
     * @param dstHeight decoded image height
     * @param dstBufsize buffer size for decoded image 
     */
    bool decodeImage(std::string& imageData, uint8_t* (&dst)[4], unsigned& dstWidth, unsigned& dstHeight, 
                     int dstLinesize[4], unsigned& dstBufsize);
    
    /**
     * @brief encode BGR image from AVFrame data
     * @param decodedImage input image for encoding
     * @return string buffer for encoded BGR image
     */
    std::string encodeBGRImage(AVFrame* decodedImage); 

    /**
     * @brief encode YUV image from AVFrame data
     * @param pFrame input image for encoding
     * @return string buffer for encoded YUV image
     */
    std::string encodeYUVImage(AVFrame* decodedImage); 

    /**
     * @brief get value of m_EncodeType
     * @return encodeType: RGB=1, YUV=2
     */
    encodeType  getEncodeType();      

    hva::hvaStatus_t rearm() override;
    hva::hvaStatus_t reset() override;

    void init() override;
    void deinit() override;

private:
    uint64_t m_WID;
    std::string m_name;
    bool m_StartFlag;
    encodeType m_EncodeType;
    int m_workStreamId;
};

}

}

}
#endif /*_JPEG_DECODER_NODE_H_*/