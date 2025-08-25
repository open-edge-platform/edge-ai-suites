// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "imu_initializer.h"
#include "../data/imu.h"
#include "optimize/g2o/vec3_vertex.h"
#include "optimize/g2o/scale_vertex.h"
#include "imu_edge.h"
#include "optimize/g2o/vec3_vertex_container.h"
#include <g2o/core/block_solver.h>
#include <g2o/core/optimization_algorithm_levenberg.h>
#include <g2o/core/optimization_algorithm_gauss_newton.h>
#include <g2o/core/robust_kernel_impl.h>
#include <g2o/core/solver.h>
#include <g2o/core/sparse_optimizer.h>
#include <g2o/solvers/csparse/linear_solver_csparse.h>
#include <g2o/solvers/dense/linear_solver_dense.h>
#include <g2o/solvers/eigen/linear_solver_eigen.h>
#include <g2o/types/sba/types_six_dof_expmap.h>
#include "optimize/g2o/se3/shot_vertex_container.h"
#include <spdlog/spdlog.h>
#include "g2o/imubias_vertex.h"
#include "g2o/so3_vertex.h"
#include "g2o/imubias_vertex_container.h"
#include <g2o/core/sparse_block_matrix.h>
#include <unsupported/Eigen/MatrixFunctions>
#include "optimize/g2o/camera_pose_vertex.h"
#include "optimize/g2o/camera_pose_vertex_container.h"
#include "data/map_database.h"
#include "data/landmark.h"
#include "util/converter.h"
#include <chrono>
#include <fstream>

#define EPSILON                   0.00001
#define INERTIAL_OPTM_ITR1        200     // used in inertial only IMU initialization
#define INERTIAL_OPTM_ITR2        10      // used in scale refinement
#define BG_ERROR_THRESHOLD        0.01

namespace openvslam {
namespace optimize {

void inertial_only_optimize(std::vector<data::keyframe*>& keyframes, KeyframeID max_keyfrm_id, Mat33_t& Rwi,
                                 double& scale, Vec3_t& ba, Vec3_t& bg, bool is_monocular, double& acc_weight,
                                 double& gyro_weight)
{
    int iterations = INERTIAL_OPTM_ITR1;

    // Setup g2o optimizer
    ::g2o::SparseOptimizer optimizer;
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolverX::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolverX>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    if (gyro_weight > EPSILON)
        algorithm->setUserLambdaInit(1e3);

    optimizer.setAlgorithm(algorithm);

    // Set keyframe related vertices (fixed poses and optimizable velocities)
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id)
            continue;

        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(true);
        optimizer.addVertex(pose_vtx);

