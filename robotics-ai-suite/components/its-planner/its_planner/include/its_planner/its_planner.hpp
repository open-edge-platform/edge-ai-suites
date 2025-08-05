// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#ifndef ITS_PLANNER__ITS_PLANNER_HPP_
#define ITS_PLANNER__ITS_PLANNER_HPP_

#include <string>
#include <memory>
#include <utility>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"

#include "nav2_core/global_planner.hpp"
#include "nav_msgs/msg/path.hpp"
#include "nav2_util/lifecycle_node.hpp"
#include "nav2_util/costmap.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

#include "../include/its_planner/path_utils/path_utils.hpp"
#include "../include/its_planner/prm/prm.hpp"
#include "../include/its_planner/its/its.hpp"

using rclcpp_lifecycle::LifecyclePublisher;

namespace its_planner
{

class ITSPlanner : public nav2_core::GlobalPlanner
{
public:
  ITSPlanner() = default;
  ~ITSPlanner() = default;

  // plugin configure
  void configure(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
    std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros) override;

  // plugin cleanup
  void cleanup() override;

  // plugin activate
  void activate() override;

  // plugin deactivate
  void deactivate() override;

  // This method creates path for given start and goal pose.
  nav_msgs::msg::Path createPlan(
    const geometry_msgs::msg::PoseStamped & start,
    const geometry_msgs::msg::PoseStamped & goal) override;

private:
  // TF buffer
  std::shared_ptr<tf2_ros::Buffer> tf_;

  std::shared_ptr<LifecyclePublisher<visualization_msgs::msg::MarkerArray>> marker_pub_;

  // node ptr
  nav2_util::LifecycleNode::SharedPtr node_;

  // Global Costmap
  nav2_costmap_2d::Costmap2D * costmap_;

  // The global frame of the costmap
  std::string global_frame_, name_;

  double interpolation_resolution_;
  std::string roadmap_;
  int w_, h_, n_;
  bool build_road_map_once_;
  bool enable_k_;
  bool catmull_spline_;
  int smoothing_window_;
  int buffer_size_;
  int min_samples_;
  // Dubins specific
  bool use_dubins_path_;
  double turn_radius_;
  double robot_radius_;
  double yaw_tolerance_;
  bool use_final_heading_;
  vector<pair<double, double>> catmullRomInterpolate(
    const pair<double, double> & P0,
    const pair<double, double> & P1,
    const pair<double, double> & P2,
    const pair<double, double> & P3,
    const int steps);

  double calculateT(
    double ti, double alpha,
    const pair<double, double> & pi,
    const pair<double, double> & pj);

  vector<double> linspace(double a, double b, int steps);
  vector<vector<int>> create2DCostmap(
    const int & width, const int & height, int count,
    vector<vector<int>> & inflation_map);
  vector<pair<double, double>> linearInterpolate(
    vector<pair<int, int>> & path,
    const int & start_index,
    const int & end_index,
    const double & stx_world,
    const double & sty_world,
    const double & steps);

  // Converts a vector of pairs in Map coordinates to World coordinates
  vector<pair<double, double>> pathToWorldCoords(vector<pair<double, double>> & path);

  // Scales a value in World scale to an equialent value in Map scale
  double worldToMapScale(double num);

  // Process the ITS Dubins path to optimize and smoothen it out, removing redundant path steps
  vector<pair<double, double>> processDubinsPath(
    vector<pair<double, double>> & dubinsPath,
    const double & initialHeading,
    const double & finalHeading,
    const vector<vector<int>> & costmap);

  vector<pair<double, double>> smoothingFilter(
    const vector<pair<double, double>> &
    linear_interpolated_path);
  void getGlobalPath(
    const vector<pair<double, double>> & planner_path,
    nav_msgs::msg::Path & global_path);
  void publishMilestoneMarkers(const vector<Pnode> & milestones);
  void generateRoadMap(
    const int & num_samples,
    const vector<vector<int>> costmap_2d,
    const vector<vector<int>> inflation_map,
    const string & filename,
    PRM & road_map);
  vector<pair<double, double>> removeRedundantITSNodes(
    vector<std::array<double, 2>> & newPath,
    const vector<pair<double, double>> & originalPath,
    const vector<int> & nodeIndeces,
    const vector<vector<int>> & costmap);
  bool isITSCollision(
    const vector<vector<int>> & costmap_2d, const MapLocation & p1,
    const MapLocation & p2, const double & step_size, vector<pair<double, double>> & checkedPath);

  void interpolateItsPathITS(
    vector<std::array<double, 2>> & newPath,
    vector<pair<double, double>> & oldPath,
    const int & numSteps,
    vector<int> & nodeIndeces);

  vector<std::array<double, 2>> getIntermediateNodesITS(
    vector<pair<double, double>> & path,
    const double & pathStepSize,
    const double & nodeStepSize,
    vector<int> & nodeIndeces);

  vector<pair<double, double>> processITSPath(
    vector<pair<double, double>> & originalPath,
    const vector<vector<int>> & costmap,
    vector<vector<int>> & inflation_map);

};

}  // namespace its_planner

#endif  // ITS_PLANNER__ITS_PLANNER_HPP_
