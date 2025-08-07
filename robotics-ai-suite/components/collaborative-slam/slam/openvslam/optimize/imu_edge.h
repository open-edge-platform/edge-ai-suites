// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef G2O_EDGE_IMU_H
#define G2O_EDGE_IMU_H

#include <g2o/core/base_vertex.h>
#include <g2o/core/base_unary_edge.h>
#include <g2o/core/base_binary_edge.h>
#include <g2o/core/base_multi_edge.h>
#include <g2o/types/slam3d_addons/g2o_types_slam3d_addons_api.h>
#include "g2o/se3/shot_vertex.h"
#include "type.h"
#include "g2o/scale_vertex.h"
#include "g2o/vec3_vertex.h"
#include "g2o/imubias_vertex.h"
#include "g2o/so3_vertex.h"
#include "../data/imu.h"
#include "g2o/camera_pose_vertex.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "camera/perspective.h"

typedef openvslam::data::frame Frame;
typedef openvslam::data::keyframe Keyframe;

namespace openvslam {

extern const Eigen::Vector3d gI;

namespace data {
class frame;
class keyframe;
}  // namespace data

namespace optimize {

namespace g2o {
class ImuCamPose {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    ImuCamPose() {}
    ImuCamPose(Keyframe* pKF);
    ImuCamPose(Frame* pF);
    ImuCamPose(Eigen::Matrix3d& Rwc, Eigen::Vector3d& twc, Keyframe* pKF);

    void Update(const double* pu);   // update in the imu reference
    void UpdateW(const double* pu);  // update in the world reference

    inline Vec2_t cam_project(const Vec3_t& pos_c) const
    {
        return {camera_->fx_ * pos_c(0) / pos_c(2) + camera_->cx_, camera_->fy_ * pos_c(1) / pos_c(2) + camera_->cy_};
    }
    Vec2_t project_mono(const Vec3_t& Xw) const;
    Vec3_t project_stereo(const Vec3_t& Xw) const;
    bool is_depth_positive(const Vec3_t& Xw) const;

    Eigen::Matrix<double, 2, 3> project_jac(const Eigen::Vector3d& x) const;

public:
    // For IMU
    Eigen::Matrix3d Rwb_;
    Eigen::Vector3d twb_;

    // For camera
    Eigen::Matrix3d Rcw_;
    Eigen::Vector3d tcw_;
    camera::perspective* camera_ = nullptr;

    // For posegraph 4DoF
    Eigen::Matrix3d Rwb0_;
    Eigen::Matrix3d DR_;

    int its_ = 0;
};

// Optimizable parameters are IMU pose
class VertexPose : public ::g2o::BaseVertex<6, ImuCamPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexPose() {}
    VertexPose(Keyframe* pKF);
    VertexPose(Frame* pF);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

class VertexPose4DoF : public ::g2o::BaseVertex<4, ImuCamPose> {
    // Translation and yaw are the only optimizable variables
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexPose4DoF() {}
    VertexPose4DoF(Keyframe* pKF);
    VertexPose4DoF(Frame* pF);
    VertexPose4DoF(Eigen::Matrix3d& Rwc, Eigen::Vector3d& twc, Keyframe* pKF);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

class VertexVelocity : public ::g2o::BaseVertex<3, Eigen::Vector3d> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexVelocity() {}
    VertexVelocity(Keyframe* pKF);
    VertexVelocity(Frame* pF);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

class VertexGyroBias : public ::g2o::BaseVertex<3, Eigen::Vector3d> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexGyroBias() {}
    VertexGyroBias(Keyframe* pKF);
    VertexGyroBias(Frame* pF);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

class VertexAccBias : public ::g2o::BaseVertex<3, Eigen::Vector3d> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexAccBias() {}
    VertexAccBias(Keyframe* pKF);
    VertexAccBias(Frame* pF);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

// Gravity direction vertex
class GDirection {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    GDirection() {}
    GDirection(Eigen::Matrix3d Rwg);

    void Update(const double* pu);

    Eigen::Matrix3d Rwg_;

    int its_ = 0;
};

class VertexGDir : public ::g2o::BaseVertex<2, GDirection> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexGDir() {}
    VertexGDir(Eigen::Matrix3d Rwg);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl() {}

    virtual void oplusImpl(const double* update_);
};

// scale vertex
class VertexScale : public ::g2o::BaseVertex<1, double> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    VertexScale();
    VertexScale(double ps);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    virtual void setToOriginImpl();

    virtual void oplusImpl(const double* update_);
};

class EdgeMono : public ::g2o::BaseBinaryEdge<2, Eigen::Vector2d, ::g2o::VertexPointXYZ, VertexPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeMono() {}

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    bool is_depth_positive();

    Eigen::Matrix<double, 9, 9> GetHessian();
};

class EdgeMonoOnlyPose : public ::g2o::BaseUnaryEdge<2, Eigen::Vector2d, VertexPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeMonoOnlyPose(const Eigen::Vector3d& Xw);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    bool is_depth_positive();

