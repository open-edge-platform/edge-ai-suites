// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation


#include <vector>
#include "../include/its_planner/path_utils/path_utils.hpp"

namespace inav_util
{

bool
isValid(int row, int col, int ROW, int COL)
{
  return (row >= 0) && (row < ROW) && (col >= 0) && (col < COL);
}

bool
isGoalReached(int row, int col, MapLocation goal)
{
  return (row == goal.x && col == goal.y) ? true : false;
}

double
euclideanDistanceSq(MapLocation p1, MapLocation p2)
{
  return (p1.x - p2.x) * (p1.x - p2.x) + (p1.y - p2.y) * (p1.y - p2.y);
}

// Checks if two points `p1` and `p2` are nearby within a distance `dist`
bool
isNearWithin(MapLocation p1, MapLocation p2, double dist)
{
  auto ED = euclideanDistanceSq(p1, p2);
  return ED <= dist * dist;
}

}  // namespace inav_util
