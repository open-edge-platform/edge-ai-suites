// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "optimize/pose_optimizer.h"
#include "optimize/g2o/se3/pose_opt_edge_wrapper.h"
#include "optimize/g2o/se3/pose_graph_edge.h"
#include "util/converter.h"

#include "optimize/g2o/se3/edge_lidar_pose.h"

#include <vector>
#include <mutex>

#include <Eigen/StdVector>
#include <g2o/core/solver.h>
#include <g2o/core/block_solver.h>
#include <g2o/core/sparse_optimizer.h>
#include <g2o/core/robust_kernel_impl.h>
#include <g2o/core/sparse_block_matrix.h>
#include <g2o/solvers/eigen/linear_solver_eigen.h>
#include <g2o/solvers/dense/linear_solver_dense.h>
#include <g2o/solvers/csparse/linear_solver_csparse.h>
#include <g2o/core/optimization_algorithm_levenberg.h>

#include <spdlog/spdlog.h>
#include <spdlog/fmt/ostr.h>

extern bool is_server_node;

constexpr float chi_sq_2D = 5.99146;
constexpr float chi_sq_3D = 7.81473;

namespace openvslam {
namespace optimize {

pose_optimizer::pose_optimizer(camera::setup_type_t camera_type, bool use_odom, bool is_localization, data::map_database* map_db,
                               const unsigned int num_trials, const unsigned int num_each_iter)
    : use_odom_(use_odom),
      is_localization_(is_localization),
      map_db_(map_db),
      num_trials_(num_trials),
      num_each_iter_(num_each_iter)
{
    obs_thr_ = use_odom_ && is_localization_ ? 2 : 5;
    set_camera_type(camera_type);
    if (is_server_node)
        optimize_node_ = &pose_optimizer::optimize_server;
    else
        optimize_node_ = &pose_optimizer::optimize_tracker;
}

void pose_optimizer::set_camera_type(camera::setup_type_t camera_type) {
    const float sqrt_chi_sq_2D = std::sqrt(chi_sq_2D);
    const float sqrt_chi_sq_3D = std::sqrt(chi_sq_3D);
    camera_type_ = camera_type;
    sqrt_chi_sq_ =
        (camera_type_ == camera::setup_type_t::Monocular || camera_type_ == camera::setup_type_t::Monocular_Inertial)
            ? sqrt_chi_sq_2D
            : sqrt_chi_sq_3D;
}

unsigned int pose_optimizer::optimize(data::frame& frm, bool compute_covariance, data::frame* last_lidar_frame,
                                      Eigen::Matrix4d* tf_lidar_camera) const
{
    return std::invoke(optimize_node_, this, frm, compute_covariance, last_lidar_frame, tf_lidar_camera);
}

unsigned int pose_optimizer::optimize_tracker(data::frame& frm, bool compute_covariance, data::frame* last_lidar_frame,
                                              Eigen::Matrix4d* tf_lidar_camera) const
{
    // 1. optimizerを構築

    std::unique_ptr<::g2o::BlockSolver_6_3> block_solver;
    // default eigen solver cannot produce covariance from g2o, so will use csparse solver when we need covariance
    if (compute_covariance) {
        auto linear_solver = ::std::make_unique<::g2o::LinearSolverCSparse<::g2o::BlockSolver_6_3::PoseMatrixType>>();
        // TODO rtabmap set as false for all solvers, but shouldn't cause problem here as only one vertex in the graph
        // linear_solver->setBlockOrdering(false);
        block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    } else {
        auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolver_6_3::PoseMatrixType>>();
        block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    }
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);

    unsigned int num_init_obs = 0;

    // 2. frameをg2oのvertexに変換してoptimizerにセットする
    // convert frame to g2o vertex and set it in optimizer

    auto frm_vtx = new g2o::se3::shot_vertex();
    frm_vtx->setId(keyframeID_to_vertexID(frm.id_ + 1));
    frm_vtx->setEstimate(util::converter::to_g2o_SE3(frm.cam_pose_cw_));
    frm_vtx->setFixed(false);
    optimizer.addVertex(frm_vtx);

    const unsigned int num_keypts = frm.num_keypts_;

    // 3. landmarkのvertexをreprojection edgeで接続する

