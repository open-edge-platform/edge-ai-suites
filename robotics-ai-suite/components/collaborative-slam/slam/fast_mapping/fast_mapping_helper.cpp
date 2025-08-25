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

#include "fast_mapping_helper.h"
#include "fast_mapping_param.h"

#include <cmath>
#include <Eigen/Core>
#include <geometry_msgs/msg/point32.h>
#include <visualization_msgs/msg/marker.hpp>
#include <spdlog/spdlog.h>

#define EPSILON        0.00001
#define INFINITE_X     99999.9

namespace fast_mapping {

bool within_map_boundary(const std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree, const Eigen::Vector3i& coords,
                         int& x_dir, int& y_dir, int& z_dir)
{
    const int size = octree->size();

    if (coords.x() >= size)
        x_dir = 1;
    else if (coords.x() < 0)
        x_dir = -1;
    if (coords.y() >= size)
        y_dir = 1;
    else if (coords.y() < 0)
        y_dir = -1;
    if (coords.z() >= size)
        z_dir = 1;
    else if (coords.z() < 0)
        z_dir = -1;

    if (x_dir != 0 || y_dir != 0 || z_dir != 0) {
        return false;
    }

    return true;
}

void save_octree_map(std::string& file_path, const struct camera_intrinsics& intrinsics,
                     const struct se_cfg& octree_cfg, se::Octree<SE_FIELD_TYPE>& octree)
{
    std::ofstream octree_map(file_path, std::ios::binary);

    spdlog::debug("Start to save octree map to {}", file_path);
    /*
        1. save configurations and camera intrinsic parameters
           in order to confirm them between two sessions when
           doing remapping.
    */
    const struct camera_intrinsics* p_intrinsics = &intrinsics;
    octree_map.write(reinterpret_cast<char *>(const_cast<struct camera_intrinsics*>(p_intrinsics)),
                                              sizeof(intrinsics));
    const struct se_cfg* p_octree_cfg = &octree_cfg;
    octree_map.write(reinterpret_cast<char *>(const_cast<struct se_cfg*>(p_octree_cfg)),
                                              sizeof(octree_cfg));

    /*
        2. save the octree map.
    */
    octree.save(octree_map);

    /*
        3. print related parameters saved to octree map.
    */
    /*
    std::cout << intrinsics << std::endl;
    std::cout << octree_cfg << std::endl;
    std::cout << "Origin Position: " << octree.get_origin_position().transpose() << std::endl;
    std::cout << "Octree Size: " << octree.size() << std::endl;
    std::cout << "Octree Dim: " << octree.dim() << std::endl;
    std::cout << "Octree Block Buffer Size: " << octree.getBlockBuffer().size() << std::endl;
    std::cout << "Octree Node Buffer Size: " << octree.getNodesBuffer().size() << std::endl;
    */
    spdlog::debug("Finish to save octree map to {}", file_path);
}

void load_octree_map(std::string& file_path, struct camera_intrinsics& intrinsics, struct se_cfg& octree_cfg,
                     std::shared_ptr<se::Octree<SE_FIELD_TYPE>>& octree)
{
    std::ifstream octree_map(file_path, std::ios::binary);
    octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();

    spdlog::debug("Start to load octree map from {}", file_path);
    /*
        1. load configurations and camera intrinsic parameters
           in order to confirm them between two sessions when
           doing remapping.
    */
    octree_map.read(reinterpret_cast<char *>(&intrinsics), sizeof(intrinsics));
    octree_map.read(reinterpret_cast<char *>(&octree_cfg), sizeof(octree_cfg));

    /*
        2. load the octree map.
    */
    octree->load(octree_map);

    /*
        3. print related parameters loaded from octree map.
    */
    /*
    std::cout << intrinsics << std::endl;
    std::cout << octree_cfg << std::endl;
    std::cout << "Origin Position: " << octree->get_origin_position().transpose() << std::endl;
    std::cout << "Octree Size: " << octree->size() << std::endl;
    std::cout << "Octree Dim: " << octree->dim() << std::endl;
    std::cout << "Octree Block Buffer Size: " << octree->getBlockBuffer().size() << std::endl;
    std::cout << "Octree Node Buffer Size: " << octree->getNodesBuffer().size() << std::endl;
    */
    spdlog::debug("Finish to load octree map from {}", file_path);
}

std_msgs::msg::ColorRGBA scaled_float_to_color(float val)
{
    int idx;
    float s = 1.0;
    float v = 1.0;
    float x, y, z;
    std_msgs::msg::ColorRGBA clr;
    clr.a = 1.0;

    if (val < 0.)
    {
        val = 0.;
    }
    if (val > 1.)
    {
        val = 1.;
    }
    val *= 6;

    idx = floor(val);
    z = val - idx;
    if (!(idx & 1))
    {
      /* if i is even. */
      z = 1 - z;
    }
    x = v * (1 - s);
    y = v * (1 - s * z);

    switch (idx)
    {
    case 6:
    case 0:
        clr.r = v;
        clr.g = y;
        clr.b = x;
        break;
    case 1:
        clr.r = y;
        clr.g = v;
        clr.b = x;
        break;
    case 2:
        clr.r = x;
        clr.g = v;
        clr.b = y;
        break;
    case 3:
        clr.r = x;
        clr.g = y;
        clr.b = v;
        break;
    case 4:
      clr.r = y;
      clr.g = x;
      clr.b = v;
      break;
    case 5:
        clr.r = v;
        clr.g = x;
        clr.b = y;
        break;
    default:
        clr.r = 1;
        clr.g = 0.5;
        clr.b = 0.5;
        break;
    }

    return clr;
}

void add_color_to_marker_points(visualization_msgs::msg::Marker &marker, std::string color_axis,
                                float color_axis_min, float color_axis_max)
{
    std::function<double(const geometry_msgs::msg::Point &)> get_value;
    if (color_axis == "x")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.x; };
    else if (color_axis == "y")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.y; };
    else if (color_axis == "z")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.z; };
    else
        return;

    float min = color_axis_min;
    float range = color_axis_max - min;
    if (range <= 0)
    {
        // decide the value range with current data
        auto compare_value = [get_value](const geometry_msgs::msg::Point &a,
                                         const geometry_msgs::msg::Point &b)
        { return get_value(a) < get_value(b); };

        auto minmax = std::minmax_element(marker.points.begin(), marker.points.end(), compare_value);
        min = get_value(*minmax.first);
        range = get_value(*minmax.second) - min;
    }
    size_t size = marker.points.size();
    marker.colors.clear();
    marker.colors.reserve(size);
    for (size_t i = 0; i < size; ++i)
    {
        const auto color = scaled_float_to_color((get_value(marker.points[i]) - min) / range);
        marker.colors.push_back(color);
    }
}

