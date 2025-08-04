// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/bow_database.h"
#include "match/bow_tree.h"
#include "match/projection.h"
#include "server_loop_detector.h"
#include "solve/sim3_solver.h"
#include "util/converter.h"

#include <spdlog/spdlog.h>

#define LOOP_DETECT_INTERVAL     10.0

namespace openvslam {
namespace module {

server_loop_detector::server_loop_detector(data::bow_database* bow_db, data::bow_vocabulary* bow_vocab,
                                           const bool fix_scale_in_Sim3_estimation)
    : loop_detector(bow_db, bow_vocab, fix_scale_in_Sim3_estimation)
{
}

void server_loop_detector::set_current_keyframe(data::keyframe* keyfrm) { cur_keyfrm_ = keyfrm; }

bool server_loop_detector::detect_loop_candidates()
{
    // if the loop detector is disabled
    // or current keyframe is not available for loop detector
    // or the loop has been corrected recently for this client
    // we cannot perfrom the loop correction
    if (!loop_detector_is_enabled_) spdlog::debug("!loop_detector_is_enabled_");
    if (!loop_detector_is_enabled_ || !cur_keyfrm_->available_for_loop_detector_ ||
        // use the same magic number as openvslam, we don't want to perform server optimization too often
        cur_keyfrm_->id_ < prev_server_optim_keyfrm_id_[cur_keyfrm_->client_id_] + LOOP_DETECT_INTERVAL) {
        spdlog::debug("avoid loop detection, current keyfrm id : {}, last server optimization keyfrm id : {}",
                      cur_keyfrm_->id_, prev_server_optim_keyfrm_id_[cur_keyfrm_->client_id_]);
        // register to the BoW database
        bow_db_->add_keyframe(cur_keyfrm_);
        return false;
    }

    // 1. search loop candidates by inquiring to the BoW dataqbase

    // 1-1. before inquiring, compute the minimum score of BoW similarity between the current and each of the
    // covisibilities

    const float min_score = compute_min_score_in_covisibilities(cur_keyfrm_);

    // 1-2. inquiring to the BoW database about the similar keyframe whose score is lower than min_score

    auto init_loop_candidates = bow_db_->acquire_loop_candidates(cur_keyfrm_, min_score);

    // 1-3. if no candidates are found, cannot perform the loop correction

    // check if the map of candidate is reset by imu initialization, if so avoid loop detection
    // since we don't want to merge current map to a previous map which has already been reset
    // (because for better accuracy, we don't trust the map with bad imu flag)
    if (!init_loop_candidates.empty()) {
        for (auto it = init_loop_candidates.begin(); it != init_loop_candidates.end();) {
            if (bad_imu_map_ids_.find((*it)->get_map_id()) != bad_imu_map_ids_.end()) {
                it = init_loop_candidates.erase(it);
            } else
                ++it;
        }
    }

    if (init_loop_candidates.empty()) {
        // clear the buffer because any candidates are not found
        cont_detected_keyfrm_sets_[cur_keyfrm_->client_id_].clear();
        // register to the BoW database
        bow_db_->add_keyframe(cur_keyfrm_);
        return false;
    }

    // 2. From now on, we treat each of the candidates as "keyframe set" in order to improve robustness of loop
    //    detection. The number of each of the candidate keyframe sets that detected are counted every time when
    //    this member functions is called if the keyframe sets were detected at the previous call, it is
    //    contained in `cont_detected_keyfrm_sets_` (note that "match of two keyframe sets" means the
    //    intersection of the two sets is NOT empty)

    const auto curr_cont_detected_keyfrm_sets = find_continuously_detected_keyframe_sets(
        cont_detected_keyfrm_sets_[cur_keyfrm_->client_id_], init_loop_candidates);

    // 3. if the number of the detection is equal of greater than the threshold (`min_continuity_`),
    //    adopt it as one of the loop candidates

    loop_candidates_to_validate_.clear();
    for (auto& curr : curr_cont_detected_keyfrm_sets) {
        const auto candidate_keyfrm = curr.lead_keyfrm_;
        const auto continuity = curr.continuity_;
        // check if the number of the detection is equal of greater than the threshold
        if (min_continuity_ <= continuity) {
            // adopt as the candidates
            loop_candidates_to_validate_.push_back(candidate_keyfrm);

            spdlog::debug("candidate_keyfrm client id: {}", candidate_keyfrm->client_id_);
        }
    }

    // 4. Update the members for the next call of this function

    cont_detected_keyfrm_sets_[cur_keyfrm_->client_id_] = curr_cont_detected_keyfrm_sets;

    // register to the BoW database
    bow_db_->add_keyframe(cur_keyfrm_);

    // return any candidate is found or not
    return !loop_candidates_to_validate_.empty();
}

bool server_loop_detector::validate_candidates(g2o::Sim3& g2o_sim3_cand_to_curr)
{
    // disallow the removal of the candidates
    for (const auto candidate : loop_candidates_to_validate_) {
        candidate->set_not_to_be_erased();
    }

    // 1. for each of the candidates, estimate and validate the Sim3 between it and the current keyframe using the
    //    observed landmarks. Then, select ONE candidate

    const bool candidate_is_found =
        select_loop_candidate_via_Sim3(loop_candidates_to_validate_, selected_candidate_, g2o_Sim3_world_to_curr_,
                                       curr_match_lms_observed_in_cand_, g2o_sim3_cand_to_curr);
    Sim3_world_to_curr_ = util::converter::to_eigen_mat(g2o_Sim3_world_to_curr_);

    if (!candidate_is_found) {
        for (const auto loop_candidate : loop_candidates_to_validate_) {
            loop_candidate->set_to_be_erased();
        }
        return false;
    }

    spdlog::debug("detect loop candidate via Sim3 estimation: keyframe {} - keyframe {}", selected_candidate_->id_,
                  cur_keyfrm_->id_);

    // 2. reproject the landmarks observed in covisibilities of the selected candidate to the current keyframe,
    //    then acquire the extra 2D-3D matches between the keypoints in the current keyframe and the landmarks
    //    observed in the covisibilities of the selected candidate
    curr_match_lms_observed_in_cand_covis_.clear();

    auto cand_covisibilities = selected_candidate_->graph_node_->get_covisibilities();
    cand_covisibilities.push_back(selected_candidate_);

    // acquire all of the landmarks observed in the covisibilities of the candidate
    // check the already inserted landmarks
    std::unordered_set<data::landmark*> already_inserted;
    for (const auto covisibility : cand_covisibilities) {
        const auto lms_in_covisibility = covisibility->get_landmarks();
        for (const auto lm : lms_in_covisibility) {
            if (!lm) {
                continue;
            }
            if (lm->will_be_erased()) {
                continue;
            }

            if (already_inserted.count(lm)) {
                continue;
            }
            curr_match_lms_observed_in_cand_covis_.push_back(lm);
            already_inserted.insert(lm);
        }
    }

    // reproject the landmarks observed in the covisibilities of the candidate to the current keyframe using Sim3
    // `Sim3_world_to_curr_`, then, acquire the extra 2D-3D matches however, landmarks in
    // `curr_match_lms_observed_in_cand_` are already matched with keypoints in the current keyframe, thus they are
    // excluded from the reprojection
    match::projection projection_matcher(0.75, true);
    projection_matcher.match_by_Sim3_transform(cur_keyfrm_, Sim3_world_to_curr_,
                                               curr_match_lms_observed_in_cand_covis_,
                                               curr_match_lms_observed_in_cand_, 10);

    // count up the matches
    unsigned int num_final_matches = 0;
    for (const auto curr_assoc_lm_in_cand : curr_match_lms_observed_in_cand_) {
        if (curr_assoc_lm_in_cand) {
            ++num_final_matches;
        }
    }

    spdlog::debug("acquired {} matches after projection-match", num_final_matches);

    // if the number of matches is greater than the threshold, adopt the selected candidate for the loop correction
    constexpr unsigned int num_final_matches_thr = 40;
    if (num_final_matches_thr <= num_final_matches) {
        // allow the removal of the candidates except for the selected one
        for (const auto loop_candidate : loop_candidates_to_validate_) {
            if (*loop_candidate == *selected_candidate_) {
                continue;
            }
            loop_candidate->set_to_be_erased();
        }
        return true;
    } else {
        spdlog::debug("destruct loop candidate because enough matches not acquired (< {})", num_final_matches_thr);
        // allow the removal of all of the candidates
        for (const auto loop_candidate : loop_candidates_to_validate_) {
            loop_candidate->set_to_be_erased();
        }
        return false;
    }
}

bool server_loop_detector::select_loop_candidate_via_Sim3(const std::vector<data::keyframe*>& loop_candidates,
                                                          data::keyframe*& selected_candidate,
                                                          g2o::Sim3& g2o_Sim3_world_to_curr,
                                                          std::vector<data::landmark*>& curr_match_lms_observed_in_cand,
                                                          g2o::Sim3& g2o_sim3_cand_to_curr) const
{
    // estimate and the Sim3 between the current keyframe and each of the candidates using the observed landmarks
    // the Sim3 is estimated both in linear and non-linear ways
    // if the inlier after the estimation is lower than the threshold, discard tha candidate

    match::bow_tree bow_matcher(0.75, true);
    match::projection projection_matcher(0.75, true);

    for (const auto candidate : loop_candidates) {
        if (candidate->will_be_erased()) {
            continue;
        }

        // estimate the matches between the keypoints in the current keyframe and the landmarks observed in the
        // candidate
        curr_match_lms_observed_in_cand.clear();
        const auto num_matches = bow_matcher.match_keyframes(cur_keyfrm_, candidate, curr_match_lms_observed_in_cand);

        // check the threshold
        if (num_matches < 20) {
            continue;
        }

        // estimate the Sim3 using keypoint-landmark matches in linear way
        // keyframe1: current keyframe, keyframe2: candidate keyframe
        // estimate Sim3 of 2->1 (candidate->current)

        solve::sim3_solver solver(cur_keyfrm_, candidate, curr_match_lms_observed_in_cand,
                                  fix_scale_in_Sim3_estimation_, 20);
        solver.find_via_ransac(200);
        if (!solver.solution_is_valid()) {
            continue;
        }

        spdlog::debug("found loop candidate via linear Sim3 estimation: keyframe {} - keyframe {}", candidate->id_,
                      cur_keyfrm_->id_);

        // find additional matches by reprojection landmarks each other

        const Mat33_t rot_cand_to_curr = solver.get_best_rotation_12();
        const Vec3_t trans_cand_to_curr = solver.get_best_translation_12();
        const float scale_cand_to_curr = solver.get_best_scale_12();

        // perform non-linear optimization of the estimated Sim3

        projection_matcher.match_keyframes_mutually(cur_keyfrm_, candidate, curr_match_lms_observed_in_cand,
                                                    scale_cand_to_curr, rot_cand_to_curr, trans_cand_to_curr, 7.5);

        g2o_sim3_cand_to_curr = g2o::Sim3(rot_cand_to_curr, trans_cand_to_curr, scale_cand_to_curr);
        const auto num_optimized_inliers = transform_optimizer_.optimize(
            cur_keyfrm_, candidate, curr_match_lms_observed_in_cand, g2o_sim3_cand_to_curr, 10);

        // check the threshold
        if (num_optimized_inliers < 20) {
            spdlog::debug(" {} num_optimized_inliers <  {}", num_optimized_inliers, 20);
            continue;
        }

        spdlog::debug("found loop candidate via nonlinear Sim3 optimization: keyframe {} - keyframe {}", candidate->id_,
                      cur_keyfrm_->id_);

        selected_candidate = candidate;
        // convert the estimated Sim3 from "candidate -> current" to "world -> current"
        // this Sim3 indicates the correct camera pose oof the current keyframe after loop correction
        g2o_Sim3_world_to_curr =
            g2o_sim3_cand_to_curr * g2o::Sim3(candidate->get_rotation(), candidate->get_translation(), 1.0);

        return true;
    }

    return false;
}

void server_loop_detector::set_server_optim_keyframe_id(const ClientID client_id,
                                                        const KeyframeID server_optim_keyfrm_id)
{
    prev_server_optim_keyfrm_id_[client_id] = server_optim_keyfrm_id;
}

}  // namespace module
}  // namespace openvslam
