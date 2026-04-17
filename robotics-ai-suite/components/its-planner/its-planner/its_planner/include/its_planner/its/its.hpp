// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#ifndef ITS_PLANNER__ITS__ITS_HPP_
#define ITS_PLANNER__ITS__ITS_HPP_

#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <random>
#include <variant>
#include <iostream>
#include <utility>

#include "../include/its_planner/path_utils/path_utils.hpp"
#include "../include/its_planner/prm/prm.hpp"

class ITS : public PRM
{
public:
  ITS();
  explicit ITS(const PRM & map)
  {
    vertices_.resize(map.vertices_.size());
    vertices_ = map.vertices_;
    milestones_.resize(map.milestones_.size());
    milestones_ = map.milestones_;
    num_vertices_ = map.num_vertices_;
    adj_list_.resize(map.adj_list_.size());
    adj_list_ = map.adj_list_;
    start_id_ = map.start_id_;
    goal_id_ = map.goal_id_;
    it_num_ = map.it_num_;
    um_node_ = map.um_node_;
  }
  ~ITS();

  enum ITS_Algo
  {
    DEFAULT,
    DUBINS
  };

  std::variant<vector<pair<int, int>>, vector<pair<double, double>>>
  getITSPath(
    vector<vector<int>> & costmap_2d,
    const MapLocation & start, const MapLocation & goal,
    const int & num, const bool & enable_k,
    const bool & useDubins = false,
    const double & turnRadius = 0.0,
    const double & robotRadius = 0.0,
    const double & initialHeading = 0.0,
    const double & finalHeading = 0.0,
    const double & headingTolerance = 0.0);

  // Search for and return a free space around point `pt` in the `costmap` within a circle of radius `rad`.
  // If none is found, return the original point
  MapLocation nearbyFreeSpace(
    vector<vector<int>> & costmap,
    const MapLocation & pt,
    const double & rad);

private:
  // Struct to store the inputs, outputs, and shared state of the intelligentTwoWaySearch function
  struct ITS_Shared_State
  {
    // Inputs
    vector<vector<int>> & costmap_2d;
    const MapLocation & start;
    const MapLocation & goal;
    const int & num;
    const bool & enable_k;
    const bool & useDubins;
    const double & turnRadius;
    const double & robotRadius;
    const double & initialHeading;
    const double & finalHeading;
    const double & headingTolerance;

    // Shared inner state
    int count = 0;
    bool search_done = false;
    bool reversed_terms = false;
    std::map<pair<int, int>, vector<pair<double, double>>> path_segments;
    vector<pair<double, double>> checkedPath;
    vector<pair<double, double>> checkedPathAlt;
    vector<pair<int, int>> pathSegmentPairs;

    // Outputs
    vector<pair<int, int>> path;
    vector<pair<double, double>> dubinsPath;
  };

  // Struct to store the individual state of one half of the ITS algorithm
  struct ITS_Half_State
  {
    Pnode p;
    vector<int> parent;
    vector<bool> visited;
    bool vis = false;
    int origin_id;
    MapLocation target;
    bool is_goal_side = false;
    bool updated = true;

    // Dubins-specific
    vector<double> headings_dict;
    double heading;
    double next_heading;
    bool try_alternate_heading = false;
    bool try_alternate_origin = false;
  };

/**
 * Performs the ITS algorithm
 *
 * @param Q      - the shared state, containing variables which both halves of the algorithm use
 * @param S      - the state containing the variables for the Start side of the algorithm
 * @param G      - the state containing the variables for the Goal side of the algorithm
 */
  void intelligentTwoWaySearch(ITS_Shared_State & Q, ITS_Half_State & S, ITS_Half_State & G);

/**
 * Performs one half of the two-way search, from an origin state N1 to a target state N2
 *
 * @param Q      - the shared state, containing variables which both halves of the algorithm use
 * @param N1     - the state for the origin side, from where the search will be conducted towards the target side
 * @param N2     - the state for the target side
 */
  void oneWaySearch(ITS_Shared_State & Q, ITS_Half_State & N1, ITS_Half_State & N2);

/**
 * Post processes one half of the search results to choose the nodes which will make up the ITS path
 *
 * @param Q      - the shared state, containing variables which both halves of the algorithm use
 * @param N1     - the state for the side currently being post-processed
 * @param N2     - the state for the other side
 */
  void postProcess(ITS_Shared_State & Q, ITS_Half_State & N1, ITS_Half_State & N2);

/**
 * Performs either a linear or Dubins collision detection, depending on whether Q.useDubins is true or not
 *
 * @param Q          - the shared state containing the useDubins boolean, to determine which type of collision check to use
 * @param pt1        - the start position of the path to be checked
 * @param pt2        - the end position of the path to be checked
 * @param heading1   - the start heading of the Dubins curve, in radians - not used if Q.useDubins is false
 * @param heading2   - the end heading of the Dubins curve, in radians - not used if Q.useDubins is false
 * @return           - true if a collision is detected along the checked path, false otherwise
 */
  bool isCollisionITS(
    ITS_Shared_State & Q,
    const MapLocation & pt1,
    const MapLocation & pt2,
    const double & heading1,
    const double & heading2);

/**
 * Helper function to reverse a pair of ints if Q.reversed_terms is true
 *
 * @param p          - a pair of integers
 * @param Q          - the shared state containing the reversed_terms boolean, to determine whether to reverse the pair
 * @return           - the reversed pair if Q.reversed_terms is true, the original pair otherwise
 */
  pair<int, int> reversed(const pair<int, int> & p, ITS_Shared_State & Q);
};
#endif  // ITS_PLANNER__ITS__ITS_HPP_
