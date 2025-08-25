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

namespace RVC {

/** Object Detection class, inherits from ros node*/
class ObjectDetection : public rclcpp::Node
{
private:
    /** reference to the plugin interface abstraction. will be used to all the plugin APIs */
    std::shared_ptr<RVC_AI::RVCAIInterface> ai;

    /** subscription to the camera RGB image topic*/
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr m_image_sub;

    /** RotatedBBList publisher */
    rclcpp::Publisher<rvc_vision_messages::msg::RotatedBBList>::SharedPtr m_rotated_bb_list_msg;

    /** boolean config parameter to enable/disable publishing the inference image with annotations*/
    bool publish_inference_images_param;

    /** config parameter to pass to the plugin initialization API */
    std::string model_name_param;

    /** inference image to publish */
    image_transport::Publisher m_inference_image_pub_;

    /** callback on receiving image from camera publisher*/
    void m_image_callback(sensor_msgs::msg::Image::UniquePtr msg);

public:
/** Destructor*/
    ~ObjectDetection();

/** Constructor*/
    explicit ObjectDetection(const rclcpp::NodeOptions & options);

};
}
