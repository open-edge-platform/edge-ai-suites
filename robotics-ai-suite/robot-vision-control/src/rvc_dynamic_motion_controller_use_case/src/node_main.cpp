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

#include "rvc_dynamic_motion_controller_use_case/state_machine.hpp"

#include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"
#include "rvc_grasp_interface/rvc_grasp_interface.hpp"
#include <pluginlib/class_loader.hpp>


/// @brief main of the application, spawns a state machine node and a goalcontroller and spi ros2
/// @param argc argument count
/// @param argv argument vector
/// @return 0 on success, 1 on failure

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);

    RCLCPP_DEBUG(rclcpp::get_logger("node_main"), "robot_demo_main package starting StateMachine");

    auto stateMachine = std::make_shared<StateMachine>();

    stateMachine->declare_parameter<std::string>(
        "motion_controller",
        "RVCMotionController::Moveit2ServoMotionController");
    stateMachine->declare_parameter<std::string>("grasp_plugin", "RVCControl::NonOrientedGrasp");
    std::string motionControllerName = stateMachine->get_parameter("motion_controller").as_string();
    std::string graspPluginName = stateMachine->get_parameter("grasp_plugin").as_string();

    RCLCPP_INFO(stateMachine->get_logger(), "LOADING MOTION CONTROLLER plugin: %s", motionControllerName.c_str());
    pluginlib::ClassLoader<RVCMotionController::RVCMotionControllerInterface> motionControllerLoader(
        "rvc_motion_controller_interface", "RVCMotionController::RVCMotionControllerInterface");
    std::shared_ptr<RVCMotionController::RVCMotionControllerInterface> motionController;
    pluginlib::ClassLoader<RVCControl::RVCGraspInterface> graspLoader("rvc_grasp_interface",
        "RVCControl::RVCGraspInterface");
    std::shared_ptr<RVCControl::RVCGraspInterface> graspPlugin;

    try
    {
        //get from yaml
        motionController = motionControllerLoader.createSharedInstance(motionControllerName);
        if (! motionController->init(stateMachine))
            return 1;
    } catch (std::exception & e)
    {
        RCLCPP_INFO(
            stateMachine->get_logger(), "Exception %s while loading plugin %s\n",
            e.what(), motionControllerName.c_str());
        return 1;
    }
    try
    {
        //get from yaml
        graspPlugin = graspLoader.createSharedInstance(graspPluginName);
        RCLCPP_INFO(stateMachine->get_logger(), "Calling grasp plugin init...");
        if (!graspPlugin->init(stateMachine))
            return 1;
        RCLCPP_INFO(stateMachine->get_logger(), "Calling grasp plugin init... DONE");
    } catch (std::exception & e)
    {
        RCLCPP_INFO(
            stateMachine->get_logger(), "Exception %s while loading plugin %s\n",
            e.what(), graspPluginName.c_str());
        return 1;
    }
    RCLCPP_INFO(stateMachine->get_logger(), "Plugins loaded successfully, initializing state machine...");

    try
    {
        bool ret = stateMachine->init(motionController.get(), graspPlugin.get());

        if (ret)
        {
            rclcpp::spin(stateMachine);
        }

        RCLCPP_INFO(stateMachine->get_logger(), "rclcpp shutdown");
        rclcpp::shutdown();

        RCLCPP_INFO(stateMachine->get_logger(), "package Clean Exit");
    }
    catch (std::exception & e)
    {
        RCLCPP_INFO(stateMachine->get_logger(), "node_main.cpp: spinning Exception %s\n", e.what());
        return 1;
    }

    return 0;
}
