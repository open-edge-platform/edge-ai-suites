// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_UTIL_RANDOM_ARRAY_H
#define OPENVSLAM_UTIL_RANDOM_ARRAY_H

#include <vector>
#include <random>

namespace openvslam {
namespace util {

std::mt19937 create_random_engine();

template<typename T>
std::vector<T> create_random_array(const size_t size, const T rand_min, const T rand_max);

} // namespace util
} // namespace openvslam

#endif // OPENVSLAM_UTIL_RANDOM_ARRAY_H
