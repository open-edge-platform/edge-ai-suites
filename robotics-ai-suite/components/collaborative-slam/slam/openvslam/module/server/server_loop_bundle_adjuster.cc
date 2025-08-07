// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "optimize/global_bundle_adjuster.h"
#include "server_loop_bundle_adjuster.h"

#include <thread>

#include <spdlog/spdlog.h>

namespace openvslam {
namespace module {

server_loop_bundle_adjuster::server_loop_bundle_adjuster(data::map_database* map_db, const unsigned int num_iter):
    loop_bundle_adjuster(map_db, num_iter)
{
}

void server_loop_bundle_adjuster::optimize(const KeyframeID identifier, MapID map_id1, MapID map_id2)
{
    spdlog::info("start loop bundle adjustment");

    // Fix the origin of the map which own this loop keyframe
    auto origin_keyframe1 = map_db_->get_origin_keyframe(map_id1);
    auto origin_keyframe2 = map_db_->get_origin_keyframe(map_id2);
    if (!origin_keyframe1 || !origin_keyframe2) {
        spdlog::error("map {} or {} doesn't exist in the origin_keyfrms_ unordered_map of map_db_!");
        return;
    }

    auto fixed_frame_id =
        map_id1 < map_id2 ? origin_keyframe1->id_ : origin_keyframe2->id_;

    if (map_id1 != map_id2) {
        auto cur_keyframe = map_db_->get_keyframe(identifier);
        if (!cur_keyframe) {
            spdlog::error("failed to get the current keyframe from map database based on the identifier {}!", identifier);
            return;
        }

        if (origin_keyframe1->client_id_ != cur_keyframe->client_id_)  // cur_keyframe is not the loop keyframe
            fixed_frame_id = origin_keyframe1->id_;
        else
            fixed_frame_id = origin_keyframe2->id_;
    }

    unsigned int num_exec_loop_BA = 0;
    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        loop_BA_is_running_ = true;
        abort_loop_BA_ = false;
        num_exec_loop_BA = num_exec_loop_BA_;
    }

    // pass the origin keyframe id of the map which owns the loop keyframe to global ba constructor
    const auto global_bundle_adjuster = optimize::global_bundle_adjuster(fixed_frame_id, map_db_, num_iter_, false);

    global_bundle_adjuster.optimize(identifier, &abort_loop_BA_, map_id1, map_id2, fixed_frame_id);

    {
        std::lock_guard<std::mutex> lock1(mtx_thread_);

        // if count_loop_BA_execution() was called during the loop BA or the loop BA was aborted,
        // cannot update the map
        if (num_exec_loop_BA != num_exec_loop_BA_ || abort_loop_BA_) {
            spdlog::info(
                "abort loop bundle adjustment. num_exec_loop_BA: {}, num_exec_loop_BA_: {}, abort_loop_BA_: {}",
                num_exec_loop_BA, num_exec_loop_BA_, abort_loop_BA_);
            loop_BA_is_running_ = false;
            abort_loop_BA_ = false;
            return;
        }

        spdlog::info("finish loop bundle adjustment");
        spdlog::info("updating the map with pose propagation");

        std::lock_guard<std::mutex> lock2(data::map_database::mtx_database_);

        // update the camera pose along the spanning tree from the origin
        spdlog::info("update the camera pose along the spanning tree from the origin");
        std::list<data::keyframe*> keyfrms_to_check;
        auto origin_keyframes_map = map_db_->get_all_origin_keyframes();
        for (const auto& origin_keyfrm : origin_keyframes_map) {
            if (origin_keyfrm.second->get_map_id() == map_id1 || origin_keyfrm.second->get_map_id() == map_id2)
                keyfrms_to_check.push_back(origin_keyfrm.second);
        }
        while (!keyfrms_to_check.empty()) {
            auto parent = keyfrms_to_check.front();
            if (!parent) {
                keyfrms_to_check.pop_front();
                continue;
            }
            const Mat44_t cam_pose_wp = parent->get_cam_pose_inv();

            const auto children = parent->graph_node_->get_spanning_children();
            for (auto& child : children) {
                if (child->loop_BA_identifier_ != identifier) {
                    // if `child` is NOT optimized by the loop BA
                    // propagate the pose correction from the spanning parent

                    // parent->child
                    const Mat44_t cam_pose_cp = child->get_cam_pose() * cam_pose_wp;
                    // world->child AFTER correction = parent->child * world->parent AFTER correction
                    child->cam_pose_cw_after_loop_BA_ = cam_pose_cp * parent->cam_pose_cw_after_loop_BA_;
                    // check as `child` has been corrected
                    child->loop_BA_identifier_ = identifier;
                }

                // need updating
                keyfrms_to_check.push_back(child);
            }

            // temporally store the camera pose BEFORE correction (for correction of landmark positions)
            parent->cam_pose_cw_before_BA_ = parent->get_cam_pose();
            // update the camera pose
            parent->set_cam_pose(parent->cam_pose_cw_after_loop_BA_);
            // finish updating
            keyfrms_to_check.pop_front();
        }

        spdlog::info("updated the landmarks");
        // update the positions of the landmarks
        const auto landmarks = map_db_->get_all_landmarks(map_id1, map_id2);
        for (auto lm : landmarks) {
            if (!lm) {
                // std::cout << "No such landmark!" << std::endl;
                continue;
            }

            if (lm->will_be_erased()) {
                continue;
            }

            if (lm->loop_BA_identifier_ == identifier) {
                // if `lm` is optimized by the loop BA

                // update with the optimized position
                lm->set_pos_in_world(lm->pos_w_after_global_BA_);
            } else {
                // if `lm` is NOT optimized by the loop BA

                // correct the position according to the move of the camera pose of the reference keyframe
                auto ref_keyfrm = lm->get_ref_keyframe();

                assert((std::string("maps :") + std::to_string(map_id1) + ", " + std::to_string(map_id2),
                        ref_keyfrm->loop_BA_identifier_ == identifier));

                // convert the position to the camera-reference using the camera pose BEFORE the correction
                const Mat33_t rot_cw_before_BA = ref_keyfrm->cam_pose_cw_before_BA_.block<3, 3>(0, 0);
                const Vec3_t trans_cw_before_BA = ref_keyfrm->cam_pose_cw_before_BA_.block<3, 1>(0, 3);
                const Vec3_t pos_c = rot_cw_before_BA * lm->get_pos_in_world() + trans_cw_before_BA;

                // convert the position to the world-reference using the camera pose AFTER the correction
                const Mat44_t cam_pose_wc = ref_keyfrm->get_cam_pose_inv();
                const Mat33_t rot_wc = cam_pose_wc.block<3, 3>(0, 0);
                const Vec3_t trans_wc = cam_pose_wc.block<3, 1>(0, 3);
                lm->set_pos_in_world(rot_wc * pos_c + trans_wc);
            }
            lm->update_normal_and_depth();
        }

        loop_BA_is_running_ = false;

        spdlog::info("updated the map");
    }
}

}  // namespace module
}  // namespace openvslam
