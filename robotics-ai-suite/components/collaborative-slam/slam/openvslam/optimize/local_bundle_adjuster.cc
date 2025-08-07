// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/local_bundle_adjuster.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "optimize/g2o/landmark_vertex_container.h"
#include "optimize/g2o/se3/reproj_edge_wrapper.h"
#include "optimize/g2o/se3/shot_vertex_container.h"
#include "optimize/g2o/se3/pose_graph_edge.h"
#include "util/converter.h"

#include <stdexcept>
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
#include <Eigen/StdVector>
#include "g2o/imubias_vertex.h"
#include "g2o/imubias_vertex_container.h"
#include <g2o/core/sparse_block_matrix.h>
#include <unsupported/Eigen/MatrixFunctions>
#include "optimize/g2o/se3/shot_vertex_container.h"
#include "../data/imu.h"
#include "optimize/g2o/vec3_vertex.h"
#include "optimize/g2o/scale_vertex.h"
#include "imu_edge.h"
#include "optimize/g2o/vec3_vertex_container.h"
#include "optimize/g2o/so3_vertex.h"

#include "optimize/g2o/camera_pose_vertex.h"
#include "optimize/g2o/camera_pose_vertex_container.h"
#include "optimize/g2o/reproj_edge_wrapper2.h"
#include "optimize/g2o/perspective_reproj_edge2.h"

// percentile of chi square distribution
#define CHI2_MONO_THR      5.991
#define CHI2_STEREO_THR    7.815

extern bool is_server_node;

constexpr float chi_sq_2D = 5.99146;
constexpr float chi_sq_3D = 7.81473;
const float sqrt_chi_sq_2D = std::sqrt(chi_sq_2D);
const float sqrt_chi_sq_3D = std::sqrt(chi_sq_3D);

