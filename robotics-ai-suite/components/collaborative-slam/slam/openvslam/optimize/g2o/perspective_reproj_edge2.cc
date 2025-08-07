// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/perspective_reproj_edge2.h"

namespace openvslam {
namespace optimize {
namespace g2o {

mono_perspective_reproj_edge2::mono_perspective_reproj_edge2()
    : BaseBinaryEdge<2, Vec2_t, landmark_vertex, camera_pose_vertex>()
{
}

bool mono_perspective_reproj_edge2::read(std::istream&) { return true; }

bool mono_perspective_reproj_edge2::write(std::ostream& os) const { return os.good(); }

void mono_perspective_reproj_edge2::linearizeOplus()
{
    auto vj = static_cast<camera_pose_vertex*>(_vertices.at(1));
    const Mat44_t cam_pose_cw = vj->camera_pose_vertex::estimate();

    auto vi = static_cast<landmark_vertex*>(_vertices.at(0));
    const Vec3_t& pos_w = vi->landmark_vertex::estimate();
    const Mat33_t rot_cw = cam_pose_cw.block(0, 0, 3, 3);

    const Vec3_t pos_c = rot_cw * pos_w + cam_pose_cw.block(0, 3, 3, 1);

    const auto x = pos_c(0);
    const auto y = pos_c(1);
    const auto z = pos_c(2);
    const auto z_sq = z * z;

    // _jacobianOplusXi(0, 0) = -fx_ * rot_cw(0, 0) / z + fx_ * x * rot_cw(2, 0) / z_sq;
    // _jacobianOplusXi(0, 1) = -fx_ * rot_cw(0, 1) / z + fx_ * x * rot_cw(2, 1) / z_sq;
    // _jacobianOplusXi(0, 2) = -fx_ * rot_cw(0, 2) / z + fx_ * x * rot_cw(2, 2) / z_sq;

    // _jacobianOplusXi(1, 0) = -fy_ * rot_cw(1, 0) / z + fy_ * y * rot_cw(2, 0) / z_sq;
    // _jacobianOplusXi(1, 1) = -fy_ * rot_cw(1, 1) / z + fy_ * y * rot_cw(2, 1) / z_sq;
    // _jacobianOplusXi(1, 2) = -fy_ * rot_cw(1, 2) / z + fy_ * y * rot_cw(2, 2) / z_sq;

    Mat23_t J23;
    J23 << fx_ / z, 0, -fx_ * x / z_sq, 0, fy_ / z, -fy_ * y / z_sq;

    _jacobianOplusXi = -J23 * rot_cw;

    Mat36_t J36;
    Mat33_t pos_w_hat;
    pos_w_hat << 0, -pos_w[2], pos_w[1], pos_w[2], 0, -pos_w[0], -pos_w[1], pos_w[0], 0;

    J36.block(0, 0, 3, 3) = -rot_cw * pos_w_hat;
    J36.block(0, 3, 3, 3) = Eigen::Matrix3d::Identity();
    _jacobianOplusXj = -J23 * J36;
}

stereo_perspective_reproj_edge2::stereo_perspective_reproj_edge2()
    : BaseBinaryEdge<3, Vec3_t, landmark_vertex, camera_pose_vertex>()
{
}

bool stereo_perspective_reproj_edge2::read(std::istream&) { return true; }

bool stereo_perspective_reproj_edge2::write(std::ostream& os) const { return os.good(); }

void stereo_perspective_reproj_edge2::linearizeOplus()
{
    auto vj = static_cast<camera_pose_vertex*>(_vertices.at(1));
    const Mat44_t cam_pose_cw = vj->camera_pose_vertex::estimate();

    auto vi = static_cast<landmark_vertex*>(_vertices.at(0));
    const Vec3_t& pos_w = vi->landmark_vertex::estimate();
    const Mat33_t rot_cw = cam_pose_cw.block(0, 0, 3, 3);

    const Vec3_t pos_c = rot_cw * pos_w + cam_pose_cw.block(0, 3, 3, 1);

    const auto x = pos_c(0);
    const auto y = pos_c(1);
    const auto z = pos_c(2);
    const auto z_sq = z * z;

    _jacobianOplusXi(0, 0) = -fx_ * rot_cw(0, 0) / z + fx_ * x * rot_cw(2, 0) / z_sq;
    _jacobianOplusXi(0, 1) = -fx_ * rot_cw(0, 1) / z + fx_ * x * rot_cw(2, 1) / z_sq;
    _jacobianOplusXi(0, 2) = -fx_ * rot_cw(0, 2) / z + fx_ * x * rot_cw(2, 2) / z_sq;

    _jacobianOplusXi(1, 0) = -fy_ * rot_cw(1, 0) / z + fy_ * y * rot_cw(2, 0) / z_sq;
    _jacobianOplusXi(1, 1) = -fy_ * rot_cw(1, 1) / z + fy_ * y * rot_cw(2, 1) / z_sq;
    _jacobianOplusXi(1, 2) = -fy_ * rot_cw(1, 2) / z + fy_ * y * rot_cw(2, 2) / z_sq;

    _jacobianOplusXi(2, 0) = _jacobianOplusXi(0, 0) - focal_x_baseline_ * rot_cw(2, 0) / z_sq;
    _jacobianOplusXi(2, 1) = _jacobianOplusXi(0, 1) - focal_x_baseline_ * rot_cw(2, 1) / z_sq;
    _jacobianOplusXi(2, 2) = _jacobianOplusXi(0, 2) - focal_x_baseline_ * rot_cw(2, 2) / z_sq;

    Mat23_t J23;
    J23 << fx_ / z, 0, -fx_ * x / z_sq, 0, fy_ / z, -fy_ * y / z_sq;

    Mat36_t J36;
    Mat33_t pos_w_hat;
    pos_w_hat << 0, -pos_w[2], pos_w[1], pos_w[2], 0, -pos_w[0], -pos_w[1], pos_w[0], 0;

    J36.block(0, 0, 3, 3) = -rot_cw * pos_w_hat;
    J36.block(0, 3, 3, 3) = Mat33_t::Identity();

    _jacobianOplusXj.block(0, 0, 2, 6) = -J23 * J36;

    _jacobianOplusXj.block(2, 0, 1, 6) =
        _jacobianOplusXj.block(0, 0, 1, 6) - focal_x_baseline_ / z_sq * J36.block(2, 0, 1, 6);
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
