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

#ifndef _VIDEO_DECODER_NODE_H_
#define _VIDEO_DECODER_NODE_H_

#include <iostream>
#include <memory>
#include <thread>
#include <sstream>
#include <algorithm>
#include <inc/api/hvaPipeline.hpp>
#include <inc/util/hvaUtil.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>
#include <inc/util/hvaConfigStringParser.hpp>
#include "nodes/databaseMeta.hpp"
#include "modules/decode_util/video_decode_helper.hpp"

namespace hce{

namespace ai{

namespace inference{

class VideoDecoderNode : public hva::hvaNode_t{
public:
    VideoDecoderNode(std::size_t totalThreadNum);

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief Constructs and returns a node worker instance: VideoDecoderNodeWorker.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

    std::string name();

private:
    hva::hvaConfigStringParser_t m_configParser;
    std::string m_name;
    float m_waitTime;
};

class VideoDecoderNodeWorker : public hva::hvaNodeWorker_t{
public:

    VideoDecoderNodeWorker(hva::hvaNode_t* parentNode, std::string name, float waitTime);
    ~VideoDecoderNodeWorker();

    /**
     * @brief Called by hva framework for each video frame, Run inference and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx) override;

    hva::hvaStatus_t rearm() override;
    hva::hvaStatus_t reset() override;

    void init() override;
    void deinit() override;
    
    /**
     * @brief Frame index increased for every coming frame, will be called at the process()
     * @param void
     */
    unsigned fetch_increment();

    /**
     * @brief send blob to downstream nodes given hvabuf and meta data
    */
    void sendBlob(const hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf, 
                  const hce::ai::inference::HceDatabaseMeta meta, unsigned streamId);

private:
    std::atomic<unsigned> m_ctr;
    std::string m_name;
    bool m_StartFlag;
    float m_waitTime;
    FFmpegDecoderManager m_decoderManager;      // use FFmpegDecoderManager to manage decoder lifecycle
    int m_workStreamId;

};
}}}
#endif /*_VIDEO_DECODER_NODE_H_*/