// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#ifndef ITS_PLANNER__PRM__PRM_HPP_
#define ITS_PLANNER__PRM__PRM_HPP_

#include <assert.h>
#include <boost/archive/text_iarchive.hpp>
#include <boost/archive/text_oarchive.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/vector.hpp>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <random>
#include <iostream>
#include <fstream>
#include <string>
#include <utility>
#include "../include/its_planner/path_utils/path_utils.hpp"

using std::string;
using std::unordered_map;
using inav_util::MapLocation;
using inav_util::Node;
using inav_util::Costs;

struct Pnode
{
  MapLocation position;
  int id;
};

struct Path
{
  MapLocation position;
  int cost;
};

class PRM
{
public:
  PRM();
  ~PRM();
  void buildRoadMap(
    const vector<vector<int>> & costmap_2d,
    const int num,
    string plan,
    const vector<vector<int>> & inflation_map,
    const int & buffer_size);
  void generateGraph(
    const vector<vector<int>> & costmap_2d,
    const vector<Pnode> & milestones,
    const double & step_size);
  vector<Pnode> getMilestones();
  bool addStartGoalNode(
    const vector<vector<int>> & costmap_2d,
    const MapLocation & start,
    const MapLocation & goal);
  int getNumberofSamples(
    const int & W, const int & H, const int & w, const int & h, const int & n,
    const int & occupancy_count);
  friend class ITS;
  vector<Pnode> milestones_;
  vector<pair<Pnode, Pnode>> vertices_;
  int num_vertices_ = 0;
  vector<vector<Pnode>> adj_list_;
  int it_num_ = 0;
  unordered_map<int, MapLocation> um_node_;
  vector<pair<Pnode, int>> getRanks();

private:
  int start_id_;
  int goal_id_;
  vector<pair<Pnode, int>> ranks_; // <milestone id, number of connectivity>
  vector<Pnode> generateMilestones(
    const pair<int, int> map_size,
    const vector<vector<int>> & costmap_2d,
    const vector<vector<int>> & inflation_map,
    const int n,
    const string plan,
    const int & buffer_size);
  bool isCollision(
    const vector<vector<int>> & costmap_2d,
    const MapLocation & p1, const MapLocation & p2, const double & step_size);
  vector<Pnode> kNearestNeighbor(
    const Pnode & p1,
    const vector<Pnode> & points,
    int K);
  void buildAdjacencyList();
  double haltonSequence(int index, int base);
  void getMinCostPoint(
    const pair<int, int> & map_size,
    const vector<vector<int>> & costmap_2d,
    const vector<vector<int>> & inflation_map,
    const int & buffer_size,
    const MapLocation & rand_pos,
    MapLocation & temp_pos);
};

namespace boost
{
namespace serialization
{
template<class Archive>
void serialize(Archive & archive, MapLocation & maplocation, const unsigned int version)
{
  archive & maplocation.x;
  archive & maplocation.y;
}
template<class Archive>
void serialize(Archive & archive, Pnode & pnode, const unsigned int version)
{
  archive & pnode.position;
  archive & pnode.id;
}
template<class Archive>
void serialize(Archive & archive, PRM & prm, const unsigned int version)
{
  archive & prm.vertices_;
  archive & prm.milestones_;
  archive & prm.num_vertices_;
  archive & prm.adj_list_;
  archive & prm.it_num_;
  archive & prm.um_node_;
}
}  // namespace serialization
}  // namespace boost
#endif  // ITS_PLANNER__PRM__PRM_HPP_
