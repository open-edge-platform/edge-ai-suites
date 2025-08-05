// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation


#include <cmath>
#include <string>
#include <memory>
#include <iostream>
#include <fstream>
#include <vector>
#include <array>
#include <utility>
#include <variant>
#include "nav2_util/node_utils.hpp"
#include "its_planner/its_planner.hpp"
#include "its_planner/prm/prm.hpp"
#include "its_planner/its/its.hpp"
#include "its_planner/dubins/dubins.hpp"
#include "its_planner/path_utils/path_utils.hpp"

using std::ifstream;
using std::max;
using inav_util::Location;


namespace its_planner
{

void ITSPlanner::configure(
  const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
  std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
  std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros)
{
  node_ = parent.lock();
  name_ = name;
  tf_ = tf;
  costmap_ = costmap_ros->getCostmap();
  global_frame_ = costmap_ros->getGlobalFrameID();

  marker_pub_ = node_->create_publisher<visualization_msgs::msg::MarkerArray>(
    "milestones_marker",
    1);

  // Parameter initialization
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".interpolation_resolution", rclcpp::ParameterValue(0.05));
  node_->get_parameter(name_ + ".interpolation_resolution", interpolation_resolution_);
  if (interpolation_resolution_ <= 0.0) {interpolation_resolution_ = 0.05;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".roadmap", rclcpp::ParameterValue("PROBABLISTIC"));
  node_->get_parameter(name_ + ".roadmap", roadmap_);
  if (roadmap_ != "PROBABLISTIC" && roadmap_ != "DETERMINISTIC") {roadmap_ = "PROBABLISTIC";}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".n", rclcpp::ParameterValue(2));
  node_->get_parameter(name_ + ".n", n_);
  if (n_ < 0) {n_ = 2;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".w", rclcpp::ParameterValue(32));
  node_->get_parameter(name_ + ".w", w_);
  if (w_ < 0) {w_ = 32;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".h", rclcpp::ParameterValue(32));
  node_->get_parameter(name_ + ".h", h_);
  if (h_ < 0) {h_ = 32;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".build_road_map_once", rclcpp::ParameterValue(true));
  node_->get_parameter(name_ + ".build_road_map_once", build_road_map_once_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".enable_k", rclcpp::ParameterValue(false));
  node_->get_parameter(name_ + ".enable_k", enable_k_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".catmull_spline", rclcpp::ParameterValue(false));
  node_->get_parameter(name_ + ".catmull_spline", catmull_spline_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".dubins_path", rclcpp::ParameterValue(false));
  node_->get_parameter(name_ + ".dubins_path", use_dubins_path_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".turn_radius", rclcpp::ParameterValue(1.0));
  node_->get_parameter(name_ + ".turn_radius", turn_radius_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".robot_radius", rclcpp::ParameterValue(1.0));
  node_->get_parameter(name_ + ".robot_radius", robot_radius_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".yaw_tolerance", rclcpp::ParameterValue(1.0));
  node_->get_parameter(name_ + ".yaw_tolerance", yaw_tolerance_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".use_final_heading", rclcpp::ParameterValue(true));
  node_->get_parameter(name_ + ".use_final_heading", use_final_heading_);
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".smoothing_window", rclcpp::ParameterValue(15));
  node_->get_parameter(name_ + ".smoothing_window", smoothing_window_);
  if (smoothing_window_ < 0) {smoothing_window_ = 15;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".buffer_size", rclcpp::ParameterValue(20));
  node_->get_parameter(name_ + ".buffer_size", buffer_size_);
  if (buffer_size_ < 0) {buffer_size_ = 20;}
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".min_samples", rclcpp::ParameterValue(500));
  node_->get_parameter(name_ + ".min_samples", min_samples_);
  if (min_samples_ < 0) {min_samples_ = 500;}
}

void ITSPlanner::cleanup()
{
  RCLCPP_INFO(
    node_->get_logger(), "CleaningUp plugin %s",
    name_.c_str());
  // PubSub
  marker_pub_.reset();
}

void ITSPlanner::activate()
{
  RCLCPP_INFO(
    node_->get_logger(), "Activating plugin %s",
    name_.c_str());
  // Lifecycle publishers must be explicitly activated
  marker_pub_->on_activate();
}

