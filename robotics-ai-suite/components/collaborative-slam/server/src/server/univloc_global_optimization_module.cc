// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "univloc_global_optimization_module.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "match/fuse.h"
#include "util/converter.h"
#include "server/server.h"
#include "server/window_graph_optimizer.h"
#include "optimize/g2o/landmark_vertex_container.h"
#include "optimize/g2o/se3/reproj_edge_wrapper.h"
#include "optimize/g2o/se3/shot_vertex_container.h"
#include "util/converter.h"

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

univloc_global_optimization_module::univloc_global_optimization_module(data::map_database* map_db, data::bow_database* bow_db,
                                                       data::bow_vocabulary* bow_vocab, const bool fix_scale,
                                                       double front_rear_camera_constraint_thr, int iteration_times,
                                                       bool segment_optimize, bool correct_loop)
    : global_optimization_module(map_db, bow_db, bow_vocab, fix_scale, front_rear_camera_constraint_thr,
                                 iteration_times, segment_optimize),
      correct_loop_(correct_loop)
{
    spdlog::debug("CONSTRUCT: univloc_global_optimization_module_tyx");
}

univloc_global_optimization_module::~univloc_global_optimization_module()
{
    abort_loop_BA();
    if (thread_for_loop_BA_) {
        thread_for_loop_BA_->join();
    }
    spdlog::debug("opt_client_thread.size: {}", thread_for_optimization_client_.size());
    for (const auto& opt_client_thread : thread_for_optimization_client_) {
        spdlog::debug("opt_client_thread.first: {}", opt_client_thread.first);
        if (opt_client_thread.second) {
            spdlog::debug("opt_client_thread.second not nullptr");
            opt_client_thread.second->join();
        }
    }
    spdlog::debug("opt_map_thread.size: {}", thread_for_optimization_map_.size());
    for (const auto& opt_map_thread : thread_for_optimization_map_) {
        spdlog::debug("opt_map_thread.first: {}", opt_map_thread.first);
        if (opt_map_thread.second) {
            spdlog::debug("opt_map_thread.second not nullptr");
            opt_map_thread.second->join();
        }
    }
    spdlog::debug("DESTRUCT: univloc_global_optimization_module");
}

void univloc_global_optimization_module::set_server(univloc_server::Server* server)
{
    server_ = server;
}

