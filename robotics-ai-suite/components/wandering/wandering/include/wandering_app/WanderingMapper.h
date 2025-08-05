// SPDX-License-Identifier: Apache-2.0
/*
Copyright (C) 2025 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*/

#include <memory>
#include <functional>
#include <future>

#include "ament_index_cpp/get_package_share_directory.hpp"

#include "rclcpp/rclcpp.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"

#include <nav2_msgs/action/navigate_to_pose.hpp>

#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>

#include <std_msgs/msg/bool.hpp>
#include "geometry_msgs/msg/twist.hpp"

#include "MapEngine.h"
#include "GoalCatcher.h"

class WanderingMapper : public rclcpp::Node
{
public:
  WanderingMapper();
  ~WanderingMapper();
  bool init();
  bool isMapped();
  void doMap();

protected:
  bool areTfFramesPresent();
  bool initialized_;
  std::shared_ptr<MapEngine> mapEngine_;
  std::shared_ptr<GoalCatcher> goalCatcher_;

private:
  bool getRobotPosition(geometry_msgs::msg::PoseStamped &pose);
  void goToLocation(const geometry_msgs::msg::PoseStamped::SharedPtr msg);
  void pauseWanderingCallback(const std_msgs::msg::Bool::ConstPtr msg);
  void resetMapHistory();
  bool initMap();
  void timerCallback();
  void rotate();

  rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr mapSubscription_;
  rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr costMapSubscription_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr poseSubscription_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr pauseWanderingSubscription;

  std::shared_ptr<tf2_ros::Buffer> tf_;
  std::shared_ptr<tf2_ros::TransformListener> listener_;
  rclcpp::TimerBase::SharedPtr timer_;
  geometry_msgs::msg::PoseStamped initial_pose_;
  double transform_tolerance_, robotRadius_;
  std::string global_frame_;
  std::string robot_base_frame_;
  std::string occupancyGridTopic_;
  std::string costMapTopic_;
  bool shouldStop_, initRotate_, shouldResetAll_, shouldPauseWandering_;
};
