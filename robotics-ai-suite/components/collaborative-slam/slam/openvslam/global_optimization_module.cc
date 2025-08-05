// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "global_optimization_module.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "match/fuse.h"
#include "util/converter.h"
#include "optimize/g2o/landmark_vertex_container.h"
#include "optimize/g2o/se3/reproj_edge_wrapper.h"
#include "optimize/g2o/se3/shot_vertex_container.h"

#include <unordered_map>

#include <g2o/core/block_solver.h>
#include <g2o/core/optimization_algorithm_levenberg.h>
#include <g2o/core/robust_kernel_impl.h>
#include <g2o/core/solver.h>
#include <g2o/core/sparse_optimizer.h>
#include <g2o/solvers/csparse/linear_solver_csparse.h>
#include <g2o/solvers/dense/linear_solver_dense.h>
#include <g2o/solvers/eigen/linear_solver_eigen.h>
#include <g2o/types/sba/types_six_dof_expmap.h>

#include <spdlog/spdlog.h>

namespace openvslam {

global_optimization_module::global_optimization_module(data::map_database* map_db, data::bow_database* bow_db,
                                                       data::bow_vocabulary* bow_vocab, const bool fix_scale,
                                                       double front_rear_camera_constraint_thr, int iteration_times,
                                                       bool segment_optimize)
    : map_db_(map_db),
      fix_scale_(fix_scale),
      front_rear_camera_constraint_thr_(front_rear_camera_constraint_thr),
      iteration_times_(iteration_times),
      segment_optimize_(segment_optimize)
{
    loop_detector_ = std::make_unique<module::server_loop_detector>(bow_db, bow_vocab, fix_scale);
    loop_bundle_adjuster_ = std::make_unique<module::server_loop_bundle_adjuster>(map_db);

    spdlog::debug("CONSTRUCT: global_optimization_module_tyx");
    spdlog::debug("iteration_times: {}", iteration_times_);
    spdlog::debug("segment: {}", segment_optimize_);
    spdlog::debug("fix_scale: {}", fix_scale);
}

global_optimization_module::~global_optimization_module()
{
    abort_loop_BA();
    if (thread_for_loop_BA_) {
        thread_for_loop_BA_->join();
    }
    spdlog::debug("DESTRUCT: global_optimization_module");
}

void global_optimization_module::enable_loop_detector()
{
    spdlog::info("enable loop detector");
    loop_detector_->enable_loop_detector();
}

void global_optimization_module::disable_loop_detector()
{
    spdlog::info("disable loop detector");
    loop_detector_->disable_loop_detector();
}

bool global_optimization_module::loop_detector_is_enabled() const { return loop_detector_->is_enabled(); }

void global_optimization_module::run()
{
    spdlog::info("start global optimization module");

    is_terminated_ = false;

    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));

        // check if termination is requested
        if (terminate_is_requested()) {
            // terminate and break
            terminate();
            break;
        }

        // check if pause is requested
        if (pause_is_requested()) {
            // pause and wait
            pause();
            // check if termination or reset is requested during pause
            while (is_paused() && !terminate_is_requested() && !reset_is_requested()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(3));
            }
        }

        // check if reset is requested
        if (reset_is_requested()) {
            // reset and continue
            reset();
            continue;
        }

        // if the queue is empty, the following process is not needed
        if (!keyframe_is_queued()) {
            continue;
        }

        // dequeue the keyframe from the queue -> cur_keyfrm_
        {
            std::lock_guard<std::mutex> lock(mtx_keyfrm_queue_);
            cur_keyfrm_ = keyfrms_queue_.front();
            keyfrms_queue_.pop_front();
        }

        // not to be removed during loop detection and correction
        cur_keyfrm_->set_not_to_be_erased();

        // pass the current keyframe to the loop detector
        loop_detector_->set_current_keyframe(cur_keyfrm_);

        // detect some loop candidate with BoW
        // TODO: recovery monucular scale from existed rgbd map

        if (!loop_detector_->detect_loop_candidates()) {
            // allow the removal of the current keyframe
            cur_keyfrm_->set_to_be_erased();

            continue;
        }

        // validate candidates and select ONE candidate from them
        if (!loop_detector_->validate_candidates(g2o_sim3_cand_to_curr_)) {
            cur_keyfrm_->set_to_be_erased();
            continue;
        } else {
            if (loop_detector_->get_selected_candidate_keyframe()->get_map_id() > cur_keyfrm_->get_map_id()) continue;
            spdlog::debug("~~~~~~~~~~~~~~~~~~~~~~~~~~~Loop validate!~~~~~~~~~~~~~~~~~~~~~~~~~");
        }
    }

    spdlog::info("terminate global optimization module");
}

