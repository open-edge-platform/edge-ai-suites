// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_GLOBAL_BUNDLE_ADJUSTER_H
#define OPENVSLAM_OPTIMIZE_GLOBAL_BUNDLE_ADJUSTER_H

#include "type.h"

namespace openvslam {

namespace data {
class map_database;
}  // namespace data

namespace optimize {

class global_bundle_adjuster {
public:
    /**
     * Constructor
     * @param map_db
     * @param num_iter
     * @param use_huber_kernel
     */
    explicit global_bundle_adjuster(const KeyframeID first_keyfrm_id_in_db, data::map_database* map_db,
                                    const unsigned int num_iter = 10, const bool use_huber_kernel = true);

    /**
     * Destructor
     */
    virtual ~global_bundle_adjuster() = default;

    /**
     * Perform optimization
     * @param lead_keyfrm_id_in_global_BA
     * @param force_stop_flag
     */
    void optimize(const KeyframeID lead_keyfrm_id_in_global_BA = 0, bool* const force_stop_flag = nullptr) const;
    void optimize(const KeyframeID lead_keyfrm_id_in_global_BA, bool* const force_stop_flag, const MapID map_id1,
                  const MapID map_id2, const KeyframeID fixed_frame_id = 0) const;

private:
    //! first (origin) keyframe id in map database
    // since keyframe id doesn't start from 0 in collab slam
    // therefore we need to mannually pass the id to this class
    const KeyframeID first_keyfrm_id_in_db_;

    //! map database
    const data::map_database* map_db_;

    //! number of iterations of optimization
    unsigned int num_iter_;

    //! use Huber loss or not
    const bool use_huber_kernel_;
};

}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_GLOBAL_BUNDLE_ADJUSTER_H
