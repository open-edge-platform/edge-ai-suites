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
#include <memory>
#include <pcl/common/transforms.h>
#include <pcl_conversions/pcl_conversions.h>
#include <sensor_msgs/image_encodings.hpp>
#include <tf2_eigen/tf2_eigen.hpp>

#include "groundfloor_segmentation/depth_conversions.hpp"
#include "groundfloor_segmentation/groundfloor_segmentation_node.hpp"

GroundfloorSegmentationNode::GroundfloorSegmentationNode()
  : Node("groundfloor_segmentation")
{
  declare_parameter("base_frame", "base_link");
  mBaseFrame = get_parameter("base_frame").as_string();

  declare_parameter("use_best_effort_qos", false);

  declare_parameter("sensor.min_distance_to_ego", 0.7);
  declare_parameter("sensor.max_surface_height", 0.2);
  declare_parameter("sensor.max_incline", 15.f);
  declare_parameter("sensor.robot_height", 2.0f);
  declare_parameter("sensor.name", "camera");

  std::string sensorName = get_parameter("sensor.name").as_string();

  // get sensor parameters
  // note: Sensors could have different parameter values!
  perception::monitor::ConfigParameters sensorParameters;
  sensorParameters.maxSurfaceHeight = get_parameter("sensor.max_surface_height").as_double();
  sensorParameters.minDistanceToEgo = get_parameter("sensor.min_distance_to_ego").as_double();
  sensorParameters.maxIncline = get_parameter("sensor.max_incline").as_double();
  sensorParameters.robotHeightMax = get_parameter("sensor.robot_height").as_double();
  sensorParameters.enhancedRobustness = true;
  sensorParameters.evaluateCalibration = false;
  sensorParameters.useExtendedGroundPlane = false;
  sensorParameters.overhangingObjectMinDistance = 0.05f;

  mPerceptionMonitor = std::make_shared<perception::monitor::PerceptionMonitor>();

  mTfBuffer = std::make_unique<tf2_ros::Buffer>(get_clock());
  mTfListener = std::make_unique<tf2_ros::TransformListener>(*mTfBuffer);

  rclcpp::QoS topicQoS = 10;
  if (get_parameter("use_best_effort_qos").as_bool())
  {
    topicQoS = rclcpp::SensorDataQoS();
  }
  topicQoS.keep_last(2);

  mSensor = std::make_shared<CameraSensor>();
  mSensor->sensor.mParameters = sensorParameters;

  std::function<void(std::shared_ptr<sensor_msgs::msg::CameraInfo>)> fnc
    = std::bind(&GroundfloorSegmentationNode::onCameraInfo, this, std::placeholders::_1, mSensor);
  mSensor->cameraInfoSub
    = create_subscription<sensor_msgs::msg::CameraInfo>(sensorName + "/depth/camera_info", topicQoS, fnc);

  mSensor->cameraDataSub = create_subscription<sensor_msgs::msg::Image>(
    sensorName + "/depth/image_rect_raw",
    topicQoS,
    std::bind(&GroundfloorSegmentationNode::onData, this, std::placeholders::_1));

  mSensor->labeledPclPub = create_publisher<sensor_msgs::msg::PointCloud2>("segmentation/labeled_points", topicQoS);
  mSensor->filteredPclPub = create_publisher<sensor_msgs::msg::PointCloud2>("segmentation/obstacle_points", topicQoS);
}

void GroundfloorSegmentationNode::onCameraInfo(const sensor_msgs::msg::CameraInfo::SharedPtr msg,
                                               std::shared_ptr<CameraSensor> sensor)
{
  RCLCPP_DEBUG(get_logger(),
               "Received initial camera info: height='%d', width='%d' for %s",
               msg->height,
               msg->width,
               sensor->name.c_str());

  sensor->cameraInfo = msg;
  sensor->sensor.setResolution(msg->width, msg->height);

  sensor->cameraInfoSub.reset(); // unsubscribe
}

bool GroundfloorSegmentationNode::setStaticSensorTransforms(const sensor_msgs::msg::Image::ConstSharedPtr &camMsg)
{
  if (!mSensor->cameraInfo)
  {
    return false;
  }

  if (!mSensor->transform)
  {
    auto transform = mTfBuffer->canTransform(mBaseFrame, camMsg->header.frame_id, camMsg->header.stamp);
    if (!transform)
    {
      RCLCPP_WARN(get_logger(), "No transform to %s available. Skipping...", mBaseFrame.c_str());
      return false;
    }

    auto rosTf = mTfBuffer->lookupTransform(
      mBaseFrame, camMsg->header.frame_id, camMsg->header.stamp, rclcpp::Duration::from_seconds(1));

    Eigen::Affine3f transformEigen = tf2::transformToEigen(rosTf).cast<float>();

    mSensor->transform = std::make_shared<Eigen::Affine3f>(transformEigen);
  }

  return true;
}

void GroundfloorSegmentationNode::onData(const sensor_msgs::msg::Image::ConstSharedPtr camMsg)
{
  auto const processing_start_time = rclcpp::Clock{RCL_SYSTEM_TIME}.now();
  if (!setStaticSensorTransforms(camMsg))
  {
    return;
  }

  if (!mSensor->cameraInfo)
  {
    return;
  }

  mSensor->imageMsg = std::const_pointer_cast<sensor_msgs::msg::Image>(camMsg);

  bool success = convert(mSensor->imageMsg,
                         mSensor->sensor.mPointCloud,
                         mSensor->sensor.mDepthImage,
                         mSensor->sensor.mHeightImage,
                         *(mSensor->transform.get()),
                         mSensor->cameraInfo);
  if (!success)
  {
    RCLCPP_WARN(get_logger(), "Unknown depth image format - Skipping");
    return;
  }

  if (!mPerceptionMonitor->execute(mSensor->sensor))
  {
    RCLCPP_WARN(get_logger(), "Segmentation not possible - Skipping");
    return;
  }

  publishData();

  auto const processing_end_time = rclcpp::Clock{RCL_SYSTEM_TIME}.now();
  auto const processing_time = (processing_end_time - processing_start_time).seconds();
  RCLCPP_DEBUG(get_logger(), "Processing done. (duration: %f ms)", processing_time * 1000);
}

void GroundfloorSegmentationNode::publishData()
{
  // publish labeled pointcloud
  sensor_msgs::msg::PointCloud2 outLabeledPclMsg;
  pcl::toROSMsg(mSensor->sensor.mLabeledPointCloud, outLabeledPclMsg);
  outLabeledPclMsg.header = mSensor->imageMsg->header;
  outLabeledPclMsg.is_dense = false;
  outLabeledPclMsg.header.frame_id = mBaseFrame;
  mSensor->labeledPclPub->publish(outLabeledPclMsg);

  // publish filtered pointcloud
  sensor_msgs::msg::PointCloud2 outObstaclePclMsg;
  pcl::toROSMsg(mSensor->sensor.mObstaclePoints, outObstaclePclMsg);
  outObstaclePclMsg.header = mSensor->imageMsg->header;
  outObstaclePclMsg.is_dense = false;
  outObstaclePclMsg.header.frame_id = mBaseFrame;
  mSensor->filteredPclPub->publish(outObstaclePclMsg);
}

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  try
  {
    auto node = std::make_shared<GroundfloorSegmentationNode>();
    rclcpp::spin(node);
  }
  catch (const std::exception &e)
  {
    std::cout << e.what();
  }
  rclcpp::shutdown();
  return 0;
}
