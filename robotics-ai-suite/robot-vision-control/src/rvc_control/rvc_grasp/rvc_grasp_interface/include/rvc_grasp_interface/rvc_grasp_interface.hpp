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

#pragma once

#ifndef __RVC_GRASP_INTERFACE_HPP__
#define __RVC_GRASP_INTERFACE_HPP__

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/macros.hpp"
#include "rvc_messages/msg/pose_stamped_list.hpp"
#include "rvc_messages/msg/pose_stamped.hpp"

using vector6d_t = std::array<double, 6>;

/// @brief Any defined controllers have to inerit from this to be used in the StateMachine node
namespace RVCControl {
class RVCGraspInterface
{
protected:
    rclcpp::Node::SharedPtr node_;
private:    
    rclcpp::Subscription<rvc_messages::msg::PoseStampedList>::SharedPtr RvcMessagesSubscriber;
    /// @brief Callback upon receiving a new message from the AI node
    /// @param Message received, it brings object type and the pose (if not of type none)
    void RvcMessagesCallback(rvc_messages::msg::PoseStampedList::SharedPtr);
    /// @brief  Private copy constructor
    RVCGraspInterface(const RVCGraspInterface&);

    /// @brief Private copy assignment operator
    RVCGraspInterface& operator=(const RVCGraspInterface&);
public:
    RCLCPP_SMART_PTR_ALIASES_ONLY(RVCGraspInterface)

    /**
     * @brief This function will be called upon receiving a new pose
     * 
     * @param msg the received message list
     */
    virtual void OnMessageReceive(rvc_messages::msg::PoseStampedList::SharedPtr msg) = 0;
    /**
     * @brief Get the Pre Grasp object pose
     * 
     * @param pose pregrasp pose
     * @return true on success
     * @return false on failure
     */
    virtual bool getPreGrasp(geometry_msgs::msg::Pose & pose) = 0;
    /**
     * @brief Get the Grasp object Pose
     * 
     * @param pose Grasp Pose
     * @return true on success
     * @return false on failure
     */
    virtual bool getGrasp(geometry_msgs::msg::Pose & pose) = 0;
    /**
     * @brief function to verify that the object is currently still valid and detected by the framework
     * 
     * @return true 
     * @return false 
     */
    virtual bool isTargetAcquired() = 0;
    /**
     * @brief Get the Current detected Object string identifier
     * 
     * @return std::string object name identifier
     */
    virtual std::string getCurrentObject() = 0;
    /**
     * @brief API entry: plugin initialization
     *
     * @param node Ros node
     * @param modelName input file name
     * @return true on success
     * @return false otherwise
     */

    virtual bool init(rclcpp::Node::SharedPtr node);
    /**
     * @brief API entry: operation to clean up upon node shutdown
     *
     * @return true
     * @return false
     */
    virtual bool on_shutdown()
    {
        RCLCPP_INFO(rclcpp::get_logger("OD"), "ai_interface: on_shutdown...");
        return false;
    }

    /**
     * @brief Destroy the RVCGraspInterface object
     * 
     */
    virtual ~RVCGraspInterface() {};

protected:
    /// @brief  Empty Constructor for pluginlib
    /// @param node a rclcpp node shared pointer
    RVCGraspInterface() {}
    std::string base_link, ee_link;
};
} //namespace RVCControl

#endif //__RVC_GRASP_INTERFACE_HPP__
