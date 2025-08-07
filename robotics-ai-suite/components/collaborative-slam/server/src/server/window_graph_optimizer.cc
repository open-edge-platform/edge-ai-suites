// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/window.h"
#include "data/map_database.h"
#include "server/server.h"
#include "server/window_graph_optimizer.h"
#include "optimize/g2o/sim3/shot_vertex.h"
#include "optimize/g2o/sim3/graph_opt_edge.h"
#include "optimize/g2o/se3/shot_vertex.h"
#include "optimize/multi_camera_edge.h"

#include "util/converter.h"

#include <Eigen/StdVector>
#include <g2o/core/solver.h>
#include <g2o/core/block_solver.h>
#include <g2o/core/sparse_optimizer.h>
#include <g2o/core/robust_kernel_impl.h>
#include <g2o/solvers/csparse/linear_solver_csparse.h>
#include <g2o/core/optimization_algorithm_levenberg.h>
#include <g2o/types/slam3d/vertex_se3.h>

#include <unordered_map>
#include <spdlog/spdlog.h>

namespace openvslam {
namespace optimize {

window_graph_optimizer::window_graph_optimizer(data::map_database* map_db, const bool fix_scale,
                                               univloc_server::Server* server)
    : univloc_graph_optimizer(map_db, fix_scale, server)
{
}

bool window_graph_optimizer::slerp_pose_between_keyframes(data::keyframe* kf, double time, Mat44_t& T_interp) const
{
    // ------kf1-----kf2----time---kf3----kf4
    // TODO: process out of range case, we get 4 keyframes but only use 2 keyframe pose to intrep
    double t1 = kf->timestamp_;
    // const data::keyframe* kf1 = nullptr;
    const data::keyframe* kf2 = nullptr;
    const data::keyframe* kf3 = nullptr;
    // const data::keyframe* kf4 = nullptr;
    if (time > t1) {
        kf2 = kf;
        unsigned int id = kf->id_;
        id++;
        kf3 = map_db_->get_keyframe(id);
        int trail_times = 10;
        while ((!kf3 || kf3->timestamp_ < time) && trail_times > 0) {
            kf3 = map_db_->get_keyframe(id++);
            trail_times--;
        }
        if (trail_times <= 0) return false;
    } else {
        kf3 = kf;
        unsigned int id = kf->id_;
        id--;
        kf2 = map_db_->get_keyframe(id);
        int trail_times = 10;

        while ((!kf2 || kf2->timestamp_ > time) && trail_times > 0) {
            kf2 = map_db_->get_keyframe(id--);
            trail_times--;
        }
        if (trail_times <= 0) return false;
    }
    assert(kf3 && "No kf3");
    Mat44_t T3 = kf3->get_cam_pose_inv();
    assert(kf2 && "No kf2");
    Mat44_t T2 = kf2->get_cam_pose_inv();

    Mat33_t R2 = T2.block(0, 0, 3, 3);
    Mat33_t R3 = T3.block(0, 0, 3, 3);

    Eigen::Vector3d t2 = T2.block(0, 3, 3, 1);
    Eigen::Vector3d t3 = T3.block(0, 3, 3, 1);

    double time2 = kf2->timestamp_;
    double time3 = kf3->timestamp_;
    Eigen::Quaterniond q2(R2);
    Eigen::Quaterniond q3(R3);
    q2.normalize();
    q3.normalize();
    if (!(time2 < time && time < time3)) spdlog::debug("time2 {}, time {}, time3 {}", time2, time, time3);
    assert(time2 < time && time < time3);

    double ratio = (time - time2) / (time3 - time2);

    auto q_interp = q2.slerp(ratio, q3).normalized();

    Eigen::Vector3d t_interp(ratio * t3[0] + (1.0 - ratio) * t2[0], ratio * t3[1] + (1.0 - ratio) * t2[1],
                             ratio * t3[2] + (1.0 - ratio) * t2[2]);

    T_interp = Mat44_t::Identity();

    T_interp.block(0, 3, 3, 1) = t_interp;

    T_interp.block(0, 0, 3, 3) = q_interp.matrix();

    return true;
}

void window_graph_optimizer::abort_graph_optimizaion()
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    abort_graph_optimization_ = true;
    switch (optimization_type_) {
        case Loop_Optimization:
            spdlog::debug("Abort this Loop_Optimization !");
            break;

        default:
            spdlog::debug("Abort this Front_Rear_Optimization !");
            break;
    }
}

bool window_graph_optimizer::is_running()
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    return graph_optimization_is_running_;
}