namespace openvslam {
namespace optimize {

local_bundle_adjuster::local_bundle_adjuster(data::map_database* map_db, const bool use_odom,
                                             const unsigned int num_first_iter, const unsigned int num_second_iter)
    : num_first_iter_(num_first_iter), num_second_iter_(num_second_iter), map_db_(map_db), use_odom_(use_odom)
{
}

local_bundle_adjuster::local_bundle_adjuster(const unsigned int num_first_iter, const unsigned int num_second_iter)
    : num_first_iter_(num_first_iter), num_second_iter_(num_second_iter), use_odom_(false)
{
}

void local_bundle_adjuster::optimize(data::keyframe* curr_keyfrm, bool* const force_stop_flag,
                                     [[maybe_unused]] const bool is_large) const
{
    if (is_server_node)
        optimize_server_node(curr_keyfrm, force_stop_flag);
    else
        optimize_tracker_node(curr_keyfrm, force_stop_flag, is_large);
}

void local_bundle_adjuster::optimize_tracker_node(data::keyframe* curr_keyfrm, bool* const force_stop_flag,
    const bool is_large) const
{
    if (curr_keyfrm->camera_->use_imu_ && data::IMU_Preintegration::imu_initialize_times_ > 0) {
        /*
            use LocalBA rather than LocalInertialBA as default ones since the latter has much
            higher possibility to result in tracking lost and bad trajectory, although it has
            better scale and RMSE than the former in the successfull cases.

            fix this kind of randomness by always enable robust kernel for inertial edges.
        */
        optimize_with_imu(curr_keyfrm, force_stop_flag, is_large);
        // optimize_without_imu(curr_keyfrm, force_stop_flag);
    } else {
        optimize_without_imu(curr_keyfrm, force_stop_flag);
    }
}

void local_bundle_adjuster::optimize_server_node(data::keyframe* curr_keyfrm, bool* const force_stop_flag) const
{
    {
        // 1. local/fixed keyframes, local landmarksを集計する
        std::unordered_map<KeyframeID, data::keyframe*> local_keyfrms;

        // correct local keyframes of the current keyframe

        local_keyfrms[curr_keyfrm->id_] = curr_keyfrm;
        const auto curr_covisibilities = curr_keyfrm->graph_node_->get_covisibilities();
        for (const auto& local_keyfrm : curr_covisibilities) {
            if (!local_keyfrm) {
                continue;
            }
            if (unlikely(local_keyfrm->will_be_erased())) {
                continue;
            }

            local_keyfrms[local_keyfrm->id_] = local_keyfrm;
        }

        // correct local landmarks seen in local keyframes
        std::unordered_map<LandmarkID, data::landmark*> local_lms;

        for (const auto& local_keyfrm : local_keyfrms) {
            const auto landmarks = local_keyfrm.second->get_landmarks();
            for (auto local_lm : landmarks) {
                if (!local_lm) {
                    continue;
                }
                if (unlikely(local_lm->will_be_erased())) {
                    continue;
                }

                // 重複を避ける
                if (local_lms.count(local_lm->id_)) {
                    continue;
                }

                local_lms[local_lm->id_] = local_lm;
            }
        }

        // fixed keyframes: keyframes which observe local landmarks but which are NOT in local keyframes
        std::unordered_map<KeyframeID, data::keyframe*> fixed_keyfrms;

        for (const auto& local_lm : local_lms) {
            const auto observations = local_lm.second->get_observations();
            for (auto& obs : observations) {
                auto fixed_keyfrm = obs.first;
                if (!fixed_keyfrm) {
                    continue;
                }
                if (fixed_keyfrm->will_be_erased()) {
                    continue;
                }

                // local keyframesに属しているときは追加しない
                if (local_keyfrms.count(fixed_keyfrm->id_)) {
                    continue;
                }

                // 重複を避ける
                if (fixed_keyfrms.count(fixed_keyfrm->id_)) {
                    continue;
                }

                fixed_keyfrms[fixed_keyfrm->id_] = fixed_keyfrm;
            }
        }

        // 2. optimizerを構築

        auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_6_3::PoseMatrixType>>();
        auto block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
        auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

        ::g2o::SparseOptimizer optimizer;
        optimizer.setAlgorithm(algorithm);

        if (force_stop_flag) {
            optimizer.setForceStopFlag(force_stop_flag);
        }

        // 3. keyframeをg2oのvertexに変換してoptimizerにセットする

        // shot vertexのcontainer
        g2o::se3::shot_vertex_container keyfrm_vtx_container(0, local_keyfrms.size() + fixed_keyfrms.size());
        // vertexに変換されたkeyframesを保存しておく
        std::unordered_map<KeyframeID, data::keyframe*> all_keyfrms;

        // local keyframesをoptimizerにセット
        for (auto& id_local_keyfrm_pair : local_keyfrms) {
            auto local_keyfrm = id_local_keyfrm_pair.second;

            all_keyfrms.emplace(id_local_keyfrm_pair);
            auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(local_keyfrm, local_keyfrm->id_ == 0);
            optimizer.addVertex(keyfrm_vtx);
        }

        // fixed keyframesをoptimizerにセット
        for (auto& id_fixed_keyfrm_pair : fixed_keyfrms) {
            auto fixed_keyfrm = id_fixed_keyfrm_pair.second;

            all_keyfrms.emplace(id_fixed_keyfrm_pair);
            auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(fixed_keyfrm, true);
            optimizer.addVertex(keyfrm_vtx);
        }

        // 4. keyframeとlandmarkのvertexをreprojection edgeで接続する

        // landmark vertexのcontainer
        g2o::landmark_vertex_container lm_vtx_container(keyfrm_vtx_container.get_max_vertex_id() + 1, local_lms.size());

        // reprojection edgeのcontainer
        using reproj_edge_wrapper = g2o::se3::reproj_edge_wrapper<data::keyframe>;
        std::vector<reproj_edge_wrapper> reproj_edge_wraps;
        reproj_edge_wraps.reserve(all_keyfrms.size() * local_lms.size());        

        for (auto& id_local_lm_pair : local_lms) {
            auto local_lm = id_local_lm_pair.second;

            // landmarkをg2oのvertexに変換してoptimizerにセットする
            auto lm_vtx = lm_vtx_container.create_vertex(local_lm, false);
            optimizer.addVertex(lm_vtx);

            const auto observations = local_lm->get_observations();
            for (const auto& obs : observations) {
                auto keyfrm = obs.first;
                auto idx = obs.second;
                if (!keyfrm) {
                    continue;
                }
                if (keyfrm->will_be_erased()) {
                    continue;
                }

                const auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(keyfrm);
                const auto& undist_keypt = keyfrm->undist_keypts_.at(idx);
                const float x_right = keyfrm->stereo_x_right_.at(idx);
                const float inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(undist_keypt.octave);
                const auto sqrt_chi_sq =
                    (keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular) ? sqrt_chi_sq_2D : sqrt_chi_sq_3D;
                auto reproj_edge_wrap = reproj_edge_wrapper(keyfrm, keyfrm_vtx, local_lm, lm_vtx, idx, undist_keypt.pt.x,
                                                            undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
                reproj_edge_wraps.push_back(reproj_edge_wrap);
                optimizer.addEdge(reproj_edge_wrap.edge_);
            }
        }

        // 5. 1回目の最適化を実行

        if (force_stop_flag) {
            if (*force_stop_flag) {
                return;
            }
        }

        optimizer.initializeOptimization();
        optimizer.optimize(num_first_iter_);

        // 6. アウトライア除去をして2回目の最適化を実行

        bool run_robust_BA = true;

        if (force_stop_flag) {
            if (*force_stop_flag) {
                run_robust_BA = false;
            }
        }

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
            optimizer.optimize(num_second_iter_);
        }

        // 7. アウトライアを集計する

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

        // 8. 情報を更新

        {
            std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);

            if (!outlier_observations.empty()) {
                for (auto& outlier_obs : outlier_observations) {
                    auto keyfrm = outlier_obs.first;
                    auto lm = outlier_obs.second;
                    keyfrm->erase_landmark(lm);
                    lm->erase_observation(keyfrm);
                }
            }

            for (auto& id_local_keyfrm_pair : local_keyfrms) {
                auto local_keyfrm = id_local_keyfrm_pair.second;

                auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(local_keyfrm);
                local_keyfrm->set_cam_pose(keyfrm_vtx->estimate());
            }

            for (auto& id_local_lm_pair : local_lms) {
                auto local_lm = id_local_lm_pair.second;

                auto lm_vtx = lm_vtx_container.get_vertex(local_lm);
                local_lm->set_pos_in_world(lm_vtx->estimate());
                local_lm->update_normal_and_depth();
            }
        }
    }
}

void local_bundle_adjuster::optimize_without_imu(openvslam::data::keyframe* curr_keyfrm,
                                                 bool* const force_stop_flag) const
{
    // 1. local/fixed keyframes, local landmarksを集計する
    std::unordered_map<KeyframeID, data::keyframe*> local_keyfrms;

    // correct local keyframes of the current keyframe

    local_keyfrms[curr_keyfrm->id_] = curr_keyfrm;
    const auto curr_covisibilities = curr_keyfrm->graph_node_->get_covisibilities();
    for (auto local_keyfrm : curr_covisibilities) {
        if (unlikely(!local_keyfrm)) {
            continue;
        }
        if (unlikely(local_keyfrm->will_be_erased())) {
            continue;
        }

        local_keyfrms[local_keyfrm->id_] = local_keyfrm;

        local_keyfrm->out_of_local_map_times_ = 0;
    }

    // correct local landmarks seen in local keyframes
    std::unordered_map<LandmarkID, data::landmark*> local_lms;
    for (auto& local_keyfrm : local_keyfrms) {
        const auto landmarks = local_keyfrm.second->get_landmarks();
        for (auto local_lm : landmarks) {
            if (!local_lm) {
                continue;
            }
            if (unlikely(local_lm->will_be_erased())) {
                continue;
            }

            // 重複を避ける
            if (local_lms.count(local_lm->id_)) {
                continue;
            }

            local_lms[local_lm->id_] = local_lm;

            local_lm->out_of_local_map_times_ = 0;
        }
    }

    // fixed keyframes: keyframes which observe local landmarks but which are NOT in local keyframes
    std::unordered_map<KeyframeID, data::keyframe*> fixed_keyfrms;
    for (auto& local_lm : local_lms) {
        auto observations = local_lm.second->get_observations();
        for (auto& obs : observations) {
            auto fixed_keyfrm = obs.first;
            if (unlikely(!fixed_keyfrm)) {
                continue;
            }
            if (unlikely(fixed_keyfrm->will_be_erased())) {
                continue;
            }

            // local keyframesに属しているときは追加しない
            if (local_keyfrms.count(fixed_keyfrm->id_)) {
                continue;
            }

            // 重複を避ける
            if (fixed_keyfrms.count(fixed_keyfrm->id_)) {
                continue;
            }

            fixed_keyfrms[fixed_keyfrm->id_] = fixed_keyfrm;

            fixed_keyfrm->out_of_local_map_times_ = 0;
        }
    }
    // 2. optimizerを構築

    auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_6_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);

