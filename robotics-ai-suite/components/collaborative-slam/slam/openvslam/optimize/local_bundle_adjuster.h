// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_LOCAL_BUNDLE_ADJUSTER_H
#define OPENVSLAM_OPTIMIZE_LOCAL_BUNDLE_ADJUSTER_H
#include <string>
namespace openvslam {

namespace data {
class keyframe;
class map_database;
}  // namespace data

namespace optimize {

class local_bundle_adjuster {
public:
    /**
     * Constructor
     * @param map_db
     * @param num_first_iter
     * @param num_second_iter
     */
    explicit local_bundle_adjuster(data::map_database* map_db, const bool use_odom = false,
                                   const unsigned int num_first_iter = 5, const unsigned int num_second_iter = 10);
    explicit local_bundle_adjuster(const unsigned int num_first_iter = 5, const unsigned int num_second_iter = 10);

    /**
     * Destructor
     */
    virtual ~local_bundle_adjuster() = default;

    /**
     * Perform optimization
     * @param curr_keyfrm
     * @param force_stop_flag
     */
    void optimize(data::keyframe* curr_keyfrm, bool* const force_stop_flag, const bool is_large) const;

private:
    void optimize_server_node(data::keyframe* curr_keyfrm, bool* const force_stop_flag) const;

    void optimize_tracker_node(data::keyframe* curr_keyfrm, bool* const force_stop_flag, const bool is_large) const;

    void optimize_without_imu(data::keyframe* curr_keyfrm, bool* const force_stop_flag) const;

    void optimize_with_imu(data::keyframe* curr_keyfrm, bool* const force_stop_flag, bool is_large) const;

    void optimize_from_server(data::keyframe* curr_keyfrm, bool* const force_stop_flag) const;

    //! number of iterations of first optimization
    const unsigned int num_first_iter_;
    //! number of iterations of second optimization
    const unsigned int num_second_iter_;

    data::map_database* map_db_ = nullptr;

    const bool use_odom_;
};

}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_LOCAL_BUNDLE_ADJUSTER_H
