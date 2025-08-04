// SPDX-License-Identifier: Apache-2.0
// ----------------- BEGIN LICENSE BLOCK ---------------------------------
//
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
//
// ----------------- END LICENSE BLOCK -----------------------------------

#include <cstdint>
#include <functional>
#include <memory>

#include <rclcpp/rclcpp.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>

#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/msg/point_field.hpp>

#include "groundfloor_segmentation/Monitor.hpp"

struct CameraSensor
{
  std::string name{"camera"};

  // ROS subscriber
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr cameraInfoSub;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr cameraDataSub;

  // ROS publisher
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr labeledPclPub;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr filteredPclPub;

  // ROS data
  sensor_msgs::msg::CameraInfo::SharedPtr cameraInfo;
  sensor_msgs::msg::Image::SharedPtr imageMsg;
  std::shared_ptr<Eigen::Affine3f> transform;

  // internal data handler
  perception::monitor::Sensor sensor;
};

class GroundfloorSegmentationNode : public rclcpp::Node
{
public:
  GroundfloorSegmentationNode();

private:
  void onData(const sensor_msgs::msg::Image::ConstSharedPtr camMsg);

  // callback for camera intrinsics
  void onCameraInfo(const sensor_msgs::msg::CameraInfo::SharedPtr msg, std::shared_ptr<CameraSensor> sensor);

  bool setStaticSensorTransforms(const sensor_msgs::msg::Image::ConstSharedPtr &camMsg);

  void publishData();

  // tf
  std::unique_ptr<tf2_ros::Buffer> mTfBuffer;
  std::unique_ptr<tf2_ros::TransformListener> mTfListener;

  // perception monitor
  std::shared_ptr<perception::monitor::PerceptionMonitor> mPerceptionMonitor;

  // internal parameters
  std::string mBaseFrame;
  std::shared_ptr<CameraSensor> mSensor;
};