remapping_region::remapping_region(struct point_2d vertexes[4], bool log_info)
{
    auto distance = [](struct point_2d point1, struct point_2d point2) -> double {
        return sqrt(pow(point1.x_ - point2.x_, 2) + pow(point1.y_ - point2.y_, 2));
    };

    // check if points are too close to each other
    for (unsigned int i = 0; i < 4; i++) {
        if (distance(vertexes[i], vertexes[(i + 1) % 4]) < EPSILON) {
            spdlog::error("In remapping region, vertexes {} and {} are too close!", i, (i + 1) % 4);
            throw std::invalid_argument("Failed to create remapping region!");
        }
    }

    if (log_info) spdlog::info("Construct remapping region!");
    for (unsigned int i = 0; i < 4; i++) {
        edges_[i] = {vertexes[i], vertexes[(i + 1) % 4]};
        if (log_info) {
            spdlog::info("Edge {}: [({}, {}), ({}, {})]", i, edges_[i].vertexes_[0].x_, edges_[i].vertexes_[0].y_,
                         edges_[i].vertexes_[1].x_, edges_[i].vertexes_[1].y_);
        }
    }

    // check if edges are colinear
    for (unsigned int i = 0; i < 4; i++) {
        if (cross_product(edges_[i], edges_[(i + 1) % 4]) == 0) {
            spdlog::error("In remapping region, edges {} and {} are colinear!", i, (i + 1) % 4);
            throw std::invalid_argument("Failed to create remapping region!");
        }
    }
}

int remapping_region::cross_product(struct line_segment_2d line1, struct line_segment_2d line2)
{
    double line1_x = line1.vertexes_[1].x_ - line1.vertexes_[0].x_;
    double line1_y = line1.vertexes_[1].y_ - line1.vertexes_[0].y_;
    double line2_x = line2.vertexes_[1].x_ - line2.vertexes_[0].x_;
    double line2_y = line2.vertexes_[1].y_ - line2.vertexes_[0].y_;

    double product = line1_x * line2_y - line2_x * line1_y;
    if (product > EPSILON) {
        return 1;
    }
    else if (product < -EPSILON) {
        return -1;
    }
    else {
        return 0;
    }
}

bool remapping_region::two_line_segments_intersect(struct line_segment_2d line1, struct line_segment_2d line2)
{
    if (cross_product(line1, {line1.vertexes_[0], line2.vertexes_[0]}) *
        cross_product(line1, {line1.vertexes_[0], line2.vertexes_[1]}) < 0) {
        if (cross_product(line2, {line2.vertexes_[0], line1.vertexes_[0]}) *
            cross_product(line2, {line2.vertexes_[0], line1.vertexes_[1]}) < 0) {
            return true;
        }
    }

    return false;
}

bool remapping_region::intersect_with_any_edges(struct line_segment_2d line)
{
    for (auto& edge : edges_)
        if (two_line_segments_intersect(edge, line)) return true;

    return false;
}

bool remapping_region::within_remapping_region(struct point_2d point)
{
    int intersection_count = 0;

    /*
        count the intersections between a horizontal line, which started
        at the given point and extended to infinity, and the edges of the
        remapping region.
    */
    struct point_2d infinite_point = {INFINITE_X, point.y_};
    struct line_segment_2d infinite_line  = {point, infinite_point};
    for (int i = 0; i < 4; i++)
        if (two_line_segments_intersect(edges_[i], infinite_line)) intersection_count++;

    return intersection_count & 1;
}

uint64_t convert_pose_id_to_masked_timestamp(uint64_t pose_id) { return pose_id & ((1ULL << BIT_SHIFTS) - 1); }

uint64_t convert_timestamp_to_pose_id(uint8_t client_id, double frame_timestamp)
{
    auto timestamp = static_cast<uint64_t>(frame_timestamp * 1'000'000'000);
    return (uint64_t(client_id) << BIT_SHIFTS) | (timestamp & ((1ULL << BIT_SHIFTS) - 1));
}

bool remapping_region::intersect_with_region(class remapping_region region)
{
    /*
        1. check if the vertexes of the given region are within
           the remapping region.
    */
    for (auto& edge : region.edges_) {
        struct point_2d vertex = edge.vertexes_[0];
        if (within_remapping_region(vertex)) return true;
    }

    /*
        2. check if the vertexes of the remapping region are within
           the given region.
    */
    for (auto& edge : edges_) {
        struct point_2d vertex = edge.vertexes_[0];
        if (region.within_remapping_region(vertex)) return true;
    }

    /*
        3. check if the edges of the given region intersects with
           any of the edge of the remapping region.
    */
    for (auto& edge : region.edges_)
        if (intersect_with_any_edges(edge)) return true;

    return false;
}

} // namespace fast_mapping
