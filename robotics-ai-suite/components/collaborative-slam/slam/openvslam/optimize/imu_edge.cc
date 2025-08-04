// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "imu_edge.h"
#include <g2o/types/slam3d/isometry3d_mappings.h>
#include <g2o/types/slam3d/vertex_se3.h>
#include "optimize/g2o/sim3/shot_vertex.h"
#include <iostream>
#include <spdlog/spdlog.h>
#include <map>
#include <unsupported/Eigen/MatrixFunctions>
#include "optimize/g2o/camera_pose_vertex.h"
#include "optimize/g2o/vec3_vertex.h"
#include "g2o/imubias_vertex.h"

#define GRAVITY_VALUE 9.81
#define INERTIAL_EDGE_EPSILON 1e-12

namespace openvslam {

const Eigen::Vector3d gI = Eigen::Vector3d(0, 0, -GRAVITY_VALUE);

namespace optimize {

namespace g2o {

ImuCamPose::ImuCamPose(Keyframe* pKF) : its_(0)
{
    // Load IMU pose
    tcw_ = pKF->get_cam_pose().block(0, 3, 3, 1);
    Rcw_ = pKF->get_cam_pose().block(0, 0, 3, 3);
    twb_ = pKF->get_imu_position();
    Rwb_ = pKF->get_imu_rotation();

    camera_ = static_cast<camera::perspective*>(pKF->camera_);

    // For posegraph 4DoF
    Rwb0_ = Rwb_;
    DR_.setIdentity();
}

ImuCamPose::ImuCamPose(Frame* pF) : its_(0)
{
    // Load IMU pose
    tcw_ = pF->get_cam_pose().block(0, 3, 3, 1);
    Rcw_ = pF->get_cam_pose().block(0, 0, 3, 3);
    twb_ = pF->get_imu_position();
    Rwb_ = pF->get_imu_rotation();

    camera_ = static_cast<camera::perspective*>(pF->camera_);

    // For posegraph 4DoF
    Rwb0_ = Rwb_;
    DR_.setIdentity();
}

ImuCamPose::ImuCamPose(Eigen::Matrix3d& Rwc, Eigen::Vector3d& twc, Keyframe* pKF) : its_(0)
{
    // This is only for posegrpah, we do not care about multicamera
    Rcw_ = Rwc.transpose();
    tcw_ = -Rcw_ * twc;
    twb_ = Rwc * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1) + twc;
    Rwb_ = Rwc * data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);

    camera_ = dynamic_cast<camera::perspective*>(pKF->camera_);

    // For posegraph 4DoF
    Rwb0_ = Rwb_;
    DR_.setIdentity();
}

void ImuCamPose::Update(const double* pu)
{
    Eigen::Vector3d ur, ut;
    ur << pu[0], pu[1], pu[2];
    ut << pu[3], pu[4], pu[5];

    // Update body pose
    twb_ += Rwb_ * ut;
    Rwb_ = Rwb_ * exp_so3(ur);

    // Normalize rotation after 5 updates
    its_++;
    if (its_ >= 3) {
        normalize_rotation(Rwb_);
        its_ = 0;
    }

    // Update camera poses
    const Eigen::Matrix3d Rbw = Rwb_.transpose();
    const Eigen::Vector3d tbw = -Rbw * twb_;

    Rcw_ = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3) * Rbw;
    tcw_ = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3) * tbw + data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
}

void ImuCamPose::UpdateW(const double* pu)
{
    Eigen::Vector3d ur, ut;
    ur << pu[0], pu[1], pu[2];
    ut << pu[3], pu[4], pu[5];

    const Eigen::Matrix3d dR = exp_so3(ur);
    DR_ = dR * DR_;
    Rwb_ = DR_ * Rwb0_;
    // Update body pose
    twb_ += ut;

    // Normalize rotation after 5 updates
    its_++;
    if (its_ >= 5) {
        DR_(0, 2) = 0.0;
        DR_(1, 2) = 0.0;
        DR_(2, 0) = 0.0;
        DR_(2, 1) = 0.0;
        normalize_rotation(DR_);
        its_ = 0;
    }

    // Update camera pose
    const Eigen::Matrix3d Rbw = Rwb_.transpose();
    const Eigen::Vector3d tbw = -Rbw * twb_;

    Rcw_ = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3) * Rbw;
    tcw_ = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3) * tbw + data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
}

Vec2_t ImuCamPose::project_mono(const Vec3_t& Xw) const
{
    Eigen::Vector3d Xc = Rcw_ * Xw + tcw_;
    return cam_project(Xc);
}

Vec3_t ImuCamPose::project_stereo(const Vec3_t& Xw) const
{
    Vec3_t Pc = Rcw_ * Xw + tcw_;
    Vec3_t pc;
    double invZ = 1 / Pc(2);
    pc.head(2) = cam_project(Pc);
    pc(2) = pc(0) - camera_->focal_x_baseline_ * invZ;
    return pc;
}

bool ImuCamPose::is_depth_positive(const Vec3_t& Xw) const
{
    return (Rcw_.row(2) * Xw + tcw_(2)) > 0.0;
}

