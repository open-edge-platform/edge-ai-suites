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

#include "nodes/CPU-backend/JpegDecoderNode.hpp"
#include "nodes/databaseMeta.hpp"

namespace hce{

namespace ai{

namespace inference{

/**
 * @brief copy source buffer to uint8 dst buffer
 * - if read all into dst buffer, set source buffer as empty
 * - if not, keep unread parts in the source buffer
 * @param opaque source buffer
 * @param buf dst uint8_t buffer
 * @param buf_size buffer size
 * @return buffer size
 */
int readBuffer (void *opaque, std::uint8_t *buf, int buf_size);

/**
 * @brief append uint8 dst buffer to source buffer
 * @param opaque source buffer
 * @param buf dst uint8_t buffer
 * @param buf_size size of `buf`
 * @return buf_size
 */
int writeBuffer(void *opaque, std::uint8_t *buf, int buf_size);

/**
 * @brief read dst uint8_t buffer into jpeg decoder
 * @param opaque source buffer for jpeg decoder
 * @param buf dst uint8_t buffer
 * @param buf_size size of `buf`
 * @return actual read buffer size of `buf`
 */
int feedDecoder (void *opaque, std::uint8_t *buf, int buf_size);

JpegDecoderNode::JpegDecoderNode(std::size_t totalThreadNum)
:hva::hvaNode_t(1, 1, totalThreadNum) {
    transitStateTo(hva::hvaState_t::configured); 
}

/**
* @brief Constructs and returns a node worker instance: JpegDecoderNodeWorker.
* @param void
*/
std::shared_ptr<hva::hvaNodeWorker_t> JpegDecoderNode::createNodeWorker() const{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new JpegDecoderNodeWorker((hva::hvaNode_t*)this,"JpegDecoderNodeWorkerInstance"));
}

std::string JpegDecoderNode::name(){
    return m_name;
}

JpegDecoderNodeWorker::JpegDecoderNodeWorker(hva::hvaNode_t* parentNode, std::string name)
:hva::hvaNodeWorker_t(parentNode), m_WID(0), m_name(name), m_StartFlag(false), m_EncodeType(BGR), m_workStreamId(-1){
}

JpegDecoderNodeWorker::~JpegDecoderNodeWorker(){}

hva::hvaStatus_t JpegDecoderNodeWorker::rearm(){
    HVA_DEBUG("Calling the rearm func.");
    return hva::hvaStatus_t::hvaSuccess;
}

hva::hvaStatus_t JpegDecoderNodeWorker::reset(){
    HVA_DEBUG("Calling the reset func.");
    return hva::hvaStatus_t::hvaSuccess;    
}

/**
 * @brief get value of m_EncodeType
 * @return encodeType: RGB=1, YUV=2
 */
JpegDecoderNodeWorker::encodeType JpegDecoderNodeWorker::getEncodeType(){
    return m_EncodeType;
}

void JpegDecoderNodeWorker::init(){
    return;
}

void JpegDecoderNodeWorker::deinit(){
    return;
}

/**
 * @brief Called by hva framework for each video frame, Run inference and pass output to following node
 * decode incoming buffer to BGR images using ffmpeg framework
 * @param batchIdx Internal parameter handled by hvaframework
 */
void JpegDecoderNodeWorker::process(std::size_t batchIdx){

    HVA_DEBUG("Start to jpeg decoder node process");
    std::vector<std::shared_ptr<hva::hvaBlob_t>> vecBlobInput = hvaNodeWorker_t::getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t> {0});
    HVA_DEBUG("Get the vecBlobInput size is %d", vecBlobInput.size());

