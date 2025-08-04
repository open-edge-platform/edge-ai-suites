// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <memory>
#include <iostream>
#include <fstream>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "std_srvs/srv/empty.hpp"

using std::placeholders::_1;
using namespace std::chrono_literals;

class PoseChecker : public rclcpp::Node
{
public:
  PoseChecker()
  : Node("pose_subscriber")
  {
    amcl_pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
      "amcl_pose",
      rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable(),
      std::bind(&PoseChecker::amcl_pose_callback, this, std::placeholders::_1));
    poses_file_.open("last_known_poses.txt");
    request_relocalization_ = this->create_client<std_srvs::srv::Empty>("request_relocalization");

    this->declare_parameter("mode", "");
    this->get_parameter("mode", mode_value_);
    if (mode_value_ == "demo" || mode_value_ == "benchmarking") {
      demo_ = true;
    }
  }
  ~PoseChecker()
  {
    poses_file_.close();
  }

private:
  void amcl_pose_callback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
  {
    auto pose_ = msg->pose;
    current_pose_ = msg;
    if (isLocalized() && pose_checker_enable_) {
      poses_file_.open("last_known_poses.txt", std::ios_base::app);
      last_known_location_.push_back({pose_.pose.position.x, pose_.pose.position.y});
      poses_file_ << pose_.pose.position.x << "," << pose_.pose.position.y << "\n";
      poses_file_.close();
    } else if (pose_checker_enable_) {
      pose_checker_enable_ = false;
      if (!demo_) {
        auto request = std::make_shared<std_srvs::srv::Empty::Request>();
        while (!request_relocalization_->wait_for_service(1s)) {
          if (!rclcpp::ok()) {
            RCLCPP_ERROR(
              rclcpp::get_logger(
                "rclcpp"), "Interrupted while waiting for the service. Exiting.");
          }
          RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
        }
        // send re-localization request
        auto result = request_relocalization_->async_send_request(request);
      }
    }
    if (isLocalized()) {
      pose_checker_enable_ = true;
    }
  }
  bool isLocalized()
  {
    if (current_pose_->pose.covariance[cov_x_] < x_tol_ &&
      current_pose_->pose.covariance[cov_y_] < y_tol_ &&
      current_pose_->pose.covariance[cov_a_] < rot_tol_)
    {
      return true;
    }

    return false;
  }
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr amcl_pose_sub_;
  geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr current_pose_;
  std::vector<std::pair<double, double>> last_known_location_;
  std::ofstream poses_file_;
  bool pose_checker_enable_ = true;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr request_relocalization_;
  static const int cov_x_ = 0;
  static const int cov_y_ = 7;
  static const int cov_a_ = 35;
  double x_tol_ = 0.5;
  double y_tol_ = 0.5;
  double rot_tol_ = M_PI / 4;
  std::string mode_value_ = "";
  bool demo_ = false;

};

int main(int argc, char * argv[])
{
  try{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<PoseChecker>();
    rclcpp::spin(node);
    rclcpp::shutdown();
  }
  catch (const rclcpp::exceptions::InvalidQosOverridesException & e) {
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Caught exception: %s", e.what());
    rclcpp::shutdown();
    return 1; 
  }
  return 0;
}
