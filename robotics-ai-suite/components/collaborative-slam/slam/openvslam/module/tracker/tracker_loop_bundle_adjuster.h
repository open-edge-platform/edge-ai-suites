// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_TRACKER_LOOP_BUNDLE_ADJUSTER_H
#define OPENVSLAM_MODULE_TRACKER_LOOP_BUNDLE_ADJUSTER_H

namespace openvslam {

class mapping_module;

namespace data {
class map_database;
}  // namespace data

namespace module {

class tracker_loop_bundle_adjuster: public loop_bundle_adjuster {
public:
    /**
     * Set the mapping module
     */
    void set_mapping_module(mapping_module* mapper);

    /**
     * Run loop BA
     */
    void optimize(const KeyframeID identifier);

private:

    //! mapping module
    mapping_module* mapper_ = nullptr;
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_TRACKER_LOOP_BUNDLE_ADJUSTER_H