void ITSPlanner::deactivate()
{
  RCLCPP_INFO(
    node_->get_logger(), "Deactivating plugin %s",
    name_.c_str());
  // Lifecycle publishers must be explicitly deactivated
  marker_pub_->on_deactivate();
}

nav_msgs::msg::Path ITSPlanner::createPlan(
  const geometry_msgs::msg::PoseStamped & start,
  const geometry_msgs::msg::PoseStamped & goal)
{
  std::unique_lock<nav2_costmap_2d::Costmap2D::mutex_t> lock(*(costmap_->getMutex()));
  nav2_costmap_2d::Costmap2D * costmap = costmap_;
  int height = costmap->getSizeInCellsX();
  int width = costmap->getSizeInCellsY();
  int count = 0;
  vector<vector<int>> inflation_map(height, vector<int>(width, 0));
  vector<vector<int>> costmap_2d = create2DCostmap(width, height, count, inflation_map);

  PRM road_map;
  const string filename = "road_map.txt";
  ifstream file;
  file.open(filename);
  int occupancy_count = (width * height) - count;
  int num_samples = max(
    road_map.getNumberofSamples(width, height, w_, h_, n_, occupancy_count),
    min_samples_);
  if (!file || build_road_map_once_) {
    generateRoadMap(num_samples, costmap_2d, inflation_map, filename, road_map);
    build_road_map_once_ = false;
  } else {  //  load roadmap from file
    try {
      std::ifstream infile(filename);
      boost::archive::text_iarchive archive(infile);
      archive >> road_map;
    } catch (const boost::archive::archive_exception & e) {
      RCLCPP_WARN(node_->get_logger(), "RoadMap is not valid, regenerating roadmap... %s");
      generateRoadMap(num_samples, costmap_2d, inflation_map, filename, road_map);
    }
  }
  file.close();

  nav_msgs::msg::Path global_path;

  // Draw milestones
  auto milestones = road_map.getMilestones();
  publishMilestoneMarkers(milestones);

  unsigned int sx, gx;
  unsigned int sy, gy;
  if (!costmap_->worldToMap(start.pose.position.x, start.pose.position.y, sx, sy)) {
    RCLCPP_WARN(node_->get_logger(), "The start pose sent to the planner is not valid %s");
    return global_path;
  }

  if (!costmap_->worldToMap(goal.pose.position.x, goal.pose.position.y, gx, gy)) {
    RCLCPP_WARN(node_->get_logger(), "The goal sent to the planner is not valid %s");
    return global_path;
  }

  if (costmap_2d[sx][sy] || costmap_2d[gx][gy]) {
    RCLCPP_WARN(node_->get_logger(), "The start/goal pose is an obstacle %s");
    return global_path;
  }

  MapLocation st, go;
  st = {static_cast<int>(sx), static_cast<int>(sy)};
  go = {static_cast<int>(gx), static_cast<int>(gy)};
  ITS its_plan(road_map);

  if (!its_plan.addStartGoalNode(costmap_2d, st, go)) {
    RCLCPP_WARN(node_->get_logger(), "The start/goal pose is not valid %s");
    return global_path;
  }

  // Headings used for ITS Dubins path
  double initialHeading, finalHeading;
  if (use_dubins_path_) {
    initialHeading =
      (start.pose.orientation.z > 0) ? 2 * acos(start.pose.orientation.w) : 2 * M_PI - 2 * acos(
      start.pose.orientation.w);
    finalHeading =
      (goal.pose.orientation.z > 0) ? 2 * acos(goal.pose.orientation.w) : 2 * M_PI - 2 * acos(
      goal.pose.orientation.w);
  }

  vector<pair<int, int>> path;
  vector<pair<double, double>> dubinsPath;
  if (use_dubins_path_) {
    double mapTurnRadius = worldToMapScale(turn_radius_);
    double mapRobotRadius = worldToMapScale(robot_radius_);
    // If for some reason the starting point is invalid, check nearby points for a valid starting spot
    if (costmap_2d[st.x][st.y]) {
      st = its_plan.nearbyFreeSpace(costmap_2d, st, mapRobotRadius);
    }
    dubinsPath =
      std::get<ITS::DUBINS>(
      its_plan.getITSPath(
        costmap_2d, st, go, 1000, enable_k_, true,
        mapTurnRadius, mapRobotRadius, initialHeading, finalHeading, yaw_tolerance_));
  } else {
    path = std::get<ITS::DEFAULT>(its_plan.getITSPath(costmap_2d, st, go, 1000, enable_k_));
  }

  if (path.empty() && dubinsPath.empty()) {
    RCLCPP_WARN(node_->get_logger(), "Path is not found %s");
    return global_path;
  }

  global_path.poses.clear();
  global_path.header.stamp = node_->now();
  global_path.header.frame_id = global_frame_;

  double stx_world;
  double sty_world;
  costmap_->mapToWorld((unsigned int)st.x, (unsigned int)st.y, stx_world, sty_world);

  path.erase(std::unique(path.begin(), path.end()), path.end());
  path.push_back({go.x, go.y});
  vector<pair<double, double>> planner_path;
  if (use_dubins_path_) {
    // Generate Dubins interpolated path
    double finalHeadingNew = (!use_final_heading_) ? -1.0 : finalHeading;
    RCLCPP_INFO(
      node_->get_logger(), "CURRENT POSE - X: %f Y: %f THETA: %f", start.pose.position.x, start.pose.position.y,
      initialHeading * 180 / M_PI);
    RCLCPP_INFO(
      node_->get_logger(), "GOAL POSE - X: %f Y: %f THETA: %f", goal.pose.position.x, goal.pose.position.y,
      finalHeading * 180 / M_PI);
    auto processedPath = processDubinsPath(dubinsPath, initialHeading, finalHeadingNew, costmap_2d);
    getGlobalPath(processedPath, global_path);
  } else if (!catmull_spline_ || path.size() < 4) {
    int start_index = 0;
    int end_index = path.size();
    auto linear_interpolated_path = linearInterpolate(
      path, start_index, end_index, stx_world,
      sty_world, interpolation_resolution_);
    vector<pair<double, double>> path_interpolated;
    for (int i = 0; i < linear_interpolated_path.size(); i++) {
      unsigned int cell_x, cell_y;
      costmap_->worldToMap(
        linear_interpolated_path[i].first, linear_interpolated_path[i].second,
        cell_x, cell_y);
      path_interpolated.push_back({cell_x, cell_y});
    }
    auto processedPath = processITSPath(path_interpolated, costmap_2d, inflation_map);
    planner_path = smoothingFilter(processedPath);
    getGlobalPath(planner_path, global_path);
  } else if (catmull_spline_) {
    int start_index = 0;
    int end_index = path.size();
    double interpolation_num = 0.25;
    auto high_res_path = linearInterpolate(
      path, start_index, end_index, stx_world,
      sty_world, interpolation_num);
    for (int i = 0; i < high_res_path.size() - 3; ++i) {
      int steps = std::hypot(
        high_res_path[i + 1].first - high_res_path[i + 2].first,
        high_res_path[i + 1].second - high_res_path[i + 2].second) /
        interpolation_resolution_;
      auto c = catmullRomInterpolate(
        high_res_path[i], high_res_path[i + 1], high_res_path[i + 2],
        high_res_path[i + 3], steps);
      getGlobalPath(c, global_path);
    }
  }

  global_path.poses.push_back(goal);
  return global_path;
}

