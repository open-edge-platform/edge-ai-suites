// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "std_srvs/srv/empty.hpp"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "nav2_msgs/srv/clear_entire_costmap.hpp"

#include <string>
#include <fstream>
#include <random>
#include <iostream>
#include <chrono>
#include <thread>
#include <mutex>
#include <future>

using NavigateToPose = nav2_msgs::action::NavigateToPose;
using GoalHandleNavigateToPose = rclcpp_action::ClientGoalHandle<NavigateToPose>;
using std::placeholders::_1;
using std::placeholders::_2;
using namespace std::chrono_literals;

static const int cov_x_ = 0;
static const int cov_y_ = 7;
static const int cov_a_ = 35;
static const double eps_x = 0.4;
static const double eps_y = 0.4;
double feedback_ = 2.0;
static int success_count = 0;
static int fail_count = 0;
bool demo = false;

class Benchmark : public rclcpp::Node
{
private:
  bool pose_recieved_ = false;
  rclcpp_action::Client<NavigateToPose>::SharedPtr send_goal_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr reset_world_;
  rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr publish_initial_pose_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr request_relocalization_;
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr amcl_pose_sub_;
  geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr current_pose_;
  std::pair<double, double> last_pose_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr global_loc_client_;
  rclcpp::Client<nav2_msgs::srv::ClearEntireCostmap>::SharedPtr clear_entire_costmap_;

  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr disable_sensor_;
  rclcpp::Client<std_srvs::srv::Empty>::SharedPtr enable_sensor_;
  std::string mode_value_ = "";
  std::string saved_pose_dir_ = "";

public:
  explicit Benchmark()
  : Node("reloc_benchmarking")
  {
    activate_services();

    publish_initial_pose_ =
      this->create_publisher<geometry_msgs::msg::PoseWithCovarianceStamped>("initialpose", 10);

    amcl_pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
      "amcl_pose",
      rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable(),
      std::bind(&Benchmark::amcl_pose_callback, this, std::placeholders::_1));

    disable_sensor_ = this->create_client<std_srvs::srv::Empty>("disable_laser");
    enable_sensor_ = this->create_client<std_srvs::srv::Empty>("enable_laser");

    this->declare_parameter("mode", "demo");
    this->get_parameter("mode", mode_value_);
    this->declare_parameter("saved_pose_dir", "");
    this->get_parameter("saved_pose_dir", saved_pose_dir_);

