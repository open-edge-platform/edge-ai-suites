// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef SEND_LOCALIZATION_HPP_
#define SEND_LOCALIZATION_HPP_

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "nav2_msgs/srv/global_localization.hpp"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "std_srvs/srv/empty.hpp"
#include "nav2_msgs/srv/clear_entire_costmap.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

#include "its_planner/path_utils/path_utils.hpp"
#include "its_planner/prm/prm.hpp"
#include <string>
#include <fstream>
#include <sstream>

using namespace std;
using namespace std::chrono_literals;
using namespace std::placeholders;

static int num_iteration = 0;

bool initialized = false;

class SendLocalization : public rclcpp::Node
{
public:
  explicit SendLocalization(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  void ReinitializeGlobalLocalization();
  void SendLocalizationCMDLastKNown();
  bool SendLocalizationCMD();

public:
  rclcpp::Client<nav2_msgs::srv::GlobalLocalization>::SharedPtr fast_global_loc_client_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr global_loc_client_;
  rclcpp::Client<nav2_msgs::srv::ClearEntireCostmap>::SharedPtr clear_entire_costmap_;
  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("send_localization");
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr amcl_pose_sub_;
  geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr current_pose_;
  std::vector<vector<double>> last_known_poses_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr marker_pub_;
  rclcpp::Service<std_srvs::srv::Empty>::SharedPtr relocalization_request_srv_;
  int window_size_ = 12;  //5;

  double last_known_poses_weights_sum_ = 0.0;
  bool last_known_pose_;

  static const int cov_x_ = 0;
  static const int cov_y_ = 7;
  static const int cov_a_ = 35;
  double x_tol_ = 0.25;
  double y_tol_ = 0.25;
  double rot_tol_ = M_PI / 4;

  void amcl_pose_callback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg);

  bool isLocalized();

  void relocalizationCallback(
    const std::shared_ptr<rmw_request_id_t>/*request_header*/,
    const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
    std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/);

  void publishWaypointMarkers();
};

#endif  // SEND_LOCALIZATION_HPP_
