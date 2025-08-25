// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "server/server.h"
#include "optimize/g2o/sim3/shot_vertex.h"
#include "optimize/g2o/sim3/graph_opt_edge.h"
#include "optimize/g2o/se3/shot_vertex.h"

#include "util/converter.h"
#include "timing.h"

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
#include "optimize/multi_camera_edge.h"
#include "server/univloc_graph_optimizer.h"

namespace openvslam {
namespace optimize {

univloc_graph_optimizer::univloc_graph_optimizer(data::map_database* map_db, const bool fix_scale, univloc_server::Server* server)
    : graph_optimizer(map_db, fix_scale), optimization_type_(Loop_Optimization), server_(server)
{
}

bool univloc_graph_optimizer::slerp_pose_between_keyframes(data::keyframe* kf, double time, Mat44_t& T_interp) const
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
        auto id = kf->id_;
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
        auto id = kf->id_;
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
    assert(time2 <= time && time <= time3);

    double ratio = (time - time2) / (time3 - time2);

    auto q_interp = q2.slerp(ratio, q3).normalized();

    Eigen::Vector3d t_interp(ratio * t3[0] + (1.0 - ratio) * t2[0], ratio * t3[1] + (1.0 - ratio) * t2[1],
                             ratio * t3[2] + (1.0 - ratio) * t2[2]);

    T_interp = Mat44_t::Identity();

    T_interp.block(0, 3, 3, 1) = t_interp;

    T_interp.block(0, 0, 3, 3) = q_interp.matrix();