Eigen::Matrix<double, 2, 3> ImuCamPose::project_jac(const Eigen::Vector3d& x) const
{
    Eigen::Matrix<double, 2, 3> Jac;
    Jac(0, 0) = camera_->fx_ / x[2];
    Jac(0, 1) = 0.f;
    Jac(0, 2) = -camera_->fx_ * x[0] / (x[2] * x[2]);
    Jac(1, 0) = 0.f;
    Jac(1, 1) = camera_->fy_ / x[2];
    Jac(1, 2) = -camera_->fy_ * x[1] / (x[2] * x[2]);

    return Jac;
}

VertexPose::VertexPose(Keyframe* pKF)
{
    setEstimate(ImuCamPose(pKF));
}

VertexPose::VertexPose(Frame* pF)
{
    setEstimate(ImuCamPose(pF));
}

void VertexPose::oplusImpl(const double* update_)
{
    _estimate.Update(update_);
    updateCache();
}

VertexPose4DoF::VertexPose4DoF(Keyframe* pKF)
{
    setEstimate(ImuCamPose(pKF));
}

VertexPose4DoF::VertexPose4DoF(Frame* pF)
{
    setEstimate(ImuCamPose(pF));
}

VertexPose4DoF::VertexPose4DoF(Eigen::Matrix3d& Rwc, Eigen::Vector3d& twc, Keyframe* pKF)
{
    setEstimate(ImuCamPose(Rwc, twc, pKF));
}

void VertexPose4DoF::oplusImpl(const double* update_)
{
    double update6DoF[6];
    update6DoF[0] = 0;
    update6DoF[1] = 0;
    update6DoF[2] = update_[0];
    update6DoF[3] = update_[1];
    update6DoF[4] = update_[2];
    update6DoF[5] = update_[3];
    _estimate.UpdateW(update6DoF);
    updateCache();
}

VertexVelocity::VertexVelocity(Keyframe* pKF) { setEstimate(pKF->get_imu_velocity()); }

// VIP! TODO: this part has problem, frame still not set the data member imu_velocity_
VertexVelocity::VertexVelocity(Frame* pF) { setEstimate(pF->imu_velocity_); }

void VertexVelocity::oplusImpl(const double* update_)
{
    Eigen::Vector3d uv;
    uv << update_[0], update_[1], update_[2];
    setEstimate(estimate() + uv);
}

VertexGyroBias::VertexGyroBias(Keyframe* pKF) { setEstimate(pKF->get_imu_bias().tail(3)); }

// VIP! TODO: this part has problem, frame still not set the data member imu_bias_
VertexGyroBias::VertexGyroBias(Frame* pF) { setEstimate(pF->imu_bias_.tail(3)); }

void VertexGyroBias::oplusImpl(const double* update_)
{
    Eigen::Vector3d ubg;
    ubg << update_[0], update_[1], update_[2];
    setEstimate(estimate() + ubg);
}

VertexAccBias::VertexAccBias(Keyframe* pKF) { setEstimate(pKF->get_imu_bias().head(3)); }

// VIP! TODO: this part has problem, frame still not set the data member imu_bias_
VertexAccBias::VertexAccBias(Frame* pF) { setEstimate(pF->imu_bias_.head(3)); }

void VertexAccBias::oplusImpl(const double* update_)
{
    Eigen::Vector3d uba;
    uba << update_[0], update_[1], update_[2];
    setEstimate(estimate() + uba);
}

GDirection::GDirection(Eigen::Matrix3d Rwg)
    : Rwg_(Rwg)
{
}

void GDirection::Update(const double* pu)
{
    Rwg_ = Rwg_ * exp_so3(Eigen::Vector3d(pu[0], pu[1], 0.0));
}

VertexGDir::VertexGDir(Eigen::Matrix3d Rwg)
{
    setEstimate(GDirection(Rwg));
}

void VertexGDir::oplusImpl(const double* update_)
{
    _estimate.Update(update_);
    updateCache();
}

VertexScale::VertexScale()
{
    setEstimate(1.0);
}

VertexScale::VertexScale(double ps)
{
    setEstimate(ps);
}

void VertexScale::setToOriginImpl()
{
    setEstimate(1.0);
}

void VertexScale::oplusImpl(const double* update_)
{
    setEstimate(estimate() * exp(*update_));
}

void EdgeMono::computeError()
{
    const ::g2o::VertexPointXYZ* VPoint = static_cast<const ::g2o::VertexPointXYZ*>(_vertices[0]);
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[1]);
    const Eigen::Vector2d obs(_measurement);
    _error = obs - VPose->estimate().project_mono(VPoint->estimate());
}

void EdgeMono::linearizeOplus()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[1]);
    const ::g2o::VertexPointXYZ* VPoint = static_cast<const ::g2o::VertexPointXYZ*>(_vertices[0]);

    const Eigen::Matrix3d& Rcw = VPose->estimate().Rcw_;
    const Eigen::Vector3d& tcw = VPose->estimate().tcw_;
    const Eigen::Vector3d Xc = Rcw * VPoint->estimate() + tcw;
    const Eigen::Matrix3d Rbc = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3).transpose();
    const Eigen::Vector3d tbc = -Rbc * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
    const Eigen::Vector3d Xb = Rbc * Xc + tbc;
    const Eigen::Matrix3d& Rcb = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);

    const Eigen::Matrix<double, 2, 3> proj_jac = VPose->estimate().project_jac(Xc);
    _jacobianOplusXi = -proj_jac * Rcw;

    Eigen::Matrix<double, 3, 6> SE3deriv;
    double x = Xb(0);
    double y = Xb(1);
    double z = Xb(2);

    SE3deriv << 0.0, z, -y, 1.0, 0.0, 0.0, -z, 0.0, x, 0.0, 1.0, 0.0, y, -x, 0.0, 0.0, 0.0, 1.0;

    _jacobianOplusXj = proj_jac * Rcb * SE3deriv;  // TODO optimize this product
}