bool global_optimization_module::is_running_optimization() { return running_optimization_; }

std::vector<data::keyframe*> global_optimization_module::get_keyframe_local_map(data::keyframe* keyframe,
                                                                                size_t numTemporalKFs)
{
    std::set<data::keyframe*> set_LocalWindowKFs;
    // Get the current KF and its neighbors(visual->covisibles)
    set_LocalWindowKFs.insert(keyframe);
    std::vector<data::keyframe*> CovisibleKFs = keyframe->graph_node_->get_top_n_covisibilities(numTemporalKFs);
    set_LocalWindowKFs.insert(CovisibleKFs.begin(), CovisibleKFs.end());

    if (numTemporalKFs > 0) {
        // if covisibilitiy is not enough, get more covisibility keyframes from covisibities
        const int nMaxTries = 3;
        int nNumTries = 0;
        while (set_LocalWindowKFs.size() < numTemporalKFs && nNumTries < nMaxTries) {
            std::vector<data::keyframe*> NewCovKFs;
            for (const auto& pKFi : set_LocalWindowKFs) {
                std::vector<data::keyframe*> KFiCov = pKFi->graph_node_->get_top_n_covisibilities(numTemporalKFs / 2);
                for (const auto& pKFcov : KFiCov) {
                    if (pKFcov && !pKFcov->will_be_erased() &&
                        set_LocalWindowKFs.find(pKFcov) == set_LocalWindowKFs.end()) {
                        NewCovKFs.push_back(pKFcov);
                    }
                }
            }

            set_LocalWindowKFs.insert(NewCovKFs.begin(), NewCovKFs.end());
            nNumTries++;
        }
    }
    std::vector<data::keyframe*> vec_LocalWindowKFs;
    std::copy(set_LocalWindowKFs.begin(), set_LocalWindowKFs.end(), std::back_inserter(vec_LocalWindowKFs));
    return vec_LocalWindowKFs;
}

void global_optimization_module::transform_map_via_sim3(module::keyframe_Sim3_pairs_t& Sim3s_nw_before_correction,
                                                        module::keyframe_Sim3_pairs_t& Sim3s_nw_after_correction,
                                                        const g2o::Sim3 g2o_Sim3_cw_after_correction,
                                                        const data::keyframe* keyframe_to_be_transformed) const
{
    std::vector<data::keyframe*> curr_map_all_keyframes =
        map_db_->get_all_keyframes(keyframe_to_be_transformed->get_map_id(), keyframe_to_be_transformed->get_map_id());

    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
    std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[keyframe_to_be_transformed->get_map_id()]);

    // camera pose of the current keyframe BEFORE loop correction
    const Mat44_t cam_pose_wc_before_correction = keyframe_to_be_transformed->get_cam_pose_inv();

    // compute Sim3s BEFORE loop correction
    Sim3s_nw_before_correction = get_Sim3s_before_loop_correction(curr_map_all_keyframes);
    // compute Sim3s AFTER loop correction
    Sim3s_nw_after_correction = get_Sim3s_after_loop_correction(cam_pose_wc_before_correction,
                                                                g2o_Sim3_cw_after_correction, curr_map_all_keyframes);

    // correct covibisibility landmark positions
    correct_covisibility_landmarks(Sim3s_nw_before_correction, Sim3s_nw_after_correction);
    // correct covisibility keyframe camera poses
    correct_covisibility_keyframes(Sim3s_nw_after_correction);
}

