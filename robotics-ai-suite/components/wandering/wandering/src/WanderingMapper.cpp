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

#include <std_msgs/msg/string.hpp>
#include "nav2_util/robot_utils.hpp"
#include "geometry_msgs/msg/point.hpp"

#include "WanderingMapper.h"

#define FULL_ROTATION       360
#define ANGLE_SPEED         30
#define UNEXPLORED_MAP_GOAL 30
#define MIN_ROBOT_RADIUS    0.001
#define MAX_ROBOT_RADIUS    10.0

using std::placeholders::_1;
using namespace std::chrono_literals;

WanderingMapper::WanderingMapper()
  : Node("wandering_mapper"), initialized_(false), transform_tolerance_(1), robotRadius_(0), global_frame_("map"),
    robot_base_frame_("base_link"), occupancyGridTopic_("/map"), costMapTopic_("/global_costmap/costmap"),
    shouldStop_(false), initRotate_(false), shouldResetAll_(false), shouldPauseWandering_(false)
  {
      rclcpp::QoS map_qos(10);  // initialize to default

      this->declare_parameter("robot_radius", 0.177);
      this->get_parameter("robot_radius", this->robotRadius_);
      RCLCPP_INFO(this->get_logger(), "Robot radius set to: %f\n", this->robotRadius_);
      this->mapEngine_ = std::make_shared<MapEngine>(true, this->robotRadius_);
      this->goalCatcher_ = std::make_shared<GoalCatcher>(this, this->global_frame_, this->robot_base_frame_, this->robotRadius_);
      // In future this should come from args or config file
      //mapSubscription_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
      //  this->occupancyGridTopic_, map_qos, std::bind(&MapEngine::mapCallback, this->mapEngine_, std::placeholders::_1));
      costMapSubscription_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
        this->costMapTopic_, map_qos, std::bind(&MapEngine::mapCallback, this->mapEngine_, std::placeholders::_1));

      poseSubscription_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
        "/wander/to", 1, std::bind(&WanderingMapper::goToLocation, this, _1));

      pauseWanderingSubscription = this->create_subscription<std_msgs::msg::Bool>(
        "/wander/pause_wandering", 1, std::bind(&WanderingMapper::pauseWanderingCallback, this, _1));


      this->tf_ = std::make_shared<tf2_ros::Buffer>(this->get_clock());
      this->listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_);

      if (this->robotRadius_ < MIN_ROBOT_RADIUS || this->robotRadius_ > MAX_ROBOT_RADIUS) {
        RCLCPP_ERROR(this->get_logger(), "Robot radius has invalid value! %f", this->robotRadius_);
        throw std::range_error("Invalid Robot radius size!");
      }
      this->timer_ = this->create_wall_timer(100ms, std::bind(&WanderingMapper::timerCallback, this));
  }

WanderingMapper::~WanderingMapper() {
  RCLCPP_INFO(this->get_logger(), "Wandering mapper destructor");
}

void WanderingMapper::timerCallback() {
  if (!this->initialized_) {
    this->initialized_ = this->init();
    if (this->initialized_)
      RCLCPP_INFO(this->get_logger(), "Wandering initialization done!");
    return;
  }

  if (!this->shouldPauseWandering_)
  {
    if (!this->initRotate_) {
      this->rotate();
      return;
    }

    if (!this->isMapped())
      this->doMap();
  }
  else
  {
      RCLCPP_INFO(this->get_logger(), "Wandering is Paused.");
  }
}

void WanderingMapper::resetMapHistory()
{
    RCLCPP_INFO(this->get_logger(), "Will Reset visited places...");
    this->mapEngine_->resetVisitedMap();
    this->goalCatcher_->resetVisitedPlaces();
}

bool WanderingMapper::init() {
    if (!this->initMap())
        return false;

    if (!this->areTfFramesPresent())
      return false;
    if (!this->getRobotPosition(this->initial_pose_))
      return false;
    if (!this->mapEngine_->setRobotPose(this->initial_pose_))
      return false;

    return this->goalCatcher_->init();
}

