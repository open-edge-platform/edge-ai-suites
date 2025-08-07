// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/bow_database.h"
#include "match/bow_tree.h"
#include "match/projection.h"
#include "module/loop_detector.h"
#include "solve/sim3_solver.h"
#include "util/converter.h"

#include <spdlog/spdlog.h>

namespace openvslam {
namespace module {

loop_detector::loop_detector(data::bow_database* bow_db, data::bow_vocabulary* bow_vocab,
                             const bool fix_scale_in_Sim3_estimation)
    : bow_db_(bow_db),
      bow_vocab_(bow_vocab),
      transform_optimizer_(fix_scale_in_Sim3_estimation),
      fix_scale_in_Sim3_estimation_(fix_scale_in_Sim3_estimation)
{
}

void loop_detector::enable_loop_detector() { loop_detector_is_enabled_ = true; }

void loop_detector::disable_loop_detector() { loop_detector_is_enabled_ = false; }

bool loop_detector::is_enabled() const { return loop_detector_is_enabled_; }



float loop_detector::compute_min_score_in_covisibilities(data::keyframe* keyfrm) const
{
    // the maximum of score is 1.0
    float min_score = 1.0;

    // search the mininum score among covisibilities
    const auto covisibilities = keyfrm->graph_node_->get_covisibilities();
    const auto& bow_vec_1 = keyfrm->bow_vec_;
    for (const auto covisibility : covisibilities) {
        if (unlikely(covisibility->will_be_erased())) {
            continue;
        }
        const auto& bow_vec_2 = covisibility->bow_vec_;

#ifdef USE_DBOW2
        const float score = bow_vocab_->score(bow_vec_1, bow_vec_2);
#else
        const float score = fbow::BoWVector::score(bow_vec_1, bow_vec_2);
#endif
        if (score < min_score) {
            min_score = score;
        }
    }

    return min_score;
}

keyframe_sets loop_detector::find_continuously_detected_keyframe_sets(
    const keyframe_sets& prev_cont_detected_keyfrm_sets, const std::vector<data::keyframe*>& keyfrms_to_search) const
{
    // count up the number of the detection of each of the keyframe sets

    // buffer to store continuity and keyframe set
    keyframe_sets curr_cont_detected_keyfrm_sets;

    // check the already counted keyframe sets to prevent from counting the same set twice
    std::map<std::set<data::keyframe*>, bool> already_checked;
    for (const auto& prev : prev_cont_detected_keyfrm_sets) {
        already_checked[prev.keyfrm_set_] = false;
    }

    for (const auto& keyfrm_to_search : keyfrms_to_search) {
        // enlarge the candidate to the "keyframe set"
        const auto keyfrm_set = keyfrm_to_search->graph_node_->get_connected_keyframes();

        // check if the initialization of the buffer is needed or not
        bool initialization_is_needed = true;

        // check continuity for each of the previously detected keyframe set
        for (const auto& prev : prev_cont_detected_keyfrm_sets) {
            // prev.keyfrm_set_: keyframe set
            // prev.lead_keyfrm_: the leader keyframe of the set
            // prev.continuity_: continuity

            // check if the keyframe set is already counted or not
            if (already_checked.at(prev.keyfrm_set_)) {
                continue;
            }

            // compute intersection between the previous set and the current set, then check if it is empty or not
            if (prev.intersection_is_empty(keyfrm_set)) {
                continue;
            }

            // initialization is not needed because any candidate is found
            initialization_is_needed = false;

            // create the new statistics by incrementing the continuity
            const auto curr_continuity = prev.continuity_ + 1;
            curr_cont_detected_keyfrm_sets.emplace_back(keyframe_set{keyfrm_set, keyfrm_to_search, curr_continuity});

            // this keyframe set is already checked
            already_checked.at(prev.keyfrm_set_) = true;
        }

        // if initialization is needed, add the new statistics
        if (initialization_is_needed) {
            curr_cont_detected_keyfrm_sets.emplace_back(keyframe_set{keyfrm_set, keyfrm_to_search, 0});
        }
    }

    return curr_cont_detected_keyfrm_sets;
}



data::keyframe* loop_detector::get_selected_candidate_keyframe() const { return selected_candidate_; }

g2o::Sim3 loop_detector::get_Sim3_world_to_current() const { return g2o_Sim3_world_to_curr_; }

std::vector<data::landmark*> loop_detector::current_matched_landmarks_observed_in_candidate() const
{
    return curr_match_lms_observed_in_cand_;
}

std::vector<data::landmark*> loop_detector::current_matched_landmarks_observed_in_candidate_covisibilities() const
{
    return curr_match_lms_observed_in_cand_covis_;
}

void loop_detector::set_loop_correct_keyframe_id(const KeyframeID loop_correct_keyfrm_id)
{
    prev_loop_correct_keyfrm_id_ = loop_correct_keyfrm_id;
}

}  // namespace module
}  // namespace openvslam