void univloc_global_optimization_module::Local_BA_for_merging_map(std::vector<data::keyframe*> vec_adjust_keyframes,
                                                          std::vector<data::keyframe*> vec_fixed_keyframes)
{
    using namespace optimize;

    //ros::Time start_time = ros::Time::now();
    auto start_time = now();
    const int first_iter_times = 5, second_iter_times = 10;

    // Step1: Get all the landmarks
    std::unordered_map<unsigned int, data::landmark*> lms;
    for (auto& kfm : vec_adjust_keyframes) {
        if (!kfm) continue;
        const auto landmarks = kfm->get_landmarks();
        for (auto& lm : landmarks) {
            if (!lm || lm->will_be_erased() || lms.count(lm->id_)) {
                continue;
            }

            lms[lm->id_] = lm;
        }
    }
    for (auto& kfm : vec_fixed_keyframes) {
        if (!kfm) continue;
        const auto landmarks = kfm->get_landmarks();
        for (auto& lm : landmarks) {
            if (!lm || lm->will_be_erased() || lms.count(lm->id_)) {
                continue;
            }

            lms[lm->id_] = lm;
        }
    }
    spdlog::info("Merging map local BA involved landmarks num: {}", lms.size());
    spdlog::info("Merging map local BA involved adjust keyframes num: {}", vec_adjust_keyframes.size());
    spdlog::info("Merging map local BA involved fixed keyframes num: {}", vec_fixed_keyframes.size());

    // 2. Set optimization parameters

    auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_6_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);

    g2o::se3::shot_vertex_container keyfrm_vtx_container(0, vec_adjust_keyframes.size() + vec_fixed_keyframes.size());

    // Step3: Add keyframes vetex
    // add adjust_keyframes
    for (auto& adjust_keyframe : vec_adjust_keyframes) {
        auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(adjust_keyframe, false);
        optimizer.addVertex(keyfrm_vtx);
    }

    // add fixed_keyframes
    for (auto& fixed_keyframe : vec_fixed_keyframes) {
        auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(fixed_keyframe, true);
        // fixed_keyframe->should_be_fixed_in_optimization_ = true;
        optimizer.addVertex(keyfrm_vtx);
    }

    // Step 4. Add landmark vetex and observation edge

    // landmark vertex
    g2o::landmark_vertex_container lm_vtx_container(keyfrm_vtx_container.get_max_vertex_id() + 1, lms.size());

    // reprojection edge
    using reproj_edge_wrapper = g2o::se3::reproj_edge_wrapper<data::keyframe>;
    std::vector<reproj_edge_wrapper> reproj_edge_wraps;
    reproj_edge_wraps.reserve((vec_adjust_keyframes.size() + vec_fixed_keyframes.size()) * lms.size());

    constexpr float chi_sq_2D = 5.99146;
    const float sqrt_chi_sq_2D = std::sqrt(chi_sq_2D);
    // 自由度n=3
    constexpr float chi_sq_3D = 7.81473;
    const float sqrt_chi_sq_3D = std::sqrt(chi_sq_3D);

    for (auto& id_lm : lms) {
        auto lm = id_lm.second;
        // landmarkをg2oのvertexに変換してoptimizerにセットする
        auto lm_vtx = lm_vtx_container.create_vertex(lm, false);
        optimizer.addVertex(lm_vtx);

        const auto observations = lm->get_observations();
        for (const auto& obs : observations) {
            auto keyfrm = obs.first;
            auto idx = obs.second;
            if (!keyfrm) {
                continue;
            }
            if (keyfrm->will_be_erased()) {
                continue;
            }

            const auto keyfrm_vtx =
                keyfrm_vtx_container.get_vertex(keyfrm);  // If we don't use all the keyframes, here should be changed!
            if (!keyfrm_vtx) continue;
            const auto& undist_keypt = keyfrm->undist_keypts_.at(idx);
            const float x_right = keyfrm->stereo_x_right_.at(idx);
            const float inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(undist_keypt.octave);
            const auto sqrt_chi_sq =
                (keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular) ? sqrt_chi_sq_2D : sqrt_chi_sq_3D;
            auto reproj_edge_wrap = reproj_edge_wrapper(keyfrm, keyfrm_vtx, lm, lm_vtx, idx, undist_keypt.pt.x,
                                                        undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
            reproj_edge_wraps.push_back(reproj_edge_wrap);
            optimizer.addEdge(reproj_edge_wrap.edge_);
        }
    }

    optimizer.initializeOptimization();
    optimizer.optimize(first_iter_times);

    // 6. run robust BA, optional
    bool run_robust_BA = true;

    if (run_robust_BA) {
        for (auto& reproj_edge_wrap : reproj_edge_wraps) {
            auto edge = reproj_edge_wrap.edge_;

            auto local_lm = reproj_edge_wrap.lm_;
            if (local_lm->will_be_erased()) {
                continue;
            }

            if (reproj_edge_wrap.is_monocular_) {
                if (chi_sq_2D < edge->chi2() || !reproj_edge_wrap.depth_is_positive()) {
                    reproj_edge_wrap.set_as_outlier();
                }
            } else {
                if (chi_sq_3D < edge->chi2() || !reproj_edge_wrap.depth_is_positive()) {
                    reproj_edge_wrap.set_as_outlier();
                }
            }

            edge->setRobustKernel(nullptr);
        }

        optimizer.initializeOptimization();
        optimizer.optimize(second_iter_times);
    }

    std::vector<std::pair<data::keyframe*, data::landmark*>> outlier_observations;
    outlier_observations.reserve(reproj_edge_wraps.size());

    for (auto& reproj_edge_wrap : reproj_edge_wraps) {
        auto edge = reproj_edge_wrap.edge_;

        auto local_lm = reproj_edge_wrap.lm_;
        if (local_lm->will_be_erased()) {
            continue;
        }

        if (reproj_edge_wrap.is_monocular_) {
            if (chi_sq_2D < edge->chi2() || !reproj_edge_wrap.depth_is_positive()) {
                outlier_observations.emplace_back(std::make_pair(reproj_edge_wrap.shot_, reproj_edge_wrap.lm_));
            }
        } else {
            if (chi_sq_3D < edge->chi2() || !reproj_edge_wrap.depth_is_positive()) {
                outlier_observations.emplace_back(std::make_pair(reproj_edge_wrap.shot_, reproj_edge_wrap.lm_));
            }
        }
    }

    // 8. update the landmarks and kayframes pose
    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
    MapID map1 = vec_adjust_keyframes[0]->get_map_id(), map2 = vec_fixed_keyframes[0]->get_map_id();
    std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[map1]);
    std::lock_guard<std::mutex> lock2(data::map_database::mtx_map_database_[map2]);

    {
        if (!outlier_observations.empty()) {
            for (auto& outlier_obs : outlier_observations) {
                auto keyfrm = outlier_obs.first;
                auto lm = outlier_obs.second;
                keyfrm->erase_landmark(lm);
                lm->erase_observation(keyfrm);
            }
        }

        for (auto& kf : vec_adjust_keyframes) {
            auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(kf);
            kf->set_cam_pose(keyfrm_vtx->estimate());
            // TODO: if we don't use pose graph, we should reset in_cur_covisibility_window_ to be false
        }

        for (auto& id_lm : lms) {
            auto lm_vtx = lm_vtx_container.get_vertex(id_lm.second);
            id_lm.second->set_pos_in_world(lm_vtx->estimate());
            id_lm.second->update_normal_and_depth();
        }
    }
    spdlog::info("Successfully excute local map for map merging!, cost time {} ms",
                 duration_ms(now() - start_time));
}

