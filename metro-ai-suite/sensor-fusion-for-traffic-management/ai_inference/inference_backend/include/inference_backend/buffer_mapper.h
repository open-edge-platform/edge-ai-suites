/*******************************************************************************
 * Copyright (C) 2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

// #include "dlstreamer/gst/mappers/gst_to_cpu.h"
// #include "dlstreamer/gst/mappers/gst_to_dma.h"
// #include "dlstreamer/gst/mappers/gst_to_vaapi.h"

#ifdef ENABLE_VAAPI
    #include <va/va.h>
    #include <va/va_drm.h>
    #include <va/va_drmcommon.h>
    #include <vpl/mfxvideo.h>
#endif

#include <inc/api/hvaBuf.hpp>
#include <inc/buffer/hvaVideoFrameWithROIBuf.hpp>

#include "common/context.h"
#include "common/image_info.h"

#include "inference_backend/image.h"

namespace InferenceBackend {

// This class is used as shim between hva::hvaVideoFrameWithROIBuf_t and InferenceBackend::Image
class BufferToImageMapper final {
  public:
    BufferToImageMapper(InferenceBackend::MemoryType memory_type)
        : _memory_type(memory_type) {
    }
    ~BufferToImageMapper() = default;

    InferenceBackend::MemoryType memoryType() const {
        return _memory_type;
    }

    InferenceBackend::ImagePtr map(hva::hvaVideoFrameWithROIBuf_t::Ptr& buffer) {

        ImagePtr image;
        if (_memory_type == MemoryType::SYSTEM) {
            // For system memory, the buffer must remain mapped the lifetime of the image
            auto deleter = [buffer](Image *img) mutable {
                buffer.reset();
                delete img;
            };
            image = {new Image(), deleter};
        } else {
            // For VAAPI and DMA - we don't care because we only need handles.
            image = std::make_shared<Image>();
        }

        // TODO: hvaVideoFrameWithROIBuf_t do not have `format` attribute
        // maybe buffer->getmeta to get input buffer type and format
        // input gpu + inference gpu = nv12
        // input cpu + inference gpu = nv12
        // input gpu + inference cpu = bgr
        // input cpu + inference cpu = bgr
        if (_memory_type == MemoryType::SYSTEM) {
            image->format = InferenceBackend::FourCC::FOURCC_BGR;
#ifdef ENABLE_VAAPI
        } else if (_memory_type == MemoryType::VAAPI) {
            image->format = InferenceBackend::FourCC::FOURCC_NV12;
#endif
        } else {
            // unsupported memory type
            return nullptr;
        }

        // TODO: hvaVideoFrameWithROIBuf_t contents 
        if (_memory_type == MemoryType::SYSTEM || _memory_type == MemoryType::USM_DEVICE_POINTER) {
            // if input buffer is va surface, need map here
            // get buf meta to check the buffer type (uint8 or mfxFrame)
            image->planes[0] = buffer->get<uint8_t*>();
        }
#ifdef ENABLE_VAAPI
        if (_memory_type == MemoryType::VAAPI) {
            mfxFrameSurface1* mfxSurface = buffer->get<mfxFrameSurface1*>();
            mfxHDL surfHandle = nullptr;
            mfxResourceType resourceType;
            mfxStatus sts;
            sts = mfxSurface->FrameInterface->GetNativeHandle(mfxSurface, &surfHandle, &resourceType);
            HVA_ASSERT(resourceType == MFX_RESOURCE_VA_SURFACE);
            image->va_surface_id = *(VASurfaceID *)surfHandle;

            mfxHDL devHandle = nullptr;
            mfxHandleType handleType;
            sts = mfxSurface->FrameInterface->GetDeviceHandle(mfxSurface, &devHandle, &handleType);
            HVA_ASSERT(handleType == MFX_HANDLE_VA_DISPLAY);
            image->va_display = devHandle;
        }
#endif
        image->width = buffer->width;
        image->height = buffer->height;
        image->type = _memory_type;
        for (size_t i = 0; i < buffer->planeNum; i++) {
            image->offsets[i] = buffer->offset[i];
            image->stride[i] = buffer->stride[i];
        }
        return image;
    }

  private:
    InferenceBackend::MemoryType _memory_type;
    // const GstVideoInfo *_video_info;
    // dlstreamer::MemoryMapperPtr _mapper;
};

} // namespace InferenceBackend

class BufferMapperFactory {
  public:
    // static dlstreamer::MemoryMapperPtr createMapper(InferenceBackend::MemoryType memory_type,
    //                                                 dlstreamer::ContextPtr output_context = nullptr) {
    //     switch (memory_type) {
    //     case InferenceBackend::MemoryType::SYSTEM:
    //         return std::make_shared<dlstreamer::MemoryMapperGSTToCPU>(nullptr, output_context);
    //     case InferenceBackend::MemoryType::DMA_BUFFER:
    //         return std::make_shared<dlstreamer::MemoryMapperGSTToDMA>(nullptr, output_context);
    //     case InferenceBackend::MemoryType::VAAPI:
    //         return std::make_shared<dlstreamer::MemoryMapperGSTToVAAPI>(nullptr, output_context);
    //     case InferenceBackend::MemoryType::USM_DEVICE_POINTER:
    //         throw std::runtime_error("Not impemented");
    //     case InferenceBackend::MemoryType::ANY:
    //     default:
    //         break;
    //     }
    //     throw std::runtime_error("MemoryType not specified");
    // }

    // static std::unique_ptr<InferenceBackend::BufferToImageMapper>
    // createMapper(InferenceBackend::MemoryType output_type, const GstVideoInfo *intput_video_info,
    //              dlstreamer::ContextPtr output_context = nullptr) {
    //     dlstreamer::MemoryMapperPtr mapper = createMapper(output_type, output_context);
    //     return std::unique_ptr<InferenceBackend::BufferToImageMapper>(
    //         new InferenceBackend::BufferToImageMapper(output_type, intput_video_info, mapper));
    // }

    static std::unique_ptr<InferenceBackend::BufferToImageMapper>
    createMapper(InferenceBackend::MemoryType output_type, hce::ai::inference::ContextPtr output_context = nullptr) {
        return std::unique_ptr<InferenceBackend::BufferToImageMapper>(
            new InferenceBackend::BufferToImageMapper(output_type));
    }

    BufferMapperFactory() = delete;
};
