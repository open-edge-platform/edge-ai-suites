// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <memory>

#include "rclcpp/rclcpp.hpp"
// #include "std_msgs/msg/string.hpp"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
using std::placeholders::_1;

class MinimalSubscriber : public rclcpp::Node
{
public:
  MinimalSubscriber()
  : Node("minimal_subscriber")
  {
    //   subscription_ = this->create_subscription<std_msgs::msg::String>(
    //   "topic", 10, std::bind(&MinimalSubscriber::topic_callback, this, _1));

    amcl_pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
      "amcl_pose",
      rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable(),
      std::bind(&MinimalSubscriber::amcl_pose_callback, this, std::placeholders::_1));

  }

private:
  // void topic_callback(const std_msgs::msg::String::SharedPtr msg) const
  void amcl_pose_callback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg) const
  {
    std::cout << "POSE IS --> : " << std::endl;
  }
  // rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr amcl_pose_sub_;
};

int main(int argc, char * argv[])
{
  try{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<MinimalSubscriber>());
    rclcpp::shutdown();
  }
  catch (const rclcpp::exceptions::InvalidQosOverridesException & e) {
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Caught exception: %s", e.what());
    rclcpp::shutdown();
    return 1; 
  }
  return 0;
}
