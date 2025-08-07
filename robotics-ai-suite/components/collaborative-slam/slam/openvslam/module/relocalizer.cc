// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/map_database.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/bow_database.h"
#include "module/relocalizer.h"
#include "util/fancy_index.h"

#include <spdlog/spdlog.h>

namespace openvslam {
namespace module {

relocalizer::relocalizer(data::bow_database* bow_db, camera::setup_type_t camera_type, const double bow_match_lowe_ratio,
                         const double proj_match_lowe_ratio, const unsigned int min_num_bow_matches,
                         const unsigned int min_num_valid_obs)
    : bow_db_(bow_db),
      min_num_bow_matches_(min_num_bow_matches),
      min_num_valid_obs_(min_num_valid_obs),
      bow_matcher_(bow_match_lowe_ratio, true),
      proj_matcher_(proj_match_lowe_ratio, true),
      pose_optimizer_(camera_type)
{
    spdlog::debug("CONSTRUCT: module::relocalizer");
}

relocalizer::~relocalizer() { spdlog::debug("DESTRUCT: module::relocalizer"); }

void relocalizer::set_camera_type(camera::setup_type_t camera_type) {
    pose_optimizer_.set_camera_type(camera_type);
}

bool relocalizer::relocalize(data::frame& curr_frm)
{
    curr_frm.compute_bow();

    // acquire relocalization candidates
    const auto reloc_candidates = bow_db_->acquire_relocalization_candidates(&curr_frm);
    if (reloc_candidates.empty()) {
        return false;
    }
    const auto num_candidates = reloc_candidates.size();

    std::vector<std::vector<data::landmark*>> matched_landmarks(num_candidates);

    // 各候補について，BoW tree matcherで対応点を求める
    for (unsigned int i = 0; i < num_candidates; ++i) {
        auto keyfrm = reloc_candidates.at(i);
        if (keyfrm->will_be_erased()) {
            continue;
        }
        matched_landmarks.at(i) = std::vector<data::landmark*>(curr_frm.num_keypts_, nullptr);
        const auto num_matches = bow_matcher_.match_frame_and_keyframe(keyfrm, curr_frm, matched_landmarks.at(i));
        // discard the candidate if the number of 2D-3D matches is less than the threshold
        if (num_matches < min_num_bow_matches_) {
            continue;
        }

        // setup PnP solver with the current 2D-3D matches
        const auto valid_indices = extract_valid_indices(matched_landmarks.at(i));
        auto pnp_solver = setup_pnp_solver(valid_indices, curr_frm.bearings_, curr_frm.keypts_, matched_landmarks.at(i),
                                           curr_frm.scale_factors_);

        // 1. Estimate the camera pose with EPnP(+RANSAC)

        pnp_solver->find_via_ransac(30);
        if (!pnp_solver->solution_is_valid()) {
            continue;
        }

        curr_frm.cam_pose_cw_ = pnp_solver->get_best_cam_pose();
        curr_frm.update_pose_params();

        // 2. Apply pose optimizer

        // get the inlier indices after EPnP+RANSAC
        const auto inlier_indices = util::resample_by_indices(valid_indices, pnp_solver->get_inlier_flags());

        // set 2D-3D matches for the pose optimization
        curr_frm.landmarks_ = std::vector<data::landmark*>(curr_frm.num_keypts_, nullptr);
        std::set<data::landmark*> already_found_landmarks;
        for (const auto idx : inlier_indices) {
            // 有効な3次元点のみをcurrent frameにセット
            curr_frm.landmarks_.at(idx) = matched_landmarks.at(i).at(idx);
            // すでに特徴点と対応した3次元点を記録しておく
            already_found_landmarks.insert(matched_landmarks.at(i).at(idx));
        }

        // pose optimization
        auto num_valid_obs = pose_optimizer_.optimize(curr_frm);
        // discard the candidate if the number of the inliers is less than the threshold
        if (num_valid_obs < min_num_bow_matches_ / 2) {
            continue;
        }

        // reject outliers
        for (unsigned int idx = 0; idx < curr_frm.num_keypts_; idx++) {
            if (!curr_frm.outlier_flags_.at(idx)) {
                continue;
            }
            curr_frm.landmarks_.at(idx) = nullptr;
        }

        // 3. Apply projection match to increase 2D-3D matches

        // projection match based on the pre-optimized camera pose
        auto num_found =
            proj_matcher_.match_frame_and_keyframe(curr_frm, reloc_candidates.at(i), already_found_landmarks, 10, 100);
        // discard the candidate if the number of the inliers is less than the threshold
        if (num_valid_obs + num_found < min_num_valid_obs_) {
            continue;
        }

        // 4. Re-apply the pose optimizer

        num_valid_obs = pose_optimizer_.optimize(curr_frm);

        // 閾値未満になったら，もう一度projection matchを行う
        if (num_valid_obs < min_num_valid_obs_) {
            // すでに対応がついているものは除く
            already_found_landmarks.clear();
            for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
                if (!curr_frm.landmarks_.at(idx)) {
                    continue;
                }
                already_found_landmarks.insert(curr_frm.landmarks_.at(idx));
            }
            // もう一度projection matchを行う -> 2D-3D対応を設定
            auto num_additional = proj_matcher_.match_frame_and_keyframe(curr_frm, reloc_candidates.at(i),
                                                                         already_found_landmarks, 3, 64);

            // 閾値未満だったら破棄
            if (num_valid_obs + num_additional < min_num_valid_obs_) {
                continue;
            }

            // もう一度最適化
            num_valid_obs = pose_optimizer_.optimize(curr_frm);

            // 閾値未満だったら破棄
            if (num_valid_obs < min_num_valid_obs_) {
                continue;
            }
        }

        // relocalize成功
        spdlog::info("relocalization succeeded");
        // TODO: current frameのreference keyframeをセットする

        // reject outliers
        for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
            if (!curr_frm.outlier_flags_.at(idx)) {
                continue;
            }
            curr_frm.landmarks_.at(idx) = nullptr;
        }