    if (force_stop_flag) {
        optimizer.setForceStopFlag(force_stop_flag);
    }

    // 3. keyframeをg2oのvertexに変換してoptimizerにセットする

    // shot vertexのcontainer
    g2o::se3::shot_vertex_container keyfrm_vtx_container(0, local_keyfrms.size() + fixed_keyfrms.size());
    // vertexに変換されたkeyframesを保存しておく
    std::unordered_map<KeyframeID, data::keyframe*> all_keyfrms;

    // local keyframesをoptimizerにセット
    for (auto& id_local_keyfrm_pair : local_keyfrms) {
        auto local_keyfrm = id_local_keyfrm_pair.second;

        all_keyfrms.emplace(id_local_keyfrm_pair);
        auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(local_keyfrm, local_keyfrm->is_origin());
        optimizer.addVertex(keyfrm_vtx);
    }

    // fixed keyframesをoptimizerにセット
    for (auto& id_fixed_keyfrm_pair : fixed_keyfrms) {
        auto fixed_keyfrm = id_fixed_keyfrm_pair.second;

        all_keyfrms.emplace(id_fixed_keyfrm_pair);
        auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(fixed_keyfrm, true);
        optimizer.addVertex(keyfrm_vtx);
    }

    // 4. keyframeとlandmarkのvertexをreprojection edgeで接続する

    // landmark vertexのcontainer
    g2o::landmark_vertex_container lm_vtx_container(keyfrm_vtx_container.get_max_vertex_id() + 1, local_lms.size());

    // reprojection edgeのcontainer
    using reproj_edge_wrapper = g2o::se3::reproj_edge_wrapper<data::keyframe>;
    std::vector<reproj_edge_wrapper> reproj_edge_wraps;
    reproj_edge_wraps.reserve(all_keyfrms.size() * local_lms.size());

    // 有意水準5%のカイ2乗値
    // 自由度n=2

    for (auto& id_local_lm_pair : local_lms) {
        auto local_lm = id_local_lm_pair.second;

        // landmarkをg2oのvertexに変換してoptimizerにセットする
        auto lm_vtx = lm_vtx_container.create_vertex(local_lm, false);
        optimizer.addVertex(lm_vtx);

        const auto observations = local_lm->get_observations();
        for (const auto& obs : observations) {
            auto keyfrm = obs.first;

            auto idx = obs.second;
            if (unlikely(!keyfrm)) {
                continue;
            }
            if (unlikely(keyfrm->will_be_erased())) {
                continue;
            }

            // This will happen rarely, this means the landmark observation has been modifiel at the same time!
            // or new landmark has been added!
            if (!fixed_keyfrms.count(keyfrm->id_) && !local_keyfrms.count(keyfrm->id_)) {
                std::cout << "No such keyframe " << keyfrm->id_ << " for landmark " << local_lm->id_
                          << " involved in this local mapping!" << std::endl;
                std::cout << " \n"
                          << " \n"
                          << " \n"
                          << " \n"
                          << " \n"
                          << " \n"
                          << " \n"
                          << " \n";
                // abort();
                continue;
            }

            const auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(keyfrm);
            const auto& undist_keypt = keyfrm->undist_keypts_.at(idx);
            const float x_right = keyfrm->stereo_x_right_.at(idx);
            const float inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(undist_keypt.octave);
            const auto sqrt_chi_sq = (keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular ||
                                      keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial)
                                         ? sqrt_chi_sq_2D
                                         : sqrt_chi_sq_3D;
            auto reproj_edge_wrap = reproj_edge_wrapper(keyfrm, keyfrm_vtx, local_lm, lm_vtx, idx, undist_keypt.pt.x,
                                                        undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
            reproj_edge_wraps.push_back(reproj_edge_wrap);
            optimizer.addEdge(reproj_edge_wrap.edge_);
        }
    }

    // Add odom edge
    if (use_odom_) {
        // use origin_keyfrm from map database as reference keyframe to construct odom edge
        auto kf1 = map_db_->odom_origin_keyfrm_;
        // only add to keyframe container when it is not added before
        // otherwise origin keyframe is already within local keyframes, no need to add
        if (!keyfrm_vtx_container.contain(kf1)) {
            auto origin_keyfrm_vtx = keyfrm_vtx_container.create_vertex(kf1, true);
            optimizer.addVertex(origin_keyfrm_vtx);
        }

        // sort the local keyframes
        std::vector<data::keyframe*> local_kfs;
        local_kfs.reserve(local_keyfrms.size());
        for (auto& it : local_keyfrms) {
            local_kfs.push_back(it.second);
        }
        std::sort(local_kfs.begin(), local_kfs.end(), [](const auto& a, const auto& b) { return a->id_ < b->id_; });

        // add odom constraint to nearby keyframes
        int size = local_kfs.size();
        Eigen::Matrix4d odom1, odom2;
        Eigen::Matrix4d T21 = Eigen::Matrix4d::Identity();
        // the first vertex of the edge is always the origin keyframe
        auto kf1_vtx = keyfrm_vtx_container.get_vertex(kf1);
        odom1 = kf1->odom_;
        // by avoid start tracking before getting valid odom data, the odom for original keyframe should be valid
        if (odom1 == Eigen::Matrix4d::Identity()) {
            spdlog::warn("Invalid odom data of original keyframe in local BA! kf id is {}", kf1->id_);
        } else {
            for (int i = 0; i < size; ++i) {
                auto kf2 = local_kfs[i];
                auto kf2_vtx = keyfrm_vtx_container.get_vertex(kf2);

                // get relative transform from odom
                odom2 = kf2->odom_;
                if (odom2 == Eigen::Matrix4d::Identity()) {
                    spdlog::debug("Invalid odom data of local keyframe in local BA! kf id is {}", kf2->id_);
                    continue;
                }

                // Tco
                Mat33_t rot_c2_o = odom2.block<3, 3>(0, 0);
                Vec3_t trans_c2_o = odom2.block<3, 1>(0, 3);
                Mat33_t rot_o_c1 = odom1.block<3, 3>(0, 0).transpose();
                Vec3_t trans_o_c1 = -rot_o_c1 * odom1.block<3, 1>(0, 3);

                Mat33_t rot_c2_c1 = rot_c2_o * rot_o_c1;
                Vec3_t trans_c2_c1 = rot_c2_o * trans_o_c1 + trans_c2_o;

                T21.block<3, 3>(0, 0) = rot_c2_c1;
                T21.block<3, 1>(0, 3) = trans_c2_c1;

                g2o::se3::pose_graph_edge* edge = new g2o::se3::pose_graph_edge();

                edge->setVertex(0, kf1_vtx);
                edge->setVertex(1, kf2_vtx);
                edge->setMeasurement(::g2o::SE3Quat(T21.block(0, 0, 3, 3), T21.block(0, 3, 3, 1)));
                // TODO: change the ratio
                MatRC_t<6, 6> information = MatRC_t<6, 6>::Identity();
                // constrain the rotation part
                information.block<3, 3>(0, 0) *= 1e6;
                // constrain the translation part
                information.block<3, 3>(3, 3) *= 1e6;
                edge->setInformation(information);
                optimizer.addEdge(edge);
                // TODO: add edge to vector and update later
            }
        }
    }

    // 5. 1回目の最適化を実行

    if (force_stop_flag) {
        if (*force_stop_flag) {
            return;
        }
    }

    optimizer.setVerbose(false);
    optimizer.initializeOptimization();
    optimizer.optimize(num_first_iter_);

    // 6. アウトライア除去をして2回目の最適化を実行

    bool run_robust_BA = true;

    if (force_stop_flag) {
        if (*force_stop_flag) {
            run_robust_BA = false;
        }
    }

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
        optimizer.optimize(num_second_iter_);
    }

