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

#pragma once

#ifdef ENABLE_VAAPI
    #include <va/va.h>
    #include <va/va_backend.h>
#endif

#include "common/context.h"

namespace hce{

namespace ai{

namespace inference{

class VAAPIContext;
using VAAPIContextPtr = std::shared_ptr<VAAPIContext>;
class VAAPIContext : public BaseContext {
  public:
    struct key {
        static constexpr auto va_display = BaseContext::key::va_display;
        static constexpr auto va_tile_id = BaseContext::key::va_tile_id;
    };

    static inline VAAPIContextPtr create(const ContextPtr &another_context) {
        // FIXME: Add support for VA only
        return create_from_another<VAAPIContext>(another_context, MemoryTypeNew::VAAPI);
    }


    VAAPIContext(void *va_display) : BaseContext(MemoryTypeNew::VAAPI) {
        _va_display = va_display;
    }

    VAAPIContext(const ContextPtr &another_context) : BaseContext(MemoryTypeNew::VAAPI) {
        DLS_CHECK(another_context);
        DLS_CHECK(_va_display = another_context->handle(key::va_display));
        _parent = another_context;
    }

    VADisplay va_display() {
        return _va_display;
    }

    // int get_current_tile_id() const noexcept {
    //     VADisplayAttribValSubDevice reg;
    //     VADisplayAttribute reg_attr;
    //     reg_attr.type = VADisplayAttribType::VADisplayAttribSubDevice;
    //     VADisplayContextP disp_context = reinterpret_cast<VADisplayContextP>(_va_display);
    //     auto drv_context = disp_context->pDriverContext;
    //     auto drv_vtable = *drv_context->vtable;
    //     if (drv_vtable.vaGetDisplayAttributes(drv_context, &reg_attr, 1) == VA_STATUS_SUCCESS) {
    //         reg.value = reg_attr.value;
    //         if (reg.bits.sub_device_count > 0)
    //             return static_cast<int>(reg.bits.current_sub_device);
    //     }
    //     return -1;
    // }

    bool is_valid() noexcept {
        static constexpr int _VA_DISPLAY_MAGIC = 0x56414430; // #include <va/va_backend.h>
        return _va_display && (_VA_DISPLAY_MAGIC == *(int *)_va_display);
    }

    std::vector<std::string> keys() const override {
        return {key::va_display};
    }

    void *handle(std::string_view key) const noexcept override {
        if (key == key::va_display || key.empty())
            return _va_display;
        // if (key == key::va_tile_id || key.empty())
        //     return reinterpret_cast<void *>(static_cast<intptr_t>(get_current_tile_id()));
        return nullptr;
    }

    // MemoryMapperPtr get_mapper(const ContextPtr &input_context, const ContextPtr &output_context) override {
    //     auto mapper = BaseContext::get_mapper(input_context, output_context);
    //     if (mapper)
    //         return mapper;

    //     auto input_type = input_context ? input_context->memory_type() : MemoryTypeNew::CPU;
    //     auto output_type = output_context ? output_context->memory_type() : MemoryTypeNew::CPU;
    //     if (input_type == MemoryTypeNew::VAAPI && output_type == MemoryTypeNew::DMA)
    //         mapper = std::make_shared<MemoryMapperVAAPIToDMA>(input_context, output_context);
    //     if (input_type == MemoryTypeNew::DMA && output_type == MemoryTypeNew::VAAPI)
    //         mapper = std::make_shared<MemoryMapperDMAToVAAPI>(input_context, output_context);

    //     BaseContext::attach_mapper(mapper);
    //     return mapper;
    // }

  protected:
    VADisplay _va_display;
};

} // namespace inference

} // namespace ai

} // namespace hce
