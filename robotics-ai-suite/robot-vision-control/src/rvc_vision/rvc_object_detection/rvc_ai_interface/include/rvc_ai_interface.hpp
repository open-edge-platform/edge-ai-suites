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

#ifndef __RVC_AI_INTERFACE_HPP__
#define __RVC_AI_INTERFACE_HPP__

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/macros.hpp"
#include "opencv2/opencv.hpp"
#include "rvc_vision_messages/msg/rotated_bb_list.hpp"

using vector6d_t = std::array<double, 6>;

/// @brief Any defined controllers have to inerit from this to be used in the StateMachine node
namespace RVC_AI {
class RVCAIInterface
{
public:
    RCLCPP_SMART_PTR_ALIASES_ONLY(RVCAIInterface)
    /**
     * @brief API entry point: define this plugin preprocessing operations
     *
     * @param inputImage cv::Mat input image to preprocess
     * @param outputImage preprocessed output cv::Mat
     * @return true on success
     * @return false otherwise
     */
    virtual bool pre_process_image(const cv::Mat inputImage, cv::Mat & outputImage) = 0;
    /**
     * @brief API entry point: run the inference on input image
     *
     * @param image input image
     * @param output result output blob in cv::Mat format
     * @return true on success
     * @return false otherwise
     */
    virtual bool run_inference_pipeline(const cv::Mat image, cv::Mat & output) = 0;
    /**
     * @brief API entry point: define the post processing to perform to retrieve the rotate bounding boxes
     *
     * @param input input blob cv::Mat
     * @param rotatedBBList output rotate Bounding box list
     * @return true on success
     * @return false otherwise
     */
    virtual bool post_process_image(const cv::Mat input, rvc_vision_messages::msg::RotatedBBList & rotatedBBList) = 0;
    /**
     * @brief API entry: plugin initialization
     *
     * @param node Ros node
     * @param modelName input file name
     * @return true on success
     * @return false otherwise
     */

    virtual bool init(rclcpp::Node * node, const std::string & modelName) = 0;
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
     * @brief Destroy the RVCAIInterface object.
     * 
     */
    virtual ~RVCAIInterface() {};

protected:
    /// @brief  Empty Constructor for pluginlib
    /// @param node a rclcpp node shared pointer
    RVCAIInterface() {}

private:
    /// @brief  Private copy constructor
    RVCAIInterface(const RVCAIInterface&);

    /// @brief Private copy assignment operator
    RVCAIInterface& operator=(const RVCAIInterface&);

};
} //namespace RVC_AI

#endif //__RVC_AI_INTERFACE_HPP__
