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

#include <functional>
#include <pcl/common/transforms.h>
#include <sensor_msgs/msg/point_field.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>

#include "groundfloor_segmentation/pointcloud_input_node.hpp"

PointCloudInput::PointCloudInput()
  : Node("pointcloud_input_for_segmentation")
{
  rclcpp::QoS topicQoS = 10;
  topicQoS.keep_last(3);

  mPCLSub = create_subscription<sensor_msgs::msg::PointCloud2>(
    "/input/points", topicQoS, std::bind(&PointCloudInput::onData, this, std::placeholders::_1));

  mPseudoImagePub = create_publisher<sensor_msgs::msg::Image>("/pseudo_camera/depth/image_rect_raw", topicQoS);
  mCameraInfoPub = create_publisher<sensor_msgs::msg::CameraInfo>("/pseudo_camera/depth/camera_info", topicQoS);
}

void PointCloudInput::onData(const sensor_msgs::msg::PointCloud2::ConstSharedPtr pointCloudMsg)
{
  if (!pointCloudMsg->is_dense)
  {
    RCLCPP_WARN(get_logger(), "Only dense pointclouds are supported");
    return;
  }

  std::vector<float> imageData;
  imageData.resize(pointCloudMsg->width * pointCloudMsg->height * 3);
  std::fill(imageData.begin(), imageData.end(), std::numeric_limits<float>::quiet_NaN());

  sensor_msgs::PointCloud2ConstIterator<float> iter_x(*pointCloudMsg, "x");
  sensor_msgs::PointCloud2ConstIterator<float> iter_y(*pointCloudMsg, "y");
  sensor_msgs::PointCloud2ConstIterator<float> iter_z(*pointCloudMsg, "z");

  for (std::size_t i = 0; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z, i += 3)
  {
    auto x = *iter_x;
    auto y = *iter_y;
    auto z = *iter_z;

    imageData[i] = x;
    imageData[i + 1] = y;
    imageData[i + 2] = z;
  }

  sensor_msgs::msg::Image msg;
  msg.encoding = "32FC3";
  msg.header = pointCloudMsg->header;
  msg.width = pointCloudMsg->width;
  msg.height = pointCloudMsg->height;
  msg.step = msg.width * 4 * 3;
  msg.is_bigendian = 0;
  msg.data.resize(msg.height * msg.step);
  memcpy(msg.data.data(), imageData.data(), imageData.size() * 4);
  mPseudoImagePub->publish(msg);

  sensor_msgs::msg::CameraInfo infoMsg;
  infoMsg.header = pointCloudMsg->header;
  infoMsg.height = pointCloudMsg->height;
  infoMsg.width = pointCloudMsg->width;

  infoMsg.k = {0, 0, 0, 0, 0, 0, 0, 0, 0};
  infoMsg.r = {0, 0, 0, 0, 0, 0, 0, 0, 0};
  infoMsg.p = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  mCameraInfoPub->publish(infoMsg);
}

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  try
  {
    auto node = std::make_shared<PointCloudInput>();
    rclcpp::spin(node);
  }
  catch (const std::exception &e)
  {
    std::cout << e.what();
  }
  rclcpp::shutdown();
  return 0;
}
