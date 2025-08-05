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

#ifndef FAST_MAPPING_HELPER_H
#define FAST_MAPPING_HELPER_H

#ifdef SE_FIELD_TYPE
#undef SE_FIELD_TYPE
#endif
#define SE_FIELD_TYPE OFusion

#include "fast_mapping_param.h"
#include "se/volume_traits.hpp"
#include "se/octree.hpp"

#include <Eigen/Core>
#include <geometry_msgs/msg/point32.h>
#include <visualization_msgs/msg/marker.hpp>

#define OCTREE_CORRECT_THRESHOLD 0.5 * 1'000'000'000
// The data type of "pose_id_" is uint64_t. The data type of "ClientID" is uint8_t.
// We want to make the first 8 bits of "pose_id_" represent client ID and the remaining 56 bits represent the
// corresponding (key)frame's timestamp.
#define BIT_SHIFTS (sizeof(uint64_t) - sizeof(uint8_t)) * 8

namespace fast_mapping {
// check if the world point (in voxel coordinate) is within the boundary of the cube
bool within_map_boundary(const std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree, const Eigen::Vector3i& coords,
                         int& x_dir, int& y_dir, int& z_dir);

// save octree map to a binary file
void save_octree_map(std::string& file_path, const struct camera_intrinsics& intrinsics,
                     const struct se_cfg& octree_cfg, se::Octree<SE_FIELD_TYPE>& octree);

// load octree map from a binary file
void load_octree_map(std::string& file_path, struct camera_intrinsics& intrinsics, struct se_cfg& octree_cfg,
                     std::shared_ptr<se::Octree<SE_FIELD_TYPE>>& octree);

std_msgs::msg::ColorRGBA scaled_float_to_color(float val);

void add_color_to_marker_points(visualization_msgs::msg::Marker &marker, std::string color_axis,
                                float color_axis_min, float color_axis_max);

uint64_t convert_pose_id_to_masked_timestamp(uint64_t pose_id);

uint64_t convert_timestamp_to_pose_id(uint8_t client_id, double frame_timestamp);

// 2D remapping region described by 4 2D points
class remapping_region {
public:
    remapping_region(struct point_2d vertexes[4], bool log_info = true);

    ~remapping_region() = default;

    /*
        check if a given line segment intersects with any egdes
        of the remapping region. 
    */
    bool intersect_with_any_edges(struct line_segment_2d line);

    bool within_remapping_region(struct point_2d point);

    /*
        check if a given 2D region intersects with the remapping
        region (has common areas).
    */
    bool intersect_with_region(class remapping_region region);

private:
    /*
        calculate the cross product for two given line segments (line1 x line2).
        1 : cross product > 0;
        0 : cross product = 0;
        -1: cross product < 0;
    */
    int cross_product(struct line_segment_2d line1, struct line_segment_2d line2);

    /*
        check if two given line segments intersect with each other
    */
    bool two_line_segments_intersect(struct line_segment_2d line1, struct line_segment_2d line2);

    struct line_segment_2d edges_[4];
};

} // namespace fast_mapping

#endif