        return true;
    }

    curr_frm.cam_pose_cw_is_valid_ = false;
    return false;
}

bool relocalizer::relocalize(data::frame& curr_frm, MapID& map_id, data::map_database* map_db,
                             data::bow_vocabulary* bow_vocab, double near_distance, double far_distance,
                             double back_distance)
{
    curr_frm.compute_bow();

    // acquire relocalization candidates
    const auto reloc_candidates = bow_db_->acquire_relocalization_candidates(&curr_frm);
    if (reloc_candidates.empty()) {
        return false;
    }
    const auto num_candidates = reloc_candidates.size();

    std::vector<std::vector<data::landmark*>> matched_landmarks(num_candidates);

    // 各候補について，BoW tree matcherで対応点を求める
    for (unsigned int i = 0; i < num_candidates; ++i) {
        auto keyfrm = reloc_candidates.at(i);
        if (keyfrm->will_be_erased()) {
            continue;
        }

        std::shared_ptr<data::keyframe> projection_keyframe =
            get_projection_keyfrm(keyfrm, map_db, bow_vocab, near_distance, far_distance, back_distance);

        // covisibility_keyframe means a virtual frame composed of landmarks in the 5 largest covisibility keyframes
        std::shared_ptr<data::keyframe> covisibility_keyframe = get_covisibility_keyfrm(keyfrm, map_db, bow_vocab, 5);

        // match twice with bow tree,
        // first match only in keyframe,
        // second match in covisibility keyframe.

        // (covisibility keyframe is more efficient than projection keyframe.
        // It may be because orb was not specific enough and projection keyframe has more landmarksso that there will
        // have more mismatch
        matched_landmarks.at(i) = std::vector<data::landmark*>(curr_frm.num_keypts_, nullptr);
        const auto num_matches_first = bow_matcher_.match_frame_and_keyframe(keyfrm, curr_frm, matched_landmarks.at(i));

        const auto num_matches_twice =
            bow_matcher_.match_frame_and_keyframe(covisibility_keyframe.get(), curr_frm, matched_landmarks.at(i));

        const auto num_matches = num_matches_first + num_matches_twice;

        // discard the candidate if the number of 2D-3D matches is less than the threshold
        if (num_matches < min_num_bow_matches_) {
            continue;
        }

        // setup PnP solver with the current 2D-3D matches
        const auto valid_indices = extract_valid_indices(matched_landmarks.at(i));
        auto pnp_solver = setup_pnp_solver(valid_indices, curr_frm.bearings_, curr_frm.keypts_, matched_landmarks.at(i),
                                           curr_frm.scale_factors_);

        // 1. Estimate the camera pose with EPnP(+RANSAC)

        pnp_solver->find_via_ransac(30);
        if (!pnp_solver->solution_is_valid()) {
            continue;
        }

        curr_frm.cam_pose_cw_ = pnp_solver->get_best_cam_pose();
        curr_frm.update_pose_params();

        // 2. Apply pose optimizer

        // get the inlier indices after EPnP+RANSAC
        const auto inlier_indices = util::resample_by_indices(valid_indices, pnp_solver->get_inlier_flags());

        // set 2D-3D matches for the pose optimization
        curr_frm.landmarks_ = std::vector<data::landmark*>(curr_frm.num_keypts_, nullptr);
        std::set<data::landmark*> already_found_landmarks;
        for (const auto idx : inlier_indices) {
            // 有効な3次元点のみをcurrent frameにセット
            curr_frm.landmarks_.at(idx) = matched_landmarks.at(i).at(idx);
            // すでに特徴点と対応した3次元点を記録しておく
            already_found_landmarks.insert(matched_landmarks.at(i).at(idx));
        }

        // pose optimization
        auto num_valid_obs = pose_optimizer_.optimize(curr_frm);
        // discard the candidate if the number of the inliers is less than the threshold
        if (num_valid_obs < min_num_bow_matches_ / 2) {
            continue;
        }

        // reject outliers
        for (unsigned int idx = 0; idx < curr_frm.num_keypts_; idx++) {
            if (!curr_frm.outlier_flags_.at(idx)) {
                continue;
            }
            curr_frm.landmarks_.at(idx) = nullptr;
        }

        // 3. Apply projection match to increase 2D-3D matches

        // projection match based on the pre-optimized camera pose
        auto num_found = proj_matcher_.match_frame_and_keyframe(curr_frm, projection_keyframe.get(),
                                                                already_found_landmarks, 10, 100);
        // discard the candidate if the number of the inliers is less than the threshold
        if (num_valid_obs + num_found < min_num_valid_obs_) {
            continue;
        }

        // 4. Re-apply the pose optimizer

        num_valid_obs = pose_optimizer_.optimize(curr_frm);

        // 閾値未満になったら，もう一度projection matchを行う
        if (num_valid_obs < min_num_valid_obs_) {
            // すでに対応がついているものは除く
            already_found_landmarks.clear();
            for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
                if (!curr_frm.landmarks_.at(idx)) {
                    continue;
                }
                already_found_landmarks.insert(curr_frm.landmarks_.at(idx));
            }
            // もう一度projection matchを行う -> 2D-3D対応を設定
            auto num_additional = proj_matcher_.match_frame_and_keyframe(curr_frm, projection_keyframe.get(),
                                                                         already_found_landmarks, 3, 64);

            // 閾値未満だったら破棄
            if (num_valid_obs + num_additional < min_num_valid_obs_) {
                continue;
            }

            // もう一度最適化
            num_valid_obs = pose_optimizer_.optimize(curr_frm);

            // 閾値未満だったら破棄
            if (num_valid_obs < min_num_valid_obs_) {
                continue;
            }
        }

        // relocalize成功
        spdlog::info("relocalization succeeded");
        // TODO: current frameのreference keyframeをセットする

        // reject outliers
        for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
            if (!curr_frm.outlier_flags_.at(idx)) {
                continue;
            }
            curr_frm.landmarks_.at(idx) = nullptr;
        }

        // set map id
        // curr_frm.set_map_id(keyfrm->get_map_id());
        map_id = keyfrm->get_map_id();

        return true;
    }

    curr_frm.cam_pose_cw_is_valid_ = false;
    return false;
}