void window_graph_optimizer::optimize(data::keyframe* loop_keyfrm, data::keyframe* curr_keyfrm,
                                      std::map<data::keyframe*, std::set<data::keyframe*>>& loop_connections,
                                      int iteration_times)
{
    spdlog::debug("Start correct loop in window optimize!");
    //ros::Time start_time = ros::Time::now();
    auto start_time= now();
    assert(loop_keyfrm->get_map_id() == curr_keyfrm->get_map_id());
    auto fixed_keyframe = map_db_->get_origin_keyframe(curr_keyfrm->get_map_id());
    if (!fixed_keyframe) {
        spdlog::error("map {} doesn't exist in the origin_keyfrms_ unordered_map of map_db_!",
                      curr_keyfrm->get_map_id());
        return;
    }

    unsigned int fixed_keyframe_id = fixed_keyframe->id_;
    unsigned int loop_identifier = curr_keyfrm->id_;
    map_id_ = curr_keyfrm->get_map_id();
    optimization_type_ = Loop_Optimization;

    server_->record_mapid_before_optimization(curr_keyfrm->get_map_id());

    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        graph_optimization_is_running_ = true;
        abort_graph_optimization_ = false;
    }

    // correct_loop is true, it means this optimization is for a loop, we need to optimize all the objects
    // Otherwise, it means this optimization is for correct front rear camera constraint, we only need to
    // optimize objects created by the two clients

    // 1. declare optimizer
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_7_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_7_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);
    optimizer.setForceStopFlag(&abort_graph_optimization_);

    // 2. perform segment
    std::map<KeyframeID, data::keyframe*> curr_keyfrms;
    std::map<KeyframeID, data::keyframe*> loop_keyfrms;
    map_db_->get_all_keyframes_map(curr_keyfrms, curr_keyfrm->get_map_id());
    map_db_->get_all_keyframes_map(loop_keyfrms, loop_keyfrm->get_map_id());
    const auto all_keyfrms = map_db_->get_all_keyframes(loop_keyfrm->get_map_id(), curr_keyfrm->get_map_id());

    std::vector<data::keyframe*> opt_keyfrms;
    std::vector<data::keyframe*> single_keyfrms;
    std::vector<data::keyframe*> window_keyfrms;
    std::vector<data::window*> all_windows;
    std::unordered_map<KeyframeID, data::keyframe*> opt_keyfrm_ids;

    // classify single keyframes and window keyframes
    classify_keyframes(curr_keyfrms, single_keyfrms, window_keyfrms, all_windows, opt_keyfrm_ids);
    classify_keyframes(loop_keyfrms, single_keyfrms, window_keyfrms, all_windows, opt_keyfrm_ids);
    opt_keyfrms.insert(opt_keyfrms.end(), single_keyfrms.begin(), single_keyfrms.end());
    opt_keyfrms.insert(opt_keyfrms.end(), window_keyfrms.begin(), window_keyfrms.end());

    // 3. add vertex
    std::unordered_map<unsigned int, ::g2o::Sim3> map_Sim3s_cw;
    std::unordered_map<unsigned int, g2o::sim3::shot_vertex*> map_vertices;

    for (auto keyfrm : all_keyfrms) {
        if (!keyfrm) {
            std::cout << "No such keyframe" << std::endl;
            continue;
        }
        if (keyfrm->will_be_erased()) {
            continue;
        }
        auto keyfrm_vtx = new g2o::sim3::shot_vertex();

        const auto id = keyfrm->id_;

        if (keyfrm->loop_BA_identifier_ == loop_identifier) {
            const Mat33_t rot_cw = keyfrm->cam_pose_cw_after_loop_BA_.block(0, 0, 3, 3);
            const Vec3_t trans_cw = keyfrm->cam_pose_cw_after_loop_BA_.block(0, 3, 3, 1);
            const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);
            // Sim3s_cw.at(id) = Sim3_cw;
            map_Sim3s_cw[id] = Sim3_cw;
            keyfrm_vtx->setEstimate(Sim3_cw);

            // add loop keyframes into single keyframes
            if (opt_keyfrm_ids.find(id) == opt_keyfrm_ids.end()) {
                opt_keyfrms.push_back(keyfrm);
                single_keyfrms.push_back(keyfrm);
                opt_keyfrm_ids[id] = keyfrm;
            }
        } else {
            const Mat33_t rot_cw = keyfrm->get_rotation();
            const Vec3_t trans_cw = keyfrm->get_translation();
            const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);
            // Sim3s_cw.at(id) = Sim3_cw;
            map_Sim3s_cw[id] = Sim3_cw;
            keyfrm_vtx->setEstimate(Sim3_cw);
        }

        // Set the map origin frame to be fiexed
        if (keyfrm->id_ == fixed_keyframe_id) {
            keyfrm_vtx->setFixed(true);

            // add fixed keyframe into single keyframes
            if (opt_keyfrm_ids.find(id) == opt_keyfrm_ids.end()) {
                opt_keyfrms.push_back(keyfrm);
                single_keyfrms.push_back(keyfrm);
                opt_keyfrm_ids[id] = keyfrm;
            }
            spdlog::debug("Set fixed keyframe: {}", keyfrm->id_);
        }

        // if keyframe has loop edges, then add to the optimizing vertex
        if (keyfrm->graph_node_->has_loop_edge()) {
            if (opt_keyfrm_ids.find(id) == opt_keyfrm_ids.end()) {
                opt_keyfrms.push_back(keyfrm);
                single_keyfrms.push_back(keyfrm);
                opt_keyfrm_ids[id] = keyfrm;
            }
        }

        // vertexをoptimizerにセット
        keyfrm_vtx->setId(keyframeID_to_vertexID(id));
        keyfrm_vtx->fix_scale_ = fix_scale_;

        // only optimizing vertex will be added to the optimizer
        if (opt_keyfrm_ids.find(id) == opt_keyfrm_ids.end()) {
            delete keyfrm_vtx;
        } else {
            optimizer.addVertex(keyfrm_vtx);
            map_vertices[id] = keyfrm_vtx;
        }
    }

    // 4. add edge
    constexpr int min_weight = 100;  // Hype parameters, need to adjust
    std::set<std::pair<unsigned int, unsigned int>> inserted_edge_pairs;

    const auto insert_edge = [&optimizer, &map_vertices, &inserted_edge_pairs](unsigned int id1, unsigned int id2,
                                                                               const ::g2o::Sim3& Sim3_21) {
        if (inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2))))
            return;
        auto edge = new g2o::sim3::graph_opt_edge();
        edge->setVertex(0, map_vertices[id1]);
        edge->setVertex(1, map_vertices[id2]);
        edge->setMeasurement(Sim3_21);

        edge->information() = MatRC_t<7, 7>::Identity();

        optimizer.addEdge(edge);
        inserted_edge_pairs.insert(std::make_pair(std::min(id1, id2), std::max(id1, id2)));
    };

    // add loop edges over threshold weight
    for (const auto& loop_connection : loop_connections) {
        auto keyfrm = loop_connection.first;
        const auto& connected_keyfrms = loop_connection.second;

        const auto id1 = keyfrm->id_;
        const ::g2o::Sim3& Sim3_1w = map_Sim3s_cw[id1];
        const ::g2o::Sim3 Sim3_w1 = Sim3_1w.inverse();

        for (const auto& connected_keyfrm : connected_keyfrms) {
            if (connected_keyfrm->will_be_erased()) continue;
            const auto id2 = connected_keyfrm->id_;

            // For edges other than current vs loop, only add those that exceed the weight threshold
            if ((id1 != curr_keyfrm->id_ || id2 != loop_keyfrm->id_) &&
                keyfrm->graph_node_->get_weight(connected_keyfrm) < min_weight) {
                continue;
            }

            // calculate pose estimzation
            // const ::g2o::Sim3& Sim3_2w = Sim3s_cw.at(id2);
            const ::g2o::Sim3& Sim3_2w = map_Sim3s_cw[id2];
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            // if there are not vertexes, create the vertexes
            if (opt_keyfrm_ids.find(id1) == opt_keyfrm_ids.end()) {
                auto keyfrm_vtx = new g2o::sim3::shot_vertex();
                // 设置pose
                const ::g2o::Sim3 Sim3_cw(map_Sim3s_cw.at(id1));
                keyfrm_vtx->setEstimate(Sim3_cw);
                keyfrm_vtx->fix_scale_ = fix_scale_;
                keyfrm_vtx->setId(keyframeID_to_vertexID(id1));
                optimizer.addVertex(keyfrm_vtx);
                map_vertices[id1] = keyfrm_vtx;
                opt_keyfrms.push_back(keyfrm);
                single_keyfrms.push_back(keyfrm);
                opt_keyfrm_ids[id1] = keyfrm;
            }
            if (opt_keyfrm_ids.find(id2) == opt_keyfrm_ids.end()) {
                auto keyfrm_vtx = new g2o::sim3::shot_vertex();
                // 设置pose
                const ::g2o::Sim3 Sim3_cw(map_Sim3s_cw.at(id2));
                keyfrm_vtx->setEstimate(Sim3_cw);
                keyfrm_vtx->fix_scale_ = fix_scale_;
                keyfrm_vtx->setId(keyframeID_to_vertexID(id2));
                optimizer.addVertex(keyfrm_vtx);
                map_vertices[id2] = keyfrm_vtx;
                opt_keyfrms.push_back(connected_keyfrm);
                single_keyfrms.push_back(connected_keyfrm);
                opt_keyfrm_ids[id2] = connected_keyfrm;
            }

            // add constraint edge
            insert_edge(id1, id2, Sim3_21);
        }
    }

    // calcualte order opt keyframs ids
    std::set<unsigned int> order_opt_keyfrm_ids;
    for (const auto& id_keyfrm : opt_keyfrm_ids) {
        order_opt_keyfrm_ids.insert(id_keyfrm.first);
    }

    // add other edges except loop connection
    for (auto keyfrm : opt_keyfrms) {
        if (!keyfrm) {
            std::cout << "No such keyframe" << std::endl;
            continue;
        }
        if (keyfrm->will_be_erased()) continue;
        const auto id1 = keyfrm->id_;

        // Check if it is included in covisibilities and make sure to use the uncorrected posture
        // (Because both must be uncorrected to calculate the relative attitude correctly)
        auto cam_pose_wc_before_BA = keyfrm->cam_pose_cw_before_BA_.inverse();

        const ::g2o::Sim3 Sim3_w1 =
            keyfrm->loop_BA_identifier_ == loop_identifier
                ? ::g2o::Sim3(cam_pose_wc_before_BA.block(0, 0, 3, 3), cam_pose_wc_before_BA.block(0, 3, 3, 1), 1.0)
                : map_Sim3s_cw.at(id1).inverse();

        auto parent_node = keyfrm->graph_node_->get_spanning_parent();
        if (parent_node) {
            // the closest keyfrm is used as the parent node
            // use the first value not less than id
            std::set<unsigned int>::iterator bound_iter = order_opt_keyfrm_ids.lower_bound(parent_node->id_);
            if (bound_iter == order_opt_keyfrm_ids.begin()) {
                parent_node = opt_keyfrm_ids[*(bound_iter)];
            } else {
                std::set<unsigned int>::iterator prev_iter = bound_iter;
                std::advance(prev_iter, -1);
                // the closet keframe will become parent
                if (*bound_iter >= id1 || *bound_iter - parent_node->id_ > parent_node->id_ - *prev_iter) {
                    parent_node = opt_keyfrm_ids[*prev_iter];
                } else {
                    parent_node = opt_keyfrm_ids[*bound_iter];
                }
            }

            const auto id2 = parent_node->id_;
            if (id1 <= id2) {
                continue;
            }
            const ::g2o::Sim3& Sim3_2w = (parent_node->loop_BA_identifier_ == loop_identifier)
                                             ? ::g2o::Sim3(parent_node->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                                           parent_node->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                                             : map_Sim3s_cw[id2];

            // calculate pose tranform
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
            //  add constraint edge
            insert_edge(id1, id2, Sim3_21);
        }

        // add loop edge which are over weight
        const auto loop_edges = keyfrm->graph_node_->get_loop_edges();
        for (const auto& connected_keyfrm : loop_edges) {
            if (connected_keyfrm->will_be_erased()) continue;

            const auto id2 = connected_keyfrm->id_;
            if (id1 <= id2) {
                continue;
            }
            const ::g2o::Sim3& Sim3_2w =
                (connected_keyfrm->loop_BA_identifier_ == loop_identifier)
                    ? ::g2o::Sim3(connected_keyfrm->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                  connected_keyfrm->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                    : map_Sim3s_cw[id2];  //(iter2 != non_corrected_Sim3s.end()) ? iter2->second : map_Sim3s_cw[id2];

            // calculate pose tranform
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
            // constraint edgeを追加
            insert_edge(id1, id2, Sim3_21);
        }

        // add edge with covisibilities over threshold weight
        const auto connected_keyfrms = keyfrm->graph_node_->get_covisibilities_over_weight(min_weight);
        for (const auto& connected_keyfrm : connected_keyfrms) {
            // null check
            if (!connected_keyfrm || !parent_node) {
                continue;
            }
            if (*connected_keyfrm == *parent_node || keyfrm->graph_node_->has_spanning_child(connected_keyfrm)) {
                continue;
            }
            if (loop_edges.count(connected_keyfrm)) {
                continue;
            }
            if (connected_keyfrm->will_be_erased()) {
                continue;
            }
            const auto id2 = connected_keyfrm->id_;
            if (opt_keyfrm_ids.find(id1) == opt_keyfrm_ids.end() || opt_keyfrm_ids.find(id2) == opt_keyfrm_ids.end()) {
                continue;
            }
            if (id1 <= id2) {
                continue;
            }
            if (inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2)))) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w =
                (connected_keyfrm->loop_BA_identifier_ == loop_identifier)
                    ? ::g2o::Sim3(connected_keyfrm->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                  connected_keyfrm->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                    : map_Sim3s_cw[id2];  // (iter2 != non_corrected_Sim3s.end()) ? iter2->second : map_Sim3s_cw[id2];

            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
            insert_edge(id1, id2, Sim3_21);
        }

        // add window edge
        // example:
        // 0,2,4 ..... 5,3,1
        // 0-5,  2-3,  4-1
        assert(2 * edge_size_ * all_windows.size() == window_keyfrms.size());
        for (size_t idx = 0; idx < all_windows.size(); idx++) {
            for (size_t idy = 0; idy < edge_size_; idy++) {
                const auto keyfrm_start = window_keyfrms.at(2 * edge_size_ * idx + 2 * idy);
                const auto keyfrm_end = window_keyfrms.at(2 * edge_size_ * idx + 2 * edge_size_ - 2 * idy - 1);
                const auto id1 = keyfrm_start->id_;
                const auto id2 = keyfrm_end->id_;
                if (inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2)))) {
                    continue;
                }

                const ::g2o::Sim3 Sim3_w1 =
                    (keyfrm_start->loop_BA_identifier_ == loop_identifier)
                        ? ::g2o::Sim3(keyfrm_start->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                      keyfrm_start->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                              .inverse()
                        : map_Sim3s_cw[id1].inverse();

                const ::g2o::Sim3& Sim3_2w =
                    (keyfrm_end->loop_BA_identifier_ == loop_identifier)
                        ? ::g2o::Sim3(keyfrm_end->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                      keyfrm_end->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                        : map_Sim3s_cw[id2];

                // calculate pose transform
                const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
                // constraint edgeを追加
                assert(id2 > id1);
                insert_edge(id1, id2, Sim3_21);
            }
        }
    }

    curr_keyfrm->graph_node_->add_loop_edge(loop_keyfrm);
    loop_keyfrm->graph_node_->add_loop_edge(curr_keyfrm);

    // 5. pose graph optimization
    optimizer.initializeOptimization();
    optimizer.setVerbose(true);
    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        if (abort_graph_optimization_) {
            graph_optimization_is_running_ = false;
            abort_graph_optimization_ = false;
            return;
        }
    }
    optimizer.optimize(iteration_times);  // TODO: Find the proper iteration times

    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        if (abort_graph_optimization_) {
            graph_optimization_is_running_ = false;
            abort_graph_optimization_ = false;
            return;
        }
    }

    // 6. update pose result
    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
    std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[curr_keyfrm->get_map_id()]);
    {
        MapID merged_map_id = std::min(loop_keyfrm->get_map_id(), curr_keyfrm->get_map_id());
        std::unordered_map<unsigned int, ::g2o::Sim3> map_corrected_Sim3s_wc;

        // first update window keyframes
        for (size_t idx = 0; idx < all_windows.size(); idx++) {
            const auto opt_window = all_windows.at(idx);
            std::vector<::g2o::Sim3, Eigen::aligned_allocator<::g2o::Sim3>> window_sim3s;
            for (size_t idy = 0; idy < 2 * edge_size_; idy++) {
                const auto keyfrm = window_keyfrms.at(2 * edge_size_ * idx + idy);
                const auto id = keyfrm->id_;
                auto keyfrm_vtx = static_cast<g2o::sim3::shot_vertex*>(optimizer.vertex(keyframeID_to_vertexID(id)));
                const ::g2o::Sim3& corrected_Sim3_cw = keyfrm_vtx->estimate();
                map_corrected_Sim3s_wc[id] = corrected_Sim3_cw.inverse();
                window_sim3s.push_back(corrected_Sim3_cw);
            }
            opt_window->update_cam_pose_slerp(window_sim3s, map_corrected_Sim3s_wc, edge_size_, merged_map_id,
                                              loop_identifier);
        }

        // then update single keyfrms
        for (auto keyfrm : single_keyfrms) {
            const auto id = keyfrm->id_;
            auto keyfrm_vtx = static_cast<g2o::sim3::shot_vertex*>(optimizer.vertex(keyframeID_to_vertexID(id)));
            const ::g2o::Sim3& corrected_Sim3_cw = keyfrm_vtx->estimate();
            const float s = corrected_Sim3_cw.scale();
            const Mat33_t rot_cw = corrected_Sim3_cw.rotation().toRotationMatrix();
            const Vec3_t trans_cw = corrected_Sim3_cw.translation() / s;
            const Mat44_t cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);

            // keyfrm->set_cam_pose(cam_pose_cw);
            keyfrm->set_map_id(merged_map_id);
            keyfrm->cam_pose_cw_after_loop_BA_ = cam_pose_cw;
            map_corrected_Sim3s_wc[id] = corrected_Sim3_cw.inverse();
            keyfrm->cam_pose_cw_before_BA_ = keyfrm->get_cam_pose();
            keyfrm->loop_BA_identifier_ = loop_identifier;
        }

        // update the camera pose along the spanning tree from the origin
        std::list<data::keyframe*> keyfrms_to_check;
        auto origin_keyfrm_for_curr = map_db_->get_origin_keyframe(curr_keyfrm->get_map_id());
        auto origin_keyfrm_for_loop = map_db_->get_origin_keyframe(loop_keyfrm->get_map_id());
        if (origin_keyfrm_for_curr) keyfrms_to_check.emplace_back(origin_keyfrm_for_curr);
        if (origin_keyfrm_for_loop) keyfrms_to_check.emplace_back(origin_keyfrm_for_loop);
        spdlog::debug("original keyframes num {}", keyfrms_to_check.size());
        std::list<data::landmark*> all_landmarks;
        size_t propagated_frame_num = 0;
        while (!keyfrms_to_check.empty()) {
            auto parent = keyfrms_to_check.front();
            const Mat44_t cam_pose_wp = parent->get_cam_pose_inv();
            const auto children = parent->graph_node_->get_spanning_children();
            for (auto& child : children) {
                if (child->loop_BA_identifier_ != loop_identifier) {
                    // if `child` is NOT optimized by the loop BA
                    // propagate the pose correction from the spanning parent

                    // parent->child
                    const Mat44_t cam_pose_cp = child->get_cam_pose() * cam_pose_wp;
                    // world->child AFTER correction = parent->child * world->parent AFTER correction
                    child->cam_pose_cw_after_loop_BA_ = cam_pose_cp * parent->cam_pose_cw_after_loop_BA_;
                    // check as `child` has been corrected
                    child->loop_BA_identifier_ = loop_identifier;

                    propagated_frame_num++;

                    child->cam_pose_cw_before_BA_ = child->get_cam_pose();
                }
                // need updating
                keyfrms_to_check.push_back(child);
            }

            // temporally store the camera pose BEFORE correction (for correction of landmark positions)

            parent->in_cur_covisibility_window_ = false;

            // update the camera pose
            parent->set_cam_pose(parent->cam_pose_cw_after_loop_BA_);

            parent->set_map_id(merged_map_id);

            // finish updating
            keyfrms_to_check.pop_front();

            auto lms = parent->get_landmarks();
            for (auto lm : lms) {
                if (lm && !lm->will_be_erased() && lm->loop_BA_identifier_ != loop_identifier) {
                    lm->loop_BA_identifier_ = loop_identifier;
                    all_landmarks.push_back(lm);
                }
            }
        }

        spdlog::debug("Propagated_keyframe_num: {}", propagated_frame_num);

        // update the positions of the landmarks
        for (auto lm : all_landmarks) {
            if (!lm) {
                std::cout << "No such landmark!" << std::endl;
                continue;
            }

            if (lm->will_be_erased()) {
                continue;
            }

            if (!lm->get_ref_keyframe()) {
                std::cerr << "No ref key_frame for this landmark" << std::endl;
            }

            // correct the position according to the move of the camera pose of the reference keyframe
            auto ref_keyfrm = lm->get_ref_keyframe();

            assert(ref_keyfrm);

            if (ref_keyfrm->loop_BA_identifier_ != loop_identifier) {
                spdlog::debug("Invalid landmark {} and ref_keyfrm {}", lm->id_, ref_keyfrm->id_);
                continue;
            }

            assert(ref_keyfrm->loop_BA_identifier_ == loop_identifier);

            // convert the position to the camera-reference using the camera pose BEFORE the correction
            const Mat33_t rot_cw_before_BA = ref_keyfrm->cam_pose_cw_before_BA_.block<3, 3>(0, 0);
            const Vec3_t trans_cw_before_BA = ref_keyfrm->cam_pose_cw_before_BA_.block<3, 1>(0, 3);
            const Vec3_t pos_c = rot_cw_before_BA * lm->get_pos_in_world() + trans_cw_before_BA;

            // convert the position to the world-reference using the camera pose AFTER the correction
            const Mat44_t cam_pose_wc = ref_keyfrm->get_cam_pose_inv();
            const Mat33_t rot_wc = cam_pose_wc.block<3, 3>(0, 0);
            const Vec3_t trans_wc = cam_pose_wc.block<3, 1>(0, 3);
            lm->set_pos_in_world(rot_wc * pos_c + trans_wc);
            lm->update_normal_and_depth();
            lm->set_map_id(merged_map_id);
        }
    }
    server_->post_process_after_loop(loop_keyfrm->client_id_, curr_keyfrm->client_id_, loop_keyfrm->get_map_id(),
                                     curr_keyfrm->get_map_id());
    std::lock_guard<std::mutex> lock_thread(mtx_thread_);
    abort_graph_optimization_ = false;
    //ros::Time end_time = ros::Time::now();
    auto end_time = now();
    loop_connections.clear();
    spdlog::debug("Correct loop optimization costs time {} s",  duration_ms(end_time - start_time));
    graph_optimization_is_running_ = false;
}

