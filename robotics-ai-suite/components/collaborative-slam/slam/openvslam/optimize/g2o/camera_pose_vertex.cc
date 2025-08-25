// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "camera_pose_vertex.h"

namespace openvslam {
namespace optimize {
namespace g2o {

Eigen::Matrix3d NormalizeRotation(const Eigen::Matrix3d R)
{
    // Eigen::Quaterniond q(R);
    // q.normalize();
    Eigen::JacobiSVD<Eigen::Matrix3d> svd(R, Eigen::ComputeFullU | Eigen::ComputeFullV);
    return svd.matrixU() * svd.matrixV().transpose();
    // return q.toRotationMatrix();
}

camera_pose_vertex::camera_pose_vertex() : BaseVertex<6, Mat44_t>() { updated_times_ = 0; }

bool camera_pose_vertex::read(std::istream& is) { return is.good(); }

bool camera_pose_vertex::write(std::ostream& os) const { return os.good(); }

void camera_pose_vertex::oplusImpl(const double* update)
{
    Eigen::Map<const Vec6_t> v(update);
    Mat44_t delta_T = Mat44_t::Identity();
    Mat33_t v_hat;
    v_hat << 0, -v[2], v[1], v[2], 0, -v[0], -v[1], v[0], 0;
    delta_T.block(0, 0, 3, 3) = v_hat.exp();
    delta_T.block(0, 3, 3, 1) = v.tail(3);
    //_estimate = _estimate * delta_T;

    _estimate.block(0, 0, 3, 3) = _estimate.block(0, 0, 3, 3) * delta_T.block(0, 0, 3, 3);
    _estimate.block(0, 3, 3, 1) = _estimate.block(0, 3, 3, 1) + v.tail(3);

    updated_times_++;
    if (updated_times_ >= 3) {
        _estimate.block(0, 0, 3, 3) = NormalizeRotation(_estimate.block(0, 0, 3, 3));
        updated_times_ = 0;
    }
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