bool EdgeMono::is_depth_positive()
{
    const ::g2o::VertexPointXYZ* VPoint = static_cast<const ::g2o::VertexPointXYZ*>(_vertices[0]);
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[1]);
    return VPose->estimate().is_depth_positive(VPoint->estimate());
}

Eigen::Matrix<double, 9, 9> EdgeMono::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 2, 9> J;
    J.block<2, 3>(0, 0) = _jacobianOplusXi;
    J.block<2, 6>(0, 3) = _jacobianOplusXj;
    return J.transpose() * information() * J;
}

EdgeMonoOnlyPose::EdgeMonoOnlyPose(const Eigen::Vector3d& Xw)
    : Xw_(Xw)
{
}

void EdgeMonoOnlyPose::computeError()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[0]);
    const Eigen::Vector2d obs(_measurement);
    _error = obs - VPose->estimate().project_mono(Xw_);
}

void EdgeMonoOnlyPose::linearizeOplus()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[0]);

    const Eigen::Matrix3d& Rcw = VPose->estimate().Rcw_;
    const Eigen::Vector3d& tcw = VPose->estimate().tcw_;
    const Eigen::Vector3d Xc = Rcw * Xw_ + tcw;
    const Eigen::Matrix3d Rbc = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3).transpose();
    const Eigen::Vector3d tbc = -Rbc * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
    const Eigen::Vector3d Xb = Rbc * Xc + tbc;
    const Eigen::Matrix3d& Rcb = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);

    Eigen::Matrix<double, 2, 3> proj_jac = VPose->estimate().project_jac(Xc);

    Eigen::Matrix<double, 3, 6> SE3deriv;
    double x = Xb(0);
    double y = Xb(1);
    double z = Xb(2);
    SE3deriv << 0.0, z, -y, 1.0, 0.0, 0.0, -z, 0.0, x, 0.0, 1.0, 0.0, y, -x, 0.0, 0.0, 0.0, 1.0;
    _jacobianOplusXi = proj_jac * Rcb * SE3deriv;  // symbol different becasue of update mode
}

bool EdgeMonoOnlyPose::is_depth_positive()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[0]);
    return VPose->estimate().is_depth_positive(Xw_);
}

Eigen::Matrix<double, 6, 6> EdgeMonoOnlyPose::GetHessian()
{
    linearizeOplus();
    return _jacobianOplusXi.transpose() * information() * _jacobianOplusXi;
}

void EdgeStereo::computeError()
{
    const ::g2o::VertexPointXYZ* VPoint = static_cast<const ::g2o::VertexPointXYZ*>(_vertices[0]);
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[1]);
    const Eigen::Vector3d obs(_measurement);
    _error = obs - VPose->estimate().project_stereo(VPoint->estimate());
}

void EdgeStereo::linearizeOplus()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[1]);
    const ::g2o::VertexPointXYZ* VPoint = static_cast<const ::g2o::VertexPointXYZ*>(_vertices[0]);

    const Eigen::Matrix3d& Rcw = VPose->estimate().Rcw_;
    const Eigen::Vector3d& tcw = VPose->estimate().tcw_;
    const Eigen::Vector3d Xc = Rcw * VPoint->estimate() + tcw;
    const Eigen::Matrix3d Rbc = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3).transpose();
    const Eigen::Vector3d tbc = -Rbc * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
    const Eigen::Vector3d Xb = Rbc * Xc + tbc;
    const Eigen::Matrix3d& Rcb = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);
    const double bf = VPose->estimate().camera_->focal_x_baseline_;
    const double inv_z2 = 1.0 / (Xc(2) * Xc(2));

    Eigen::Matrix<double, 3, 3> proj_jac;
    proj_jac.block<2, 3>(0, 0) = VPose->estimate().project_jac(Xc);
    proj_jac.block<1, 3>(2, 0) = proj_jac.block<1, 3>(0, 0);
    proj_jac(2, 2) += bf * inv_z2;

    _jacobianOplusXi = -proj_jac * Rcw;

    Eigen::Matrix<double, 3, 6> SE3deriv;
    double x = Xb(0);
    double y = Xb(1);
    double z = Xb(2);

    SE3deriv << 0.0, z, -y, 1.0, 0.0, 0.0, -z, 0.0, x, 0.0, 1.0, 0.0, y, -x, 0.0, 0.0, 0.0, 1.0;

    _jacobianOplusXj = proj_jac * Rcb * SE3deriv;
}

Eigen::Matrix<double, 9, 9> EdgeStereo::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 3, 9> J;
    J.block<3, 3>(0, 0) = _jacobianOplusXi;
    J.block<3, 6>(0, 3) = _jacobianOplusXj;
    return J.transpose() * information() * J;
}

EdgeStereoOnlyPose::EdgeStereoOnlyPose(const Eigen::Vector3d& Xw)
    : Xw_(Xw)
{
}