void window_graph_optimizer::classify_keyframes(const std::map<KeyframeID, data::keyframe*>& all_keyframes,
                                                std::vector<data::keyframe*>& single_keyframes,
                                                std::vector<data::keyframe*>& window_keyframes,
                                                std::vector<data::window*>& all_windows,
                                                std::unordered_map<KeyframeID, data::keyframe*>& opt_keyfrm_ids)
{
    curr_window_ptr_ = new data::window(0);
    all_windows.push_back(curr_window_ptr_);
    find_edge_ = false;
    current_window_id_ = 0;
    edge_number_ = 0;
    int kf_count = 0;

    for (const auto& id_kf : all_keyframes) {
        kf_count++;
        unsigned int id = id_kf.first;
        current_kf_ = id_kf.second;
        if (!current_kf_) {
            std::cout << "No such keyframe, id: " << id << std::endl;
            continue;
        }

        if (find_edge_) {
            bool not_validate = judge_window(kf_count);
            velocity_vector_.erase(velocity_vector_.begin());
            single_keyframes.push_back(current_kf_);
            opt_keyfrm_ids[current_kf_->id_] = current_kf_;
            last_kf_ = current_kf_;
            if (!not_validate) {
                edge_number_++;
                // If don’t need a new window for a few consecutive frames.
                // it is considered stable, then create the next window
                if (edge_number_ >= error_window_size_) {
                    current_window_id_++;
                    curr_window_ptr_ = new data::window(current_window_id_);
                    all_windows.push_back(curr_window_ptr_);
                    reproject_error_vector_.clear();
                    find_edge_ = false;
                    last_kf_ = nullptr;
                }
            } else {
                edge_number_ = 0;
            }
        } else {
            if (judge_window(kf_count)) {
                finished_current_window(single_keyframes, all_windows, window_keyframes, opt_keyfrm_ids);
            } else {
                curr_window_ptr_->insert_keyframe(current_kf_);
            }
            last_kf_ = current_kf_;
        }
    }
}

