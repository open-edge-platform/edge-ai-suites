// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "module/keyframe_inserter.h"
#include <spdlog/spdlog.h>
#include "data/bow_database.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "mapping_module.h"

namespace openvslam {
namespace module {

keyframe_inserter::keyframe_inserter(const camera::setup_type_t setup_type, const float true_depth_thr,
                                     data::map_database* map_db, data::bow_database* bow_db,
                                     const unsigned int min_num_frms, const unsigned int max_num_frms)
    : setup_type_(setup_type),
      true_depth_thr_(true_depth_thr),
      map_db_(map_db),
      bow_db_(bow_db),
      min_num_frms_(min_num_frms),
      max_num_frms_(max_num_frms)
{
}

void keyframe_inserter::set_mapping_module(mapping_module* mapper) { mapper_ = mapper; }

void keyframe_inserter::reset()
{
    // For each client, it's not proper to reset this
    /*frm_id_of_last_keyfrm_ = 0;*/
}

bool keyframe_inserter::new_keyframe_is_needed(const data::frame& curr_frm, const unsigned int num_tracked_lms,
                                               const data::keyframe& ref_keyfrm) const
{
    assert(mapper_);
    // mapping moduleが停止しているときはキーフレームが追加できない
    if (mapper_->is_paused() || mapper_->pause_is_requested()) {
        return false;
    }

    const auto num_keyfrms = map_db_->get_num_keyframes();

    // reference keyframeで観測している3次元点のうち，3視点以上から観測されている3次元点の数を数える
    const unsigned int min_obs_thr = (3 <= num_keyfrms) ? 3 : 2;

    const auto num_reliable_lms = ref_keyfrm.get_num_tracked_landmarks(
        min_obs_thr);  // Here landmarks from server won't be counted, for it only has no observation at now

    // mappingが処理中かどうか
    const bool mapper_is_idle = mapper_->get_keyframe_acceptability();

    if (mapper_is_idle) {
        // mapping moduleが処理中でなければ，とりあえずkeyframeを追加しておく
        spdlog::debug("mapper_is_idle is satisfied!");
    } else {
        spdlog::debug("mapper_is_idle is  not satisfied!");
    }

    // TODO make these numbers configurable
    // 最新のキーフレームで観測している3次元点数に対する，現在のフレームで観測している3次元点数の割合の閾値
    constexpr unsigned int num_tracked_lms_thr = 15;
    const float lms_ratio_thr = 0.9;

    // 条件A1: 前回のキーフレーム挿入からmax_num_frames_以上経過していたらキーフレームを追加する
    const bool cond_a1 = frm_id_of_last_keyfrm_ + max_num_frms_ <= curr_frm.id_;
    // 条件A2: min_num_frames_以上経過していて,mapping moduleが待機状態であればキーフレームを追加する
    const bool cond_a2 = (frm_id_of_last_keyfrm_ + min_num_frms_ <= curr_frm.id_) && mapper_is_idle;
    // 条件A3: 前回のキーフレームから視点が移動してたらキーフレームを追加する
    const bool cond_a3 = num_tracked_lms < num_reliable_lms * 0.25;

    // 条件B:
    // (キーフレーム追加の必要条件)3次元点が閾値以上観測されていて，3次元点との割合が一定割合以下であればキーフレームを追加する
    bool cond_b = (num_tracked_lms_thr <= num_tracked_lms);

    cond_b = cond_b && (num_tracked_lms < num_reliable_lms * lms_ratio_thr);

    // Temporal condition for Inertial cases
    bool cond_c = false;
    constexpr unsigned int num_tracked_lms_thr_low = 15;
    constexpr unsigned int num_tracked_lms_thr_high = 75;
    if (((num_tracked_lms < num_tracked_lms_thr_high) && (num_tracked_lms > num_tracked_lms_thr_low)) &&
        ref_keyfrm.camera_->use_imu_)
        cond_c = true;

    if (cond_c) {
        if (mapper_is_idle) {
            return true;
        } else {
            mapper_->abort_local_BA();
            if (ref_keyfrm.camera_->setup_type_ != camera::setup_type_t::Monocular_Inertial) {
                if (mapper_->get_num_queued_keyframes() <= 2)
                    return true;
                else
                    return false;
            } else
                return false;
        }
    }

    // Bが満たされていなければ追加しない
    if (!cond_b) {
        spdlog::debug("Condition b is not satisfied! num_tracked_lms: {}, num_reliable_lms:{} ", num_tracked_lms,
                      num_reliable_lms);
        return false;
    }

    // Aのいずれも満たされていなければ追加しない
    if (!cond_a1 && !cond_a2 && !cond_a3) {
        spdlog::debug("Condition a1 a2 and a3 are not satisfied!");
        return false;
    }

    if (mapper_is_idle) {
        // mapping moduleが処理中でなければ，とりあえずkeyframeを追加しておく
        return true;
    }
    // mapping moduleが処理中だったら，local BAを止めてキーフレームを追加する
    if (setup_type_ != camera::setup_type_t::Monocular && mapper_->get_num_queued_keyframes() <= 2) {
        mapper_->abort_local_BA();
        return true;
    } else {
        spdlog::debug("mapper_->get_num_queued_keyframes: {}", mapper_->get_num_queued_keyframes());
    }

    return false;
}

data::keyframe* keyframe_inserter::insert_new_keyframe(data::frame& curr_frm, bool send_to_server)
{
    // mapping moduleを(強制的に)動かす
    if (!mapper_->set_force_to_run(true)) {
        spdlog::debug("Can't create keyframe from this frame");
        return nullptr;
    }

    curr_frm.update_pose_params();
    auto keyfrm = new data::keyframe(curr_frm, map_db_, bow_db_);

    // Add server landmark and this keyframe connection
    for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
#ifdef ENABLE_SEMANTIC_SLAM
        if (curr_frm.segment_outlier_flags_[idx]) continue;
#endif
        auto lm = curr_frm.landmarks_.at(idx);
        if (!lm) continue;
        if (lm->come_from_server()) {
            auto p_landmark = map_db_->get_landmark(lm->id_);
            if (p_landmark) {
                p_landmark->set_pos_in_world(lm->get_pos_in_world());
                p_landmark->add_observation(keyfrm, idx);
                keyfrm->add_landmark(p_landmark, idx);
                p_landmark->compute_descriptor();
                p_landmark->update_normal_and_depth();
                curr_frm.landmarks_.at(idx) = p_landmark;

                // This server landmark will be add to local map, so it need to be erased from server landmark container
                if (send_to_server) map_db_->add_erased_server_landmark(lm->id_);
            } else {
                p_landmark = new data::landmark(lm->get_pos_in_world(), keyfrm, map_db_, lm->id_, true);
                p_landmark->add_observation(keyfrm, idx);
                keyfrm->add_landmark(p_landmark, idx);
                curr_frm.landmarks_.at(idx) = p_landmark;
                p_landmark->compute_descriptor();
                p_landmark->update_normal_and_depth();
                // This landmark comes from server, so it is not newly created by this client
                p_landmark->set_not_new_created();
                map_db_->add_landmark(p_landmark);
                if (send_to_server) map_db_->add_erased_server_landmark(lm->id_);
            }
        }
    }