vector<vector<int>> ITSPlanner::create2DCostmap(
  const int & width, const int & height, int count,
  vector<vector<int>> & inflation_map)
{
  vector<vector<int>> costmap_2d(height, vector<int>(width, 0));
  for (size_t x = 0; x < height; x++) {
    for (size_t y = 0; y < width; y++) {
      unsigned int cost = costmap_->getCost(x, y);
      costmap_2d[x][y] = 1;
      inflation_map[x][y] = cost;
      if (cost == nav2_costmap_2d::FREE_SPACE || cost <= 240) {  // 128 = MEDIUM_COST
        costmap_2d[x][y] = 0;
        count++;
      }
    }
  }
  return costmap_2d;
}

vector<pair<double, double>> ITSPlanner::linearInterpolate(
  vector<pair<int, int>> & path,
  const int & start_index,
  const int & end_index,
  const double & stx_world,
  const double & sty_world,
  const double & steps)
{
  vector<pair<double, double>> linear_interpolated_path;
  for (int i = start_index; i < end_index; ++i) {
    double pathi_x, pathi_y, pathi_m1_x, pathi_m1_y;
    costmap_->mapToWorld(
      (unsigned int)path[i].first, (unsigned int)path[i].second,
      pathi_x, pathi_y);
    double yaw = atan2(pathi_y - sty_world, pathi_x - stx_world);
    int total_number_of_loop = std::hypot(pathi_x - stx_world, pathi_y - sty_world) / steps;
    double x = stx_world;
    double y = sty_world;
    if (i > 0) {
      costmap_->mapToWorld(
        (unsigned int)path[i - 1].first, (unsigned int)path[i - 1].second,
        pathi_m1_x, pathi_m1_y);
      yaw = atan2(pathi_y - pathi_m1_y, pathi_x - pathi_m1_x);
      total_number_of_loop = std::hypot(pathi_x - pathi_m1_x, pathi_y - pathi_m1_y) / steps;
      x = pathi_m1_x;
      y = pathi_m1_y;
    }
    for (int i = 0; i < total_number_of_loop; i++) {
      x += steps * cos(yaw);
      y += steps * sin(yaw);
      linear_interpolated_path.push_back({x, y});
    }
  }
  return linear_interpolated_path;
}

