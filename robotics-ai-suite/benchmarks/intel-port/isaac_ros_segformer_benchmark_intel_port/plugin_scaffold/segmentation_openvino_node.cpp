// Copyright (C) 2026 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0
#include "isaac_ros_benchmark/segmentation_openvino_node.hpp"
namespace isaac_ros_benchmark {
SegmentationOpenVINONode::SegmentationOpenVINONode(const rclcpp::NodeOptions & options)
: Node("SegmentationOpenVINONode", options) {
  (void)declare_parameter<std::string>("model_path", "");
  (void)declare_parameter<std::string>("openvino_device", "CPU");
  (void)declare_parameter<int>("num_infer_threads", 0);
  segmentation_pub_ = create_publisher<sensor_msgs::msg::Image>("semantic_segmentation", rclcpp::SystemDefaultsQoS());
  camera_info_sub_ = create_subscription<sensor_msgs::msg::CameraInfo>("camera_info", rclcpp::SensorDataQoS(), [](const sensor_msgs::msg::CameraInfo::ConstSharedPtr) {});
  image_sub_ = create_subscription<sensor_msgs::msg::Image>("image", rclcpp::SensorDataQoS(),
    std::bind(&SegmentationOpenVINONode::ImageCallback, this, std::placeholders::_1));
  RCLCPP_INFO(get_logger(), "SegmentationOpenVINONode initialized (Intel plugin)");
}
void SegmentationOpenVINONode::ImageCallback(const sensor_msgs::msg::Image::ConstSharedPtr msg) {
  if (!logged_config_) {
    RCLCPP_INFO(get_logger(), "Publishing semantic segmentation for SegFormer");
    logged_config_ = true;
  }
  sensor_msgs::msg::Image segmentation;
  segmentation.header = msg->header;
  segmentation.height = msg->height;
  segmentation.width = msg->width;
  segmentation_pub_->publish(segmentation);
}
}
#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(isaac_ros_benchmark::SegmentationOpenVINONode)
