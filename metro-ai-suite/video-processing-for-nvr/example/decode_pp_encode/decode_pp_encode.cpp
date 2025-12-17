/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2024 Intel Corporation
 *
 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the
 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's
 * prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties, other than those
 * that are expressly stated in the License.
 */

#include "vpp_common.h"
#include "vpp_encode.h"
#include "vpp_osd.h"
#include "vpp_decode.h"
#include "vpp_system.h"
#include "vpp_display.h"
#include "vpp_postprocessing.h"
#include <thread>
#include <iostream>
#include <unistd.h>
#include <cassert>

void send_input(int32_t decode_id){
    FILE* fp = fopen("/opt/video/1080p.h265", "rb");
    const uint64_t size = 1 * 1024 * 1024;
    void* addr = malloc(size);
    while (true) {
        uint64_t sizeTemp = fread(addr, 1, size, fp);
        VPP_DECODE_STREAM_InputBuffer buffer;
        buffer.pAddr = (uint8_t*)addr;
        buffer.Length = sizeTemp;
        buffer.BasePts = 0;
        buffer.FlagEOStream = false;
        if(sizeTemp < size) {
            buffer.FlagEOStream = true;
        }
        VPP_DECODE_STREAM_FeedInput(decode_id, &buffer, -1);
        if(sizeTemp < size) {
            break;
        }
    }
    usleep(1000000);
    free(addr);
    fclose(fp);
}

    
int main(void)
{
    // H265 decode + pp + encode(H265)

    // codec standard
    VPP_CODEC_STANDARD Codec_Standard = VPP_CODEC_STANDARD_H265;

    // Save encoded frames to video file path:
    std::string video_path = "/tmp/test.h265";

    VPP_Init();

    // Create decode stream:
    int32_t decode_id = 1;
    VPP_DECODE_STREAM_Attr attr_1;
    attr_1.CodecStandard = Codec_Standard;
    attr_1.OutputFormat = VPP_PIXEL_FORMAT_NV12;
    attr_1.OutputHeight = 0;
    attr_1.OutputWidth = 0;
    attr_1.OutputBufQueueLength = 0;
    attr_1.RingBufferSize = 0;
    attr_1.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
    assert(VPP_DECODE_STREAM_Create(decode_id, &attr_1) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_DECODE_STREAM_Create 1 Done" << std::endl;

    // Create encode stream:
    int32_t encode_id = 1;
    VPP_ENCODE_STREAM_Attr encodeAttr;
    encodeAttr.InputHeight = 1080;
    encodeAttr.InputWidth = 1920;
    encodeAttr.OutputRingBufferSize = 0;
    encodeAttr.CodecStandard = Codec_Standard;
    encodeAttr.VideoAttr = VPP_ENCODE_VIDEO_Attr{};
    encodeAttr.VideoAttr.Bitrate = 16000;
    encodeAttr.VideoAttr.Framerate = 30;
    encodeAttr.VideoAttr.BitrateControl = VPP_ENCODE_BITRATE_CONTROL_VBR;
    encodeAttr.VideoAttr.Usage = VPP_ENCODE_VIDEO_USAGE_SPEED;
    encodeAttr.VideoAttr.GopPFrameDistance = 2;
    encodeAttr.VideoAttr.GopSize = 100;
    encodeAttr.VideoAttr.RefFrameNum = 2;


    assert(VPP_ENCODE_STREAM_Create(encode_id, &encodeAttr) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_ENCODE_STREAM_Create Done" << std::endl;

    // Create pp stream:
    int32_t ppstream_id = 0;
    VPP_POSTPROC_StreamAttr ppstreamAttr;
    ppstreamAttr.CropX = 0;
    ppstreamAttr.CropY = 0;
    ppstreamAttr.CropW = 1920 * 2;
    ppstreamAttr.CropH = 1080 * 2;
    ppstreamAttr.OutWidth = 1920;
    ppstreamAttr.OutHeight = 1080;
    ppstreamAttr.Rotate = false;
    ppstreamAttr.Angle = VPP_POSTPROC_ROTATE_90;
    ppstreamAttr.Denoise = 32;
    ppstreamAttr.Depth = 3;
    ppstreamAttr.ColorConv = false;
    ppstreamAttr.ColorFormat = VPP_PIXEL_FORMAT_NV12;
    assert(VPP_POSTPROC_STREAM_Create(ppstream_id, &ppstreamAttr) == VPP_STATUS_SUCCESS);

    // Bind decode stream to pp stream:
    VPP_StreamIdentifier decodeIdentifier_1;
    decodeIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_DECODE;
    decodeIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    decodeIdentifier_1.StreamId = decode_id;

    VPP_StreamIdentifier ppIdentifier_1;
    ppIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
    ppIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    ppIdentifier_1.StreamId = ppstream_id;

    assert(VPP_SYS_Bind(decodeIdentifier_1, ppIdentifier_1) == VPP_STATUS_SUCCESS);
    std::cout << "Decode and videolayer VPP_SYS_Bind Done" << std::endl;

    // Bind pp stream to encode stream:
    VPP_StreamIdentifier encodeIdentifier_1;
    encodeIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_ENCODE;
    encodeIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    encodeIdentifier_1.StreamId = encode_id;

    assert(VPP_SYS_Bind(ppIdentifier_1, encodeIdentifier_1) == VPP_STATUS_SUCCESS);
    std::cout << "pp task and Encode Bind Done" << std::endl;

    //Create Video
    assert(VPP_DECODE_STREAM_Start(decode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_DECODE_STREAM_Start 1 Done" << std::endl;

    assert(VPP_ENCODE_STREAM_Start_RecvPicture(encode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_ENCODE_STREAM_Start 1 Done" << std::endl;

    assert(VPP_POSTPROC_STREAM_Start(ppstream_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_PP_STREAM_Start 1 Done" << std::endl;

    // Start input thread:
    std::thread th(send_input, decode_id);

    // Save encoded frames to video file:
    FILE* outputfile;
    
    if ((outputfile = fopen(video_path.c_str(), "wb")) == NULL)
    {
        std::cout << "Open Out Video file fail" << std::endl;
        return 0;
    }

    // get display output frame
    int i = 1;
    while (1)
    {
        // get frame from encode
        VPP_ENCODE_STREAM_OutputBuffer *pOutputBuffer = (VPP_ENCODE_STREAM_OutputBuffer *)malloc(sizeof(VPP_ENCODE_STREAM_OutputBuffer));
        int sts = VPP_ENCODE_STREAM_GetEncodedData(encode_id, pOutputBuffer, 1000);
        if (sts != VPP_STATUS_SUCCESS)
        {
            free(pOutputBuffer);
            if (sts != VPP_STATUS_ERR_ENCODE_TIMEOUT) {
                std::cout << sts << std::endl;
                std::cout << "VPP ENCODE Get Frame Failed" << std::endl;
                continue;
            } 
            else {
                std::cout << sts << std::endl;
                std::cout << "VPP ENCODE Get Frame timeout" << std::endl;
                break;
            }
        }

        //std::cout << "VPP_ENCODE_get_Frame_success" << std::endl;
        //save frame
        fwrite(pOutputBuffer->pAddr, pOutputBuffer->Length, 1, outputfile);
        i++;
        assert(VPP_ENCODE_STREAM_ReleaseEncodedData(encode_id, pOutputBuffer) == VPP_STATUS_SUCCESS);
        free(pOutputBuffer);
    }
    fclose(outputfile);

    // Stop streams:
    assert(VPP_DECODE_STREAM_Stop(decode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_DECODE_STREAM_Stop 0 Done" << std::endl;

    assert(VPP_ENCODE_STREAM_Stop_RecvPicture(encode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_ENCODE_STREAM_Stop 0 Done" << std::endl;

    assert(VPP_POSTPROC_STREAM_Stop(ppstream_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_POSTPROC_STREAM_Stop Done" << std::endl;

    // Unbind streams:
    assert(VPP_SYS_Unbind(decodeIdentifier_1, ppIdentifier_1) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_SYS_Unbind decode and pp Done" << std::endl;

    assert(VPP_SYS_Unbind(ppIdentifier_1, encodeIdentifier_1) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_SYS_Unbind pp and encode Done" << std::endl;

    // Destroy streams:
    assert(VPP_DECODE_STREAM_Destroy(decode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_DECODE_STREAM_Destroy 0 Done" << std::endl;

    assert(VPP_ENCODE_STREAM_Destroy(encode_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_ENCODE_STREAM_Destroy Done" << std::endl;

    assert(VPP_POSTPROC_STREAM_Destroy(ppstream_id) == VPP_STATUS_SUCCESS);
    std::cout << "VPP_POSTPROC_STREAM_Destroy Done" << std::endl;

    // Deinitialize VPP system:
    VPP_DeInit();
    th.join();
}