    // 7. アウトライアを集計する

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

    // 8. 情報を更新

    {
        std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);

        if (!outlier_observations.empty()) {
            for (auto& outlier_obs : outlier_observations) {
                auto keyfrm = outlier_obs.first;
                auto lm = outlier_obs.second;
                keyfrm->erase_landmark(lm);
                lm->erase_observation(keyfrm);
            }
        }

        for (auto& id_local_keyfrm_pair : local_keyfrms) {
            auto local_keyfrm = id_local_keyfrm_pair.second;

            auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(local_keyfrm);
            local_keyfrm->set_cam_pose(keyfrm_vtx->estimate());
        }

        for (auto& id_local_lm_pair : local_lms) {
            auto local_lm = id_local_lm_pair.second;

            auto lm_vtx = lm_vtx_container.get_vertex(local_lm);
            local_lm->set_pos_in_world(lm_vtx->estimate());
            local_lm->update_normal_and_depth();
        }
    }
}

// For future using if necessary
void local_bundle_adjuster::optimize_from_server(openvslam::data::keyframe* curr_keyfrm,
                                                 bool* const force_stop_flag) const
{
    // 1. local/fixed keyframes, local landmarksを集計する
    std::unordered_map<KeyframeID, data::keyframe*> relative_keyfrms;
    std::unordered_map<LandmarkID, data::landmark*> local_lms;

    auto all_local_keyframes = map_db_->get_all_keyframes();

    auto all_local_landmarks = map_db_->get_all_landmarks();

    for (auto lm : all_local_landmarks) {
        local_lms[lm->id_] = lm;
    }

    for (auto kf : all_local_keyframes) {
        relative_keyfrms[kf->id_] = kf;
    }

    // 2. optimizerを構築

    auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_6_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);

    if (force_stop_flag) {
        optimizer.setForceStopFlag(force_stop_flag);
    }

    // 3. keyframeをg2oのvertexに変換してoptimizerにセットする

    // shot vertexのcontainer
    g2o::se3::shot_vertex_container keyfrm_vtx_container(0, relative_keyfrms.size());
    // vertexに変換されたkeyframesを保存しておく
    std::unordered_map<KeyframeID, data::keyframe*> all_keyfrms;

    // local keyframesをoptimizerにセット
    for (auto& id_relative_keyfrm_pair : relative_keyfrms) {
        auto relative_keyfrm = id_relative_keyfrm_pair.second;

        all_keyfrms.emplace(id_relative_keyfrm_pair);
        auto keyfrm_vtx = keyfrm_vtx_container.create_vertex(relative_keyfrm, relative_keyfrm->update_from_server_);
        optimizer.addVertex(keyfrm_vtx);
    }

    // 4. keyframeとlandmarkのvertexをreprojection edgeで接続する

    // landmark vertexのcontainer
    g2o::landmark_vertex_container lm_vtx_container(keyfrm_vtx_container.get_max_vertex_id() + 1, local_lms.size());

    // reprojection edgeのcontainer
    using reproj_edge_wrapper = g2o::se3::reproj_edge_wrapper<data::keyframe>;
    std::vector<reproj_edge_wrapper> reproj_edge_wraps;
    reproj_edge_wraps.reserve(all_keyfrms.size() * local_lms.size());

    for (auto& id_local_lm_pair : local_lms) {
        auto local_lm = id_local_lm_pair.second;

        // landmarkをg2oのvertexに変換してoptimizerにセットする
        auto lm_vtx = lm_vtx_container.create_vertex(local_lm, false);
        optimizer.addVertex(lm_vtx);

        const auto observations = local_lm->get_observations();
        for (const auto& obs : observations) {
            auto keyfrm = obs.first;
            auto idx = obs.second;
            if (!keyfrm) {
                continue;
            }
            if (keyfrm->will_be_erased()) {
                continue;
            }

            const auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(keyfrm);
            const auto& undist_keypt = keyfrm->undist_keypts_.at(idx);
            const float x_right = keyfrm->stereo_x_right_.at(idx);
            const float inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(undist_keypt.octave);
            const auto sqrt_chi_sq = (curr_keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular ||
                                      curr_keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial)
                                         ? sqrt_chi_sq_2D
                                         : sqrt_chi_sq_3D;
            auto reproj_edge_wrap = reproj_edge_wrapper(keyfrm, keyfrm_vtx, local_lm, lm_vtx, idx, undist_keypt.pt.x,
                                                        undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
            reproj_edge_wraps.push_back(reproj_edge_wrap);
            optimizer.addEdge(reproj_edge_wrap.edge_);
        }
    }

    // 5. 1回目の最適化を実行

    if (force_stop_flag) {
        if (*force_stop_flag) {
            return;
        }
    }

    optimizer.initializeOptimization();
    optimizer.optimize(num_first_iter_);

    // 6. アウトライア除去をして2回目の最適化を実行

    bool run_robust_BA = true;

    if (force_stop_flag) {
        if (*force_stop_flag) {
            run_robust_BA = false;
        }
    }

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
        optimizer.optimize(num_second_iter_);
    }

    // 7. アウトライアを集計する

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

    // 8. 情報を更新

    {
        // std::lock_guard<std::mutex> lock(data::map_database::mtx_database_);

        if (!outlier_observations.empty()) {
            for (auto& outlier_obs : outlier_observations) {
                auto keyfrm = outlier_obs.first;
                auto lm = outlier_obs.second;
                keyfrm->erase_landmark(lm);
                lm->erase_observation(keyfrm);
            }
        }

        for (auto& id_relative_keyfrm_pair : relative_keyfrms) {
            auto relative_keyfrm = id_relative_keyfrm_pair.second;

            auto keyfrm_vtx = keyfrm_vtx_container.get_vertex(relative_keyfrm);
            relative_keyfrm->set_cam_pose(keyfrm_vtx->estimate());
        }

        for (auto& id_local_lm_pair : local_lms) {
            auto local_lm = id_local_lm_pair.second;

            auto lm_vtx = lm_vtx_container.get_vertex(local_lm);
            local_lm->set_pos_in_world(lm_vtx->estimate());
            local_lm->update_normal_and_depth();
        }
    }
    std::cout << "Successfully update local map from server by optimization!" << std::endl;
}