// Converts a vector of pairs in Map coordinates to World coordinates
vector<pair<double, double>> ITSPlanner::pathToWorldCoords(vector<pair<double, double>> & path)
{
  double x1 = 1.0; double y1 = 1.0;
  double x2 = 0.0; double y2 = 5.0;
  double wx1, wy1, wx2, wy2;
  costmap_->mapToWorld(x1, y1, wx1, wy1);
  costmap_->mapToWorld(x2, y2, wx2, wy2);
  double mx = (wx2 - wx1) / (x2 - x1);
  double my = (wy2 - wy1) / (y2 - y1);
  double bx = wx2 - mx * x2;
  double by = wy2 - mx * y2;

  auto toWorld = [&](pair<double, double> coord) {
      double wx = mx * coord.first + bx;
      double wy = my * coord.second + by;
      pair<double, double> pair = {wx, wy};
      return pair;
    };


  vector<pair<double, double>> pathInWorldCoords(path.size());
  for (size_t i = 0; i < path.size(); i++) {
    pathInWorldCoords[i] = toWorld(path[i]);
  }
  return pathInWorldCoords;
}

// Scales a value in World scale to an equialent value in Map scale
double ITSPlanner::worldToMapScale(double num)
{
  double wx1 = 0; double wy1 = 0; double wx2 = 1; double wy2 = 0;
  unsigned int mx1, my1, mx2, my2;
  costmap_->worldToMap(wx1, wy1, mx1, my1);
  costmap_->worldToMap(wx2, wy2, mx2, my2);
  double scale = sqrt(pow(mx2 - mx1, 2) + pow(my2 - my1, 2));
  return num * scale;
}

// Process the ITS Dubins path to optimize and smoothen it out, removing redundant path steps
vector<pair<double, double>> ITSPlanner::processDubinsPath(
  vector<pair<double, double>> & dubinsPath,
  const double & initialHeading,
  const double & finalHeading,
  const vector<vector<int>> & costmap)
{
  // Calibrate the turn and robot radii into map coords
  double mapTurnRadius = worldToMapScale(turn_radius_);
  double mapRobotRadius = worldToMapScale(robot_radius_);

  // Interpolate the dubinsPath to add intermediate nodes along the path
  vector<std::array<double, 3>> pathWithHeadings;
  vector<int> nodeIndeces;
  interpolateItsPath(pathWithHeadings, dubinsPath, 30.0, initialHeading, finalHeading, nodeIndeces);

  // Get rid of redundant milestones
  vector<pair<double, double>> mapPath = removeRedundantNodes(
    pathWithHeadings, dubinsPath,
    nodeIndeces, mapTurnRadius,
    yaw_tolerance_, costmap);

  // Convert path from map to world coords
  vector<pair<double, double>> worldPath = pathToWorldCoords(mapPath);

  // Return processed path
  return worldPath;
}


void ITSPlanner::publishMilestoneMarkers(const vector<Pnode> & milestones)
{
  visualization_msgs::msg::Marker m;
  auto ma = std::make_unique<visualization_msgs::msg::MarkerArray>();  for (size_t i = 0;
    i < milestones.size(); i++)
  {
    m.header.frame_id = "map";
    m.type = m.SPHERE;
    m.action = m.ADD;
    m.id = milestones[i].id;
    m.pose.orientation.x = 0.0;
    m.pose.orientation.y = 0.0;
    m.pose.orientation.z = 0.0;
    m.pose.orientation.w = 1.0;
    m.scale.x = 0.025;
    m.scale.y = 0.025;
    m.scale.z = 0.025;
    m.color.a = 1.0;
    m.color.r = 0.0;
    m.color.g = 0.0;
    m.color.b = 1.0;
    m.points.clear();
    double x_m, y_m;
    costmap_->mapToWorld(
      (unsigned int)milestones[i].position.x,
      (unsigned int)milestones[i].position.y,
      x_m, y_m);
    m.pose.position.x = x_m;
    m.pose.position.y = y_m;
    m.pose.position.z = 0.0;
    ma->markers.push_back(m);
  }
  marker_pub_->publish(std::move(ma));
}

