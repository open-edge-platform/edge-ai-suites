// SPDX-License-Identifier: Apache-2.0
/*
Copyright (C) 2025 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*/

#ifndef MapEninge_H
#define MapEninge_H
#include <memory>
#include <vector>

#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav2_costmap_2d/costmap_2d.hpp"

#define MOVEMENTS_COUNT      4
#define GRID_DIRECTION_COUNT 2*MOVEMENTS_COUNT

class MapEngine
{
public:
  MapEngine(bool useCostMap, double robotRadius);
  ~MapEngine();
  bool init();
  void mapCallback(const nav_msgs::msg::OccupancyGrid::SharedPtr map);
  bool setRobotPose(const geometry_msgs::msg::PoseStamped pose);
  double getUnexploredPrstg() const;
  void checkMapCoverage();
  bool getNextGoalCoord(double &x, double &y);
  void resetVisitedMap();
  bool shouldReset();
  bool isMapValid();

private:
  uint8_t moveToNearestUnknownCell(uint32_t &i, uint32_t &j, int thrI, int thrJ);
  void moveToFarestFreeCell(uint32_t &i, uint32_t &j, int thrI, int thrJ);
  bool exploreDirections(double &x, double &y, bool unknownArea);
  bool shouldMove(uint32_t targetI, uint32_t targetJ);
  bool getNextFreeCell(uint32_t &i, uint32_t &j);
  bool checkAreaForValue(uint32_t i, uint32_t j, uint32_t range, uint8_t value);
  bool isWithinCostmap(uint32_t i, uint32_t j, int thrI, int thrJ);
  void printMap();
  void updateMapInfo();

  nav_msgs::msg::OccupancyGrid::SharedPtr map_;
  nav2_costmap_2d::Costmap2D costmap_;
  geometry_msgs::msg::PoseStamped robotPose_;
  uint32_t robotIMapIndex_, robotJMapIndex_;
  double unexploredPrctg_;
  double freePrctg_;
  double occupiedPrctg_;
  double robotRadius_;
  uint8_t coordOffset_, robotRadiusCells_;
  std::vector<bool> visitedMap_;
  uint32_t logCounter;
  uint32_t logRate_;
  uint16_t mapPrintCounter_;
  bool useCostMap_, resetDone_, storeMapToFile_;
  std::string movMethodNames_[MOVEMENTS_COUNT] = {"right", "up", "left", "down"};
  /* (0, 1) -right, (0, -1) - left (-1, 0) - up (1, 0) - down*/
  int directions_[GRID_DIRECTION_COUNT] = {0, 1, -1, 0, 0, -1, 1, 0}; 
};

#endif
