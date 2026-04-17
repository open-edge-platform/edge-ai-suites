// SPDX-License-Identifier: Apache-2.0
/*
 * Copyright (c) 2008-2018, Andrew Walker
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
#ifdef WIN32
#define _USE_MATH_DEFINES
#endif
#include <string>
#include <math.h>
#include <stdio.h>
#include <vector>
#include <array>
#include <map>
#include <set>
#include <string>
#include <algorithm>    // std::reverse
#include "../include/its_planner/dubins/dubins.hpp"
#include "../include/its_planner/path_utils/path_utils.hpp"

#define EPSILON (10e-10)

typedef enum
{
  L_SEG = 0,
  S_SEG = 1,
  R_SEG = 2
} SegmentType;

/* The segment types for each of the Path types */
const SegmentType DIRDATA[][3] = {
  {L_SEG, S_SEG, L_SEG},
  {L_SEG, S_SEG, R_SEG},
  {R_SEG, S_SEG, L_SEG},
  {R_SEG, S_SEG, R_SEG},
  {R_SEG, L_SEG, R_SEG},
  {L_SEG, R_SEG, L_SEG}
};

typedef struct
{
  double alpha;
  double beta;
  double d;
  double sa;
  double sb;
  double ca;
  double cb;
  double c_ab;
  double d_sq;
} DubinsIntermediateResults;


int dubins_word(DubinsIntermediateResults * in, DubinsPathType pathType, double out[3]);

int dubins_intermediate_results(
  DubinsIntermediateResults * in, double q0[3], double q1[3],
  double rho);

int dubins_shortest_path(DubinsPath * path, double q0[3], double q1[3], double rho)
{
  int i, errcode;
  DubinsIntermediateResults in;
  double params[3];
  double cost;
  double best_cost = INFINITY;
  int best_word = -1;
  errcode = dubins_intermediate_results(&in, q0, q1, rho);
  if (errcode != EDUBOK) {
    return errcode;
  }


  path->qi[0] = q0[0];
  path->qi[1] = q0[1];
  path->qi[2] = q0[2];
  path->rho = rho;

  for (i = 0; i < 6; i++) {
    DubinsPathType pathType = (DubinsPathType)i;
    errcode = dubins_word(&in, pathType, params);
    if (errcode == EDUBOK) {
      cost = params[0] + params[1] + params[2];
      if (cost < best_cost) {
        best_word = i;
        best_cost = cost;
        path->param[0] = params[0];
        path->param[1] = params[1];
        path->param[2] = params[2];
        path->type = pathType;
      }
    }
  }
  if (best_word == -1) {
    return EDUBNOPATH;
  }
  return EDUBOK;
}

int dubins_path(DubinsPath * path, double q0[3], double q1[3], double rho, DubinsPathType pathType)
{
  int errcode;
  DubinsIntermediateResults in;
  errcode = dubins_intermediate_results(&in, q0, q1, rho);
  if (errcode == EDUBOK) {
    double params[3];
    errcode = dubins_word(&in, pathType, params);
    if (errcode == EDUBOK) {
      path->param[0] = params[0];
      path->param[1] = params[1];
      path->param[2] = params[2];
      path->qi[0] = q0[0];
      path->qi[1] = q0[1];
      path->qi[2] = q0[2];
      path->rho = rho;
      path->type = pathType;
    }
  }
  return errcode;
}

double dubins_path_length(DubinsPath * path)
{
  double length = 0.;
  length += path->param[0];
  length += path->param[1];
  length += path->param[2];
  length = length * path->rho;
  return length;
}

double dubins_segment_length(DubinsPath * path, int i)
{
  if ( (i < 0) || (i > 2) ) {
    return INFINITY;
  }
  return path->param[i] * path->rho;
}

double dubins_segment_length_normalized(DubinsPath * path, int i)
{
  if ( (i < 0) || (i > 2) ) {
    return INFINITY;
  }
  return path->param[i];
}

