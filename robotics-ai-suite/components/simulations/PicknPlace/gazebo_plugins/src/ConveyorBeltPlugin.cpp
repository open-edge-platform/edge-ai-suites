// SPDX-License-Identifier: Apache-2.0
/*
 * Copyright (C) 2017 Open Source Robotics Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
*/

/*
Modification:
    * Merge ConveyorBelt and ROS2 interfacing into a single file
*/

#include <functional>
#include <string>
#include <rclcpp/rclcpp.hpp>

#include "ConveyorBeltPlugin.hpp"
#include "gazebo_compat.hpp"

namespace gz{
namespace sim{
namespace systems{

/////////////////////////////////////////////////
ConveyorBeltPlugin::~ConveyorBeltPlugin()
{
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::Configure(const gazebo::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gazebo::EntityComponentManager &_ecm,
      gazebo::EventManager &)
{
  this->entity = _entity;
  this->model = gazebo::Model(_entity);

  if (!this->model.Valid(_ecm))
  {
    std::cerr << "ConveyorBeltPlugin should be attached to a model entity." << std::endl;
    return;
  }

    // Read SDF params
  if (_sdf)
  {
    if (_sdf->HasElement("max_velocity"))
      this->max_velocity_ = _sdf->Get<double>("max_velocity");
    if (_sdf->HasElement("publish_rate"))
      this->publish_rate_ = _sdf->Get<double>("publish_rate");
    if (_sdf->HasElement("joint_name"))
      this->joint_name_ = _sdf->Get<std::string>("joint_name");

    // Fortress has no JointPositionLimits component; allow overrides here
    if (_sdf->HasElement("lower_limit"))
      this->lower_limit_ = _sdf->Get<double>("lower_limit");
    if (_sdf->HasElement("upper_limit"))
      this->upper_limit_ = _sdf->Get<double>("upper_limit");
  }
  if (this->publish_rate_ <= 0.0) this->publish_rate_ = 1000.0;

  this->publish_period_ = std::chrono::nanoseconds(
      static_cast<int64_t>((1.0 / this->publish_rate_) * 1e9));

  // Resolve joint
  this->joint = model.JointByName(_ecm, this->joint_name_);
  if (this->joint == gazebo::kNullEntity)
  {
    RCLCPP_ERROR(this->ros_node_->get_logger(), "Joint [%s] not found.", this->joint_name_.c_str());
    return;
  }

  // Ensure command component exists
  if (!_ecm.Component<gazebo::components::JointVelocityCmd>(this->joint))
    _ecm.CreateComponent(this->joint, gazebo::components::JointVelocityCmd({0.0}));

  // Initialize ROS node if it hasn't been initialized yet
  if (!rclcpp::ok())
  {
    rclcpp::init(0, nullptr);
  }

  // // Initialize ROS node
  auto node_name = _sdf->Get<std::string>("node_name", "conveyor_belt_simplified").first;
  this->ros_node_ = rclcpp::Node::make_shared(node_name);


  std::string stateTopic = "conveyor/state";
  std::string controlTopic = "conveyor/control";

  try
  {
  //  // Initialize publisher
  this->status_pub_ = this->ros_node_->create_publisher<robot_config_plugins::msg::ConveyorBeltState>(
    stateTopic, rclcpp::QoS(10));

  // // Create control service for conveyorbelt
  this->controlService_ = this->ros_node_->create_service<robot_config_plugins::srv::ConveyorBeltControl>(
    controlTopic,
    std::bind(
      &ConveyorBeltPlugin::OnControlCommand, this,
      std::placeholders::_1, std::placeholders::_2));

  gzwarn << "[ROS2ConveyorBeltSystem] Loaded: joint=" << this->joint_name_
          << " vmax=" << this->max_velocity_
          << " pub_rate=" << this->publish_rate_
          << " limits=[" << this->lower_limit_ << ", " << this->upper_limit_ << "]\n";

  }
  catch (const std::exception& e)
  {
    std::cerr << "Exception occurred :" <<  e.what() << std::endl;
    return;
  }

  // set init joint position to zero
  _ecm.SetComponentData<gazebo::components::JointPosition>(this->joint, {0, 0});
}

void ConveyorBeltPlugin::OnControlCommand(robot_config_plugins::srv::ConveyorBeltControl::Request::SharedPtr _req,
      robot_config_plugins::srv::ConveyorBeltControl::Response::SharedPtr _res)
{
  RCLCPP_INFO(this->ros_node_->get_logger(),
              "Received conveyor control command: power=%.3f",
              _req->power);
  std::scoped_lock lk(this->mtx_);
  _res->success = false;

  if (_req->power >= 0.0 && _req->power <= 100.0)
  {
    this->power_ = _req->power;
    this->belt_velocity_ = this->max_velocity_ * (this->power_ / 100.0);
    _res->success = true;
  }
  else
  {
    RCLCPP_WARN(this->ros_node_->get_logger(),
                "Conveyor power must be in [0,100], got %.3f", _req->power);
  }
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::PreUpdate(const gazebo::UpdateInfo &_info,
      gazebo::EntityComponentManager &_ecm)
{

  // Spin ROS callbacks
  if (this->ros_node_)
  rclcpp::spin_some(this->ros_node_);

  if (_info.paused || this->joint == gazebo::kNullEntity)
    return;

  // --- Sim time + dt ---
  const auto sim_ns =
      std::chrono::duration_cast<std::chrono::nanoseconds>(_info.simTime);
  double dt = 0.0;
  if (this->last_time_.count() > 0)
    dt = (sim_ns - this->last_time_).count() * 1e-9;
  this->last_time_ = sim_ns;

  // --- Read current joint position (if available) ---
  double q = std::numeric_limits<double>::quiet_NaN();
  if (auto pos = _ecm.Component<gazebo::components::JointPosition>(this->joint))
  {
    if (!pos->Data().empty())
      q = pos->Data()[0];
  }

  // --- Decide if we need to wrap (arm a one-tick reset) ---
  const double eps = 1e-3;  // ~1 mm safety margin

  bool arm_by_q = false;
  if (std::isfinite(q))
    arm_by_q = (q >= (this->upper_limit_ - eps));

  if (!this->pending_reset_)
  {
    // Integrate distance traveled by the belt since last frame (always available)
    this->travel_accum_ += std::abs(this->belt_velocity_) * dt;

    const bool arm_by_integrator = (this->travel_accum_ >= (this->upper_limit_ - eps));

    if (arm_by_q || arm_by_integrator)
    {
      this->pending_reset_ = true;
      this->travel_accum_  = 0.0;   // restart distance tally after each wrap
    }
  }

  // --- Command joint velocity; pause for one tick if we're resetting ---
  {
    std::scoped_lock lk(this->mtx_);
    auto *velCmd =
        _ecm.Component<gazebo::components::JointVelocityCmd>(this->joint);
    if (!velCmd)
      velCmd = _ecm.CreateComponent(
          this->joint, gazebo::components::JointVelocityCmd({0.0}));

    if (this->pending_reset_)
      velCmd->Data() = {0.0};                  // pause so reset can apply cleanly
    else
      velCmd->Data() = {this->belt_velocity_}; // normal conveyor motion
  }

  // --- If armed, perform the reset this tick and disarm ---
  if (this->pending_reset_)
  {
    auto *reset =
        _ecm.Component<gazebo::components::JointPositionReset>(this->joint);
    if (!reset)
      reset = _ecm.CreateComponent(
          this->joint, gazebo::components::JointPositionReset({0.0}));
    else
      reset->Data() = {0.0};

    this->pending_reset_ = false;
  }

  // --- Throttled publishes (by sim time) ---
  if (sim_ns - this->last_pub_sim_ >= this->publish_period_)
  {
    this->publishStatus();
    this->last_pub_sim_ = sim_ns;
  }

  // // Optional debug:
  static int k = 0;
  if ((k++ % 200) == 0)
    gzmsg << "[belt_joint] q=" << (std::isfinite(q) ? q : -1)
           << " s_accum=" << this->travel_accum_
           << " v_cmd=" << this->belt_velocity_
           << " upper=" << this->upper_limit_
           << " resetting=" << std::boolalpha << this->pending_reset_ << std::noboolalpha
           << "\n";
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::SetPower(const double _power)
{
  if (!this->joint || !this->linkEntity)
    return;

  if (_power < 0 || _power > 100)
  {
    std::cerr << printf("Incorrect power value [ %f ]. \tAccepted values are in the [0-100] range", _power) << std::endl;
    return;
  }

  this->beltPower = _power;

  std::string msg;
  msg = std::to_string(_power / 100.0);

  // Convert the power (percentage) to a velocity.
  this->beltVelocity = this->kMaxBeltLinVel * this->beltPower / 100.0;
  printf("Received power of: %f,  setting velocity to: %f\n", _power, this->beltVelocity);
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::publishStatus()
{
  robot_config_plugins::msg::ConveyorBeltState msg;
  {
    std::scoped_lock lk(this->mtx_);
    msg.power   = this->power_;
    msg.enabled = (this->power_ > 0.0);
  }
  this->status_pub_->publish(msg);
}

}
}
}
// Plugin registration - use the compatibility macro
GAZEBO_ADD_PLUGIN(
  gz::sim::systems::ConveyorBeltPlugin,
  gz::sim::System,
  gz::sim::systems::ConveyorBeltPlugin::ISystemConfigure,
  gz::sim::systems::ConveyorBeltPlugin::ISystemPreUpdate
)