    // input blob is not empty
    for (const auto& pBlob : vecBlobInput) {
        std::chrono::time_point<std::chrono::high_resolution_clock> currentTime;
        currentTime = std::chrono::high_resolution_clock::now();
        TimeStamp_t timeMeta;
        timeMeta.timeStamp = currentTime;

        // start processing
        unsigned frameIdx = pBlob->frameId;
        hva::hvaVideoFrameWithROIBuf_t::Ptr buf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithROIBuf_t>(pBlob->get(0));

        // inherit buffer tag from previous input field
        // 0: default value
        // 1: stands for the last frame of a sequence inputs
        unsigned tag = buf->getTag();
        HVA_DEBUG("Jpeg decoder start processing with frameid %u and streamid %u with tag %d", pBlob->frameId, pBlob->streamId, tag);

        // for sanity: check the consistency of streamId, each worker should work on one streamId.
        int streamId = (int)pBlob->streamId;
        if (m_workStreamId >= 0 && streamId != m_workStreamId) {
            HVA_ERROR(
                "Jpeg decoder worker should work on streamId: %d, but received "
                "data from invalid streamId: %d!",
                m_workStreamId, streamId);
            // send output
            buf->drop = true;
            buf->rois.clear();
            HVA_DEBUG("Jpeg decoder sending blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
            sendOutput(pBlob, 0, std::chrono::milliseconds(0));
            HVA_DEBUG("Jpeg decoder completed sent blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
            continue;
        } else {
            // the first coming stream decides the workStreamId for this worker
            m_workStreamId = streamId;
        }

        // make blob for input
        auto jpegBlob = hva::hvaBlob_t::make_blob();
        if (!jpegBlob) {
            HVA_ERROR("Jpeg decoder make an empty blob!");
            continue;
        }

        // read image string data from buffer
        std::string tmpJpgStrData = buf->get<std::string>();
        bool decodeSuccess = false;
        if(!tmpJpgStrData.empty()){
            
            // inherit rois from previous input field
            std::vector<hva::hvaROI_t> rois;
            if(!buf->rois.empty()){
                rois = buf->rois;
                HVA_DEBUG("Jpeg decoder receives a buffer with rois of size %d", buf->rois.size());
            }

            // start to decode image from buffer
            HVA_DEBUG("Jpeg decoder prepares to feed to ffmpeg");
            unsigned dstHeight, dstWidth, dstBufsize;
            uint8_t* dst[4];
            int dstLinesize[4];
            bool ret = decodeImage(tmpJpgStrData, dst, dstWidth, dstHeight, dstLinesize, dstBufsize);
            HVA_DEBUG("Jpeg decoder prepares to feeding ffmpeg done");
            if(!ret) {
                HVA_DEBUG("OpenImage failed.\n");
                decodeSuccess = false;
            }
            else {

                // decoding job done, send to the subsequent nodes
                HVA_DEBUG("Jpeg decoder encoding image done");
                hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf =
                    hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(
                        dst[0], dstBufsize, [](uint8_t* p) { av_freep(&p); });
                hvabuf->frameId = frameIdx;
                hvabuf->width = dstWidth;
                hvabuf->height = dstHeight;
                hvabuf->stride[0] = (unsigned)dstLinesize[0];       // channels * width
                hvabuf->rois = rois;
                hvabuf->drop = false;
                hvabuf->setMeta<uint64_t>(0);
                hvabuf->tagAs(tag);
                jpegBlob->frameId = frameIdx;
                jpegBlob->streamId = pBlob->streamId;
                jpegBlob->push(hvabuf);
                decodeSuccess = true;
            }
        }
        
        if (!decodeSuccess) {
            HVA_DEBUG("Jpeg decoder receives an empty buf on frame %d", frameIdx);
            // send empty buffer to the subsequent nodes
            hva::hvaVideoFrameWithROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithROIBuf_t::make_buffer<uint8_t*>(NULL, 0);
            hvabuf->frameId = frameIdx;
            hvabuf->width = 0;
            hvabuf->height = 0;
            hvabuf->drop = true;
            hvabuf->setMeta<uint64_t>(0);
            hvabuf->setMeta(timeMeta);
            hvabuf->tagAs(tag);
            jpegBlob->frameId = frameIdx;
            jpegBlob->streamId = pBlob->streamId;
            jpegBlob->push(hvabuf);
        }

        // inherit meta data from previous input field
        HceDatabaseMeta meta;
        jpegBlob->get(0)->setMeta(timeMeta);
        if(buf->getMeta(meta) == hva::hvaSuccess){
            meta.bufType = HceDataMetaBufType::BUFTYPE_UINT8;
            jpegBlob->get(0)->setMeta(meta);
            HVA_DEBUG("Jpeg decoder copied meta to next buffer, mediauri: %s", meta.mediaUri.c_str());
        }
        SendController::Ptr controllerMeta;
        if(buf->getMeta(controllerMeta) == hva::hvaSuccess){
            jpegBlob->get(0)->setMeta(controllerMeta);
            HVA_DEBUG("Jpeg decoder copied controller meta to next buffer");
        }

        InferenceTimeStamp_t inferenceTimeMeta;
        currentTime = std::chrono::high_resolution_clock::now();
        inferenceTimeMeta.startTime = currentTime;
        jpegBlob->get(0)->setMeta(inferenceTimeMeta);

        VideoTimeStamp_t videoTimeMeta;
        videoTimeMeta.startTime = currentTime;
        jpegBlob->get(0)->setMeta(videoTimeMeta);

        // process done
        // send output
        HVA_DEBUG("Jpeg decoder sending blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
        sendOutput(jpegBlob, 0, std::chrono::milliseconds(0));
        HVA_DEBUG("Jpeg decoder completed sent blob with frameid %u and streamid %u", pBlob->frameId, pBlob->streamId);
    }
}

/**
 * @brief to decode images from string buffer
 * @param imageData string buffer
 * @param dst decoded image
 * @param dstWidth decoded image width
 * @param dstHeight decoded image height
 * @param dstBufsize buffer size for decoded image 
 */
bool JpegDecoderNodeWorker::decodeImage(std::string& imageData, uint8_t* (&dst_data)[4], 
                                        unsigned& dstWidth, unsigned& dstHeight, 
                                        int dstLinesize[4], unsigned& dstBufsize) {

    AVFormatContext *pFormatCtx;
    AVCodecContext *pCodecCtx; 
    AVFrame *pFrame;
    AVPacket *packet;          
    int stream_index = -1;
    struct SwsContext *img_convert_ctx; 

    #if LIBAVCODEC_VERSION_INT < AV_VERSION_INT(58, 9, 100)
        av_register_all(); 
    #endif
    pFormatCtx = avformat_alloc_context();   

    // Each block is defined as 4KB
    int len_size = 32768;
    unsigned char *aviobuffer = (unsigned char *)av_mallocz(len_size);  // freed in avio_close() <-- avformat_close_input()

    // Allocate and initialize an AVIOContext for buffered I/O
    std::stringstream ss(imageData);
    AVIOContext *avio = avio_alloc_context(aviobuffer, len_size, 0, &ss, feedDecoder, NULL, NULL);   
    pFormatCtx->pb = avio;
    
    // Open an input stream and read the header.
	if(avformat_open_input(&pFormatCtx, NULL, NULL, NULL) != 0) {
		HVA_DEBUG("Couldn't open input stream.\n");
        avformat_close_input(&pFormatCtx);
		return false;
	}
    pFormatCtx->max_analyze_duration = AV_TIME_BASE;
	if(avformat_find_stream_info(pFormatCtx, NULL) < 0) {
		HVA_DEBUG("Couldn't find stream information.\n");
        avformat_close_input(&pFormatCtx);
		return false;
	}

    // Print detailed information about the input or output format
    av_dump_format(pFormatCtx, 0, "file", 0);
    stream_index = av_find_best_stream(pFormatCtx, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    if(stream_index < 0) {
        HVA_DEBUG("Could not find %s stream in input file \n",
                av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        avformat_close_input(&pFormatCtx);
        return false;
    }

    // Find a registered decoder with a matching codec ID
    const AVCodec *pCodec = avcodec_find_decoder(pFormatCtx->streams[stream_index]->codecpar->codec_id);
    if(pCodec == NULL) {
        HVA_DEBUG("Codec not found\n");
        avformat_close_input(&pFormatCtx);
        return false;
    }

    // Allocate an AVCodecContext
    pCodecCtx = avcodec_alloc_context3(pCodec);
    if(pCodecCtx == NULL) {
        HVA_DEBUG("Could not allocate video codec context.\n");
        avformat_close_input(&pFormatCtx);
        avcodec_free_context(&pCodecCtx);
        return false;
    }

    // Fill the codec context based on the values from the supplied codec parameters.
    if(avcodec_parameters_to_context(pCodecCtx, pFormatCtx->streams[stream_index]->codecpar) < 0) {
        HVA_DEBUG("Failed to copy codec parameters to decoder context.\n");
        avformat_close_input(&pFormatCtx);
        avcodec_free_context(&pCodecCtx);
        return false;
    }

    // Initialize the AVCodecContext to use the given AVCodec
    if(avcodec_open2(pCodecCtx, pCodec, NULL) < 0) {
        HVA_DEBUG("Could not open codec\n");
        avformat_close_input(&pFormatCtx);
        avcodec_free_context(&pCodecCtx);
        return false;
    }
    pFrame = av_frame_alloc();
    if(!pFrame) {
        HVA_DEBUG("Can't allocate memory for AVFrame\n");
        av_frame_free(&pFrame);
        avformat_close_input(&pFormatCtx);
        avcodec_free_context(&pCodecCtx);
        return false;
    }
    // packet = (AVPacket *)av_mallocz(sizeof(AVPacket));
    packet = av_packet_alloc();

    //Read the next frame of a stream to packet
    while(av_read_frame(pFormatCtx, packet) >= 0) {
        if(packet->stream_index != stream_index) {
            continue;
        }
        // Supply raw packet data as input to a decoder
        int ret = avcodec_send_packet(pCodecCtx, packet);

        // return < 0 if the packet is can't decode. 
        if(ret < 0) {
            continue;
        }

        // Get the decoded output data from a decoder.
        if(avcodec_receive_frame(pCodecCtx, pFrame) == 0){
            av_packet_unref(packet);
            break;
        }
    }
    // Free the requested memory space
    av_packet_unref(packet);
    av_packet_free(&packet);

    // Save decoded buffer to string

    // align buffer to a multiple of 64
    pCodecCtx->width = (pCodecCtx->width + 63) & ~63;
    pFrame->width = (pFrame->width + 63) & ~63;

    dstBufsize = av_image_alloc(dst_data, dstLinesize, pCodecCtx->width, pCodecCtx->height, AV_PIX_FMT_BGR24, 1);
    memset(dst_data[0], 0, dstBufsize);
    img_convert_ctx = sws_getContext(pFrame->width, pFrame->height, pCodecCtx->pix_fmt, pCodecCtx->width,
                       pCodecCtx->height, AV_PIX_FMT_BGR24, SWS_BICUBIC, NULL, NULL, NULL);
    
    // color conversion and scaling for decoded image
    sws_scale(img_convert_ctx, (const uint8_t *const *)pFrame->data, pFrame->linesize, 0,
              pFrame->height, dst_data, dstLinesize);

    dstHeight = pFrame->height;
    dstWidth = pFrame->width;

    // Free the requested memory space
    av_frame_unref(pFrame);
    av_frame_free(&pFrame);
    av_freep(&avio->buffer);
    av_freep(&avio);
    avformat_close_input(&pFormatCtx);
    avcodec_free_context(&pCodecCtx);
    sws_freeContext(img_convert_ctx);

    return true;    
}

/**
 * @brief encode BGR image from AVFrame data
 * @param decodedImage input image for encoding
 * @return string buffer for encoded BGR image
 */
std::string JpegDecoderNodeWorker::encodeBGRImage(AVFrame* decodedImage) {

    AVFrame*	FrameBGR;				
    uint8_t*	bgrBuffer;
    int			bgrBufferSize;
    SwsContext*	ConvertCtxYUV2BGR;
    bgrBuffer = NULL;
    ConvertCtxYUV2BGR = NULL;
    FrameBGR = av_frame_alloc();
    int width = decodedImage->width, height = decodedImage->height;

    // get buffer size in AV_PIX_FMT_BGR24 format 
    // avpicture_get_size is deprecated, use av_image_get_buffer_size() instead.
    bgrBufferSize = av_image_get_buffer_size(AV_PIX_FMT_BGR24, width, height, 1);

    bgrBuffer = (uint8_t *)av_mallocz(bgrBufferSize * sizeof(uint8_t));

    // associate FrameBGR data to bgrBuffer in AV_PIX_FMT_BGR24 format.
    // avpicture_fill is deprecated, use av_image_fill_arrays() instead.
    av_image_fill_arrays(FrameBGR->data, FrameBGR->linesize, bgrBuffer, AV_PIX_FMT_BGR24, width, height, 1);

    ConvertCtxYUV2BGR = sws_getContext(width, height, AV_PIX_FMT_YUV420P, width, height, AV_PIX_FMT_BGR24, SWS_BICUBIC, NULL, NULL, NULL);

    // color conversion and scaling for decoded image
    sws_scale(ConvertCtxYUV2BGR, (uint8_t const * const *)decodedImage->data, decodedImage->linesize, 0, decodedImage->height, FrameBGR->data, FrameBGR->linesize);

    // copy BGR data to string buffer
    std::string BGRStr(bgrBuffer, bgrBuffer + bgrBufferSize);

    // Free the requested memory space
    av_free(bgrBuffer);
    av_frame_free(&FrameBGR);
    sws_freeContext(ConvertCtxYUV2BGR);

    return BGRStr;
}

/**
 * @brief encode YUV image from AVFrame data
 * @param pFrame input image for encoding
 * @return string buffer for encoded YUV image
 */
std::string JpegDecoderNodeWorker::encodeYUVImage(AVFrame *pFrame) {

    int width = pFrame->width;
    int height = pFrame->height;
    int ret = -1;
    AVFormatContext *pFormatCtx;
    AVCodecContext *pCodecCtx = NULL; 
    AVPacket pkt;                     
    AVStream *pAVStream;

    // allocate an AVFormatContext for an output format: mjpeg
    pFormatCtx = avformat_alloc_context(); 
	avformat_alloc_output_context2(&pFormatCtx, NULL, "mjpeg", NULL);
    
    // Each block is defined as 4KB
    size_t obuf_size = 32768;
	unsigned char * iobuffer=(unsigned char *)av_mallocz(obuf_size);
    
    // Allocate and initialize an AVIOContext for buffered I/O
    std::string YUVdata;
    AVIOContext *avio =avio_alloc_context(iobuffer, obuf_size, 1, &YUVdata, NULL, writeBuffer, NULL);
    if(avio == NULL || avio == nullptr) {
        HVA_DEBUG("Can't allocate memory for AVIOContext\n");
        return NULL;
    }

    // Add a new stream to a media file.
    pFormatCtx->pb=avio;
    pFormatCtx->flags=AVFMT_FLAG_CUSTOM_IO;
    pAVStream = avformat_new_stream(pFormatCtx, 0);
    if (pAVStream == NULL) {
        HVA_DEBUG("Failed to add a new stream to a media file.\n");
        return NULL;
    }

    // Find a registered encoder with a matching codec ID
    pAVStream->codecpar->codec_id = pFormatCtx->oformat->video_codec;
    pAVStream->codecpar->codec_type = AVMEDIA_TYPE_VIDEO;
    pAVStream->codecpar->format = AV_PIX_FMT_YUVJ420P;
    pAVStream->codecpar->width = width;
    pAVStream->codecpar->height = height;
    const AVCodec *pCodec = avcodec_find_encoder(pAVStream->codecpar->codec_id);
    if (pCodec == NULL) {
        HVA_DEBUG("Codec not found.\n");
        return NULL;
    }

    // Allocate an AVCodecContext
    pCodecCtx = avcodec_alloc_context3(pCodec);
    if (pCodecCtx == NULL) {
        HVA_DEBUG("Could not allocate video codec context.\n");
        return NULL;
    }

    // Fill the codec context based on the values from the supplied codec parameters.
    if (avcodec_parameters_to_context(pCodecCtx, pAVStream->codecpar) < 0) {
        HVA_DEBUG("Failed to copy codec parameters to encoder context.\n");
        return NULL;
    }

    // Initialize the AVCodecContext to use the given AVCodec
    pCodecCtx->time_base.num = 1;
    pCodecCtx->time_base.den = 25;
    if (avcodec_open2(pCodecCtx, pCodec, NULL) < 0) {
        HVA_DEBUG("Could not open codec.\n");
        return NULL;
    }

    // Allocate the stream private data and write the stream header to an output media file. 
    ret = avformat_write_header(pFormatCtx, NULL);
    if (ret < 0) {
        HVA_DEBUG("Write_header fail.\n");
        return NULL;
    }
    
    // Allocate the payload of a packet and initialize its fields with default values.
    if (av_new_packet(&pkt, pFrame->width * pFrame->height * 3) < 0) {
        HVA_DEBUG("Allocate the payload of a packet fail.\n");
        return NULL;
    }

    // Supply a raw video or audio frame to the encoder.
    ret = avcodec_send_frame(pCodecCtx, pFrame);
    if (ret < 0) {
        HVA_DEBUG("avcodec_send_frame failed.\n");
        return NULL;
    }

    // Read encoded data from the encoder.
    ret = avcodec_receive_packet(pCodecCtx, &pkt);
    if (ret < 0) {
        HVA_DEBUG("avcodec_receive_packet failed.\n");
        return NULL;
    }

    // Write a packet to an output media file.
    ret = av_write_frame(pFormatCtx, &pkt);
    if (ret < 0) {
        HVA_DEBUG("av_write_frame failed.\n");
        return NULL;
    }
    
    // Free the requested memory space
    av_packet_unref(&pkt);
    av_write_trailer(pFormatCtx);
    avcodec_close(pCodecCtx);
    avformat_close_input(&pFormatCtx);

    return YUVdata;
}

/**
 * @brief read dst uint8_t buffer into jpeg decoder
 * @param opaque source buffer for jpeg decoder
 * @param buf dst uint8_t buffer
 * @param buf_size size of `buf`
 * @return actual read buffer size of `buf`
 */
int feedDecoder (void *opaque, std::uint8_t *buf, int buf_size){
    std::stringstream* ss = reinterpret_cast<std::stringstream*>(opaque);
    auto actualSize = ss->readsome((char*)buf, buf_size);
    HVA_DEBUG("Reads %d bytes into jpeg decoder", actualSize);
    if (!actualSize)
        return AVERROR_EOF;
    return actualSize;
}

/**
 * @brief copy source buffer to uint8 dst buffer
 * - if read all into dst buffer, set source buffer as empty
 * - if not, keep unread parts in the source buffer
 * @param opaque source buffer
 * @param buf dst uint8_t buffer
 * @param buf_size size of `buf`
 * @return buf_size
 */
int readBuffer(void *opaque, std::uint8_t *buf, int buf_size){  

    std::string *image_str = static_cast<std::string*>(opaque);
    buf_size = (image_str->length() < buf_size ? image_str->length() : buf_size);
    std::string tmp = image_str->substr(0, buf_size);
    const char *image_part = tmp.c_str();
    memcpy(buf, image_part, buf_size);
    buf_size == image_str->length() ? image_str->assign("") : image_str->assign(image_str->substr(buf_size));
    return buf_size;
}

/**
 * @brief append uint8 dst buffer to source buffer
 * @param opaque source buffer
 * @param buf dst uint8_t buffer
 * @param buf_size size of `buf`
 * @return buf_size
 */
int writeBuffer(void *opaque, std::uint8_t *buf, int buf_size) {

    std::string tmp = std::string(buf, buf + buf_size);
    std::string *image_str = static_cast<std::string*>(opaque);
    image_str->append(tmp);
    return buf_size;
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(CPUJpegDecoderNode, JpegDecoderNode(threadNum))
#endif //#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY


}
}
}
