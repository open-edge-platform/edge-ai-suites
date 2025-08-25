// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_PERSPECTIVE_REPROJ_EDGE2_H
#define OPENVSLAM_OPTIMIZER_G2O_PERSPECTIVE_REPROJ_EDGE2_H

// In this edge, keyframe pose is parameterized with position and rotation matrix, instead of SE(3)

#include "type.h"
#include "optimize/g2o/landmark_vertex.h"
#include "camera_pose_vertex.h"
#include <g2o/core/base_binary_edge.h>
#include <g2o/core/base_unary_edge.h>

namespace openvslam {
namespace optimize {
namespace g2o {

class mono_perspective_reproj_edge2 final
    : public ::g2o::BaseBinaryEdge<2, Vec2_t, landmark_vertex, camera_pose_vertex> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    mono_perspective_reproj_edge2();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    double initial_chi2_ = 0.1;

    bool computed_initial_chi2 = false;

    void computeError() override
    {
        const auto v1 = static_cast<const camera_pose_vertex*>(_vertices.at(1));
        const auto v2 = static_cast<const landmark_vertex*>(_vertices.at(0));
        const Vec2_t obs(_measurement);
        const Vec3_t pos_c = v1->estimate().block(0, 0, 3, 3) * v2->estimate() + v1->estimate().block(0, 3, 3, 1);
        _error = obs - cam_project(pos_c);

        if (!computed_initial_chi2) {
            computed_initial_chi2 = true;
            initial_chi2_ = chi2();
            if (initial_chi2_ < 0) {
                std::cout << initial_chi2_ << std::endl;
                std::cout << _error.transpose() << std::endl;
                std::cout << information() << std::endl;
                abort();
            }
        }
    }

    void linearizeOplus() override;

    bool depth_is_positive() const
    {
        const auto v1 = static_cast<const camera_pose_vertex*>(_vertices.at(1));
        const auto v2 = static_cast<const landmark_vertex*>(_vertices.at(0));
        const Vec3_t pos_c = v1->estimate().block(0, 0, 3, 3) * v2->estimate() + v1->estimate().block(0, 3, 3, 1);
        return 0.0 < pos_c[2];
    }

    inline Vec2_t cam_project(const Vec3_t& pos_c) const
    {
        return {fx_ * pos_c(0) / pos_c(2) + cx_, fy_ * pos_c(1) / pos_c(2) + cy_};
    }

    double fx_ = 0.0, fy_ = 0.0, cx_ = 0.0, cy_ = 0.0;
};

class stereo_perspective_reproj_edge2 final
    : public ::g2o::BaseBinaryEdge<3, Vec3_t, landmark_vertex, camera_pose_vertex> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    stereo_perspective_reproj_edge2();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void computeError() override
    {
        const auto v1 = static_cast<const camera_pose_vertex*>(_vertices.at(1));
        const auto v2 = static_cast<const landmark_vertex*>(_vertices.at(0));
        const Vec3_t obs(_measurement);
        const Vec3_t pos_c = v1->estimate().block(0, 0, 3, 3) * v2->estimate() + v1->estimate().block(0, 3, 3, 1);
        _error = obs - cam_project(pos_c);
    }

    void linearizeOplus() override;

    bool depth_is_positive() const
    {
        const auto v1 = static_cast<const camera_pose_vertex*>(_vertices.at(1));
        const auto v2 = static_cast<const landmark_vertex*>(_vertices.at(0));
        const Vec3_t pos_c = v1->estimate().block(0, 0, 3, 3) * v2->estimate() + v1->estimate().block(0, 3, 3, 1);
        return 0 < pos_c[2];
    }

    inline Vec3_t cam_project(const Vec3_t& pos_c) const
    {
        const double reproj_x = fx_ * pos_c(0) / pos_c(2) + cx_;
        return {reproj_x, fy_ * pos_c(1) / pos_c(2) + cy_, reproj_x - focal_x_baseline_ / pos_c(2)};
    }

    double fx_ = 0.0, fy_ = 0.0, cx_ = 0.0, cy_ = 0.0, focal_x_baseline_ = 0.0;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_SE3_PERSPECTIVE_REPROJ_EDGE_H
