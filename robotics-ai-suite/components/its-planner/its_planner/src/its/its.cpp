// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#include <limits.h>  // INT_MAX
#include <float.h>  // FLT_MAX
#include <vector>
#include <set>
#include <map>
#include <iostream>
#include <algorithm>  // reverse
#include <variant>
#include <queue>
#include <stack>
#include <utility>
#include "../include/its_planner/its/its.hpp"
#include "../include/its_planner/dubins/dubins.hpp"


ITS::~ITS()
{
}

std::variant<vector<pair<int, int>>, vector<pair<double, double>>>
ITS::getITSPath(
  vector<vector<int>> & costmap_2d,
  const MapLocation & start, const MapLocation & goal,
  const int & num, const bool & enable_k,
  const bool & useDubins,
  const double & turnRadius,
  const double & robotRadius,
  const double & initialHeading,
  const double & finalHeading,
  const double & headingTolerance)
{
  ITS_Shared_State Q =
  {costmap_2d, start, goal, num, enable_k, useDubins, turnRadius, robotRadius, initialHeading,
    finalHeading, headingTolerance};
  ITS_Half_State S;
  ITS_Half_State G;
  S.p = {start, start_id_};
  G.p = {goal, goal_id_};
  S.origin_id = start_id_;
  G.origin_id = goal_id_;
  S.target = goal;
  G.target = start;
  G.parent.resize(num_vertices_, -1);
  S.parent.resize(num_vertices_, -1);
  S.parent[start_id_] = start_id_;
  G.parent[goal_id_] = goal_id_;
  S.visited.resize(num_vertices_, false);
  G.visited.resize(num_vertices_, false);
  S.visited[start_id_] = true;
  G.visited[goal_id_] = true;
  G.is_goal_side = true;

  if (useDubins) {
    S.headings_dict.resize(num_vertices_);
    G.headings_dict.resize(num_vertices_);
    S.headings_dict[start_id_] = initialHeading;
    G.headings_dict[goal_id_] = finalHeading;
    S.heading = initialHeading;
    G.heading = finalHeading;
  }

  intelligentTwoWaySearch(Q, S, G);
  if (useDubins) {return Q.dubinsPath;} else {return Q.path;}
}

//  ITS Algo
void ITS::intelligentTwoWaySearch(ITS_Shared_State & Q, ITS_Half_State & S, ITS_Half_State & G)
{
  while (isCollisionITS(Q, S.p.position, G.p.position, S.heading, G.heading) && !S.vis && !G.vis) {
    if (isGoalReached(
        S.p.position.x, S.p.position.y,
        Q.goal) || isGoalReached(G.p.position.x, G.p.position.y, Q.start)) {break;}
    Q.count++;
    if (Q.count >= num_vertices_ * 2) {
      return;                                  // Path is not found

    }
    // Start side search
    oneWaySearch(Q, S, G);
    if (Q.search_done) {break;}

    // Goal side search
    oneWaySearch(Q, G, S);
    if (Q.search_done) {break;}

    if (!S.updated && !G.updated) {
      return;                             // If neither side updated, then path is not found.

    }
    // While loop condition must be checked from S to G, so reset the reversed_terms boolean
    Q.reversed_terms = false;
  }

  if (Q.useDubins && !S.vis && !G.vis) {
    // Store the checked path from the while loop condition
    Q.path_segments[{S.p.id, G.p.id}] = Q.checkedPath;
  }

  postProcess(Q, S, G);

  if (Q.useDubins && !S.vis && !G.vis) {
    // Recall the checked path from the while loop condition
    Q.pathSegmentPairs.push_back({S.p.id, G.p.id});
  }

  postProcess(Q, G, S);

  if (isGoalReached(
      S.p.position.x, S.p.position.y,
      Q.start) && isGoalReached(G.p.position.x, G.p.position.y, Q.goal))
  {
    Q.path.push_back({Q.start.x, Q.start.y});
    Q.path.push_back({Q.goal.x, Q.goal.y});
    if (Q.useDubins) {Q.pathSegmentPairs.push_back({S.p.id, G.p.id});}
  }

  if (Q.useDubins) {
    // Aggregate the path segments to form the final dubinsPath
    for (size_t i = 0; i < Q.pathSegmentPairs.size(); i++) {
      auto pathSegment = Q.path_segments[Q.pathSegmentPairs[i]];
      Q.dubinsPath.insert(Q.dubinsPath.end(), pathSegment.begin(), pathSegment.end());
    }
  }
}

