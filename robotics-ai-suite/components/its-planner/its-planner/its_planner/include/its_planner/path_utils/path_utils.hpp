// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#ifndef ITS_PLANNER__PATH_UTILS__PATH_UTILS_HPP_
#define ITS_PLANNER__PATH_UTILS__PATH_UTILS_HPP_

#include <vector>
#include <utility>

using std::vector;
using std::pair;

namespace inav_util
{

struct MapLocation
{
  int x;
  int y;
};


struct Location
{
  float x;
  float y;
};

struct Rank
{
  Location position;
  double sigma;
  double weight;
};

struct Costs
{
  double f, g, h;
};

template<typename COST>
struct Node
{
  MapLocation parent;
  int parent_id;
  COST cost;
  explicit Node(COST cost)
  {
    this->parent = {-1, -1};
    this->parent_id = -1;
    this->cost = cost;
  }
  Node(MapLocation parent, COST cost)
  {
    this->parent = parent;
    this->cost = cost;
  }
};

bool isValid(int row, int col, int ROW, int COL);
bool isGoalReached(int row, int col, MapLocation goal);
double euclideanDistanceSq(MapLocation p1, MapLocation p2);
bool isNearWithin(MapLocation p1, MapLocation p2, double dist);

template<typename T>
vector<pair<int, int>>
getPath(T & nodes, MapLocation & start, MapLocation & goal)
{
  int row = goal.x;
  int col = goal.y;
  vector<pair<int, int>> path;
  while (!(nodes[row][col].parent.x == row && nodes[row][col].parent.y == col )) {
    path.push_back({row, col});
    int temp_row = nodes[row][col].parent.x;
    int temp_col = nodes[row][col].parent.y;
    row = temp_row;
    col = temp_col;
  }
  return path;
}

}  // namespace inav_util
#endif  // ITS_PLANNER__PATH_UTILS__PATH_UTILS_HPP_
