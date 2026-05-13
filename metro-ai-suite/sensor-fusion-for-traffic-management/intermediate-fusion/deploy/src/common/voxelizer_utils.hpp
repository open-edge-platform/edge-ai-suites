#pragma once

#include <cstdint>
#include <sycl/sycl.hpp>

namespace bevfusion::voxelizer {

inline int div_up(int value, int divisor)
{
    return value / divisor + ((value % divisor) > 0);
}

inline int atomic_fetch_add(int* addr, int operand)
{
    sycl::atomic_ref<int,
                     sycl::memory_order::relaxed,
                     sycl::memory_scope::device,
                     sycl::access::address_space::global_space>
        obj(*addr);
    return obj.fetch_add(operand);
}

inline std::uint32_t next_power(std::uint32_t value)
{
    value--;
    value |= value >> 1;
    value |= value >> 2;
    value |= value >> 4;
    value |= value >> 8;
    value |= value >> 16;
    value++;
    return value;
}

}  // namespace bevfusion::voxelizer