// hard to give a proper function name!
void global_optimization_module::transform_map_via_sim3(data::keyframe* keyframe_to_be_transformed, g2o::Sim3 T_sim3,
                                                        module::keyframe_Sim3_pairs_t& Sim3s_nw_before_correction,
                                                        // Sim3 camera poses AFTER loop correction
                                                        module::keyframe_Sim3_pairs_t& Sim3s_nw_after_correction)
{
    std::vector<data::keyframe*> curr_map_all_keyframes =
        map_db_->get_all_keyframes(keyframe_to_be_transformed->get_map_id(), keyframe_to_be_transformed->get_map_id());

    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);

    std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[keyframe_to_be_transformed->get_map_id()]);

    // compute Sim3s BEFORE loop correction
    Sim3s_nw_before_correction = get_Sim3s_before_loop_correction(curr_map_all_keyframes);

    Sim3s_nw_after_correction = get_Sim3s_after_correction_via_sim3_transform(T_sim3, curr_map_all_keyframes);

    // Here we just use the function, actually there is no covisibility landmarks
    // correct landmark positions
    correct_covisibility_landmarks(Sim3s_nw_before_correction, Sim3s_nw_after_correction);
    // correct keyframe camera poses
    correct_covisibility_keyframes(Sim3s_nw_after_correction);
}

void global_optimization_module::queue_keyframe(data::keyframe* keyfrm)
{
    std::lock_guard<std::mutex> lock(mtx_keyfrm_queue_);
    if (keyfrm->id_ != 0) {
        keyfrms_queue_.push_back(keyfrm);
    }
}

bool global_optimization_module::keyframe_is_queued() const
{
    std::lock_guard<std::mutex> lock(mtx_keyfrm_queue_);
    return (!keyfrms_queue_.empty());
}

void global_optimization_module::correct_loop()
{
    spdlog::debug("start correcting loop!");    
}

module::keyframe_Sim3_pairs_t global_optimization_module::get_Sim3s_before_loop_correction(
    const std::vector<data::keyframe*>& neighbors) const
{
    module::keyframe_Sim3_pairs_t Sim3s_nw_before_loop_correction;

    for (const auto neighbor : neighbors) {
        // camera pose of `neighbor` BEFORE loop correction
        const Mat44_t cam_pose_nw = neighbor->get_cam_pose();
        // create Sim3 from SE3
        const Mat33_t& rot_nw = cam_pose_nw.block<3, 3>(0, 0);
        const Vec3_t& trans_nw = cam_pose_nw.block<3, 1>(0, 3);
        const g2o::Sim3 Sim3_nw_before_correction(rot_nw, trans_nw, 1.0);
        Sim3s_nw_before_loop_correction[neighbor] = Sim3_nw_before_correction;
    }

    return Sim3s_nw_before_loop_correction;
}

module::keyframe_Sim3_pairs_t global_optimization_module::get_Sim3s_after_correction_via_sim3_transform(
    const g2o::Sim3& Transform_sim3, const std::vector<data::keyframe*>& neighbors) const
{
    module::keyframe_Sim3_pairs_t Sim3s_nw_after_loop_correction;

    for (auto neighbor : neighbors) {
        // camera pose of `neighbor` BEFORE loop correction
        const Mat44_t cam_pose_nw_before_correction = neighbor->get_cam_pose();
        const Mat33_t& rot_nc = cam_pose_nw_before_correction.block<3, 3>(0, 0);
        const Vec3_t& trans_nc = cam_pose_nw_before_correction.block<3, 1>(0, 3);
        // create the relative Sim3 from the current to `neighbor`
        const g2o::Sim3 cam_pose_sim3_before_correction(rot_nc, trans_nc, 1.0);
        // compute the camera poses AFTER loop correction of the neighbors
        const g2o::Sim3 Sim3_nw_after_correction = cam_pose_sim3_before_correction * Transform_sim3;
        Sim3s_nw_after_loop_correction[neighbor] = Sim3_nw_after_correction;
    }

    return Sim3s_nw_after_loop_correction;
}

