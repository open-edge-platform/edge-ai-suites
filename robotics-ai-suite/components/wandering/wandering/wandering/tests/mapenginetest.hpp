// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#ifndef WANDERING__TESTS__MAPENGINETEST_HPP_
#define WANDERING__TESTS__MAPENGINETEST_HPP_

#include <gtest/gtest.h>

#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "MapEngine.h"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav2_costmap_2d/costmap_2d.hpp"
#include "nav_msgs/msg/map_meta_data.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "std_msgs/msg/header.hpp"
#include "utils.h"  // NOLINT

// Taken from gazebo world simulation
#define GAZEBO_MAP_RESOLUTION 0.05
#define GAZEBO_ORIGIN_X -3.453418
#define GAZEBO_ORIGIN_Y -3.122562
#define GAZEBO_ROBOT_RADIUS 0.22
#define GAZEBO_ROBOT_INITIALPOSE_X -1.999700
#define GAZEBO_ROBOT_INITIALPOSE_Y -0.500000
#define GAZEBO_ROBOT_INITIALORIENT 0.999995

#define VISITED_THRSHLD 0.25

using std::cerr;
using std::cout;
using std::endl;
using std::ifstream;
using std::stoi;
using std::string;
using std::vector;

using std::filesystem::path;

static const std::array<uint8_t, 256> costs_mapping_test = occup_cost_mapping();

static bool loadMapFromFile(const string filePath, nav_msgs::msg::OccupancyGrid & map)
{
  string line;
  uint32_t beg_offset = 6;
  uint32_t num_offset = 4;
  int val = -2;
  uint32_t rows = 0;
  uint32_t cols = 0;
  vector<int> values;
  ifstream myfile(filePath);
  if (myfile.is_open()) {
    uint32_t lineOffset = beg_offset;
    while (getline(myfile, line)) {
      cols = 0;
      while (lineOffset < line.length()) {
        val = stoi(line.substr(lineOffset, num_offset));
        lineOffset += num_offset;
        cols++;
        values.push_back(val);
      }
      lineOffset = beg_offset;
      rows++;
    }
    myfile.close();
  } else {
    return false;
  }

  map.info.resolution = GAZEBO_MAP_RESOLUTION;
  map.info.width = cols;
  map.info.height = rows;
  map.info.origin.position.x = GAZEBO_ORIGIN_X;
  map.info.origin.position.y = GAZEBO_ORIGIN_Y;
  uint32_t mapSize = map.info.width * map.info.height;
  map.data.resize(mapSize, -1);
  if (mapSize != values.size()) {
    return false;
  }

  for (uint32_t i = 0; i < mapSize; i++) {
    map.data[i] = values[i];
  }

  return true;
}

static void convertToCostmap(
  const nav_msgs::msg::OccupancyGrid & mapGrid, nav2_costmap_2d::Costmap2D & costmapGrid)
{
  costmapGrid.resizeMap(
    mapGrid.info.width, mapGrid.info.height, mapGrid.info.resolution,
    mapGrid.info.origin.position.x, mapGrid.info.origin.position.y);

  uint8_t * costmap_data = costmapGrid.getCharMap();
  uint32_t mapSize = mapGrid.info.width * mapGrid.info.height;
  for (uint32_t i = 0; i < mapSize; i++) {
    uint8_t cell_cost = static_cast<uint8_t>(mapGrid.data[i]);
    costmap_data[i] = costs_mapping_test[cell_cost];
  }
}

class MapEngineTest : public ::testing::Test
{
public:
  MapEngineTest()
  {
    mapGrid_ = std::make_shared<nav_msgs::msg::OccupancyGrid>();
    this->visitedPlaces_ = 0;
    this->costmapGrid_ = nav2_costmap_2d::Costmap2D();
    this->notCountableArea_ = 0;
    this->shouldVisitPointsCount_ = 0;
    this->useCostMap_ = false;
  }

  ~MapEngineTest() {}

  void resetVisited()
  {
    this->mapEngine_->resetVisitedMap();
    this->visitedPlaces_ = 0;
    this->visitedPoints_.clear();
  }

  bool isVisited(double x, double y)
  {
    for (auto & visitedPoint : this->visitedPoints_) {
      double x_diff = fabs(x - visitedPoint.pose.position.x);
      double y_diff = fabs(y - visitedPoint.pose.position.y);

      if (x_diff < GAZEBO_ROBOT_RADIUS && y_diff < GAZEBO_ROBOT_RADIUS) {
        return true;
      }
    }

    return false;
  }

