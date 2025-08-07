// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "config.h"
#include "camera/perspective.h"
#include "camera/fisheye.h"
#include "camera/equirectangular.h"
#include <opencv2/core/eigen.hpp>
#include <sensor_msgs/msg/camera_info.hpp>

#include <spdlog/spdlog.h>

#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <ament_index_cpp/get_package_share_directory.hpp>

#define EPSILON           0.00001
#define MAX_ITERATIONS    10000

bool cmpf(double A, double B, double epsilon = EPSILON) {
    return (fabs(A - B) < epsilon);
}

namespace openvslam {

config::config(const std::string& config_file_path) : config(YAML::LoadFile(config_file_path), config_file_path) {}

config::config(const YAML::Node& yaml_node, const std::string& config_file_path)
    : config_file_path_(config_file_path), yaml_node_(yaml_node)
{
    spdlog::debug("CONSTRUCT: config");

    spdlog::info("config file loaded: {}", config_file_path_);

    throw std::invalid_argument("Loading configurations from yaml file is not yet supported!");
}

config::config(rclcpp::Node *pnh, std::string config_path):pnh_(pnh), config_path_(config_path)
{
    spdlog::debug("CONSTRUCT: config from ros parameters");

    get_ros_param("server_mode", server_mode_, "mapping");

    get_ros_param("grid_size", map_grid_size_, map_grid_size_);

    // grid_size should not be 0 since division is done with grid_size
    if (cmpf(map_grid_size_, 0.0))
        throw std::invalid_argument("Grid size cannot be 0!");

    get_ros_param("vocabulary", vocabulary_path_, vocabulary_path_);
    do {
        // check whether the given path is absolute or relative to the config folder
        auto exist = [](std::string filename) {
            std::ifstream fs(filename);
            return fs.good();
        };
        if (exist(vocabulary_path_)) break;
        std::string another_path = config_path_ + vocabulary_path_;
        if (exist(another_path)) {
            vocabulary_path_ = another_path;
            break;
        }
        std::string package_dir = ament_index_cpp::get_package_share_directory("univloc_server");
        spdlog::info("univloc server package dir is {}", package_dir);
        std::string alternative_path = package_dir + "/config/" + vocabulary_path_;
        if (exist(alternative_path)) {
            vocabulary_path_ = alternative_path;
            break;
        }
        throw std::invalid_argument("Wrong vocabulary path: " + vocabulary_path_);
    } while (false);

    get_ros_param("fix_scale", fix_scale_, fix_scale_);

    get_ros_param("correct_loop", correct_loop_, correct_loop_);

    get_ros_param("save_map_path", save_map_path_, std::string(""));

    get_ros_param("load_map_path", load_map_path_, std::string(""));

    get_ros_param("server_remapping_region", remapping_region_vertexes_);

    get_ros_param("front_rear_camera_constraint_thr", front_rear_camera_constraint_thr_, 0.5);

    get_ros_param("iteration_times", iteration_times_, 10);
    // Iteration time should be positive and not big number since
    if (iteration_times_ < 0 || iteration_times_ > MAX_ITERATIONS)
        throw std::invalid_argument("Number of iteration times should be between : 0 - " + std::to_string(MAX_ITERATIONS));

    get_ros_param("use_segment_optimize", segment_optimize_, false);

    get_ros_param("server_zmin", server_zmin_, 0.3);

    get_ros_param("server_zmax", server_zmax_, 0.6);
}

config::~config()
{
    spdlog::debug("DESTRUCT: config");
}

std::ostream& operator<<(std::ostream& os, const config& /*cfg*/)
{
    // TODO print parameters

    return os;
}

bool config::is_config_valid()
{
    if (server_mode_ == "mapping") {
        if (!load_map_path_.empty()) {
            spdlog::critical("Option load_map_path should be empty in mapping mode!");
            return false;
        }
    }
    else if (server_mode_ == "remapping") {
        if (load_map_path_.empty()) {
            spdlog::critical("Option load_map_path shouldn't be empty in remapping mode!");
            return false;
        }
        if (remapping_region_vertexes_.size() != 8) {
            spdlog::critical("Option remapping_region should include 4 points in the format of [P1.x, P1.y \
                              P2.x, P2.y, P3.x, P3.y, P4.x, P4.y]");
            return false;
        }
    }
    else if(server_mode_ ==  "localization" || server_mode_ ==  "relocalization") {
        if (load_map_path_.empty()) {
            spdlog::critical("Option load_map_path shouldn't be empty in localization and relocalization mode!");
            return false;
        }
    } else {
        spdlog::critical("Invalid value of server_mode option, only support mapping, localization or remapping!");
        return false;
    }

    return true;
}

}  // namespace openvslam
