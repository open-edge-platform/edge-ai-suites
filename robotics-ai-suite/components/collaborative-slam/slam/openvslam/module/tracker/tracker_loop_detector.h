// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_TRACKER_LOOP_DETECTOR_H
#define OPENVSLAM_MODULE_TRACKER_LOOP_DETECTOR_H

#include "data/bow_vocabulary.h"
#include "module/module_type.h"
#include "module/loop_detector.h"
#include "optimize/transform_optimizer.h"

#include <atomic>

namespace openvslam {

namespace data {
class keyframe;
class bow_database;
}  // namespace data

namespace module {

class tracker_loop_detector: public loop_detector {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    /**
     * Set the current keyframe
     */
    void set_current_keyframe(data::keyframe* keyfrm) override;

    /**
     * Detect loop candidates using BoW vocabulary
     */
    bool detect_loop_candidates() override;

    /**
     * Validate loop candidates selected in detect_loop_candidate()
     */
    bool validate_candidates();

private:

    /**
     * Select ONE candidate from the candidates via linear and nonlinear Sim3 validation
     */
    bool select_loop_candidate_via_Sim3(const std::vector<data::keyframe*>& loop_candidates,
                                        data::keyframe*& selected_candidate, g2o::Sim3& g2o_Sim3_world_to_curr,
                                        std::vector<data::landmark*>& curr_match_lms_observed_in_cand) const;

    //! previously detected keyframe sets as loop candidate
    keyframe_sets cont_detected_keyfrm_sets_;
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_TRACKER_LOOP_DETECTOR_H
