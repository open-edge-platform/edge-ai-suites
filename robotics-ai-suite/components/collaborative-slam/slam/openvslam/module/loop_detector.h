// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_MODULE_LOOP_DETECTOR_H
#define OPENVSLAM_MODULE_LOOP_DETECTOR_H

#include "data/bow_vocabulary.h"
#include "module/module_type.h"
#include "optimize/transform_optimizer.h"

#include <atomic>

namespace openvslam {

namespace data {
class keyframe;
class bow_database;
}  // namespace data

namespace module {

class loop_detector {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    /**
     * Constructor
     */
    loop_detector(data::bow_database* bow_db, data::bow_vocabulary* bow_vocab, const bool fix_scale_in_Sim3_estimation);

    /**
     * Enable loop detection
     */
    void enable_loop_detector();

    /**
     * Disable loop detection
     */
    void disable_loop_detector();

    /**
     * Get the loop detector status
     */
    bool is_enabled() const;

    /**
     * Set the current keyframe
     */
    virtual void set_current_keyframe(data::keyframe* keyfrm) = 0;

    /**
     * Detect loop candidates using BoW vocabulary
     */
    virtual bool detect_loop_candidates() = 0;


    /**
     * Get the selected candidate keyframe after loop detection and validation
     */
    data::keyframe* get_selected_candidate_keyframe() const;

    /**
     * Get the estimated Sim3 from the world the the current
     */
    g2o::Sim3 get_Sim3_world_to_current() const;

    /**
     * Get the matches between the keypoint indices of the current keyframe and the landmarks observed in the candidate
     */
    std::vector<data::landmark*> current_matched_landmarks_observed_in_candidate() const;

    /**
     * Get the matches between the keypoint indices of the current keyframe and the landmarks observed in covisibilities
     * of the candidate
     */
    std::vector<data::landmark*> current_matched_landmarks_observed_in_candidate_covisibilities() const;

    /**
     * Set the keyframe ID when loop correction is performed
     * no longer used, please refer to the comment for prev_loop_correct_keyfrm_id_
     */
    void set_loop_correct_keyframe_id(const KeyframeID loop_correct_keyfrm_id);

protected:

    /**
     * Compute the minimum score among covisibilities
     */
    float compute_min_score_in_covisibilities(data::keyframe* keyfrm) const;

    /**
     * Find continuously detected keyframe sets
     */
    keyframe_sets find_continuously_detected_keyframe_sets(const keyframe_sets& prev_cont_detected_keyfrm_sets,
                                                           const std::vector<data::keyframe*>& keyfrms_to_search) const;



    //! BoW database
    data::bow_database* bow_db_;
    //! BoW vocabulary
    data::bow_vocabulary* bow_vocab_;

    //! transform optimizer
    const optimize::transform_optimizer transform_optimizer_;

    //! flag which indicates the loop detector is enabled or not
    std::atomic<bool> loop_detector_is_enabled_{true};

    //! for stereo/RGBD models, fix scale when estimating Sim3
    const bool fix_scale_in_Sim3_estimation_;

    //-----------------------------------------
    // variables for loop detection and correction

    //! current keyframe
    data::keyframe* cur_keyfrm_ = nullptr;
    //! final loop candidate
    data::keyframe* selected_candidate_ = nullptr;

    //! loop candidate for validation
    std::vector<data::keyframe*> loop_candidates_to_validate_;

    //! matches between the keypoint indices of the current keyframe and the landmarks observed in the candidate
    std::vector<data::landmark*> curr_match_lms_observed_in_cand_;
    //! matches between the keypoint indices of the current keyframe and the landmarks observed in covisibilities of the
    //! candidate
    std::vector<data::landmark*> curr_match_lms_observed_in_cand_covis_;

    //! the Sim3 camera pose of the current keyframe AFTER loop correction (in Mat44_t format)
    Mat44_t Sim3_world_to_curr_;
    //! the Sim3 camera pose of the current keyframe AFTER loop correction (in g2o::Sim3 format)
    g2o::Sim3 g2o_Sim3_world_to_curr_;

    //! the keyframe ID when the previouls loop correction was performed
    /*
        prev_loop_correct_keyfrm_id_ is no longer used in our multi-slam architecture,
        it is reserved since they are the original OpenVSLAM design;
        instead, we use prev_server_optim_keyfrm_id_ defined in server_loop_detector.h
        which contains information of last server optimization keyframe id for each client
    */
    KeyframeID prev_loop_correct_keyfrm_id_ = 0;

    //! the threshold of the continuity of continuously detected keyframe set
    static constexpr unsigned int min_continuity_ = 3;
};

}  // namespace module
}  // namespace openvslam

#endif  // OPENVSLAM_MODULE_LOOP_DETECTOR_H