module::keyframe_Sim3_pairs_t global_optimization_module::get_Sim3s_after_loop_correction(
    const Mat44_t& cam_pose_wc_before_correction, const g2o::Sim3& g2o_Sim3_cw_after_correction,
    const std::vector<data::keyframe*>& neighbors) const
{
    module::keyframe_Sim3_pairs_t Sim3s_nw_after_loop_correction;

    for (auto neighbor : neighbors) {
        // camera pose of `neighbor` BEFORE loop correction
        const Mat44_t cam_pose_nw_before_correction = neighbor->get_cam_pose();
        // create the relative Sim3 from the current to `neighbor`
        const Mat44_t cam_pose_nc = cam_pose_nw_before_correction * cam_pose_wc_before_correction;
        const Mat33_t& rot_nc = cam_pose_nc.block<3, 3>(0, 0);
        const Vec3_t& trans_nc = cam_pose_nc.block<3, 1>(0, 3);
        const g2o::Sim3 Sim3_nc(rot_nc, trans_nc, 1.0);
        // compute the camera poses AFTER loop correction of the neighbors
        const g2o::Sim3 Sim3_nw_after_correction = Sim3_nc * g2o_Sim3_cw_after_correction;
        Sim3s_nw_after_loop_correction[neighbor] = Sim3_nw_after_correction;
    }

    return Sim3s_nw_after_loop_correction;
}

void global_optimization_module::correct_covisibility_landmarks(
    const module::keyframe_Sim3_pairs_t& Sim3s_nw_before_correction,
    const module::keyframe_Sim3_pairs_t& Sim3s_nw_after_correction) const
{
    for (const auto& t : Sim3s_nw_after_correction) {
        auto neighbor = t.first;
        // neighbor->world AFTER loop correction
        const auto Sim3_wn_after_correction = t.second.inverse();
        // world->neighbor BEFORE loop correction
        const auto& Sim3_nw_before_correction = Sim3s_nw_before_correction.at(neighbor);

        const auto ngh_landmarks = neighbor->get_landmarks();
        for (auto lm : ngh_landmarks) {
            if (!lm) {
                continue;
            }
            if (lm->will_be_erased()) {
                continue;
            }

            // avoid duplication
            if (lm->loop_fusion_identifier_ == cur_keyfrm_->id_) {
                continue;
            }
            lm->loop_fusion_identifier_ = cur_keyfrm_->id_;

            // correct position of `lm`
            const Vec3_t pos_w_before_correction = lm->get_pos_in_world();
            const Vec3_t pos_w_after_correction =
                Sim3_wn_after_correction.map(Sim3_nw_before_correction.map(pos_w_before_correction));
            lm->pos_w_after_global_BA_ = pos_w_after_correction;
            lm->set_pos_in_world(pos_w_after_correction);
            // update geometry
            lm->update_normal_and_depth();

            // record the reference keyframe used in loop fusion of landmarks
            lm->ref_keyfrm_id_in_loop_fusion_ = neighbor->id_;
        }
    }
}

