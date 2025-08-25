// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "../include/send_localization.hpp"

SendLocalization::SendLocalization(const rclcpp::NodeOptions & options)
: Node("nav2_send_goal")
{
  last_known_pose_ = true;
  amcl_pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
    "amcl_pose",
    rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable(),
    std::bind(&SendLocalization::amcl_pose_callback, this, _1));

  fast_global_loc_client_ = node->create_client<nav2_msgs::srv::GlobalLocalization>(
    "fast_global_localization");

  global_loc_client_ =
    node->create_client<std_srvs::srv::Empty>("reinitialize_global_localization");

  clear_entire_costmap_ = node->create_client<nav2_msgs::srv::ClearEntireCostmap>(
    "global_costmap/clear_entirely_global_costmap");

  marker_pub_ = this->create_publisher<visualization_msgs::msg::MarkerArray>(
    "localization_waypoints", 1);

  relocalization_request_srv_ = create_service<std_srvs::srv::Empty>(
    "request_relocalization",
    std::bind(&SendLocalization::relocalizationCallback, this, _1, _2, _3));
}

void SendLocalization::ReinitializeGlobalLocalization()
{
  auto request = std::make_shared<std_srvs::srv::Empty::Request>();
  while (!global_loc_client_->wait_for_service(1s)) {
    if (!rclcpp::ok()) {
      RCLCPP_ERROR(
        rclcpp::get_logger(
          "rclcpp"), "Interrupted while waiting for the service. Exiting.");
    }
    RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
  }
  auto result = global_loc_client_->async_send_request(request);
}

void SendLocalization::SendLocalizationCMDLastKNown()
{
  std::ifstream known_poses_file("last_known_poses.txt", std::ios::in);
  std::string line = "";
  double weight = 1;
  while (getline(known_poses_file, line)) {
    string x_value;
    string y_value;
    stringstream inputString(line);
    getline(inputString, x_value, ',');
    getline(inputString, y_value);
    last_known_poses_.push_back({std::stod(x_value), std::stod(y_value), weight});
    line = "";
    weight += 1.0;
  }
  reverse(last_known_poses_.begin(), last_known_poses_.end());
}
bool SendLocalization::SendLocalizationCMD()
{
  vector<inav_util::Rank> ranks;
  vector<double> center_x;
  vector<double> center_y;
  vector<double> sig;
  vector<double> weight;

  vector<double> file_weights;
  auto request = std::make_shared<nav2_msgs::srv::GlobalLocalization::Request>();

  if (last_known_pose_) {
    SendLocalizationCMDLastKNown();
    publishWaypointMarkers();
    last_known_poses_weights_sum_ = 0;
    int size = min(window_size_, (int)last_known_poses_.size());
    for (int i = 0; i < size; i++) {
      last_known_poses_weights_sum_ += last_known_poses_[i][2];
    }
    for (int i = 0; i < size; i++) {
      center_x.push_back(last_known_poses_[i][0]);
      center_y.push_back(last_known_poses_[i][1]);
      sig.push_back((2.0 * (last_known_poses_[i][2] / last_known_poses_weights_sum_)));
      weight.push_back(last_known_poses_[i][2] / last_known_poses_weights_sum_);
      inav_util::Rank rank;
      rank.position.x = last_known_poses_[i][0];
      rank.position.y = last_known_poses_[i][1];

      rank.sigma = (2.0 * (last_known_poses_[i][2] / last_known_poses_weights_sum_));

      rank.weight = last_known_poses_[i][2] / last_known_poses_weights_sum_;

      ranks.push_back(rank);
    }
  } else {
    std::ifstream rank_file("ranks.csv", std::ios::in);
    std::string line = "";
    double sum_weight = 0.0;
    while (getline(rank_file, line)) {
      string x_value;
      string y_value;
      string w_value;
      stringstream inputString(line);
      getline(inputString, x_value, ',');
      getline(inputString, y_value, ',');
      getline(inputString, w_value);
      center_x.push_back(std::stod(x_value));
      center_y.push_back(std::stod(y_value));
      weight.push_back(std::stod(w_value));
      last_known_poses_.push_back({std::stod(x_value), std::stod(y_value), std::stod(w_value)});
      sum_weight += std::stod(w_value);
      line = "";
    }
    for (int i = 0; i < weight.size(); i++) {
      sig.push_back(0.25);
      weight[i] = ((double)weight[i] / sum_weight);
    }
    rank_file.close();
  }
  publishWaypointMarkers();
  request->center_x = center_x;
  request->center_y = center_y;
  request->sigma = sig;
  request->weights = weight;
  while (!fast_global_loc_client_->wait_for_service(1s)) {
    if (!rclcpp::ok()) {
      RCLCPP_ERROR(
        rclcpp::get_logger(
          "rclcpp"), "Interrupted while waiting for the service. Exiting.");
    }
    RCLCPP_INFO(
      rclcpp::get_logger(
        "rclcpp"), "fast global localization service not available, waiting again...");
  }

  auto result = fast_global_loc_client_->async_send_request(request);

  auto request_clear_costmap = std::make_shared<nav2_msgs::srv::ClearEntireCostmap::Request>();
  while (!clear_entire_costmap_->wait_for_service(1s)) {
    if (!rclcpp::ok()) {
      RCLCPP_ERROR(
        rclcpp::get_logger(
          "rclcpp"), "Interrupted while waiting for the service. Exiting.");
    }
    RCLCPP_INFO(
      rclcpp::get_logger(
        "rclcpp"), "clear entire costmap service not available, waiting again...");
  }
  auto result_clear_costmap = clear_entire_costmap_->async_send_request(request_clear_costmap);
  return center_x.size() > 0 ? true : false;
}

