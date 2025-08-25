// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_SERVER_LOOP_BUNDLE_ADJUSTER_H
#define OPENVSLAM_MODULE_SERVER_LOOP_BUNDLE_ADJUSTER_H


#include "data/keyframe.h"
#include "data/landmark.h"
#include "module/loop_bundle_adjuster.h"

#include <mutex>
#include <unordered_map>
#include <vector>

namespace openvslam {

namespace data {
class map_database;
}  // namespace data

namespace module {

class server_loop_bundle_adjuster: public loop_bundle_adjuster {
public:

    explicit server_loop_bundle_adjuster(data::map_database* map_db, const unsigned int num_iter = 10);

    /**
     * Run loop BA
     */
    void optimize(const KeyframeID identifier, MapID map_id1, MapID map_id2);
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_SERVER_LOOP_BUNDLE_ADJUSTER_H