void global_optimization_module::correct_covisibility_keyframes(
    const module::keyframe_Sim3_pairs_t& Sim3s_nw_after_correction, bool correct_pose) const
{
    for (const auto& t : Sim3s_nw_after_correction) {
        auto neighbor = t.first;
        const auto Sim3_nw_after_correction = t.second;

        const auto s_nw = Sim3_nw_after_correction.scale();
        const Mat33_t rot_nw = Sim3_nw_after_correction.rotation().toRotationMatrix();
        const Vec3_t trans_nw = Sim3_nw_after_correction.translation() / s_nw;
        const Mat44_t cam_pose_nw = util::converter::to_eigen_cam_pose(rot_nw, trans_nw);

        // Here the pose will be changed, so we need to record its pose which will be used to allign
        // old keyframe msg pose
        neighbor->cam_pose_cw_before_BA_ = neighbor->get_cam_pose();
        neighbor->in_cur_covisibility_window_ = true;
        if (correct_pose)
            neighbor->set_cam_pose(cam_pose_nw);
        else
            neighbor->cam_pose_cw_after_loop_BA_ = cam_pose_nw;

        // update graph
        neighbor->graph_node_->update_connections();
        neighbor->loop_BA_identifier_ = cur_keyfrm_->id_;
    }
}

void global_optimization_module::replace_duplicated_landmarks(
    const std::vector<data::landmark*>& curr_match_lms_observed_in_cand,
    const module::keyframe_Sim3_pairs_t& Sim3s_nw_after_correction, bool replace_cand_landmarks) const
{
    // resolve duplications of landmarks between the current keyframe and the loop candidate
    int replaced_landmarks_num = 0;
    {
        std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
        std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[cur_keyfrm_->get_map_id()]);

        unsigned int landmark_size = cur_keyfrm_->get_num_landmarks();
        for (unsigned int idx = 0; idx < landmark_size; ++idx) {
            auto curr_match_lm_in_cand = curr_match_lms_observed_in_cand.at(idx);
            if (!curr_match_lm_in_cand) {
                continue;
            }

            auto lm_in_curr = cur_keyfrm_->get_landmark(idx);
            if (lm_in_curr) {
                // if the landmark corresponding `idx` exists,
                // replace it with `curr_match_lm_in_cand` (observed in the candidate)
                if (replace_cand_landmarks)
                    curr_match_lm_in_cand->replace(lm_in_curr);
                else
                    lm_in_curr->replace(curr_match_lm_in_cand);
            } else {
                // if landmark corresponding `idx` does not exists,
                // add association between the current keyframe and `curr_match_lm_in_cand`
                cur_keyfrm_->add_landmark(curr_match_lm_in_cand, idx);
                curr_match_lm_in_cand->add_observation(cur_keyfrm_, idx);
                curr_match_lm_in_cand->compute_descriptor();

                curr_match_lm_in_cand->observed_in_other_keyframe_id_ = cur_keyfrm_->id_;
                curr_match_lm_in_cand->observed_in_other_keyframe_index_ = idx;
            }
            replaced_landmarks_num++;
        }
    }
    spdlog::debug("replaced_landmarks_num between current frame and loop frame is: {}", replaced_landmarks_num);
    // resolve duplications of landmarks between the current keyframe and the candidates of the loop candidate
    // TODO: use current keyframe landmarks to replace candidate landmarks
    replaced_landmarks_num = 0;
    const auto curr_match_lms_observed_in_cand_covis =
        loop_detector_->current_matched_landmarks_observed_in_candidate_covisibilities();
    match::fuse fuser(0.8);
    auto neighbors = cur_keyfrm_->graph_node_->get_connected_keyframes();
    for (const auto& t : Sim3s_nw_after_correction) {
        auto neighbor = t.first;
        if (neighbors.find(neighbor) == neighbors.end()) continue;
        const Mat44_t Sim3_nw_after_correction = util::converter::to_eigen_mat(t.second);

        // reproject the landmarks observed in the current keyframe to the neighbor,
        // then search duplication of the landmarks
        std::vector<data::landmark*> lms_to_replace(curr_match_lms_observed_in_cand_covis.size(), nullptr);
        fuser.detect_duplication(neighbor, Sim3_nw_after_correction, curr_match_lms_observed_in_cand_covis, 4,
                                 lms_to_replace);

        std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
        std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[cur_keyfrm_->get_map_id()]);

        // if any landmark duplication is found, replace it
        for (unsigned int i = 0; i < curr_match_lms_observed_in_cand_covis.size(); ++i) {
            auto lm_to_replace = lms_to_replace.at(i);
            if (lm_to_replace) {
                if (replace_cand_landmarks)
                    curr_match_lms_observed_in_cand_covis.at(i)->replace(lm_to_replace);
                else
                    lm_to_replace->replace(curr_match_lms_observed_in_cand_covis.at(i));
                replaced_landmarks_num++;
            }
        }
    }
    spdlog::debug("replaced_landmarks_num between current frame and loop candidates is: {}", replaced_landmarks_num);
}

