// Copyright (C) 2026 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0
#ifndef ISAAC_ROS_BENCHMARK__DOPE_OPENVINO_NODE_HPP_
#define ISAAC_ROS_BENCHMARK__DOPE_OPENVINO_NODE_HPP_
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "vision_msgs/msg/detection3_d_array.hpp"

namespace isaac_ros_benchmark {
class DopeOpenVINONode : public rclcpp::Node {
public:
  explicit DopeOpenVINONode(const rclcpp::NodeOptions & options);
private:
  void ImageCallback(const sensor_msgs::msg::Image::ConstSharedPtr msg);
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_sub_;
  rclcpp::Publisher<vision_msgs::msg::Detection3DArray>::SharedPtr detections_pub_;
  bool logged_config_{false};
};
}
#endif