bool window_graph_optimizer::judge_window(int kf_count)
{
    bool need_create_window = false;
    const Mat33_t rot_cw = current_kf_->get_cam_pose().block<3, 3>(0, 0);
    const Vec3_t trans_cw = current_kf_->get_cam_pose().block<3, 1>(0, 3);
    const auto landmarks = current_kf_->get_landmarks();

    float reproj_error_sum = 0;
    int reporoj_num = 0;
    for (size_t idx = 0; idx < landmarks.size(); idx++) {
        const auto landmark = landmarks.at(idx);
        if (!landmark || landmark->get_ref_keyframe()->id_ + interval_threshold_ > current_kf_->id_) {
            continue;
        }
        // only calculate the error of the landmark which was construct before current_kf_
        Vec3_t landmark_pos = landmark->get_pos_in_world();
        Vec2_t reproj;
        float x_right;
        current_kf_->camera_->reproject_to_image(rot_cw, trans_cw, landmark_pos, reproj, x_right);
        Vec2_t kpt_loc(current_kf_->keypts_.at(idx).pt.x, current_kf_->keypts_.at(idx).pt.y);
        reproj_error_sum += (reproj - kpt_loc).norm();
        reporoj_num++;
    }

    // Step 1: judge reproject error
    // TODO_TYX: number and reproject average evaluate together
    // if there are no covisibilities before an interval threhold, we need to create a new window
    if (kf_count > (int)interval_threshold_) {
        if (reporoj_num == 0) {
            need_create_window = true;
        } else {
            reproject_error_vector_.push_back(reproj_error_sum / reporoj_num);
            // if reproject error over a threshold, create new window
            // only over a window size, calculate reproject error
            if (reproject_error_vector_.size() >= error_window_size_) {
                float reproject_error_average =
                    std::accumulate(reproject_error_vector_.begin(), reproject_error_vector_.end(), 0.0) /
                    reproject_error_vector_.size();
                // std::cout<<"reproject_error "<<reproject_error_average<<std::endl;
                reproject_error_vector_.erase(reproject_error_vector_.begin());
                if (reproject_error_average > reproj_threshold_) {
                    need_create_window = true;
                }
            }
        }
    }
    // Step 2: judge velocity error
    // calculate the velocity of the keyframe with last keyframe
    if (last_kf_) {
        const Mat44_t velocity_now = current_kf_->get_cam_pose() * last_kf_->get_cam_pose_inv();
        velocity_vector_.push_back(velocity_now);
        const Mat44_t aver_velocity = calcualte_median_velocity();
        Vec7_t aver_vec = ::g2o::Sim3(aver_velocity.block<3, 3>(0, 0), Vec3_t(0, 0, 0), 1).log();
        Vec7_t curr_vec = ::g2o::Sim3(velocity_now.block<3, 3>(0, 0), Vec3_t(0, 0, 0), 1).log();
        Vec7_t distance_vec = ::g2o::Sim3(velocity_now.block<3, 3>(0, 0), velocity_now.block<3, 1>(0, 3), 1).log();
        current_kf_->window_distance_ = last_kf_->window_distance_ + distance_vec.norm();

        float veloctity_error = (curr_vec - aver_vec).norm();
        // std::cout<<"veloctity_error "<<veloctity_error<<std::endl;
        if (veloctity_error > veloctity_error_threshold_) {
            need_create_window = true;
        }
    }

    return need_create_window;
}