void univloc_global_optimization_module::merge_map_via_loop()
{
    // No pose graph optimization when merging map!

    //ros::Time start1 = ros::Time::now();
    auto start1 = now();
    spdlog::warn("Start merge_map_via_loop!");

    auto merge_keyfrm = loop_detector_->get_selected_candidate_keyframe();

    for (const auto& opt_client_thread : thread_for_optimization_client_) {
        if (opt_client_thread.second && graph_optimizers_client_[opt_client_thread.first]->is_running() &&
            (graph_optimizers_client_[opt_client_thread.first]->get_map_id() == cur_keyfrm_->get_map_id() ||
             graph_optimizers_client_[opt_client_thread.first]->get_map_id() == merge_keyfrm->get_map_id())) {
            spdlog::debug("waiting thread_for_optimization_client to stop!");
            while (graph_optimizers_client_[opt_client_thread.first]->is_running())
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            opt_client_thread.second->join();
            thread_for_optimization_client_[opt_client_thread.first] = nullptr;
        }
    }

    if (thread_for_optimization_map_[cur_keyfrm_->get_map_id()] &&
        graph_optimizers_map_[cur_keyfrm_->get_map_id()]->is_running()) {
        spdlog::debug("waiting thread_for_optimization_map to stop!");
        while (graph_optimizers_map_[cur_keyfrm_->get_map_id()]->is_running()) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
        thread_for_optimization_map_[cur_keyfrm_->get_map_id()]->join();
        thread_for_optimization_map_[cur_keyfrm_->get_map_id()] = nullptr;
    }

    if (thread_for_optimization_map_[merge_keyfrm->get_map_id()] &&
        graph_optimizers_map_[merge_keyfrm->get_map_id()]->is_running()) {
        spdlog::debug("waiting thread_for_optimization_map to stop!");
        while (graph_optimizers_map_[merge_keyfrm->get_map_id()]->is_running()) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
        thread_for_optimization_map_[merge_keyfrm->get_map_id()]->join();
        thread_for_optimization_map_[merge_keyfrm->get_map_id()] = nullptr;
    }

    server_->pre_process_before_loop(cur_keyfrm_, merge_keyfrm);
    MapID map1 = cur_keyfrm_->get_map_id(), map2 = merge_keyfrm->get_map_id();

    // TODO:  choose which map to be fixed!
    // Inactive map should be merged into active map?
    // Smaller active map should be merged into larger active map?

    spdlog::info("current_keyframeID: {}, mapID {}, ClientID: {}", cur_keyfrm_->id_, cur_keyfrm_->get_map_id(),
                 cur_keyfrm_->client_id_);
    spdlog::info("merge_keyframeID: {}, mapID {}, ClientID: {}", merge_keyfrm->id_, merge_keyfrm->get_map_id(),
                 merge_keyfrm->client_id_);
    // Merge current keyframe map into looped_keyframe map. TODO: Merge smaller map into larger map
    // Reference: ORB_SLAM3
    const size_t keyframe_window_size = 30;

    // TODO: process message queue(maybe no need)
    cur_keyfrm_->graph_node_->update_connections();

    // Sim3 camera poses BEFORE loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_before_correction;
    // Sim3 camera poses AFTER loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_after_correction;

    std::vector<data::keyframe*> fixed_window_keyframes;
    std::vector<data::keyframe*> adjust_window_keyframes;
    std::map<data::keyframe*, std::set<data::keyframe*>> new_connections;

    spdlog::debug("merge_keyfrm get_map_id: {}, relative client map id : {}", merge_keyfrm->get_map_id(),
                  server_->get_running_client_map_id(merge_keyfrm));
    if (false && merge_keyfrm->get_map_id() != server_->get_running_client_map_id(merge_keyfrm)) {
        // The loop keyframe map is inactive, so we will transform the map onto current active map
        cur_keyfrm_->should_be_fixed_in_optimization_ = true;

        spdlog::debug("Merge inactive map into current active map");
        Mat44_t cam_pose_nw = cur_keyfrm_->get_cam_pose();
        Mat33_t rot_nw = cam_pose_nw.block<3, 3>(0, 0);
        Vec3_t trans_nw = cam_pose_nw.block<3, 1>(0, 3);
        g2o::Sim3 Sim3_nw_before_correction(rot_nw, trans_nw, 1.0);
        auto Temp_transform = loop_detector_->get_Sim3_world_to_current() * Sim3_nw_before_correction;
        // Temp_transform = Temp_transform.inverse();

        Mat44_t transform_from_loopframe_to_currentframe = Mat44_t::Identity();
        transform_from_loopframe_to_currentframe.block(0, 0, 3, 3) = Temp_transform.rotation().matrix();
        transform_from_loopframe_to_currentframe.block(0, 3, 3, 1) = Temp_transform.translation();

        transform_from_loopframe_to_currentframe =
            merge_keyfrm->get_cam_pose_inv() * transform_from_loopframe_to_currentframe * cur_keyfrm_->get_cam_pose();

        g2o::Sim3 T_transform(transform_from_loopframe_to_currentframe.block(0, 0, 3, 3),
                              transform_from_loopframe_to_currentframe.block(0, 3, 3, 1), 1.0);

        transform_map_via_sim3(merge_keyfrm, Temp_transform, Sim3s_nw_before_correction, Sim3s_nw_after_correction);

        const auto curr_match_lms_observed_in_cand = loop_detector_->current_matched_landmarks_observed_in_candidate();

        replace_duplicated_landmarks(curr_match_lms_observed_in_cand, Sim3s_nw_after_correction, true);

        fixed_window_keyframes = get_keyframe_local_map(cur_keyfrm_, keyframe_window_size);

        adjust_window_keyframes = get_keyframe_local_map(merge_keyfrm, keyframe_window_size);

        new_connections = extract_new_connections(fixed_window_keyframes);
    } else {
        spdlog::debug("Merge current keyframe map into loop keyframe map");
        // Transform map
        transform_map_via_sim3(Sim3s_nw_before_correction, Sim3s_nw_after_correction,
                               loop_detector_->get_Sim3_world_to_current(), cur_keyfrm_);

        // The transform from the image coordinate of the map to be aligned to its world coordinate.
        Mat44_t Twc_aligned = (cur_keyfrm_->cam_pose_cw_before_BA_).inverse();
        // The transform from the world coordinate of the reference map to the image coordinate of the map to be
        // aligned.
        Mat44_t Tcw_aligned_ref = util::converter::to_eigen_mat(loop_detector_->get_Sim3_world_to_current());
        // The transform from the world coordinate of the reference map to the world coordinate of the map to be
        // aligned.
        Mat44_t Tww_aligned_ref = Twc_aligned * Tcw_aligned_ref;
        server_->set_coordinate_transform(cur_keyfrm_->client_id_, Tww_aligned_ref);

        // Resolve duplications of landmarks caused by map merging
        const auto curr_match_lms_observed_in_cand = loop_detector_->current_matched_landmarks_observed_in_candidate();
        replace_duplicated_landmarks(curr_match_lms_observed_in_cand, Sim3s_nw_after_correction, false);

        // Get some window keyframes of merge_keyfrm
        fixed_window_keyframes = get_keyframe_local_map(merge_keyfrm, keyframe_window_size);
        adjust_window_keyframes = get_keyframe_local_map(cur_keyfrm_, keyframe_window_size);
        new_connections = extract_new_connections(adjust_window_keyframes);
    }

    // Extract the new connections created after loop fusion
    if (new_connections[cur_keyfrm_].find(merge_keyfrm) == new_connections[cur_keyfrm_].end())
        new_connections[cur_keyfrm_].insert(merge_keyfrm);

    // Perform local BA in the merged keyframes window
    Local_BA_for_merging_map(adjust_window_keyframes, fixed_window_keyframes);

    // add a loop edge
    merge_keyfrm->graph_node_->add_loop_edge(cur_keyfrm_);
    cur_keyfrm_->graph_node_->add_loop_edge(merge_keyfrm);

    // set the map merge information to the loop detector
    loop_detector_->set_server_optim_keyframe_id(cur_keyfrm_->client_id_, cur_keyfrm_->id_);

    // Change map id
    MapID merged_map_id = std::min(cur_keyfrm_->get_map_id(), merge_keyfrm->get_map_id());
    if (merged_map_id != cur_keyfrm_->get_map_id()) {
        std::vector<data::keyframe*> keyframes =
            map_db_->get_all_keyframes(cur_keyfrm_->get_map_id(), cur_keyfrm_->get_map_id());
        std::vector<data::landmark*> landmarks =
            map_db_->get_all_landmarks(cur_keyfrm_->get_map_id(), cur_keyfrm_->get_map_id());
        for (auto& kf : keyframes) kf->set_map_id(merged_map_id);
        for (auto& lm : landmarks) lm->set_map_id(merged_map_id);
    } else {
        std::vector<data::keyframe*> keyframes =
            map_db_->get_all_keyframes(merge_keyfrm->get_map_id(), merge_keyfrm->get_map_id());
        std::vector<data::landmark*> landmarks =
            map_db_->get_all_landmarks(merge_keyfrm->get_map_id(), merge_keyfrm->get_map_id());
        for (auto& kf : keyframes) kf->set_map_id(merged_map_id);
        for (auto& lm : landmarks) lm->set_map_id(merged_map_id);
    }

    assert(map1 != map2);
    server_->post_process_after_loop(cur_keyfrm_->client_id_, merge_keyfrm->client_id_, map1, map2);

    // Request the octree from each of the running clients
    std::set<ClientID> running_clients;
    if (!map_db_->is_keyframe_loaded(cur_keyfrm_)) running_clients.emplace(cur_keyfrm_->client_id_);
    if (!map_db_->is_keyframe_loaded(merge_keyfrm)) running_clients.emplace(merge_keyfrm->client_id_);
    server_->request_octree_from_clients(running_clients);

    auto end1 = now();
    spdlog::warn("Map merging consumes time: {} ms", duration_ms(end1 - start1));
}

