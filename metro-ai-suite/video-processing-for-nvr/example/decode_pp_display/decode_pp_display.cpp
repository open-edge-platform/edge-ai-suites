#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <unistd.h>

#include "vpp_common.h"
#include "vpp_decode.h"
#include "vpp_postprocessing.h"
#include "vpp_display.h"
#include "vpp_system.h"

int main(void)
{
    VPP_Init();
    int32_t id = 0;
    VPP_DECODE_STREAM_Attr attr;
    attr.CodecStandard = VPP_CODEC_STANDARD_H265;
    attr.OutputFormat = VPP_PIXEL_FORMAT_NV12;
    attr.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
    attr.OutputHeight = 0;
    attr.OutputWidth = 0;
    attr.OutputBufQueueLength = 0;
    attr.RingBufferSize = 0;

    assert(VPP_DECODE_STREAM_Create(id, &attr) == VPP_STATUS_SUCCESS);

    int32_t stream_id = 0;
    VPP_POSTPROC_StreamAttr streamAttr;
    streamAttr.CropX = 0;
    streamAttr.CropY = 0;
    streamAttr.CropW = 1920;
    streamAttr.CropH = 1080;
    streamAttr.OutWidth = 1920;
    streamAttr.OutHeight = 1080;
    streamAttr.Rotate = false;
    streamAttr.Angle = VPP_POSTPROC_ROTATE_0;
    streamAttr.ColorFormat = VPP_PIXEL_FORMAT_NV12;
    streamAttr.Denoise = 32;
    streamAttr.Depth = 3;

    assert(VPP_POSTPROC_STREAM_Create(stream_id, &streamAttr) == VPP_STATUS_SUCCESS);

    VPP_StreamIdentifier decodeIdentifier_1;
    decodeIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_DECODE;
    decodeIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    decodeIdentifier_1.StreamId = id;
    VPP_StreamIdentifier ppIdentifier_1;
    ppIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
    ppIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    ppIdentifier_1.StreamId = stream_id;

    assert(VPP_SYS_Bind(decodeIdentifier_1, ppIdentifier_1) == VPP_STATUS_SUCCESS);
    printf("Decode and PP stream VPP_SYS_Bind Done \n");

    // Get avaliable device
    VPP_DISPLAY_Dev *pDevArray = nullptr;
    uint32_t deviceCount;
    assert(VPP_DISPLAY_DEV_GetList(&pDevArray, &deviceCount) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_GetList, DeviceCount: %u \n", deviceCount);
    assert(deviceCount > 0);
    assert(pDevArray != nullptr);
    printf("DevAttrsCount: %u \n", pDevArray->DevAttrsCount);

    // Select first avaliable device and create
    int32_t deviceId = pDevArray->DevId;
    assert(VPP_DISPLAY_DEV_Create(deviceId) ==  VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Create Done \n");

    //Set device first Attribute
    VPP_DISPLAY_DEV_SetAttrs(deviceId, pDevArray->pDevAttrs);
    printf("VPP_DISPLAY_DEV_SetAttrs Done \n");

    // Get device Attributes
    VPP_DISPLAY_DEV_Attrs *pDisplayAttrs = new VPP_DISPLAY_DEV_Attrs;
    memset(pDisplayAttrs, 0, sizeof(VPP_DISPLAY_DEV_Attrs));
    VPP_DISPLAY_DEV_GetAttrs(deviceId, pDisplayAttrs);
    printf("VPP_DISPLAY_DEV_GetAttrs Done \n");

    // Create Videolayer
    int32_t videoLayerId = 1;
    assert(VPP_DISPLAY_VIDEOLAYER_Create(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Create Done \n");

    //Set VideoLayer Attributes
    VPP_DISPLAY_VIDEOLAYER_Attrs *pAttrs = new VPP_DISPLAY_VIDEOLAYER_Attrs;
    memset(pAttrs, 0, sizeof(VPP_DISPLAY_VIDEOLAYER_Attrs));
    pAttrs->DisplayRect.X = 0;
    pAttrs->DisplayRect.Y = 0;
    pAttrs->DisplayRect.Width = 1920;
    pAttrs->DisplayRect.Height = 1080;
    pAttrs->FrameBufferSize.Width = 1920;
    pAttrs->FrameBufferSize.Height = 1080;
    pAttrs->FrameRate = 25;
    assert(VPP_DISPLAY_VIDEOLAYER_SetAttrs(videoLayerId, pAttrs) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_SetAttrs Done \n");

    assert(VPP_DISPLAY_VIDEOLAYER_BindDev(videoLayerId, deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_BindDev Done \n");

    //Create Stream
    int32_t streamId_1 = 1;
    assert(VPP_DISPLAY_STREAM_Create(videoLayerId, streamId_1) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_STREAM_Create Done \n");

    //Set Stream attrs
    VPP_DISPLAY_STREAM_Attrs *pStreamAttrs_1 = new VPP_DISPLAY_STREAM_Attrs;
    memset(pStreamAttrs_1, 0, sizeof(VPP_DISPLAY_STREAM_Attrs));
    pStreamAttrs_1->StreamOutRect.X = 0;
    pStreamAttrs_1->StreamOutRect.Y = 0;
    pStreamAttrs_1->StreamOutRect.Width = 1920;
    pStreamAttrs_1->StreamOutRect.Height = 1080;
    assert(VPP_DISPLAY_STREAM_SetAttrs(videoLayerId, streamId_1, pStreamAttrs_1) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_STREAM_SetAttrs Done \n");

    //Set Framerate
    assert(VPP_DISPLAY_STREAM_SetFrameRate(videoLayerId, streamId_1, 25) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_STREAM_SetFrameRate Done \n");

    VPP_StreamIdentifier ppStreamIdentifier_1;
    ppStreamIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
    ppStreamIdentifier_1.DeviceId = VPP_ID_NOT_APPLICABLE;
    ppStreamIdentifier_1.StreamId = stream_id;

    VPP_StreamIdentifier videoLayerIdentifier_1;
    videoLayerIdentifier_1.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
    videoLayerIdentifier_1.DeviceId = videoLayerId;
    videoLayerIdentifier_1.StreamId = streamId_1;
    assert(VPP_SYS_Bind(ppStreamIdentifier_1, videoLayerIdentifier_1) == VPP_STATUS_SUCCESS);
    printf("PP stream and videolayer VPP_SYS_Bind Done \n");

    assert(VPP_DECODE_STREAM_Start(id) == VPP_STATUS_SUCCESS);
    assert(VPP_POSTPROC_STREAM_Start(stream_id) == VPP_STATUS_SUCCESS);
    assert(VPP_DISPLAY_VIDEOLAYER_Start(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Start Done \n");
    assert(VPP_DISPLAY_DEV_Start(deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Start Done \n");

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

        VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);

        if(sizeTemp < size) {
            break;
        }
    }

    VPP_POSTPROC_StreamAttr attrToGet;
    assert(VPP_POSTPROC_STREAM_GetAttr(stream_id, &attrToGet) == VPP_STATUS_SUCCESS);
    assert(streamAttr.CropX == attrToGet.CropX);
    assert(streamAttr.CropY == attrToGet.CropY);
    assert(streamAttr.CropW == attrToGet.CropW);
    assert(streamAttr.CropH == attrToGet.CropH);
    assert(streamAttr.OutWidth == attrToGet.OutWidth);
    assert(streamAttr.OutHeight == attrToGet.OutHeight);
    assert(streamAttr.Rotate == attrToGet.Rotate);
    assert(streamAttr.Angle == attrToGet.Angle);
    assert(streamAttr.Denoise == attrToGet.Denoise);
    assert(streamAttr.ColorFormat == attrToGet.ColorFormat);

    usleep(10000000);
    assert(VPP_DECODE_STREAM_Stop(id) == VPP_STATUS_SUCCESS);
    printf("VPP_DECODE_STREAM_Stop Done \n");
    usleep(1000000);
    assert(VPP_POSTPROC_STREAM_Stop(stream_id) == VPP_STATUS_SUCCESS);
    printf("VPP_POSTPROC_STREAM_Stop Done \n");
    assert(VPP_SYS_Unbind(decodeIdentifier_1, ppIdentifier_1) == VPP_STATUS_SUCCESS);
    printf("VPP_SYS_Unbind decode and pp Done \n");
    usleep(1000000);
    assert(VPP_DISPLAY_VIDEOLAYER_Stop(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Stop Done \n");
    assert(VPP_SYS_Unbind(ppStreamIdentifier_1, videoLayerIdentifier_1) == VPP_STATUS_SUCCESS);
    printf("VPP_SYS_Unbind pp stream and video layer Done \n");
    assert(VPP_DISPLAY_DEV_Stop(deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Stop Done \n");
    assert(VPP_DISPLAY_VIDEOLAYER_UnbindDev(videoLayerId, deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_UnbindDev Done \n");
    assert(VPP_DECODE_STREAM_Destroy(id) == VPP_STATUS_SUCCESS);
    printf("VPP_DECODE_STREAM_Destroy Done \n");
    assert(VPP_POSTPROC_STREAM_Destroy(stream_id) == VPP_STATUS_SUCCESS);
    printf("VPP_POSTPROC_STREAM_Destroy Done \n");
    assert(VPP_DISPLAY_STREAM_Destroy(videoLayerId, streamId_1) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_STREAM_Destroy Done \n");
    assert(VPP_DISPLAY_VIDEOLAYER_Destroy(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Destroy Done \n");
    assert(VPP_DISPLAY_DEV_Destroy(deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Destroy Done \n");
    VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
    fclose(fp);
    free(addr);
    VPP_DeInit();
}