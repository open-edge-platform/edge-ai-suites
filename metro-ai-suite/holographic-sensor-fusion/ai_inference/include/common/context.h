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

#include <stdexcept>
#include <vector>
#include <memory>
#include <string>
#include "memory_type.h"
#include "memory_mapper.h"
#include <map>

namespace hce{

namespace ai{

namespace inference{

#define DLS_CHECK(_VAR)                                                                                                \
    if (!(_VAR))                                                                                                       \
        throw std::runtime_error(std::string(__FUNCTION__) + ": Error on: " #_VAR);

#define DLS_CHECK_GE0(_VAR)                                                                                            \
    {                                                                                                                  \
        auto _res = _VAR;                                                                                              \
        if (_res < 0)                                                                                                  \
            throw std::runtime_error(std::string(__FUNCTION__) + ": Error " + std::to_string(_res) +                   \
                                     " calling: " #_VAR);                                                              \
    }

class Context;
using ContextPtr = std::shared_ptr<Context>;

class MemoryMapper;
using MemoryMapperPtr = std::shared_ptr<MemoryMapper>;

class Context {
  public:
    /**
     * @brief Type of handles stored in context.
     */
    using handle_t = void *;

    virtual ~Context(){};

    // /**
    //  * @brief Returns memory type of this context.
    //  */
    // virtual BufferMemoryType memory_type() const = 0;

    /**
     * @brief Returns memory type of this context.
     */
    virtual MemoryTypeNew memory_type() const = 0;
    /**
     * @brief Returns a handle by key. If empty key, returns default handle. If no handle with the specified key,
     * returns 0.
     * @param key the key of the handle to find
     */
    virtual handle_t handle(std::string_view key = {}) const noexcept = 0;
    /**
     * @brief Returns an object for memory mapping between two contexts. Function typically expects one of contexts to
     * be this context. If one of contexts has memory type CPU or context reference is nullptr, function returns object
     * for mapping to or from system memory. If creating memory mapping object failed, exception is thrown.
     * @param input_context Context of input memory
     * @param output_context Context of output memory
     */
    virtual MemoryMapperPtr get_mapper(const ContextPtr &input_context, const ContextPtr &output_context) = 0;

    /**
     * @brief Create another context of specified memory type. New context belongs to same device (if multiple GPUs) as
     * original context, and parent() returns reference to original context. If creating new context failed, function
     * returns nullptr.
     * @param memory_type Memory type of new context
     */
    virtual ContextPtr derive_context(MemoryTypeNew memory_type) noexcept = 0;
    // /**
    //  * @brief Returns an object for memory mapping between two contexts. Function typically expects one of contexts to
    //  * be this context. If one of contexts has memory type CPU or context reference is nullptr, function returns object
    //  * for mapping to or from system memory. If creating memory mapping object failed, exception is thrown.
    //  * @param input_context Context of input memory
    //  * @param output_context Context of output memory
    //  */
    // virtual MemoryMapperPtr get_mapper(const ContextPtr &input_context, const ContextPtr &output_context) = 0;

    // /**
    //  * @brief Create another context of specified memory type. New context belongs to same device (if multiple GPUs) as
    //  * original context, and parent() returns reference to original context. If creating new context failed, function
    //  * returns nullptr.
    //  * @param memory_type Memory type of new context
    //  */
    // virtual ContextPtr derive_context(BufferMemoryType memory_type) noexcept = 0;

    /**
     * @brief Returns parent context if this context was created from another context via derive_context(), nullptr
     * otherwise.
     */
    virtual ContextPtr parent() noexcept = 0;
};

class BaseContext : public Context {
  public:
    struct key {
        static constexpr auto va_display = "va_display"; // (VAAPI) VADisplay
        static constexpr auto va_tile_id = "va_tile_id"; // (VAAPI) VADisplay
        static constexpr auto cl_context = "cl_context"; // (OpenCL) cl_context
        static constexpr auto cl_queue = "cl_queue";     // (OpenCL) cl_command_queue
        static constexpr auto ze_context = "ze_context"; // (Level-zero) ze_context_handle_t
        static constexpr auto ze_device = "ze_device";   // (Level-zero) ze_device_handle_t
    };

    BaseContext() {};
    BaseContext(MemoryTypeNew memory_type) : _memory_type(memory_type) {
    }

    MemoryTypeNew memory_type() const override {
        return _memory_type;
    }
    handle_t handle(std::string_view /*key*/) const noexcept override {
        return nullptr;
    }

    virtual std::vector<std::string> keys() const {
        return {};
    }
    MemoryMapperPtr get_mapper(const ContextPtr &input_context, const ContextPtr &output_context) override {
        auto mapper_it = _mappers.find({input_context.get(), output_context.get()});
        return (mapper_it != _mappers.end()) ? mapper_it->second : nullptr;
    }
    ContextPtr derive_context(MemoryTypeNew /*memory_type*/) noexcept override {
        return nullptr;
    }
    ContextPtr parent() noexcept override {
        return _parent;
    }

    void set_parent(ContextPtr parent) {
        _parent = parent;
    }
    void attach_mapper(MemoryMapperPtr mapper) {
        if (mapper)
            _mappers[{mapper->input_context().get(), mapper->output_context().get()}] = mapper;
    }

    void remove_mapper(MemoryMapperPtr mapper) {
        // _mappers.erase({mapper->input_context().get(), mapper->output_context().get()});
        _mappers.erase(std::make_pair(mapper->input_context().get(), mapper->output_context().get()));
    }

    ~BaseContext() {
        for (auto &mapper : _mappers) {
            BaseContext *input_context = dynamic_cast<BaseContext *>(mapper.first.first);
            if (input_context && input_context != this)
                input_context->remove_mapper(mapper.second);
            BaseContext *output_context = dynamic_cast<BaseContext *>(mapper.first.second);
            if (output_context && output_context != this)
                output_context->remove_mapper(mapper.second);
        }
    }
    // ~BaseContext() {};

  protected:
    MemoryTypeNew _memory_type;
    ContextPtr _parent;
    std::map<std::pair<Context *, Context *>, MemoryMapperPtr> _mappers; // use pointers (not shared_ptr) by perf reason

    template <typename T>
    static inline std::shared_ptr<T> create_from_another(const ContextPtr &another_context,
                                                         MemoryTypeNew new_memory_type) {
        auto casted = std::dynamic_pointer_cast<T>(another_context);
        if (casted)
            return casted;
        ContextPtr ctx = another_context;
        if (another_context && another_context->memory_type() != new_memory_type) {
            auto derived = another_context->derive_context(new_memory_type);
            if (derived) {
                casted = std::dynamic_pointer_cast<T>(derived);
                if (casted)
                    return casted;
                ctx = derived;
            }
        }
        return std::make_shared<T>(ctx);
    }
};



} // namespace inference

} // namespace ai

} // namespace hce