  bool testInit(string filePath, bool costMap)
  {
    nav_msgs::msg::OccupancyGrid & map = *mapGrid_;
    if (!loadMapFromFile(filePath, map)) {
      return false;
    }

    uint64_t mapSize = map.info.width * map.info.height;
    uint32_t occupiedCounter = 0;
    uint32_t unknownCounter = 0;
    for (uint64_t i = 0; i < mapSize; i++) {
      if (map.data[i] == -1) {
        unknownCounter++;
      } else if (map.data[i] == 100) {
        occupiedCounter++;
      }
    }

    this->notCountableArea_ =
      static_cast<double>(occupiedCounter + unknownCounter) / static_cast<double>(mapSize);
    convertToCostmap(map, this->costmapGrid_);
    this->useCostMap_ = costMap;
    cout << "MapEngineTest Costmap W " << this->costmapGrid_.getSizeInCellsX() << " H "
         << this->costmapGrid_.getSizeInCellsY() << endl;
    cout << "MapEngineTest Costmap " << this->costmapGrid_.getSizeInMetersX() << "x"
         << this->costmapGrid_.getSizeInMetersY() << "m" << endl;
    cout << "Area which will not be visited " << (this->notCountableArea_ * 100.0) << "%" << endl;
    double surfaceSize =
      this->costmapGrid_.getSizeInMetersX() * this->costmapGrid_.getSizeInMetersY();
    double robotSurface = pow(GAZEBO_ROBOT_RADIUS * 2, 2);
    // Moving to every single point could be long so we add some threshold
    this->shouldVisitPointsCount_ =
      uint32_t((1.0 - this->notCountableArea_ - VISITED_THRSHLD) * (surfaceSize / robotSurface));
    cout << "Based on map surface size of " << surfaceSize << "m2 and robot size of "
         << robotSurface << "m2 "
         << "there should be " << this->shouldVisitPointsCount_ << " visited points on the map "
         << endl;
    this->mapEngine_ = std::make_shared<MapEngine>(costMap, GAZEBO_ROBOT_RADIUS);
    this->mapEngine_->mapCallback(this->mapGrid_);
    this->mapEngine_->checkMapCoverage();
    geometry_msgs::msg::PoseStamped initialPose;
    initialPose.pose.position.x = GAZEBO_ROBOT_INITIALPOSE_X;
    initialPose.pose.position.y = GAZEBO_ROBOT_INITIALPOSE_Y;
    this->mapEngine_->setRobotPose(initialPose);
    this->visitedPoints_.push_back(initialPose);

    return true;
  }

  bool testCoord()
  {
    double x, y;
    while (this->mapEngine_->getNextGoalCoord(x, y)) {
      if (
        x < this->costmapGrid_.getOriginX() ||
        x > (this->costmapGrid_.getSizeInMetersX() - this->costmapGrid_.getOriginX())) {
        cerr << "X coord " << x << " out of the bounds!" << endl;
        return false;
      }

      if (
        y < this->costmapGrid_.getOriginY() ||
        y > (this->costmapGrid_.getSizeInMetersY() - this->costmapGrid_.getOriginY())) {
        cerr << "Y coord " << y << " out of the bounds!" << endl;
        return false;
      }

      if (this->isVisited(x, y)) {
        cerr << "Coords (" << x << ", " << y << ") already visited" << endl;
        continue;
      }

      if (this->useCostMap_) {
        uint32_t i, j;
        this->costmapGrid_.worldToMap(x, y, i, j);
        uint8_t * costmap_data = this->costmapGrid_.getCharMap();
        uint32_t index = this->costmapGrid_.getIndex(i, j);
        if (costmap_data[index] > nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE) {
          cerr << "Got coord (" << i << ", " << j << ") with cost: " << int(costmap_data[index])
               << endl;
          return false;
        }
      }

      geometry_msgs::msg::PoseStamped pose;
      pose.pose.position.x = x;
      pose.pose.position.y = y;
      this->mapEngine_->setRobotPose(pose);
      this->visitedPoints_.push_back(pose);
      this->visitedPlaces_++;
    }

    cout << "Visited " << this->visitedPlaces_ << " compared to " << shouldVisitPointsCount_
         << endl;
    if (this->visitedPlaces_ < shouldVisitPointsCount_) {
      return false;
    }

    return true;
  }

private:
  nav_msgs::msg::OccupancyGrid::SharedPtr mapGrid_;
  std::shared_ptr<MapEngine> mapEngine_;
  nav2_costmap_2d::Costmap2D costmapGrid_;
  vector<geometry_msgs::msg::PoseStamped> visitedPoints_;
  double notCountableArea_;
  uint32_t shouldVisitPointsCount_;
  bool useCostMap_;
  uint32_t visitedPlaces_;
};

#endif  // WANDERING__TESTS__MAPENGINETEST_HPP_
