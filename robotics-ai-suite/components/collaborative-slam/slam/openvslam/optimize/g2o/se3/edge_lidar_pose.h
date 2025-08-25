// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_SE3_EDGE_LIDAR_POSE_H
#define OPENVSLAM_OPTIMIZER_G2O_SE3_EDGE_LIDAR_POSE_H

#include "type.h"
#include <g2o/core/base_vertex.h>
#include <g2o/core/base_unary_edge.h>
#include <g2o/types/slam3d/se3quat.h>
#include "util/converter.h"

// referenced from: https://github.com/gaoxiang12/slambook2/blob/master/ch7/pose_estimation_3d3d.cpp

namespace openvslam {
namespace optimize {
namespace g2o {
namespace se3 {

class VertexPose : public ::g2o::BaseVertex<6, ::g2o::SE3Quat> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    void setToOriginImpl() override { _estimate = ::g2o::SE3Quat(); }

    // left multiplication on SE3
    void oplusImpl(const double *update_) override
    {
        Eigen::Map<const Vec6_t> update(update_);
        setEstimate(::g2o::SE3Quat::exp(update) * estimate());
    }

    bool read([[maybe_unused]] std::istream &in) override { return false; }

    bool write([[maybe_unused]] std::ostream &out) const override { return false; }
};

class EdgeLidarPose : public ::g2o::BaseUnaryEdge<3, Eigen::Vector3d, VertexPose> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    EdgeLidarPose(const Eigen::Vector3d &point) : _point(point) {}

    void computeError() override
    {
        const VertexPose *pose = static_cast<const VertexPose *>(_vertices[0]);
        _error = _measurement - pose->estimate() * _point;
    }

    void linearizeOplus() override
    {
        VertexPose *pose = static_cast<VertexPose *>(_vertices[0]);
        ::g2o::SE3Quat T = pose->estimate();
        Eigen::Vector3d xyz_trans = T * _point;
        _jacobianOplusXi.block<3, 3>(0, 0) = -Eigen::Matrix3d::Identity();
        _jacobianOplusXi.block<3, 3>(0, 3) = util::converter::to_skew_symmetric_mat(xyz_trans);
    }

    bool read([[maybe_unused]] std::istream &in) { return false; }

    bool write([[maybe_unused]] std::ostream &out) const { return false; }

protected:
    Eigen::Vector3d _point;
};

}  // namespace se3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_SE3_EDGE_LIDAR_POSE_H