    frm_id_of_last_keyfrm_ = curr_frm.id_;

    // Add odom into keyframe from data in frame
    if (mapper_->use_odom_) {
        keyfrm->odom_ = curr_frm.odom_;
    }

    // do pre_integration calculation ahead of queue_keyframe
    if (setup_type_ == camera::setup_type_t::Monocular_Inertial) {
        return keyfrm;
    }

    // monocularだったらkeyframeをmapping moduleにqueueして終わり
    if (setup_type_ == camera::setup_type_t::Monocular) {
        if (send_to_server)
            queue_keyframe(keyfrm);
        else
            store_keyframe(keyfrm);
        return keyfrm;
    }

    // 有効なdepthとそのindexを格納する
    std::vector<std::pair<float, unsigned int>> depth_idx_pairs;
    depth_idx_pairs.reserve(curr_frm.num_keypts_);
    for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
        const auto depth = curr_frm.depths_.at(idx);
        // depthが有効な範囲のものを追加する
        if (0 < depth) {
            depth_idx_pairs.emplace_back(std::make_pair(depth, idx));
        }
    }

    // do pre_integration calculation ahead of queue_keyframe
    if (depth_idx_pairs.empty() &&
        (setup_type_ == camera::setup_type_t::Stereo_Inertial || setup_type_ == camera::setup_type_t::RGBD_Inertial)) {
        return keyfrm;
    }

