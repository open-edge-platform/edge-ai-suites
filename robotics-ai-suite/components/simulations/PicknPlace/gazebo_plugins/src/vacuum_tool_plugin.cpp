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

#include "vacuum_gripper/vacuum_tool_plugin.hpp"

namespace robot_config_plugins {

VacuumToolPlugin::~VacuumToolPlugin()
{
  if (executor) {
    executor->cancel();
  }
  if (thread_executor_spin.joinable()) {
    thread_executor_spin.join();
  }
}

void VacuumToolPlugin::Configure(
  const gazebo::Entity &_entity,
  const std::shared_ptr<const sdf::Element> &_sdf,
  gazebo::EntityComponentManager &_ecm,
  gazebo::EventManager &)
{ 
  // Read SDF tags
  std::string ros_namespace = "";
  if (_sdf->HasElement("ros")){
    if (_sdf->GetElementImpl("ros")->HasElement("namespace")){
      ros_namespace = _sdf->GetElementImpl("ros")->Get<std::string>("namespace");
    }
  }

  // Get tool type from SDF (default to VG_2 if not specified)
  int tool_type_int = 2;
  if (_sdf->HasElement("tool_type")) {
    tool_type_int = _sdf->Get<int>("tool_type");
  }
  tool_type = static_cast<VacuumTools>(tool_type_int);

  // Initialize malfunction system (simplified - no trial component)
  // You can add malfunctions manually if needed
  malfunctions.clear();
  malfunction_active = false;
  grasp_occurrence = 0;
  
  // GZ setup
  auto model = gazebo::Model(_entity);
  gripper_base_link = model.LinkByName(_ecm, "base_link");
  if (gripper_base_link == gazebo::kNullEntity) {
    gzerr << "Could not find base_link in model" << std::endl;
    return;
  }

  gz_node = std::make_shared<gz_transport::Node>();

  std::vector<std::string> topic_names; 
  std::string topic = "/world/default/model/" + model.Name(_ecm) + "/link/suction_{n}_link/sensor/contact_sensor/contact";

  int suction_cup_count = tool_type == VacuumTools::VG_2 ? 2 : 4;
  for(int i = 1; i <= suction_cup_count; i++){
    std::string name = topic;
    topic_names.push_back(name.replace(topic.find("{n}"), 3, std::to_string(i)));
  }
  
  if (tool_type == VacuumTools::VG_2) {
    gz_node->Subscribe(topic_names[0], &VacuumToolPlugin::contact_sensor_1_cb, this);
    gz_node->Subscribe(topic_names[1], &VacuumToolPlugin::contact_sensor_2_cb, this);
  } else if(tool_type == VacuumTools::VG_4) {
    gz_node->Subscribe(topic_names[0], &VacuumToolPlugin::contact_sensor_1_cb, this);
    gz_node->Subscribe(topic_names[1], &VacuumToolPlugin::contact_sensor_2_cb, this);
    gz_node->Subscribe(topic_names[2], &VacuumToolPlugin::contact_sensor_3_cb, this);
    gz_node->Subscribe(topic_names[3], &VacuumToolPlugin::contact_sensor_4_cb, this);
  }

  // ROS setup
  if (!rclcpp::ok()){
    rclcpp::init(0, nullptr);
  }

  ros_node = rclcpp::Node::make_shared(model.Name(_ecm) + "_plugin_node", ros_namespace);

  rclcpp::Parameter sim_time("use_sim_time", true);
  ros_node->set_parameter(sim_time);

  executor = std::make_shared<rclcpp::executors::MultiThreadedExecutor>();
  executor->add_node(ros_node);

  auto spin = [this](){
    while(rclcpp::ok()){
      executor->spin_once();
    }
  };

  thread_executor_spin = std::thread(spin);

  if (tool_type == VacuumTools::VG_2) {
    attach_srv = ros_node->create_service<Trigger>(
      "grasp",
      std::bind(&VacuumToolPlugin::vg_2_attach_cb, this, std::placeholders::_1, std::placeholders::_2)
    );
  } else if(tool_type == VacuumTools::VG_4) {
    attach_srv = ros_node->create_service<Trigger>(
      "grasp",
      std::bind(&VacuumToolPlugin::vg_4_attach_cb, this, std::placeholders::_1, std::placeholders::_2)
    );
  }

  detach_srv = ros_node->create_service<Trigger>(
    "release",
    std::bind(&VacuumToolPlugin::detach_object_cb, this, std::placeholders::_1, std::placeholders::_2)
  );

  // Initialize lock state
  lock_state = VacuumToolLockState::UNLOCKED;
  lock_joint = gazebo::kNullEntity;

  RCLCPP_INFO(ros_node->get_logger(), "Vacuum tool plugin configured for tool type: %d", static_cast<int>(tool_type));
}

void VacuumToolPlugin::PreUpdate(const gazebo::UpdateInfo &,
    gazebo::EntityComponentManager &_ecm)
{
  switch (lock_state)
  {
  case VacuumToolLockState::LOCK_REQUESTED: {
    // Get link entity for shell
    auto model = _ecm.EntityByName(attach_object_name);
    
    if (!model.has_value()) {
      gzerr << "Unable to locate model: " << attach_object_name << std::endl;
      lock_state = VacuumToolLockState::UNLOCKED;
      break;
    }
    
    auto shell_link = gazebo::Model(model.value()).LinkByName(_ecm, "base_link");
    if (shell_link == gazebo::kNullEntity) {
      gzerr << "Unable to locate base_link in model: " << attach_object_name << std::endl;
      lock_state = VacuumToolLockState::UNLOCKED;
      break;
    }

    // Create lock joint using DetachableJoint
    lock_joint = _ecm.CreateEntity();
    
    // Create a fixed joint between gripper and object
    _ecm.CreateComponent(lock_joint, 
      gazebo::components::DetachableJoint({gripper_base_link, shell_link, "fixed"}));

    lock_state = VacuumToolLockState::LOCKED;
    
    grasp_occurrence++;
    
    RCLCPP_INFO(ros_node->get_logger(), "Object attached: %s", attach_object_name.c_str());
    break;
  }
  case VacuumToolLockState::UNLOCK_REQUESTED:
    // Unlock joint
    if (lock_joint != gazebo::kNullEntity) {
      _ecm.RequestRemoveEntity(lock_joint);
      lock_joint = gazebo::kNullEntity;
    }

    lock_state = VacuumToolLockState::UNLOCKED;
    RCLCPP_INFO(ros_node->get_logger(), "Object detached: %s", attach_object_name.c_str());
    attach_object_name = "";
    break;
  case VacuumToolLockState::LOCKED:
    // Already locked, nothing to do
    break;
  case VacuumToolLockState::UNLOCKED:
    // Already unlocked, nothing to do
    break;
  }

  // If malfunction is active check if should be cleared
  if (malfunction_active && std::all_of(pad_contacts.begin(), pad_contacts.end(),
      [](const auto& entry) { return !entry.second.in_contact; })) {
    clear_malfunction();
  }
}

void VacuumToolPlugin::vg_2_attach_cb(const TriggerReqPtr request, TriggerResPtr response)
{
  (void)request; // Suppress unused parameter warning
  
  if(lock_state == VacuumToolLockState::LOCKED){
    response->success = false;
    response->message = "Already holding object";
    return;
  }
  
  if (!pad_contacts[1].in_contact || !pad_contacts[2].in_contact) {
    response->success = false;
    response->message = "Both suction cups must be in contact with the shell";
    return;
  }
  
  if (pad_contacts[1].model_name != pad_contacts[2].model_name){
    response->success = false;
    response->message = "Suction cups are in contact with different shells";
    return;
  }
  
  if (should_malfunction()) {
    response->success = false;
    response->message = "Vacuum gripper is malfunctioning";
    return;
  }

  attach_object_name = pad_contacts[1].model_name;
  
  lock_state = VacuumToolLockState::LOCK_REQUESTED;

  response->success = wait_for_state(VacuumToolLockState::LOCKED);
  response->message = response->success ? "Top shell attached" : "Unable to grasp object";
}

void VacuumToolPlugin::vg_4_attach_cb(const TriggerReqPtr request, TriggerResPtr response)
{
  (void)request; // Suppress unused parameter warning
  
  if(lock_state == VacuumToolLockState::LOCKED){
    response->success = false;
    response->message = "Already holding object";
    return;
  }
  
  if (!pad_contacts[1].in_contact || !pad_contacts[2].in_contact || !pad_contacts[3].in_contact || !pad_contacts[4].in_contact) {
    response->success = false;
    response->message = "All suction cups must be in contact with the shell";
    return;
  }
  
  if (pad_contacts[1].model_name != pad_contacts[2].model_name || pad_contacts[3].model_name != pad_contacts[4].model_name){
    response->success = false;
    response->message = "Suction cups are in contact with different shells";
    return;
  }  
  
  if (should_malfunction()) {
    response->success = false;
    response->message = "Vacuum gripper is malfunctioning";
    return;
  }

  if(pad_contacts[1].model_name.find("bottom") != std::string::npos){
    attach_object_name = pad_contacts[1].model_name;
  } else {
    attach_object_name = pad_contacts[3].model_name;
  }

  lock_state = VacuumToolLockState::LOCK_REQUESTED;

  response->success = wait_for_state(VacuumToolLockState::LOCKED);
  response->message = response->success ? "Module attached" : "Unable to grasp object";
}

void VacuumToolPlugin::detach_object_cb(const TriggerReqPtr request, TriggerResPtr response)
{
  (void)request; // Suppress unused parameter warning
  
  if(lock_state != VacuumToolLockState::LOCKED){
    response->success = false;
    response->message = "Tool not holding object";
    return;
  }
  
  lock_state = VacuumToolLockState::UNLOCK_REQUESTED;

  response->success = wait_for_state(VacuumToolLockState::UNLOCKED);
  response->message = response->success ? "Object detached" : "Unable to release object";
}

void VacuumToolPlugin::contact_sensor_1_cb(const gz_msgs::Contacts &_gz_contacts_msg)
{
  auto shell = shell_in_contact(_gz_contacts_msg);
  pad_contacts[1] = PadContact{shell.has_value(), shell.has_value() ? shell.value() : ""};
}

void VacuumToolPlugin::contact_sensor_2_cb(const gz_msgs::Contacts &_gz_contacts_msg)
{
  auto shell = shell_in_contact(_gz_contacts_msg);
  pad_contacts[2] = PadContact{shell.has_value(), shell.has_value() ? shell.value() : ""};
}

void VacuumToolPlugin::contact_sensor_3_cb(const gz_msgs::Contacts &_gz_contacts_msg)
{
  auto shell = shell_in_contact(_gz_contacts_msg);
  pad_contacts[3] = PadContact{shell.has_value(), shell.has_value() ? shell.value() : ""};
}

void VacuumToolPlugin::contact_sensor_4_cb(const gz_msgs::Contacts &_gz_contacts_msg)
{
  auto shell = shell_in_contact(_gz_contacts_msg);
  pad_contacts[4] = PadContact{shell.has_value(), shell.has_value() ? shell.value() : ""};
}

std::optional<std::string> VacuumToolPlugin::shell_in_contact(const gz_msgs::Contacts &_gz_contacts_msg)
{
  std::string collision;
  for (int i = 0; i < _gz_contacts_msg.contact_size(); ++i){
    collision = _gz_contacts_msg.contact(i).collision2().name();

    std::string collision_name = "";
  
    switch (tool_type)
    {
    case VacuumTools::VG_2:
      collision_name = "vg_2";
      break;

    case VacuumTools::VG_4:
      collision_name = "vg_4";
      break;
    }

    if (collision.find(collision_name) != std::string::npos){
      return collision.substr(0, collision.find("::")); // model name
    }
  }

  return std::nullopt;
}

bool VacuumToolPlugin::wait_for_state(VacuumToolLockState state)
{
  rclcpp::Time start_time = ros_node->now();
  rclcpp::Rate rate(100);
  while(rclcpp::ok()){
    if (lock_state == state) {
      break;
    } else if (ros_node->now() - start_time > rclcpp::Duration::from_seconds(3.0)) {
      gzerr << "Timed out during request\n";
      return false;
    }
    rate.sleep();
  };

  return lock_state == state;
}

bool VacuumToolPlugin::should_malfunction()
{
  // Check if malfunction challenge should activate based on current grasp occurrence
  if (malfunctions.empty()) {
    return false;
  }

  malfunction_active = std::find_if(malfunctions.begin(), malfunctions.end(), 
    [this](const auto& p) { return !p.second && p.first == grasp_occurrence; }
  ) != malfunctions.end();
  
  return malfunction_active;
}

void VacuumToolPlugin::clear_malfunction()
{
  // Clear malfunction challenge based on current grasp occurrence
  auto it = std::find_if(malfunctions.begin(), malfunctions.end(),
    [this](const auto& p) { return p.first == grasp_occurrence; });

  if (it != malfunctions.end()) {
    it->second = true;
    malfunction_active = false;
    RCLCPP_INFO(ros_node->get_logger(), "Malfunction cleared for grasp occurrence: %d", grasp_occurrence);
  }
}

// Implementacja funkcji z header'a (jeśli potrzebne)
void VacuumToolPlugin::attach_cb(const TriggerReqPtr request, TriggerResPtr response)
{
  // Przekieruj do odpowiedniej funkcji w zależności od typu narzędzia
  if (tool_type == VacuumTools::VG_2) {
    vg_2_attach_cb(request, response);
  } else {
    vg_4_attach_cb(request, response);
  }
}

void VacuumToolPlugin::detach_cb(const TriggerReqPtr request, TriggerResPtr response)
{
  detach_object_cb(request, response);
}

void VacuumToolPlugin::contact_sensor_cb(const gz_msgs::Contacts &_msg)
{
  // Ogólna funkcja callback - można przekierować do contact_sensor_1_cb
  contact_sensor_1_cb(_msg);
}

bool VacuumToolPlugin::lock_tool_to_object()
{
  // Simplified implementation - już zaimplementowane w PreUpdate
  return lock_state == VacuumToolLockState::LOCKED;
}

} // namespace robot_config_plugins

// Register the plugin using compatibility macro
GAZEBO_ADD_PLUGIN(
  robot_config_plugins::VacuumToolPlugin,
  gazebo::System,
  robot_config_plugins::VacuumToolPlugin::ISystemConfigure,
  robot_config_plugins::VacuumToolPlugin::ISystemPreUpdate
)