vector<pair<double, double>> ITSPlanner::smoothingFilter(
  const vector<pair<double, double>> &
  linear_interpolated_path)
{
  vector<pair<double, double>> smoothed_path;
  for (size_t i = smoothing_window_; i < linear_interpolated_path.size(); i++) {
    double x = 0.0;
    double y = 0.0;
    for (size_t j = 0; j < smoothing_window_; j++) {
      x += linear_interpolated_path[i - j].first;
      y += linear_interpolated_path[i - j].second;
    }
    smoothed_path.push_back({x / smoothing_window_, y / smoothing_window_});
  }
  return smoothed_path;
}

void ITSPlanner::getGlobalPath(
  const vector<pair<double, double>> & planner_path,
  nav_msgs::msg::Path & global_path)
{
  for (size_t i = 0; i < planner_path.size(); i++) {
    geometry_msgs::msg::PoseStamped pose;
    pose.pose.position.x = planner_path[i].first;
    pose.pose.position.y = planner_path[i].second;
    pose.pose.position.z = 0.0;
    pose.pose.orientation.x = 0.0;
    pose.pose.orientation.y = 0.0;
    pose.pose.orientation.z = 0.0;
    pose.pose.orientation.w = 1.0;
    pose.header.stamp = node_->now();
    pose.header.frame_id = global_frame_;
    global_path.poses.push_back(pose);
  }
}

// Implementing Catmull Rom based on:
// https://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
vector<pair<double, double>> ITSPlanner::catmullRomInterpolate(
  const pair<double, double> & P0,
  const pair<double, double> & P1,
  const pair<double, double> & P2,
  const pair<double, double> & P3,
  const int steps)
{
  if (steps < 4) {
    vector<pair<double, double>> t;
    t.push_back({P2.first, P2.second});
    return t;
  }
  double t0 = 0.0;
  double t1 = calculateT(t0, 0.5, P0, P1);
  double t2 = calculateT(t1, 0.5, P1, P2);
  double t3 = calculateT(t2, 0.5, P2, P3);
  vector<double> t = linspace(t1, t2, steps);

  vector<Location> A1, A2, A3, B1, B2;
  vector<pair<double, double>> C;
  for (size_t i = 0; i < t.size(); i++) {
    Location a;
    a.x = (t1 - t[i]) / (t1 - t0) * P0.first + (t[i] - t0) / (t1 - t0) * P1.first;
    a.y = (t1 - t[i]) / (t1 - t0) * P0.second + (t[i] - t0) / (t1 - t0) * P1.second;
    A1.push_back(a);
  }
  for (size_t i = 0; i < t.size(); i++) {
    Location a;
    a.x = ((t2 - t[i]) / (t2 - t1)) * P1.first + ((t[i] - t1) / (t2 - t1)) * P2.first;
    a.y = ((t2 - t[i]) / (t2 - t1)) * P1.second + ((t[i] - t1) / (t2 - t1)) * P2.second;
    A2.push_back(a);
  }
  for (size_t i = 0; i < t.size(); i++) {
    Location a;
    a.x = (t3 - t[i]) / (t3 - t2) * P2.first + (t[i] - t2) / (t3 - t2) * P3.first;
    a.y = (t3 - t[i]) / (t3 - t2) * P2.second + (t[i] - t2) / (t3 - t2) * P3.second;
    A3.push_back(a);
  }
  for (size_t i = 0; i < t.size(); i++) {
    Location b;
    b.x = (t2 - t[i]) / (t2 - t0) * A1[i].x + (t[i] - t0) / (t2 - t0) * A2[i].x;
    b.y = (t2 - t[i]) / (t2 - t0) * A1[i].y + (t[i] - t0) / (t2 - t0) * A2[i].y;
    B1.push_back(b);
  }
  for (size_t i = 0; i < t.size(); i++) {
    Location b;
    b.x = (t3 - t[i]) / (t3 - t1) * A2[i].x + (t[i] - t1) / (t3 - t1) * A3[i].x;
    b.y = (t3 - t[i]) / (t3 - t1) * A2[i].y + (t[i] - t1) / (t3 - t1) * A3[i].y;
    B2.push_back(b);
  }
  for (size_t i = 0; i < t.size(); i++) {
    pair<double, double> c;
    c.first = (t2 - t[i]) / (t2 - t1) * B1[i].x + (t[i] - t1) / (t2 - t1) * B2[i].x;
    c.second = (t2 - t[i]) / (t2 - t1) * B1[i].y + (t[i] - t1) / (t2 - t1) * B2[i].y;
    C.push_back(c);
  }
  return C;
}