void univloc_global_optimization_module::merge_map_via_front_rear_camera_constraint()
{
    spdlog::debug("start merge_map_via_front_rear_camera_constraint");
    assert(cur_keyfrm_->graph_node_->has_front_rear_camera_constraint());
    auto id_constraint_keyframe = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint();
    auto constrait_pose = map_db_->get_constraint(id_constraint_keyframe.first);
    data::keyframe* merge_keyfrm = id_constraint_keyframe.second;

    if (thread_for_optimization_map_[cur_keyfrm_->get_map_id()]) {
        while (graph_optimizers_map_[cur_keyfrm_->get_map_id()]->is_running()) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
        thread_for_optimization_map_[cur_keyfrm_->get_map_id()]->join();
        thread_for_optimization_map_[cur_keyfrm_->get_map_id()] = nullptr;
    }

    if (thread_for_optimization_map_[merge_keyfrm->get_map_id()]) {
        while (graph_optimizers_map_[merge_keyfrm->get_map_id()]->is_running()) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
        thread_for_optimization_map_[merge_keyfrm->get_map_id()]->join();
        thread_for_optimization_map_[merge_keyfrm->get_map_id()] = nullptr;
    }

    ClientID thread_idx = std::min(cur_keyfrm_->client_id_, merge_keyfrm->client_id_);

    if (graph_optimizers_client_[thread_idx]) {
        if (thread_for_optimization_client_[thread_idx]) {
            spdlog::debug(
                "merge_map_via_front_rear_camera_constraint: Waiting for last graph_optimizers_client thread exiting!");
            while (graph_optimizers_client_[thread_idx]->is_running()) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            }
            thread_for_optimization_client_[thread_idx]->join();
            thread_for_optimization_client_[thread_idx] = nullptr;
        }
    }

    MapID cur_keyfrm_map = cur_keyfrm_->get_map_id(), merge_keyfrm_map = merge_keyfrm->get_map_id();

    server_->pre_process_before_loop(cur_keyfrm_, merge_keyfrm);

    spdlog::debug("merge_keyfrm map id: {},  cur_keyfrm map id: {}", merge_keyfrm_map, cur_keyfrm_map);

    // Transform larger id map to smaller id map!
    assert(cur_keyfrm_map != merge_keyfrm_map);

    unsigned int smaller_map_client_id, larger_map_client_id;

    if (cur_keyfrm_map > merge_keyfrm_map) {
        smaller_map_client_id = merge_keyfrm->client_id_;
        larger_map_client_id = cur_keyfrm_->client_id_;
    } else {
        larger_map_client_id = merge_keyfrm->client_id_;
        smaller_map_client_id = cur_keyfrm_->client_id_;
    }

    Mat44_t transform_from_cur_to_constraint =
        larger_map_client_id < smaller_map_client_id ? constrait_pose.matrix() : constrait_pose.inverse().matrix();

    if (cur_keyfrm_map > merge_keyfrm_map)
        transform_from_cur_to_constraint =
            cur_keyfrm_->get_cam_pose_inv() * transform_from_cur_to_constraint * merge_keyfrm->get_cam_pose();
    else
        transform_from_cur_to_constraint =
            merge_keyfrm->get_cam_pose_inv() * transform_from_cur_to_constraint * cur_keyfrm_->get_cam_pose();

    // Sim3 camera poses BEFORE loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_before_correction;
    // Sim3 camera poses AFTER loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_after_correction;

    Mat33_t R = transform_from_cur_to_constraint.block(0, 0, 3, 3);
    Vec3_t t = transform_from_cur_to_constraint.block(0, 3, 3, 1);
    g2o::Sim3 T_transform(R, t, 1.0);
    if (cur_keyfrm_map > merge_keyfrm_map)
        transform_map_via_sim3(cur_keyfrm_, T_transform, Sim3s_nw_before_correction, Sim3s_nw_after_correction);
    else {
        spdlog::debug("Transform merge_keyfrm map to cur_keyfrm_ map!");
        transform_map_via_sim3(merge_keyfrm, T_transform, Sim3s_nw_before_correction, Sim3s_nw_after_correction);
    }

    int constrain_id = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint().first;
    auto constrain_pose = map_db_->get_constraint(constrain_id);
    Mat44_t constrain_pose_m = constrain_pose.matrix();
    Mat44_t error = constrain_pose_m.inverse() * cur_keyfrm_->get_cam_pose() * merge_keyfrm->get_cam_pose_inv();
    const double thr = 0.05;
    if (error.block(0, 3, 3, 1).norm() < thr) {
        merge_keyfrm->execute_front_rear_camera_constraint_ = true;
        cur_keyfrm_->execute_front_rear_camera_constraint_ = true;
    }
    spdlog::debug("End merge_map_via_front_rear_camera_constraint");

    // Change map id
    MapID merged_map_id = std::min(cur_keyfrm_->get_map_id(), merge_keyfrm->get_map_id()),
          changed_map_id = std::max(cur_keyfrm_->get_map_id(), merge_keyfrm->get_map_id());

    std::vector<data::keyframe*> keyframes = map_db_->get_all_keyframes(changed_map_id, changed_map_id);
    std::vector<data::landmark*> landmarks = map_db_->get_all_landmarks(changed_map_id, changed_map_id);
    for (auto& kf : keyframes) kf->set_map_id(merged_map_id);
    for (auto& lm : landmarks) lm->set_map_id(merged_map_id);
    last_corrected_front_rear_camera_constraints_[cur_keyfrm_->client_id_] = cur_keyfrm_;
    last_corrected_front_rear_camera_constraints_[merge_keyfrm->client_id_] = merge_keyfrm;
    server_->post_process_after_loop(cur_keyfrm_->client_id_, merge_keyfrm->client_id_, cur_keyfrm_map,
                                     merge_keyfrm_map);
}