    return true;
}

void univloc_graph_optimizer::abort_graph_optimizaion()
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

bool univloc_graph_optimizer::is_running()
{
    std::lock_guard<std::mutex> lock(mtx_thread_);
    return graph_optimization_is_running_;
}

ClientID univloc_graph_optimizer::get_keyframe_id() { return client_id_; }

void univloc_graph_optimizer::optimize_involved(data::keyframe* cur_keyframe, data::keyframe* constraint_keyframe,
                                        int iteration_times, bool post_process)
{
    spdlog::debug("Start correct front and rear camera constraints!");
    optimization_type_ = Front_Rear_Optimization;
    //ros::Time start_time = ros::Time::now();
    auto start_time = now();
    map_id_ = cur_keyframe->get_map_id();
    assert(cur_keyframe->get_map_id() == constraint_keyframe->get_map_id());
    client_id_ = std::min(cur_keyframe->client_id_, constraint_keyframe->client_id_);

    std::vector<data::keyframe*> involved_keyfrms;

    data::keyframe *origin_keyframe1, *origin_keyframe2;

    // TODO: select the proper keyframe to be fixed
    data::keyframe* tmp_keyframe = cur_keyframe;

    while (1) {
        assert(tmp_keyframe);
        data::keyframe* parent = tmp_keyframe->graph_node_->get_spanning_parent();
        if (tmp_keyframe->is_origin() || !parent) {
            origin_keyframe1 = tmp_keyframe;
            spdlog::debug("Get origin keyframe: {}", origin_keyframe1->id_);
            break;
        }
        tmp_keyframe = parent;
    }

    std::list<data::keyframe*> keyframe_to_check;
    keyframe_to_check.push_back(origin_keyframe1);
    while (!keyframe_to_check.empty()) {
        tmp_keyframe = keyframe_to_check.front();
        involved_keyfrms.push_back(tmp_keyframe);
        keyframe_to_check.pop_front();
        auto children = tmp_keyframe->graph_node_->get_spanning_children();
        for (const auto& child : children) keyframe_to_check.push_back(child);
    }

    tmp_keyframe = constraint_keyframe;

    while (1) {
        assert(tmp_keyframe);
        data::keyframe* parent = tmp_keyframe->graph_node_->get_spanning_parent();
        if (tmp_keyframe->is_origin() || !parent) {
            origin_keyframe2 = tmp_keyframe;
            spdlog::debug("Get origin keyframe: {}", origin_keyframe2->id_);
            break;
        }
        tmp_keyframe = parent;
    }

    keyframe_to_check.push_back(origin_keyframe2);
    while (!keyframe_to_check.empty()) {
        tmp_keyframe = keyframe_to_check.front();
        involved_keyfrms.push_back(tmp_keyframe);
        keyframe_to_check.pop_front();
        auto children = tmp_keyframe->graph_node_->get_spanning_children();
        for (const auto& child : children) keyframe_to_check.push_back(child);
    }

    data::keyframe* fixed_keyfrm = nullptr;
    /* ------The princeple of setting the fixed keyframe during optimization------
      1, If only one client starts a new session map, then the origin keyframe of another client map should be fixed;
      2, Else, the earlier created origin keyframe of the two clients should be set fixed!
    */

    if (post_process) {
        if (origin_keyframe1->id_ == server_->get_client_origin_keyframe(cur_keyframe->client_id_)->id_) {
            server_->record_mapid_before_optimization(cur_keyframe);
        } else {
            fixed_keyfrm = origin_keyframe2;
        }
        if (origin_keyframe2->id_ == server_->get_client_origin_keyframe(constraint_keyframe->client_id_)->id_) {
            server_->record_mapid_before_optimization(constraint_keyframe);
        } else {
            if (!fixed_keyfrm)
                fixed_keyfrm = origin_keyframe1;
            else {
                fixed_keyfrm =
                    origin_keyframe1->timestamp_ < origin_keyframe2->timestamp_ ? origin_keyframe1 : origin_keyframe2;
            }
        }
    }

    if (!fixed_keyfrm)
        fixed_keyfrm =
            origin_keyframe1->timestamp_ < origin_keyframe2->timestamp_ ? origin_keyframe1 : origin_keyframe2;

    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        graph_optimization_is_running_ = true;
        abort_graph_optimization_ = false;
    }
    // 1. declare optimizer
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_7_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_7_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));
    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);
    optimizer.setForceStopFlag(&abort_graph_optimization_);

    // 2 finding involved landmarks
    std::unordered_map<KeyframeID, ::g2o::Sim3> map_Sim3s_cw;
    std::unordered_map<KeyframeID, g2o::sim3::shot_vertex*> map_vertices;
    std::unordered_map<KeyframeID, g2o::sim3::shot_vertex*> front_rear_camera_constraint_vertices;

    // constexpr int min_weight = 100;  // Hype parameters, need to adjust
    KeyframeID max_kfm_id = 0;
    spdlog::debug("Start adding involved_keyfrms vertexes {}", involved_keyfrms.size());

    for (const auto keyfrm : involved_keyfrms) {
        auto keyfrm_vtx = new g2o::sim3::shot_vertex();

        const auto id = keyfrm->id_;

        max_kfm_id = std::max(max_kfm_id, id);

        // 姿勢が修正されていない場合はkeyframeの姿勢をSim3に変換してセットする
        const Mat33_t rot_cw = keyfrm->get_rotation();
        const Vec3_t trans_cw = keyfrm->get_translation();
        const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);

        map_Sim3s_cw[id] = Sim3_cw;
        keyfrm_vtx->setEstimate(Sim3_cw);

        keyfrm_vtx->setFixed(fixed_keyfrm->id_ == keyfrm->id_);

        keyfrm_vtx->setId(keyframeID_to_vertexID(id));
        keyfrm_vtx->fix_scale_ = fix_scale_;

        optimizer.addVertex(keyfrm_vtx);
        map_vertices[id] = keyfrm_vtx;
    }

    max_kfm_id++;

    spdlog::debug("Finished adding involved_keyfrms vertexes");

    auto all_multi_camera_constraints = map_db_->get_all_multicamera_constraints();
    for (const auto& multi_camera_constraint : all_multi_camera_constraints) {  // use sim3 or se3 parameters
        const int id = multi_camera_constraint.first;
        auto front_rear_camera_constraint_vtx = new g2o::sim3::shot_vertex();
        auto r = multi_camera_constraint.second.matrix().block(0, 0, 3, 3),
             t = multi_camera_constraint.second.matrix().block(0, 3, 3, 1);
        const ::g2o::Sim3 initial_value(r, t, 1.0);
        front_rear_camera_constraint_vtx->setEstimate(initial_value);
        front_rear_camera_constraint_vtx->fix_scale_ = fix_scale_;
        front_rear_camera_constraint_vtx->setFixed(true);
        front_rear_camera_constraint_vtx->setId(keyframeID_to_vertexID(id + max_kfm_id));  // max_kfm_id as the id offset
        optimizer.addVertex(front_rear_camera_constraint_vtx);
        front_rear_camera_constraint_vertices[id] = front_rear_camera_constraint_vtx;
    }

    // 3. edgeを追加

    // どのkeyframe間にedgeが追加されたかを保存しておく
    std::set<std::pair<KeyframeID, KeyframeID>> inserted_edge_pairs;

    // constraint edgeを追加する関数
    const auto insert_edge = [&optimizer, &map_vertices, &inserted_edge_pairs](KeyframeID id1, KeyframeID id2,
                                                                               const ::g2o::Sim3& Sim3_21) {
        auto edge = new g2o::sim3::graph_opt_edge();
        edge->setVertex(0, map_vertices[id1]);
        edge->setVertex(1, map_vertices[id2]);
        edge->setMeasurement(Sim3_21);

        edge->information() = MatRC_t<7, 7>::Identity();

        optimizer.addEdge(edge);
        inserted_edge_pairs.insert(std::make_pair(std::min(id1, id2), std::max(id1, id2)));
    };

    const auto insert_multi_camera_edge = [&optimizer, &map_vertices, &front_rear_camera_constraint_vertices](
                                              KeyframeID id1, KeyframeID id2, int id3,
                                              const Mat44_t& T_pose) {
        auto edge = new g2o::EdgeMultiCamera();

        // if id1 and id2 are not in the same map, the constraint has no impact
        if (!map_vertices.count(id1)) {
            spdlog::debug("No such map_vertices id1 {} front and rear camera constraint! ", id1);
            return;
        }
        edge->setVertex(0, map_vertices[id1]);
        if (!map_vertices.count(id2)) {
            spdlog::debug("No such map_vertices id2 {} front and rear camera constraint!", id2);
            return;
        }
        edge->setVertex(1, map_vertices[id2]);
        if (!front_rear_camera_constraint_vertices.count(id3)) {
            spdlog::debug("No such front_rear_camera_constraint_vertices front and rear camera constraint!");
            return;
        }
        edge->setVertex(2, front_rear_camera_constraint_vertices[id3]);

        ::g2o::Sim3 I_sim3(T_pose.block(0, 0, 3, 3), T_pose.block(0, 3, 3, 1), 1.0);

        edge->setMeasurement(I_sim3);

        edge->information() = MatRC_t<7, 7>::Identity();

        if (edge->numUndefinedVertices()) spdlog::debug("Invalid edge front and rear camera constraint!");

        optimizer.addEdge(edge);
    };

    spdlog::debug("Add involved_keyfrms edges!");
    for (const auto keyfrm : involved_keyfrms) {
        // 片方のkeyframeの姿勢を取り出す
        const auto id1 = keyfrm->id_;

        // const ::g2o::Sim3 Sim3_w1 = ((iter1 != non_corrected_Sim3s.end()) ? iter1->second :
        // Sim3s_cw.at(id1)).inverse();
        const ::g2o::Sim3 Sim3_w1 = map_Sim3s_cw[id1].inverse();

        const auto parent_node = keyfrm->graph_node_->get_spanning_parent();

        if (parent_node) {
            if (parent_node->will_be_erased()) continue;
            const auto id2 = parent_node->id_;

            if (id1 <= id2) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w = map_Sim3s_cw[id2];

            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            insert_edge(id1, id2, Sim3_21);
        }

        const auto loop_edges = keyfrm->graph_node_->get_loop_edges();
        for (const auto& connected_keyfrm : loop_edges) {
            if (connected_keyfrm->will_be_erased()) continue;
            const auto id2 = connected_keyfrm->id_;

            if (id1 <= id2) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w = map_Sim3s_cw[id2];

            // 相対姿勢を計算
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            // constraint edgeを追加
            insert_edge(id1, id2, Sim3_21);
        }

        // threshold weight以上のcovisibilitiesを追加する
        /*const auto connected_keyfrms = keyfrm->graph_node_->get_covisibilities_over_weight(min_weight);
        for (const auto connected_keyfrm : connected_keyfrms) {
            // null check
            if (!connected_keyfrm || !parent_node) {
                continue;
            }
            // parent-childのedgeはすでに追加しているので除外
            if (*connected_keyfrm == *parent_node || keyfrm->graph_node_->has_spanning_child(connected_keyfrm)) {
                continue;
            }
            // loop対応している場合はすでに追加しているので除外
            if (static_cast<bool>(loop_edges.count(connected_keyfrm))) {
                continue;
            }

            if (connected_keyfrm->will_be_erased()) {
                continue;
            }

            const auto id2 = connected_keyfrm->id_;

            if (id1 <= id2) {
                continue;
            }
            if (static_cast<bool>(inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2))))) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w = map_Sim3s_cw[id2];

            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            insert_edge(id1, id2, Sim3_21);
        }*/

        // Add multi camera constraint
        if (keyfrm->graph_node_->has_front_rear_camera_constraint()) {
            const auto multi_camera_constraint = keyfrm->graph_node_->get_front_rear_camera_constraint();
            const auto constraint_id = multi_camera_constraint.first;
            const auto id2 = multi_camera_constraint.second->id_;
            // The transform is from smaller id client to bigger id client
            if (keyfrm->client_id_ > multi_camera_constraint.second->client_id_) continue;
            if (multi_camera_constraint.second->will_be_erased()) continue;

            double time2 = multi_camera_constraint.second->timestamp_;
            Mat44_t slerp_pose;
            if (!slerp_pose_between_keyframes(keyfrm, time2, slerp_pose)) {
                spdlog::debug("Invalid slerping");
                continue;
            }
            /*  -----------------Figure of Virtual keyframe-----------------
                ---------keyfrm-------virtual keyfrm----------next keyfrm---------
                              -pose_c_v-
                ------------------multi_camera_constraint keyfrm------------------
            */

            Mat44_t pose_c_v = keyfrm->get_cam_pose() * slerp_pose;  // Relative pose from keyframe to virtual keyframe
            insert_multi_camera_edge(id1, id2, constraint_id, pose_c_v);
        }
    }

    // 4. pose graph optimizationを走らせる
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

    spdlog::debug("Start optimizing invloved objects now");
    optimizer.optimize(iteration_times);  // TODO: Find the proper iteration times
    spdlog::debug("End optimizing invloved objects now");

    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        if (abort_graph_optimization_) {
            graph_optimization_is_running_ = false;
            abort_graph_optimization_ = false;
            return;
        }
    }

    std::lock_guard<std::mutex> lock1(data::map_database::mtx_client_map_database_[std::make_pair(
        cur_keyframe->client_id_, cur_keyframe->get_map_id())]);
    std::lock_guard<std::mutex> lock2(data::map_database::mtx_client_map_database_[std::make_pair(
        constraint_keyframe->client_id_, constraint_keyframe->get_map_id())]);
    {
        KeyframeID loop_identifier = involved_keyfrms[0]->id_;
        std::unordered_map<KeyframeID, ::g2o::Sim3> map_corrected_Sim3s_wc;

        for (auto keyfrm : involved_keyfrms) {
            if (!keyfrm) {
                continue;
            }
            if (keyfrm->will_be_erased()) continue;

            const auto id = keyfrm->id_;

            auto keyfrm_vtx = static_cast<g2o::sim3::shot_vertex*>(optimizer.vertex(keyframeID_to_vertexID(id)));

            const ::g2o::Sim3& corrected_Sim3_cw = keyfrm_vtx->estimate();
            const float s = corrected_Sim3_cw.scale();
            const Mat33_t rot_cw = corrected_Sim3_cw.rotation().toRotationMatrix();
            const Vec3_t trans_cw = corrected_Sim3_cw.translation() / s;

            const Mat44_t cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);
            keyfrm->cam_pose_cw_after_loop_BA_ = cam_pose_cw;
            keyfrm->loop_BA_identifier_ = loop_identifier;
        }

        std::list<data::keyframe*> keyfrms_to_check;
        keyfrms_to_check.push_back(origin_keyframe1);
        keyfrms_to_check.push_back(origin_keyframe2);
        spdlog::debug("origin_keyframe1 id: {}", origin_keyframe1->id_);
        spdlog::debug("origin_keyframe2 id: {}", origin_keyframe2->id_);

        std::list<data::landmark*> involved_landmarks;
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

                    spdlog::debug("propagated_frame: {}", child->id_);

                    propagated_frame_num++;
                }
                // need updating
                keyfrms_to_check.push_back(child);
            }

            // temporally store the camera pose BEFORE correction (for correction of landmark positions)
            parent->cam_pose_cw_before_BA_ = parent->get_cam_pose();

            // update the camera pose
            parent->set_cam_pose(parent->cam_pose_cw_after_loop_BA_);

            parent->loop_BA_identifier_ = loop_identifier;

            auto lms = parent->get_landmarks();
            for (auto lm : lms) {
                if (lm && !lm->will_be_erased() && lm->loop_BA_identifier_ != loop_identifier) {
                    lm->loop_BA_identifier_ = loop_identifier;
                    involved_landmarks.push_back(lm);
                }
            }

            // finish updating
            keyfrms_to_check.pop_front();
        }

        spdlog::debug("Propagated_keyframe_num: {}", propagated_frame_num);

        for (auto& lm : involved_landmarks) {
            auto ref_keyfrm = lm->get_ref_keyframe();
            assert(ref_keyfrm);
            if (ref_keyfrm->loop_BA_identifier_ != loop_identifier) {
                spdlog::debug("Invalid ref keyframe: {}, ref keyframe loop_identifier {}, current loop_identifire {}",
                              ref_keyfrm->id_, ref_keyfrm->loop_BA_identifier_, loop_identifier);
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
        }
    }

    if (post_process) {
        spdlog::debug("post process after correct front rear camera constraints");
        if (origin_keyframe1->id_ == server_->get_client_origin_keyframe(cur_keyframe->client_id_)->id_)
            server_->post_process_after_loop(cur_keyframe->client_id_, cur_keyframe->client_id_);
        if (origin_keyframe2->id_ == server_->get_client_origin_keyframe(constraint_keyframe->client_id_)->id_)
            server_->post_process_after_loop(constraint_keyframe->client_id_, constraint_keyframe->client_id_);
    }

    std::lock_guard<std::mutex> lock_thread(mtx_thread_);
    abort_graph_optimization_ = false;
    graph_optimization_is_running_ = false;

    //ros::Time end_time = ros::Time::now();
    auto end_time = now();
    spdlog::debug("Correct front and rear camera constraint optimization costs time {} s",
                  duration_ms(end_time - start_time));

    spdlog::debug("optimize involved keyframes costs time {} s for {} edges", duration_ms(end_time - start_time),
                  optimizer.activeEdges().size());
}