void EdgeStereoOnlyPose::computeError()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[0]);
    const Eigen::Vector3d obs(_measurement);
    _error = obs - VPose->estimate().project_stereo(Xw_);
}

void EdgeStereoOnlyPose::linearizeOplus()
{
    const VertexPose* VPose = static_cast<const VertexPose*>(_vertices[0]);

    const Eigen::Matrix3d& Rcw = VPose->estimate().Rcw_;
    const Eigen::Vector3d& tcw = VPose->estimate().tcw_;
    const Eigen::Vector3d Xc = Rcw * Xw_ + tcw;
    const Eigen::Matrix3d Rbc = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3).transpose();
    const Eigen::Vector3d tbc = -Rbc * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1);
    const Eigen::Vector3d Xb = Rbc * Xc + tbc;
    const Eigen::Matrix3d& Rcb = data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);
    const double bf = VPose->estimate().camera_->focal_x_baseline_;
    const double inv_z2 = 1.0 / (Xc(2) * Xc(2));

    Eigen::Matrix<double, 3, 3> proj_jac;
    proj_jac.block<2, 3>(0, 0) = VPose->estimate().project_jac(Xc);
    proj_jac.block<1, 3>(2, 0) = proj_jac.block<1, 3>(0, 0);
    proj_jac(2, 2) += bf * inv_z2;

    Eigen::Matrix<double, 3, 6> SE3deriv;
    double x = Xb(0);
    double y = Xb(1);
    double z = Xb(2);
    SE3deriv << 0.0, z, -y, 1.0, 0.0, 0.0, -z, 0.0, x, 0.0, 1.0, 0.0, y, -x, 0.0, 0.0, 0.0, 1.0;
    _jacobianOplusXi = proj_jac * Rcb * SE3deriv;
}

Eigen::Matrix<double, 6, 6> EdgeStereoOnlyPose::GetHessian()
{
    linearizeOplus();
    return _jacobianOplusXi.transpose() * information() * _jacobianOplusXi;
}

EdgeInertialGS::EdgeInertialGS(data::IMU_Preintegration_Ptr imu_preintegration_ptr)
    : J_R_bg_(imu_preintegration_ptr->J_R_bg_),
      J_v_bg_(imu_preintegration_ptr->J_v_bg_),
      J_p_bg_(imu_preintegration_ptr->J_p_bg_),
      J_v_ba_(imu_preintegration_ptr->J_v_ba_),
      J_p_ba_(imu_preintegration_ptr->J_p_ba_),
      imu_preintegration_ptr_(imu_preintegration_ptr),
      integration_time_(imu_preintegration_ptr->integration_time_),
      g_(Eigen::Vector3d::Zero())
{
    // This edge links 8 vertices
    resize(8);
    // TODO: default inverse may not be stable
    Eigen::Matrix<double, 9, 9> Info = imu_preintegration_ptr_->covariance_.block(0, 0, 9, 9).inverse();
    Info = (Info + Info.transpose()) / 2;
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double, 9, 9>> es(Info);
    Eigen::Matrix<double, 9, 1> eigs = es.eigenvalues();
    for (int i = 0; i < 9; i++)
        if (eigs[i] < INERTIAL_EDGE_EPSILON) eigs[i] = 0;
    Info = es.eigenvectors() * eigs.asDiagonal() * es.eigenvectors().transpose();
    setInformation(Info);
}

void EdgeInertialGS::computeError()
{
    // TODO Maybe Reintegrate inertial measurments when difference between linearization point and current estimate is
    // too big
    const VertexPose* VP1 = static_cast<const VertexPose*>(_vertices[0]);
    const VertexVelocity* VV1 = static_cast<const VertexVelocity*>(_vertices[1]);
    const VertexGyroBias* VG = static_cast<const VertexGyroBias*>(_vertices[2]);
    const VertexAccBias* VA = static_cast<const VertexAccBias*>(_vertices[3]);
    const VertexPose* VP2 = static_cast<const VertexPose*>(_vertices[4]);
    const VertexVelocity* VV2 = static_cast<const VertexVelocity*>(_vertices[5]);
    const VertexGDir* VGDir = static_cast<const VertexGDir*>(_vertices[6]);
    const VertexScale* VS = static_cast<const VertexScale*>(_vertices[7]);

    Eigen::VectorXd bias = Eigen::VectorXd(6);
    bias << VA->estimate()[0], VA->estimate()[1], VA->estimate()[2], VG->estimate()[0], VG->estimate()[1],
        VG->estimate()[2];
    g_ = VGDir->estimate().Rwg_ * gI;

    const double s = VS->estimate();

    const Eigen::Matrix3d dR = imu_preintegration_ptr_->get_delta_rotation(bias);
    const Eigen::Vector3d dV = imu_preintegration_ptr_->get_delta_velocity(bias);
    const Eigen::Vector3d dP = imu_preintegration_ptr_->get_delta_position(bias);

    const Eigen::Vector3d er = log_so3(dR.transpose() * VP1->estimate().Rwb_.transpose() * VP2->estimate().Rwb_);
    const Eigen::Vector3d ev =
        VP1->estimate().Rwb_.transpose() * (s * (VV2->estimate() - VV1->estimate()) - g_ * integration_time_) - dV;
    const Eigen::Vector3d ep =
        VP1->estimate().Rwb_.transpose() *
            (s * (VP2->estimate().twb_ - VP1->estimate().twb_ - VV1->estimate() * integration_time_) -
             g_ * integration_time_ * integration_time_ / 2) -
        dP;

    _error << er, ev, ep;
}