    // reprojection edgeのcontainer
    using pose_opt_edge_wrapper = g2o::se3::pose_opt_edge_wrapper<data::frame>;
    std::vector<pose_opt_edge_wrapper> pose_opt_edge_wraps;
    pose_opt_edge_wraps.reserve(num_keypts);
    for (unsigned int idx = 0; idx < num_keypts; ++idx) {
        auto lm = frm.landmarks_.at(idx);
        if (!lm) {
            continue;
        }
        if (unlikely(lm->will_be_erased())) {
            continue;
        }

        ++num_init_obs;
        frm.outlier_flags_.at(idx) = false;

        // frameのvertexをreprojection edgeで接続する
        const auto& undist_keypt = frm.undist_keypts_.at(idx);
        const float x_right = frm.stereo_x_right_.at(idx);
        const float inv_sigma_sq = frm.inv_level_sigma_sq_.at(undist_keypt.octave);
        const float sqrt_chi_sq = sqrt_chi_sq_;
        auto pose_opt_edge_wrap = pose_opt_edge_wrapper(&frm, frm_vtx, lm->get_pos_in_world(), idx, undist_keypt.pt.x,
                                                        undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
        pose_opt_edge_wraps.push_back(pose_opt_edge_wrap);
        optimizer.addEdge(pose_opt_edge_wrap.edge_);
    }

    // Add odom edge
    if (map_db_ && use_odom_ && is_localization_) {
        // use origin_keyfrm from map database as reference keyframe to construct odom edge
        auto kf1 = map_db_->odom_origin_keyfrm_;
        auto origin_keyfrm_vtx = new g2o::se3::shot_vertex();
        origin_keyfrm_vtx->setId(keyframeID_to_vertexID(kf1->id_));
        origin_keyfrm_vtx->setEstimate(util::converter::to_g2o_SE3(kf1->get_cam_pose()));
        origin_keyfrm_vtx->setFixed(true);
        optimizer.addVertex(origin_keyfrm_vtx);

        Eigen::Matrix4d T21 = Eigen::Matrix4d::Identity();
        Eigen::Matrix4d odom1 = kf1->odom_;
        Eigen::Matrix4d odom2 = frm.odom_;

        if (odom1 == Eigen::Matrix4d::Identity() || odom2 == Eigen::Matrix4d::Identity()) {
            spdlog::warn("Invalid odom data in pose optimizer!");
        } else {
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
            edge->setVertex(0, origin_keyfrm_vtx);
            edge->setVertex(1, frm_vtx);
            edge->setMeasurement(::g2o::SE3Quat(T21.block(0, 0, 3, 3), T21.block(0, 3, 3, 1)));
            // TODO: change the ratio
            MatRC_t<6, 6> information = MatRC_t<6, 6>::Identity();
            // constrain the rotation part
            information.block<3, 3>(0, 0) *= 1e6;
            // constrain the translation part
            information.block<3, 3>(3, 3) *= 1e6;
            edge->setInformation(information);
            optimizer.addEdge(edge);
        }
    }

    // Phase 1
    // In the feature_extraction_module: everytime a lidar frame is recived with an image frame, we set
    // the lidar_landmarks_.updated to true.  This way, we know that this image frame also has lidar data
    // so here, if the current image frame has lidar data, we want to do the bundle adjustment based on
    // both the lidar and image.
    // in order to know if we are working with two consecutive lidar frames, we have an id for each lidar frame
    // so we only want to do the BA based on lidar and image, if the two lidar frames are consecutive
    // to check for this condtion:  last_lidar_frame->get_prev_lidar_cam_pose().second == (frm.lidar_frame_id_-1)
    if (frm.is_lidar_enable() && frm.lidar_landmarks_.updated && last_lidar_frame != NULL &&
        last_lidar_frame->lidar_frame_id_ == (frm.lidar_frame_id_ - 1)) {
        Eigen::Matrix3d R_cl = tf_lidar_camera->block(0, 0, 3, 3);
        Eigen::Vector3d t_cl = tf_lidar_camera->block(0, 3, 3, 1);
        // Sorting the matched points based on distance value.  The points with smaller distance value
        // are the highest confidence matched points.
        std::sort(
            frm.matched_feature_points_.begin(), frm.matched_feature_points_.end(),
            [](const std::tuple<cv::Point2d, cv::Point2d, double>& a,
               const std::tuple<cv::Point2d, cv::Point2d, double>& b) { return std::get<2>(a) < std::get<2>(b); });

        for (size_t i = 0; i < frm.matched_feature_points_.size(); i++) {
            std::tuple matched_points = frm.matched_feature_points_[i];
            // prev_p_l:  Previous lidar points in lidar frame
            // it's a 2D lidar, the z component is where the lidar is located
            // in this case the z is zero with respect to lidar frame.
            Eigen::Vector3d prev_p_l(std::get<0>(matched_points).x, std::get<0>(matched_points).y, 0.);
            // curr_p_l:  Current lidar points in lidar frame
            Eigen::Vector3d curr_p_l(std::get<1>(matched_points).x, std::get<1>(matched_points).y, 0.);
            // prev_p_c: Previous frame lidar points in camera frame
            Eigen::Vector3d prev_p_c = (R_cl * prev_p_l + t_cl);
            Eigen::Matrix4d T_prev_cam_pose_inv = last_lidar_frame->get_cam_pose().inverse();
            Eigen::Matrix3d R_prev = T_prev_cam_pose_inv.block(0, 0, 3, 3);
            Eigen::Vector3d t_prev = T_prev_cam_pose_inv.block(0, 3, 3, 1);

            Eigen::Vector3d landmark_position_in_world_frame = R_prev * prev_p_c + t_prev;
            g2o::se3::EdgeLidarPose* lidar_edge = new g2o::se3::EdgeLidarPose(landmark_position_in_world_frame);
            lidar_edge->setVertex(0, frm_vtx);
            // measurement should be landmark position in current frame
            lidar_edge->setMeasurement(R_cl * curr_p_l + t_cl);
            lidar_edge->setInformation(Mat33_t::Identity() * (25000));
            optimizer.addEdge(lidar_edge);
        }
    }

    if (num_init_obs < obs_thr_) {
        return 0;
    }

    // 4. robust BAを実行する

    unsigned int num_bad_obs = 0;
    for (unsigned int trial = 0; trial < num_trials_; ++trial) {
        optimizer.setVerbose(false);
        optimizer.initializeOptimization();
        optimizer.optimize(num_each_iter_);

        num_bad_obs = 0;

        for (auto& pose_opt_edge_wrap : pose_opt_edge_wraps) {
            auto edge = pose_opt_edge_wrap.edge_;

            if (frm.outlier_flags_.at(pose_opt_edge_wrap.idx_)) {
                edge->computeError();
            }

            if (pose_opt_edge_wrap.is_monocular_) {
                if (chi_sq_2D < edge->chi2()) {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = true;
                    pose_opt_edge_wrap.set_as_outlier();
                    ++num_bad_obs;
                    // spdlog::debug("edge error is {}, standard is {}", edge->chi2(), chi_sq_2D);
                } else {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = false;
                    pose_opt_edge_wrap.set_as_inlier();
                }
            } else {
                if (chi_sq_3D < edge->chi2()) {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = true;
                    pose_opt_edge_wrap.set_as_outlier();
                    ++num_bad_obs;
                } else {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = false;
                    pose_opt_edge_wrap.set_as_inlier();
                }
            }

            if (trial == num_trials_ - 2) {
                edge->setRobustKernel(nullptr);
            }
        }

        if (num_init_obs - num_bad_obs < 5) {
            break;
        }
    }

    spdlog::debug("num_bad_obs: {}, num_init_obs: {}", num_bad_obs, num_init_obs);
    // 5. 情報を更新
    frm.set_cam_pose(frm_vtx->estimate());

    // get covariance matrix of current frame from g2o
    if (compute_covariance) {
        Mat66_t covariance = Mat66_t::Identity();
        ::g2o::SparseBlockMatrix<Dym_Mat_t> spinv;
        optimizer.computeMarginals(spinv, frm_vtx);
        // spdlog::debug("spinv is\n {}", spinv);
        if (frm_vtx->hessianIndex() >= 0 && frm_vtx->hessianIndex() < (int)spinv.blockCols().size()) {
            ::g2o::SparseBlockMatrix<Dym_Mat_t>::SparseMatrixBlock* block =
                spinv.blockCols()[frm_vtx->hessianIndex()].begin()->second;
            if (block && block->cols() == 6 && block->cols() == 6)
                memcpy(covariance.data(), block->data(), covariance.size() * sizeof(double));
            // spdlog::debug("covariance is\n {}", covariance);
            frm.covariance_matrix_ = covariance;
        }
    }

    return num_init_obs - num_bad_obs;
}

// compute_covariance flag, last Lidar frame and transformation of Lidar to camera are not used on server side
unsigned int pose_optimizer::optimize_server(data::frame& frm, bool /* compute_covariance */,
                                             data::frame* /* last_lidar_frame */,
                                             Eigen::Matrix4d* /* tf_lidar_camera */) const
{
    const int min_inlier_thr = 20;
    // 1. optimizerを構築

    auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolver_6_3::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolver_6_3>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    ::g2o::SparseOptimizer optimizer;
    optimizer.setAlgorithm(algorithm);

    unsigned int num_init_obs = 0;

    // 2. frameをg2oのvertexに変換してoptimizerにセットする

    auto frm_vtx = new g2o::se3::shot_vertex();
    frm_vtx->setId(keyframeID_to_vertexID(frm.id_));
    frm_vtx->setEstimate(util::converter::to_g2o_SE3(frm.cam_pose_cw_));
    frm_vtx->setFixed(false);
    optimizer.addVertex(frm_vtx);

    const unsigned int num_keypts = frm.num_keypts_;

    // 3. landmarkのvertexをreprojection edgeで接続する

    // reprojection edgeのcontainer
    using pose_opt_edge_wrapper = g2o::se3::pose_opt_edge_wrapper<data::frame>;
    std::vector<pose_opt_edge_wrapper> pose_opt_edge_wraps;
    pose_opt_edge_wraps.reserve(num_keypts);

    for (unsigned int idx = 0; idx < num_keypts; ++idx) {
        auto lm = frm.landmarks_.at(idx);
        if (!lm) {
            continue;
        }
        if (unlikely(lm->will_be_erased())) {
            continue;
        }

        ++num_init_obs;
        frm.outlier_flags_.at(idx) = false;

        // frameのvertexをreprojection edgeで接続する
        const auto& undist_keypt = frm.undist_keypts_.at(idx);
        const float x_right = frm.stereo_x_right_.at(idx);
        const float inv_sigma_sq = frm.inv_level_sigma_sq_.at(undist_keypt.octave);
        const float sqrt_chi_sq = sqrt_chi_sq_;
        auto pose_opt_edge_wrap = pose_opt_edge_wrapper(&frm, frm_vtx, lm->get_pos_in_world(), idx, undist_keypt.pt.x,
                                                        undist_keypt.pt.y, x_right, inv_sigma_sq, sqrt_chi_sq);
        pose_opt_edge_wraps.push_back(pose_opt_edge_wrap);
        optimizer.addEdge(pose_opt_edge_wrap.edge_);
    }

    if (num_init_obs < obs_thr_) {
        return 0;
    }

    // 4. robust BAを実行する

    unsigned int num_bad_obs = 0;
    for (unsigned int trial = 0; trial < num_trials_; ++trial) {
        optimizer.initializeOptimization();
        optimizer.optimize(num_each_iter_);

        num_bad_obs = 0;

        for (auto& pose_opt_edge_wrap : pose_opt_edge_wraps) {
            auto edge = pose_opt_edge_wrap.edge_;

            if (frm.outlier_flags_.at(pose_opt_edge_wrap.idx_)) {
                edge->computeError();
            }

            if (pose_opt_edge_wrap.is_monocular_) {
                if (chi_sq_2D < edge->chi2()) {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = true;
                    pose_opt_edge_wrap.set_as_outlier();
                    ++num_bad_obs;
                    // spdlog::debug("edge error is {}, standard is {}", edge->chi2(), chi_sq_2D);
                } else {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = false;
                    pose_opt_edge_wrap.set_as_inlier();
                }
            } else {
                if (chi_sq_3D < edge->chi2()) {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = true;
                    pose_opt_edge_wrap.set_as_outlier();
                    ++num_bad_obs;
                } else {
                    frm.outlier_flags_.at(pose_opt_edge_wrap.idx_) = false;
                    pose_opt_edge_wrap.set_as_inlier();
                }
            }

            if (trial == num_trials_ - 2) {
                edge->setRobustKernel(nullptr);
            }
        }

        if (num_init_obs - num_bad_obs < 5) {
            break;
        }
    }

    spdlog::debug("num_bad_obs: {}, num_init_obs: {}", num_bad_obs, num_init_obs);
    // 5. 情報を更新
    if (num_init_obs - num_bad_obs > min_inlier_thr) frm.set_cam_pose(frm_vtx->estimate());

    return num_init_obs - num_bad_obs;
}

}  // namespace optimize
}  // namespace openvslam