void univloc_graph_optimizer::optimize(data::keyframe* loop_keyfrm, data::keyframe* curr_keyfrm,
                               std::map<data::keyframe*, std::set<data::keyframe*>>& loop_connections,
                               std::vector<data::keyframe*>& unused_nerbors,
                               pair_keyframe_pose_vec loop_connections_with_pose, int iteration_times)
{
    spdlog::debug("Start correct loop!");
    unsigned int loop_edge = 0, child_parent_edge = 0, front_rear_camera_edge = 0;
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
    // 2. add vertex

    const auto all_keyfrms = map_db_->get_all_keyframes(loop_keyfrm->get_map_id(), curr_keyfrm->get_map_id());
    auto all_multi_camera_constraints = map_db_->get_all_multicamera_constraints();

    std::unordered_map<KeyframeID, ::g2o::Sim3> map_Sim3s_cw;

    std::unordered_map<KeyframeID, g2o::sim3::shot_vertex*> map_vertices;

    std::unordered_map<KeyframeID, g2o::sim3::shot_vertex*> front_rear_camera_constraint_vertices;

    constexpr int loop_min_weight = 20;  // Hype parameters, need to adjust min_weight = 100,

    KeyframeID max_kfm_id = 0;
    for (auto keyfrm : all_keyfrms) {
        if (!keyfrm) {
            continue;
        }
        if (keyfrm->will_be_erased()) {
            continue;
        }
        auto keyfrm_vtx = new g2o::sim3::shot_vertex();

        const auto id = keyfrm->id_;

        max_kfm_id = std::max(max_kfm_id, id);

        // 最適化前に姿勢が修正されているかをチェック
        /*const auto iter = pre_corrected_Sim3s.find(keyfrm);
        if (iter != pre_corrected_Sim3s.end()) {
            // 最適化前に姿勢を修正済みの場合はその姿勢を取り出してvertexにセットする
            // Sim3s_cw.at(id) = iter->second; //Shoule be modified for multi slam
            map_Sim3s_cw[id] = iter->second;
            keyfrm_vtx->setEstimate(iter->second);
        }
        else*/
        if (keyfrm->loop_BA_identifier_ == loop_identifier) {
            const Mat33_t rot_cw = keyfrm->cam_pose_cw_after_loop_BA_.block(0, 0, 3, 3);
            const Vec3_t trans_cw = keyfrm->cam_pose_cw_after_loop_BA_.block(0, 3, 3, 1);
            const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);
            // Sim3s_cw.at(id) = Sim3_cw;
            map_Sim3s_cw[id] = Sim3_cw;
            keyfrm_vtx->setEstimate(Sim3_cw);
        }

        else {
            const Mat33_t rot_cw = keyfrm->get_rotation();
            const Vec3_t trans_cw = keyfrm->get_translation();
            const ::g2o::Sim3 Sim3_cw(rot_cw, trans_cw, 1.0);

            // Sim3s_cw.at(id) = Sim3_cw;
            map_Sim3s_cw[id] = Sim3_cw;
            keyfrm_vtx->setEstimate(Sim3_cw);
        }

        // ループの起点になった点はfixしておく
        keyfrm_vtx->setFixed(keyfrm->id_ == fixed_keyframe_id);

        /*if (*keyfrm == *loop_keyfrm) {
            keyfrm_vtx->setFixed(true);
            spdlog::debug("Set loop_keyfrm to be fixed: {}", loop_keyfrm->id_);
        }*/
        // Set the map origin frame to be fiexed
        // if (keyfrm->id_ == fixed_keyframe_id) {
        //    spdlog::debug("Set fixed keyframe: {}", keyfrm->id_);
        //}

        // vertexをoptimizerにセット
        keyfrm_vtx->setId(keyframeID_to_vertexID(id));
        keyfrm_vtx->fix_scale_ = fix_scale_;

        optimizer.addVertex(keyfrm_vtx);
        // vertices.at(id) = keyfrm_vtx;
        map_vertices[id] = keyfrm_vtx;
    }

    /*if (!set_fixed_frame)
        map_vertices[loop_keyfrm->id_]->setFixed(true);*/
    max_kfm_id++;
    for (const auto& multi_camera_constraint : all_multi_camera_constraints) {  // use sim3 or se3 parameters
        const int id = multi_camera_constraint.first;
        auto front_rear_camera_constraint_vtx = new g2o::sim3::shot_vertex();
        auto r = multi_camera_constraint.second.matrix().block(0, 0, 3, 3),
             t = multi_camera_constraint.second.matrix().block(0, 3, 3, 1);
        const ::g2o::Sim3 initial_value(r, t, 1.0);
        front_rear_camera_constraint_vtx->setEstimate(initial_value);
        front_rear_camera_constraint_vtx->fix_scale_ = fix_scale_;
        front_rear_camera_constraint_vtx->setFixed(true);
        front_rear_camera_constraint_vtx->setId(keyframeID_to_vertexID(id + max_kfm_id));  // max_kfm_id as the id offset
        optimizer.addVertex(front_rear_camera_constraint_vtx);
        front_rear_camera_constraint_vertices[id] = front_rear_camera_constraint_vtx;
    }

    // 3. edgeを追加

    // どのkeyframe間にedgeが追加されたかを保存しておく
    std::set<std::pair<KeyframeID, KeyframeID>> inserted_edge_pairs;

    // constraint edgeを追加する関数
    const auto insert_edge = [&optimizer, &map_vertices, &inserted_edge_pairs](KeyframeID id1, KeyframeID id2,
                                                                               const ::g2o::Sim3& Sim3_21) {
        if (static_cast<bool>(inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2)))))
            return;
        auto edge = new g2o::sim3::graph_opt_edge();
        edge->setVertex(0, map_vertices[id1]);
        edge->setVertex(1, map_vertices[id2]);
        edge->setMeasurement(Sim3_21);

        edge->information() = MatRC_t<7, 7>::Identity();

        optimizer.addEdge(edge);
        inserted_edge_pairs.insert(std::make_pair(std::min(id1, id2), std::max(id1, id2)));
    };

    const auto insert_multi_camera_edge = [&optimizer, &map_vertices, &front_rear_camera_constraint_vertices](
                                              KeyframeID id1, KeyframeID id2, int id3,
                                              const Mat44_t T_pose) {
        auto edge = new g2o::EdgeMultiCamera();

        // if id1 and id2 are not in the same map, the constraint has no impact
        if (!map_vertices.count(id1)) spdlog::debug("No such map_vertices id1 {}!", id1);
        edge->setVertex(0, map_vertices[id1]);
        if (!map_vertices.count(id2)) spdlog::debug("No such map_vertices id2 {}!", id2);
        edge->setVertex(1, map_vertices[id2]);
        if (!front_rear_camera_constraint_vertices.count(id3))
            spdlog::debug("No such front_rear_camera_constraint_vertices!");
        edge->setVertex(2, front_rear_camera_constraint_vertices[id3]);

        ::g2o::Sim3 I_sim3(T_pose.block(0, 0, 3, 3), T_pose.block(0, 3, 3, 1), 1.0);
        edge->setMeasurement(I_sim3);

        edge->information() = MatRC_t<7, 7>::Identity();

        if (edge->numUndefinedVertices()) {
            spdlog::debug("Invalid edge!");
        }

        optimizer.addEdge(edge);
    };

    // threshold weight以上のloop edgeを追加する
    /*for (const auto& loop_connection : loop_connections) {
        auto keyfrm = loop_connection.first;
        const auto& connected_keyfrms = loop_connection.second;

        const auto id1 = keyfrm->id_;

        // const ::g2o::Sim3& Sim3_1w = Sim3s_cw.at(id1);
        const ::g2o::Sim3& Sim3_1w = map_Sim3s_cw[id1];
        const ::g2o::Sim3 Sim3_w1 = Sim3_1w.inverse();

        for (auto connected_keyfrm : connected_keyfrms) {
            if (connected_keyfrm->will_be_erased())
                continue;
            const auto id2 = connected_keyfrm->id_;

            // current vs loop以外のedgeについては，weight thresholdを超えているもののみ
            // を追加する
            if ((id1 != curr_keyfrm->id_ || id2 != loop_keyfrm->id_) &&
    keyfrm->graph_node_->get_weight(connected_keyfrm) < loop_min_weight) {
                // spdlog::debug("Loop connection weight: {}", keyfrm->graph_node_->get_weight(connected_keyfrm));
                continue;
            }

            // 相対姿勢を計算
            // const ::g2o::Sim3& Sim3_2w = Sim3s_cw.at(id2);
            const ::g2o::Sim3& Sim3_2w = map_Sim3s_cw[id2];
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
            // constraint edgeを追加

            insert_edge(id1, id2, Sim3_21);
        }
    }*/
    int valid_loop_connections_size = 0;
    spdlog::debug("all_loop_connections_size: {}", loop_connections_with_pose.size());

    for (const auto& loop_connection_with_pose : loop_connections_with_pose) {
        const auto& keyfrm_pose_1 = loop_connection_with_pose.first;
        const auto& keyfrm_pose_2 = loop_connection_with_pose.second;

        const auto& keyfrm1 = keyfrm_pose_1.first;
        const auto& keyfrm2 = keyfrm_pose_2.first;

        const auto id1 = keyfrm1->id_;
        const auto id2 = keyfrm2->id_;

        const ::g2o::Sim3& Sim3_1w =
            ::g2o::Sim3(keyfrm_pose_1.second.block(0, 0, 3, 3), keyfrm_pose_1.second.block(0, 3, 3, 1), 1.0);
        const ::g2o::Sim3 Sim3_w1 = Sim3_1w.inverse();

        if (keyfrm1->graph_node_->get_weight(keyfrm2) >= loop_min_weight) {
            const ::g2o::Sim3& Sim3_2w =
                ::g2o::Sim3(keyfrm_pose_2.second.block(0, 0, 3, 3), keyfrm_pose_2.second.block(0, 3, 3, 1), 1.0);
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;
            insert_edge(id1, id2, Sim3_21);
            valid_loop_connections_size++;
        }
    }

    spdlog::debug("valid_loop_connections_size: {}", valid_loop_connections_size);

    // loop connection以外のedgeを追加する
    for (auto keyfrm : all_keyfrms) {
        if (!keyfrm) {
            continue;
        }
        if (keyfrm->will_be_erased()) continue;
        // 片方のkeyframeの姿勢を取り出す
        const auto id1 = keyfrm->id_;

        // covisibilitiesに含まれているかをチェックし，必ず修正前の姿勢を使うようにする
        // (正しく相対姿勢を計算するには両者が修正前である必要があるため)

        auto cam_pose_wc_before_BA = keyfrm->cam_pose_cw_before_BA_.inverse();

        const ::g2o::Sim3 Sim3_w1 =
            keyfrm->loop_BA_identifier_ == loop_identifier
                ? ::g2o::Sim3(cam_pose_wc_before_BA.block(0, 0, 3, 3), cam_pose_wc_before_BA.block(0, 3, 3, 1), 1.0)
                : map_Sim3s_cw.at(id1).inverse();  //((iter1 != non_corrected_Sim3s.end()) ? iter1->second :
                                                   // map_Sim3s_cw[id1]).inverse();

        auto parent_node = keyfrm->graph_node_->get_spanning_parent();

        if (parent_node) {
            if (parent_node->will_be_erased()) continue;
            const auto id2 = parent_node->id_;

            // 重複を防ぐ
            if (id1 <= id2) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w = (parent_node->loop_BA_identifier_ == loop_identifier)
                                             ? ::g2o::Sim3(parent_node->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                                           parent_node->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                                             : map_Sim3s_cw[id2];

            // 相対姿勢を計算
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            // constraint edgeを追加

            insert_edge(id1, id2, Sim3_21);

            child_parent_edge++;
        }

        // loop edgeはweightにかかわらず追加する
        const auto loop_edges = keyfrm->graph_node_->get_loop_edges();
        for (const auto& connected_keyfrm : loop_edges) {
            if (connected_keyfrm->will_be_erased()) continue;

            const auto id2 = connected_keyfrm->id_;

            // 重複を防ぐ
            if (id1 <= id2) {
                continue;
            }

            // covisibilitiesに含まれているかをチェックし，必ず修正前の姿勢を使うようにする
            // (正しく相対姿勢を計算するには両者が修正前である必要があるため)
            // const auto iter2 = non_corrected_Sim3s.find(connected_keyfrm);
            // const ::g2o::Sim3& Sim3_2w = (iter2 != non_corrected_Sim3s.end()) ? iter2->second : Sim3s_cw.at(id2);
            const ::g2o::Sim3& Sim3_2w =
                (connected_keyfrm->loop_BA_identifier_ == loop_identifier)
                    ? ::g2o::Sim3(connected_keyfrm->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                  connected_keyfrm->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                    : map_Sim3s_cw[id2];  //(iter2 != non_corrected_Sim3s.end()) ? iter2->second : map_Sim3s_cw[id2];

            // 相対姿勢を計算
            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            // constraint edgeを追加
            insert_edge(id1, id2, Sim3_21);

            loop_edge++;
        }

        // threshold weight以上のcovisibilitiesを追加する
        /*const auto connected_keyfrms = keyfrm->graph_node_->get_covisibilities_over_weight(min_weight);
        for (auto connected_keyfrm : connected_keyfrms) {
            // null check
            if (!connected_keyfrm || !parent_node) {
                continue;
            }

            // parent-childのedgeはすでに追加しているので除外
            if (*connected_keyfrm == *parent_node || keyfrm->graph_node_->has_spanning_child(connected_keyfrm)) {
                continue;
            }
            // loop対応している場合はすでに追加しているので除外
            if (static_cast<bool>(loop_edges.count(connected_keyfrm))) {
                continue;
            }

            if (connected_keyfrm->will_be_erased()) {
                continue;
            }

            const auto id2 = connected_keyfrm->id_;

            // 重複を防ぐ
            if (id1 <= id2) {
                continue;
            }
            if (static_cast<bool>(inserted_edge_pairs.count(std::make_pair(std::min(id1, id2), std::max(id1, id2))))) {
                continue;
            }

            const ::g2o::Sim3& Sim3_2w =
                (connected_keyfrm->loop_BA_identifier_ == loop_identifier)
                    ? ::g2o::Sim3(connected_keyfrm->cam_pose_cw_before_BA_.block(0, 0, 3, 3),
                                  connected_keyfrm->cam_pose_cw_before_BA_.block(0, 3, 3, 1), 1.0)
                    : map_Sim3s_cw[id2];  // (iter2 != non_corrected_Sim3s.end()) ? iter2->second : map_Sim3s_cw[id2];

            const ::g2o::Sim3 Sim3_21 = Sim3_2w * Sim3_w1;

            insert_edge(id1, id2, Sim3_21);
        }*/

        // Add multi camera constraint
        if (keyfrm->graph_node_->has_front_rear_camera_constraint()) {
            auto multi_camera_constraint = keyfrm->graph_node_->get_front_rear_camera_constraint();
            const auto constraint_id = multi_camera_constraint.first;
            const auto id2 = multi_camera_constraint.second->id_;
            /*spdlog::debug(
                "insert_multi_camera_edge constraint {} between client {} keyframe {} and client {} keyframe {} ",
                constraint_id, keyfrm->client_id_, id1, multi_camera_constraint.second->client_id_, id2);*/
            if (multi_camera_constraint.second->get_map_id() != loop_keyfrm->get_map_id() &&
                multi_camera_constraint.second->get_map_id() != curr_keyfrm->get_map_id()) {
                spdlog::debug("The two constrained keyframes of the same robot are not in the same map!");
                continue;
            }
            // The transform is from smaller id client to bigger id client
            if (keyfrm->client_id_ > multi_camera_constraint.second->client_id_) continue;
            if (multi_camera_constraint.second->will_be_erased()) continue;

            double time2 = multi_camera_constraint.second->timestamp_;
            Mat44_t slerp_pose;
            if (!slerp_pose_between_keyframes(keyfrm, time2, slerp_pose)) {
                spdlog::debug("Invalid slerping");
                continue;
            }
            Mat44_t pose_c_v = keyfrm->get_cam_pose() * slerp_pose;

            /*  -----------------Figure of Virtual keyframe-----------------
               ---------keyfrm-------virtual keyfrm----------next keyfrm---------
                             -pose_c_v-
               ------------------multi_camera_constraint keyfrm------------------
           */

            insert_multi_camera_edge(id1, id2, constraint_id, pose_c_v);
            front_rear_camera_edge++;
        }
    }

    // 4. pose graph optimizationを走らせる
    optimizer.initializeOptimization();

    // std::cout << "Global Pose Graph involed: \n";
    // std::cout << "active edges: " << optimizer.activeEdges().size() << "\n ";
    // std::cout << "Keyframes: " << all_keyfrms.size() << "\n ";
    // std::cout << "loop edge num: " << loop_edge << "\n";
    // std::cout << "child-parent edge num: " << child_parent_edge << "\n";
    // std::cout << "front_rear_camera edge num: " << front_rear_camera_edge << "\n";

    optimizer.setVerbose(true);
    {
        std::lock_guard<std::mutex> lock(mtx_thread_);
        if (abort_graph_optimization_) {
            graph_optimization_is_running_ = false;
            abort_graph_optimization_ = false;
            return;
        }
    }

    optimizer.optimize(iteration_times);

    // 5. 姿勢を更新
    std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);
    std::lock_guard<std::mutex> lock1(data::map_database::mtx_map_database_[curr_keyfrm->get_map_id()]);
    {
        // 点群の位置修正のために，全keyframeの姿勢(修正後)を保存しておく
        MapID merged_map_id = std::min(loop_keyfrm->get_map_id(), curr_keyfrm->get_map_id());

        std::unordered_map<KeyframeID, ::g2o::Sim3> map_corrected_Sim3s_wc;

        for (auto keyfrm : all_keyfrms) {
            if (!keyfrm) {
                continue;
            }

            if (keyfrm->will_be_erased()) continue;

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
            // if (keyfrm->loop_BA_identifier_ != loop_identifier)
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

            KeyframeID id = ref_keyfrm->id_;

            if (map_Sim3s_cw.find(id) != map_Sim3s_cw.end()) {
                const ::g2o::Sim3& Sim3_cw = map_Sim3s_cw.at(id);
                const ::g2o::Sim3& corrected_Sim3_wc = map_corrected_Sim3s_wc.at(id);

                const Vec3_t pos_w = lm->get_pos_in_world();
                const Vec3_t corrected_pos_w = corrected_Sim3_wc.map(Sim3_cw.map(pos_w));

                lm->set_pos_in_world(corrected_pos_w);
            } else {
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
            lm->set_map_id(merged_map_id);
        }
    }
    server_->post_process_after_loop(loop_keyfrm->client_id_, curr_keyfrm->client_id_, loop_keyfrm->get_map_id(),
                                     curr_keyfrm->get_map_id());
    std::lock_guard<std::mutex> lock_thread(mtx_thread_);
    abort_graph_optimization_ = false;
    loop_connections.clear();
    unused_nerbors.clear();
    loop_connections_with_pose.clear();

    graph_optimization_is_running_ = false;
    curr_keyfrm->graph_node_->add_loop_edge(loop_keyfrm);
    loop_keyfrm->graph_node_->add_loop_edge(curr_keyfrm);
}

}  // namespace optimize
}  // namespace openvslam
