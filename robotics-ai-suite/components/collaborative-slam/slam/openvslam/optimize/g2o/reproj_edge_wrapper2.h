// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_G2O_SE3_REPROJ_EDGE_WRAPPER2_H
#define OPENVSLAM_OPTIMIZE_G2O_SE3_REPROJ_EDGE_WRAPPER2_H

#include "camera/perspective.h"
#include "camera/fisheye.h"
//#include "camera/equirectangular.h"
#include "optimize/g2o/perspective_reproj_edge2.h"
#include <g2o/core/robust_kernel_impl.h>
#include "camera_pose_vertex.h"
namespace openvslam {

namespace data {
class landmark;
}  // namespace data

namespace optimize {
namespace g2o {

template <typename T>
class reproj_edge_wrapper2 {
public:
    reproj_edge_wrapper2() = delete;

    reproj_edge_wrapper2(T* shot, camera_pose_vertex* shot_vtx, data::landmark* lm, landmark_vertex* lm_vtx,
                         const unsigned int idx, const float obs_x, const float obs_y, const float obs_x_right,
                         const float inv_sigma_sq, const float sqrt_chi_sq, const bool use_huber_loss = true);

    virtual ~reproj_edge_wrapper2() = default;

    inline bool is_inlier() const { return edge_->level() == 0; }

    inline bool is_outlier() const { return edge_->level() != 0; }

    inline void set_as_inlier() const { edge_->setLevel(0); }

    inline void set_as_outlier() const { edge_->setLevel(1); }

    inline bool depth_is_positive() const;

    ::g2o::OptimizableGraph::Edge* edge_;

    camera::base* camera_;
    T* shot_;
    data::landmark* lm_;
    const unsigned int idx_;
    const bool is_monocular_;
};

template <typename T>
reproj_edge_wrapper2<T>::reproj_edge_wrapper2(T* shot, camera_pose_vertex* shot_vtx, data::landmark* lm,
                                              landmark_vertex* lm_vtx, const unsigned int idx, const float obs_x,
                                              const float obs_y, const float obs_x_right, const float inv_sigma_sq,
                                              const float sqrt_chi_sq, const bool use_huber_loss)
    : camera_(shot->camera_), shot_(shot), lm_(lm), idx_(idx), is_monocular_(obs_x_right < 0)
{
    switch (camera_->model_type_) {
        case camera::model_type_t::Perspective: {
            auto c = static_cast<camera::perspective*>(camera_);
            if (is_monocular_) {
                auto edge = new mono_perspective_reproj_edge2();

                const Vec2_t obs{obs_x, obs_y};
                edge->setMeasurement(obs);
                edge->setInformation(Mat22_t::Identity() * inv_sigma_sq);

                edge->fx_ = c->fx_;
                edge->fy_ = c->fy_;
                edge->cx_ = c->cx_;
                edge->cy_ = c->cy_;

                edge->setVertex(0, lm_vtx);
                edge->setVertex(1, shot_vtx);

                edge_ = edge;
            } else {
                auto edge = new stereo_perspective_reproj_edge2();

                const Vec3_t obs{obs_x, obs_y, obs_x_right};
                edge->setMeasurement(obs);
                edge->setInformation(Mat33_t::Identity() * inv_sigma_sq);

                edge->fx_ = c->fx_;
                edge->fy_ = c->fy_;
                edge->cx_ = c->cx_;
                edge->cy_ = c->cy_;
                edge->focal_x_baseline_ = camera_->focal_x_baseline_;

                edge->setVertex(0, lm_vtx);
                edge->setVertex(1, shot_vtx);

                edge_ = edge;
            }
            break;
        }
        case camera::model_type_t::Fisheye: {
            auto c = static_cast<camera::fisheye*>(camera_);
            if (is_monocular_) {
                auto edge = new mono_perspective_reproj_edge2();

                const Vec2_t obs{obs_x, obs_y};
                edge->setMeasurement(obs);
                edge->setInformation(Mat22_t::Identity() * inv_sigma_sq);

                edge->fx_ = c->fx_;
                edge->fy_ = c->fy_;
                edge->cx_ = c->cx_;
                edge->cy_ = c->cy_;

                edge->setVertex(0, lm_vtx);
                edge->setVertex(1, shot_vtx);

                edge_ = edge;
            } else {
                auto edge = new stereo_perspective_reproj_edge2();

                const Vec3_t obs{obs_x, obs_y, obs_x_right};
                edge->setMeasurement(obs);
                edge->setInformation(Mat33_t::Identity() * inv_sigma_sq);

                edge->fx_ = c->fx_;
                edge->fy_ = c->fy_;
                edge->cx_ = c->cx_;
                edge->cy_ = c->cy_;
                edge->focal_x_baseline_ = camera_->focal_x_baseline_;

                edge->setVertex(0, lm_vtx);
                edge->setVertex(1, shot_vtx);

                edge_ = edge;
            }
            break;
        }
        default:
            edge_ = nullptr;
            throw std::invalid_argument("Equirectangular camera not yet supported");
            break;

            // case camera::model_type_t::Equirectangular: {
            //     assert(is_monocular_);

            //     auto c = static_cast<camera::equirectangular*>(camera_);

            //     auto edge = new equirectangular_reproj_edge();

            //     const Vec2_t obs{obs_x, obs_y};
            //     edge->setMeasurement(obs);
            //     edge->setInformation(Mat22_t::Identity() * inv_sigma_sq);

            //     edge->cols_ = c->cols_;
            //     edge->rows_ = c->rows_;

            //     edge->setVertex(0, lm_vtx);
            //     edge->setVertex(1, shot_vtx);

            //     edge_ = edge;

            //     break;
            // }
    }

    // loss functionを設定
    if (use_huber_loss) {
        auto huber_kernel = new ::g2o::RobustKernelHuber();
        huber_kernel->setDelta(sqrt_chi_sq);
        if (!edge_) {
            throw std::runtime_error("invalid edge_");
        }
        edge_->setRobustKernel(huber_kernel);
    }
}

template <typename T>
bool reproj_edge_wrapper2<T>::depth_is_positive() const
{
    switch (camera_->model_type_) {
        case camera::model_type_t::Perspective: {
            if (is_monocular_) {
                return static_cast<mono_perspective_reproj_edge2*>(edge_)
                    ->mono_perspective_reproj_edge2::depth_is_positive();
            } else {
                return static_cast<stereo_perspective_reproj_edge2*>(edge_)
                    ->stereo_perspective_reproj_edge2::depth_is_positive();
            }
        }
        case camera::model_type_t::Fisheye: {
            if (is_monocular_) {
                return static_cast<mono_perspective_reproj_edge2*>(edge_)
                    ->mono_perspective_reproj_edge2::depth_is_positive();
            } else {
                return static_cast<stereo_perspective_reproj_edge2*>(edge_)
                    ->stereo_perspective_reproj_edge2::depth_is_positive();
            }
        }
        case camera::model_type_t::Equirectangular: {
            return true;
        }
    }

    return true;
}

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_G2O_SE3_REPROJ_EDGE_WRAPPER_H