void local_bundle_adjuster::optimize_with_imu(data::keyframe* curr_keyfrm, bool* const force_stop_flag,
                                                   bool is_large) const
{
    spdlog::debug("{}: start localBA with IMU, is_large: {}", __func__, is_large);
    // the window size of temporal keyframes to optimize, experience values form ORB3
    unsigned int max_optimize_window_size;
    // maximum iteration number of g2o optimizer, experience values from ORB3
    unsigned int iterations;
    if (is_large) {
        max_optimize_window_size = 25;
        iterations = 4;
    } else {
        max_optimize_window_size = 10;
        iterations = 10;
    }

    // Monocular initialization needs 2 keyframes, so we just exclude the corner case
    const unsigned int optimize_window_size = std::min(map_db_->get_num_keyframes() - 2, max_optimize_window_size);

    // temporal optimizable keyframes
    std::vector<data::keyframe*> temporal_keyframes;
    temporal_keyframes.emplace_back(curr_keyfrm);
    curr_keyfrm->is_considered_ = true;
    curr_keyfrm->is_fixed_ = false;
    for (unsigned int i = 1; i < optimize_window_size; i++) {
        if (temporal_keyframes.back()->pre_keyframe_) {
            temporal_keyframes.emplace_back(temporal_keyframes.back()->pre_keyframe_);
            temporal_keyframes.back()->is_considered_ = true;
            temporal_keyframes.back()->is_fixed_ = false;
        } else {
            break;
        }
    }

    // landmarks seen by temporal optimizable keyframes
    std::vector<data::landmark*> local_landmarks;
    for (auto& keyfrm : temporal_keyframes) {
        std::vector<data::landmark*> item_landmarks = keyfrm->get_landmarks();
        for (auto& landmark : item_landmarks) {
            if (!landmark || landmark->will_be_erased())
                continue;

            if (!landmark->is_considered_) {
                local_landmarks.emplace_back(landmark);
                landmark->is_considered_ = true;
                landmark->is_fixed_ = false;
            }
        }
    }

    // fixed keyframes in optimizer
    // take the keyframe at the boundary of the temporal window as fixed
    std::vector<data::keyframe*> fixed_keyframes;
    if (temporal_keyframes.back()->pre_keyframe_) {
        fixed_keyframes.emplace_back(temporal_keyframes.back()->pre_keyframe_);
        fixed_keyframes.back()->is_considered_ = true;
        fixed_keyframes.back()->is_fixed_ = true;
    } else {
        fixed_keyframes.emplace_back(temporal_keyframes.back());
        temporal_keyframes.pop_back();
        fixed_keyframes.back()->is_fixed_ = true;
    }

    // Covisibility Keyframes and related landmarks
    const std::vector<data::keyframe*> covisibility_keyframes = curr_keyfrm->graph_node_->get_covisibilities();
    std::vector<data::keyframe*> optcov_keyframes;
    const unsigned int max_cov_keyframes = 0;
    for (auto& keyfrm : covisibility_keyframes) {
        if (optcov_keyframes.size() >= max_cov_keyframes)
            break;

        if (!keyfrm || keyfrm->will_be_erased())
            continue;

        if (!keyfrm->is_considered_) {
            optcov_keyframes.emplace_back(keyfrm);
            keyfrm->is_considered_ = true;
            keyfrm->is_fixed_ = false;

            std::vector<data::landmark*> item_landmarks = keyfrm->get_landmarks();
            for (auto& landmark : item_landmarks) {
                if (!landmark || landmark->will_be_erased())
                    continue;

                if (!landmark->is_considered_) {
                    local_landmarks.emplace_back(landmark);
                    landmark->is_considered_ = true;
                    landmark->is_fixed_ = false;
                }
            }
        }
    }

    // take covisible keyframes which are not considered previously as fixed
    const unsigned int max_fixed_keframes = 200;
    for (auto& landmark : local_landmarks) {
        std::map<data::keyframe*, unsigned int> observations = landmark->get_observations();
        for (auto& observation : observations) {
            data::keyframe* keyfrm = observation.first;
            if (!keyfrm || keyfrm->will_be_erased())
                continue;

            if (!keyfrm->is_considered_) {
                fixed_keyframes.emplace_back(keyfrm);
                keyfrm->is_considered_ = true;
                keyfrm->is_fixed_ = true;
                break;
            }
        }

        if (fixed_keyframes.size() >= max_fixed_keframes)
            break;
    }

    // setup g2o optimizer
    ::g2o::SparseOptimizer optimizer;
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolverX::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolverX>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));
    if (is_large) {
        algorithm->setUserLambdaInit(1e-2);
    } else {
        algorithm->setUserLambdaInit(1e0);
    }
    optimizer.setAlgorithm(algorithm);

    // set temporal keyframe related vertices
    for (auto& keyfrm : temporal_keyframes) {
        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(false);
        optimizer.addVertex(pose_vtx);

        if (keyfrm->imu_is_initialized_) {
            g2o::VertexVelocity* velocity_vtx = new g2o::VertexVelocity(keyfrm);
            velocity_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx));
            velocity_vtx->setFixed(false);
            optimizer.addVertex(velocity_vtx);
            g2o::VertexGyroBias* gyro_vtx = new g2o::VertexGyroBias(keyfrm);
            gyro_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx));
            gyro_vtx->setFixed(false);
            optimizer.addVertex(gyro_vtx);
            g2o::VertexAccBias* acc_vtx = new g2o::VertexAccBias(keyfrm);
            acc_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx));
            acc_vtx->setFixed(false);
            optimizer.addVertex(acc_vtx);
        }
    }

    // set covisibility keyframe related vertices
    for (auto& keyfrm : optcov_keyframes) {
        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(false);
        optimizer.addVertex(pose_vtx);
    }

    // set fixed keyframe related vertices
    for (auto& keyfrm : fixed_keyframes) {
        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(true);
        optimizer.addVertex(pose_vtx);

        if (keyfrm->imu_is_initialized_) {
            g2o::VertexVelocity* velocity_vtx = new g2o::VertexVelocity(keyfrm);
            velocity_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx));
            velocity_vtx->setFixed(true);
            optimizer.addVertex(velocity_vtx);
            g2o::VertexGyroBias* gyro_vtx = new g2o::VertexGyroBias(keyfrm);
            gyro_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx));
            gyro_vtx->setFixed(true);
            optimizer.addVertex(gyro_vtx);
            g2o::VertexAccBias* acc_vtx = new g2o::VertexAccBias(keyfrm);
            acc_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx));
            acc_vtx->setFixed(true);
            optimizer.addVertex(acc_vtx);
        }
    }

    // set graph edges
    for (auto& keyfrm : temporal_keyframes) {
        if (!keyfrm->pre_keyframe_)
            continue;

        data::keyframe* pre_keyframe = keyfrm->pre_keyframe_;
        if (!keyfrm->imu_is_initialized_ || !pre_keyframe->imu_is_initialized_) {
            spdlog::debug("keyframe {} or keyframe {} isn't do imu initialization", keyfrm->id_, pre_keyframe->id_);
            continue;
        }

        auto keyfrm_preintegration = keyfrm->get_imu_constraint().second;
        if (!keyfrm_preintegration) {
            spdlog::debug("keyframe {}: doesn't have preintegration in constraint pair", keyfrm->id_);
            continue;
        }

        keyfrm_preintegration->set_new_imu_bias(pre_keyframe->get_imu_bias());
        int temp_pose_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::PoseVtx);
        ::g2o::HyperGraph::Vertex* temp_pose_vtx1 = optimizer.vertex(temp_pose_vtx1_id);
        int temp_velocity_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::VelocityVtx);
        ::g2o::HyperGraph::Vertex* temp_velocity_vtx1 = optimizer.vertex(temp_velocity_vtx1_id);
        int temp_gyro_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::GyroBiasVtx);
        ::g2o::HyperGraph::Vertex* temp_gyro_vtx1 = optimizer.vertex(temp_gyro_vtx1_id);
        int temp_acc_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::AccBiasVtx);
        ::g2o::HyperGraph::Vertex* temp_acc_vtx1 = optimizer.vertex(temp_acc_vtx1_id);
        int temp_pose_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
        ::g2o::HyperGraph::Vertex* temp_pose_vtx2 = optimizer.vertex(temp_pose_vtx2_id);
        int temp_velocity_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
        ::g2o::HyperGraph::Vertex* temp_velocity_vtx2 = optimizer.vertex(temp_velocity_vtx2_id);
        int temp_gyro_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx);
        ::g2o::HyperGraph::Vertex* temp_gyro_vtx2 = optimizer.vertex(temp_gyro_vtx2_id);
        int temp_acc_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx);
        ::g2o::HyperGraph::Vertex* temp_acc_vtx2 = optimizer.vertex(temp_acc_vtx2_id);

        if (!temp_pose_vtx1 || !temp_velocity_vtx1 || !temp_pose_vtx2 || !temp_velocity_vtx2 ||
            !temp_gyro_vtx1 || !temp_acc_vtx1 || !temp_gyro_vtx2 || !temp_acc_vtx2) {
            std::cout << "Error " << temp_pose_vtx1 << ", " << temp_velocity_vtx1 << ", " <<
                         temp_pose_vtx2 << ", " << temp_velocity_vtx2 << ", " << temp_gyro_vtx1 <<
                         ", " << temp_acc_vtx1 << ", " << temp_gyro_vtx2 << ", " << temp_acc_vtx2 << std::endl;
            continue;
        }

        g2o::EdgeInertial* inertial_edge = new g2o::EdgeInertial(keyfrm_preintegration);
        inertial_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx1));
        inertial_edge->setVertex(1, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx1));
        inertial_edge->setVertex(2, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gyro_vtx1));
        inertial_edge->setVertex(3, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_acc_vtx1));
        inertial_edge->setVertex(4, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx2));
        inertial_edge->setVertex(5, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx2));

        // if the third times of imu initialization hasn't been down or the keyframe is at the window boundary
        /*
            always enable robust kernel to decrease the randomness
            caused by bad landmarks.
        */
        // if(keyfrm == temporal_keyframes.back() || data::IMU_Preintegration::imu_initialize_times_ < 3)
        {
            ::g2o::RobustKernelHuber* rki = new ::g2o::RobustKernelHuber;
            inertial_edge->setRobustKernel(rki);
            if (keyfrm == temporal_keyframes.back())
                inertial_edge->setInformation(inertial_edge->information()*1e-2);
            // specific percentiles of chi-square distribution
            rki->setDelta(sqrt(16.92));
        }

        optimizer.addEdge(inertial_edge);

        g2o::EdgeGyroRW* gyro_rw_edge = new g2o::EdgeGyroRW();
        gyro_rw_edge->setVertex(0, temp_gyro_vtx1);
        gyro_rw_edge->setVertex(1, temp_gyro_vtx2);
        Mat33_t gyro_info = keyfrm_preintegration->covariance_.block<3, 3>(9, 9).inverse();
        gyro_rw_edge->setInformation(gyro_info);
        optimizer.addEdge(gyro_rw_edge);

        g2o::EdgeAccRW* acc_rw_edge = new g2o::EdgeAccRW();
        acc_rw_edge->setVertex(0, temp_acc_vtx1);
        acc_rw_edge->setVertex(1, temp_acc_vtx2);
        Mat33_t acc_info = keyfrm_preintegration->covariance_.block<3, 3>(12, 12).inverse();
        acc_rw_edge->setInformation(acc_info);
        optimizer.addEdge(acc_rw_edge);
    }

    // set landmark related vertices and edges
    const unsigned int edges_size = (temporal_keyframes.size() + fixed_keyframes.size()) * local_landmarks.size();

    // monocular edges
    std::vector<g2o::EdgeMono*> mono_edges;
    mono_edges.reserve(edges_size);

    std::vector<data::keyframe*> mono_keyframes;
    mono_keyframes.reserve(edges_size);

    std::vector<data::landmark*> mono_landmarks;
    mono_landmarks.reserve(edges_size);

    // stereo edges
    std::vector<g2o::EdgeStereo*> stereo_edges;
    stereo_edges.reserve(edges_size);

    std::vector<data::keyframe*> stereo_keyframes;
    stereo_keyframes.reserve(edges_size);

    std::vector<data::landmark*> stereo_landmarks;
    stereo_landmarks.reserve(edges_size);

    const float thHuberMono = sqrt(CHI2_MONO_THR);
    const float thHuberStereo = sqrt(CHI2_STEREO_THR);

    for (auto& landmark : local_landmarks) {
        ::g2o::VertexPointXYZ* visual_point_vtx = new ::g2o::VertexPointXYZ();
        visual_point_vtx->setEstimate(landmark->get_pos_in_world());
        int id = uint64ID_to_IMUvtxID(landmark->id_, IMU_VertexType::LandmarkVtx);
        visual_point_vtx->setId(id);
        visual_point_vtx->setMarginalized(true);
        optimizer.addVertex(visual_point_vtx);

        const std::map<data::keyframe*, unsigned int> observations = landmark->get_observations();
        for (auto& observation : observations) {
            data::keyframe* keyfrm = observation.first;
            if (!keyfrm->is_considered_ || keyfrm->will_be_erased())
                continue;

            const int left_index = observation.second;
            cv::KeyPoint keypoint;
            float inv_sigma_sq;
            float x_right_disparity;
            if (keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial) {
                try {
                    keypoint = keyfrm->undist_keypts_.at(left_index);
                    inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(keypoint.octave);
                } catch (std::out_of_range const& err) {
                    std::cout << err.what() << std::endl;
                    continue;
                }
                Vec2_t obs;
                obs << keypoint.pt.x, keypoint.pt.y;

                g2o::EdgeMono* mono_edge = new g2o::EdgeMono();
                ::g2o::OptimizableGraph::Vertex* temp_pose_vtx;
                int temp_pose_vtx_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
                temp_pose_vtx = dynamic_cast<::g2o::OptimizableGraph::Vertex*>(optimizer.vertex(temp_pose_vtx_id));
                mono_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(optimizer.vertex(id)));
                mono_edge->setVertex(1, temp_pose_vtx);
                mono_edge->setMeasurement(obs);
                mono_edge->setInformation(inv_sigma_sq * Mat22_t::Identity());

                ::g2o::RobustKernelHuber* rk = new ::g2o::RobustKernelHuber;
                mono_edge->setRobustKernel(rk);
                rk->setDelta(thHuberMono);

                optimizer.addEdge(mono_edge);
                mono_edges.emplace_back(mono_edge);
                mono_keyframes.emplace_back(keyfrm);
                mono_landmarks.emplace_back(landmark);
            } else {
                try {
                    keypoint = keyfrm->undist_keypts_.at(left_index);
                    x_right_disparity = keyfrm->stereo_x_right_.at(left_index);
                    inv_sigma_sq = keyfrm->inv_level_sigma_sq_.at(keypoint.octave);
                } catch (std::out_of_range const& err) {
                    std::cout << err.what() << std::endl;
                    continue;
                }
                Vec3_t obs;
                obs << keypoint.pt.x, keypoint.pt.y, x_right_disparity;

                g2o::EdgeStereo* stereo_edge = new g2o::EdgeStereo();
                ::g2o::OptimizableGraph::Vertex* temp_pose_vtx;
                int temp_pose_vtx_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
                temp_pose_vtx = dynamic_cast<::g2o::OptimizableGraph::Vertex*>(optimizer.vertex(temp_pose_vtx_id));
                stereo_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(optimizer.vertex(id)));
                stereo_edge->setVertex(1, temp_pose_vtx);
                stereo_edge->setMeasurement(obs);
                stereo_edge->setInformation(inv_sigma_sq * Mat33_t::Identity());

                ::g2o::RobustKernelHuber* rk = new ::g2o::RobustKernelHuber;
                stereo_edge->setRobustKernel(rk);
                rk->setDelta(thHuberStereo);

                optimizer.addEdge(stereo_edge);
                stereo_edges.emplace_back(stereo_edge);
                stereo_keyframes.emplace_back(keyfrm);
                stereo_landmarks.emplace_back(landmark);
            }
        }
    }

    // Optimize
    optimizer.initializeOptimization();
    optimizer.computeActiveErrors();
    double err = optimizer.activeRobustChi2();
    optimizer.optimize(iterations);
    double err_end = optimizer.activeRobustChi2();
    if (force_stop_flag)
        optimizer.setForceStopFlag(force_stop_flag);

    // check inlier observations
    const float chi2Mono2 = CHI2_MONO_THR;
    const float chi2Stereo2 = CHI2_STEREO_THR;
    std::vector<std::pair<data::keyframe*, data::landmark*>> to_erase_pairs;
    to_erase_pairs.reserve(std::max(mono_edges.size(), stereo_edges.size()));
    unsigned int index = 0;

    if (curr_keyfrm->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial) {
        // monocular
        for (auto& mono_edge : mono_edges) {
            data::landmark* landmark = mono_landmarks[index];
            if (landmark->will_be_erased()) {
                index++;
                continue;
            }

            // the multiplier of the threshold is an experience number for EuRoC dataset
            const bool is_close = (landmark->get_distance_to_cam_center() < 10.0);
            if ((mono_edge->chi2() > 1.05 * chi2Mono2 && !is_close) || (mono_edge->chi2() > 3 * chi2Mono2 && is_close) ||
                !mono_edge->is_depth_positive()) {
                data::keyframe* keyfrm = mono_keyframes[index];
                to_erase_pairs.emplace_back(std::make_pair(keyfrm, landmark));
            }
            index++;
        }
    } else {
        // stereo
        for (auto& stereo_edge : stereo_edges) {
            data::landmark* landmark = stereo_landmarks[index];
            if (landmark->will_be_erased()) {
                index++;
                continue;
            }
    
            if (stereo_edge->chi2() > chi2Stereo2) {
                data::keyframe* keyfrm = stereo_keyframes[index];
                to_erase_pairs.emplace_back(std::make_pair(keyfrm, landmark));
            }
            index++;
        }
    }

    // TODO: some convergence problems have been detected here
    if ((2 * err < err_end || std::isnan(err) || std::isnan(err_end)) && !is_large) {
        spdlog::warn("failed to do localBA with IMU, meet convergence issue");
        return;
    }

    // erase landmark for keyframe and erase observation for landmark
    for (auto& pair : to_erase_pairs) {
        data::keyframe* keyfrm = pair.first;
        data::landmark* landmark = pair.second;
        keyfrm->erase_landmark(landmark);
        landmark->erase_observation(keyfrm);
    }

    // reset optimization flags of fixed keyframes
    // will reset optimization flags of optimizable keyframes and landmarks
    // when recovering optimized data
    for (auto& keyfrm : fixed_keyframes) {
        keyfrm->is_considered_ = false;
        keyfrm->is_fixed_ = false;
    }

    // recover optimized data
    for (auto& keyfrm : temporal_keyframes) {
        int temp_pose_vtx_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
        g2o::VertexPose* temp_pose_vtx = dynamic_cast<g2o::VertexPose*>(optimizer.vertex(temp_pose_vtx_id));
        Mat44_t Tcw = Mat44_t::Identity();
        Tcw.block(0, 0, 3, 3) = temp_pose_vtx->estimate().Rcw_;
        Tcw.block(0, 3, 3, 1) = temp_pose_vtx->estimate().tcw_;
        keyfrm->set_cam_pose(Tcw);
        keyfrm->is_considered_ = false;
        keyfrm->is_fixed_ = false;

        if (keyfrm->imu_is_initialized_) {
            int velocity_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
            g2o::VertexVelocity* temp_velocity_vtx = dynamic_cast<g2o::VertexVelocity*>(optimizer.vertex(velocity_id));
            keyfrm->set_imu_velocity(temp_velocity_vtx->estimate());

            g2o::VertexGyroBias* temp_gyro_vtx;
            g2o::VertexAccBias* temp_acc_vtx;
            int temp_gyro_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx);
            int temp_acc_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx);
            temp_gyro_vtx = dynamic_cast<g2o::VertexGyroBias*>(optimizer.vertex(temp_gyro_id));
            temp_acc_vtx = dynamic_cast<g2o::VertexAccBias*>(optimizer.vertex(temp_acc_id));
            VecX_t imu_bias(6);
            imu_bias << temp_acc_vtx->estimate(), temp_gyro_vtx->estimate();
            keyfrm->set_new_imu_bias(imu_bias);
            if (keyfrm->id_ == temporal_keyframes.front()->id_)
                data::IMU_Preintegration::set_measurement_bias(imu_bias);
        }
    }

    for (auto& keyfrm : optcov_keyframes) {
        int temp_pose_vtx_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
        g2o::VertexPose* temp_pose_vtx = dynamic_cast<g2o::VertexPose*>(optimizer.vertex(temp_pose_vtx_id));
        Mat44_t Tcw = Mat44_t::Identity();
        Tcw.block(0, 0, 3, 3) = temp_pose_vtx->estimate().Rcw_;
        Tcw.block(0, 3, 3, 1) = temp_pose_vtx->estimate().tcw_;
        keyfrm->set_cam_pose(Tcw);
        keyfrm->is_considered_ = false;
        keyfrm->is_fixed_ = false;
    }

    for (auto& landmark : local_landmarks) {
        int vpt_id = uint64ID_to_IMUvtxID(landmark->id_, IMU_VertexType::LandmarkVtx);
        ::g2o::VertexPointXYZ* visual_point_vtx = dynamic_cast<::g2o::VertexPointXYZ*>(optimizer.vertex(vpt_id));
        landmark->set_pos_in_world(visual_point_vtx->estimate());
        landmark->is_considered_ = false;
        landmark->is_fixed_ = false;
        landmark->update_normal_and_depth();
    }

    spdlog::debug("{}: finish localBA with IMU", __func__);
}

}  // namespace optimize
}  // namespace openvslam
