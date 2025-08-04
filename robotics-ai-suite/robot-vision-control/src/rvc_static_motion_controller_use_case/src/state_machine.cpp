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

#include "rvc_static_motion_controller_use_case/state_machine.hpp"

using namespace std::chrono_literals;

StateMachine::StateMachine()
  : rclcpp::Node("StateMachineNode")
    , gripperCloseCommandWasSent(false)
    , enableController(false)
    , controllerSpeed(20)
    , controllerSpeedGUI(20)
    , sendToSafePos(1)
    , state(start_state)
    , enableFullCycle(true)
    , enableTrackingOnCloseGripper(false)
    , globalObjectClassId("none")
    , receivedSettings(false)
    , firstGraspReceived(false)
{
    objectDetected = 0;
    lastPublishedState = 0;
    try
    {
        this->declare_parameter<std::vector<double>>("safe_point_joints", std::vector<double>() );
        this->declare_parameter<std::vector<double>>("safe_point_pose", std::vector<double>() );
        this->declare_parameter<std::vector<double>>("drop_point_pose", std::vector<double>() );
    } catch (const std::exception & e)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Exception thrown during init stage with message: %s \n",
            e.what() );
    }
}

StateMachine::~StateMachine()
{
}

bool StateMachine::init(RVCMotionControllerInterface * motionController, RVCControl::RVCGraspInterface * graspPlugin)
{

    this->motionController = motionController;
    this->graspPlugin = graspPlugin;

    auto qostransientlocal = rclcpp::QoS(
        rclcpp::QoSInitialization::from_rmw(
            rmw_qos_profile_default), rmw_qos_profile_default);
    qostransientlocal.transient_local();
#ifndef BUILD_SENSOR_DATA
    auto qos = rclcpp::QoS(
        rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_default),
        rmw_qos_profile_default);
#else
    auto qos = rclcpp::QoS(
        rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_sensor_data),
        rmw_qos_profile_sensor_data);
#endif


    target_picked_pub = this->create_publisher<std_msgs::msg::Bool>("target_picked", qos);

    gripperDetectionSubscriber =
        this->create_subscription<std_msgs::msg::UInt16>(
        "gripper_sensor_broadcaster/object_grasped",
        qos, [this](const std_msgs::msg::UInt16::SharedPtr msg)
        {
            firstGraspReceived = true;
            this->objectDetected = ( msg->data == 1 || msg->data == 2 ) ? 1 : 0;
            static int prev = this->objectDetected;

            if (this->objectDetected != prev)
            {
                prev = this->objectDetected;
            }
        });
    settingsSubscriber =
        this->create_subscription<gui_settings::msg::GuiSettingsMsg>(
        "/computer_vision_robot_demo/settings",
        qostransientlocal, std::bind(
            &StateMachine::settingsCallback, this,
            std::placeholders::_1) );


    auto getPoseFromParam = [](std::vector<double> param)
        {
            geometry_msgs::msg::Pose item;
            item.position.x = param[0];
            item.position.y = param[1];
            item.position.z = param[2];
            item.orientation.x = param[3];
            item.orientation.y = param[4];
            item.orientation.z = param[5];
            item.orientation.w = param[6];
            return item;
        };

    safe_point_pose = getPoseFromParam(get_parameter("safe_point_pose").as_double_array());
    drop_pose = getPoseFromParam(get_parameter("drop_point_pose").as_double_array());

    state_machine_timer_ = create_wall_timer(
        std::chrono::milliseconds(2),
        std::bind(&StateMachine::run, this) );


    return true;
}

void StateMachine::settingsCallback(gui_settings::msg::GuiSettingsMsg::SharedPtr msg)
{
    enableController = msg->enable_controller;
    controllerSpeedGUI = msg->robot_speed;

    if (controllerSpeed != controllerSpeedGUI)
    {
        controllerSpeed = controllerSpeedGUI;
        motionController->setControllerSpeed(controllerSpeed);
    }

    sendToSafePos = msg->enable_safe_position;
    enableFullCycle = msg->enable_fullcycle;
    enableTrackingOnCloseGripper = msg->enable_tracking_on_close_gripper;
    receivedSettings = true;
}

