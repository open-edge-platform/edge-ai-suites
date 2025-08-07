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

#pragma once
#include <se/volume_traits.hpp>
#include <se/octree.hpp>

#include <memory>
#include <map>
#include <iostream>
#include <vector>

#include "ImageFrame.h"

class OctoMap {

public:

    struct Intrinsics
    {
        int width;  /**< Width of the image in pixels */
        int height; /**< Height of the image in pixels */
        float ppx;  /**< Horizontal coordinate of the principal point of the image, as a pixel offset from the left edge */
        float ppy;  /**< Vertical coordinate of the principal point of the image, as a pixel offset from the top edge */
        float fx;   /**< Focal length of the image plane, as a multiple of pixel width */
        float fy;   /**< Focal length of the image plane, as a multiple of pixel height */
        //rs2_distortion model;    /**< Distortion model of the image */

        Intrinsics()
            : width(0), height(0), ppx(0), ppy(0), fx(0), fy(0)
        {}

        Intrinsics (int width_, int height_, float ppx_, float ppy_, float fx_, float fy_, std::vector<double> coeffs_)
            : width(width_), height(height_), ppx(ppx_), ppy(ppy_), fx(fx_), fy(fy_)
        {
            for (double c : coeffs_) {
                if(std::abs(c) > 1e-3) {
                    std::cout << "[fast_mapping] Image has distortion. Not yet supported!" <<std::endl;
                }
            }
        }

        Intrinsics downscale(const int ratio) const
        {
            Intrinsics out;
            out.width = width / ratio;
            out.height = height / ratio;
            out.ppx = ppx / ratio;
            out.ppy = ppy / ratio;
            out.fx = fx / ratio;
            out.fy = fy / ratio;
            return out;
        }

        inline Eigen::Matrix3f K() const
        {
            Eigen::Matrix3f K;
            K << fx, 0, ppx,
                0, fy, ppy,
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
            K << fx, 0, ppx, 0,
                0, fy, ppy, 0,
                0, 0, 1, 0,
                0, 0, 0, 1;
            return K;
        }

        inline Eigen::Matrix4f invK4() const
        {
            return K4().inverse();
        }
    };

     struct OctreeConfiguration
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
    };

    // Class Constructor
    OctoMap(struct OctreeConfiguration& config);

    // Implicit Destructor
    ~OctoMap() {};

    // Class methods


    // Sets camera intrinsics
    void setIntrinsics(const int height, const int width, const float ppx, const float ppy, const float fx, const float fy)
    {
        intrinsics_.height = height;
        intrinsics_.width = width;
        intrinsics_.fx = fx;
        intrinsics_.fy = fy;
        intrinsics_.ppx = ppx;
        intrinsics_.ppy = ppy;
    }

    // Integrates graph of poses into the Octree
    void integrate(std::shared_ptr<ImageFrame> frame);

    // Returns a referece to the Octree
    se::Octree<SE_FIELD_TYPE>& getOctree() { return *octree_; }

    // Get origin position of the Octree
    const Eigen::Vector3f& getOriginPosition() { return origin_position_; }

    // Get the scaled intrinsics
    struct Intrinsics getScaledIntrinsics() { return intrinsics_.downscale(octree_cfg_.compute_size_ratio); }


    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

private:

    // Check if the world points are withing the boundry of the cube
    Eigen::Vector3i checkMapBoundry(const std::vector<Eigen::Vector3f> &points_world) const;

    // Set origin of the volume cube
    void setOrigin(const float x, const float y, const float z)
    {
        origin_position_ = Eigen::Vector3f(x,y,z);
        offset_(0, 3) = -x;
        offset_(1, 3) = -y;
        offset_(2, 3) = -z;
    }

    // Configuration
    struct OctreeConfiguration octree_cfg_;

    // Camera Intrinsics
    struct Intrinsics intrinsics_;

    // The Octree
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_;

    // Origin of the cube
    Eigen::Vector3f origin_position_ = Eigen::Vector3f::Zero();

    // Offset relative to the cube origin position
    Eigen::Matrix4f offset_ = Eigen::Matrix4f::Zero();

    // Dynamic offset when expanding the Octree
    Eigen::Vector3f dynamic_offset_ =  Eigen::Vector3f::Zero();

    // 3D world points
    std::vector<Eigen::Vector3f> world_points_;

    int id_ = 0;
};