double ITSPlanner::calculateT(
  double ti, double alpha,
  const pair<double, double> & pi,
  const pair<double, double> & pj)
{
  double xi = pi.first;
  double yi = pi.second;
  double xj = pj.first;
  double yj = pj.second;
  alpha = alpha / 2;
  return pow( ( pow((xj - xi), 2) + pow((yj - yi), 2) ), alpha) + ti;
}

vector<double> ITSPlanner::linspace(double a, double b, int steps)
{
  // create a vector of length num
  vector<double> v;
  for (size_t i = 0; i < steps; i++) {
    v.push_back(a + i * ( (b - a) / steps ));
  }
  return v;
}

void ITSPlanner::generateRoadMap(
  const int & num_samples,
  const vector<vector<int>> costmap_2d,
  const vector<vector<int>> inflation_map,
  const string & filename,
  PRM & road_map)
{
  RCLCPP_INFO(node_->get_logger(), "Building roadmap... %s");
  road_map.buildRoadMap(costmap_2d, num_samples, roadmap_, inflation_map, buffer_size_);
  std::ofstream outfile(filename);
  boost::archive::text_oarchive archive(outfile);
  archive << road_map;
}

vector<pair<double, double>> ITSPlanner::removeRedundantITSNodes(
  vector<std::array<double, 2>> & newPath,
  const vector<pair<double, double>> & originalPath,
  const vector<int> & nodeIndeces,
  const vector<vector<int>> & costmap)
{
  vector<pair<double, double>> path;
  vector<pair<double, double>> originalPathSeg;
  std::map<pair<int, int>, vector<pair<double, double>>> path_segments;

  int numNodes = newPath.size();
  int startNode = 0;
  int goalNode = numNodes - 1;
  int currNode = startNode;

  std::set<int> essentialNodeSet;
  vector<std::set<int>> childrenNodes(numNodes);

  // Compare nodes from start side to goal side to find potential shortcuts
  while (currNode != goalNode) {
    for (int compareNode = goalNode; compareNode > currNode; compareNode--) {
      auto q1 = newPath[currNode].data();
      auto q2 = newPath[compareNode].data();

      inav_util::MapLocation pt1 = {(int) q1[0], (int) q1[1]};
      inav_util::MapLocation pt2 = {(int) q2[0], (int) q2[1]};

      bool done = false;

      originalPathSeg = vector<pair<double, double>>(
        originalPath.begin() + nodeIndeces[currNode],
        originalPath.begin() + nodeIndeces[compareNode]);

      vector<pair<double, double>> checkedPath;

      if (!isITSCollision(costmap, pt1, pt2, 1.0, checkedPath)) {
        // Don't consider this a shortcut if it's the same or longer than the original path
        if ((int) originalPathSeg.size() - (int) checkedPath.size() < 1) {
          essentialNodeSet.insert(currNode);
          currNode++;
          break;
        } else {
          // It's a shortcut!
          path_segments[{currNode, compareNode}] = checkedPath;
          done = true;
        }
      } else if (compareNode == currNode + 1) {
        essentialNodeSet.insert(currNode);
        currNode++;
        break;
      }

      if (done) {
        essentialNodeSet.insert(currNode);
        childrenNodes[currNode].insert(compareNode);
        currNode = compareNode;
        break;
      }
    }
  }

  essentialNodeSet.insert(goalNode);

  // Postprocessing
  vector<int> essentialNodes(essentialNodeSet.begin(), essentialNodeSet.end());
  if (essentialNodes.size() == 0) {return path;}
  for (size_t i = 0; i < essentialNodes.size() - 1; i++) {
    childrenNodes[essentialNodes[i]].insert(essentialNodes[i + 1]);
  }

  for (size_t i = 0; i < essentialNodes.size() - 1; i++) {
    int curr = essentialNodes[i];
    int next = essentialNodes[i + 1];
    vector<pair<double, double>> pathSeg;
    if (path_segments.find({curr, next}) == path_segments.end()) {
      pathSeg = vector<pair<double, double>>(
        originalPath.begin() + nodeIndeces[curr], originalPath.begin() + nodeIndeces[next]);
    } else {
      pathSeg = path_segments[{essentialNodes[i], essentialNodes[i + 1]}];
    }
    path.insert(path.end(), pathSeg.begin(), pathSeg.end());
  }
  return path;
}