bool WanderingMapper::areTfFramesPresent() {
    std::vector< std::string > ids;
    this->tf_->_getFrameStrings(ids);
    if (std::find(ids.begin(), ids.end(), this->global_frame_) != ids.end()) {
        if (!(std::find(ids.begin(), ids.end(), this->robot_base_frame_) != ids.end())) {
            RCLCPP_WARN(this->get_logger(), "Frame %s not present in tf list...", this->robot_base_frame_.c_str());
            return false;
        }
    }
    else {
        RCLCPP_WARN(this->get_logger(), "Frame %s not present in tf list...", this->global_frame_.c_str());
        return false;
    }

    return true;
}


void WanderingMapper::goToLocation(const geometry_msgs::msg::PoseStamped::SharedPtr msg){
    nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal = std::make_shared<nav2_msgs::action::NavigateToPose::Goal>();
    goal->pose = *msg;

    this->resetMapHistory();
    rclcpp::sleep_for(std::chrono::seconds(1));
    this->goalCatcher_->send_goal(goal, rclcpp::Node::now());
}


void WanderingMapper::pauseWanderingCallback(const std_msgs::msg::Bool::ConstPtr msg){
      RCLCPP_INFO(this->get_logger(), "pauseWanderingCallback %d", msg->data);
      bool shouldPause = msg->data;
      this->shouldPauseWandering_ = shouldPause;

// Reset of the entire Mapping process is needed because the robot may be moved during the pause
      if (shouldPause)
            this->resetMapHistory();
}

bool WanderingMapper::initMap() {
    RCLCPP_INFO(this->get_logger(), "Waiting for the map");
    rclcpp::sleep_for(std::chrono::seconds(1));
    return this->mapEngine_->init();
}

bool WanderingMapper::isMapped() {
    this->mapEngine_->checkMapCoverage();
    if (this->mapEngine_->getUnexploredPrstg() < UNEXPLORED_MAP_GOAL) {
        RCLCPP_INFO(this->get_logger(), "Mapped!");
        return true;
    }
    else if (this->shouldStop_)
      return true;
    if (this->mapEngine_->shouldReset()) {
      RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Resetting visited goals...");
      this->goalCatcher_->resetVisitedPlaces();
      this->initRotate_ = false;
      return true;
    }
    return false;
}

bool WanderingMapper::getRobotPosition(geometry_msgs::msg::PoseStamped &pose) {
    if (!nav2_util::getCurrentPose(
        pose, *tf_, global_frame_, robot_base_frame_,
        transform_tolerance_)) {
        RCLCPP_ERROR(this->get_logger(), "Current robot pose is not available.");
        return false;
    }

    return true;
}

void WanderingMapper::doMap() {
    if (this->goalCatcher_->isMoving())
        return;

    geometry_msgs::msg::PoseStamped robotPose;
    if (!this->getRobotPosition(robotPose))
      return;
    this->mapEngine_->setRobotPose(robotPose);
    double x = 0.0, y = 0.0;
    if (!this->mapEngine_->getNextGoalCoord(x, y)) {
      RCLCPP_INFO(this->get_logger(), "No more coordinates for mapping! Area is either mapped or robot is stuck.");
      // Sleep here first to get updated map
      if (!this->shouldResetAll_){
        rclcpp::sleep_for(std::chrono::seconds(2));
        this->shouldResetAll_ = true;
        RCLCPP_INFO(this->get_logger(), "Will try to wait for a map update...");
      } else {
        this->resetMapHistory();
      }
      return;
    }

    nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal = std::make_shared<nav2_msgs::action::NavigateToPose::Goal>();
    goal->pose.pose.position.x = x;
    goal->pose.pose.position.y = y;

    this->goalCatcher_->send_goal(goal, rclcpp::Node::now());
    this->shouldResetAll_ = false;
}

void WanderingMapper::rotate() {
    if (this->goalCatcher_->isRotating())
      return;

    geometry_msgs::msg::PoseStamped pose;
    if (!this->getRobotPosition(pose))
      return;

    nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal = std::make_shared<nav2_msgs::action::NavigateToPose::Goal>();

    goal->pose.pose = pose.pose;
    goal->behavior_tree =
      std::string(ament_index_cpp::get_package_share_directory("wandering_app")
                  + "/behavior_trees/spin360.xml");

    this->goalCatcher_->send_goal(goal, rclcpp::Node::now());
    RCLCPP_INFO(this->get_logger(), "Rotate...");

    this->initRotate_ = true;
}