    if (mode_value_ == "demo") {
      this->Demo();
    } else {
      this->runBenchmarking(100);
    }
  }

  void reset_services()
  {
    send_goal_.reset();
    request_relocalization_.reset();
    global_loc_client_.reset();
    clear_entire_costmap_.reset();
    reset_world_.reset();
  }

  void activate_services()
  {
    send_goal_ = rclcpp_action::create_client<NavigateToPose>(this, "navigate_to_pose");
    request_relocalization_ = this->create_client<std_srvs::srv::Empty>("request_relocalization");
    global_loc_client_ = this->create_client<std_srvs::srv::Empty>(
      "reinitialize_global_localization");
    clear_entire_costmap_ = this->create_client<nav2_msgs::srv::ClearEntireCostmap>(
      "global_costmap/clear_entirely_global_costmap");
    reset_world_ = this->create_client<std_srvs::srv::Empty>("reset_simulation");
  }
  bool sendGoal(float x_goal, float y_goal)
  {
    while (!send_goal_->wait_for_action_server()) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the goal service. Exiting.");
        rclcpp::shutdown();
        return false;
      }
      RCLCPP_INFO(get_logger(), "send goal Action server is not yet available...");
    }
    auto goal = nav2_msgs::action::NavigateToPose::Goal();
    goal.pose.header.stamp = this->now();
    goal.pose.header.frame_id = "map";
    goal.pose.pose.position.x = x_goal;
    goal.pose.pose.position.y = y_goal;
    goal.pose.pose.orientation.x = 0.0;
    goal.pose.pose.orientation.y = 0.0;
    goal.pose.pose.orientation.w = 1.0;
    goal.pose.pose.orientation.z = 0.0;

    auto send_goal_options = rclcpp_action::Client<NavigateToPose>::SendGoalOptions();
    send_goal_options.feedback_callback = std::bind(&Benchmark::feedbackCallback, this, _1, _2);
    send_goal_options.result_callback = std::bind(&Benchmark::resultCallback, this, _1);
    auto goal_handle_future = send_goal_->async_send_goal(goal, send_goal_options);

    // future = self.goal_handle.cancel_goal_async()


    if (rclcpp::spin_until_future_complete(this->get_node_base_interface(), goal_handle_future) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_WARN(get_logger(), "Failed to send Goal.");
      return false;
    }

    // wait for result
    auto goal_handle = goal_handle_future.get();
    if (!this->waitForGoalCompletion(goal_handle)) {
      RCLCPP_WARN(get_logger(), "Failed to wait for Goal completion.");
      return false;
    } else {
      RCLCPP_INFO(get_logger(), "Wait for Goal complete Success!");
      return true;
    }
    return false;
  }

  bool waitForGoalCompletion(const GoalHandleNavigateToPose::SharedPtr & goal_handle)
  {
    while (rclcpp::ok()) {
      if (goal_handle->get_status() == rclcpp_action::GoalStatus::STATUS_SUCCEEDED) {
        return true;
      }
      if (feedback_ < 0.28) {
        feedback_ = 2.0;
        auto future = send_goal_->async_cancel_all_goals();
        return true;
      }
      if (goal_handle->get_status() == rclcpp_action::GoalStatus::STATUS_ABORTED ||
        goal_handle->get_status() == rclcpp_action::GoalStatus::STATUS_CANCELED ||
        goal_handle->get_status() == rclcpp_action::GoalStatus::STATUS_UNKNOWN)
      {
        return false;
      }

      if (demo) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10000));
        disableSensor();
        // resetWorld();
        std::this_thread::sleep_for(std::chrono::milliseconds(10000));
        enableSensor();
        clearCostmap();
        std::this_thread::sleep_for(std::chrono::milliseconds(2000));

        // send re-localization request
        auto request = std::make_shared<std_srvs::srv::Empty::Request>();
        while (!request_relocalization_->wait_for_service(std::chrono::seconds(1))) {
          if (!rclcpp::ok()) {
            RCLCPP_ERROR(
              get_logger(), "Interrupted while waiting for the relocalization service. Exiting.");
            rclcpp::shutdown();
            return false;
          }
          RCLCPP_INFO(get_logger(), "service not available, waiting again...");
        }
        auto result = request_relocalization_->async_send_request(request);
        std::this_thread::sleep_for(std::chrono::milliseconds(2000));
        demo = false;
        auto future = send_goal_->async_cancel_all_goals();
        std::this_thread::sleep_for(std::chrono::milliseconds(5000));
        this->sendGoal(2.00, -0.5);
      }
      rclcpp::spin_some(this->get_node_base_interface());
    }
    return false;
  }

  void feedbackCallback(
    GoalHandleNavigateToPose::SharedPtr,
    const std::shared_ptr<const NavigateToPose::Feedback> feedback)
  {
    if (feedback->distance_remaining > 0) {
      feedback_ = feedback->distance_remaining;
    }
  }

  void resultCallback(GoalHandleNavigateToPose::WrappedResult result)
  {
    switch (result.code) {
      case rclcpp_action::ResultCode::SUCCEEDED:
        RCLCPP_INFO(get_logger(), "Success!!!");
        break;
      case rclcpp_action::ResultCode::ABORTED:
        RCLCPP_ERROR(get_logger(), "Goal was aborted");
        return;
      case rclcpp_action::ResultCode::CANCELED:
        RCLCPP_ERROR(get_logger(), "Goal was canceled");
        return;
      default:
        RCLCPP_ERROR(get_logger(), "Unknown result code");
        return;
    }
  }

  void sendinitialPose()
  {
    geometry_msgs::msg::PoseWithCovarianceStamped pose;
    pose.header.frame_id = "map";
    pose.header.stamp = this->now();
    pose.pose.pose.position.x = -2.0;
    pose.pose.pose.position.y = -0.5;
    pose.pose.pose.position.z = 0.0;
    pose.pose.pose.orientation.x = 0.0;
    pose.pose.pose.orientation.y = 0.0;
    pose.pose.pose.orientation.z = 0.0;
    pose.pose.pose.orientation.w = 1.0;
    for (int i = 0; i < 35; i++) {
      pose.pose.covariance[i] = 0.0;
    }
    pose.pose.covariance[0] = 0.02;
    pose.pose.covariance[7] = 0.02;
    pose.pose.covariance[35] = 0.02;
    publish_initial_pose_->publish(pose);
    RCLCPP_INFO(this->get_logger(), "Sent initial pose");
  }

  void runBenchmarking(int num_itr)
  {
    std::vector<int> relocalization_time;
    for (int i = 0; i < num_itr; i++) {
      RCLCPP_INFO(get_logger(), "Current itr num= %d", i);
      resetWorld();
      sendinitialPose();
      clearCostmap();
      // std::pair<double, double> goal;
      auto goal = getRandomGoalPose();
      while (sqrt(
          (goal.first - (-2.0)) * (goal.first - (-2.0)) +
          (goal.second - (-0.5)) * (goal.second - (-0.5))) < 2.0)
      {
        goal = getRandomGoalPose();
      }
      if (this->sendGoal(goal.first, goal.second)) {
        // save last pose location
        last_pose_ = {current_pose_->pose.pose.position.x, current_pose_->pose.pose.position.y};
        // Do relocalization
        testRelocalization(relocalization_time);
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(5000));
    }
    int sum = 0;
    for (int i = 0; i < relocalization_time.size(); i++) {
      sum += relocalization_time[i];
    }
    if (relocalization_time.size() > 0) {
      RCLCPP_INFO(
        get_logger(), "average time took for re-localization = %d",
        sum / relocalization_time.size());
    }
    RCLCPP_INFO(get_logger(), "fail_count = %d", fail_count);
    RCLCPP_INFO(get_logger(), "success_count = %d", success_count);
    return;
  }

  void clearCostmap()
  {
    // clear costmap
    auto request = std::make_shared<nav2_msgs::srv::ClearEntireCostmap::Request>();
    while (!clear_entire_costmap_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "service not available, waiting again...");
    }
    auto result = clear_entire_costmap_->async_send_request(request);
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
  }

  void resetWorld()
  {
    reset_services();
    activate_services();
    pose_recieved_ = false;
    auto request_reset = std::make_shared<std_srvs::srv::Empty::Request>();
    while (!reset_world_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the reset service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "reset service not available, waiting again...");
    }
    auto reset_world = reset_world_->async_send_request(request_reset);
  }

  std::pair<double, double>
  getRandomGoalPose()
  {
    std::string line;
    int random = 0;
    int numOfLines = 0;
    std::pair<double, double> goal;
    std::ifstream saved_poses_file(saved_pose_dir_ + "/saved_poses.txt");
    
    // Create a random device and use it to seed a mersenne twister engine
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> distrib(0, 149); // Assuming we want a number between 0 and 149
    random = distrib(gen);
    
    while (getline(saved_poses_file, line)) {
      ++numOfLines;
      if (numOfLines == random) {
        std::string x_value;
        std::string y_value;
        std::stringstream inputString(line);
        getline(inputString, x_value, ',');
        getline(inputString, y_value);
        line = "";
        goal.first = std::stod(x_value);
        goal.second = std::stod(y_value);
        return goal;
      }
    }
    return goal;
  }

  void testRelocalization(std::vector<int> & relocalization_time)
  {
    pose_recieved_ = false;
    ReinitializeGlobalLocalization();
    std::this_thread::sleep_for(std::chrono::milliseconds(2000));
    // send re-localization request
    auto request = std::make_shared<std_srvs::srv::Empty::Request>();
    while (!request_relocalization_->wait_for_service(5s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(
          get_logger(), "Interrupted while waiting for the relocalization service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "service not available, waiting again...");
    }
    auto result = request_relocalization_->async_send_request(request);
    // Measure the time it takes to re-localize.
    auto s_reloc_timer = std::chrono::steady_clock::now();
    std::chrono::milliseconds timeout(10000);

    while (!isLocalized() ) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting relocaliztion. Exiting.");
        rclcpp::shutdown();
        return;
      }
      rclcpp::spin_some(this->get_node_base_interface());
      auto current_time = std::chrono::steady_clock::now();
      auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(
        current_time - s_reloc_timer);
      if (elapsed_time >= timeout) {
        RCLCPP_INFO(get_logger(), "Re-localization failed...");
        return;
      }
    }

    auto e_reloc_timer = std::chrono::steady_clock::now();
    auto elapsed_reloc_time = std::chrono::duration_cast<std::chrono::milliseconds>(
      e_reloc_timer - s_reloc_timer);
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (abs(last_pose_.first - current_pose_->pose.pose.position.x) < eps_x &&
      abs(last_pose_.second - current_pose_->pose.pose.position.y) < eps_y)
    {
      success_count++;
      RCLCPP_INFO(get_logger(), "Time it took in (ms) = %d", elapsed_reloc_time.count());
      relocalization_time.push_back(elapsed_reloc_time.count());
    } else { //  It localized to a wrong location
      fail_count++;
    }
    double success_rate = ((double)success_count / (double)(success_count + fail_count)) * 100.0;
    RCLCPP_INFO(get_logger(), "success_count = %d", success_count);
    RCLCPP_INFO(get_logger(), "fail_count = %d", fail_count);
    RCLCPP_INFO(get_logger(), "success_rate = %f", success_rate);
    // measure success
  }

  void ReinitializeGlobalLocalization()
  {
    auto request = std::make_shared<std_srvs::srv::Empty::Request>();
    while (!global_loc_client_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "service not available, waiting again...");
    }
    auto result = global_loc_client_->async_send_request(request);
  }

  void amcl_pose_callback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
  {
    auto pose_ = msg->pose;
    current_pose_ = msg;
    pose_recieved_ = true;
  }
  bool isLocalized()
  {
    if (pose_recieved_ &&
      current_pose_->pose.covariance[cov_x_] < 0.25 &&
      current_pose_->pose.covariance[cov_y_] < 0.25 &&
      current_pose_->pose.covariance[cov_a_] < 0.25)
    {
      return true;
    }

    return false;
  }

  void disableSensor()
  {
    auto request_reset = std::make_shared<std_srvs::srv::Empty::Request>();
    while (!reset_world_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the reset service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "reset service not available, waiting again...");
    }
    auto disable_sensor = disable_sensor_->async_send_request(request_reset);
  }

  void enableSensor()
  {
    auto request_reset = std::make_shared<std_srvs::srv::Empty::Request>();
    while (!reset_world_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(get_logger(), "Interrupted while waiting for the reset service. Exiting.");
        rclcpp::shutdown();
        return;
      }
      RCLCPP_INFO(get_logger(), "reset service not available, waiting again...");
    }
    auto enable_sensor = enable_sensor_->async_send_request(request_reset);
  }

  void Demo()
  {
    demo = true;
    sendinitialPose();
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    this->sendGoal(2.00, -0.5);
  }
};

int main(int argc, char ** argv)
{
  try{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<Benchmark>();
    rclcpp::spin(node);
    rclcpp::shutdown();
  } catch (const rclcpp::exceptions::InvalidQosOverridesException & e) {
    // Log the error and handle the exception
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Caught exception: %s", e.what());
    rclcpp::shutdown();
    return 1; // error 
  }
  return 0;
}
