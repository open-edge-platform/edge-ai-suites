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

#ifndef VACUUM_GRIPPER__VACUUM_TOOL_PLUGIN_HPP_
#define VACUUM_GRIPPER__VACUUM_TOOL_PLUGIN_HPP_

// Compatibility layer for different Gazebo versions
#include "gazebo_compat.hpp"


#include <ament_index_cpp/get_package_share_directory.hpp>
#include <rclcpp/rclcpp.hpp>

// Use standard ROS interfaces
#include <std_srvs/srv/trigger.hpp>
#include <std_msgs/msg/string.hpp>

// Standard library includes
#include <thread>
#include <chrono>
#include <optional>
#include <map>
#include <vector>
#include <algorithm>
#include <string>

using Trigger = std_srvs::srv::Trigger;
using TriggerReqPtr = Trigger::Request::SharedPtr;
using TriggerResPtr = Trigger::Response::SharedPtr;

namespace robot_config_plugins {

  // Define VacuumTools enum
  enum class VacuumTools {
    VG_2 = 2,
    VG_4 = 4
  };

  struct PadContact {
    bool in_contact;
    std::string model_name;
  };

  enum class VacuumToolLockState {
    LOCKED,
    UNLOCKED,
    LOCK_REQUESTED,
    UNLOCK_REQUESTED
  };

  class VacuumToolPlugin
      : public gazebo::System,
        public gazebo::ISystemConfigure,
        public gazebo::ISystemPreUpdate
  {
    public:

    ~VacuumToolPlugin();

    void Configure (
      const gazebo::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gazebo::EntityComponentManager &_ecm,
      gazebo::EventManager &_event_mgr) override;
    
    void PreUpdate(
      const gazebo::UpdateInfo &_info,
      gazebo::EntityComponentManager &_ecm) final;
    
    private:
    // ROS callbacks
    void attach_cb(const TriggerReqPtr request, TriggerResPtr response);
    void detach_cb(const TriggerReqPtr request, TriggerResPtr response);
    
    // VG-specific callbacks (needed by implementation)
    void vg_2_attach_cb(const TriggerReqPtr request, TriggerResPtr response);
    void vg_4_attach_cb(const TriggerReqPtr request, TriggerResPtr response);
    void detach_object_cb(const TriggerReqPtr request, TriggerResPtr response);

    // GZ callbacks
    void contact_sensor_cb(const gz_msgs::Contacts &);
    void contact_sensor_1_cb(const gz_msgs::Contacts &_gz_contacts_msg);
    void contact_sensor_2_cb(const gz_msgs::Contacts &_gz_contacts_msg);
    void contact_sensor_3_cb(const gz_msgs::Contacts &_gz_contacts_msg);
    void contact_sensor_4_cb(const gz_msgs::Contacts &_gz_contacts_msg);

    bool wait_for_state(VacuumToolLockState);

    // Functions
    std::optional<std::string> shell_in_contact(const gz_msgs::Contacts &);
    bool lock_tool_to_object();
    bool should_malfunction();
    void clear_malfunction();
      
    // GZ
    std::shared_ptr<gz_transport::Node> gz_node;
    gazebo::Entity lock_joint;
    gazebo::Entity gripper_base_link;
    gazebo::Entity world_entity = 1;
    
    // ROS
    rclcpp::Node::SharedPtr ros_node;
    rclcpp::executors::MultiThreadedExecutor::SharedPtr executor;
    std::thread thread_executor_spin;
    rclcpp::Service<Trigger>::SharedPtr attach_srv;
    rclcpp::Service<Trigger>::SharedPtr detach_srv;

    // Variables
    std::string attach_object_name = "";
    std::map<int, PadContact> pad_contacts;
    VacuumToolLockState lock_state = VacuumToolLockState::UNLOCKED;
    
    // Tool-specific variables (needed by implementation)
    VacuumTools tool_type = VacuumTools::VG_2;
    std::vector<std::pair<int, bool>> malfunctions;
    bool malfunction_active = false;
    int grasp_occurrence = 0;
  };
} // namespace robot_config_plugins

#endif // VACUUM_GRIPPER__VACUUM_TOOL_PLUGIN_HPP_