void window_graph_optimizer::finished_current_window(std::vector<data::keyframe*>& single_keyframes,
                                                     std::vector<data::window*>& all_windows,
                                                     std::vector<data::keyframe*>& window_keyframes,
                                                     std::unordered_map<KeyframeID, data::keyframe*>& opt_keyfrm_ids)
{
    edge_number_ = 0;
    if (curr_window_ptr_->get_window_size() >= 2 * edge_size_ + error_window_size_) {
        find_edge_ = true;
        for (size_t iter = 0; iter < error_window_size_ - 1; iter++) {
            auto final_kf = curr_window_ptr_->get_final_kefrm();
            single_keyframes.push_back(final_kf);
            opt_keyfrm_ids[final_kf->id_] = final_kf;
            curr_window_ptr_->erase_final_kefrm();
        }
        std::vector<Mat44_t, Eigen::aligned_allocator<Mat44_t>> velocity_vector_copy(velocity_vector_);
        velocity_vector_.clear();
        for (size_t idx = velocity_vector_copy.size() - error_window_size_; idx < velocity_vector_copy.size(); idx++) {
            velocity_vector_.push_back(velocity_vector_copy.at(idx));
        }
        single_keyframes.push_back(current_kf_);
        opt_keyfrm_ids[current_kf_->id_] = current_kf_;
        curr_window_ptr_->get_opt_keframes(window_keyframes, opt_keyfrm_ids, edge_size_);
        // get window keyframes
    } else {
        find_edge_ = true;
        size_t kf_number = curr_window_ptr_->get_window_size();
        for (size_t iter = 0; iter < kf_number; iter++) {
            auto final_kf = curr_window_ptr_->get_final_kefrm();
            single_keyframes.push_back(final_kf);
            opt_keyfrm_ids[final_kf->id_] = final_kf;
            curr_window_ptr_->erase_final_kefrm();
        }
        // delete this window
        all_windows.pop_back();
        delete curr_window_ptr_;
        single_keyframes.push_back(current_kf_);
        opt_keyfrm_ids[current_kf_->id_] = current_kf_;
    }
}

