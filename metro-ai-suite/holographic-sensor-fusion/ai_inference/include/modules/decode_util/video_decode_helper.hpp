/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_VIDEO_DECODE_HELPER_HPP
#define HCE_AI_INF_VIDEO_DECODE_HELPER_HPP

#include <inc/api/hvaLogger.hpp>

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

// Read buffer in block
int feedVideoDecoder(void* opaque, std::uint8_t* buf, int buf_size) {
    std::stringstream* ss = reinterpret_cast<std::stringstream*>(opaque);
    auto actualSize = ss->readsome((char*)buf, buf_size);
    if (!actualSize)
        return AVERROR_EOF;
    return actualSize;
}

enum decodeStatus_t {
    DECODER_NONE = 0,
    DECODER_PREPARED,
    DECODER_GOING,
    DECODER_BUFFER_EOS,
    DECODER_VIDEO_EOS,
};

class FFmpegDecoderManager {
public:

    FFmpegDecoderManager() : m_frameOrder(0u), m_state(decodeStatus_t::DECODER_NONE) {
    }

    ~FFmpegDecoderManager() {
    }

    /**
     * @brief manage memory space
     * 
    */
    bool init() {
        HVA_DEBUG("init FFmpeg decode session.");

        // release bitstream and contexts
        m_bitstream.str("");
        
        return true;
    }

    /**
     * @brief manage memory space, corresponding to init()
     * 
    */
    void deinit() {
        HVA_DEBUG("deinit FFmpeg decode session.");

        // release bitstream and contexts
        m_bitstream.str("");
    }
    
