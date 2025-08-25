// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#include <limits.h>  // INT_MAX
#include <float.h>  // FLT_MAX
#include <vector>
#include <set>
#include <iostream>
#include <algorithm>  // reverse
#include <queue>
#include <stack>
#include <string>
#include <utility>
#include <random>

#include "../include/its_planner/prm/prm.hpp"

using std::min;
using std::set;
using std::priority_queue;
using std::make_pair;

const int MAX_NEIGHBORS = 50;

PRM::PRM()
{
  start_id_ = milestones_.size();
  goal_id_ = start_id_ + 1;
}

PRM::~PRM()
{
}

bool operator==(Pnode const & lhs, Pnode const & rhs)
{
  return lhs.id == rhs.id;
}

bool operator<(Pnode const & lhs, Pnode const & rhs)
{
  return lhs.id < rhs.id;
}

void
PRM::buildRoadMap(
  const vector<vector<int>> & costmap_2d,
  const int num,
  string plan,
  const vector<vector<int>> & inflation_map,
  const int & buffer_size)
{
  pair<int, int> map_size = {costmap_2d.size(), costmap_2d[0].size()};
  auto milestones = generateMilestones(map_size, costmap_2d, inflation_map, num, plan, buffer_size);
  milestones_ = milestones;
  generateGraph(costmap_2d, milestones, 1.0);
  buildAdjacencyList();
}
// 1. Sample configurations by picking coordinates at random
// 2. Test sampled configurations for collision
// 3. Keep collision-free configurations as milestones
vector<Pnode>
PRM::generateMilestones(
  const pair<int, int> map_size,
  const vector<vector<int>> & costmap_2d,
  const vector<vector<int>> & inflation_map,
  const int n,
  const string plan,
  const int & buffer_size)
{
  int count = 0;
  vector<Pnode> milestones;
  int id = 0;
  vector<vector<bool>> visited(map_size.first, vector<bool>(map_size.second, false));
  std::random_device rd;
  while (count < n) {
    if (plan == "PROBABLISTIC") {
      std::uniform_int_distribution<int> dist_one(0, map_size.first - 1);
      std::uniform_int_distribution<int> dist_two(0, map_size.second - 1);
      MapLocation rand_pos = {dist_one(rd), dist_two(rd)};
      MapLocation temp_pos = rand_pos;
      if (!costmap_2d[rand_pos.x][rand_pos.y] && !visited[rand_pos.x][rand_pos.y]) {
        visited[rand_pos.x][rand_pos.y] = true;
        getMinCostPoint(
          map_size,
          costmap_2d,
          inflation_map,
          buffer_size,
          rand_pos,
          temp_pos);
        if (!visited[temp_pos.x][temp_pos.y]) {
          milestones.push_back({temp_pos, id});
          visited[temp_pos.x][temp_pos.y] = true;
          id++;
        }
        count++;
      }
    } else if (plan == "DETERMINISTIC") {
      int x = haltonSequence(count, 2) * map_size.first;
      int y = haltonSequence(count, 3) * map_size.second;
      if (!costmap_2d[x][y] && !visited[x][y]) {
        visited[x][y] = true;
        MapLocation temp_pos = {x, y};
        getMinCostPoint(
          map_size,
          costmap_2d,
          inflation_map,
          buffer_size,
          {x, y},
          temp_pos);
        if (!visited[temp_pos.x][temp_pos.y]) {
          visited[temp_pos.x][temp_pos.y] = true;
          milestones.push_back({temp_pos, id});
          id++;
        }
      }
      count++;
    }
  }
  num_vertices_ = milestones.size();
  return milestones;
}

// 4. Each milestone is linked by straight paths to its nearest neighbors
// 5. Keep the collision-free links to form the PRM
void
PRM::generateGraph(
  const vector<vector<int>> & costmap_2d,
  const vector<Pnode> & milestones, const double & step_size)
{
  for (int i = 0; i < milestones.size(); i++) {
    int s = milestones_.size() - 1;
    Pnode u = milestones[i];
    um_node_[u.id] = u.position;
    vector<Pnode> kpoints = kNearestNeighbor(u, milestones, min(s, MAX_NEIGHBORS));
    for (int j = 0; j < kpoints.size(); j++) {
      Pnode v = kpoints[j];
      if (!isCollision(costmap_2d, u.position, v.position, step_size)) {
        if (u.id <= v.id) {
          continue;                 // Prevent duplication of edges
        }
        vertices_.push_back({u, v});
      }
    }
  }
}