bool univloc_global_optimization_module::detect_front_rear_camera_constraint()
{
    // TODO : correct front rear camera constraint of the old trajectory when starting a new session
    if (cur_keyfrm_->is_origin() && last_corrected_front_rear_camera_constraints_.count(cur_keyfrm_->client_id_))
        return true;
    if (!cur_keyfrm_->graph_node_->has_front_rear_camera_constraint()) return false;

    Mat44_t cur_keyframe_pose = cur_keyfrm_->get_cam_pose();
    data::keyframe* constraint_keyframe = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint().second;

    last_front_rear_camera_constraints_[cur_keyfrm_->client_id_] = cur_keyfrm_;
    last_front_rear_camera_constraints_[constraint_keyframe->client_id_] = constraint_keyframe;

    if (cur_keyfrm_->get_map_id() != constraint_keyframe->get_map_id()) return true;

    Mat44_t relative_pose = cur_keyframe_pose * constraint_keyframe->get_cam_pose_inv();
    int constraint_id = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint().first;
    auto constraint_pose = map_db_->get_constraint(constraint_id);
    Mat44_t constraint_pose_m = Mat44_t::Identity();
    constraint_pose_m.block(0, 0, 3, 3) = constraint_pose.rotation().matrix();
    constraint_pose_m.block(0, 3, 3, 1) = constraint_pose.translation();

    Mat44_t transform_diff = constraint_pose_m.inverse() * relative_pose;

    if ((transform_diff.block(0, 3, 3, 1)).norm() > front_rear_camera_constraint_thr_) {
        spdlog::debug("Get front_rear_camera_constraint!");
        return true;
    }
    return false;
}

void univloc_global_optimization_module::add_loop_connections(
    MapID map_id, const std::map<data::keyframe*, std::set<data::keyframe*>>& new_connections)
{
    loop_connections_with_pose_[map_id].clear();
    for (auto& item : new_connections) {
        loop_connections_[map_id][item.first] = item.second;  // What if one kfm has two connections
        auto kf_pose_1 = item.first->loop_BA_identifier_ == cur_keyfrm_->id_
                             ? std::make_pair(item.first, item.first->cam_pose_cw_after_loop_BA_)
                             : std::make_pair(item.first, item.first->get_cam_pose());
        for (auto& kf_pose : item.second) {
            auto kf_pose_2 = kf_pose->loop_BA_identifier_ == cur_keyfrm_->id_
                                 ? std::make_pair(kf_pose, kf_pose->cam_pose_cw_after_loop_BA_)
                                 : std::make_pair(kf_pose, kf_pose->get_cam_pose());
            loop_connections_with_pose_[map_id].push_back(std::make_pair(kf_pose_1, kf_pose_2));
        }
    }
}

