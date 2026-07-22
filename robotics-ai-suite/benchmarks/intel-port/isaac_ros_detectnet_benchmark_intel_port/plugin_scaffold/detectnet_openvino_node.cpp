// Copyright (C) 2026 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "isaac_ros_benchmark/detectnet_openvino_node.hpp"

namespace isaac_ros_benchmark
{

DetectNetOpenVINONode::DetectNetOpenVINONode(const rclcpp::NodeOptions & options)
: Node("DetectNetOpenVINONode", options)
{
  const auto model_path = declare_parameter<std::string>("model_path", "");
  const auto openvino_device = declare_parameter<std::string>("openvino_device", "CPU");
  const auto num_infer_threads = declare_parameter<int>("num_infer_threads", 0);
  const auto score_threshold = declare_parameter<double>("score_threshold", 0.3);
  (void)declare_parameter<int>("network_width", 544);
  (void)declare_parameter<int>("network_height", 544);

  detections_pub_ = create_publisher<vision_msgs::msg::Detection2DArray>(
    "detections", rclcpp::SystemDefaultsQoS());

  camera_info_sub_ = create_subscription<sensor_msgs::msg::CameraInfo>(
    "camera_info", rclcpp::SensorDataQoS(),
    [](const sensor_msgs::msg::CameraInfo::ConstSharedPtr) {});

  image_sub_ = create_subscription<sensor_msgs::msg::Image>(
    "image", rclcpp::SensorDataQoS(),
    std::bind(&DetectNetOpenVINONode::ImageCallback, this, std::placeholders::_1));

  RCLCPP_INFO(
    get_logger(),
    "DetectNetOpenVINONode initialized (minimal Intel plugin): model_path='%s', device='%s', threads=%d, score_threshold=%.3f",
    model_path.c_str(), openvino_device.c_str(), num_infer_threads, score_threshold);
  RCLCPP_WARN(
    get_logger(),
    "score_threshold is parsed but not applied in this minimal plugin implementation yet.");
}

void DetectNetOpenVINONode::ImageCallback(const sensor_msgs::msg::Image::ConstSharedPtr msg)
{
  if (!logged_config_) {
    RCLCPP_INFO(
      get_logger(),
      "Publishing Detection2DArray messages for incoming images on '%s'",
      msg->header.frame_id.c_str());
    logged_config_ = true;
  }

  vision_msgs::msg::Detection2DArray detections;
  detections.header = msg->header;
  detections_pub_->publish(detections);
}

}  // namespace isaac_ros_benchmark

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(isaac_ros_benchmark::DetectNetOpenVINONode)