std::shared_ptr<data::keyframe> relocalizer::get_covisibility_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                                     data::bow_vocabulary* bow_vocab, int top_number)
{
    std::vector<data::keyframe*> covisi_kfs = keyfrm->graph_node_->get_top_n_covisibilities(top_number);
    covisi_kfs.push_back(keyfrm);

    std::vector<data::landmark*> nearby_landmarks;
    std::unordered_set<unsigned int> landmarks_ids;
    for (auto kf : covisi_kfs) {
        std::vector<data::landmark*> lms = kf->get_landmarks();
        for (auto lm : lms) {
            if (!lm) continue;
            if (landmarks_ids.find(lm->id_) != landmarks_ids.end()) continue;
            nearby_landmarks.push_back(lm);
            landmarks_ids.emplace(lm->id_);
        }
    }

    std::shared_ptr<data::keyframe> virtual_keyframe = get_virtual_keyfrm(keyfrm, map_db, bow_vocab, nearby_landmarks);

    return virtual_keyframe;
}

std::shared_ptr<data::keyframe> relocalizer::get_projection_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                                   data::bow_vocabulary* bow_vocab,
                                                                   double near_distance, double far_distance, double back_distance)
{
    std::vector<cv::Point3f> point_3d;
    std::vector<cv::Point2f> point_2d;
    std::vector<cv::Point2f> convex_hull;
    std::vector<data::landmark*> nearby_landmarks =
        map_db->get_landmarks_in_frustum(keyfrm->get_cam_pose(), keyfrm->camera_, keyfrm->get_map_id(), 0, false,
                                         point_3d, point_2d, convex_hull, near_distance, far_distance, back_distance);

    std::shared_ptr<data::keyframe> virtual_keyframe = get_virtual_keyfrm(keyfrm, map_db, bow_vocab, nearby_landmarks);
    return virtual_keyframe;
}

