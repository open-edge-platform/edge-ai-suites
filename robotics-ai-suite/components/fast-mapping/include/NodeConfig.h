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

#include <string>

// Structure grouping all the configuration parameters of FastMapping.
    struct NodeConfig
    {
        // Min and max values
        float p_voxel_color_axis_min_;
        float p_voxel_color_axis_max_;

        // Size of the voxel
        float p_map_resolution_;

        // Maximum size of the depth ray
        float p_depth_max_range_;

        // Min and max values of the 'z' axis - gives the height of the robot
        float p_projection_min_z_;
        float p_projection_max_z_;

        // Interval of the logging time
        float p_stat_log_interval_;

        // Diameter of the robot to be marked free
        float p_robot_radius_;

        // Noise factor when generating the 2D map
        float p_noise_factor_;

        // Z Min and Max for the 3D map
        float p_zmin_;

        float p_zmax_;

        // Wait for transformation delay
        float p_tf_delay_;

        // Size of the volumetric map
        int p_map_size_;

        // Factor for scaling the depth image
        int p_depth_scale_ratio_;

        // Size of the queue holding the frames
        int p_frame_queue_size_;

        // Maximum size of the image
        int p_res_max_width_;
        int p_res_max_height_;

        // set to x/y/z to publish voxels colored along corrosponding world axis, or empty for unitary color
        std::string p_voxel_color_axis_;

        // depth info topic
        std::string p_depth_info_topic_;

        // depth topic
        std::string p_depth_topic_;

        // Map frame
        std::string p_map_frame_;

        NodeConfig() :
            p_voxel_color_axis_min_(-1.),
            p_voxel_color_axis_max_(4.),
            p_map_resolution_(0.04), // 4cm
            p_depth_max_range_(6),
            p_projection_min_z_(.1),
            p_projection_max_z_(1),
            p_stat_log_interval_(3), //seconds
            p_robot_radius_(0.2), // 20 cm
            p_noise_factor_(0.02),
            p_zmin_(-std::numeric_limits<float>::infinity()),
            p_zmax_(std::numeric_limits<float>::infinity()),
            p_tf_delay_(.5),
            p_map_size_(512),
            p_depth_scale_ratio_(2),
            p_frame_queue_size_(10),
            p_res_max_width_(1028),
            p_res_max_height_(768),
            p_voxel_color_axis_("z"),
            p_map_frame_("map")
        {}
    };