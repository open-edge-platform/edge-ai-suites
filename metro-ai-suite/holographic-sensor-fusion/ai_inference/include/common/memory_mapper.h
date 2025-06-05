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

#include "context.h"
#include <memory>

namespace hce{

namespace ai{

namespace inference{

enum class AccessMode { Read = 1, Write = 2, ReadWrite = 3 };

// TODO
// class TensorPtr;
// class FramePtr;
class Context;
using ContextPtr = std::shared_ptr<Context>;
/**
 * @brief MemoryMapper objects can map TensorPtr or FramePtr from one context to another context. It could be mapping
 * between GPU memory and CPU memory, or GPU to GPU mapping between two different frameworks (for example, mapping from
 * OpenCL to SYCL) assuming two contexts allocated on same GPU device.
 * MemoryMapper objects are created by Context::get_mapper function, or utility function create_mapper which is able to
 * create MemoryMapper object as chain of multiple mappers, for example OpenCL to DPC++/SYCL mapper is internally chain
 * of three mappers OpenCL -> DMA -> LevelZero -> SYCL.
 */
class MemoryMapper {
  public:
    virtual ~MemoryMapper() = default;

    /**
     * @brief Map tensor into another context. The function returns mapped tensor, so that the parent() on output tensor
     * returns original tensor and context() on output tensor returns input_context().
     * @param src Tensor to map
     * @param mode Access mode - read or write or read+write
     */
    // TODO
    // virtual TensorPtr map(TensorPtr src, AccessMode mode = AccessMode::ReadWrite) = 0;

    /**
     * @brief Map frame into another context. The function returns mapped frame, so that the parent() on output frame
     * returns original frame and context() on output frame returns input_context().
     * @param src Frame to map
     * @param mode Access mode - read or write or read+write
     */
    // TODO
    // virtual FramePtr map(FramePtr src, AccessMode mode = AccessMode::ReadWrite) = 0;

    /**
     * @brief Returns context specified as input context on mapper object creation
     */
    virtual ContextPtr input_context() const = 0;

    /**
     * @brief Returns context specified as output context on mapper object creation
     */
    virtual ContextPtr output_context() const = 0;
};

using MemoryMapperPtr = std::shared_ptr<MemoryMapper>;

} // namespace inference

} // namespace ai

} // namespace hce