bool
PRM::addStartGoalNode(
  const vector<vector<int>> & costmap_2d, const MapLocation & start,
  const MapLocation & goal)
{
  start_id_ = milestones_.size();
  goal_id_ = start_id_ + 1;
  milestones_.push_back({start, start_id_});
  milestones_.push_back({goal, goal_id_});
  num_vertices_ = milestones_.size();

  adj_list_.resize(num_vertices_);
  int s = milestones_.size() - 1;
  vector<Pnode> kpoints = kNearestNeighbor(
    milestones_[start_id_], milestones_,
    min(MAX_NEIGHBORS, s));
  Pnode node_u = milestones_[start_id_];
  int start_neighbor_count = 0;
  for (int j = 0; j < kpoints.size(); j++) {
    if (!isCollision(costmap_2d, milestones_[start_id_].position, kpoints[j].position, 1)) {
      Pnode u = node_u;
      Pnode v = {kpoints[j].position, kpoints[j].id};
      vertices_.push_back({u, v});
      um_node_[u.id] = u.position;
      adj_list_[start_id_].push_back(v);
      adj_list_[v.id].push_back(u);
      start_neighbor_count++;
    }
  }
  if (start_neighbor_count == 0) {return false;}

  vector<Pnode> kpointsg = kNearestNeighbor(
    milestones_[goal_id_], milestones_,
    min(MAX_NEIGHBORS, s));
  Pnode node_ug = milestones_[goal_id_];
  int goal_neighbor_count = 0;
  for (int j = 0; j < kpointsg.size(); j++) {
    if (!isCollision(costmap_2d, milestones_[goal_id_].position, kpointsg[j].position, 1)) {
      Pnode u = node_ug;
      Pnode v = {kpointsg[j].position, kpointsg[j].id};
      vertices_.push_back({u, v});
      um_node_[u.id] = u.position;
      adj_list_[goal_id_].push_back(v);
      adj_list_[v.id].push_back(u);
      goal_neighbor_count++;
    }
  }
  if (goal_neighbor_count == 0) {return false;}

  for (auto & list : adj_list_) {
    sort(list.begin(), list.end());
    list.erase(unique(list.begin(), list.end()), list.end());
  }

  return true;
}

vector<Pnode>
PRM::getMilestones()
{
  return milestones_;
}

double
PRM::haltonSequence(int index, int base)
{
  double f = 1.0;
  double r = 0.0;
  while (index > 0) {
    f = f / base;
    r = r + f * (index % base);
    index = index / base;
  }
  return r;
}


vector<Pnode>
PRM::kNearestNeighbor(const Pnode & p1, const vector<Pnode> & points, int K)
{
  vector<Pnode> kpoints;
  priority_queue<pair<double, int>> max_heap;
  for (int i = 0; i < points.size(); i++) {
    if (p1.id != points[i].id) {
      double dist = inav_util::euclideanDistanceSq(p1.position, points[i].position);
      max_heap.push(make_pair(dist, i));
      if (max_heap.size() > K) {
        max_heap.pop();
      }
    }
  }
  while (!max_heap.empty()) {
    kpoints.emplace_back(points[max_heap.top().second]);
    max_heap.pop();
  }
  return kpoints;
}

bool
PRM::isCollision(
  const vector<vector<int>> & costmap_2d, const MapLocation & p1,
  const MapLocation & p2, const double & step_size)
{
  double yaw = atan2f(p2.y - p1.y, p2.x - p1.x);
  int D = sqrt(inav_util::euclideanDistanceSq(p1, p2));
  int num_steps = D / step_size;
  double x = p1.x;
  double y = p1.y;
  for (int i = 0; i < num_steps; i++) {
    x += step_size * cos(yaw);
    y += step_size * sin(yaw);
    if (costmap_2d[floor(x)][floor(y)] || costmap_2d[ceil(x)][ceil(y)]) {
      return true;
    }
  }
  return false;
}

void PRM::buildAdjacencyList()
{
  adj_list_.resize(num_vertices_);
  for (const auto & it : vertices_) {
    Pnode u = it.first;
    Pnode v = it.second;
    adj_list_[u.id].push_back(v);
    adj_list_[v.id].push_back(u);
  }
}
vector<pair<Pnode, int>> PRM::getRanks()
{
  if (ranks_.size() > 0) {return ranks_;}
  ranks_.resize(num_vertices_);
  for (u_int i = 0; i < adj_list_.size(); i++) {
    ranks_[i] = {milestones_[i], adj_list_[i].size()};
  }
  // sort based on second element
  sort(
    ranks_.begin(), ranks_.end(),
    [](const pair<Pnode, int> & left, const pair<Pnode, int> & right) {
      return left.second > right.second;
    });
  return ranks_;
}
int
PRM::getNumberofSamples(
  const int & W, const int & H, const int & w, const int & h, const int & n,
  const int & occupancy_count)
{
  double occupancy_density = static_cast<double>(occupancy_count) / (W * H);
  return ((W * H) / (w * h)) * n * occupancy_density;
}

void
PRM::getMinCostPoint(
  const pair<int, int> & map_size,
  const vector<vector<int>> & costmap_2d,
  const vector<vector<int>> & inflation_map,
  const int & buffer_size,
  const MapLocation & rand_pos,
  MapLocation & temp_pos)
{
  int min_cost = inflation_map[rand_pos.x][rand_pos.y];
  for (int i = rand_pos.x - buffer_size; i < rand_pos.x + buffer_size; i++) {
    for (int j = rand_pos.y - buffer_size; j < rand_pos.y + buffer_size; j++) {
      if (i >= 0 && i < map_size.first && j >= 0 && j < map_size.second && !costmap_2d[i][j]) {
        int m = inflation_map[i][j];
        if (m < min_cost) {
          temp_pos = {i, j};
          min_cost = m;
        }
      }
    }
  }
}