void EdgeInertialGS::linearizeOplus()
{
    const VertexPose* VP1 = static_cast<const VertexPose*>(_vertices[0]);
    const VertexVelocity* VV1 = static_cast<const VertexVelocity*>(_vertices[1]);
    const VertexGyroBias* VG = static_cast<const VertexGyroBias*>(_vertices[2]);
    const VertexAccBias* VA = static_cast<const VertexAccBias*>(_vertices[3]);
    const VertexPose* VP2 = static_cast<const VertexPose*>(_vertices[4]);
    const VertexVelocity* VV2 = static_cast<const VertexVelocity*>(_vertices[5]);
    const VertexGDir* VGDir = static_cast<const VertexGDir*>(_vertices[6]);
    const VertexScale* VS = static_cast<const VertexScale*>(_vertices[7]);
    Eigen::VectorXd bias = Eigen::VectorXd(6);
    bias << VA->estimate()[0], VA->estimate()[1], VA->estimate()[2], VG->estimate()[0], VG->estimate()[1],
        VG->estimate()[2];

    const Eigen::VectorXd db = imu_preintegration_ptr_->get_delta_bias(bias);
    Eigen::Vector3d dbg(db[3], db[4], db[5]);

    const Eigen::Matrix3d Rwb1 = VP1->estimate().Rwb_;
    const Eigen::Matrix3d Rbw1 = Rwb1.transpose();
    const Eigen::Matrix3d Rwb2 = VP2->estimate().Rwb_;
    const Eigen::Matrix3d Rwg = VGDir->estimate().Rwg_;
    Eigen::MatrixXd Gm = Eigen::MatrixXd::Zero(3, 2);
    Gm(0, 1) = -GRAVITY_VALUE;
    Gm(1, 0) = GRAVITY_VALUE;
    const double s = VS->estimate();
    const Eigen::MatrixXd dGdTheta = Rwg * Gm;
    const Eigen::Matrix3d dR = imu_preintegration_ptr_->get_delta_rotation(bias);
    const Eigen::Matrix3d eR = dR.transpose() * Rbw1 * Rwb2;
    const Eigen::Vector3d er = log_so3(eR);
    const Eigen::Matrix3d invJr = jacobian_right_inverse(er);

    // Jacobians wrt Pose 1
    _jacobianOplus[0].setZero();
    // rotation
    _jacobianOplus[0].block<3, 3>(0, 0) = -invJr * Rwb2.transpose() * Rwb1;
    _jacobianOplus[0].block<3, 3>(3, 0) =
        skew(Rbw1 * (s * (VV2->estimate() - VV1->estimate()) - g_ * integration_time_));
    _jacobianOplus[0].block<3, 3>(6, 0) =
        skew(Rbw1 * (s * (VP2->estimate().twb_ - VP1->estimate().twb_ - VV1->estimate() * integration_time_) -
                     0.5 * g_ * integration_time_ * integration_time_));
    // translation
    _jacobianOplus[0].block<3, 3>(6, 3) = -s * Eigen::Matrix3d::Identity();

    // Jacobians wrt Velocity 1
    _jacobianOplus[1].setZero();
    _jacobianOplus[1].block<3, 3>(3, 0) = -s * Rbw1;
    _jacobianOplus[1].block<3, 3>(6, 0) = -s * Rbw1 * integration_time_;

    // Jacobians wrt Gyro bias
    _jacobianOplus[2].setZero();
    _jacobianOplus[2].block<3, 3>(0, 0) = -invJr * eR.transpose() * jacobian_right(J_R_bg_ * dbg) * J_R_bg_;
    _jacobianOplus[2].block<3, 3>(3, 0) = -J_v_bg_;
    _jacobianOplus[2].block<3, 3>(6, 0) = -J_p_bg_;

    // Jacobians wrt Accelerometer bias
    _jacobianOplus[3].setZero();
    _jacobianOplus[3].block<3, 3>(3, 0) = -J_v_ba_;
    _jacobianOplus[3].block<3, 3>(6, 0) = -J_p_ba_;

    // Jacobians wrt Pose 2
    _jacobianOplus[4].setZero();
    // rotation
    _jacobianOplus[4].block<3, 3>(0, 0) = invJr;
    // translation
    _jacobianOplus[4].block<3, 3>(6, 3) = s * Rbw1 * Rwb2;

    // Jacobians wrt Velocity 2
    _jacobianOplus[5].setZero();
    _jacobianOplus[5].block<3, 3>(3, 0) = s * Rbw1;

    // Jacobians wrt Gravity direction
    _jacobianOplus[6].setZero();
    _jacobianOplus[6].block<3, 2>(3, 0) = -Rbw1 * dGdTheta * integration_time_;
    _jacobianOplus[6].block<3, 2>(6, 0) = -0.5 * Rbw1 * dGdTheta * integration_time_ * integration_time_;

    // Jacobians wrt scale factor
    _jacobianOplus[7].setZero();
    _jacobianOplus[7].block<3, 1>(3, 0) = Rbw1 * (VV2->estimate() - VV1->estimate());
    _jacobianOplus[7].block<3, 1>(6, 0) =
        Rbw1 * (VP2->estimate().twb_ - VP1->estimate().twb_ - VV1->estimate() * integration_time_);
}

