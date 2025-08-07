// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "match/bow_tree.h"
#include "match/angle_checker.h"

#ifdef USE_DBOW2
#include <DBoW2/FeatureVector.h>
#else
#include <fbow/fbow.h>
#endif

#include <spdlog/spdlog.h>

namespace openvslam {
namespace match {

unsigned int bow_tree::match_frame_and_keyframe(data::keyframe* keyfrm, data::frame& frm,
                                                std::vector<data::landmark*>& matched_lms_in_frm) const
{
    unsigned int num_matches = 0;

    angle_checker<int> angle_checker;

    bool can_check_orientation = !keyfrm->keypts_.empty();

    const auto keyfrm_lms = keyfrm->get_landmarks();

#ifdef USE_DBOW2
    DBoW2::FeatureVector::const_iterator keyfrm_itr = keyfrm->bow_feat_vec_.begin();
    DBoW2::FeatureVector::const_iterator frm_itr = frm.bow_feat_vec_.begin();
    const DBoW2::FeatureVector::const_iterator kryfrm_end = keyfrm->bow_feat_vec_.end();
    const DBoW2::FeatureVector::const_iterator frm_end = frm.bow_feat_vec_.end();
#else
    fbow::BoWFeatVector::const_iterator keyfrm_itr = keyfrm->bow_feat_vec_.begin();
    fbow::BoWFeatVector::const_iterator frm_itr = frm.bow_feat_vec_.begin();
    const fbow::BoWFeatVector::const_iterator kryfrm_end = keyfrm->bow_feat_vec_.end();
    const fbow::BoWFeatVector::const_iterator frm_end = frm.bow_feat_vec_.end();
#endif

    while (keyfrm_itr != kryfrm_end && frm_itr != frm_end) {
        // BoW treeのノード番号(first)が一致しているか確認する
        if (keyfrm_itr->first == frm_itr->first) {
            // BoW treeのノード番号(first)が一致していれば，
            // 実際に特徴点index(second)を持ってきて対応しているか確認する
            const auto keyfrm_indices = keyfrm_itr->second;
            const auto frm_indices = frm_itr->second;

            for (const auto keyfrm_idx : keyfrm_indices) {
                // keyfrm_idxの特徴点と3次元点が対応していない場合はスルーする
                if (keyfrm_idx >= keyfrm_lms.size()) {
                    spdlog::warn("{} beyond the boundary of keyfrm_lms vector, size: {}", keyfrm_idx, keyfrm_lms.size());
                    continue;
                }

                auto* lm = keyfrm_lms.at(keyfrm_idx);
                if (!lm) {
                    // spdlog::debug("landmark does not exist!");
                    continue;
                }
                if (lm->will_be_erased()) {
                    // spdlog::debug("landmark will be erased!");
                    continue;
                }

                if (keyfrm->descriptors_.rows < 0 ||
                    keyfrm_idx >= static_cast<unsigned int>(keyfrm->descriptors_.rows)) {
                    spdlog::warn("{} beyond the boundary of keyfrm descriptors_ rows, size: {}", keyfrm_idx,
                                 keyfrm->descriptors_.rows);
                    continue;
                }
                const auto& keyfrm_desc = keyfrm->descriptors_.row(keyfrm_idx);

                unsigned int best_hamm_dist = MAX_HAMMING_DIST;
                int best_frm_idx = -1;
                unsigned int second_best_hamm_dist = MAX_HAMMING_DIST;

                for (const auto frm_idx : frm_indices) {
                    if (frm_idx >= matched_lms_in_frm.size()) {
                        spdlog::warn("{} beyond the boundary of matched_lms_in_frm vector, size: {}", frm_idx,
                                     matched_lms_in_frm.size());
                        continue;
                    }

                    if (matched_lms_in_frm.at(frm_idx)) {
                        continue;
                    }

                    if (frm.descriptors_.rows < 0 || frm_idx >= static_cast<unsigned int>(frm.descriptors_.rows)) {
                        spdlog::warn("{} beyond the boundary of keyfrm descriptors_ rows, size: {}", frm_idx,
                                     frm.descriptors_.rows);
                        continue;
                    }
                    const auto& frm_desc = frm.descriptors_.row(frm_idx);

                    const auto hamm_dist = compute_descriptor_distance_32(keyfrm_desc, frm_desc);

                    if (hamm_dist < best_hamm_dist) {
                        second_best_hamm_dist = best_hamm_dist;
                        best_hamm_dist = hamm_dist;
                        best_frm_idx = frm_idx;
                    } else if (hamm_dist < second_best_hamm_dist) {
                        second_best_hamm_dist = hamm_dist;
                    }
                }

                if (HAMMING_DIST_THR_LOW < best_hamm_dist) {
                    continue;
                }

                // ratio test
                if (lowe_ratio_ * second_best_hamm_dist < static_cast<float>(best_hamm_dist)) {
                    continue;
                }

                if (best_frm_idx < 0 || static_cast<unsigned int>(best_frm_idx) >= matched_lms_in_frm.size()) {
                    spdlog::warn("{} beyond the boundary of matched_lms_in_frm vector, size: {}", best_frm_idx,
                                 matched_lms_in_frm.size());
                    continue;
                }
                matched_lms_in_frm.at(best_frm_idx) = lm;

                if (check_orientation_ && can_check_orientation) {
                    if (keyfrm_idx >= keyfrm->keypts_.size() ||
                        static_cast<unsigned int>(best_frm_idx) >= frm.keypts_.size()) {
                        spdlog::warn("{} beyond the boundary of keyfrm keypts_ vector, size: {} or {} \
                                     beyond the boundary of frm keypts vector, size: {}", keyfrm_idx,
                                     keyfrm->keypts_.size(), best_frm_idx, frm.keypts_.size());
                        continue;
                    }
                    const auto delta_angle = keyfrm->keypts_.at(keyfrm_idx).angle - frm.keypts_.at(best_frm_idx).angle;
                    angle_checker.append_delta_angle(delta_angle, best_frm_idx);
                }

                ++num_matches;
                // spdlog::debug("num_matches is {}", num_matches);
            }

            ++keyfrm_itr;
            ++frm_itr;
        } else if (keyfrm_itr->first < frm_itr->first) {
            // keyfrm_itrのノード番号のほうが小さいので，ノード番号が合うところまでイテレータkeyfrm_itrをすすめる
            keyfrm_itr = keyfrm->bow_feat_vec_.lower_bound(frm_itr->first);
        } else {
            // frm_itrのノード番号のほうが小さいので，ノード番号が合うところまでイテレータfrm_itrをすすめる
            frm_itr = frm.bow_feat_vec_.lower_bound(keyfrm_itr->first);
        }
    }

    spdlog::debug("before checking orientation, num_matches is {}", num_matches);
    if (check_orientation_ && can_check_orientation) {
        const auto invalid_matches = angle_checker.get_invalid_matches();
        for (const auto invalid_idx : invalid_matches) {
            if (invalid_idx < 0 || static_cast<unsigned int>(invalid_idx) >= matched_lms_in_frm.size()) {
                spdlog::warn("{} beyond the boundary of matched_lms_in_frm vector, size: {}", invalid_idx,
                                 matched_lms_in_frm.size());
                continue;
            }
            matched_lms_in_frm.at(invalid_idx) = nullptr;
            --num_matches;
        }
    }
    spdlog::debug("final num_matches is {}", num_matches);

    return num_matches;
}

unsigned int bow_tree::match_keyframes(data::keyframe* keyfrm_1, data::keyframe* keyfrm_2,
                                       std::vector<data::landmark*>& matched_lms_in_keyfrm_1) const
{
    unsigned int num_matches = 0;

    angle_checker<int> angle_checker;

    const auto keyfrm_1_lms = keyfrm_1->get_landmarks();
    const auto keyfrm_2_lms = keyfrm_2->get_landmarks();

    matched_lms_in_keyfrm_1 = std::vector<data::landmark*>(keyfrm_1_lms.size(), nullptr);

    // keyframe2の特徴点のうち，keyfram1の特徴点と対応が取れているものはtrueにする
    // NOTE: sizeはkeyframe2の特徴点に一致
    std::vector<bool> is_already_matched_in_keyfrm_2(keyfrm_2_lms.size(), false);

#ifdef USE_DBOW2
    DBoW2::FeatureVector::const_iterator itr_1 = keyfrm_1->bow_feat_vec_.begin();
    DBoW2::FeatureVector::const_iterator itr_2 = keyfrm_2->bow_feat_vec_.begin();
    const DBoW2::FeatureVector::const_iterator itr_1_end = keyfrm_1->bow_feat_vec_.end();
    const DBoW2::FeatureVector::const_iterator itr_2_end = keyfrm_2->bow_feat_vec_.end();
#else
    fbow::BoWFeatVector::const_iterator itr_1 = keyfrm_1->bow_feat_vec_.begin();
    fbow::BoWFeatVector::const_iterator itr_2 = keyfrm_2->bow_feat_vec_.begin();
    const fbow::BoWFeatVector::const_iterator itr_1_end = keyfrm_1->bow_feat_vec_.end();
    const fbow::BoWFeatVector::const_iterator itr_2_end = keyfrm_2->bow_feat_vec_.end();
#endif

    while (itr_1 != itr_1_end && itr_2 != itr_2_end) {
        // BoW treeのノード番号(first)が一致しているか確認する
        if (itr_1->first == itr_2->first) {
            // BoW treeのノード番号(first)が一致していれば，
            // 実際に特徴点index(second)を持ってきて対応しているか確認する
            const auto& keyfrm_1_indices = itr_1->second;
            const auto& keyfrm_2_indices = itr_2->second;

            for (const auto idx_1 : keyfrm_1_indices) {
                // keyfrm_1の特徴点と3次元点が対応していない場合はスルーする
                auto* lm_1 = keyfrm_1_lms.at(idx_1);
                if (!lm_1) {
                    continue;
                }
                if (lm_1->will_be_erased()) {
                    continue;
                }

                const auto& desc_1 = keyfrm_1->descriptors_.row(idx_1);

                unsigned int best_hamm_dist = MAX_HAMMING_DIST;
                int best_idx_2 = -1;
                unsigned int second_best_hamm_dist = MAX_HAMMING_DIST;

                for (const auto idx_2 : keyfrm_2_indices) {
                    // keyfrm_2の特徴点と3次元点が対応していない場合はスルーする
                    auto* lm_2 = keyfrm_2_lms.at(idx_2);
                    if (!lm_2) {
                        continue;
                    }
                    if (lm_2->will_be_erased()) {
                        continue;
                    }

                    if (is_already_matched_in_keyfrm_2.at(idx_2)) {
                        continue;
                    }

                    const auto& desc_2 = keyfrm_2->descriptors_.row(idx_2);

                    const auto hamm_dist = compute_descriptor_distance_32(desc_1, desc_2);

                    if (hamm_dist < best_hamm_dist) {
                        second_best_hamm_dist = best_hamm_dist;
                        best_hamm_dist = hamm_dist;
                        best_idx_2 = idx_2;
                    } else if (hamm_dist < second_best_hamm_dist) {
                        second_best_hamm_dist = hamm_dist;
                    }
                }

                if (HAMMING_DIST_THR_LOW < best_hamm_dist) {
                    continue;
                }

                // ratio test
                if (lowe_ratio_ * second_best_hamm_dist < static_cast<float>(best_hamm_dist)) {
                    continue;
                }

                // 対応情報を記録する
                // keyframe1のidx_1とkeyframe2のbest_idx_2が対応している
                matched_lms_in_keyfrm_1.at(idx_1) = keyfrm_2_lms.at(best_idx_2);
                // keyframe2のbest_idx_2はすでにkeyframe1の特徴点と対応している
                is_already_matched_in_keyfrm_2.at(best_idx_2) = true;

                num_matches++;

                if (check_orientation_) {
                    const auto delta_angle = keyfrm_1->keypts_.at(idx_1).angle - keyfrm_2->keypts_.at(best_idx_2).angle;
                    angle_checker.append_delta_angle(delta_angle, idx_1);
                }
            }

            ++itr_1;
            ++itr_2;
        } else if (itr_1->first < itr_2->first) {
            itr_1 = keyfrm_1->bow_feat_vec_.lower_bound(itr_2->first);
        } else {
            itr_2 = keyfrm_2->bow_feat_vec_.lower_bound(itr_1->first);
        }
    }

    if (check_orientation_) {
        const auto invalid_matches = angle_checker.get_invalid_matches();
        for (const auto invalid_idx : invalid_matches) {
            matched_lms_in_keyfrm_1.at(invalid_idx) = nullptr;
            --num_matches;
        }
    }

    return num_matches;
}

}  // namespace match
}  // namespace openvslam
