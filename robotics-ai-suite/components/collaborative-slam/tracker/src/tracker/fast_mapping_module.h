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

#ifndef FAST_MAPPING_MODULE_H
#define FAST_MAPPING_MODULE_H

#include <fast_mapping_helper.h>
#include <se/volume_traits.hpp>
#include <se/octree.hpp>

#include <opencv2/opencv.hpp>
#include <spdlog/spdlog.h>

#include <map>
#include <mutex>
#include <vector>
#include <optional>

#include "DataQueue.h"
#include "data/keyframe.h"
#include "LoopTimer.h"

#ifdef SE_FIELD_TYPE
#undef SE_FIELD_TYPE
#endif
#define SE_FIELD_TYPE OFusion

namespace univloc_tracker {
    class Config;
    class ImageFrame;
}

namespace fast_mapping {

    using RequestQueue = DataQueue<std::shared_ptr<univloc_tracker::ImageFrame>>;
    using MapMsgQueue = DataQueue<univloc_msgs::MapConstPtr>;

class fast_mapping_module {

public:

    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    // Constructor
    fast_mapping_module(std::shared_ptr<univloc_tracker::Config> cfg, RequestQueue& reconstruction_queue);

    // Destructor
    ~fast_mapping_module();

    // Returns a reference to the Octree
    se::Octree<SE_FIELD_TYPE>& get_octree();

    // Get a copy of the block list of the Octree
    void get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active);

    // Get a reference of camera intrinsics
    const struct camera_intrinsics& get_camera_intrinsics() const;

    // Get a reference of octree configuration
    const struct se_cfg& get_octree_cfg() const;

    // Update message queue
    void queue_map_message(univloc_msgs::MapConstPtr map_msg);

    // Update octree with the corrected keyframes
    void update_octree_from_server(std::vector<openvslam::data::keyframe*> keyfrms);

    // Set remapping region in remapping mode if region existed
    void construct_remapping_region(std::vector<double> vertexes);

    // run function
    void run();

    // Set transform from the world coordinate of the reference map to the world coordinate of the map to be aligned
    void set_coordinate_transform_matrix(const std::optional<Eigen::Matrix4d>& Tww_aligned_ref);

    std::pair<uint64_t, Eigen::Matrix4d> find_closest_transform(const std::map<uint64_t, Eigen::Matrix4d>& transforms,
                                                                const se::Node<SE_FIELD_TYPE>* node);

    // set the flag of skip processing frame
    void set_skip_processing_frame(bool skip_frame);

    // get the flag of skip processing frame
    bool get_skip_processing_frame() const;

    unsigned int get_tracker_octree_merged_times();

private:

    // Check if the world points are within the boundary of the cube
    Eigen::Vector3i check_map_boundary(const std::vector<Eigen::Vector3f>& points_world) const;

    // Check whether correction from loop closure is enough to trigger an octree reconstruction
    bool correct_octree_from_loop_closure(const Eigen::Matrix4d& cam_pose_wc_before_correction,
                                          const Eigen::Matrix4d& cam_pose_wc_after_correction,
                                          const uint64_t pose_id);

    // Replaces the actuall octree with the global octree from server.
    void update_local_octree_from_server(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> global_octree);

    // Get the scaled intrinsics
    struct camera_intrinsics get_scaled_intrinsics() { return intrinsics_->downscale(octree_cfg_.compute_size_ratio); }

    // integrate a frame in the octree
    void octree_integrate(std::shared_ptr<univloc_tracker::ImageFrame> frame);

    // Configuration
    struct se_cfg octree_cfg_;

    // Camera Intrinsics
    std::unique_ptr<struct camera_intrinsics> intrinsics_;

    // The Octree
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_;

    // Offset relative to the cube origin position
    Eigen::Matrix4f offset_ = Eigen::Matrix4f::Zero();

    // dynamic offset when expanding the Octree
    Eigen::Vector3f dynamic_offset_ = Eigen::Vector3f::Zero();

    // configuration
    std::shared_ptr<univloc_tracker::Config> cfg_;

    // 3D world points
    std::vector<Eigen::Vector3f> world_points_;

    // Queue of localized images ready to be integrated in the octree
    RequestQueue& reconstruction_queue_;

    // MapMsq queue for handling map merge requests
    MapMsgQueue mapmsg_queue_;

    // Remapping region
    std::unique_ptr<fast_mapping::remapping_region> remapping_region_;

    // Octree Mutex
    /*
        TODO: Currently, this lock is only using to protect the nodes buffer and voxel block buffer. Maybe a better
        way in the future is to have a lock within Octree class. But it needs much more time to carefully go
        through each member functions and we don't have much time now.
    */
    mutable std::mutex octree_mutex_;

    // frames counter
    int id_ = 0;

    // Timer
    LoopTimer timer_;

    // Transform from the world coordinate of the reference map to the world coordinate of the map to be aligned
    std::optional<Eigen::Matrix4d> coordinate_transform_ = std::nullopt;

    // If the Octree map of this tracker has been aligned with the loaded Octree map of server in remapping mode
    std::atomic<bool> coordinate_is_aligned_ = false;

    ClientID client_id_;

    // Skip processing frames Mutex
    mutable std::mutex mtx_skip_frame_;

    // Skip processing frames for fast mapping module
    bool skip_frame_ = false;

    // Indicate the times of map merge that tracker has participated
    std::atomic<unsigned int> tracker_octree_merged_times_ = 0;
};

} //namespace fast_mapping
#endif
