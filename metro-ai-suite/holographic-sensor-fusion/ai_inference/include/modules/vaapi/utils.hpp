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

#ifndef HCE_AI_INF_VAAPI_UTILS_HPP
#define HCE_AI_INF_VAAPI_UTILS_HPP

#include "common/common.hpp"

#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#ifdef ENABLE_VAAPI
    #include "va/va.h"
    #include "va/va_drm.h"
    #include "vpl/mfxjpeg.h"
    #include "vpl/mfxvideo.h"
    #include "vpl/mfxdispatcher.h"
#endif

namespace hce{

namespace ai{

namespace inference{

// Read encoded stream from buffer
mfxStatus ReadEncodedStreamFromBuffer(mfxBitstream &bs, std::string& content) {
    if (content.size() == 0) {
        if (bs.DataLength == 0)
            return MFX_ERR_MORE_DATA;

        return MFX_ERR_NONE;
    }
    mfxU8 *p0 = bs.Data;
    mfxU8 *p1 = bs.Data + bs.DataOffset;
    if (bs.DataOffset > bs.MaxLength - 1) {
        return MFX_ERR_NOT_ENOUGH_BUFFER;
    }
    if (bs.DataLength + bs.DataOffset > bs.MaxLength) {
        return MFX_ERR_NOT_ENOUGH_BUFFER;
    }
    for (mfxU32 i = 0; i < bs.DataLength; i++) {
        *(p0++) = *(p1++);
    }
    bs.DataOffset = 0;

    mfxU32 readSize = content.size() > bs.MaxLength - bs.DataLength ? bs.MaxLength - bs.DataLength : content.size();
    content.copy((char *)(bs.Data + bs.DataLength), readSize, 0);
    content.erase(content.begin(), content.begin() + readSize);  
    bs.DataLength += readSize;

    if (bs.DataLength == 0)
        return MFX_ERR_MORE_DATA;

    return MFX_ERR_NONE;
}

// Read encoded stream from file
mfxStatus ReadEncodedStream(mfxBitstream &bs, FILE *f) {
    mfxU8 *p0 = bs.Data;
    mfxU8 *p1 = bs.Data + bs.DataOffset;
    if (bs.DataOffset > bs.MaxLength - 1) {
        return MFX_ERR_NOT_ENOUGH_BUFFER;
    }
    if (bs.DataLength + bs.DataOffset > bs.MaxLength) {
        return MFX_ERR_NOT_ENOUGH_BUFFER;
    }
    try {
        memcpy(p1, p0, bs.DataLength);
        bs.DataOffset = 0;
        mfxU32 readSize = (mfxU32)fread(bs.Data + bs.DataLength, 1, bs.MaxLength - bs.DataLength, f);
        if (readSize < (bs.MaxLength - bs.DataLength)) {
            if (feof(f))
                printf("Error fread in ReadEncodedStream: unexpected end of file\n");
            else if (ferror(f))
                perror("Error fread in ReadEncodedStream");
        }
        bs.DataLength += readSize;
    } catch (const std::exception &e) {
        perror("Failed to ReadEncodedStream");
        return MFX_ERR_UNKNOWN;
    }
    
    if (bs.DataLength == 0)
        return MFX_ERR_MORE_DATA;

    return MFX_ERR_NONE;
}


// Write raw I420 frame to dataStr
mfxStatus WriteRawFrame(mfxFrameSurface1 *surface, std::string& dataStr) {
    mfxU16 w, h, i, pitch;
    mfxFrameInfo *info = &surface->Info;
    mfxFrameData *data = &surface->Data;

    w = info->Width;
    h = info->Height;

    // write the output to disk
    switch (info->FourCC) {
        case MFX_FOURCC_I420:
            // Y
            pitch = data->Pitch;
            for (i = 0; i < h; i++) {
                // fwrite(data->Y + i * pitch, 1, w, f);
                dataStr.append((char*)data->Y + i * pitch, w);
            }
            // U
            pitch /= 2;
            h /= 2;
            w /= 2;
            for (i = 0; i < h; i++) {
                // fwrite(data->U + i * pitch, 1, w, f);
                dataStr.append((char*)data->U + i * pitch, w);
            }
            // V
            for (i = 0; i < h; i++) {
                // fwrite(data->V + i * pitch, 1, w, f);
                dataStr.append((char*)data->V + i * pitch, w);
            }
            break;
        case MFX_FOURCC_NV12:
        /**
         * YYYY
         * UVUV
         */
            // Y
            pitch = data->Pitch;
            for (i = 0; i < h; i++) {
                // fwrite(data->Y + i * pitch, 1, w, f);
                dataStr.append((char*)(data->Y + i * pitch), w);
            }
            // UV
            h /= 2;
            for (i = 0; i < h; i++) {
                // fwrite(data->UV + i * pitch, 1, w, f);
                dataStr.append((char*)(data->UV + i * pitch), w);
            }
            break;
        case MFX_FOURCC_RGB4:
            // BGRA
            // pitch: 4096 (1024 * 4<BGRA>), h: 768
            {
                pitch = data->Pitch;
                for (i = 0; i < h; i++) {
                    // fwrite(data->B + i * pitch, 1, pitch, f);
                    dataStr.append((char*)data->B + i * pitch, pitch);
                }
            }
            break;
        case MFX_FOURCC_BGR4:
            // Y
            pitch = data->Pitch;
            for (i = 0; i < h; i++) {
                // fwrite(data->R + i * pitch, 1, pitch, f);
                dataStr.append((char*)data->R + i * pitch, pitch);
            }
            break;
        default:
            return MFX_ERR_UNSUPPORTED;
    }

    return MFX_ERR_NONE;
}

// Write raw frame to dataStr
mfxStatus WriteRawFrame_InternalMem(mfxFrameSurface1 *surface, std::string& dataStr) {
    mfxStatus sts = surface->FrameInterface->Map(surface, MFX_MAP_READ);
    if (sts != MFX_ERR_NONE) {
        printf("mfxFrameSurfaceInterface->Map failed (%d)\n", sts);
        return sts;
    }

    sts = WriteRawFrame(surface, dataStr);
    if (sts != MFX_ERR_NONE) {
        printf("Error in WriteRawFrame\n");
    }

    sts = surface->FrameInterface->Unmap(surface);
    if (sts != MFX_ERR_NONE) {
        printf("mfxFrameSurfaceInterface->Unmap failed (%d)\n", sts);
        return sts;
    }

    sts = surface->FrameInterface->Release(surface);
    if (sts != MFX_ERR_NONE) {
        printf("mfxFrameSurfaceInterface->Release failed (%d)\n", sts);
        return sts;
    }

    return sts;
}

// Shows implementation info for Media SDK or oneVPL
mfxVersion ShowImplInfo(mfxSession session) {
    mfxIMPL impl;
    mfxVersion version = { 0, 1 };

    mfxStatus sts = MFXQueryIMPL(session, &impl);
    if (sts != MFX_ERR_NONE)
        return version;

    sts = MFXQueryVersion(session, &version);
    if (sts != MFX_ERR_NONE)
        return version;

    printf("Session loaded: ApiVersion = %d.%d \timpl= ", version.Major, version.Minor);

    switch (impl) {
        case MFX_IMPL_SOFTWARE:
            puts("Software");
            break;
        case MFX_IMPL_HARDWARE | MFX_IMPL_VIA_VAAPI:
            puts("Hardware:VAAPI");
            break;
        case MFX_IMPL_HARDWARE | MFX_IMPL_VIA_D3D11:
            puts("Hardware:D3D11");
            break;
        case MFX_IMPL_HARDWARE | MFX_IMPL_VIA_D3D9:
            puts("Hardware:D3D9");
            break;
        default:
            puts("Unknown");
            break;
    }

    return version;
}

std::string mfxstatus_to_string(int64_t err) {
    return mfxstatus_to_string(static_cast<mfxStatus>(err));
}

std::string mfxstatus_to_string(mfxStatus err) {
    switch(err)
    {
        case MFX_ERR_NONE:
            return "MFX_ERR_NONE";
        case MFX_ERR_UNKNOWN:
            return "MFX_ERR_UNKNOWN";
        case MFX_ERR_NULL_PTR:
            return "MFX_ERR_NULL_PTR";
        case MFX_ERR_UNSUPPORTED:
            return "MFX_ERR_UNSUPPORTED";
        case MFX_ERR_MEMORY_ALLOC:
            return "MFX_ERR_MEMORY_ALLOC";
        case MFX_ERR_NOT_ENOUGH_BUFFER:
            return "MFX_ERR_NOT_ENOUGH_BUFFER";
        case MFX_ERR_INVALID_HANDLE:
            return "MFX_ERR_INVALID_HANDLE";
        case MFX_ERR_LOCK_MEMORY:
            return "MFX_ERR_LOCK_MEMORY";
        case MFX_ERR_NOT_INITIALIZED:
            return "MFX_ERR_NOT_INITIALIZED";
        case MFX_ERR_NOT_FOUND:
            return "MFX_ERR_NOT_FOUND";
        case MFX_ERR_MORE_DATA:
            return "MFX_ERR_MORE_DATA";
        case MFX_ERR_MORE_SURFACE:
            return "MFX_ERR_MORE_SURFACE";
        case MFX_ERR_ABORTED:
            return "MFX_ERR_ABORTED";
        case MFX_ERR_DEVICE_LOST:
            return "MFX_ERR_DEVICE_LOST";
        case MFX_ERR_INCOMPATIBLE_VIDEO_PARAM:
            return "MFX_ERR_INCOMPATIBLE_VIDEO_PARAM";
        case MFX_ERR_INVALID_VIDEO_PARAM:
            return "MFX_ERR_INVALID_VIDEO_PARAM";
        case MFX_ERR_UNDEFINED_BEHAVIOR:
            return "MFX_ERR_UNDEFINED_BEHAVIOR";
        case MFX_ERR_DEVICE_FAILED:
            return "MFX_ERR_DEVICE_FAILED";
        case MFX_ERR_MORE_BITSTREAM:
            return "MFX_ERR_MORE_BITSTREAM";
        case MFX_ERR_GPU_HANG:
            return "MFX_ERR_GPU_HANG";
        case MFX_ERR_REALLOC_SURFACE:
            return "MFX_ERR_REALLOC_SURFACE";
        case MFX_ERR_RESOURCE_MAPPED:
            return "MFX_ERR_RESOURCE_MAPPED";
        case MFX_ERR_NOT_IMPLEMENTED:
            return "MFX_ERR_NOT_IMPLEMENTED";
        case MFX_WRN_DEVICE_BUSY:
            return "MFX_WRN_DEVICE_BUSY";
        case MFX_WRN_VIDEO_PARAM_CHANGED:
            return "MFX_WRN_VIDEO_PARAM_CHANGED";
        case MFX_WRN_IN_EXECUTION:
            return "MFX_WRN_IN_EXECUTION";

        default:
            break;
    }

    std::string ret("<unknown ");
    ret += std::to_string(err) + ">";
    return ret;
}

std::string mfxColorFourCC_to_string(mfxU32 fourCC) {
    switch(fourCC)
    {
        case MFX_FOURCC_I420:
            return "MFX_FOURCC_I420";
            break;
        case MFX_FOURCC_NV12:
            return "MFX_FOURCC_NV12";
            break;
        case MFX_FOURCC_RGB4:
            return "MFX_FOURCC_RGB4";
            break;
        case MFX_FOURCC_BGR4:
            return "MFX_FOURCC_BGR4";
            break;
        default:
            break;
    }

    std::string ret("<unknown ");
    ret += std::to_string(fourCC) + ">";
    return ret;
}

bool string_to_mfxColorFourCC(std::string color, mfxU32 &fourCC) {

    if (color == "I420")
        fourCC = MFX_FOURCC_I420;
    else if (color == "NV12")
        fourCC = MFX_FOURCC_NV12;
    else if (color == "RGBA")
        fourCC = MFX_FOURCC_RGB4;
    // else if (color == "BGRA")
    //     fourCC = MFX_FOURCC_BGR4;
    else if (color == "BGR")
        fourCC = MFX_FOURCC_BGR4;
    else {
        std::string checkList = "YUV; NV12; RGBA";
        return false;
    }
    return true;
}


mfxU16 FourCCToChroma(mfxU32 fourCC) {
    switch (fourCC) {
        case MFX_FOURCC_NV12:
        case MFX_FOURCC_P010:
        case MFX_FOURCC_P016:
            return MFX_CHROMAFORMAT_YUV420;
        case MFX_FOURCC_NV16:
        case MFX_FOURCC_I422:
        case MFX_FOURCC_I210:
        case MFX_FOURCC_P210:
        case MFX_FOURCC_Y210:
        case MFX_FOURCC_Y216:
        case MFX_FOURCC_YUY2:
            return MFX_CHROMAFORMAT_YUV422;
        case MFX_FOURCC_Y410:
        case MFX_FOURCC_A2RGB10:
        case MFX_FOURCC_AYUV:
        case MFX_FOURCC_RGB4:
        case MFX_FOURCC_BGR4:
            return MFX_CHROMAFORMAT_YUV444;
    }

    return MFX_CHROMAFORMAT_YUV420;
}

}  // namespace inference
}  // namespace ai
}  // namespace hce

#endif //#ifndef HCE_AI_INF_VAAPI_UTILS_HPP