bool
ITSPlanner::isITSCollision(
  const vector<vector<int>> & costmap_2d, const MapLocation & p1,
  const MapLocation & p2, const double & step_size, vector<pair<double, double>> & checkedPath)
{
  double yaw = atan2f(p2.y - p1.y, p2.x - p1.x);
  int D = sqrt(inav_util::euclideanDistanceSq(p1, p2));
  int num_steps = D / step_size;
  double x = p1.x;
  double y = p1.y;
  for (int i = 0; i < num_steps; i++) {
    x += step_size * cos(yaw);
    y += step_size * sin(yaw);
    checkedPath.push_back({x, y});
    if (costmap_2d[floor(x)][floor(y)] || costmap_2d[ceil(x)][ceil(y)]) {
      return true;
    }
  }
  return false;
}

// Process the ITS path to optimize and smoothen it out, removing redundant path steps
vector<pair<double, double>> ITSPlanner::processITSPath(
  vector<pair<double, double>> & originalPath,
  const vector<vector<int>> & costmap, vector<vector<int>> & inflation_map)
{
  // Interpolate to add intermediate nodes along the path
  vector<std::array<double, 2>> newPath;
  vector<int> nodeIndeces;
  interpolateItsPathITS(newPath, originalPath, 30.0, nodeIndeces);

  // Get rid of redundant milestones
  vector<pair<double, double>> mapPath = removeRedundantITSNodes(
    newPath, originalPath,
    nodeIndeces, costmap);

  // Convert path from map to world coords
  vector<pair<double, double>> worldPath = pathToWorldCoords(mapPath);

  // Return processed path
  return worldPath;

}

void ITSPlanner::interpolateItsPathITS(
  vector<std::array<double, 2>> & newPath,
  vector<pair<double, double>> & oldPath,
  const int & numSteps,
  vector<int> & nodeIndeces)
{
  if (oldPath.empty()) {return;}
  double nodeStepSize = (double) oldPath.size() / (double) numSteps;
  std::array<double, 2> startNode = {oldPath[0].first, oldPath[0].second};
  std::array<double, 2> goalNode = {oldPath.back().first, oldPath.back().second};
  newPath = {startNode};
  nodeIndeces = {0};
  auto interNodes = getIntermediateNodesITS(oldPath, 1.0, nodeStepSize, nodeIndeces);
  newPath.insert(newPath.end(), interNodes.begin(), interNodes.end());
  newPath.push_back(goalNode);
  nodeIndeces.push_back(oldPath.size() - 1);
}

vector<std::array<double, 2>> ITSPlanner::getIntermediateNodesITS(
  vector<pair<double, double>> & path,
  const double & pathStepSize,
  const double & nodeStepSize,
  vector<int> & nodeIndeces)
{
  vector<std::array<double, 2>> interNodes;
  if (path.size() == 0) {return interNodes;}

  double distCovered = 0;
  double heading;
  int stoppingPt = nodeStepSize / pathStepSize;
  stoppingPt = (stoppingPt > path.size()) ? 0 : stoppingPt;
  for (size_t i = 0; i < path.size() - stoppingPt; i++) {
    distCovered += pathStepSize;
    if (distCovered >= nodeStepSize) {
      interNodes.push_back({path[i].first, path[i].second});
      nodeIndeces.push_back(i);
      distCovered = 0;
    }
  }
  return interNodes;
}
}  // namespace its_planner

#include "pluginlib/class_list_macros.hpp"
PLUGINLIB_EXPORT_CLASS(its_planner::ITSPlanner, nav2_core::GlobalPlanner)
