// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#ifndef FAST_MAPPING_PARAM_H
#define FAST_MAPPING_PARAM_H

#include <iostream>
#include <Eigen/Core>

namespace fast_mapping {

    const float unknown_tol = 0.4;
    const float unknown_upper = std::log((0.5 + unknown_tol) / (0.5 - unknown_tol));
    const float unknown_lower = 0.0;
    // const float unknown_lower = std::log((0.5 - unknown_tol) / (0.5 + unknown_tol));
    const int8_t occupied_prob = 100;
    const int8_t free_prob = 0;
    const int8_t unknown_prob = -1;

    struct camera_intrinsics
    {
        int width;  /**< Width of the image in pixels */
        int height; /**< Height of the image in pixels */
        float cx;  /**< Horizontal coordinate of the principal point of the image,
                        as a pixel offset from the left edge */
        float cy;  /**< Vertical coordinate of the principal point of the image,
                        as a pixel offset from the top edge */
        float fx;   /**< Focal length of the image plane, as a multiple of pixel width */
        float fy;   /**< Focal length of the image plane, as a multiple of pixel height */
        //rs2_distortion model;    /**< Distortion model of the image */

        camera_intrinsics()
            : width(0), height(0), cx(0), cy(0), fx(0), fy(0)
        {}

        camera_intrinsics (const int width_, const int height_, const float cx_, const float cy_, const float fx_, const float fy_)
            : width(width_), height(height_), cx(cx_), cy(cy_), fx(fx_), fy(fy_)
        {}

        camera_intrinsics downscale(const int ratio)
        {
            camera_intrinsics out;
            out.width = width / ratio;
            out.height = height / ratio;
            out.cx = cx / ratio;
            out.cy = cy / ratio;
            out.fx = fx / ratio;
            out.fy = fy / ratio;
            return out;
        }

        inline Eigen::Matrix3f K() const
        {
            Eigen::Matrix3f K;
            K << fx, 0, cx,
                0, fy, cy,
                0, 0, 1;
            return K;
        }

        inline Eigen::Matrix3f invK() const
        {
            return K().inverse();
        }

        inline Eigen::Matrix4f K4() const
        {
            Eigen::Matrix4f K;
            K << fx, 0, cx, 0,
                0, fy, cy, 0,
                0, 0, 1, 0,
                0, 0, 0, 1;
            return K;
        }

        inline Eigen::Matrix4f invK4() const
        {
            return K4().inverse();
        }

        friend std::ostream& operator<<(std::ostream& os, const struct camera_intrinsics& intrinsics)
        {
            return os << "Camera Intrinsics\n"
                      << "{\n"
                      << "    width: " << intrinsics.width << "\n"
                      << "    height: " << intrinsics.height << "\n"
                      << "    cx: " << intrinsics.cx << "\n"
                      << "    cy: " << intrinsics.cy << "\n"
                      << "    fx: " << intrinsics.fx << "\n"
                      << "    fy: " << intrinsics.fy << "\n"
                      << "}";
        }
    };

    struct se_cfg
    {
        int compute_size_ratio;
        int voxel_per_side;
        float volume_size_meter;
        float noise_factor;
        float logodds_lower;
        float logodds_upper;
        float zmin;
        float zmax;
        float depth_max_range;
        int correction_threshold;

        se_cfg()
            : compute_size_ratio(0), voxel_per_side(0), volume_size_meter(0.0), noise_factor(0.0), logodds_lower(0.0),
              logodds_upper(0.0), zmin(0.0), zmax(0.0), depth_max_range(0.0), correction_threshold(0)
        {}

        friend std::ostream& operator<<(std::ostream& os, const struct se_cfg cfg)
        {
            return os << "Octree Configuration\n"
                      << "{\n"
                      << "    compute_size_ratio: " << cfg.compute_size_ratio << "\n"
                      << "    voxel_per_side: " << cfg.voxel_per_side << "\n"
                      << "    volume_size_meter: " << cfg.volume_size_meter << "\n"
                      << "    noise_factor: " << cfg.noise_factor << "\n"
                      << "    logodds_lower: " << cfg.logodds_lower << "\n"
                      << "    logodds_upper: " << cfg.logodds_upper << "\n"
                      << "    zmin: " << cfg.zmin << "\n"
                      << "    zmax: " << cfg.zmax << "\n"
                      << "    depth_max_range: " << cfg.depth_max_range << "\n"
                      << "    correction_threshold: " << cfg.correction_threshold << "\n"
                      << "}";
        }
    };

    // point of 2D region
    struct point_2d {
        double x_;
        double y_;
    };

    // line segment of 2D region
    struct line_segment_2d {
        struct point_2d vertexes_[2];
    };

}  //namespace fast_mapping

#endif  // FAST_MAPPING_PARAM_H