void SendLocalization::amcl_pose_callback(
  const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
{
  auto pose_ = msg->pose;
  current_pose_ = msg;
  double amcl_pose_x = pose_.pose.position.x;
  double amcl_pose_y = pose_.pose.position.y;

  if (isLocalized()) {
    if (!initialized) {
      auto request = std::make_shared<nav2_msgs::srv::ClearEntireCostmap::Request>();
      while (!clear_entire_costmap_->wait_for_service(1s)) {
        if (!rclcpp::ok()) {
          RCLCPP_ERROR(
            rclcpp::get_logger(
              "rclcpp"), "Interrupted while waiting for the service. Exiting.");
        }
        RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
      }
      auto result = clear_entire_costmap_->async_send_request(request);
      initialized = true;
    }
  } else {
    num_iteration++;
  }
}

bool SendLocalization::isLocalized()
{
  if (current_pose_->pose.covariance[cov_x_] < x_tol_ &&
    current_pose_->pose.covariance[cov_y_] < y_tol_ &&
    current_pose_->pose.covariance[cov_a_] < rot_tol_)
  {
    return true;
  }

  return false;
}

void SendLocalization::relocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/)
{
  SendLocalizationCMD();
}

void SendLocalization::publishWaypointMarkers()
{
  visualization_msgs::msg::Marker m;
  auto ma = std::make_unique<visualization_msgs::msg::MarkerArray>();
  for (size_t i = 0; i < std::min((int)last_known_poses_.size(), 10); i++) {
    m.header.frame_id = "map";
    m.type = m.SPHERE;
    m.action = m.ADD;
    m.id = i;
    m.pose.orientation.x = 0.0;
    m.pose.orientation.y = 0.0;
    m.pose.orientation.z = 0.0;
    m.pose.orientation.w = 1.0;
    m.scale.x = 0.025;
    m.scale.y = 0.025;
    m.scale.z = 0.025;
    m.color.a = 1.0;
    m.color.r = 1.0;
    m.color.g = 0.0;
    m.color.b = 0.0;
    m.points.clear();
    m.pose.position.x = last_known_poses_[i][0];
    m.pose.position.y = last_known_poses_[i][1];
    m.pose.position.z = 0.0;
    ma->markers.push_back(m);
  }
  marker_pub_->publish(std::move(ma));
}