DubinsPathType dubins_path_type(DubinsPath * path)
{
  return path->type;
}

void dubins_segment(double t, double qi[3], double qt[3], SegmentType type)
{
  double st = sinf(qi[2]);
  double ct = cosf(qi[2]);
  if (type == L_SEG) {
    qt[0] = +sinf(qi[2] + t) - st;
    qt[1] = -cosf(qi[2] + t) + ct;
    qt[2] = t;
  } else if (type == R_SEG) {
    qt[0] = -sinf(qi[2] - t) + st;
    qt[1] = +cosf(qi[2] - t) - ct;
    qt[2] = -t;
  } else if (type == S_SEG) {
    qt[0] = ct * t;
    qt[1] = st * t;
    qt[2] = 0.0;
  }
  qt[0] += qi[0];
  qt[1] += qi[1];
  qt[2] += qi[2];
}

int dubins_path_sample(DubinsPath * path, double t, double q[3])
{
  /* tprime is the normalised variant of the parameter t */
  double tprime = t / path->rho;
  double qi[3];   /* The translated initial configuration */
  double q1[3];   /* end-of segment 1 */
  double q2[3];   /* end-of segment 2 */
  const SegmentType * types = DIRDATA[path->type];
  double p1, p2;

  if (t < 0 || t > dubins_path_length(path) ) {
    return EDUBPARAM;
  }

  /* initial configuration */
  qi[0] = 0.0;
  qi[1] = 0.0;
  qi[2] = path->qi[2];

  /* generate the target configuration */
  p1 = path->param[0];
  p2 = path->param[1];
  dubins_segment(p1, qi, q1, types[0]);
  dubins_segment(p2, q1, q2, types[1]);
  if (tprime < p1) {
    dubins_segment(tprime, qi, q, types[0]);
  } else if (tprime < (p1 + p2) ) {
    dubins_segment(tprime - p1, q1, q, types[1]);
  } else {
    dubins_segment(tprime - p1 - p2, q2, q, types[2]);
  }

  /* scale the target configuration, translate back to the original starting point */
  q[0] = q[0] * path->rho + path->qi[0];
  q[1] = q[1] * path->rho + path->qi[1];
  q[2] = mod2pi(q[2]);

  return EDUBOK;
}

int dubins_path_sample_many(
  DubinsPath * path, double stepSize,
  DubinsPathSamplingCallback cb, void * user_data)
{
  int retcode;
  double q[3];
  double x = 0.0;
  double length = dubins_path_length(path);
  while (x < length) {
    dubins_path_sample(path, x, q);
    retcode = cb(q, x, user_data);
    if (retcode != 0) {
      return retcode;
    }
    x += stepSize;
  }
  return 0;
}

int dubins_path_endpoint(DubinsPath * path, double q[3])
{
  return dubins_path_sample(path, dubins_path_length(path) - EPSILON, q);
}

int dubins_extract_subpath(DubinsPath * path, double t, DubinsPath * newpath)
{
  /* calculate the true parameter */
  double tprime = t / path->rho;

  if ((t < 0) || (t > dubins_path_length(path))) {
    return EDUBPARAM;
  }

  /* copy most of the data */
  newpath->qi[0] = path->qi[0];
  newpath->qi[1] = path->qi[1];
  newpath->qi[2] = path->qi[2];
  newpath->rho = path->rho;
  newpath->type = path->type;

  /* fix the parameters */
  newpath->param[0] = fmin(path->param[0], tprime);
  newpath->param[1] = fmin(path->param[1], tprime - newpath->param[0]);
  newpath->param[2] = fmin(path->param[2], tprime - newpath->param[0] - newpath->param[1]);
  return 0;
}

