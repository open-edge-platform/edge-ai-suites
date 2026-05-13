#pragma once

#include <CL/cl.h>
#include <openvino/openvino.hpp>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include <sycl/sycl.hpp>
#include <stdexcept>
#include <vector>
#include <cstring>

namespace bevfusion {

struct TensorView
{
    enum class Location {
        Host,
        USMDevice,
        USMShared,
        RemoteCL,
        Unknown,
    };

    float *data = nullptr;             // raw pointer when available (host or USM)
    ov::Tensor remote;                 // OpenVINO tensor, usually GPU/RemoteCL
    std::vector<size_t> shape;         // NCHW-like shape
    Location loc = Location::Unknown;  // where the data currently lives

    bool empty() const
    {
        return numel() == 0;
    }

    size_t numel() const
    {
        size_t n = 1;
        for (auto d : shape)
            n *= d;
        return (data == nullptr && !remote) ? 0 : n;
    }

    size_t bytes() const
    {
        return numel() * sizeof(float);
    }

    bool is_host() const
    {
        return loc == Location::Host;
    }
    bool is_usm() const
    {
        return loc == Location::USMDevice || loc == Location::USMShared;
    }
    bool is_remote() const
    {
        return loc == Location::RemoteCL;
    }

    float *device_ptr_or_null() const
    {
        return is_usm() ? data : nullptr;
    }

    static TensorView FromHost(const float *ptr, const std::vector<size_t> &shape_in)
    {
        TensorView t;
        t.data = const_cast<float *>(ptr);
        t.shape = shape_in;
        t.loc = Location::Host;
        return t;
    }

    static TensorView FromUSM(float *ptr, const std::vector<size_t> &shape_in, Location loc = Location::USMDevice)
    {
        TensorView t;
        t.data = ptr;
        t.shape = shape_in;
        t.loc = loc;
        return t;
    }

    static TensorView FromRemote(const ov::Tensor &tensor)
    {
        TensorView t;
        t.remote = tensor;
        if (tensor) {
            const auto &s = tensor.get_shape();
            t.shape.assign(s.begin(), s.end());
            t.loc = Location::RemoteCL;
        }
        else {
            t.shape.clear();
            t.loc = Location::Unknown;
        }
        return t;
    }

    std::vector<float> to_host(sycl::queue *queue) const
    {
        const size_t n = numel();
        std::vector<float> host(n, 0.0f);

        if (n == 0)
            return host;

        if (loc == Location::Host) {
            std::memcpy(host.data(), data, n * sizeof(float));
            return host;
        }

        if (is_usm()) {
            if (!queue)
                throw std::runtime_error("to_host requires queue for USM copy");
            queue->memcpy(host.data(), data, n * sizeof(float)).wait();
            return host;
        }

        if (loc == Location::RemoteCL) {
            if (!queue)
                throw std::runtime_error("to_host requires queue for RemoteCL tensor");
            auto cl_tensor = remote.as<ov::intel_gpu::ocl::ClBufferTensor>();
            if (!cl_tensor)
                throw std::runtime_error("Remote tensor is not ClBufferTensor");

            cl_command_queue clq = sycl::get_native<sycl::backend::opencl>(*queue);
            cl_mem buffer = cl_tensor.get();
            const size_t bytes = n * sizeof(float);
            const cl_int err = clEnqueueReadBuffer(clq, buffer, CL_TRUE, 0, bytes, host.data(), 0, nullptr, nullptr);
            if (err != CL_SUCCESS) {
                throw std::runtime_error("clEnqueueReadBuffer failed with error " + std::to_string(err));
            }
            return host;
        }

        throw std::runtime_error("Unsupported tensor location for to_host");
    }
};

}  // namespace bevfusion