        g2o::VertexVelocity* velocity_vtx = new g2o::VertexVelocity(keyfrm);
        velocity_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx));
        velocity_vtx->setFixed(false);
        optimizer.addVertex(velocity_vtx);
    }

    // Set bias related vertices
    g2o::VertexGyroBias* gyro_vtx = new g2o::VertexGyroBias(keyframes.front());
    gyro_vtx->setId(uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx));
    gyro_vtx->setFixed(false);
    optimizer.addVertex(gyro_vtx);

    g2o::VertexAccBias* acc_vtx = new g2o::VertexAccBias(keyframes.front());
    acc_vtx->setId(uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx));
    acc_vtx->setFixed(false);
    optimizer.addVertex(acc_vtx);

    // Set bias related edges
    Vec3_t bias_weight;
    bias_weight.setZero();

    g2o::EdgePriorAcc* acc_edge = new g2o::EdgePriorAcc(bias_weight);
    acc_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(acc_vtx));
    acc_edge->setInformation(acc_weight * Mat33_t::Identity());
    optimizer.addEdge(acc_edge);

    g2o::EdgePriorGyro* gyro_edge = new g2o::EdgePriorGyro(bias_weight);
    gyro_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(gyro_vtx));
    gyro_edge->setInformation(gyro_weight * Mat33_t::Identity());
    optimizer.addEdge(gyro_edge);

    // Set gravity and scale vertices (optimizable scale for Monocular)
    g2o::VertexGDir* gravity_dir_vtx = new g2o::VertexGDir(Rwi);
    gravity_dir_vtx->setId(uint64ID_to_IMUvtxID(2, IMU_VertexType::CommonVtx));
    gravity_dir_vtx->setFixed(false);
    optimizer.addVertex(gravity_dir_vtx);

    g2o::VertexScale* scale_vtx = new g2o::VertexScale(scale);
    scale_vtx->setId(uint64ID_to_IMUvtxID(3, IMU_VertexType::CommonVtx));
    scale_vtx->setFixed(!is_monocular);
    optimizer.addVertex(scale_vtx);

    // Set graph edges
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id || keyfrm->will_be_erased())
            continue;

        if (keyfrm->pre_keyframe_ && keyfrm->pre_keyframe_->id_ <= max_keyfrm_id) {
            auto keyfrm_preintegration = keyfrm->get_imu_constraint().second;
            if (!keyfrm_preintegration) {
                spdlog::debug("keyframe {}: doesn't have preintegration in constraint pair", keyfrm->id_);
                continue;
            }

            data::keyframe* pre_keyframe = keyfrm->pre_keyframe_;
            keyfrm_preintegration->set_new_imu_bias(pre_keyframe->get_imu_bias());
            int temp_pose_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::PoseVtx);
            ::g2o::HyperGraph::Vertex* temp_pose_vtx1 = optimizer.vertex(temp_pose_vtx1_id);
            int temp_velocity_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::VelocityVtx);
            ::g2o::HyperGraph::Vertex* temp_velocity_vtx1 = optimizer.vertex(temp_velocity_vtx1_id);
            int temp_pose_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
            ::g2o::HyperGraph::Vertex* temp_pose_vtx2 = optimizer.vertex(temp_pose_vtx2_id);
            int temp_velocity_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
            ::g2o::HyperGraph::Vertex* temp_velocity_vtx2 = optimizer.vertex(temp_velocity_vtx2_id);
            int temp_gyro_vtx_id = uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_gyro_vtx = optimizer.vertex(temp_gyro_vtx_id);
            int temp_acc_vtx_id = uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_acc_vtx = optimizer.vertex(temp_acc_vtx_id);
            int temp_gravity_dir_vtx_id = uint64ID_to_IMUvtxID(2, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_gravity_dir_vtx = optimizer.vertex(temp_gravity_dir_vtx_id);
            int temp_scale_vtx_id = uint64ID_to_IMUvtxID(3, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_scale_vtx = optimizer.vertex(temp_scale_vtx_id);
            if (!temp_pose_vtx1 || !temp_velocity_vtx1 || !temp_pose_vtx2 || !temp_velocity_vtx2 ||
                !temp_gyro_vtx || !temp_acc_vtx || !temp_gravity_dir_vtx || !temp_scale_vtx) {
                std::cout << "Error " << temp_pose_vtx1 << ", " << temp_velocity_vtx1 << ", " <<
                             temp_pose_vtx2 << ", " << temp_velocity_vtx2 << ", " << temp_gyro_vtx <<
                             ", " << temp_acc_vtx << ", " << temp_gravity_dir_vtx <<
                             ", " << temp_scale_vtx << std::endl;
                continue;
            }

            g2o::EdgeInertialGS* inertial_edge = new g2o::EdgeInertialGS(keyfrm_preintegration);
            inertial_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx1));
            inertial_edge->setVertex(1, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx1));
            inertial_edge->setVertex(2, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gyro_vtx));
            inertial_edge->setVertex(3, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_acc_vtx));
            inertial_edge->setVertex(4, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx2));
            inertial_edge->setVertex(5, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx2));
            inertial_edge->setVertex(6, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gravity_dir_vtx));
            inertial_edge->setVertex(7, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_scale_vtx));
            optimizer.addEdge(inertial_edge);
        }
    }

    // Optimize
    optimizer.setVerbose(false);
    optimizer.initializeOptimization();
    optimizer.optimize(iterations);

    // Recover optimized data
    scale = scale_vtx->estimate();
    ba << acc_vtx->estimate();
    bg << gyro_vtx->estimate();
    Rwi = gravity_dir_vtx->estimate().Rwg_;

    VecX_t imu_bias(6);
    imu_bias << ba, bg;
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id)
            continue;

        KeyframeID velocity_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
        g2o::VertexVelocity* temp_velocity_vtx = dynamic_cast<g2o::VertexVelocity*>(optimizer.vertex(velocity_id));
        keyfrm->set_imu_velocity(temp_velocity_vtx->estimate());

        if ((keyfrm->get_imu_bias().tail(3) - bg).norm() > BG_ERROR_THRESHOLD) {
            keyfrm->set_new_imu_bias(imu_bias);
            auto keyfrm_preintegration = keyfrm->get_imu_constraint().second;
            if (keyfrm_preintegration)
                keyfrm_preintegration->re_pre_integrate_imu_measurement(imu_bias);
        } else {
            keyfrm->set_new_imu_bias(imu_bias);
        }
    }

    // Update last_bias_
    data::IMU_Preintegration::set_measurement_bias(imu_bias);
}