    Eigen::Matrix<double, 6, 6> GetHessian();

public:
    const Eigen::Vector3d Xw_;
};

class EdgeStereo : public ::g2o::BaseBinaryEdge<3, Eigen::Vector3d, ::g2o::VertexPointXYZ, VertexPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeStereo() {}

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    Eigen::Matrix<double, 9, 9> GetHessian();
};

class EdgeStereoOnlyPose : public ::g2o::BaseUnaryEdge<3, Eigen::Vector3d, VertexPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeStereoOnlyPose(const Eigen::Vector3d& Xw);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    Eigen::Matrix<double, 6, 6> GetHessian();

public:
    const Eigen::Vector3d Xw_;  // 3D point coordinates
};

// Edge inertial whre gravity is included as optimizable variable and it is not supposed to be pointing in -z axis, as
// well as scale
class EdgeInertialGS : public ::g2o::BaseMultiEdge<9, Vec9_t> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeInertialGS(data::IMU_Preintegration_Ptr imu_preintegration_ptr);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();
    virtual void linearizeOplus();

    const Eigen::Matrix3d J_R_bg_, J_v_bg_, J_p_bg_;
    const Eigen::Matrix3d J_v_ba_, J_p_ba_;
    data::IMU_Preintegration_Ptr imu_preintegration_ptr_;
    const double integration_time_;
    Eigen::Vector3d g_;
};

class EdgeInertial : public ::g2o::BaseMultiEdge<9, Vec9_t> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeInertial(data::IMU_Preintegration_Ptr imu_preintegration_ptr);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();
    virtual void linearizeOplus();

    Eigen::Matrix<double, 24, 24> GetHessian();

    Eigen::Matrix<double, 9, 9> GetHessian2();

    const Eigen::Matrix3d J_R_bg_, J_v_bg_, J_p_bg_;
    const Eigen::Matrix3d J_v_ba_, J_p_ba_;
    data::IMU_Preintegration_Ptr imu_preintegration_ptr_;
    const double integration_time_;
    Eigen::Vector3d g_;
};

class EdgeGyroRW : public ::g2o::BaseBinaryEdge<3, Eigen::Vector3d, VertexGyroBias, VertexGyroBias> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeGyroRW() {}

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    Eigen::Matrix<double, 6, 6> GetHessian();

    Eigen::Matrix3d GetHessian2();
};

class EdgeAccRW : public ::g2o::BaseBinaryEdge<3, Eigen::Vector3d, VertexAccBias, VertexAccBias> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeAccRW() {}

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    Eigen::Matrix<double, 6, 6> GetHessian();

    Eigen::Matrix3d GetHessian2();
};

// Priors for biases
class EdgePriorAcc : public ::g2o::BaseUnaryEdge<3, Eigen::Vector3d, VertexAccBias> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgePriorAcc(const Eigen::Vector3d& bprior);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    const Eigen::Vector3d bprior_;
};

class EdgePriorGyro : public ::g2o::BaseUnaryEdge<3, Eigen::Vector3d, VertexGyroBias> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgePriorGyro(const Eigen::Vector3d& bprior);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    const Eigen::Vector3d bprior_;
};

class Edge4DoF : public ::g2o::BaseBinaryEdge<6, Vec6_t, VertexPose4DoF, VertexPose4DoF> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    Edge4DoF(const Eigen::Matrix4d& delta_T);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    // virtual void linearizeOplus(); // numerical implementation

    Eigen::Matrix4d delta_Tij_;
    Eigen::Matrix3d delta_Rij_;
    Eigen::Vector3d delta_tij_;
};

class ConstraintPoseImu {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    ConstraintPoseImu(const Eigen::Matrix3d& Rwb, const Eigen::Vector3d& twb, const Eigen::Vector3d& vwb,
                      const Eigen::Vector3d& bg, const Eigen::Vector3d& ba, const Eigen::Matrix<double, 15, 15>& H);

    Eigen::Matrix3d Rwb_;
    Eigen::Vector3d twb_;
    Eigen::Vector3d vwb_;
    Eigen::Vector3d bg_;
    Eigen::Vector3d ba_;
    Eigen::Matrix<double, 15, 15> H_;
};

class EdgePriorPoseImu : public ::g2o::BaseMultiEdge<15, Vec15_t> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    EdgePriorPoseImu(ConstraintPoseImu* c);

    virtual bool read(std::istream&) { return false; }
    virtual bool write(std::ostream&) const { return false; }

    void computeError();

    virtual void linearizeOplus();

    Eigen::Matrix<double, 15, 15> GetHessian();

    Eigen::Matrix3d Rwb_;
    Eigen::Vector3d twb_, vwb_;
    Eigen::Vector3d bg_, ba_;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
#endif
