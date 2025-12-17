/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024-2025 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef _VPL_DECODER_NODE_H_
#define _VPL_DECODER_NODE_H_

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

#include <fcntl.h>
#include <unistd.h>
#ifdef ENABLE_VAAPI
    #include "vaapi_utils.h"
    #include "va_device_manager.h"
    #include "modules/vaapi/utils.hpp"
    #include "modules/vaapi/context.h"
    #include "va/va.h"
    #include "va/va_drm.h"
    #include "vpl/mfxjpeg.h"
    #include "vpl/mfxvideo.h"
    #include "vpl/mfxdispatcher.h"
#endif

#define BITSTREAM_BUFFER_SIZE      2000000
#define SYNC_TIMEOUT               60000
#define MAJOR_API_VERSION_REQUIRED 2
#define MINOR_API_VERSION_REQUIRED 2
#define ALIGN16(value)           (((value + 15) >> 4) << 4)
#define ALIGN32(X)               (((mfxU32)((X) + 31)) & (~(mfxU32)31))
#define VPLVERSION(major, minor) (major << 16 | minor)


namespace hce{

namespace ai{

namespace inference{

typedef struct VPLInitParameters {
    int deviceID;                   // for CPU: -1, for GPU: >= 0
    mfxU32 inCodec;                 // MFX_CODEC_AVC, MFX_CODEC_HEVC

    size_t vppOutHeight;            // VPP output height
    size_t vppOutWidth;             // VPP output width

    mfxU32 vppOutFourCC;            // VPP output Corlor Format
    mfxU16 vppOutChromaFormat;      // VPP output Chroma Format

} VPLInitParameters;

enum decodeStatus_t {
    DECODER_NONE = 0,
    DECODER_PREPARED,
    DECODER_GOING,
    DECODER_BUFFER_EOS,
    DECODER_VIDEO_EOS,
};

class VPLDecoderManager {
public:

    VPLDecoderManager();
    ~VPLDecoderManager();

    bool init(bool useGPU, mfxU32 inCodec, VADisplay vaDisplay);
    void deinit();
    
    /**
     * @brief init decoder
     */
    bool initDecoder(VPLInitParameters vplParam, std::string& buffer);

    /**
     * @brief reset decoder
     * memset bitstream.Data
     * reset RT decoder parameters
     */
    bool resetDecoder(VPLInitParameters vplParam, std::string& buffer);
    
    /**
     * @brief deinit decoder
     */
    void deinitDecoder();

    /**
     * @brief start a decoder, handle different decode status
     */
    bool startDecode(VPLInitParameters vplParam, std::string& buffer);

    /**
     * @brief decode to get next frame data
     */
    bool decodeNext(std::string& buffer, mfxFrameSurface1** pmfxDecOutSurface,
                    mfxFrameSurface1** pmfxVPPSurfacesOut);
    // bool decodeNext(std::string& buffer, mfxFrameSurface1** pmfxDecOutSurface,
    //                 mfxSurfaceArray* pmfxOutSurfaces);

    mfxLoader getLoader();

    mfxSession getSession();

    decodeStatus_t getState();

    decodeStatus_t setState(decodeStatus_t state);

    unsigned getFrameOrder();

    mfxVideoParam getDecodeParams();

    mfxVideoParam getVPPParams();

    bool isVPPUsed();

private:
    
    /**
     * @brief create a VPL session
     */
    bool createVPLSession();

    /**
     * @brief attach EXT VPP param for SFC
     */
    void attachExtParam();

    /**
     * @brief delete EXT VPP param buffers for SFC
     */
    void deleteExtBuffers();

    /**
     * decodeStatus_t str
     */
    std::string decodeStatusToString(decodeStatus_t sts);

    /**
     * @brief prepare decode runtime params
     * m_decodeParams and m_mfxVPPParams will be updated
     */
    bool prepareVideoParam(VPLInitParameters vplParam);

    mfxSession m_session = NULL;
    mfxLoader m_loader = NULL;
    VADisplay m_vaDisplay = nullptr;
    mfxBitstream m_bitstream = {};
    mfxVideoParam m_decodeParams = {};
    mfxVideoParam m_mfxVPPParams = {};
    // mfxVideoChannelParam **m_mfxVPPChParams = nullptr;

    bool m_useGPU;
    mfxU32 m_inCodec;
    bool m_vppUsed = false;
    unsigned m_frameOrder;

    std::vector<mfxExtBuffer*> m_ExtBuffers;

    decodeStatus_t m_state = decodeStatus_t::DECODER_NONE;
};


class VPLDecoderNode : public hva::hvaNode_t{
public:
    VPLDecoderNode(std::size_t totalThreadNum);

    /**
    * @brief Parse params, called by hva framework right after node instantiate.
    * @param config Configure string required by this node.
    */
    virtual hva::hvaStatus_t configureByString(const std::string& config) override;

    /**
    * @brief Constructs and returns a node worker instance: VPLDecoderNodeWorker.
    * @param void
    */
    virtual std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

private:
    hva::hvaConfigStringParser_t m_configParser;
    
    float m_waitTime;
    unsigned int m_decodeInterval;

    VPLInitParameters m_vplParam;
};

class VPLDecoderNodeWorker : public hva::hvaNodeWorker_t{
public:

    VPLDecoderNodeWorker(hva::hvaNode_t* parentNode, VPLInitParameters vplParam, float waitTime, unsigned int decodeInterval);
    ~VPLDecoderNodeWorker();

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

private:
    std::atomic<unsigned> m_ctr;
    bool m_StartFlag;

    // VPL parameters
    VPLInitParameters m_vplParam;
    
    bool m_useGPU;
    hce::ai::inference::ColorFormat m_colorFmt;     // BGR; I420; NV12
    float m_waitTime;
    unsigned int m_decodeInterval;
    int m_workStreamId;

    VADisplay m_vaDisplay = nullptr;
    VAAPIContextPtr m_vaContext = nullptr;

    // mfxSession CreateVPLSession(mfxLoader *loader);
    VPLDecoderManager m_vplDecoderManager;

    void sendEmptyBlob(const hva::hvaBlob_t::Ptr &blob, unsigned tag, unsigned frameId, unsigned streamId);

};

}}}
#endif /*_VPL_DECODER_NODE_H_*/