EdgeInertial::EdgeInertial(data::IMU_Preintegration_Ptr imu_preintegration_ptr)
    : J_R_bg_(imu_preintegration_ptr->J_R_bg_),
      J_v_bg_(imu_preintegration_ptr->J_v_bg_),
      J_p_bg_(imu_preintegration_ptr->J_p_bg_),
      J_v_ba_(imu_preintegration_ptr->J_v_ba_),
      J_p_ba_(imu_preintegration_ptr->J_p_ba_),
      imu_preintegration_ptr_(imu_preintegration_ptr),
      integration_time_(imu_preintegration_ptr->integration_time_)
{
    // This edge links 6 vertices
    resize(6);
    g_ = gI;
    // TODO: default inverse may not be stable
    Eigen::Matrix<double, 9, 9> Info = imu_preintegration_ptr_->covariance_.block(0, 0, 9, 9).inverse();
    Info = (Info + Info.transpose()) / 2;
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double, 9, 9>> es(Info);
    Eigen::Matrix<double, 9, 1> eigs = es.eigenvalues();
    for (int i = 0; i < 9; i++)
        if (eigs[i] < INERTIAL_EDGE_EPSILON) eigs[i] = 0;
    Info = es.eigenvectors() * eigs.asDiagonal() * es.eigenvectors().transpose();
    setInformation(Info);
}

void EdgeInertial::computeError()
{
    // TODO Maybe Reintegrate inertial measurments when difference between linearization point and current estimate is
    // too big
    const VertexPose* VP1 = static_cast<const VertexPose*>(_vertices[0]);
    const VertexVelocity* VV1 = static_cast<const VertexVelocity*>(_vertices[1]);
    const VertexGyroBias* VG1 = static_cast<const VertexGyroBias*>(_vertices[2]);
    const VertexAccBias* VA1 = static_cast<const VertexAccBias*>(_vertices[3]);
    const VertexPose* VP2 = static_cast<const VertexPose*>(_vertices[4]);
    const VertexVelocity* VV2 = static_cast<const VertexVelocity*>(_vertices[5]);
    Eigen::VectorXd bias = Eigen::VectorXd(6);
    bias << VA1->estimate()[0], VA1->estimate()[1], VA1->estimate()[2], VG1->estimate()[0], VG1->estimate()[1],
        VG1->estimate()[2];

    const Eigen::Matrix3d dR = imu_preintegration_ptr_->get_delta_rotation(bias);
    const Eigen::Vector3d dV = imu_preintegration_ptr_->get_delta_velocity(bias);
    const Eigen::Vector3d dP = imu_preintegration_ptr_->get_delta_position(bias);

    const Eigen::Vector3d er = log_so3(dR.transpose() * VP1->estimate().Rwb_.transpose() * VP2->estimate().Rwb_);
    const Eigen::Vector3d ev =
        VP1->estimate().Rwb_.transpose() * (VV2->estimate() - VV1->estimate() - g_ * integration_time_) - dV;
    const Eigen::Vector3d ep = VP1->estimate().Rwb_.transpose() *
                                   (VP2->estimate().twb_ - VP1->estimate().twb_ - VV1->estimate() * integration_time_ -
                                    g_ * integration_time_ * integration_time_ / 2) -
                               dP;

    _error << er, ev, ep;
}

