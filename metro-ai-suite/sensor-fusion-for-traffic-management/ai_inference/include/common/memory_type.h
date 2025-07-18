/*******************************************************************************
 * Copyright (C) 2018-2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <memory>
#include <stdexcept>

namespace hce{

namespace ai{

namespace inference{

/**
 * @brief Enum lists supported memory types. Memory type CPU may work with any CPU-accessible memory buffers, other
 * memory types assume memory allocation on CPU or GPU via underlying framework and data access via framework-specific
 * memory handles, for example cl_mem in OpenCL.
 */
enum class MemoryTypeNew {
    Any = 0,

    // Direct pointers
    CPU = 0x1,
    USM = 0x2,

    // Memory handles
    DMA = 0x10,
    OpenCL = 0x20,
    VAAPI = 0x40,
    GST = 0x80,
    FFmpeg = 0x100,
    OpenCV = 0x200,
    OpenCVUMat = 0x400,
    OpenVINO = 0x8000,
    PyTorch = 0x10000,
    TensorFlow = 0x20000,
    VA = 0x40000,
};

template <typename T_DOWN, typename T_UP>
static inline std::shared_ptr<T_DOWN> ptr_cast(const std::shared_ptr<T_UP> &ptr_up) {
    auto ptr_down = std::dynamic_pointer_cast<T_DOWN>(ptr_up);
    if (!ptr_down)
        throw std::runtime_error("Error casting to " + std::string(typeid(T_DOWN).name()));
    return ptr_down;
}

inline const char *memory_type_to_string(MemoryTypeNew type) {
    switch (type) {
    case MemoryTypeNew::CPU:
        return "System";
    case MemoryTypeNew::GST:
        return "GStreamer";
    case MemoryTypeNew::FFmpeg:
        return "FFmpeg";
    case MemoryTypeNew::VAAPI:
        return "VASurface";
    case MemoryTypeNew::DMA:
        return "DMABuf";
    case MemoryTypeNew::USM:
        return "USM";
    case MemoryTypeNew::OpenCL:
        return "OpenCL";
    case MemoryTypeNew::OpenCV:
        return "OpenCV";
    case MemoryTypeNew::OpenCVUMat:
        return "OpenCVUMat";
    case MemoryTypeNew::OpenVINO:
        return "OpenVINO";
    case MemoryTypeNew::PyTorch:
        return "PyTorch";
    case MemoryTypeNew::TensorFlow:
        return "TensorFlow";
    case MemoryTypeNew::VA:
        return "VAMemory";
    case MemoryTypeNew::Any:
        return "Any";
    }
    throw std::runtime_error("Unknown MemoryType");
}

static inline MemoryTypeNew memory_type_from_string(std::string str) {
    if (str == "System" || str == "SystemMemory")
        return MemoryTypeNew::CPU;
    if (str == "GStreamer")
        return MemoryTypeNew::GST;
    if (str == "VASurface")
        return MemoryTypeNew::VAAPI;
    if (str == "DMABuf")
        return MemoryTypeNew::DMA;
    if (str == "USM")
        return MemoryTypeNew::USM;
    if (str == "OpenCL")
        return MemoryTypeNew::OpenCL;
    if (str == "OpenVINO")
        return MemoryTypeNew::OpenVINO;
    if (str == "TensorFlow")
        return MemoryTypeNew::TensorFlow;
    if (str == "Any")
        return MemoryTypeNew::Any;
    throw std::runtime_error("Unknown MemoryType string");
}

} // namespace inference

} // namespace ai

} // namespace hce