Mat44_t window_graph_optimizer::calcualte_median_velocity()
{
    Vec3_t trans_average(0, 0, 0);
    Mat44_t quat_sum(Mat44_t::Zero(4, 4));
    for (const auto& velocity : velocity_vector_) {
        const Quat_t quat(velocity.block<3, 3>(0, 0));
        const Vec4_t quat_vec(quat.x(), quat.y(), quat.z(), quat.w());
        trans_average += velocity.block<3, 1>(0, 3);
        quat_sum += quat_vec * quat_vec.transpose();
    }
    trans_average = trans_average / velocity_vector_.size();

    Eigen::EigenSolver<Mat44_t> es(quat_sum);
    MatX_t evecs = es.eigenvectors().real();
    MatX_t evals = es.eigenvalues().real();
    MatX_t::Index evalsMax;
    evals.rowwise().sum().maxCoeff(&evalsMax);
    Quat_t quat_average(evecs.block<4, 1>(0, evalsMax));
    Mat44_t aver_velocity = Mat44_t::Identity();
    aver_velocity.block<3, 3>(0, 0) = quat_average.normalized().toRotationMatrix();
    aver_velocity.block<3, 1>(0, 3) = trans_average;
    return aver_velocity;
}

}  // namespace optimize
}  // namespace openvslam
