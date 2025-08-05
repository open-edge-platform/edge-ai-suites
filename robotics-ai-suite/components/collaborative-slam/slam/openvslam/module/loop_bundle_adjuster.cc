// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "module/loop_bundle_adjuster.h"
#include "optimize/global_bundle_adjuster.h"

#include <thread>

#include <spdlog/spdlog.h>

namespace openvslam {
namespace module {

loop_bundle_adjuster::loop_bundle_adjuster(data::map_database* map_db, const unsigned int num_iter)
    : map_db_(map_db), num_iter_(num_iter)
{
}

void loop_bundle_adjuster::count_loop_BA_execution()
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    ++num_exec_loop_BA_;
}

void loop_bundle_adjuster::abort()
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    abort_loop_BA_ = true;
}

bool loop_bundle_adjuster::is_running() const
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    return loop_BA_is_running_;
}

}  // namespace module
}  // namespace openvslam