auto global_optimization_module::extract_new_connections(const std::vector<data::keyframe*>& covisibilities) const
    -> std::map<data::keyframe*, std::set<data::keyframe*>>
{
    std::map<data::keyframe*, std::set<data::keyframe*>> new_connections;

    for (auto covisibility : covisibilities) {
        // acquire neighbors BEFORE loop fusion (because update_connections() is not called yet)
        const auto neighbors_before_update = covisibility->graph_node_->get_covisibilities();

        // call update_connections()
        covisibility->graph_node_->update_connections();
        // acquire neighbors AFTER loop fusion
        new_connections[covisibility] = covisibility->graph_node_->get_connected_keyframes();

        // remove covisibilities
        for (const auto keyfrm_to_erase : covisibilities) {
            new_connections.at(covisibility).erase(keyfrm_to_erase);
        }
        // remove nighbors before loop fusion
        for (const auto keyfrm_to_erase : neighbors_before_update) {
            new_connections.at(covisibility).erase(keyfrm_to_erase);
        }
        if (new_connections.at(covisibility).empty()) new_connections.erase(covisibility);
    }

    return new_connections;
}

void global_optimization_module::request_reset()
{
    {
        std::lock_guard<std::mutex> lock(mtx_reset_);
        reset_is_requested_ = true;
    }

    // BLOCK until reset
    while (true) {
        {
            std::lock_guard<std::mutex> lock(mtx_reset_);
            if (!reset_is_requested_) {
                break;
            }
        }
        std::this_thread::sleep_for(std::chrono::microseconds(3000));
    }
}

bool global_optimization_module::reset_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_reset_);
    return reset_is_requested_;
}

void global_optimization_module::reset()
{
    std::lock_guard<std::mutex> lock(mtx_reset_);
    spdlog::info("reset global optimization module");
    keyfrms_queue_.clear();
    loop_detector_->prev_server_optim_keyfrm_id_.clear();
    reset_is_requested_ = false;
}

void global_optimization_module::request_pause()
{
    std::lock_guard<std::mutex> lock1(mtx_pause_);
    pause_is_requested_ = true;
}

bool global_optimization_module::pause_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    return pause_is_requested_;
}

bool global_optimization_module::is_paused() const
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    return is_paused_;
}

void global_optimization_module::pause()
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    spdlog::info("pause global optimization module");
    is_paused_ = true;
}

void global_optimization_module::resume()
{
    std::lock_guard<std::mutex> lock1(mtx_pause_);
    std::lock_guard<std::mutex> lock2(mtx_terminate_);

    // if it has been already terminated, cannot resume
    if (is_terminated_) {
        return;
    }

    is_paused_ = false;
    pause_is_requested_ = false;

    spdlog::info("resume global optimization module");
}

void global_optimization_module::request_terminate()
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    terminate_is_requested_ = true;
}

bool global_optimization_module::is_terminated() const
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    return is_terminated_;
}

bool global_optimization_module::terminate_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    return terminate_is_requested_;
}

void global_optimization_module::terminate()
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    is_terminated_ = true;
}

bool global_optimization_module::loop_BA_is_running() const { return loop_bundle_adjuster_->is_running(); }

void global_optimization_module::abort_loop_BA() { loop_bundle_adjuster_->abort(); }

}  // namespace openvslam