void EdgeInertial::linearizeOplus()
{
    const VertexPose* VP1 = static_cast<const VertexPose*>(_vertices[0]);
    const VertexVelocity* VV1 = static_cast<const VertexVelocity*>(_vertices[1]);
    const VertexGyroBias* VG1 = static_cast<const VertexGyroBias*>(_vertices[2]);
    const VertexAccBias* VA1 = static_cast<const VertexAccBias*>(_vertices[3]);
    const VertexPose* VP2 = static_cast<const VertexPose*>(_vertices[4]);
    const VertexVelocity* VV2 = static_cast<const VertexVelocity*>(_vertices[5]);
    Eigen::VectorXd bias = Eigen::VectorXd(6);
    bias << VA1->estimate()[0], VA1->estimate()[1], VA1->estimate()[2], VG1->estimate()[0], VG1->estimate()[1],
        VG1->estimate()[2];

    const Eigen::VectorXd db = imu_preintegration_ptr_->get_delta_bias(bias);
    Eigen::Vector3d dbg(db[3], db[4], db[5]);

    const Eigen::Matrix3d Rwb1 = VP1->estimate().Rwb_;
    const Eigen::Matrix3d Rbw1 = Rwb1.transpose();
    const Eigen::Matrix3d Rwb2 = VP2->estimate().Rwb_;

    const Eigen::Matrix3d dR = imu_preintegration_ptr_->get_delta_rotation(bias);
    const Eigen::Matrix3d eR = dR.transpose() * Rbw1 * Rwb2;
    const Eigen::Vector3d er = log_so3(eR);
    const Eigen::Matrix3d invJr = jacobian_right_inverse(er);

    // Jacobians wrt Pose 1
    _jacobianOplus[0].setZero();
    // rotation
    _jacobianOplus[0].block<3, 3>(0, 0) = -invJr * Rwb2.transpose() * Rwb1;  // OK
    _jacobianOplus[0].block<3, 3>(3, 0) =
        skew(Rbw1 * (VV2->estimate() - VV1->estimate() - g_ * integration_time_));  // OK
    _jacobianOplus[0].block<3, 3>(6, 0) =
        skew(Rbw1 * (VP2->estimate().twb_ - VP1->estimate().twb_ - VV1->estimate() * integration_time_ -
                     0.5 * g_ * integration_time_ * integration_time_));  // OK
    // translation
    _jacobianOplus[0].block<3, 3>(6, 3) = -Eigen::Matrix3d::Identity();  // OK

    // Jacobians wrt Velocity 1
    _jacobianOplus[1].setZero();
    _jacobianOplus[1].block<3, 3>(3, 0) = -Rbw1;                      // OK
    _jacobianOplus[1].block<3, 3>(6, 0) = -Rbw1 * integration_time_;  // OK

    // Jacobians wrt Gyro 1
    _jacobianOplus[2].setZero();
    _jacobianOplus[2].block<3, 3>(0, 0) = -invJr * eR.transpose() * jacobian_right(J_R_bg_ * dbg) * J_R_bg_;  // OK
    _jacobianOplus[2].block<3, 3>(3, 0) = -J_v_bg_;                                                           // OK
    _jacobianOplus[2].block<3, 3>(6, 0) = -J_p_bg_;                                                           // OK

    // Jacobians wrt Accelerometer 1
    _jacobianOplus[3].setZero();
    _jacobianOplus[3].block<3, 3>(3, 0) = -J_v_ba_;  // OK
    _jacobianOplus[3].block<3, 3>(6, 0) = -J_p_ba_;  // OK

    // Jacobians wrt Pose 2
    _jacobianOplus[4].setZero();
    // rotation
    _jacobianOplus[4].block<3, 3>(0, 0) = invJr;  // OK
    // translation
    _jacobianOplus[4].block<3, 3>(6, 3) = Rbw1 * Rwb2;  // OK

    // Jacobians wrt Velocity 2
    _jacobianOplus[5].setZero();
    _jacobianOplus[5].block<3, 3>(3, 0) = Rbw1;  // OK
}

Eigen::Matrix<double, 24, 24> EdgeInertial::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 9, 24> J;
    J.block<9, 6>(0, 0) = _jacobianOplus[0];
    J.block<9, 3>(0, 6) = _jacobianOplus[1];
    J.block<9, 3>(0, 9) = _jacobianOplus[2];
    J.block<9, 3>(0, 12) = _jacobianOplus[3];
    J.block<9, 6>(0, 15) = _jacobianOplus[4];
    J.block<9, 3>(0, 21) = _jacobianOplus[5];
    return J.transpose() * information() * J;
}

Eigen::Matrix<double, 9, 9> EdgeInertial::GetHessian2()
{
    linearizeOplus();
    Eigen::Matrix<double, 9, 9> J;
    J.block<9, 6>(0, 0) = _jacobianOplus[4];
    J.block<9, 3>(0, 6) = _jacobianOplus[5];
    return J.transpose() * information() * J;
}

void EdgeGyroRW::computeError()
{
    const VertexGyroBias* VG1 = static_cast<const VertexGyroBias*>(_vertices[0]);
    const VertexGyroBias* VG2 = static_cast<const VertexGyroBias*>(_vertices[1]);
    _error = VG2->estimate() - VG1->estimate();
}

void EdgeGyroRW::linearizeOplus()
{
    _jacobianOplusXi = -Eigen::Matrix3d::Identity();
    _jacobianOplusXj.setIdentity();
}

Eigen::Matrix<double, 6, 6> EdgeGyroRW::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 3, 6> J;
    J.block<3, 3>(0, 0) = _jacobianOplusXi;
    J.block<3, 3>(0, 3) = _jacobianOplusXj;
    return J.transpose() * information() * J;
}

Eigen::Matrix3d EdgeGyroRW::GetHessian2()
{
    linearizeOplus();
    return _jacobianOplusXj.transpose() * information() * _jacobianOplusXj;
}

void EdgeAccRW::computeError()
{
    const VertexAccBias* VA1 = static_cast<const VertexAccBias*>(_vertices[0]);
    const VertexAccBias* VA2 = static_cast<const VertexAccBias*>(_vertices[1]);
    _error = VA2->estimate() - VA1->estimate();
}

void EdgeAccRW::linearizeOplus()
{
    _jacobianOplusXi = -Eigen::Matrix3d::Identity();
    _jacobianOplusXj.setIdentity();
}

Eigen::Matrix<double, 6, 6> EdgeAccRW::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 3, 6> J;
    J.block<3, 3>(0, 0) = _jacobianOplusXi;
    J.block<3, 3>(0, 3) = _jacobianOplusXj;
    return J.transpose() * information() * J;
}

Eigen::Matrix3d EdgeAccRW::GetHessian2()
{
    linearizeOplus();
    return _jacobianOplusXj.transpose() * information() * _jacobianOplusXj;
}

EdgePriorAcc::EdgePriorAcc(const Eigen::Vector3d& bprior)
    : bprior_(bprior)
{
}