    /**
     * @brief init decoder, reset contexts for decoder
     */
    bool initDecoder() {
        HVA_DEBUG("init FFmpeg decoder.");
        m_streamIndex = -1;
        m_frameOrder = 0;
        m_state = decodeStatus_t::DECODER_NONE;
        
        //Lower versions require manual registration of all FFmpeg codecs
#if LIBAVCODEC_VERSION_INT < AV_VERSION_INT(58, 9, 100)
        av_register_all();
#endif
        // Initialize the AVFormatContext for the output stream
        m_pFormatCtx = avformat_alloc_context();
        // Each block is defined as 4KB
        int len_size = 32768;
        unsigned char* aviobuffer = (unsigned char*)av_mallocz(len_size);  // freed in avio_close() <-- avformat_close_input()
        // Allocate and initialize an AVIOContext for buffered I/O
        AVIOContext* avio = avio_alloc_context(aviobuffer, len_size, 0, &m_bitstream,
                                               feedVideoDecoder, NULL, NULL);
        m_pFormatCtx->pb = avio;

        // Open an input stream and read the header.
        if (avformat_open_input(&m_pFormatCtx, NULL, NULL, NULL) != 0) {
            HVA_DEBUG("Couldn't open input stream.\n");
            return false;
        }
        if (avformat_find_stream_info(m_pFormatCtx, NULL) < 0) {
            HVA_DEBUG("Couldn't find stream information.\n");
            return false;
        }
        // Print detailed information about the input or output format
        av_dump_format(m_pFormatCtx, 0, "file", 0);
        m_streamIndex = av_find_best_stream(m_pFormatCtx, AVMEDIA_TYPE_VIDEO, -1,
                                           -1, NULL, 0);
        if (m_streamIndex < 0) {
            HVA_DEBUG("Could not find %s stream in input file \n",
                        av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
            return false;
        }
        // Find a registered decoder with a matching codec ID
        const AVCodec* pCodec = avcodec_find_decoder(m_pFormatCtx->streams[m_streamIndex]->codecpar->codec_id);
        if (pCodec == NULL) {
            HVA_DEBUG("Codec not found\n");
            return false;
        }
        // Allocate an AVCodecContext
        m_pCodecCtx = avcodec_alloc_context3(pCodec);
        if (m_pCodecCtx == NULL) {
          HVA_DEBUG("Could not allocate video codec context.\n");
          return false;
        }
        
        // Fill the codec context based on the values from the supplied codec parameters.
        if (avcodec_parameters_to_context(
                m_pCodecCtx, m_pFormatCtx->streams[m_streamIndex]->codecpar) < 0) {
          HVA_DEBUG("Failed to copy codec parameters to decoder context.\n");
          return false;
        }
        
        // Initialize the AVCodecContext to use the given AVCodec
        if (avcodec_open2(m_pCodecCtx, pCodec, NULL) < 0) {
          HVA_DEBUG("Could not open codec\n");
          return false;
        }
        
        // allocate pFrame and packet
        m_pFrame = av_frame_alloc();
        if (!m_pFrame) {
          HVA_DEBUG("Can't allocate memory for AVFrame\n");
          return false;
        }
        m_packet = av_packet_alloc();
        if (!m_packet) {
          HVA_DEBUG("Can't allocate memory for packet\n");
          return false;
        }

        // set ffmpeg log level
        av_log_set_level(AV_LOG_FATAL);
        int level = av_log_get_level();
        HVA_DEBUG("FFmpeg av log level: %d\n", level);

        // success, transit state
        setState(decodeStatus_t::DECODER_PREPARED);
        return true;
    }

    /**
     * @brief reset decoder context, get prepared for next round decoding
     * reset runtime decoder parameters
     */
    bool resetDecoder() {
        HVA_DEBUG("reset FFmpeg decoder.");

        if (!(m_state == decodeStatus_t::DECODER_VIDEO_EOS)) {
            HVA_ERROR("ERR - decoder state: %s (DECODER_VIDEO_EOS is required), still reset decoder!",
                        decodeStatusToString(m_state).c_str());
            HVA_ASSERT(false);
        }
        
        // init again with new buffer
        initDecoder();

        return true;
    }
    
    /**
     * @brief deinit decoder, reset contexts for decoder
     */
    void deinitDecoder() {
        HVA_DEBUG("deinit FFmpeg decoder.");
        
        // release bitstream and contexts
        m_bitstream.str("");

        m_streamIndex = -1;
        m_frameOrder = 0;
        
        // Free the requested memory space
        av_packet_unref(m_packet);
        av_packet_free(&m_packet);
        av_frame_free(&m_pFrame);
        avformat_close_input(&m_pFormatCtx);
        avcodec_free_context(&m_pCodecCtx);
        m_state = decodeStatus_t::DECODER_NONE;
    }

    /**
     * @brief start a decoder, handle different decode status
     */
    bool startDecode(std::string& buffer) {

        // append buffer to decoder stream buffer
        m_bitstream << buffer;

        switch (m_state) {
            case decodeStatus_t::DECODER_NONE:
                //
                // init a decoder, `buffer` must contain video header
                //
                if (!initDecoder()) {
                    HVA_ERROR("Failed to init decoder.");
                    return false;
                }
                break;
            case decodeStatus_t::DECODER_VIDEO_EOS:
                //
                // last decoding process is done, reset the decoder to process new coming video
                //
                HVA_ERROR("Error decode status: %s",
                        decodeStatusToString(m_state).c_str());
                return false;
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
            default:
                HVA_ERROR("unknown decode status: %s",
                        decodeStatusToString(m_state).c_str());
                return false;
        }
        // try fetch the very first frame
        int ret = av_read_frame(m_pFormatCtx, m_packet);
        if (ret < 0) {
            HVA_ERROR("ERR - At least one frame should be fetched, try to enlarge buffer size\n");
            return false;
        }
        
        return true;
    }

    /**
     * @brief decode to get next frame data
     * @param hvabuf save decoded frame data in hvabuf
     * @return status int: 
     *          > 1 stands for eof
     *          > 0 stands for still going
     */
    int decodeNext(hva::hvaVideoFrameWithROIBuf_t::Ptr& hvabuf) {

        int status = 0;

        if (m_packet->stream_index != m_streamIndex) {
            av_packet_unref(m_packet);
            // read next frame
            status = av_read_frame(m_pFormatCtx, m_packet);
            return status;
        }

        // Supply raw packet data as input to a decoder
        int ret = avcodec_send_packet(m_pCodecCtx, m_packet);
        if (ret < 0) {
            av_packet_unref(m_packet);
            // read next frame
            status = av_read_frame(m_pFormatCtx, m_packet);
            return status;
        }

        // Get the decoded output data from a decoder.
        ret = avcodec_receive_frame(m_pCodecCtx, m_pFrame);
        if (ret != 0) {
            return status;
        }

        // Get the decoded output data from a decoder.
        // color convert
        unsigned dstBufsize;
        uint8_t* dst[4];
        int dst_linesize[4];
        struct SwsContext* img_convert_ctx;

        // align buffer to a multiple of 64
        m_pCodecCtx->width = (m_pCodecCtx->width + 63) & ~63;
        m_pFrame->width = (m_pFrame->width + 63) & ~63;
        
        dstBufsize = av_image_alloc(dst, dst_linesize, m_pCodecCtx->width,
                                    m_pCodecCtx->height, AV_PIX_FMT_BGR24, 1);
        memset(dst[0], 0, dstBufsize);
        img_convert_ctx = sws_getContext(
            m_pFrame->width, m_pFrame->height, m_pCodecCtx->pix_fmt,
            m_pCodecCtx->width, m_pCodecCtx->height, AV_PIX_FMT_BGR24,
            SWS_BICUBIC, NULL, NULL, NULL);
        sws_scale(img_convert_ctx, (const uint8_t* const*)m_pFrame->data,
                    m_pFrame->linesize, 0, m_pFrame->height, dst, dst_linesize);
        
        // decode success
        m_dstWidth = m_pCodecCtx->width;
        m_dstHeight = m_pCodecCtx->height;

        HVA_DEBUG("This frame is decoded done");
        hvabuf =
            hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(
                dst[0], dstBufsize, [](uint8_t* p) { av_freep(&p); });
        hvabuf->frameId = getFrameOrder();
        hvabuf->width = getFrameWidth();
        hvabuf->height = getFrameHeight();
        hvabuf->stride[0] = (unsigned)dst_linesize[0];
        hvabuf->drop = false;

        // Free the requested memory space for each frame
        sws_freeContext(img_convert_ctx);

        // release resources per frame
        av_frame_unref(m_pFrame);
        av_packet_unref(m_packet);
        
        // If it is the last frame, it is marked as 1
        if (av_read_frame(m_pFormatCtx, m_packet) != 0) {
            setState(decodeStatus_t::DECODER_BUFFER_EOS);
            status = 1;
        }

        // Increase frame order
        m_frameOrder ++;
        setState(decodeStatus_t::DECODER_GOING);
        return status;
    }

    /**
     * @brief transit decoder status
    */
    decodeStatus_t setState(decodeStatus_t state)  {
        HVA_DEBUG("FFmpeg Decoder state transit to %s", decodeStatusToString(state).c_str());
        m_state = state;
        return m_state;
    }

    /**
     * @brief get decoder status
    */
    decodeStatus_t getState() {
        return m_state;
    }

    /**
     * @brief frame order
    */
    unsigned getFrameOrder()  {
        // starts from 0
        return m_frameOrder;
    }

    /**
     * @brief decoded frame height
    */
    unsigned getFrameHeight()  {
        return m_dstHeight;
    }

    /**
     * @brief decoded frame height
    */
    unsigned getFrameWidth()  {
        return m_dstWidth;
    }

private:

    /**
     * decodeStatus_t str
     */
    std::string decodeStatusToString(decodeStatus_t sts) {
        switch(sts)
        {
            case decodeStatus_t::DECODER_NONE:
                return "DECODER_NONE";
            case decodeStatus_t::DECODER_PREPARED:
                return "DECODER_PREPARED";
            case decodeStatus_t::DECODER_GOING:
                return "DECODER_GOING";
            case decodeStatus_t::DECODER_BUFFER_EOS:
                return "DECODER_BUFFER_EOS";
            case decodeStatus_t::DECODER_VIDEO_EOS:
                return "DECODER_VIDEO_EOS";
            default:
                break;
        }

        std::string ret("<unknown ");
        ret += std::to_string(sts) + ">";
        return ret;
    }

    unsigned m_frameOrder;
    decodeStatus_t m_state;
    
    unsigned m_dstHeight, m_dstWidth;
    AVFormatContext* m_pFormatCtx;
    AVCodecContext* m_pCodecCtx;
    AVPacket* m_packet;
    AVFrame* m_pFrame;
    int m_streamIndex = -1;

    std::stringstream m_bitstream;

    struct SwsContext* m_img_convert_ctx;
};


}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_VIDEO_DECODE_HELPER_HPP