void univloc_global_optimization_module::correct_loop()
{
    spdlog::warn("start correcting loop!");

    auto final_candidate_keyfrm = loop_detector_->get_selected_candidate_keyframe();

    unsigned int thread_idx = cur_keyfrm_->get_map_id(), map_id = cur_keyfrm_->get_map_id();
    if (thread_for_optimization_map_[thread_idx] && graph_optimizers_map_[thread_idx])
        graph_optimizers_map_[thread_idx]->abort_graph_optimizaion();

    for (const auto& opt_client_thread : thread_for_optimization_client_) {
        if (opt_client_thread.second &&
            graph_optimizers_client_[opt_client_thread.first]->get_map_id() == cur_keyfrm_->get_map_id())
            graph_optimizers_client_[opt_client_thread.first]->abort_graph_optimizaion();
    }

    // set the loop correction information to the loop detector
    loop_detector_->set_server_optim_keyframe_id(cur_keyfrm_->client_id_, cur_keyfrm_->id_);

    if (map_db_->is_keyframe_loaded(final_candidate_keyfrm)) {
        spdlog::info("[detect loop]: current keyframe {} belongs to client {}, and its loop candidate keyframe {} "
                     "is loaded from previous map with client ID {}", cur_keyfrm_->id_, cur_keyfrm_->client_id_,
                     final_candidate_keyfrm->id_, final_candidate_keyfrm->client_id_);
    } else {
        spdlog::info("[detect loop]: current keyframe {} belongs to client {}, and its loop candidate keyframe {} "
                     "belongs to running client {}", cur_keyfrm_->id_, cur_keyfrm_->client_id_, final_candidate_keyfrm->id_,
                     final_candidate_keyfrm->client_id_);
    }

    // 0-2. update the graph
    // This will add loop keyframes to current keyframe covisibility!
    cur_keyfrm_->graph_node_->update_connections();

    // data::keyframe origin_keyframe = map_db_->get_origin_keyfrm(cur_keyfrm_->get_map_id());

    // 1. compute the Sim3 of the covisibilities of the current keyframe whose Sim3 is already estimated by the loop
    // detector then, the covisibilities are moved to the corrected positions finally, landmarks observed in them are
    // also moved to the correct position using the camera poses before and after camera pose correction

    // acquire the covisibilities of the current keyframe
    std::vector<data::keyframe*> curr_neighbors = cur_keyfrm_->graph_node_->get_covisibilities();
    curr_neighbors.push_back(cur_keyfrm_);

    for (auto& kf : curr_neighbors) {
        unused_neighbors_[map_id].push_back(kf);
    }

    // Sim3 camera poses BEFORE loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_before_correction;
    // Sim3 camera poses AFTER loop correction
    module::keyframe_Sim3_pairs_t Sim3s_nw_after_correction;

    const auto g2o_Sim3_cw_after_correction = loop_detector_->get_Sim3_world_to_current();
    {
        std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
        std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[cur_keyfrm_->get_map_id()]);

        // camera pose of the current keyframe BEFORE loop correction
        const Mat44_t cam_pose_wc_before_correction = cur_keyfrm_->get_cam_pose_inv();

        // compute Sim3s BEFORE loop correction
        Sim3s_nw_before_correction = get_Sim3s_before_loop_correction(curr_neighbors);
        // compute Sim3s AFTER loop correction
        Sim3s_nw_after_correction = get_Sim3s_after_loop_correction(cam_pose_wc_before_correction,
                                                                    g2o_Sim3_cw_after_correction, curr_neighbors);

        // correct covibisibility landmark positions
        // TODO: in openvslam, correct_covisibility_landmarks is used for correct_loop
        //       need to investigate the reason why not using it (comment out before Improve IMU commit)
        // correct_covisibility_landmarks(Sim3s_nw_before_correction, Sim3s_nw_after_correction);
        // correct covisibility keyframe camera poses
        correct_covisibility_keyframes(Sim3s_nw_after_correction, false);
    }

    /*for (auto& kf : unused_neighbors_[map_id])
        kf->loop_BA_identifier_ = cur_keyfrm_->id_;*/

    // 2. resolve duplications of landmarks caused by loop fusion
    const auto curr_match_lms_observed_in_cand = loop_detector_->current_matched_landmarks_observed_in_candidate();
    replace_duplicated_landmarks(curr_match_lms_observed_in_cand, Sim3s_nw_after_correction, false);

    // 3. extract the new connections created after loop fusion
    spdlog::debug("extract_new_connections!");
    auto new_connections = extract_new_connections(curr_neighbors);
    if (new_connections[cur_keyfrm_].find(final_candidate_keyfrm) == new_connections[cur_keyfrm_].end())
        new_connections[cur_keyfrm_].insert(final_candidate_keyfrm);

    add_loop_connections(map_id, new_connections);
    // 4. pose graph optimization

    spdlog::debug("waiting thread_for_optimization_client to stop!");
    for (const auto& opt_client_thread : thread_for_optimization_client_) {
        if (opt_client_thread.second &&
            graph_optimizers_client_[opt_client_thread.first]->get_map_id() == cur_keyfrm_->get_map_id()) {
            while (graph_optimizers_client_[opt_client_thread.first]->is_running())
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            opt_client_thread.second->join();
            thread_for_optimization_client_[opt_client_thread.first] = nullptr;
        }
    }

    if (graph_optimizers_map_[thread_idx]) {
        if (thread_for_optimization_map_[thread_idx]) {
            spdlog::debug("waiting thread_for_optimization_map to stop!");
            while (graph_optimizers_map_[thread_idx]->is_running()) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            }
            thread_for_optimization_map_[thread_idx]->join();
            thread_for_optimization_map_[thread_idx] = nullptr;
        }
    } else {
        if (segment_optimize_) {
            graph_optimizers_map_[thread_idx] =
                std::make_unique<optimize::window_graph_optimizer>(map_db_, fix_scale_, server_);
        } else {
            graph_optimizers_map_[thread_idx] =
                std::make_unique<optimize::univloc_graph_optimizer>(map_db_, fix_scale_, server_);
        }
    }

    // pause the process of msg in client_handler::worker to avoid wrong msg process ordering
    // otherwise, the process_msg_stored_in_queue func will process msg eariler than the worker func
    // thus causing "no reference frame for xx mappoint" warning
    server_->pre_process_before_loop(cur_keyfrm_, cur_keyfrm_);

    spdlog::debug("Start thread_for_optimization_map!");
    if (segment_optimize_) {
        thread_for_optimization_map_[thread_idx] = std::unique_ptr<std::thread>(new std::thread(
            std::bind(&optimize::window_graph_optimizer::optimize,
                      static_cast<optimize::window_graph_optimizer*>(graph_optimizers_map_[thread_idx].get()),
                      final_candidate_keyfrm, cur_keyfrm_, loop_connections_.at(map_id), iteration_times_)));
    } else {
        thread_for_optimization_map_[thread_idx] = std::unique_ptr<std::thread>(new std::thread(
            std::bind(&optimize::univloc_graph_optimizer::optimize, graph_optimizers_map_[thread_idx].get(),
                      final_candidate_keyfrm, cur_keyfrm_, loop_connections_.at(map_id), unused_neighbors_[map_id],
                      loop_connections_with_pose_.at(map_id), iteration_times_)));
    }
}