void inertial_only_optimize(data::map_database* map_db, KeyframeID max_keyfrm_id, Mat33_t& Rwi,
                                 double& scale)
{
    int iterations = INERTIAL_OPTM_ITR2;
    const std::vector<data::keyframe*> keyframes = map_db->get_all_keyframes();

    // Setup g2o optimizer
    ::g2o::SparseOptimizer optimizer;
    ::g2o::OptimizationAlgorithmGaussNewton* algorithm;
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolverX::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolverX>(std::move(linear_solver));
    algorithm  = new ::g2o::OptimizationAlgorithmGaussNewton(std::move(block_solver));
    optimizer.setAlgorithm(algorithm);

    // Set keyframe related vertices
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id || keyfrm->will_be_erased()) {
            spdlog::debug("keyframe {}: id is larged than max_id, or it will be erased", keyfrm->id_);
            continue;
        }

        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(true);
        optimizer.addVertex(pose_vtx);

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

    // Set gravity and scale vertice
    g2o::VertexGDir* gravity_dir_vtx = new g2o::VertexGDir(Rwi);
    gravity_dir_vtx->setId(uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx));
    gravity_dir_vtx->setFixed(false);
    optimizer.addVertex(gravity_dir_vtx);

    g2o::VertexScale* scale_vtx = new g2o::VertexScale(scale);
    scale_vtx->setId(uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx));
    scale_vtx->setFixed(false);
    optimizer.addVertex(scale_vtx);

    // Set graph edges
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id || keyfrm->will_be_erased())
            continue;

        if (keyfrm->pre_keyframe_ && keyfrm->pre_keyframe_->id_ <= max_keyfrm_id) {
            auto keyfrm_preintegration = keyfrm->get_imu_constraint().second;
            if (!keyfrm_preintegration) {
                spdlog::debug("keyframe {}: doesn't have preintegration in constraint pair", keyfrm->id_);
                continue;
            }

            data::keyframe* pre_keyframe = keyfrm->pre_keyframe_;
            int temp_pose_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::PoseVtx);
            ::g2o::HyperGraph::Vertex* temp_pose_vtx1 = optimizer.vertex(temp_pose_vtx1_id);
            int temp_velocity_vtx1_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::VelocityVtx);
            ::g2o::HyperGraph::Vertex* temp_velocity_vtx1 = optimizer.vertex(temp_velocity_vtx1_id);
            int temp_pose_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
            ::g2o::HyperGraph::Vertex* temp_pose_vtx2 = optimizer.vertex(temp_pose_vtx2_id);
            int temp_velocity_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
            ::g2o::HyperGraph::Vertex* temp_velocity_vtx2 = optimizer.vertex(temp_velocity_vtx2_id);
            int temp_gyro_vtx_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::GyroBiasVtx);
            ::g2o::HyperGraph::Vertex* temp_gyro_vtx = optimizer.vertex(temp_gyro_vtx_id);
            int temp_acc_vtx_id = uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::AccBiasVtx);
            ::g2o::HyperGraph::Vertex* temp_acc_vtx = optimizer.vertex(temp_acc_vtx_id);
            int temp_gravity_dir_vtx_id = uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_gravity_dir_vtx = optimizer.vertex(temp_gravity_dir_vtx_id);
            int temp_scale_vtx_id = uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx);
            ::g2o::HyperGraph::Vertex* temp_scale_vtx = optimizer.vertex(temp_scale_vtx_id);
            if (!temp_pose_vtx1 || !temp_velocity_vtx1 || !temp_pose_vtx2 || !temp_velocity_vtx2 ||
                !temp_gyro_vtx || !temp_acc_vtx || !temp_gravity_dir_vtx || !temp_scale_vtx) {
                std::cout << "Error " << temp_pose_vtx1 << ", " << temp_velocity_vtx1 << ", " <<
                             temp_pose_vtx2 << ", " << temp_velocity_vtx2 << ", " << temp_gyro_vtx <<
                             ", " << temp_acc_vtx << ", " << temp_gravity_dir_vtx <<
                             ", " << temp_scale_vtx << std::endl;
                continue;
            }

            g2o::EdgeInertialGS* inertial_edge = new g2o::EdgeInertialGS(keyfrm_preintegration);
            inertial_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx1));
            inertial_edge->setVertex(1, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx1));
            inertial_edge->setVertex(2, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gyro_vtx));
            inertial_edge->setVertex(3, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_acc_vtx));
            inertial_edge->setVertex(4, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx2));
            inertial_edge->setVertex(5, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx2));
            inertial_edge->setVertex(6, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gravity_dir_vtx));
            inertial_edge->setVertex(7, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_scale_vtx));
            ::g2o::RobustKernelHuber* rki = new ::g2o::RobustKernelHuber;
            inertial_edge->setRobustKernel(rki);
            // specific percentiles of chi-square distribution
            rki->setDelta(1.0);
            optimizer.addEdge(inertial_edge);
        }
    }

    // Optimize
    optimizer.setVerbose(false);
    optimizer.initializeOptimization();
    optimizer.optimize(iterations);

    // Recover optimized data
    scale = scale_vtx->estimate();
    Rwi = gravity_dir_vtx->estimate().Rwg_;
}
void visual_inertial_optimize(data::map_database* map_db, KeyframeID max_keyfrm_id, int iterations,
                                   bool is_monocular, bool is_gyro_acc_init, double acc_weight, double gyro_weight)
{
    const std::vector<data::keyframe*> keyframes = map_db->get_all_keyframes();
    const std::vector<data::landmark*> landmarks = map_db->get_all_landmarks();

    // Setup g2o optimizer
    ::g2o::SparseOptimizer optimizer;
    auto linear_solver = ::std::make_unique<::g2o::LinearSolverEigen<::g2o::BlockSolverX::PoseMatrixType>>();
    auto block_solver = ::std::make_unique<::g2o::BlockSolverX>(std::move(linear_solver));
    auto algorithm = new ::g2o::OptimizationAlgorithmLevenberg(std::move(block_solver));

    algorithm->setUserLambdaInit(1e3);
    optimizer.setAlgorithm(algorithm);
    optimizer.setVerbose(false);

    // Set keyframe related vertices
    data::keyframe* max_keyframe = nullptr;
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id) {
            continue;
        }

        if (keyfrm->id_ == max_keyfrm_id) {
            max_keyframe = keyfrm;
        }

        g2o::VertexPose* pose_vtx = new g2o::VertexPose(keyfrm);
        pose_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx));
        pose_vtx->setFixed(true);
        optimizer.addVertex(pose_vtx);

        if (keyfrm->imu_is_initialized_) {
            g2o::VertexVelocity* velocity_vtx = new g2o::VertexVelocity(keyfrm);
            velocity_vtx->setId(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx));
            velocity_vtx->setFixed(false);
            optimizer.addVertex(velocity_vtx);
            if (!is_gyro_acc_init) {
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
    }

    // Set bias related vertices
    if (!max_keyframe) {
        spdlog::warn("keyframe with maximum ID {} isn't in the map database", max_keyfrm_id);
        return;
    }

    if (is_gyro_acc_init) {
        g2o::VertexGyroBias* gyro_vtx = new g2o::VertexGyroBias(max_keyframe);
        gyro_vtx->setId(uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx));
        gyro_vtx->setFixed(false);
        optimizer.addVertex(gyro_vtx);

        g2o::VertexAccBias* acc_vtx = new g2o::VertexAccBias(max_keyframe);
        acc_vtx->setId(uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx));
        acc_vtx->setFixed(false);
        optimizer.addVertex(acc_vtx);
    }

    // Set graph edges
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id || keyfrm->will_be_erased())
            continue;

        data::keyframe* pre_keyframe = keyfrm->pre_keyframe_;
        if (!pre_keyframe || pre_keyframe->id_ > max_keyfrm_id)
            continue;

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
        ::g2o::HyperGraph::Vertex* temp_gyro_vtx1 = nullptr;
        ::g2o::HyperGraph::Vertex* temp_acc_vtx1 = nullptr;
        ::g2o::HyperGraph::Vertex* temp_gyro_vtx2 = nullptr;
        ::g2o::HyperGraph::Vertex* temp_acc_vtx2 = nullptr;
        if (!is_gyro_acc_init) {
            temp_gyro_vtx1 = optimizer.vertex(uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::GyroBiasVtx));
            temp_acc_vtx1 = optimizer.vertex(uint64ID_to_IMUvtxID(pre_keyframe->id_, IMU_VertexType::AccBiasVtx));
            temp_gyro_vtx2 = optimizer.vertex(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx));
            temp_acc_vtx2 = optimizer.vertex(uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx));
        } else {
            temp_gyro_vtx1 = optimizer.vertex(uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx));
            temp_acc_vtx1 = optimizer.vertex(uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx));
        }
        int temp_pose_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
        ::g2o::HyperGraph::Vertex* temp_pose_vtx2 = optimizer.vertex(temp_pose_vtx2_id);
        int temp_velocity_vtx2_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
        ::g2o::HyperGraph::Vertex* temp_velocity_vtx2 = optimizer.vertex(temp_velocity_vtx2_id);
        if (!is_gyro_acc_init) {
            if (!temp_pose_vtx1 || !temp_velocity_vtx1 || !temp_pose_vtx2 || !temp_velocity_vtx2 ||
                !temp_gyro_vtx1 || !temp_acc_vtx1 || !temp_gyro_vtx2 || !temp_acc_vtx2) {
                std::cout << "Error " << temp_pose_vtx1 << ", " << temp_velocity_vtx1 << ", " <<
                             temp_pose_vtx2 << ", " << temp_velocity_vtx2 << ", " << temp_gyro_vtx1 <<
                             ", " << temp_acc_vtx1 << ", " << temp_gyro_vtx2 << ", " << temp_acc_vtx2 << std::endl;
                continue;
            }
        } else {
            if (!temp_pose_vtx1 || !temp_velocity_vtx1 || !temp_pose_vtx2 || !temp_velocity_vtx2 ||
                !temp_gyro_vtx1 || !temp_acc_vtx1) {
                std::cout << "Error " << temp_pose_vtx1 << ", " << temp_velocity_vtx1 << ", " <<
                             temp_pose_vtx2 << ", " << temp_velocity_vtx2 << ", " << temp_gyro_vtx1 <<
                             ", " << temp_acc_vtx1 << std::endl;
                continue;
            }
        }

        g2o::EdgeInertial* inertial_edge = new g2o::EdgeInertial(keyfrm_preintegration);
        inertial_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx1));
        inertial_edge->setVertex(1, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx1));
        inertial_edge->setVertex(2, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gyro_vtx1));
        inertial_edge->setVertex(3, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_acc_vtx1));
        inertial_edge->setVertex(4, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_pose_vtx2));
        inertial_edge->setVertex(5, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_velocity_vtx2));

        ::g2o::RobustKernelHuber* rki = new ::g2o::RobustKernelHuber;
        inertial_edge->setRobustKernel(rki);
        // specific percentiles of chi-square distribution
        rki->setDelta(sqrt(16.92));

        optimizer.addEdge(inertial_edge);

        if (!is_gyro_acc_init) {
            g2o::EdgeGyroRW* gyro_rw_edge = new g2o::EdgeGyroRW();
            gyro_rw_edge->setVertex(0, temp_gyro_vtx1);
            gyro_rw_edge->setVertex(1, temp_gyro_vtx2);
            Mat33_t gyro_info = keyfrm_preintegration->covariance_.block<3, 3>(9, 9).inverse();
            gyro_rw_edge->setInformation(gyro_info);
            gyro_rw_edge->computeError();
            optimizer.addEdge(gyro_rw_edge);

            g2o::EdgeAccRW* acc_rw_edge = new g2o::EdgeAccRW();
            acc_rw_edge->setVertex(0, temp_acc_vtx1);
            acc_rw_edge->setVertex(1, temp_acc_vtx2);
            Mat33_t acc_info = keyfrm_preintegration->covariance_.block<3, 3>(12, 12).inverse();
            acc_rw_edge->setInformation(acc_info);
            acc_rw_edge->computeError();
            optimizer.addEdge(acc_rw_edge);
        }
    }

    // Set common bias related edges
    if (is_gyro_acc_init) {
        int temp_gyro_vtx_id = uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx);
        ::g2o::HyperGraph::Vertex* temp_gyro_vtx = optimizer.vertex(temp_gyro_vtx_id);
        int temp_acc_vtx_id = uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx);
        ::g2o::HyperGraph::Vertex* temp_acc_vtx = optimizer.vertex(temp_acc_vtx_id);

        // Add priority to common bias
        Vec3_t bias_weight;
        bias_weight.setZero();

        g2o::EdgePriorAcc* acc_edge = new g2o::EdgePriorAcc(bias_weight);
        acc_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_acc_vtx));
        acc_edge->setInformation(acc_weight * Mat33_t::Identity());
        optimizer.addEdge(acc_edge);

        g2o::EdgePriorGyro* gyro_edge = new g2o::EdgePriorGyro(bias_weight);
        gyro_edge->setVertex(0, dynamic_cast<::g2o::OptimizableGraph::Vertex*>(temp_gyro_vtx));
        gyro_edge->setInformation(gyro_weight * Mat33_t::Identity());
        optimizer.addEdge(gyro_edge);
    }

    // Set landmark related vertices and edges
    const double thHuberMono = sqrt(5.991);
    const double thHuberStereo = sqrt(7.815);
    for (auto& landmark : landmarks) {
        ::g2o::VertexPointXYZ* visual_point_vtx = new ::g2o::VertexPointXYZ();
        visual_point_vtx->setEstimate(landmark->get_pos_in_world());
        int id = uint64ID_to_IMUvtxID(landmark->id_, IMU_VertexType::LandmarkVtx);
        visual_point_vtx->setId(id);
        visual_point_vtx->setMarginalized(true);
        optimizer.addVertex(visual_point_vtx);

        const std::map<data::keyframe*, unsigned int> observations = landmark->get_observations();
        for (auto& observation : observations) {
            data::keyframe* keyfrm = observation.first;
            if (keyfrm->id_ > max_keyfrm_id || keyfrm->will_be_erased())
                continue;

            const int left_index = observation.second;
            cv::KeyPoint keypoint;
            float inv_sigma_sq;
            float x_right_disparity;
            if (is_monocular) {
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
            }
        }
    }

    // Optimize
    optimizer.initializeOptimization();
    optimizer.optimize(iterations);

    // Recover optimized data
    for (auto& keyfrm : keyframes) {
        if (keyfrm->id_ > max_keyfrm_id)
            continue;

        int temp_pose_vtx_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::PoseVtx);
        g2o::VertexPose* temp_pose_vtx = dynamic_cast<g2o::VertexPose*>(optimizer.vertex(temp_pose_vtx_id));
        Mat44_t Tcw = Mat44_t::Identity();
        Tcw.block(0, 0, 3, 3) = temp_pose_vtx->estimate().Rcw_;
        Tcw.block(0, 3, 3, 1) = temp_pose_vtx->estimate().tcw_;
        keyfrm->set_cam_pose(Tcw);

        if (keyfrm->imu_is_initialized_) {
            int velocity_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::VelocityVtx);
            g2o::VertexVelocity* temp_velocity_vtx = dynamic_cast<g2o::VertexVelocity*>(optimizer.vertex(velocity_id));
            keyfrm->set_imu_velocity(temp_velocity_vtx->estimate());

            g2o::VertexGyroBias* temp_gyro_vtx;
            g2o::VertexAccBias* temp_acc_vtx;
            if (!is_gyro_acc_init) {
                int temp_gyro_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::GyroBiasVtx);
                int temp_acc_id = uint64ID_to_IMUvtxID(keyfrm->id_, IMU_VertexType::AccBiasVtx);
                temp_gyro_vtx = dynamic_cast<g2o::VertexGyroBias*>(optimizer.vertex(temp_gyro_id));
                temp_acc_vtx = dynamic_cast<g2o::VertexAccBias*>(optimizer.vertex(temp_acc_id));
            } else {
                int temp_gyro_id = uint64ID_to_IMUvtxID(0, IMU_VertexType::CommonVtx);
                int temp_acc_id = uint64ID_to_IMUvtxID(1, IMU_VertexType::CommonVtx);
                temp_gyro_vtx = dynamic_cast<g2o::VertexGyroBias*>(optimizer.vertex(temp_gyro_id));
                temp_acc_vtx = dynamic_cast<g2o::VertexAccBias*>(optimizer.vertex(temp_acc_id));
            }
            VecX_t imu_bias(6);
            imu_bias << temp_acc_vtx->estimate(), temp_gyro_vtx->estimate();
            keyfrm->set_new_imu_bias(imu_bias);
            if (keyfrm->id_ == max_keyfrm_id)
                data::IMU_Preintegration::set_measurement_bias(imu_bias);
        }
    }

    for (auto& landmark : landmarks) {
        int vpt_id = uint64ID_to_IMUvtxID(landmark->id_, IMU_VertexType::LandmarkVtx);
        ::g2o::VertexPointXYZ* visual_point_vtx = dynamic_cast<::g2o::VertexPointXYZ*>(optimizer.vertex(vpt_id));
        landmark->set_pos_in_world(visual_point_vtx->estimate());
        landmark->update_normal_and_depth();
    }
}

}  // namespace optimize

}  // namespace openvslam