void StateMachine::switchState(int newState)
{
    if (newState != this->state)
    {
        RCLCPP_INFO(
            this->get_logger(), "DIFFERENT: switchState: from %s to"
            " %s targetAcquired %d globalObjectClassId %s objectDetectedInGripper %d )",
            stateName[this->state].c_str(), stateName[newState].c_str(), graspPlugin->isTargetAcquired(),
            globalObjectClassId.c_str(), objectDetected);
    }

    this->state = newState;
}

void StateMachine::openGripper()
{
    motionController->sendGripperPosition(0.0);
}

void StateMachine::closeGripper()
{
    motionController->sendGripperPosition(0.9);
}

void StateMachine::run(void)
{
    const auto timer_expiration_time = 1500ms;

    controllerSpeed = controllerSpeedGUI;

    switch (state) {
      case start_state:
          {
              switchState(init_state);
              break;
          }
      case init_state:
          {
              if (receivedSettings == false)
              {
                  RCLCPP_INFO_THROTTLE(
                      get_logger(), *this->get_clock(), 3000,
                      "Didnt received GuiSettings yet..");
                  break;
              }


              int graspPublisher =
                  this->count_publishers("gripper_sensor_broadcaster/object_grasped");

              if (graspPublisher < 1)
              {
                  //RCLCPP_INFO_THROTTLE(get_logger(), *this->get_clock(), 100, "graspPublisher not up yet ");
                  //break;
              }

              if (firstGraspReceived == false)
              {
                  RCLCPP_INFO_THROTTLE(get_logger(), *this->get_clock(), 1000, "didnt receive first grasp ");
                  //break;
              }

              switchState(sync_state);
              break;
          }
      case sync_state:
          {

              if (lastPublishedState > sync_state)
              {

                  RCLCPP_INFO(
                      get_logger(), "DARIO: OVERRIDE STARTSTATE with last published state %d %s",
                      lastPublishedState, stateName[lastPublishedState].c_str());

                  if ((lastPublishedState == tracking_outer_point_state ||
                      lastPublishedState == closing_gripper_state ||
                      lastPublishedState == opening_gripper_state ||
                      lastPublishedState == tracking_inner_point_state ) &&
                      graspPlugin->isTargetAcquired() == false)
                  {
                      static uint32_t cc = 0;
                      cc++;

                      if (cc > 500)
                      {
                          cc = 0;
                          RCLCPP_FATAL(
                              get_logger(),
                              "DARIO: OVERRIDE STARTSTATE FAILED!!, targetAcquired didnt became"
                              " true for 500 cycles after publisher was online... going_to_safe_position_state");

                          motionController->sendGoal(safe_point_pose);
                          switchState(going_to_safe_position_state);
                      }

                      break;
                  }

                  globalObjectClassId = lastDropObject;
                  switchState(lastPublishedState);
                  break;
              }
              else
              {
                  RCLCPP_INFO(
                      get_logger(), "-----------------> lastPublishedState is %d %s, NO override",
                      lastPublishedState, stateName[lastPublishedState].c_str());

                  motionController->setControllerSpeed(controllerSpeed);
                  motionController->sendGoal(safe_point_pose);
                  switchState(going_to_safe_position_state);
                  break;
              }

              break;
          }

      case going_to_safe_position_state:
          {
              if (enableController == false)
              {
                  break;
              }

              if (motionController->isGoalNear() )
              {
                  RCLCPP_INFO_THROTTLE(
                      get_logger(),
                      *this->get_clock(), 1000,
                      "going_to_safe_position_state, GOAL REACHED!! targetAcquired %d objectDetected %d",
                      graspPlugin->isTargetAcquired(),
                      objectDetected);

                  // Destination reached: we have an object grabbed, send to drop point..
                  if (objectDetected != 0)
                  {
                      motionController->sendGoal(drop_pose);

                      switchState(going_to_drop_object_state);
                      break;
                  }
                  else
                  {
                      if (graspPlugin->isTargetAcquired() == true)
                      {
                          RCLCPP_INFO(
                              get_logger(),
                              "going_to_safe_position_state: target is acquired!!! forced to open gripper and going to tracking_outer_point_state");
                          openGripper();

                          //Take a snapshot and fully commit a cycle (or go to safe pos if failed to grab)
                          graspPlugin->getPreGrasp(outerDestinationTCPPose);
                          graspPlugin->getGrasp(innerDestinationTCPPose);

                          motionController->sendGoal(outerDestinationTCPPose);
                          switchState(tracking_outer_point_state);
                          break;
                      }
                  }
              }

              break;
          }
      case going_to_drop_object_state:
          {
              std::string objectIndex = globalObjectClassId;

              if (objectIndex == "none")
              {
                  RCLCPP_INFO(
                      get_logger(),
                      "FATAL: sanity check failed!! objectIndex is %s globalObjectClassId %s. going_to_safe_position_state",
                      objectIndex.c_str(), globalObjectClassId.c_str() );
                  openGripper();
                  motionController->sendGoal(safe_point_pose);
                  switchState(going_to_safe_position_state);
                  break;
              }



              if (motionController->isGoalNear() )
              {
                  {
                      static bool start_timer = true;
                      // Waiting a bit standing still while opening the gripper...
                      static auto start_time = std::chrono::steady_clock::now();

                      if (start_timer)
                      {
                          start_time = std::chrono::steady_clock::now();
                      }

                      RCLCPP_INFO_THROTTLE(
                          get_logger(), *this->get_clock(), 1000,
                          "Drop point at objectIndex %s reached ,opening gripper ...", objectIndex.c_str());

                      openGripper();
                      std_msgs::msg::Bool msg;
                      msg.data = false;
                      target_picked_pub->publish(msg);


                      motionController->sendGoal(safe_point_pose);
                      switchState(going_to_safe_position_state);
                      break;
                  }
              }

              break;
          }
      case tracking_outer_point_state:
          {
                  if (motionController->isGoalNear() && ( motionController->getGripperPositionFeedback() < 0.02 ) )
                  {
                    motionController->sendGoal(innerDestinationTCPPose);
                    switchState(tracking_inner_point_state);
                    break;
                  }

              break;
          }
      case tracking_inner_point_state:
          {

                  if (motionController->isGoalNear() )
                  {
                      globalObjectClassId = graspPlugin->getCurrentObject();
                      RCLCPP_DEBUG(
                          get_logger(), "====> going to drop %s",
                          globalObjectClassId.c_str() );

                      gripperCloseCommandWasSentAt = std::chrono::steady_clock::now();
                      closeGripper();
                      switchState(closing_gripper_state);
                      break;
                  }

              break;
          }
      case closing_gripper_state:
          {
              if (objectDetected != 0)
              {
                  std_msgs::msg::Bool msg;
                  msg.data = true;
                  target_picked_pub->publish(msg);
                  motionController->sendGoal(safe_point_pose);
                  switchState(going_to_safe_position_state);
              }
              else
              {            
                auto myNow = std::chrono::steady_clock::now();
                auto diff = myNow - gripperCloseCommandWasSentAt;
                auto elapsedMillis = std::chrono::duration_cast<std::chrono::milliseconds>(diff);

                if ( ( elapsedMillis > timer_expiration_time ) ||
                    ( motionController->getGripperPositionFeedback() > 0.7 ) )
                {
                    RCLCPP_INFO(
                        this->get_logger(),
                        "closing_gripper_state TIMEOUT or failed to pick up the object: "
                        "opening gripper millis %ld gripperPositionFeedback %f", elapsedMillis.count(),
                        motionController->getGripperPositionFeedback() );
                    openGripper();
                    motionController->sendGoal(safe_point_pose);
                    switchState(going_to_safe_position_state);
                    break;
                }
              }
              break;
          }
      default:
          {
              RCLCPP_INFO(this->get_logger(), "StateMachine: FATAL: IMPOSSIBLE STATE! ");
              exit(0);
          }

    }

}