void ITS::oneWaySearch(ITS_Shared_State & Q, ITS_Half_State & N1, ITS_Half_State & N2)
{
  float d = FLT_MAX;
  int pID = N1.p.id;
  Pnode p_temp = N1.p;
  if (!N1.updated) {return;}
  N1.updated = false;
  double heading_temp = N1.heading;
  Pnode neighbor;

  Q.reversed_terms = N1.is_goal_side;

  // 1. Visit the neigbors of N1 and select the node which is closest to N2
  for (int i = 0; i < adj_list_[pID].size(); i++) {
    neighbor = adj_list_[pID][i];
    auto pt1 = N1.p.position;
    auto pt2 = neighbor.position;

    if (Q.useDubins) {
      N1.next_heading = (!Q.reversed_terms) ? mod2pi(atan2f(pt2.y - pt1.y, pt2.x - pt1.x)) : mod2pi(
        atan2f(
          pt1.y - pt2.y,
          pt1.x - pt2.x));
      if (isNearWithin(pt2, N1.target, Q.robotRadius)) {
        N1.next_heading = N2.headings_dict[N2.origin_id];
      }

      // Try alternate heading to see if we can keep progressing search
      if (N1.try_alternate_heading) {
        auto parentPt = um_node_[N1.parent[pID]];
        auto parentHeading = N1.headings_dict[N1.parent[pID]];
        if (!isCollisionITS(Q, parentPt, pt1, parentHeading, N1.next_heading)) {
          N1.heading = N1.next_heading;
          Q.checkedPathAlt = Q.checkedPath;
        }
      }
    }
    int v = neighbor.id;
    if (!N1.visited[v] && N2.visited[v] &&
      (!Q.useDubins || !isCollisionITS(Q, pt1, pt2, N1.heading, N2.headings_dict[v])))
    {
      // This node has already been visited from the other direction and is reachable
      N2.vis = true;
      p_temp = neighbor;
      if (Q.useDubins) {
        heading_temp = N2.headings_dict[v];
        if (N1.try_alternate_heading) {
          Q.path_segments[reversed({N1.parent[pID], pID}, Q)] = Q.checkedPathAlt;
        }
        Q.path_segments[reversed({pID, p_temp.id}, Q)] = Q.checkedPath;
      }

      break;
    } else if (!N1.visited[v]) {
      // Calculate collision check here so Q.checkedPath will have correct path stored for the 'g' cost component
      bool isCollision = (Q.useDubins) ? isCollisionITS(
        Q, N1.p.position, neighbor.position,
        N1.heading, N1.next_heading) : false;
      double g = (Q.useDubins) ? pow(Q.checkedPath.size(), 2) : euclideanDistanceSq(
        N1.p.position,
        neighbor.position);
      double h = euclideanDistanceSq(neighbor.position, {N2.p.position.x, N2.p.position.y});
      double k = 0;
      if (Q.enable_k) {k = euclideanDistanceSq(neighbor.position, {N1.target.x, N1.target.y});}
      double f = g + h + k;

      if (f < d && (!Q.useDubins || !isCollision)) {
        d = f;
        p_temp = neighbor;

        if (Q.useDubins) {
          heading_temp = N1.next_heading;
          if (N1.try_alternate_heading) {
            Q.path_segments[reversed({N1.parent[pID], pID}, Q)] = Q.checkedPathAlt;
          }
          Q.path_segments[reversed({pID, p_temp.id}, Q)] = Q.checkedPath;
        }
      }
    }
  }

  // 2. Update point
  if (p_temp.id != pID) {
    N1.p = p_temp;
    N1.updated = true;
    N1.visited[N1.p.id] = true;

    if (Q.useDubins) {
      N1.heading = heading_temp;
      N1.headings_dict[N1.p.id] = N1.heading;
      if (N1.try_alternate_heading) {
        N1.headings_dict[pID] = N1.heading;
        N1.try_alternate_heading = false;
      }
    }

    N1.parent[p_temp.id] = pID;
    int parent_of_pID = N1.parent[pID];
    MapLocation parent_of_pID_pos = um_node_[parent_of_pID];
    for (int i = 0; i < adj_list_[parent_of_pID].size(); i++) {
      int v = p_temp.id;
      if (adj_list_[parent_of_pID][i].id == v &&
        (!Q.useDubins ||
        !isCollisionITS(
          Q, parent_of_pID_pos, N1.p.position, N1.headings_dict[parent_of_pID],
          N1.heading)))
      {
        N1.parent[v] = parent_of_pID;
        if (Q.useDubins) {Q.path_segments[reversed({parent_of_pID, p_temp.id}, Q)] = Q.checkedPath;}
        break;
      }
    }

    if (N2.vis) {
      Q.search_done = true;
    }
  } else if (Q.useDubins) {
    if (!N1.try_alternate_heading && pID != N1.origin_id) {
      N1.try_alternate_heading = true;
      N1.updated = true;
    } else {
      if (pID == N1.origin_id && !N1.try_alternate_origin) {
        N1.p.position = nearbyFreeSpace(Q.costmap_2d, N1.p.position, Q.robotRadius);
        N1.try_alternate_origin = true;
      }
    }
  }
}

