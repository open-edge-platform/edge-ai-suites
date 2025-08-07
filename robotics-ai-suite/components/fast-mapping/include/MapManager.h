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

#include <rclcpp/rclcpp.hpp>
#include <rclcpp/time.hpp>

#include <nav_msgs/msg/occupancy_grid.hpp>
#include <std_srvs/srv/empty.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <visualization_msgs/msg/marker.hpp>
#include <std_msgs/msg/color_rgba.hpp>

#include "OctoMap.h"
#include "NodeConfig.h"

class MapManager :  public rclcpp::Node
{

public:
    static constexpr float unknown_tol = 0.4;
    static constexpr float unknown_upper = std::log((0.5 + unknown_tol) / (0.5 - unknown_tol));
    static constexpr float unknown_lower = std::log((0.5 - unknown_tol) / (0.5 + unknown_tol));

    // Class constructor
    MapManager(std::shared_ptr<OctoMap> octomap, struct NodeConfig& config);

    ~MapManager();


    void publish_maps(std::shared_ptr<ImageFrame> currFrame);

    // Helper function to clear the RVIZ markers
    void clearMarkers();

private:
    // The Octree representation of the free space is too coarse therefore
    // use the depth image to update the free space for navigation.
    void updateFreeOrUnknownSpace(std::shared_ptr<ImageFrame> currFrame);

    void publish_occupancy_map();

    void publish_volumetric_map();

    // Pointer to the Octomap class holding the depth images and poses
    std::shared_ptr<OctoMap> octomap_;
    // Occupancy grid
    nav_msgs::msg::OccupancyGrid::SharedPtr grid_template_;
    // 3D map of occupied voxels
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_fused_map_;
    // 3D occupancy map of occupied and free voxels
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_occupancy_;
    // 2D map
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_planar_map_;
    // Node config
    struct NodeConfig config_;
};