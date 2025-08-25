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

#pragma once

#include <limits>
#include <pcl/common/transforms.h>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>

#include <depth_image_proc/conversions.hpp>

// Handles float or uint16 depths
template <typename T>
void convert(const sensor_msgs::msg::Image::ConstSharedPtr &depth_msg,
             pcl::PointCloud<pcl::PointXYZ> &pclCloud,
             std::vector<float> &depthMatrix,
             std::vector<float> &heightMatrix,
             const Eigen::Affine3f transform,
             const sensor_msgs::msg::CameraInfo::ConstSharedPtr &camInfo)
{
  auto cloud_msg = std::make_shared<sensor_msgs::msg::PointCloud2>();
  cloud_msg->header = depth_msg->header;
  cloud_msg->height = depth_msg->height;
  cloud_msg->width = depth_msg->width;
  cloud_msg->is_dense = false;
  cloud_msg->is_bigendian = false;

  sensor_msgs::PointCloud2Modifier pcd_modifier(*cloud_msg);
  pcd_modifier.setPointCloud2FieldsByString(1, "xyz");

  image_geometry::PinholeCameraModel model;
  model.fromCameraInfo(camInfo);

  depth_image_proc::convertDepth<T>(depth_msg, cloud_msg, model);

  pcl::PCLPointCloud2 pclPC2;
  pcl_conversions::toPCL(*cloud_msg, pclPC2);
  pcl::fromPCLPointCloud2(pclPC2, pclCloud);

  // transform entire point cloud (not pointwise in loop above) due to speed advantage
  pcl::transformPointCloud(pclCloud, pclCloud, transform);

  // create depth and height images
  const unsigned int width = depth_msg->width;
  const unsigned int height = depth_msg->height;
  for (unsigned int v = 0; v < height; ++v)
  {
    for (unsigned int u = 0; u < width; ++u)
    {
      auto &point = pclCloud[u + v * width];
      heightMatrix[u + v * width] = point.z;
      depthMatrix[u + v * width] = std::sqrt(point.x * point.x + point.y * point.y);
    }
  }
}

void convert(const sensor_msgs::msg::Image::ConstSharedPtr &depth_msg,
             pcl::PointCloud<pcl::PointXYZ> &pclCloud,
             std::vector<float> &depthMatrix,
             std::vector<float> &heightMatrix,
             const Eigen::Affine3f &transform)
{
  const unsigned int width = depth_msg->width;
  const unsigned int height = depth_msg->height;
  const float *image_data = reinterpret_cast<const float *>(&depth_msg->data[0]);
  for (std::size_t i = 0; i < width * height; i++)
  {
    pclCloud[i] = pcl::PointXYZ(image_data[i * 3], image_data[i * 3 + 1], image_data[i * 3 + 2]);
  }

  // transform entire point cloud (not pointwise in loop above) due to speed advantage
  pcl::transformPointCloud(pclCloud, pclCloud, transform);

  // create depth and height images
  for (std::size_t i = 0; i < pclCloud.size(); i++)
  {
    auto &point = pclCloud[i];
    heightMatrix[i] = point.z;
    depthMatrix[i] = std::sqrt(point.x * point.x + point.y * point.y);
  }
}

bool convert(const sensor_msgs::msg::Image::ConstSharedPtr &depth_msg,
             pcl::PointCloud<pcl::PointXYZ> &pclCloud,
             std::vector<float> &depthMatrix,
             std::vector<float> &heightMatrix,
             const Eigen::Affine3f &transform,
             const sensor_msgs::msg::CameraInfo::ConstSharedPtr &camInfo)
{
  if (depth_msg->encoding == sensor_msgs::image_encodings::TYPE_16UC1
      || depth_msg->encoding == sensor_msgs::image_encodings::MONO16)
  {
    convert<uint16_t>(depth_msg, pclCloud, depthMatrix, heightMatrix, transform, camInfo);
    return true;
  }
  else if (depth_msg->encoding == sensor_msgs::image_encodings::TYPE_32FC1)
  {
    convert<float>(depth_msg, pclCloud, depthMatrix, heightMatrix, transform, camInfo);
    return true;
  }
  else if (depth_msg->encoding == sensor_msgs::image_encodings::TYPE_32FC3)
  {
    convert(depth_msg, pclCloud, depthMatrix, heightMatrix, transform);
    return true;
  }
  else
  {
    return false;
  }
}