int dubins_intermediate_results(
  DubinsIntermediateResults * in, double q0[3], double q1[3],
  double rho)
{
  double dx, dy, D, d, theta, alpha, beta;
  if (rho <= 0.0) {
    return EDUBBADRHO;
  }

  dx = q1[0] - q0[0];
  dy = q1[1] - q0[1];
  D = sqrt(dx * dx + dy * dy);
  d = D / rho;
  theta = 0;

  /* test required to prevent domain errors if dx=0 and dy=0 */
  if (d > 0) {
    theta = mod2pi(atan2f(dy, dx));
  }
  alpha = mod2pi(q0[2] - theta);
  beta = mod2pi(q1[2] - theta);

  in->alpha = alpha;
  in->beta = beta;
  in->d = d;
  in->sa = sinf(alpha);
  in->sb = sinf(beta);
  in->ca = cosf(alpha);
  in->cb = cosf(beta);
  in->c_ab = cosf(alpha - beta);
  in->d_sq = d * d;

  return EDUBOK;
}

int dubins_LSL(DubinsIntermediateResults * in, double out[3])
{
  double tmp0, tmp1, p_sq;

  tmp0 = in->d + in->sa - in->sb;
  p_sq = 2 + in->d_sq - (2 * in->c_ab) + (2 * in->d * (in->sa - in->sb));

  if (p_sq >= 0) {
    tmp1 = atan2f( (in->cb - in->ca), tmp0);
    out[0] = mod2pi(tmp1 - in->alpha);
    out[1] = sqrt(p_sq);
    out[2] = mod2pi(in->beta - tmp1);
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_RSR(DubinsIntermediateResults * in, double out[3])
{
  double tmp0 = in->d - in->sa + in->sb;
  double p_sq = 2 + in->d_sq - (2 * in->c_ab) + (2 * in->d * (in->sb - in->sa));
  if (p_sq >= 0) {
    double tmp1 = atan2f( (in->ca - in->cb), tmp0);
    out[0] = mod2pi(in->alpha - tmp1);
    out[1] = sqrt(p_sq);
    out[2] = mod2pi(tmp1 - in->beta);
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_LSR(DubinsIntermediateResults * in, double out[3])
{
  double p_sq = -2 + (in->d_sq) + (2 * in->c_ab) + (2 * in->d * (in->sa + in->sb));
  if (p_sq >= 0) {
    double p = sqrt(p_sq);
    double tmp0 = atan2f( (-in->ca - in->cb), (in->d + in->sa + in->sb) ) - atan2f(-2.0, p);
    out[0] = mod2pi(tmp0 - in->alpha);
    out[1] = p;
    out[2] = mod2pi(tmp0 - mod2pi(in->beta));
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_RSL(DubinsIntermediateResults * in, double out[3])
{
  double p_sq = -2 + in->d_sq + (2 * in->c_ab) - (2 * in->d * (in->sa + in->sb));
  if (p_sq >= 0) {
    double p = sqrt(p_sq);
    double tmp0 = atan2( (in->ca + in->cb), (in->d - in->sa - in->sb) ) - atan2f(2.0, p);
    out[0] = mod2pi(in->alpha - tmp0);
    out[1] = p;
    out[2] = mod2pi(in->beta - tmp0);
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_RLR(DubinsIntermediateResults * in, double out[3])
{
  double tmp0 = (6. - in->d_sq + 2 * in->c_ab + 2 * in->d * (in->sa - in->sb)) / 8.;
  double phi = atan2f(in->ca - in->cb, in->d - in->sa + in->sb);
  if (fabs(tmp0) <= 1) {
    double p = mod2pi((2 * M_PI) - acos(tmp0) );
    double t = mod2pi(in->alpha - phi + mod2pi(p / 2.));
    out[0] = t;
    out[1] = p;
    out[2] = mod2pi(in->alpha - in->beta - t + mod2pi(p));
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_LRL(DubinsIntermediateResults * in, double out[3])
{
  double tmp0 = (6. - in->d_sq + 2 * in->c_ab + 2 * in->d * (in->sb - in->sa)) / 8.;
  double phi = atan2f(in->ca - in->cb, in->d + in->sa - in->sb);
  if (fabs(tmp0) <= 1) {
    double p = mod2pi(2 * M_PI - acos(tmp0) );
    double t = mod2pi(-in->alpha - phi + p / 2.);
    out[0] = t;
    out[1] = p;
    out[2] = mod2pi(mod2pi(in->beta) - in->alpha - t + mod2pi(p));
    return EDUBOK;
  }
  return EDUBNOPATH;
}

int dubins_word(DubinsIntermediateResults * in, DubinsPathType pathType, double out[3])
{
  int result;
  switch (pathType) {
    case LSL:
      result = dubins_LSL(in, out);
      break;
    case RSL:
      result = dubins_RSL(in, out);
      break;
    case LSR:
      result = dubins_LSR(in, out);
      break;
    case RSR:
      result = dubins_RSR(in, out);
      break;
    case LRL:
      result = dubins_LRL(in, out);
      break;
    case RLR:
      result = dubins_RLR(in, out);
      break;
    default:
      result = EDUBNOPATH;
  }
  return result;
}


// Dubins path interpolation functions for ITS Planner
double fmodr(double x, double y)
{
  return x - y * floor(x / y);
}

double mod2pi(double theta)
{
  return fmodr(theta, 2 * M_PI);
}

int dubins_shortest_path_with_tolerance(
  DubinsPath * path,
  double q0[3],
  double q1[3],
  double yaw_tolerance,
  double rho,
  const vector<vector<int>> & costmap_2d,
  bool ensure_no_collision)
{
  int i, errcode;
  DubinsIntermediateResults in;
  double params[3];
  int best_word = -1;
  double cost;
  double best_cost = INFINITY;
  double best_valid_cost = INFINITY;
  DubinsPath best_valid_path;

  int numHeadings = 16;
  double newFinalHeading;

  for (size_t j = 0; j < numHeadings; j++) {
    newFinalHeading = lerp(q1[2] - yaw_tolerance, q1[2] + yaw_tolerance, j / (double) numHeadings);
    double q1_new[3] = {q1[0], q1[1], newFinalHeading};

    errcode = dubins_intermediate_results(&in, q0, q1_new, rho);
    if (errcode != EDUBOK) {
      return errcode;
    }

    path->qi[0] = q0[0];
    path->qi[1] = q0[1];
    path->qi[2] = q0[2];
    path->rho = rho;

    for (i = 0; i < 6; i++) {
      DubinsPathType pathType = (DubinsPathType)i;
      errcode = dubins_word(&in, pathType, params);
      if (errcode == EDUBOK) {
        cost = params[0] + params[1] + params[2];
        if (cost < best_cost) {
          path->param[0] = params[0];
          path->param[1] = params[1];
          path->param[2] = params[2];
          path->type = pathType;
          best_word = i;
          best_cost = cost;

          if (ensure_no_collision) {
            // Ensure this path does not collide with obstacles in costmap
            auto interpolated_path = interpolate_dubins_path(path, 1.0, rho);

            bool path_is_valid = true;
            for (size_t k = 0; k < interpolated_path.size(); k++) {
              inav_util::MapLocation pt;
              pt.x = (int) (interpolated_path[k].first + 0.5);
              pt.y = (int) (interpolated_path[k].second + 0.5);
              if (costmap_2d[pt.x][pt.y]) {
                path_is_valid = false;
                break;
              }
            }

            if (path_is_valid && cost < best_valid_cost) {
              best_valid_cost = cost;
              best_valid_path = *path;
            }
          }
        }
      }
    }
  }

  if (best_valid_cost != INFINITY) {
    *path = best_valid_path;
    return EDUBOK;
  }

  if (best_word == -1) {
    return EDUBNOPATH;
  }
  return EDUBOK;
}

bool collisionWithinRadius(
  const vector<vector<int>> & costmap_2d,
  const inav_util::MapLocation & pt,
  const int & rad)
{
  for (int x = pt.x - rad; x < pt.x + rad; x++) {
    for (int y = pt.y - rad; y < pt.y + rad; y++) {
      bool withinRad = pow(x - pt.x, 2) + pow(y - pt.y, 2) <= rad * rad;

      if (withinRad &&
        (x < 0 || x >= costmap_2d.size() || y < 0 || y >= costmap_2d[0].size() ||
        costmap_2d[x][y]))
      {
        return true;
      }
    }
  }
  return false;
}

vector<pair<double, double>> linear_interpolation(
  double (& curr_pose)[3], const double & length,
  const double & step_size)
{
  vector<pair<double, double>> path_segment;

  // Calculate end pos
  double endX = curr_pose[0] + length * cosf(curr_pose[2]);
  double endY = curr_pose[1] + length * sinf(curr_pose[2]);

  // Linearly interpolate from curr pos to end pos
  int num_steps = length / step_size;
  path_segment.reserve(num_steps);
  double inc = 1.0 / num_steps;
  for (double i = 0; i < 1.0; i += inc) {
    path_segment.push_back(
    {
      lerp(curr_pose[0], endX, i),
      lerp(curr_pose[1], endY, i)
    }
    );
  }

  // Update curr pos
  curr_pose[0] = endX;
  curr_pose[1] = endY;

  return path_segment;
}

vector<pair<double, double>> circular_interpolation(
  double (& curr_pose)[3], const double & length,
  const double & step_size,
  const double & turnRadius, const char & side)
{
  vector<pair<double, double>> path_segment;

  // Find angle of arc
  double arc_angle = length / turnRadius;

  // Find center of tangent circle
  double phi = (side == *"L") ? curr_pose[2] + M_PI / 2 : curr_pose[2] - M_PI / 2;
  double cx = curr_pose[0] + turnRadius * cosf(phi);
  double cy = curr_pose[1] + turnRadius * sinf(phi);

  // Center to curr pos vec
  double vx = curr_pose[0] - cx;
  double vy = curr_pose[1] - cy;

  // Calculate angle step size
  double angle_step_size = step_size / turnRadius;

  // Calculate "rotation matrix" constants
  double sin_val = (side == *"L") ? sinf(angle_step_size) : sinf(-angle_step_size);
  double cos_val = (side == *"L") ? cosf(angle_step_size) : cosf(-angle_step_size);

  // Circularly interpolate from curr pos to end pos
  int num_steps = length / step_size;
  path_segment.reserve(num_steps);
  for (int i = 0; i < num_steps; i++) {
    auto temp_vx = vx;
    vx = temp_vx * cos_val - vy * sin_val;
    vy = temp_vx * sin_val + vy * cos_val;
    path_segment.push_back(
    {
      cx + vx,
      cy + vy
    }
    );
  }

  // Calculate end pos and update curr pos
  double signed_arc_angle = (side == *"L") ? arc_angle : -arc_angle;
  double sin_val_full = sinf(signed_arc_angle);
  double cos_val_full = cosf(signed_arc_angle);
  double endX = cx + (curr_pose[0] - cx) * cos_val_full - (curr_pose[1] - cy) * sin_val_full;
  double endY = cy + (curr_pose[0] - cx) * sin_val_full + (curr_pose[1] - cy) * cos_val_full;
  curr_pose[0] = endX;
  curr_pose[1] = endY;
  curr_pose[2] = curr_pose[2] + signed_arc_angle;

  return path_segment;
}

vector<pair<double, double>> interpolate_dubins_path(
  DubinsPath * path, const double & step_size,
  const double & turnRadius)
{
  vector<pair<double, double>> interpolated_path;
  vector<pair<double, double>> path_segment;

  size_t capacity = dubins_path_length(path) / step_size;
  interpolated_path.reserve(capacity);

  // Break up path_type into iterable segments
  std::string path_type;
  switch (path->type) {
    case LSL: path_type = "LSL"; break;
    case LSR: path_type = "LSR"; break;
    case LRL: path_type = "LRL"; break;
    case RSR: path_type = "RSR"; break;
    case RSL: path_type = "RSL"; break;
    case RLR: path_type = "RLR"; break;
  }

  // Iterate over each segment of path
  double curr_pose[3]; std::copy(std::begin(path->qi), std::end(path->qi), std::begin(curr_pose));
  for (int i = 0; i < path_type.length(); i++) {
    if (path_type[i] == *"S") {
      path_segment = linear_interpolation(curr_pose, path->param[i] * path->rho, step_size);
    } else {
      path_segment = circular_interpolation(
        curr_pose, path->param[i] * path->rho, step_size,
        turnRadius, path_type[i]);
    }

    interpolated_path.insert(interpolated_path.end(), path_segment.begin(), path_segment.end());
  }


  return interpolated_path;
}

bool isDubinsCollision(
  const vector<vector<int>> & costmap,
  const inav_util::MapLocation & p1,
  const inav_util::MapLocation & p2,
  const double & step_size,
  const double & turnRadius,
  const double & initialHeading,
  const double & finalHeading,
  const double & headingTolerance,
  const bool & ensureNoCollision,
  vector<pair<double, double>> * retPath)
{
  DubinsPath path;
  double q1[] = {(double) p1.x, (double) p1.y, initialHeading};
  double q2[] = {(double) p2.x, (double) p2.y, finalHeading};
  dubins_shortest_path_with_tolerance(
    &path, q1, q2, headingTolerance, turnRadius, costmap,
    ensureNoCollision);

  auto interpolated_path = interpolate_dubins_path(&path, step_size, turnRadius);
  if (retPath) {*retPath = interpolated_path;}

  for (size_t k = 0; k < interpolated_path.size(); k++) {
    inav_util::MapLocation pt;
    pt.x = (int) (interpolated_path[k].first + 0.5);
    pt.y = (int) (interpolated_path[k].second + 0.5);
    if (pt.x >= costmap.size() || pt.x < 0 ||
      pt.y >= costmap[0].size() || pt.y < 0 ||
      costmap[pt.x][pt.y])
    {
      return true;
    }
  }
  return false;
}

vector<pair<double, double>> removeRedundantNodes(
  vector<std::array<double, 3>> & pathWithHeadings,
  const vector<pair<double, double>> & dubinsPath,
  const vector<int> & nodeIndeces,
  const double & turnRadius,
  const double & headingTolerance,
  const vector<vector<int>> & costmap)
{
  vector<pair<double, double>> path;
  vector<pair<double, double>> checkedPath;
  vector<pair<double, double>> originalPathSeg;
  std::map<pair<int, int>, vector<pair<double, double>>> path_segments;

  int numNodes = pathWithHeadings.size();
  int startNode = 0;
  int goalNode = numNodes - 1;
  int currNode = startNode;

  std::set<int> essentialNodeSet;
  vector<std::set<int>> childrenNodes(numNodes);

  // Compare nodes from start side to goal side to find potential shortcuts
  while (currNode != goalNode) {
    for (int compareNode = goalNode; compareNode > currNode; compareNode--) {
      auto q1 = pathWithHeadings[currNode].data();
      auto q2 = pathWithHeadings[compareNode].data();

      inav_util::MapLocation pt1 = {(int) q1[0], (int) q1[1]};
      inav_util::MapLocation pt2 = {(int) q2[0], (int) q2[1]};

      bool done = false;

      originalPathSeg = vector<pair<double, double>>(
        dubinsPath.begin() + nodeIndeces[currNode], dubinsPath.begin() + nodeIndeces[compareNode]);
      double newHeadingTolerance = (compareNode == goalNode) ? M_PI / 48 : headingTolerance;
      if (!isDubinsCollision(
          costmap, pt1, pt2, 1.0, turnRadius, q1[2], q2[2], newHeadingTolerance,
          true, &checkedPath))
      {
        // Don't consider this a shortcut if it's the same or longer than the original path
        if ((int) originalPathSeg.size() - (int) checkedPath.size() < turnRadius) {
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
        dubinsPath.begin() + nodeIndeces[curr], dubinsPath.begin() + nodeIndeces[next]);
    } else {
      pathSeg = path_segments[{essentialNodes[i], essentialNodes[i + 1]}];
    }
    path.insert(path.end(), pathSeg.begin(), pathSeg.end());
  }
  return path;
}

int samplingCallback(double q[3], double t, void * interpolated_path)
{
  vector<pair<double, double>> * temp = (vector<pair<double, double>> *)interpolated_path;
  temp->push_back(std::make_pair(q[0], q[1]));
  return 0;
}

double meanHeading(pair<double, double> * q0, pair<double, double> * q1, pair<double, double> * q2)
{
  pair<double, double> vec1 = {q1->first - q0->first, q1->second - q0->second};
  double heading1 = mod2pi(atan2f(vec1.second, vec1.first));
  if (!q2) {return heading1;}
  pair<double, double> vec2 = {q2->first - q1->first, q2->second - q1->second};
  double heading2 = mod2pi(atan2f(vec2.second, vec2.first));
  double dot = vec1.first * vec2.first + vec1.second * vec2.second;
  double det = vec1.first * vec2.second - vec1.second * vec2.first;
  double angleBetween = atan2f(det, dot);
  double finalHeading = heading1 + angleBetween / 2.0;
  return finalHeading;
}


void interpolateItsPath(
  vector<std::array<double, 3>> & pathWithHeadings,
  vector<pair<double, double>> & oldPath,
  const int & numSteps,
  const double & initialHeading,
  const double & finalHeading,
  vector<int> & nodeIndeces)
{
  if (oldPath.empty()) {return;}
  double nodeStepSize = (double) oldPath.size() / (double) numSteps;
  std::array<double, 3> startNode = {oldPath[0].first, oldPath[0].second, initialHeading};
  std::array<double, 3> goalNode = {oldPath.back().first, oldPath.back().second, finalHeading};
  pathWithHeadings = {startNode};
  nodeIndeces = {0};
  auto interNodes = getIntermediateNodes(
    oldPath, 1.0, nodeStepSize, initialHeading, finalHeading,
    nodeIndeces);
  pathWithHeadings.insert(pathWithHeadings.end(), interNodes.begin(), interNodes.end());
  pathWithHeadings.push_back(goalNode);
  nodeIndeces.push_back(oldPath.size() - 1);
}

vector<std::array<double, 3>> getIntermediateNodes(
  vector<pair<double, double>> & path,
  const double & pathStepSize,
  const double & nodeStepSize,
  const double & initialHeading,
  const double & finalHeading,
  vector<int> & nodeIndeces)
{
  vector<std::array<double, 3>> interNodes;
  if (path.size() == 0) {return interNodes;}

  double distCovered = 0;
  double heading;
  int stoppingPt = nodeStepSize / pathStepSize;
  stoppingPt = (stoppingPt > path.size()) ? 0 : stoppingPt;
  for (size_t i = 0; i < path.size() - stoppingPt; i++) {
    distCovered += pathStepSize;
    if (distCovered >= nodeStepSize) {
      heading = (i == 0) ? initialHeading : (i == path.size() - 1) ? finalHeading : meanHeading(
        &path[i - 1], &path[i], &path[i + 1]);
      interNodes.push_back({path[i].first, path[i].second, heading});
      nodeIndeces.push_back(i);
      distCovered = 0;
    }
  }
  return interNodes;
}