    // 有効なdepthがなかったらqueueして終わり
    if (depth_idx_pairs.empty()) {
        if (send_to_server)
            queue_keyframe(keyfrm);
        else
            store_keyframe(keyfrm);
        return keyfrm;
    }

    // keyframeをqueueして終わり
    if (send_to_server) {
        // カメラに近い順に並べ直す
        std::sort(depth_idx_pairs.begin(), depth_idx_pairs.end());

        // depthを使って3次元点を最小min_num_to_create点作る
        constexpr unsigned int min_num_to_create = 100;
        for (unsigned int count = 0; count < depth_idx_pairs.size(); ++count) {
            const auto depth = depth_idx_pairs.at(count).first;
            const auto idx = depth_idx_pairs.at(count).second;

            // 最小閾値以上の点が追加されて，かつdepthの範囲が敷居を超えたら追加をやめる
            if (min_num_to_create < count && true_depth_thr_ < depth) {
                break;
            }

            // idxに対応する3次元点がある場合はstereo triangulationしない
            {
                auto lm = curr_frm.landmarks_.at(idx);
                if (lm) {
                    assert(lm->has_observation());
                    continue;
                }
            }

            // idxに対応する3次元がなければstereo triangulationで作る
            const Vec3_t pos_w = curr_frm.triangulate_stereo(idx);
            auto lm = new data::landmark(pos_w, keyfrm, map_db_);

            lm->add_observation(keyfrm, idx);
            keyfrm->add_landmark(lm, idx);
            curr_frm.landmarks_.at(idx) = lm;

            lm->compute_descriptor();
            lm->update_normal_and_depth();

            map_db_->add_landmark(lm);
        }
        // do pre_integration calculation ahead of queue_keyframe
        if (setup_type_ == camera::setup_type_t::Stereo_Inertial || setup_type_ == camera::setup_type_t::RGBD_Inertial)
            return keyfrm;
        queue_keyframe(keyfrm);
    } else
        store_keyframe(keyfrm);
    return keyfrm;
}  // namespace module

void keyframe_inserter::queue_keyframe(data::keyframe* keyfrm)
{
    mapper_->queue_keyframe(keyfrm);
    mapper_->set_force_to_run(false);
}

void keyframe_inserter::store_keyframe(data::keyframe* keyfrm)
{
    // compute BoW feature vector
    keyfrm->compute_bow();

    // update graph
    const auto cur_lms = keyfrm->get_landmarks();
    for (unsigned int idx = 0; idx < cur_lms.size(); ++idx) {
        auto lm = cur_lms.at(idx);
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        // if `lm` does not have the observation information from `keyfrm`,
        // add the association between the keyframe and the landmark
        if (lm->is_observed_in_keyframe(keyfrm)) {
            continue;
        }

        // update connection
        lm->add_observation(keyfrm, idx);
        // update geometry
        lm->update_normal_and_depth();
        lm->compute_descriptor();
    }
    keyfrm->graph_node_->update_connections();

    // store the new keyframe to the map database
    map_db_->add_keyframe(keyfrm);
}

}  // namespace module
}  // namespace openvslam
