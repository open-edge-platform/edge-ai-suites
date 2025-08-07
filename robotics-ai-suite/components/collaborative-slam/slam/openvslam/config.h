// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include "rclcpp/rclcpp.hpp"
#include <yaml-cpp/yaml.h>

namespace openvslam {

class config {
public:
    //! Constructor
    explicit config(const std::string& config_file_path);
    explicit config(const YAML::Node& yaml_node, const std::string& config_file_path = "");
    explicit config(rclcpp::Node *pnh, std::string config_path = "");
    //! Destructor
    ~config();

    friend std::ostream& operator<<(std::ostream& os, const config& cfg);

    bool is_config_valid();

    //! ROS1 and ROS2 get param

    template <typename T>
    void get_ros_param(std::string name, T& dst, const T& default_value)
    {
        dst = pnh_->declare_parameter(name, default_value);
    }

    template <typename T>
    void get_ros_param(std::string name, T& dst)
    {
        //pnh_.param(name, dst, dst);
        get_ros_param(name, dst, dst);
    }

    void get_ros_param(std::string name, std::string& dst, const char* default_value)
    {
        get_ros_param(name, dst, std::string(default_value));
    }

    void get_ros_param(std::string name, float& dst, double default_value)
    {
        get_ros_param(name, dst, static_cast<float>(default_value));
    }

    //! path to config YAML file
    const std::string config_file_path_;

    //! YAML node
    const YAML::Node yaml_node_;

    std::string server_mode_ = "";

    double map_grid_size_ = 0.1;

    std::string vocabulary_path_ = std::string("orb_vocab.dbow2");

    bool fix_scale_ = true;

    bool correct_loop_ = true;

    std::string save_map_path_;

    std::string load_map_path_;

    double front_rear_camera_constraint_thr_ = 0.0;

    int iteration_times_ = 0;

    bool segment_optimize_ = false;

    rclcpp::Node *pnh_;

    std::string config_path_;

    float server_zmin_ = 0.3; // Min and max values of the 'z' axis - gives the height of the robot

    float server_zmax_ = 0.6;

    std::vector<double> remapping_region_vertexes_; // Format: P1.x, P1,y, P2.x, P2.y, P3.x, P3.y, P4.x, P4.y
};

}  // namespace openvslam

