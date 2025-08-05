// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <chrono>

typedef std::chrono::high_resolution_clock timing_clock;

inline std::chrono::time_point<timing_clock> now() { return timing_clock::now(); }

template<typename Time>
inline double duration_ms(const Time& t)
{
    return std::chrono::duration_cast<std::chrono::microseconds>(t).count() * 0.001L;
}

inline double duration_ms(const std::chrono::time_point<timing_clock>& t1,
                          const std::chrono::time_point<timing_clock>& t2)
{
    return duration_ms(t2 - t1);
}