void univloc_global_optimization_module::correct_front_rear_camera_constraint()
{
    if (cur_keyfrm_->is_origin()) {
        return;

        // TODO: correct the constraint when one of the client starts a new session!
        /*
        data::keyframe *kf1 = nullptr, *kf2 = nullptr;

        if (last_front_rear_camera_constraints_.count(cur_keyfrm_->client_id_)) {
            kf1 = last_front_rear_camera_constraints_[cur_keyfrm_->client_id_];
            kf2 = kf1->graph_node_->get_front_rear_camera_constraint().second;
        } else
            return;
        // Avoid duplicate operation!
        if (!kf1 || !kf2) return;
        if (last_corrected_front_rear_camera_constraints_.count(kf1->client_id_) &&
            last_corrected_front_rear_camera_constraints_[kf1->client_id_]->id_ == kf1->id_)
            return;

        if (kf1->get_map_id() != kf2->get_map_id()) return;
        MapID map_id = kf1->get_map_id();
        spdlog::info("correctting front_rear_camera_constraint when start a new map session!");

        if (thread_for_optimization_map_[map_id] && graph_optimizers_map_[map_id]->is_running()) {
            while (graph_optimizers_map_[map_id]->is_running()) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            }
            thread_for_optimization_map_[map_id]->join();
            thread_for_optimization_map_.erase(map_id);
            graph_optimizers_map_.erase(map_id);
        }
        assert(kf1->client_id_ != kf2->client_id_);
        ClientID thread_idx = std::min(kf1->client_id_, kf2->client_id_);
        if (graph_optimizers_client_[thread_idx] && graph_optimizers_client_[thread_idx]->is_running()) {
            if (kf1 && graph_optimizers_client_[thread_idx]->get_keyframe_id() != std::min(kf1->id_, kf2->id_))
                graph_optimizers_client_[thread_idx]->abort_graph_optimizaion();

            if (thread_for_optimization_client_[thread_idx]) {
                spdlog::debug("when start a new map session Waiting for last graph_optimizers_client thread exiting!");
                while (graph_optimizers_client_[thread_idx]->is_running()) {
                    std::this_thread::sleep_for(std::chrono::microseconds(100));
                }
                thread_for_optimization_client_[thread_idx]->join();
                thread_for_optimization_client_[thread_idx] = nullptr;
            }

            if (kf1 && kf2 && graph_optimizers_client_[thread_idx]->get_keyframe_id() != std::min(kf1->id_, kf2->id_)) {
                // It means that a map session created by this client finished, its front_rear_camera_constraints should
                // be corrected
                spdlog::debug("Correct front and rear camera constraints when start a new map session for client {}",
                              cur_keyfrm_->client_id_);
                int iteration_times = iteration_times_ * 0.5;
                if (thread_for_optimization_client_.count(thread_idx))
                    thread_for_optimization_client_.erase(thread_idx);
                thread_for_optimization_client_[thread_idx] = std::unique_ptr<std::thread>(new std::thread(
                    std::bind(&optimize::univloc_graph_optimizer::optimize_involved, graph_optimizers_client_[thread_idx].get(),
                              kf1, kf2, iteration_times, true)));
                last_corrected_front_rear_camera_constraints_[kf1->client_id_] = kf1;
                last_corrected_front_rear_camera_constraints_[kf2->client_id_] = kf2;
            }
        } else {
            spdlog::debug("Create thread and optimizer for front rear camera constraint when starting a new session!");
            graph_optimizers_client_[thread_idx] = nullptr;
            if (graph_optimizers_client_.count(thread_idx)) graph_optimizers_client_.erase(thread_idx);
            graph_optimizers_client_[thread_idx] =
                std::make_unique<optimize::univloc_graph_optimizer>(map_db_, fix_scale_, server_);
            int iteration_times = iteration_times_ * 0.5;
            if (thread_for_optimization_client_.count(thread_idx)) {
                thread_for_optimization_client_[thread_idx] = nullptr;
                thread_for_optimization_client_.erase(thread_idx);
            }

            thread_for_optimization_client_[thread_idx] = std::unique_ptr<std::thread>(new std::thread(
                std::bind(&optimize::univloc_graph_optimizer::optimize_involved, graph_optimizers_client_[thread_idx].get(),
                          kf1, kf2, iteration_times, true)));
            last_corrected_front_rear_camera_constraints_[kf1->client_id_] = kf1;
            last_corrected_front_rear_camera_constraints_[kf2->client_id_] = kf2;
        }

        return;
        */
    }
    spdlog::debug("start correct_front_rear_camera_constraint");
    assert(cur_keyfrm_->graph_node_->has_front_rear_camera_constraint());
    data::keyframe* merge_keyfrm = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint().second;

    ClientID thread_idx = std::min(cur_keyfrm_->client_id_, merge_keyfrm->client_id_);
    if (graph_optimizers_client_[thread_idx] &&
        graph_optimizers_client_[thread_idx]->get_map_id() == cur_keyfrm_->get_map_id())
        graph_optimizers_client_[thread_idx]->abort_graph_optimizaion();

    MapID map_id = cur_keyfrm_->get_map_id();

    if (thread_for_optimization_map_[map_id]) {
        while (graph_optimizers_map_[map_id]->is_running()) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
        thread_for_optimization_map_[map_id]->join();
        thread_for_optimization_map_.erase(map_id);
        graph_optimizers_map_.erase(map_id);
    }

    if (graph_optimizers_client_[thread_idx]) {
        if (thread_for_optimization_client_[thread_idx] &&
            graph_optimizers_client_[thread_idx]->get_map_id() == map_id) {
            spdlog::debug("Waiting for last graph_optimizers_client thread exiting!");
            while (graph_optimizers_client_[thread_idx]->is_running()) {
                std::this_thread::sleep_for(std::chrono::microseconds(100));
            }
            thread_for_optimization_client_[thread_idx]->join();
            thread_for_optimization_client_[thread_idx] = nullptr;
            spdlog::debug("Abort last graph_optimizers_client thread!");
        }
    } else {
        if (graph_optimizers_client_.count(thread_idx)) graph_optimizers_client_.erase(thread_idx);
        graph_optimizers_client_[thread_idx] =
            std::make_unique<optimize::univloc_graph_optimizer>(map_db_, fix_scale_, server_);
    }

    // pause the process of msg in client_handler::worker to avoid wrong msg process ordering
    // otherwise, the process_msg_stored_in_queue func will process msg eariler than the worker func
    // thus causing "no reference frame for xx mappoint" warning
    server_->pre_process_before_loop(cur_keyfrm_, cur_keyfrm_);

    int iteration_times = iteration_times_ * 0.5;
    if (thread_for_optimization_client_.count(thread_idx)) thread_for_optimization_client_.erase(thread_idx);
    thread_for_optimization_client_[thread_idx] = std::unique_ptr<std::thread>(new std::thread(
        std::bind(&optimize::univloc_graph_optimizer::optimize_involved, graph_optimizers_client_[thread_idx].get(),
                  cur_keyfrm_, merge_keyfrm, iteration_times, true)));
    last_corrected_front_rear_camera_constraints_[cur_keyfrm_->client_id_] = cur_keyfrm_;
    last_corrected_front_rear_camera_constraints_[merge_keyfrm->client_id_] = merge_keyfrm;
}

