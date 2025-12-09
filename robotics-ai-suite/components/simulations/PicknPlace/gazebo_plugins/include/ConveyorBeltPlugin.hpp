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

#ifndef _GAZEBO_CONVEYOR_BELT_PLUGIN_HH_
#define _GAZEBO_CONVEYOR_BELT_PLUGIN_HH_

#include "gazebo_compat.hpp"
#include <rclcpp/rclcpp.hpp>
#include <sdf/sdf.hh>
#include <mutex>
#include <chrono>
#include <limits>

#include "robot_config_plugins/msg/conveyor_belt_state.hpp"
#include "robot_config_plugins/srv/conveyor_belt_control.hpp"

namespace gz
{
namespace sim
{
namespace systems
{
  /// \brief A plugin for simulating a conveyor belt.
  /// The plugin accepts the following SDF parameters:
  ///
  /// <max_velocity>: Maximum linear velocity of the belt (m/s).
  /// <publish_rate>: Rate at which the conveyor belt state is published (Hz).
  /// <joint_name>: Joint name used to control the belt.
  /// <lower_limit>: Lower limit of the joint (meters).
  /// <upper_limit>: Upper limit of the joint (meters).
  class ConveyorBeltPlugin
    : public gazebo::System,
      public gazebo::ISystemConfigure,
      public gazebo::ISystemPreUpdate
  {
    /// \brief Constructor.
    public: ConveyorBeltPlugin() = default;

    /// \brief Destructor.
    public: virtual ~ConveyorBeltPlugin();

    /// \brief Load the conveyor belt plugin.
    public: void Configure(const gazebo::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gazebo::EntityComponentManager &_ecm,
      gazebo::EventManager &_eventMgr) override;

    /// \brief Pre-update method invoked before every simulation update.
    public: void PreUpdate(const gazebo::UpdateInfo &_info,
      gazebo::EntityComponentManager &_ecm) override;

    ///  \brief Receives requests on the conveyor belt's topic.
    /// \param[in] _req The desired state of the conveyor belt.
    /// \param[in] _res If the service succeeded or not.
    public: void OnControlCommand(
      robot_config_plugins::srv::ConveyorBeltControl::Request::SharedPtr _req,
      robot_config_plugins::srv::ConveyorBeltControl::Response::SharedPtr _res);

    /// \brief Set the power of the conveyor belt.
    /// \param[in] _power Power of the belt as a percentage (0-100).
    protected: void SetPower(const double _power);

    /// \brief Overwrite this method for sending periodic updates with the
    /// conveyor state.
    private: virtual void publishStatus();

    // ROS2 Components
    private: rclcpp::Node::SharedPtr ros_node_;
    private: rclcpp::Service<robot_config_plugins::srv::ConveyorBeltControl>::SharedPtr controlService_;
    private: rclcpp::Publisher<robot_config_plugins::msg::ConveyorBeltState>::SharedPtr status_pub_;

    // gz-transport node for subscriber and service
    public: gz_transport::Node node;

    // Gazebo entities
    private: gazebo::Entity entity{gazebo::kNullEntity};
    private: gazebo::Model model{gazebo::kNullEntity};
    private: gazebo::Entity joint{gazebo::kNullEntity};
    private: gazebo::Entity linkEntity{gazebo::kNullEntity};

    // Configuration parameters
    private: std::string joint_name_{"belt_joint"};
    private: double max_velocity_{1.0};     // m/s
    private: double publish_rate_{1000.0};  // Hz
    private: double lower_limit_{0.0};      // meters
    private: double upper_limit_{0.01};     // meters (wrap distance target)

    // State variables (protected by mutex)
    private: std::mutex mtx_;
    private: double power_{10.0};           // [0..100]
    private: double belt_velocity_{1.0};    // m/s (derived)

    // Legacy variables (for compatibility with SetPower method)
    protected: double beltVelocity{0.0};    // Belt velocity (m/s)
    protected: double beltPower{0.0};       // Belt power as percentage
    protected: bool enabled{true};          // If true, power commands are processed

    // Wrap control
    private: bool pending_reset_{false};
    private: double travel_accum_{0.0};     // Distance integrator (meters since last wrap)

    // Timing
    private: std::chrono::nanoseconds last_time_{std::chrono::nanoseconds(0)};
    private: std::chrono::nanoseconds publish_period_{std::chrono::nanoseconds(1'000'000)};
    private: std::chrono::nanoseconds last_pub_sim_{std::chrono::nanoseconds(0)};

    // Constants
    private: const double kMaxBeltLinVel{0.2};  // Maximum linear velocity of the belt

    // Unused legacy variables (kept for compatibility)
    private: gz_math::Angle limit;
  };

}
}
}
#endif