void ITS::postProcess(ITS_Shared_State & Q, ITS_Half_State & N1, ITS_Half_State & N2)
{
  Q.reversed_terms = N1.is_goal_side;
  if (!isGoalReached(N2.p.position.x, N2.p.position.y, N2.target)) {
    MapLocation currNode = N1.p.position;
    int id = N1.p.id;
    if (N1.vis) {
      N1.p = N2.p;
      currNode = N1.p.position;
      id = N1.p.id;
    }
    while (id != N1.origin_id) {
      Q.path.push_back({currNode.x, currNode.y});
      if (Q.useDubins) {Q.pathSegmentPairs.push_back(reversed({N1.parent[id], id}, Q));}
      id = N1.parent[id];
      currNode = um_node_[id];
      if (id == N1.parent[id]) {
        Q.path.push_back({currNode.x, currNode.y});
        break;
      }
    }
    if (!N1.is_goal_side) {
      reverse(Q.path.begin(), Q.path.end());
      if (Q.useDubins) {reverse(Q.pathSegmentPairs.begin(), Q.pathSegmentPairs.end());}
    }
  }
}

MapLocation ITS::nearbyFreeSpace(
  vector<vector<int>> & costmap,
  const MapLocation & pt,
  const double & rad)
{
  for (int x = pt.x - rad; x < pt.x + rad; x++) {
    for (int y = pt.y - rad; y < pt.y + rad; y++) {
      bool withinRad = pow(x - pt.x, 2) + pow(y - pt.y, 2) <= rad * rad;
      if (withinRad && !costmap[x][y]) {
        return {x, y};
      }
    }
  }
  return pt;
}


bool ITS::isCollisionITS(
  ITS_Shared_State & Q,
  const MapLocation & pt1,
  const MapLocation & pt2,
  const double & heading1,
  const double & heading2)
{
  if (Q.useDubins) {
    double newHeadingTolerance = Q.headingTolerance;
    if (!Q.reversed_terms) {
      if (isGoalReached(pt2.x, pt2.y, Q.goal)) {newHeadingTolerance = M_PI / 48;}
      return isDubinsCollision(
        Q.costmap_2d, pt1, pt2, 1.0, Q.turnRadius, heading1, heading2,
        newHeadingTolerance, false, &Q.checkedPath);
    } else {
      if (isGoalReached(pt1.x, pt1.y, Q.goal)) {newHeadingTolerance = M_PI / 48;}
      return isDubinsCollision(
        Q.costmap_2d, pt2, pt1, 1.0, Q.turnRadius, heading2, heading1,
        newHeadingTolerance, false, &Q.checkedPath);
    }
  } else {
    return isCollision(Q.costmap_2d, pt1, pt2, 1.0);
  }
}

pair<int, int> ITS::reversed(const pair<int, int> & p, ITS_Shared_State & Q)
{
  if (Q.reversed_terms) {
    return {p.second, p.first};
  } else {
    return p;
  }
}
