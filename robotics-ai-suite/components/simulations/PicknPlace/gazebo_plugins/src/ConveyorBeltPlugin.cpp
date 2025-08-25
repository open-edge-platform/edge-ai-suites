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
#include <gazebo/common/Events.hh>
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/PhysicsIface.hh>
#include <gazebo/physics/Joint.hh>
#include <gazebo/physics/Model.hh>
#include <gazebo/physics/World.hh>
#include "ConveyorBeltPlugin.hpp"


using namespace gazebo;

GZ_REGISTER_MODEL_PLUGIN(ConveyorBeltPlugin)

/////////////////////////////////////////////////
ConveyorBeltPlugin::~ConveyorBeltPlugin()
{
  this->updateConnection.reset();
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::Load(physics::ModelPtr _model, sdf::ElementPtr _sdf)
{
  
   // Initialize ROS node
  this->ros_node_ = gazebo_ros::Node::Get(_sdf);
 
  const gazebo_ros::QoS & qos = this->ros_node_->get_qos();
  
  std::string controlTopic = "conveyor/control";
  if (_sdf->HasElement("control_topic"))
    controlTopic = _sdf->Get<std::string>("control_topic");

  std::string stateTopic = "conveyor/state";
  if (_sdf->HasElement("state_topic"))
    stateTopic = _sdf->Get<std::string>("state_topic");

  try 
  {
   // Initialize publisher
  this->pub_ = this->ros_node_->create_publisher<robot_config_plugins::msg::ConveyorBeltState>(
    stateTopic, qos.get_publisher_qos(stateTopic, rclcpp::QoS(1)));

  // Create control service for conveyorbelt
  this->controlService_ = this->ros_node_->create_service<robot_config_plugins::srv::ConveyorBeltControl>(
    controlTopic,
    std::bind(
      &ConveyorBeltPlugin::OnControlCommand, this,
      std::placeholders::_1, std::placeholders::_2));
  
  }
  catch (const std::exception& e)
  {
    RCLCPP_ERROR(
        ros_node_->get_logger(), "Exception occured : %s", e.what());
    return;
  }
  
  // Read and set the joint that controls the belt.
  std::string jointName = "belt_joint";
  if (_sdf->HasElement("joint"))
    jointName = _sdf->Get<std::string>("joint");

  RCLCPP_INFO(this->ros_node_->get_logger(), "Using joint name of: [%s]" , jointName.c_str());
  this->joint = _model->GetJoint(jointName);
  if (!this->joint)
  {
    RCLCPP_ERROR(this->ros_node_->get_logger(), "Joint [%s] not found, belt disabled" , jointName.c_str());
    return;
  }

  // Read and set the belt's link.
  std::string linkName = "belt_link";
  if (_sdf->HasElement("link"))
    linkName = _sdf->Get<std::string>("link");
  
  RCLCPP_INFO(this->ros_node_->get_logger(),  "Using link name of: [%s]" , linkName.c_str());

  auto worldPtr = gazebo::physics::get_world();
  this->link = boost::static_pointer_cast<physics::Link>(
    worldPtr->EntityByName(linkName));
  if (!this->link)
  {
    RCLCPP_ERROR(this->ros_node_->get_logger(),  "Link not found");
    return;
  }

  // Set the point where the link will be moved to its starting pose.
  this->limit = this->joint->UpperLimit(0) - 0.4;

  
  // Initialize Gazebo transport
  this->gzNode = transport::NodePtr(new transport::Node());
  this->gzNode->Init();

  // Publisher for modifying the rate at which the belt is populated.
  // TODO(dhood): this should not be in this class.
  std::string populationRateModifierTopic = "population_rate_modifier";
  if (_sdf->HasElement("population_rate_modifier_topic"))
    populationRateModifierTopic = _sdf->Get<std::string>("population_rate_modifier_topic");
  this->populationRateModifierPub =
    this->gzNode->Advertise<msgs::GzString>(populationRateModifierTopic);

  // Read the power of the belt.
  if (_sdf->HasElement("power"))
    this->beltPower = _sdf->Get<double>("power");
  
  RCLCPP_INFO(this->ros_node_->get_logger(), "Power %f", this->beltPower );


  this->SetPower(this->beltPower);
  RCLCPP_INFO(this->ros_node_->get_logger(), "Using belt power of: %f", this->beltPower );

  // Subscriber for the belt's activation topic.
  if (_sdf->HasElement("enable_topic"))
  {
    std::string enableTopic = _sdf->Get<std::string>("enable_topic");
    this->enabledSub =
      this->gzNode->Subscribe(enableTopic, &ConveyorBeltPlugin::OnEnabled, this);
    this->enabled = false;
  }

  // Listen to the update event that is broadcasted every simulation iteration.
  this->updateConnection = event::Events::ConnectWorldUpdateBegin(
    std::bind(&ConveyorBeltPlugin::OnUpdate, this));

}

bool ConveyorBeltPlugin::OnControlCommand(
  robot_config_plugins::srv::ConveyorBeltControl::Request::SharedPtr _req,
  robot_config_plugins::srv::ConveyorBeltControl::Response::SharedPtr _res)
{
  

  RCLCPP_INFO(this->ros_node_->get_logger(),  "Conveyor control service called with: %f", _req->power );

  if (!this->IsEnabled())
  {
    RCLCPP_ERROR(this->ros_node_->get_logger(), "Belt is not currently enabled so power cannot be set. It may be congested.");
    _res->success = false;
    return true;
  }

  this->SetPower(_req->power);
  _res->success = true;
  
  return true;
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::OnUpdate()
{
  this->joint->SetVelocity(0, this->beltVelocity);
  

  // Reset the belt.
  if (ignition::math::Angle(this->joint->Position(0)) >= this->limit)
  {
    // Warning: Megahack!!
    // We should use "this->joint->SetPosition(0, 0)" here but I found that
    // this line occasionally freezes the joint. I tracked the problem and
    // found an incorrect value in childLinkPose within
    // Joint::SetPositionMaximal(). This workaround makes sure that the right
    // numbers are always used in our scenario.
    //const ignition::math::Pose3d childLinkPose(1.20997, 2.5998, 0.8126, 0, 0, -1.57);
    //const ignition::math::Pose3d newChildLinkPose(1.20997, 2.98, 0.8126, 0, 0, -1.57);
    //this->link->MoveFrame(childLinkPose, newChildLinkPose);
    this->joint->SetPosition(0,0);
     
  }

  this->Publish();
}

/////////////////////////////////////////////////
bool ConveyorBeltPlugin::IsEnabled() const
{
  return this->enabled;
}

/////////////////////////////////////////////////
double ConveyorBeltPlugin::Power() const
{
  if (!this->joint || !this->link)
    return 0.0;

  return this->beltPower;
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::SetPower(const double _power)
{
  if (!this->joint || !this->link)
    return;

  if (_power < 0 || _power > 100)
  {
    RCLCPP_ERROR(this->ros_node_->get_logger(), "Incorrect power value [ %f ]. \tAccepted values are in the [0-100] range", _power);
    return;
  }

  this->beltPower = _power;

  // Publish a message on the rate modifier topic of the PopulationPlugin.
  gazebo::msgs::GzString msg;
  msg.set_data(std::to_string(_power / 100.0));
  this->populationRateModifierPub->Publish(msg);

  // Convert the power (percentage) to a velocity.
  this->beltVelocity = this->kMaxBeltLinVel * this->beltPower / 100.0;
  RCLCPP_INFO(this->ros_node_->get_logger(), "Received power of: %f,  setting velocity to: %f", _power, this->beltVelocity);
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::OnEnabled(ConstGzStringPtr &_msg)
{
  gzdbg << "Received enable request: " << _msg->data() << std::endl;

  if (_msg->data() == "enabled")
  {
    this->enabled = true;
    this->SetPower(0);
  } else if (_msg->data() == "disabled")
  {
    this->enabled = false;
    this->SetPower(0);
  } else
  {
    gzerr << "Unknown activation command [" << _msg->data() << "]" << std::endl;
  }
}

/////////////////////////////////////////////////
void ConveyorBeltPlugin::Publish() const
{
}
