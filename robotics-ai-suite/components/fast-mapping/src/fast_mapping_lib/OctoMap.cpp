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

#include "OctoMap.h"
#include "logger.h"

#include <se/functors/projective_functor.hpp>
#include <se/bfusion/mapping_impl.hpp>
#include <se/functors/projective_functor.hpp>

// Class constructor
OctoMap::OctoMap(struct OctreeConfiguration& config)
{
    octree_cfg_ = config;

    octree_ = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
    octree_->init(config.voxel_per_side, config.volume_size_meter);

    const auto vol = -config.volume_size_meter * 0.5;
    setOrigin(vol, vol, std::isfinite(config.zmax) ? config.zmax : vol);
}

// Check if the world points are exceeding the Octree boundry
Eigen::Vector3i OctoMap::checkMapBoundry(const std::vector<Eigen::Vector3f> &points_world) const
{
    const float inverse_voxel_size = octree_->size() / octree_->dim();
    const int size = octree_->size();

    int x_dir = 0, y_dir = 0, z_dir = 0;
    for (const auto &point : points_world)
    {
        Eigen::Vector3f voxel_scaled = (point * inverse_voxel_size).array().floor();

        if (voxel_scaled.x() >= size) x_dir = 1;
        else if (voxel_scaled.x() < 0) x_dir = -1;
        if (voxel_scaled.y() >= size) y_dir = 1;
        else if (voxel_scaled.y() < 0) y_dir = -1;
        if (voxel_scaled.z() >= size) z_dir = 1;
        else if (voxel_scaled.z() < 0) z_dir = -1;
        if (x_dir != 0 && y_dir != 0 && z_dir != 0) break;
    }
    return Eigen::Vector3i(x_dir, y_dir, z_dir);
}

void OctoMap::integrate(std::shared_ptr<ImageFrame> frame)
{
    cv::Mat depth = frame->image2;
    if (depth.empty()) return;

    std::optional<Eigen::Matrix4d> Tcw = frame->maybe_pose;
    if (!Tcw) return;

    Eigen::Matrix4d T_wc = *Tcw;

    const auto depth_ptr = depth.ptr<unsigned short>();
    const auto scaled_intrinsics = getScaledIntrinsics();
    const int scale_ratio = octree_cfg_.compute_size_ratio;
    const unsigned int out_w = depth.size().width / scale_ratio;
    const unsigned int out_h = depth.size().height / scale_ratio;
    const unsigned int width_multiply_ratio = depth.size().width * scale_ratio;

    // Extract points from depth image and scale to meters
    std::vector<float>points(out_w * out_h);
    for (unsigned int y = 0; y < out_h; y++)
    {
        unsigned int in_offset = width_multiply_ratio * y;
        unsigned int out_offset = out_w * y;
        for (unsigned int x = 0; x < out_w; x++)
        {
            float dist = static_cast<float>(depth_ptr[x * scale_ratio + in_offset]) / 1000.0;
            points[x + out_offset] = dist < octree_cfg_.depth_max_range ? dist : 0;
        }
    }

    // Convert to pointcloud
    Eigen::Matrix4f k_pose = T_wc.cast<float>() * scaled_intrinsics.invK4();
    Eigen::Vector3f offset = offset_.topRightCorner<3, 1>() + dynamic_offset_;
    int i = 0;

    if (!world_points_.empty()) world_points_.clear();

    for (unsigned int y = 0; y < out_h; y++)
    {
        for (unsigned int x = 0; x < out_w; x++)
        {
            auto depth = std::abs(points[i++]);
            if (depth == 0) continue;
            Eigen::Vector3f point = (k_pose * (Eigen::Vector3f(x, y, 1) * depth).homogeneous()).head<3>();
            world_points_.push_back(point + offset);
        }
    }

    // Add Octree offset to camera
    Eigen::Matrix4f octree_pose = T_wc.cast<float>() + offset_;
    octree_pose.topRightCorner<3, 1>() += dynamic_offset_;

    // check whether we need to extend the octree
    world_points_.push_back(octree_pose.topRightCorner<3, 1>());

    Eigen::Vector3i direction = checkMapBoundry(world_points_);
    if (direction(0) != 0 || direction(1) != 0 || direction(2) != 0)
    {
        auto new_offset = octree_->expand(direction);
        dynamic_offset_ += new_offset;
        origin_position_ -= new_offset;

        octree_pose.topRightCorner<3, 1>() += new_offset;
        for (auto& point : world_points_)
        {
            point += new_offset;
        }
    }
    world_points_.pop_back();

    // compute the max and min height with respect to the octree position
    float zmin = octree_cfg_.zmin + dynamic_offset_(2) + offset_(2, 3);
    float zmax = octree_cfg_.zmax + dynamic_offset_(2) + offset_(2, 3);

    Eigen::Matrix4f K = scaled_intrinsics.K4();
    float n = 6 * octree_cfg_.noise_factor; // band around the depth points

    octree_->allocate_points(world_points_, octree_pose, zmin, zmax, n, id_);

    // timer_.startNextProc("Update probabilities");

    // Update proabilities of each occupied Node/VoxelBlock
    Eigen::Vector2i computation_size = Eigen::Vector2i(out_w, out_h);
    float timestamp = (1.f / 30.f) * frame->timestamp;
    struct bfusion_update funct(points.data(), computation_size, octree_cfg_.noise_factor, timestamp, octree_cfg_.logodds_lower, octree_cfg_.logodds_upper);
    se::functor::projective_map(*octree_, octree_pose.inverse(), K, computation_size, funct);

    FM_LOG(debug) << "Integrated frame with ID " << id_ <<std::endl;

    id_++;
}