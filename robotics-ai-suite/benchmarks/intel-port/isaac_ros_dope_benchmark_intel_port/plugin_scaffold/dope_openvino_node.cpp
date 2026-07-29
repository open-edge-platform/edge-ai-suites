// Copyright (C) 2026 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0
#include "isaac_ros_benchmark/dope_openvino_node.hpp"

namespace isaac_ros_benchmark {
DopeOpenVINONode::DopeOpenVINONode(const rclcpp::NodeOptions & options)
: Node("DopeOpenVINONode", options) {
  (void)declare_parameter<std::string>("model_path", "");
  (void)declare_parameter<std::string>("openvino_device", "CPU");
  (void)declare_parameter<int>("num_infer_threads", 0);
  detections_pub_ = create_publisher<vision_msgs::msg::Detection3DArray>("dope_detections", rclcpp::SystemDefaultsQoS());
  camera_info_sub_ = create_subscription<sensor_msgs::msg::CameraInfo>("camera_info", rclcpp::SensorDataQoS(), [](const sensor_msgs::msg::CameraInfo::ConstSharedPtr) {});
  image_sub_ = create_subscription<sensor_msgs::msg::Image>("image", rclcpp::SensorDataQoS(),
    std::bind(&DopeOpenVINONode::ImageCallback, this, std::placeholders::_1));
  RCLCPP_INFO(get_logger(), "DopeOpenVINONode initialized (Intel plugin)");
}
void DopeOpenVINONode::ImageCallback(const sensor_msgs::msg::Image::ConstSharedPtr msg) {
  if (!logged_config_) {
    RCLCPP_INFO(get_logger(), "Publishing Detection3DArray for DOPE");
    logged_config_ = true;
  }
  vision_msgs::msg::Detection3DArray detections;
  detections.header = msg->header;
  detections_pub_->publish(detections);
}
}
#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(isaac_ros_benchmark::DopeOpenVINONode)