void univloc_global_optimization_module::run()
{
    spdlog::info("start global optimization module");

    is_terminated_ = false;

    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));

        detect_front_rear_camera_constraint_ = false;

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

        // check whether certain map should be avoided for map merge
        // detailed check is within detect_loop_candidates func
        if (cur_keyfrm_->bad_imu_to_reset_) {
            loop_detector_->bad_imu_map_ids_.emplace(cur_keyfrm_->get_map_id());
            spdlog::debug("bad imu detected for map id");
        }

        // detect some loop candidate with BoW
        // TODO: recovery monucular scale from existed rgbd map

        if (!loop_detector_->detect_loop_candidates()) {
            if (detect_front_rear_camera_constraint()) {
                detect_front_rear_camera_constraint_ = true;

                goto Optimization;
            }
            // allow the removal of the current keyframe
            cur_keyfrm_->set_to_be_erased();
            // Not found loop, then sending nearby landmarks to relevant client
            server_->send_nearby_landmarks_to_client(cur_keyfrm_);

            continue;
        }

        // validate candidates and select ONE candidate from them
        if (!loop_detector_->validate_candidates(g2o_sim3_cand_to_curr_)) {
            // could not find
            // allow the removal of the current keyframe
            if (detect_front_rear_camera_constraint()) {
                detect_front_rear_camera_constraint_ = true;
                goto Optimization;
            }

            cur_keyfrm_->set_to_be_erased();
            server_->send_nearby_landmarks_to_client(cur_keyfrm_);
            continue;
        } else {
            // TODO: this assumption constraints only the map with larger ID can merge to map with smaller ID.
            //       But in the real scenario, we do have some opposite cases.
            if (loop_detector_->get_selected_candidate_keyframe()->get_map_id() > cur_keyfrm_->get_map_id()) {
                spdlog::warn("Currently we only allow the map with larger ID merge to the map with smaller ID, \
                              so please change the order of your startup for the multiple clients to meet this \
                              kind of requirement!");
                continue;
            }
            spdlog::debug("~~~~~~~~~~~~~~~~~~~~~~~~~~~Loop validate!~~~~~~~~~~~~~~~~~~~~~~~~~");
            goto Optimization;
        }

    Optimization:

        //ros::Time start = ros::Time::now();
        auto start = now();
        // If two keyframes come from different map, we should merge the two maps at first
        data::keyframe* looped_keyframe = nullptr;
        if (detect_front_rear_camera_constraint_) {
            if (cur_keyfrm_->is_origin()) {
                correct_front_rear_camera_constraint();
                continue;
            }
            auto id_constraint_keyframe = cur_keyfrm_->graph_node_->get_front_rear_camera_constraint();
            looped_keyframe = id_constraint_keyframe.second;

        } else
            looped_keyframe = loop_detector_->get_selected_candidate_keyframe();

        assert(looped_keyframe);

        if (looped_keyframe->get_map_id() != cur_keyfrm_->get_map_id() && !cur_keyfrm_->is_origin()) {
            if (detect_front_rear_camera_constraint_) {
                merge_map_via_front_rear_camera_constraint();
                spdlog::info("merge_map_via_front_rear_camera_constraint comsumes time: {} ms",
                             duration_ms(now() - start));
            } else {
                merge_map_via_loop();
                spdlog::info("merge_map_via_loop comsumes time: {} ms", duration_ms(now() - start));
            }
        } else {
            if (detect_front_rear_camera_constraint_) {
                correct_front_rear_camera_constraint();
                spdlog::info("correct_front_rear_camera_constraint comsumes time: {} ms",
                             duration_ms(now() - start));
            } else if (looped_keyframe->get_map_id() == cur_keyfrm_->get_map_id() && correct_loop_) {
                correct_loop();
                spdlog::warn("correct_loop comsumes time: {} ms", duration_ms(now() - start));
            }
        }
        spdlog::info("~~~~~~~~~~~~~~~~~~~~~~~~~~~Optimization Finished!~~~~~~~~~~~~~~~~~~~~~~~~~");
    }

    spdlog::info("terminate global optimization module");
}

}  // namespace openvslam
