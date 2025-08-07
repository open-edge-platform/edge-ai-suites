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

#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/World.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo_ros/node.hpp>
#include <gazebo_ros/utils.hpp>
#include <std_srvs/srv/set_bool.hpp>
#include <std_srvs/srv/empty.hpp>

class GazeboROSNameSpace : public gazebo::SystemPlugin
{
public:
  /// Constructor
  GazeboROSNameSpace();
  ~GazeboROSNameSpace();
  // Documentation inherited
  void Load(int argc, char ** argv) override;

  /// Callback when a world is created.
  /// \param[in] _world_name The world's name
  void OnWorldCreated(const std::string & _world_name);

  void OnClearNameSpace(
    const std::shared_ptr<std_srvs::srv::Empty::Request> /*req*/,
    std::shared_ptr<std_srvs::srv::Empty::Response> res);

  /// \brief Keep a pointer to the world.
  gazebo::physics::WorldPtr world_;

  /// Gazebo-ROS node
  gazebo_ros::Node::SharedPtr ros_node_;


  /// ROS service to handle requests to unpause physics.
  rclcpp::Service<std_srvs::srv::Empty>::SharedPtr  namespace_reset_service_;

  /// To be notified once the world is created.
  gazebo::event::ConnectionPtr world_created_event_;

};

GazeboROSNameSpace::~GazeboROSNameSpace()
{
 
}

void GazeboROSNameSpace::Load(int argc, char ** argv) //(gazebo::physics::WorldPtr _world, sdf::ElementPtr _sdf)
{
  if (!rclcpp::ok()) {
      rclcpp::init(argc, argv);      
    } 

  try
  {
    ros_node_ = gazebo_ros::Node::Get();
    namespace_reset_service_ = ros_node_->create_service<std_srvs::srv::Empty>(
      "clear_namespace",
      std::bind(
        &GazeboROSNameSpace::OnClearNameSpace, this,
        std::placeholders::_1, std::placeholders::_2));
  }
  catch (const std::exception& e)
  {
    RCLCPP_ERROR(
        ros_node_->get_logger(), "Exception occured while loading plugin: %s", e.what());    
  }
}


GazeboROSNameSpace::GazeboROSNameSpace()
{
}

void GazeboROSNameSpace::OnClearNameSpace(
  const std::shared_ptr<std_srvs::srv::Empty::Request> /*_req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>  _res)
{
  try
  {
    auto rcl_context = rclcpp::contexts::get_global_default_context()->get_rcl_context();
    if (rcl_context) {
        rcl_arguments_t rcl_args = rcl_get_zero_initialized_arguments();

        // Initialize arguments with empty contents
        rcl_ret_t ret = rcl_parse_arguments(0,NULL, rcl_get_default_allocator(), &rcl_args);
        ret = ret;
        // Free up space from previous call
        ret = rcl_arguments_fini(&rcl_context->global_arguments);
        ret = ret;

        rcl_context->global_arguments = rcl_args;
        RCLCPP_INFO(
        ros_node_->get_logger(), "Namespace cleared");
    }
  }
  catch (const std::exception& e)
  {
    RCLCPP_ERROR(
        ros_node_->get_logger(), "Exception occured while clearing namespace: %s", e.what());    
  }
}

GZ_REGISTER_SYSTEM_PLUGIN(GazeboROSNameSpace)
