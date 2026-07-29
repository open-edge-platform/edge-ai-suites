/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2024 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <boost/filesystem.hpp>

#include "nodes/GPU-backend/VPLDecoderNode.hpp"

namespace hce {

namespace ai {

namespace inference {

VPLDecoderManager::VPLDecoderManager() : m_frameOrder(0u) {}

VPLDecoderManager::~VPLDecoderManager()
{
    // deinitDecoder();
    deinit();
}

mfxLoader VPLDecoderManager::getLoader()
{
    return m_loader;
}

mfxSession VPLDecoderManager::getSession()
{
    return m_session;
}

decodeStatus_t VPLDecoderManager::getState()
{
    return m_state;
}

decodeStatus_t VPLDecoderManager::setState(decodeStatus_t state)
{
    HVA_DEBUG("VPL Decoder state transit to %s", decodeStatusToString(state).c_str());
    return m_state = state;
}

unsigned VPLDecoderManager::getFrameOrder()
{
    // starts from 0
    return m_frameOrder - 1;
}

mfxVideoParam VPLDecoderManager::getDecodeParams()
{
    return m_decodeParams;
}

mfxVideoParam VPLDecoderManager::getVPPParams()
{
    return m_mfxVPPParams;
}

bool VPLDecoderManager::isVPPUsed()
{
    return m_vppUsed;
}

bool VPLDecoderManager::init(bool useGPU, mfxU32 inCodec, VADisplay vaDisplay)
{
    HVA_DEBUG("init VPL session.");
    m_useGPU = useGPU;
    m_inCodec = inCodec;
    m_vaDisplay = vaDisplay;
    return createVPLSession();
}

/**
 * @brief deinit VPL decoder context
 */
void VPLDecoderManager::deinit()
{
    // HVA_DEBUG("deinit VPL session.");
    // TODO

    // Clean up resources - It is recommended to close components first, before
    // releasing allocated surfaces, since some surfaces may still be locked by
    // internal resources.
    if (m_session) {
        MFXClose(m_session);
        m_session = nullptr;
    }

    if (m_loader) {
        MFXUnload(m_loader);
        m_loader = nullptr;
    }

    if (m_bitstream.Data) {
        free(m_bitstream.Data);
        m_bitstream = {};
    }

    m_frameOrder = 0;
    m_vppUsed = false;
    m_decodeParams = {};
    m_mfxVPPParams = {};

    m_state = decodeStatus_t::DECODER_NONE;
}

/**
 * @brief init decoder
 */
bool VPLDecoderManager::initDecoder(VPLInitParameters vplParam, std::string &buffer)
{
    HVA_DEBUG("init VPL decoder.");

    mfxStatus sts = MFX_ERR_NONE;
    m_bitstream = {};
    m_frameOrder = 0;

    // Prepare input bitstream and start decoding
    m_bitstream.MaxLength = BITSTREAM_BUFFER_SIZE;
    m_bitstream.Data = reinterpret_cast<mfxU8 *>(calloc(m_bitstream.MaxLength, sizeof(mfxU8)));
    if (!m_bitstream.Data) {
        HVA_ERROR("Error allocating bitstream");
        return false;
    }
    m_bitstream.CodecId = m_inCodec;

    // Pre-parse input stream
    sts = ReadEncodedStreamFromBuffer(m_bitstream, buffer);
    if (sts != MFX_ERR_NONE) {
        HVA_ERROR("Error reading bitstream");
        return false;
    }

    // prepare decode runtime params
    // m_decodeParams and m_mfxVPPParams will be updated
    if (!prepareVideoParam(vplParam)) {
        HVA_DEBUG("Error preparing mfxVideoParam");
        return false;
    }

    // Initialize decoder
    sts = MFXVideoDECODE_Init(m_session, &m_decodeParams);
    if (sts != MFX_ERR_NONE) {
        HVA_ERROR("Error initializing decoder");
        return false;
    }

    if (m_vppUsed) {
        // Initialize VPP to do resize post-process
        sts = MFXVideoVPP_Init(m_session, &m_mfxVPPParams);
        if (sts != MFX_ERR_NONE) {
            HVA_ERROR("Error initializing vpp %d", sts);
            return false;
        }
    }

    m_state = decodeStatus_t::DECODER_PREPARED;
    return true;
}

/**
 * @brief reset decoder
 * memset bitstream.Data
 * reset RT decoder parameters
 */
bool VPLDecoderManager::resetDecoder(VPLInitParameters vplParam, std::string &buffer)
{
    HVA_DEBUG("reset VPL decoder.");

    if (!(m_state == decodeStatus_t::DECODER_VIDEO_EOS)) {
        HVA_ERROR("ERR - decoder state: %s (DECODER_VIDEO_EOS is required), still reset decoder!", decodeStatusToString(m_state).c_str());
        HVA_ASSERT(false);
    }

    mfxStatus sts = MFX_ERR_NONE;
    m_frameOrder = 0;

    // Prepare input bitstream and start decoding
    memset(m_bitstream.Data, 0, m_bitstream.MaxLength);

    // Pre-parse input stream
    sts = ReadEncodedStreamFromBuffer(m_bitstream, buffer);
    if (sts != MFX_ERR_NONE) {
        HVA_ERROR("Error reading bitstream");
        return false;
    }

    // prepare decode runtime params
    // m_decodeParams and m_mfxVPPParams will be updated
    if (!prepareVideoParam(vplParam)) {
        HVA_DEBUG("Error preparing mfxVideoParam");
        return false;
    }

    // reset decoder and vpp
    MFXVideoDECODE_Reset(m_session, &m_decodeParams);
    if (m_vppUsed) {
        MFXVideoVPP_Reset(m_session, &m_mfxVPPParams);
    }

    m_state = decodeStatus_t::DECODER_PREPARED;
    return true;
}

/**
 * @brief deinit decoder
 */
void VPLDecoderManager::deinitDecoder()
{
    // HVA_DEBUG("deinit VPL decoder.");

    // if (!(m_state == decodeStatus_t::DECODER_VIDEO_EOS ||
    //       m_state == decodeStatus_t::DECODER_NONE)) {
    //     HVA_WARNING("WARN - decoder state: %s, still deinit decoder!",
    //                 decodeStatusToString(m_state).c_str());
    // }

    // close decoder and vpp
    MFXVideoDECODE_Close(m_session);
    if (m_vppUsed) {
        MFXVideoVPP_Close(m_session);
    }

    if (m_bitstream.Data) {
        free(m_bitstream.Data);
        m_bitstream = {};
    }

    m_frameOrder = 0;
    m_vppUsed = false;
    m_decodeParams = {};
    m_mfxVPPParams = {};

    m_state = decodeStatus_t::DECODER_NONE;
}

/**
 * @brief create a VPL session
 */
bool VPLDecoderManager::createVPLSession()
{
    mfxStatus sts = MFX_ERR_NONE;

    // Initialize VPL session
    m_loader = MFXLoad();
    if (m_loader == NULL) {
        HVA_ERROR("MFXLoad failed -- is implementation in path?");
        return false;
    }

    if (m_useGPU) {
        // Check: Implementation used must be the type requested from HW
        {
            mfxConfig cfg;
            mfxVariant cfgVal;
            cfg = MFXCreateConfig(m_loader);
            cfgVal.Type = MFX_VARIANT_TYPE_U32;
            cfgVal.Data.U32 = MFX_IMPL_TYPE_HARDWARE;
            sts = MFXSetConfigFilterProperty(cfg, (mfxU8 *)"mfxImplDescription.Impl", cfgVal);
            if (sts != MFX_ERR_NONE) {
                HVA_ERROR("MFXSetConfigFilterProperty failed for HW decoder");
                return false;
            }
        }

        // // Check: Implementation used must be MFX_GPUCOPY_ON
        // {
        //     mfxConfig cfg;
        //     mfxVariant cfgVal;
        //     cfg = MFXCreateConfig(m_loader);
        //     cfgVal.Type     = MFX_VARIANT_TYPE_U16;
        //     cfgVal.Data.U16 = MFX_GPUCOPY_ON;
        //     sts =
        //         MFXSetConfigFilterProperty(cfg, (mfxU8 *)"DeviceCopy", cfgVal);
        //     if (sts != MFX_ERR_NONE) {
        //         HVA_ERROR("MFXSetConfigFilterProperty failed for GPU Copy ON");
        //         return false;
        //     }
        // }
    }
    else {
        // Check: Implementation used must be the type requested from SW
        {
            mfxConfig cfg;
            mfxVariant cfgVal;
            cfg = MFXCreateConfig(m_loader);
            cfgVal.Type = MFX_VARIANT_TYPE_U32;
            cfgVal.Data.U32 = MFX_IMPL_TYPE_SOFTWARE;
            sts = MFXSetConfigFilterProperty(cfg, (mfxU8 *)"mfxImplDescription.Impl", cfgVal);
            if (sts != MFX_ERR_NONE) {
                HVA_ERROR("MFXSetConfigFilterProperty failed for SW decoder");
                return false;
            }
        }
    }

    // Check: Implementation must provide a decoder for h264 or h265
    {
        mfxConfig cfg;
        mfxVariant cfgVal;
        cfg = MFXCreateConfig(m_loader);
        cfgVal.Type = MFX_VARIANT_TYPE_U32;
        cfgVal.Data.U32 = m_inCodec;
        sts = MFXSetConfigFilterProperty(cfg, (mfxU8 *)"mfxImplDescription.mfxDecoderDescription.decoder.CodecID", cfgVal);
        if (sts != MFX_ERR_NONE) {
            HVA_ERROR("MFXSetConfigFilterProperty failed for decoder CodecID");
            return false;
        }
    }

    // {
    //     // Implementation used must have VPP scaling capability
    //     mfxConfig cfg;
    //     mfxVariant cfgVal;
    //     cfg = MFXCreateConfig(m_loader);
    //     cfgVal.Type     = MFX_VARIANT_TYPE_U32;
    //     cfgVal.Data.U32 = MFX_EXTBUFF_VPP_SCALING;
    //     sts             = MFXSetConfigFilterProperty(
    //         cfg,
    //         (mfxU8 *)"mfxImplDescription.mfxVPPDescription.filter.FilterFourCC",
    //         cfgVal);
    //     if (sts != MFX_ERR_NONE) {
    //         HVA_ERROR("ERROR: MFXSetConfigFilterProperty failed for VPP scale");
    //         return false;
    //     }
    // }

    // {
    //     // Implementation used must have VPP CSC capability
    //     mfxConfig cfg;
    //     mfxVariant cfgVal;
    //     cfg = MFXCreateConfig(m_loader);
    //     cfgVal.Type     = MFX_VARIANT_TYPE_U32;
    //     cfgVal.Data.U32 = MFX_EXTBUFF_VPP_COLOR_CONVERSION;
    //     sts             = MFXSetConfigFilterProperty(
    //         cfg,
    //         (mfxU8 *)"mfxImplDescription.mfxVPPDescription.filter.FilterFourCC",
    //         cfgVal);
    //     if (sts != MFX_ERR_NONE) {
    //         HVA_ERROR("ERROR: MFXSetConfigFilterProperty failed for VPP CSC");
    //         return false;
    //     }
    // }

    // create a new session with implementation i
    sts = MFXCreateSession(m_loader, 0, &m_session);
    if (sts != MFX_ERR_NONE) {
        HVA_ERROR("Cannot create VPL session");
        return false;
    }

    // Print info about implementation loaded
    ShowImplInfo(m_session);

    // initialize available accelerator(s)
    if (m_useGPU && m_vaDisplay != nullptr) {
        MFXVideoCORE_SetHandle(m_session, static_cast<mfxHandleType>(MFX_HANDLE_VA_DISPLAY), m_vaDisplay);
        // HVA_DEBUG("VADisplay addr: %p", m_vaDisplay);
    }
    return true;
}

/**
 * decodeStatus_t str
 */
std::string VPLDecoderManager::decodeStatusToString(decodeStatus_t sts)
{
    switch (sts) {
        case decodeStatus_t::DECODER_NONE: return "DECODER_NONE";
        case decodeStatus_t::DECODER_PREPARED: return "DECODER_PREPARED";
        case decodeStatus_t::DECODER_GOING: return "DECODER_GOING";
        case decodeStatus_t::DECODER_BUFFER_EOS: return "DECODER_BUFFER_EOS";
        case decodeStatus_t::DECODER_VIDEO_EOS: return "DECODER_VIDEO_EOS";
        default: break;
    }

    std::string ret("<unknown ");
    ret += std::to_string(sts) + ">";
    return ret;
}

/**
 * @brief prepare decode runtime params
 * m_decodeParams and m_mfxVPPParams will be updated
 */
bool VPLDecoderManager::prepareVideoParam(VPLInitParameters vplParam)
{
    HVA_DEBUG("prepare mfxVideoParam.");

    mfxStatus sts = MFX_ERR_NONE;

    if (!m_bitstream.Data) {
        HVA_ERROR("bitstream should be initialized before preparing MFXVideoParam");
        return false;
    }

    // Initialize decode parameters
    m_decodeParams.mfx.CodecId = m_inCodec;
    m_decodeParams.IOPattern = m_useGPU ? MFX_IOPATTERN_OUT_VIDEO_MEMORY : MFX_IOPATTERN_OUT_SYSTEM_MEMORY;
    sts = MFXVideoDECODE_DecodeHeader(m_session, &m_bitstream, &m_decodeParams);
    if (sts != MFX_ERR_NONE) {
        HVA_DEBUG("status %s", sts);
        HVA_ERROR("Error decoding header");
        return false;
    }

    // prepare decode params
    if (m_decodeParams.mfx.CodecId == MFX_CODEC_JPEG) {
        m_decodeParams.mfx.FrameInfo.Height = ALIGN16(m_decodeParams.mfx.FrameInfo.Height);
        m_decodeParams.mfx.FrameInfo.Width = ALIGN16(m_decodeParams.mfx.FrameInfo.Width);
    }
    size_t oriImgWidth = m_decodeParams.mfx.FrameInfo.Width;
    size_t oriImgHeight = m_decodeParams.mfx.FrameInfo.Height;
    m_decodeParams.mfx.FrameInfo.FrameRateExtN = 30;
    m_decodeParams.mfx.FrameInfo.FrameRateExtD = 1;

    // prepare vpp params (if need)
    bool do_vppResize = false, do_vppCSC = false;
    if (vplParam.vppOutWidth > 0 && vplParam.vppOutHeight > 0 && (oriImgWidth != vplParam.vppOutWidth || oriImgHeight != vplParam.vppOutHeight)) {
        do_vppResize = true;
        HVA_DEBUG("VPP received resize parameters: [%d, %d] => [%d, %d]", oriImgHeight, oriImgWidth, vplParam.vppOutHeight, vplParam.vppOutWidth);
    }
    else {
        do_vppResize = false;
        vplParam.vppOutWidth = oriImgWidth;
        vplParam.vppOutHeight = oriImgHeight;
    }
    if (vplParam.vppOutFourCC != m_decodeParams.mfx.FrameInfo.FourCC) {
        do_vppCSC = true;
        HVA_DEBUG("VPP received CSC parameters: %s => %s", mfxColorFourCC_to_string(m_decodeParams.mfx.FrameInfo.FourCC).c_str(),
                  mfxColorFourCC_to_string(vplParam.vppOutFourCC).c_str());
    }
    if (do_vppResize || do_vppCSC) {
        // Initialize VPP to do resize post-process
        m_vppUsed = true;

        // m_mfxVPPParams.vpp.In = m_decodeParams.mfx.FrameInfo;
        m_mfxVPPParams.vpp.In.FourCC = m_decodeParams.mfx.FrameInfo.FourCC;
        m_mfxVPPParams.vpp.In.ChromaFormat = vplParam.vppOutChromaFormat;
        m_mfxVPPParams.vpp.In.Width = oriImgWidth;
        m_mfxVPPParams.vpp.In.Height = oriImgHeight;
        m_mfxVPPParams.vpp.In.CropW = oriImgWidth;
        m_mfxVPPParams.vpp.In.CropH = oriImgHeight;
        m_mfxVPPParams.vpp.In.PicStruct = MFX_PICSTRUCT_PROGRESSIVE;
        m_mfxVPPParams.vpp.In.FrameRateExtN = m_decodeParams.mfx.FrameInfo.FrameRateExtN;
        m_mfxVPPParams.vpp.In.FrameRateExtD = m_decodeParams.mfx.FrameInfo.FrameRateExtD;
        m_mfxVPPParams.vpp.Out.FourCC = vplParam.vppOutFourCC;
        m_mfxVPPParams.vpp.Out.ChromaFormat = vplParam.vppOutChromaFormat;
        m_mfxVPPParams.vpp.Out.Width = ALIGN16(vplParam.vppOutWidth);
        m_mfxVPPParams.vpp.Out.Height = ALIGN16(vplParam.vppOutHeight);
        m_mfxVPPParams.vpp.Out.CropW = vplParam.vppOutWidth;
        m_mfxVPPParams.vpp.Out.CropH = vplParam.vppOutHeight;
        m_mfxVPPParams.vpp.Out.PicStruct = MFX_PICSTRUCT_PROGRESSIVE;
        m_mfxVPPParams.vpp.Out.FrameRateExtN = m_decodeParams.mfx.FrameInfo.FrameRateExtN;
        m_mfxVPPParams.vpp.Out.FrameRateExtD = m_decodeParams.mfx.FrameInfo.FrameRateExtD;
        m_mfxVPPParams.IOPattern =
            m_useGPU ? (MFX_IOPATTERN_IN_VIDEO_MEMORY | MFX_IOPATTERN_OUT_VIDEO_MEMORY) : (MFX_IOPATTERN_IN_SYSTEM_MEMORY | MFX_IOPATTERN_OUT_SYSTEM_MEMORY);
    }
    return true;
}

/**
 * @brief start a decoder, handle different decode status
 */
bool VPLDecoderManager::startDecode(VPLInitParameters vplParam, std::string &buffer)
{
    switch (m_state) {
        case decodeStatus_t::DECODER_NONE:
            //
            // init a decoder, `buffer` must contain video header
            //
            if (!initDecoder(vplParam, buffer)) {
                HVA_ERROR("Failed to init decoder.");
                return false;
            }
            break;
        case decodeStatus_t::DECODER_VIDEO_EOS:
            //
            // deinit a decoder, release bitstream and contexts
            //
            // deinitDecoder();
            if (!resetDecoder(vplParam, buffer)) {
                HVA_ERROR("Failed to reset decoder.");
                return false;
            }
            break;
        case decodeStatus_t::DECODER_BUFFER_EOS:
            //
            // transit state to be ready for decoding the comming buffer
            //
            m_state = decodeStatus_t::DECODER_GOING;
            break;
        case decodeStatus_t::DECODER_PREPARED:
            // do nothing, can continue to decode
            break;
        case decodeStatus_t::DECODER_GOING:
            // do nothing, can continue to decode
            break;
        default: HVA_ERROR("unknown decode status: %s", decodeStatusToString(m_state).c_str()); return false;
    }
    return true;
}

/**
 * @brief decode to get next frame data
 */
bool VPLDecoderManager::decodeNext(std::string &buffer, mfxFrameSurface1 **pmfxDecOutSurface, mfxFrameSurface1 **pmfxVPPSurfacesOut)
{
    mfxStatus sts;
    mfxSyncPoint syncp = {};

    bool isDraining = false;
    *pmfxDecOutSurface = NULL;
    *pmfxVPPSurfacesOut = NULL;

    // read next piece of buffer, each piece with max length of BITSTREAM_BUFFER_SIZE
    if (isDraining == false) {
        sts = ReadEncodedStreamFromBuffer(m_bitstream, buffer);
        if (sts != MFX_ERR_NONE) {
            isDraining = true;
        }
    }

    // decode next frame
    sts = MFXVideoDECODE_DecodeFrameAsync(m_session, (isDraining) ? NULL : &m_bitstream, NULL, pmfxDecOutSurface, &syncp);

    if (sts == MFX_ERR_NONE) {
        // sucessfully decoded
        m_frameOrder++;

        m_state = decodeStatus_t::DECODER_GOING;

        if (!*pmfxDecOutSurface) {
            HVA_ERROR("ERROR - empty array of decode output at buffer frame: %d, status: %s", getFrameOrder(), mfxstatus_to_string(sts).c_str());
            return false;
        }

        if (m_vppUsed) {
            *pmfxVPPSurfacesOut = NULL;
            // resize here
            // The function processes a single input frame to a single output frame with internal allocation of output frame.
            sts = MFXVideoVPP_ProcessFrameAsync(m_session, *pmfxDecOutSurface, pmfxVPPSurfacesOut);
            if (!*pmfxVPPSurfacesOut) {
                HVA_ERROR("ERROR - empty array of vpp output at buffer frame: %d, status: %s", getFrameOrder(), mfxstatus_to_string(sts).c_str());
                return false;
            }
        }
        else {
            *pmfxVPPSurfacesOut = *pmfxDecOutSurface;
        }

        return true;
    }
    else if (sts == MFX_WRN_VIDEO_PARAM_CHANGED) {
        // The decoder detected a new sequence header in the bitstream.
        // Video parameters may have changed.
        // In external memory allocation case, might need to reallocate the output surface
        // can optionally retrieve new video parameters by calling MFXVideoDECODE_GetVideoParam.
        // mfxVideoParam decodeParamsNew = {};
        // MFXVideoDECODE_GetVideoParam(m_session, &decodeParamsNew);
        HVA_WARNING("Video VPL decoder node detected a new sequence "
                    "header in the bitstream at buffer frame: %d, choose to ignore!",
                    getFrameOrder());

        m_state = decodeStatus_t::DECODER_GOING;
        return false;
    }
    else if (sts == MFX_ERR_MORE_DATA) {
        // The function requires more bitstream at input before decoding can proceed
        HVA_DEBUG("Video VPL decoder node decoded end of the input video at frame: %d", getFrameOrder());
        m_state = decodeStatus_t::DECODER_BUFFER_EOS;
        return false;
    }
    else if (sts == MFX_WRN_DEVICE_BUSY) {
        // For non-CPU implementations,
        // Wait a few milliseconds then try again
        HVA_WARNING("Device busy at frame: %d, wait 10 milliseconds then try again", getFrameOrder());
        sleep(10 / 1000.0);
        m_state = decodeStatus_t::DECODER_GOING;
        return false;
    }
    else {
        // quit
        HVA_ERROR("unknown status %s", mfxstatus_to_string(sts).c_str());
        HVA_ASSERT(false);
    }
}

VPLDecoderNode::VPLDecoderNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum)
{
    transitStateTo(hva::hvaState_t::configured);
}

std::shared_ptr<hva::hvaNodeWorker_t> VPLDecoderNode::createNodeWorker() const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new VPLDecoderNodeWorker((hva::hvaNode_t *)this, m_vplParam, m_waitTime, m_decodeInterval));
}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 */
hva::hvaStatus_t VPLDecoderNode::configureByString(const std::string &config)
{
    if (config.empty())
        return hva::hvaFailure;

    if (!m_configParser.parse(config)) {
        HVA_ERROR("Illegal parse string!");
        return hva::hvaFailure;
    }

    // Decoder device, default as iGPU, i.e. "GPU.0"
    std::string deviceName = "GPU.0";
    std::string colorFormat = "NV12";
    m_configParser.getVal<std::string>("Device", deviceName);
    if (deviceName.find("GPU") != std::string::npos) {
        // If the system has an integrated GPU, its ‘id’ is always ‘0’ ("GPU.0").
        // Devices are enumerated as GPU.X, where X={0, 1, 2,...} (only Intel® GPU devices are considered).
        if (deviceName.rfind(".") == -1) {
            // "GPU", equals to "GPU.0"
            m_vplParam.deviceID = 0;
        }
        else {
            m_vplParam.deviceID = std::stoi(deviceName.substr(deviceName.rfind(".") + 1));
        }
        colorFormat = "NV12";
    }
    else if (deviceName == "CPU") {
        m_vplParam.deviceID = -1;
        colorFormat = "I420";
        // HVA_ERROR("Video vpl decode node cannot support for device: %s", deviceName.c_str());
        // return hva::hvaFailure;
    }
    else {
        HVA_ERROR("unknown device: %s", deviceName.c_str());
        return hva::hvaFailure;
    }

    std::string codecType = "";
    m_configParser.getVal<std::string>("CodecType", codecType);
    if ("H264" == codecType) {
        m_vplParam.inCodec = MFX_CODEC_AVC;
    }
    else if ("H265" == codecType) {
        m_vplParam.inCodec = MFX_CODEC_HEVC;
    }
    else if ("JPEG" == codecType) {
        m_vplParam.inCodec = MFX_CODEC_JPEG;
    }
    else {
        HVA_ERROR("Video vpl decode node cannot support for codec type: %s, choices: H264,H265,JPEG", codecType.c_str());
        return hva::hvaFailure;
    }

    // resize parameters
    int vppOutHeight = 0;
    int vppOutWidth = 0;
    m_configParser.getVal<int>("OutHeight", vppOutHeight);
    m_configParser.getVal<int>("OutWidth", vppOutWidth);
    m_vplParam.vppOutHeight = vppOutHeight;
    m_vplParam.vppOutWidth = vppOutWidth;

    // CSC parameters
    // TODO: enable CSC
    m_configParser.getVal<std::string>("CSC", colorFormat);
    if (!string_to_mfxColorFourCC(colorFormat, m_vplParam.vppOutFourCC)) {
        return hva::hvaFailure;
    }
    m_vplParam.vppOutChromaFormat = FourCCToChroma(m_vplParam.vppOutFourCC);

    float waitTime = 0;
    m_configParser.getVal<float>("WaitTime", waitTime);
    m_waitTime = waitTime;

    // decode interval
    int decodeInterval = 1;
    m_configParser.getVal<int>("DecodeInterval", decodeInterval);
    m_decodeInterval = (unsigned int)decodeInterval;

    transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

VPLDecoderNodeWorker::VPLDecoderNodeWorker(hva::hvaNode_t *parentNode, VPLInitParameters vplParam, float waitTime, unsigned int decodeInterval)
    : hva::hvaNodeWorker_t(parentNode), m_ctr(0u), m_vplParam(vplParam), m_StartFlag(false), m_waitTime(waitTime), m_decodeInterval(decodeInterval),
      m_workStreamId(-1)
{
    m_useGPU = m_vplParam.deviceID >= 0;
    if (m_useGPU) {
        m_vaContext = std::make_shared<hce::ai::inference::VAAPIContext>(VADeviceManager::getInstance().getVADisplay(m_vplParam.deviceID));
        m_vaDisplay = m_vaContext->va_display();
        // m_vaDisplay = VADeviceManager::getInstance().getVADisplay(m_vplParam.deviceID);
        // HVA_DEBUG("device id %d, VADisplay addr: %p", m_vplParam.deviceID, m_vaDisplay);
    }
    m_vplDecoderManager.init(m_useGPU, m_vplParam.inCodec, m_vaDisplay);
}

VPLDecoderNodeWorker::~VPLDecoderNodeWorker() {}

hva::hvaStatus_t VPLDecoderNodeWorker::rearm()
{
    HVA_DEBUG("Calling the rearm func.");
    return hva::hvaStatus_t::hvaSuccess;
}

hva::hvaStatus_t VPLDecoderNodeWorker::reset()
{
    HVA_DEBUG("Calling the reset func.");
    return hva::hvaStatus_t::hvaSuccess;
}

void VPLDecoderNodeWorker::init()
{
    return;
}

void VPLDecoderNodeWorker::deinit()
{
    return;
}

/**
 * @brief Frame index increased for every coming frame, will be called at the process()
 * @param void
 */
unsigned VPLDecoderNodeWorker::fetch_increment()
{
    return m_ctr++;
}

void VPLDecoderNodeWorker::sendEmptyBlob(const hva::hvaBlob_t::Ptr &blob, unsigned tag, unsigned frameId, unsigned streamId)
{
    //
    // for sanity check
    //
    hva::hvaVideoFrameWithROIBuf_t::Ptr videoBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(blob->get(0));
    HVA_ASSERT(videoBuf);

    std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
    currentTime = std::chrono::high_resolution_clock::now();
    TimeStamp_t timeMeta;
    timeMeta.timeStamp = currentTime;

    hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf;
    hvabuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<mfxFrameSurface1 *>(NULL, 0);

    hvabuf->frameId = frameId;
    hvabuf->width = 0;
    hvabuf->height = 0;
    hvabuf->drop = true;
    hvabuf->setMeta(timeMeta);
    hvabuf->setMeta<uint64_t>(0);
    hvabuf->tagAs(tag);

    auto jpegBlob = hva::hvaBlob_t::make_blob();
    if (!jpegBlob) {
        HVA_ERROR("Video VPL decoder make an empty blob!");
        HVA_ASSERT(false);
    }
    // frameIdx for blobs should always keep increasing
    jpegBlob->frameId = fetch_increment();
    jpegBlob->streamId = streamId;
    jpegBlob->push(hvabuf);
    HVA_DEBUG("Sending jpegBlob at blob frame id: %d with empty buffer!", frameId);
    // Set the meta attribute
    HceDatabaseMeta meta;
    if (videoBuf->getMeta(meta) == hva::hvaSuccess) {
        meta.bufType = HceDataMetaBufType::BUFTYPE_MFX_FRAME;
        meta.colorFormat = m_colorFmt;
        jpegBlob->get(0)->setMeta(meta);
        HVA_DEBUG("Video VPL decoder copied meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
    }
    SendController::Ptr controllerMeta;
    if (videoBuf->getMeta(controllerMeta) == hva::hvaSuccess) {
        jpegBlob->get(0)->setMeta(controllerMeta);
        HVA_DEBUG("Video VPL decoder copied controller meta to next buffer");
    }

    InferenceTimeStamp_t inferenceTimeMeta;
    currentTime = std::chrono::high_resolution_clock::now();
    inferenceTimeMeta.startTime = currentTime;
    hvabuf->setMeta(inferenceTimeMeta);

    VideoTimeStamp_t videoTimeMeta;
    videoTimeMeta.startTime = currentTime;
    hvabuf->setMeta(videoTimeMeta);

    sendOutput(jpegBlob, 0, std::chrono::milliseconds(0));
    HVA_DEBUG("Sended jpegBlob success");
}

void VPLDecoderNodeWorker::process(std::size_t batchIdx)
{
    HVA_DEBUG("Start to video VPL decoder node process");
    std::vector<std::shared_ptr<hva::hvaBlob_t>> vecBlobInput = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    for (const auto &pBlob : vecBlobInput) {
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
        currentTime = std::chrono::high_resolution_clock::now();
        TimeStamp_t timeMeta;
        timeMeta.timeStamp = currentTime;

        getParentPtr()->emitEvent(hvaEvent_PipelineLatencyCapture, &pBlob->frameId);
        std::shared_ptr<hva::timeStampInfo> decodeIn = std::make_shared<hva::timeStampInfo>(pBlob->frameId, "decodeIn");

        getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &decodeIn);

        hva::hvaVideoFrameWithROIBuf_t::Ptr videoBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(pBlob->get(0));

        HVA_DEBUG("Video VPL decoder node %d on blob frameId %d", batchIdx, pBlob->frameId);

        // if (videoBuf->frameId < 5) {
        //     std::shared_ptr<hva::timeStampInfo> decodeIn = std::make_shared<hva::timeStampInfo>(videoBuf->frameId, "decodeIn");
        //     getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &decodeIn);
        // }
        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        int streamId = (int)pBlob->streamId;
        if (m_workStreamId >= 0 && streamId != m_workStreamId) {
            HVA_ERROR("Video decoder worker should work on streamId: %d, but received "
                      "data from invalid streamId: %d!",
                      m_workStreamId, streamId);
            // send output
            videoBuf->drop = true;
            videoBuf->rois.clear();
            HVA_DEBUG("Video decoder sending blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
            sendOutput(pBlob, 0, std::chrono::milliseconds(0));
            HVA_DEBUG("Video decoder completed sent blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
            continue;
        }
        else {
            // the first coming stream decides the workStreamId for this worker
            m_workStreamId = streamId;
        }

        // Get the video buffer
        std::string tmpVideoStrData = videoBuf->get<std::string>();
        HVA_DEBUG("tmpVideoStrData size is %d", tmpVideoStrData.size());

        HVA_DEBUG("m_decodeInterval is %d", m_decodeInterval);

        if (m_decodeInterval > 1 && pBlob->frameId % m_decodeInterval != 0) {
            HVA_DEBUG("VPLDecoderNode skip processing at frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);

            // send empty blob as the last frame
            unsigned frameId = m_vplDecoderManager.getFrameOrder();
            sendEmptyBlob(pBlob, videoBuf->getTag(), frameId, streamId);
            return;
        }
        else if (!tmpVideoStrData.empty()) {
            std::vector<hva::hvaROI_t> rois;
            // Use the origin rois
            if (!videoBuf->rois.empty()) {
                rois = videoBuf->rois;
                HVA_DEBUG("Video VPL decoder node receives a buffer with rois of size %d", videoBuf->rois.size());
            }

            //
            // Use oneVPL to decode h264
            //
            bool isStillGoing = true;
            mfxStatus sts = MFX_ERR_NONE;

            // get vpl session
            // mfxLoader loader = m_vplDecoderManager.getLoader();
            // mfxSession session = m_vplDecoderManager.getSession();

            // process start
            getLatencyMonitor().startRecording(pBlob->frameId, "decoding");
            HVA_DEBUG("Video VPL decoder start decoding");
            if (!m_vplDecoderManager.startDecode(m_vplParam, tmpVideoStrData)) {
                HVA_ASSERT(false);
            }

            // Original image size
            size_t oriImgWidth = m_vplDecoderManager.getDecodeParams().mfx.FrameInfo.Width;
            size_t oriImgHeight = m_vplDecoderManager.getDecodeParams().mfx.FrameInfo.Height;

            // buffer frameId will be operated in VPLDecoderManager
            mfxU32 frameId;
            while (isStillGoing == true) {
                mfxFrameSurface1 *pmfxDecOutSurface = NULL;
                mfxFrameSurface1 *pmfxVPPSurfacesOut = NULL;

                //
                // decode next frame and save to pmfxDecOutSurface, pmfxVPPSurfacesOut
                //
                bool res = m_vplDecoderManager.decodeNext(tmpVideoStrData, &pmfxDecOutSurface, &pmfxVPPSurfacesOut);
                frameId = (mfxU32)m_vplDecoderManager.getFrameOrder();

                if (m_vplDecoderManager.getState() == decodeStatus_t::DECODER_BUFFER_EOS) {
                    isStillGoing = false;
                    break;
                }

                if (!res || !pmfxVPPSurfacesOut) {
                    // skip if we can get empty decoded frame but buffer is not end
                    HVA_WARNING("WARN - empty array of decode output at frame: %d, skip it", frameId);
                    continue;
                }

                // process decoded frame
                pmfxVPPSurfacesOut->FrameInterface->Synchronize(pmfxVPPSurfacesOut, SYNC_TIMEOUT);

                // process input infomation
                // note that width and height in Info has been aligned to 16
                unsigned inputWidth = (&pmfxVPPSurfacesOut->Info)->Width;
                unsigned inputHeight = (&pmfxVPPSurfacesOut->Info)->Height;
                mfxU32 inputCC = (&pmfxVPPSurfacesOut->Info)->FourCC;
                HVA_DEBUG("This frame: %d is decoded done, height: %d, width: "
                          "%d, inputCC: %s",
                          frameId, inputHeight, inputWidth, mfxColorFourCC_to_string(inputCC).c_str());
                switch (inputCC) {
                    case MFX_FOURCC_I420: m_colorFmt = hce::ai::inference::ColorFormat::I420; break;
                    case MFX_FOURCC_NV12: m_colorFmt = hce::ai::inference::ColorFormat::NV12; break;
                    case MFX_FOURCC_RGB4: m_colorFmt = hce::ai::inference::ColorFormat::BGRX; break;
                    default: HVA_DEBUG("unknown color format: %s", mfxColorFourCC_to_string(inputCC).c_str()); HVA_ASSERT(false);
                }

                getLatencyMonitor().stopRecording(pBlob->frameId, "decoding");
                // Make hva blob data
                hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf;
                if (!m_useGPU) {
                    HVA_ERROR("Error - SW decoding not implemented for VPL decoder");
                    HVA_ASSERT(false);
                }

                // pmfxVPPSurfacesOut->FrameInterface->AddRef(pmfxVPPSurfacesOut);

                hvabuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<mfxFrameSurface1 *>(pmfxVPPSurfacesOut, sizeof(pmfxVPPSurfacesOut),
                                                                                         [](mfxFrameSurface1 *p) { p->FrameInterface->Release(p); });

                //
                // hvaframework requires frameId starts from 0
                //  different with blob->frameId, frameId for hvabuf in video pipeline,
                //  it's the relative frame number in one video.
                //
                hvabuf->frameId = frameId;
                hvabuf->width = inputWidth;
                hvabuf->height = inputHeight;
                hvabuf->rois = rois;
                hvabuf->drop = false;
                hvabuf->setMeta(timeMeta);
                hvabuf->setMeta<uint64_t>(0);
                hvabuf->tagAs(videoBuf->getTag());

                // make blob for input
                auto jpegBlob = hva::hvaBlob_t::make_blob();
                if (!jpegBlob) {
                    HVA_ERROR("Video VPL decoder make an empty blob!");
                    HVA_ASSERT(false);
                }

                // frameIdx for blobs should always keep increasing
                jpegBlob->frameId = fetch_increment();
                jpegBlob->streamId = streamId;
                jpegBlob->push(hvabuf);

                // Set the meta attribute
                HceDatabaseMeta meta;
                if (videoBuf->getMeta(meta) == hva::hvaSuccess) {
                    meta.bufType = HceDataMetaBufType::BUFTYPE_MFX_FRAME;
                    meta.colorFormat = m_colorFmt;
                    meta.scaleHeight = oriImgHeight * 1.0 / inputHeight;
                    meta.scaleWidth = oriImgWidth * 1.0 / inputWidth;
                    jpegBlob->get(0)->setMeta(meta);
                    HVA_DEBUG("Video VPL decoder copied meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
                }
                SendController::Ptr controllerMeta;
                if (videoBuf->getMeta(controllerMeta) == hva::hvaSuccess) {
                    jpegBlob->get(0)->setMeta(controllerMeta);
                    HVA_DEBUG("Video VPL decoder copied controller meta to next buffer");
                }

                InferenceTimeStamp_t inferenceTimeMeta;
                currentTime = std::chrono::high_resolution_clock::now();
                inferenceTimeMeta.startTime = currentTime;
                hvabuf->setMeta(inferenceTimeMeta);

                VideoTimeStamp_t videoTimeMeta;
                videoTimeMeta.startTime = currentTime;
                hvabuf->setMeta(videoTimeMeta);

                // Free the requested memory space for each frame
                if (m_vplDecoderManager.isVPPUsed()) {
                    sts = pmfxDecOutSurface->FrameInterface->Release(pmfxDecOutSurface);
                    if (sts != MFX_ERR_NONE) {
                        HVA_ERROR("Failed to release decode output");
                        HVA_ASSERT(false);
                    }
                }

                HVA_DEBUG("Sending jpegBlob at blob frame id: %d with buffer frame: %d", jpegBlob->frameId, hvabuf->frameId);
                auto send = sendOutput(jpegBlob, 0, std::chrono::milliseconds(0));
                if (send != hva::hvaSuccess) {
                    HVA_ERROR("This frame is %d sended fail and the error is %d", jpegBlob->frameId, send);
                    HVA_ASSERT(false);
                }
                else {
                    HVA_DEBUG("The %d frame sended success", jpegBlob->frameId);
                }

                // if (frameId < 5) {
                //     std::shared_ptr<hva::timeStampInfo> decodeOut = std::make_shared<hva::timeStampInfo>(frameId, "decodeOut");
                //     getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &decodeOut);
                // }

            }  // while (isStillGoing == true)

            if (m_vplDecoderManager.getState() != decodeStatus_t::DECODER_BUFFER_EOS) {
                // abnormally quit
                HVA_ERROR("Video VPL decoder node %d abnormally quit on frameId %d", batchIdx, frameId);
                sendEmptyBlob(pBlob, videoBuf->getTag(), frameId, streamId);
                return;
            }
            // process done

            //
            // If the very last frame of this video stream is received
            // then send empty blob as the last frame
            //
            std::shared_ptr<hva::timeStampInfo> decodeOut = std::make_shared<hva::timeStampInfo>(pBlob->frameId, "decodeOut");
            getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &decodeOut);

            if (videoBuf->getTag() == hvaBlobBufferTag::END_OF_REQUEST) {
                // transit DECODER_BUFFER_EOS -> DECODER_VIDEO_EOS
                m_vplDecoderManager.setState(decodeStatus_t::DECODER_VIDEO_EOS);
                // m_vplDecoderManager.deinitDecoder();
                HVA_DEBUG("Video VPL decoder node %d processed %d frames", batchIdx, frameId);

                // sendEmptyBlob((unsigned)(hvaBlobBufferTag::END_OF_REQUEST), frameId, streamId);
                return;
            }

        }  // if (!tmpVideoStrData.empty())
        else {
            HVA_DEBUG("Video VPL decoder receives an empty buf on frame %d", pBlob->frameId);

            // send empty blob as the last frame
            unsigned frameId = m_vplDecoderManager.getFrameOrder();
            sendEmptyBlob(pBlob, videoBuf->getTag(), frameId, streamId);
            return;
        }
    }
}


#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(VPLDecoderNode, VPLDecoderNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference
}  // namespace ai
}  // namespace hce