void EdgePriorAcc::computeError()
{
    const VertexAccBias* VA = static_cast<const VertexAccBias*>(_vertices[0]);
    _error = bprior_ - VA->estimate();
}

void EdgePriorAcc::linearizeOplus()
{
    // Jacobian wrt bias
    _jacobianOplusXi.block<3, 3>(0, 0) = Eigen::Matrix3d::Identity();
}

EdgePriorGyro::EdgePriorGyro(const Eigen::Vector3d& bprior)
    : bprior_(bprior)
{
}

void EdgePriorGyro::computeError()
{
    const VertexGyroBias* VG = static_cast<const VertexGyroBias*>(_vertices[0]);
    _error = bprior_ - VG->estimate();
}

void EdgePriorGyro::linearizeOplus()
{
    // Jacobian wrt bias
    _jacobianOplusXi.block<3, 3>(0, 0) = Eigen::Matrix3d::Identity();
}

Edge4DoF::Edge4DoF(const Eigen::Matrix4d& delta_T)
{
    delta_Tij_ = delta_T;
    delta_Rij_ = delta_T.block<3, 3>(0, 0);
    delta_tij_ = delta_T.block<3, 1>(0, 3);
}

void Edge4DoF::computeError()
{
    const VertexPose4DoF* VPi = static_cast<const VertexPose4DoF*>(_vertices[0]);
    const VertexPose4DoF* VPj = static_cast<const VertexPose4DoF*>(_vertices[1]);
    _error << log_so3(VPi->estimate().Rcw_ * VPj->estimate().Rcw_.transpose() * delta_Rij_.transpose()),
        VPi->estimate().Rcw_ * (-VPj->estimate().Rcw_.transpose() * VPj->estimate().tcw_) + VPi->estimate().tcw_ -
            delta_tij_;
}

ConstraintPoseImu::ConstraintPoseImu(const Eigen::Matrix3d& Rwb, const Eigen::Vector3d& twb,
                                     const Eigen::Vector3d& vwb, const Eigen::Vector3d& bg,
                                     const Eigen::Vector3d& ba, const Eigen::Matrix<double, 15, 15>& H)
    : Rwb_(Rwb),
      twb_(twb),
      vwb_(vwb),
      bg_(bg),
      ba_(ba),
      H_(H)
{
    H_ = (H_ + H_) / 2;
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double, 15, 15> > es(H_);
    Eigen::Matrix<double, 15, 1> eigs = es.eigenvalues();
    for (int i = 0; i < 15; i++)
        if (eigs[i] < 1e-12) eigs[i] = 0;
    H_ = es.eigenvectors() * eigs.asDiagonal() * es.eigenvectors().transpose();
}

EdgePriorPoseImu::EdgePriorPoseImu(ConstraintPoseImu* c)
    : Rwb_(c->Rwb_),
      twb_(c->twb_),
      vwb_(c->vwb_),
      bg_(c->bg_),
      ba_(c->ba_)
{
    resize(4);
    setInformation(c->H_);
}

void EdgePriorPoseImu::computeError()
{
    const VertexPose* VP = static_cast<const VertexPose*>(_vertices[0]);
    const VertexVelocity* VV = static_cast<const VertexVelocity*>(_vertices[1]);
    const VertexGyroBias* VG = static_cast<const VertexGyroBias*>(_vertices[2]);
    const VertexAccBias* VA = static_cast<const VertexAccBias*>(_vertices[3]);

    const Eigen::Vector3d er = log_so3(Rwb_.transpose() * VP->estimate().Rwb_);
    const Eigen::Vector3d et = Rwb_.transpose() * (VP->estimate().twb_ - twb_);
    const Eigen::Vector3d ev = VV->estimate() - vwb_;
    const Eigen::Vector3d ebg = VG->estimate() - bg_;
    const Eigen::Vector3d eba = VA->estimate() - ba_;

    _error << er, et, ev, ebg, eba;
}

void EdgePriorPoseImu::linearizeOplus()
{
    const VertexPose* VP = static_cast<const VertexPose*>(_vertices[0]);
    const Eigen::Vector3d er = log_so3(Rwb_.transpose() * VP->estimate().Rwb_);
    _jacobianOplus[0].setZero();
    _jacobianOplus[0].block<3, 3>(0, 0) = jacobian_right_inverse(er);
    _jacobianOplus[0].block<3, 3>(3, 3) = Rwb_.transpose() * VP->estimate().Rwb_;
    _jacobianOplus[1].setZero();
    _jacobianOplus[1].block<3, 3>(6, 0) = Eigen::Matrix3d::Identity();
    _jacobianOplus[2].setZero();
    _jacobianOplus[2].block<3, 3>(9, 0) = Eigen::Matrix3d::Identity();
    _jacobianOplus[3].setZero();
    _jacobianOplus[3].block<3, 3>(12, 0) = Eigen::Matrix3d::Identity();
}

Eigen::Matrix<double, 15, 15> EdgePriorPoseImu::GetHessian()
{
    linearizeOplus();
    Eigen::Matrix<double, 15, 15> J;
    J.block<15, 6>(0, 0) = _jacobianOplus[0];
    J.block<15, 3>(0, 6) = _jacobianOplus[1];
    J.block<15, 3>(0, 9) = _jacobianOplus[2];
    J.block<15, 3>(0, 12) = _jacobianOplus[3];
    return J.transpose() * information() * J;
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