std::shared_ptr<data::keyframe> relocalizer::get_virtual_keyfrm(data::keyframe* keyfrm, data::map_database* map_db,
                                                                data::bow_vocabulary* bow_vocab,
                                                                std::vector<data::landmark*>& nearby_landmarks)
{
    std::vector<cv::KeyPoint> keypts, undist_keypts;
    size_t num_keypts = nearby_landmarks.size();
    std::vector<float> stereo_x_right(num_keypts, 0), depths(num_keypts, 0);
    std::vector<data::landmark*> lm_vec(num_keypts, nullptr);
    cv::Mat descriptors(num_keypts, 32, CV_8U);
    openvslam::eigen_alloc_vector<Eigen::Vector3d> bearings;
    bearings.resize(num_keypts);
    auto camera_pose = keyfrm->get_cam_pose();
    unsigned int idx = 0;

    for (auto lm : nearby_landmarks) {
        // TODO: now the descriptor may be invalid, that is a bug
        if (lm->get_descriptor().cols != 32) continue;
        descriptors.row(idx) = lm->get_descriptor();
        Eigen::Vector3d lm_in_camera =
            camera_pose.block(0, 0, 3, 3) * lm->get_pos_in_world() + camera_pose.block(0, 3, 3, 1);

        if (lm_in_camera[2] <= 0)
            lm_vec[idx] = nullptr;
        else {
            lm_vec[idx] = lm;

            lm_in_camera = lm_in_camera / lm_in_camera[2];

            bearings[idx] = lm_in_camera / lm_in_camera.head(2).norm();
        }
        idx++;
    }
    static const unsigned int num_scale_levels = keyfrm->num_scale_levels_;
    static const float scale_factor = keyfrm->scale_factor_;

    std::shared_ptr<data::keyframe> virtual_keyframe = std::make_shared<data::keyframe>(
        static_cast<unsigned int>(-1), static_cast<unsigned int>(-1), keyfrm->timestamp_, camera_pose, keyfrm->camera_,
        keyfrm->depth_thr_, num_keypts, keypts, undist_keypts, bearings, stereo_x_right, depths, descriptors,
        num_scale_levels, scale_factor, bow_vocab, bow_db_, map_db, 10, 10);
    if (!virtual_keyframe)
        throw std::runtime_error("Could not create vrtual keyframe in relocalizer!");
    for (unsigned int i = 0; i < num_keypts; i++) {
        if (lm_vec[i]) {
            virtual_keyframe->add_landmark(lm_vec[i], i);
        }
    }
    return virtual_keyframe;
}

std::vector<unsigned int> relocalizer::extract_valid_indices(const std::vector<data::landmark*>& landmarks) const
{
    std::vector<unsigned int> valid_indices;
    valid_indices.reserve(landmarks.size());
    for (unsigned int idx = 0; idx < landmarks.size(); ++idx) {
        auto lm = landmarks.at(idx);
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }
        valid_indices.push_back(idx);
    }
    return valid_indices;
}

std::unique_ptr<solve::pnp_solver> relocalizer::setup_pnp_solver(const std::vector<unsigned int>& valid_indices,
                                                                 const eigen_alloc_vector<Vec3_t>& bearings,
                                                                 const std::vector<cv::KeyPoint>& keypts,
                                                                 const std::vector<data::landmark*>& matched_landmarks,
                                                                 const std::vector<float>& scale_factors) const
{
    // resample valid elements
    const auto valid_bearings = util::resample_by_indices(bearings, valid_indices);
    const auto valid_keypts = util::resample_by_indices(keypts, valid_indices);
    const auto valid_assoc_lms = util::resample_by_indices(matched_landmarks, valid_indices);
    eigen_alloc_vector<Vec3_t> valid_landmarks(valid_indices.size());
    for (unsigned int i = 0; i < valid_indices.size(); ++i) {
        valid_landmarks.at(i) = valid_assoc_lms.at(i)->get_pos_in_world();
    }
    // setup PnP solver
    return std::unique_ptr<solve::pnp_solver>(
        new solve::pnp_solver(valid_bearings, valid_keypts, valid_landmarks, scale_factors));
}

}  // namespace module
}  // namespace openvslam
