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
#ifndef DUBINS_HPP
#define DUBINS_HPP

#include <vector>
#include "../path_utils/path_utils.hpp"


typedef enum
{
  LSL = 0,
  LSR = 1,
  RSL = 2,
  RSR = 3,
  RLR = 4,
  LRL = 5
} DubinsPathType;

typedef struct
{
  /* the initial configuration */
  double qi[3];
  /* the lengths of the three segments */
  double param[3];
  /* model forward velocity / model angular velocity */
  double rho;
  /* the path type described */
  DubinsPathType type;
} DubinsPath;

#define EDUBOK        (0)   /* No error */
#define EDUBCOCONFIGS (1)   /* Colocated configurations */
#define EDUBPARAM     (2)   /* Path parameterisitation error */
#define EDUBBADRHO    (3)   /* the rho value is invalid */
#define EDUBNOPATH    (4)   /* no connection between configurations with this word */

/**
 * Callback function for path sampling
 *
 * @note the q parameter is a configuration
 * @note the t parameter is the distance along the path
 * @note the user_data parameter is forwarded from the caller
 * @note return non-zero to denote sampling should be stopped
 */
typedef int (* DubinsPathSamplingCallback)(double q[3], double t, void * user_data);

/**
 * Generate a path from an initial configuration to
 * a target configuration, with a specified maximum turning
 * radii
 *
 * A configuration is (x, y, theta), where theta is in radians, with zero
 * along the line x = 0, and counter-clockwise is positive
 *
 * @param path  - the resultant path
 * @param q0    - a configuration specified as an array of x, y, theta
 * @param q1    - a configuration specified as an array of x, y, theta
 * @param rho   - turning radius of the vehicle (forward velocity divided by maximum angular velocity)
 * @return      - non-zero on error
 */
int dubins_shortest_path(DubinsPath * path, double q0[3], double q1[3], double rho);

/**
 * Generate a path with a specified word from an initial configuration to
 * a target configuration, with a specified turning radius
 *
 * @param path     - the resultant path
 * @param q0       - a configuration specified as an array of x, y, theta
 * @param q1       - a configuration specified as an array of x, y, theta
 * @param rho      - turning radius of the vehicle (forward velocity divided by maximum angular velocity)
 * @param pathType - the specific path type to use
 * @return         - non-zero on error
 */
int dubins_path(DubinsPath * path, double q0[3], double q1[3], double rho, DubinsPathType pathType);

/**
 * Calculate the length of an initialised path
 *
 * @param path - the path to find the length of
 */
double dubins_path_length(DubinsPath * path);

/**
 * Return the length of a specific segment in an initialized path
 *
 * @param path - the path to find the length of
 * @param i    - the segment you to get the length of (0-2)
 */
double dubins_segment_length(DubinsPath * path, int i);

/**
 * Return the normalized length of a specific segment in an initialized path
 *
 * @param path - the path to find the length of
 * @param i    - the segment you to get the length of (0-2)
 */
double dubins_segment_length_normalized(DubinsPath * path, int i);

/**
 * Extract an integer that represents which path type was used
 *
 * @param path    - an initialised path
 * @return        - one of LSL, LSR, RSL, RSR, RLR or LRL
 */
DubinsPathType dubins_path_type(DubinsPath * path);

/**
 * Calculate the configuration along the path, using the parameter t
 *
 * @param path - an initialised path
 * @param t    - a length measure, where 0 <= t < dubins_path_length(path)
 * @param q    - the configuration result
 * @returns    - non-zero if 't' is not in the correct range
 */
int dubins_path_sample(DubinsPath * path, double t, double q[3]);

/**
 * Walk along the path at a fixed sampling interval, calling the
 * callback function at each interval
 *
 * The sampling process continues until the whole path is sampled, or the callback returns a non-zero value
 *
 * @param path      - the path to sample
 * @param stepSize  - the distance along the path for subsequent samples
 * @param cb        - the callback function to call for each sample
 * @param user_data - optional information to pass on to the callback
 *
 * @returns - zero on successful completion, or the result of the callback
 */
int dubins_path_sample_many(
  DubinsPath * path,
  double stepSize,
  DubinsPathSamplingCallback cb,
  void * user_data);

/**
 * Convenience function to identify the endpoint of a path
 *
 * @param path - an initialised path
 * @param q    - the configuration result
 */
int dubins_path_endpoint(DubinsPath * path, double q[3]);

/**
 * Convenience function to extract a subset of a path
 *
 * @param path    - an initialised path
 * @param t       - a length measure, where 0 < t < dubins_path_length(path)
 * @param newpath - the resultant path
 */
int dubins_extract_subpath(DubinsPath * path, double t, DubinsPath * newpath);

int samplingCallback(double q[3], double t, void * user_data);


/**
 * Generate a path from an initial configuration to a target configuration, with a specified
 * maximum turning radii and a specified tolerance in which the final heading may deviate
 *
 * @param path            - the resultant path
 * @param q0              - a configuration specified as an array of x, y, theta
 * @param q1              - a configuration specified as an array of x, y, theta
 * @param yaw_tolerance   - the amount in radians the final heading can deviate
 * @param rho             - turning radius of the vehicle (forward velocity divided by maximum angular velocity)
 * @param costmap         - a binary two-dimensional array representing an obstacle map
 * @return                - non-zero on error
 */
int dubins_shortest_path_with_tolerance(
  DubinsPath * path,
  double q0[3],
  double q1[3],
  double yaw_tolerance,
  double rho,
  const vector<vector<int>> & costmap,
  bool ensure_no_collision
);

/**
 * Check for a collision in the costmap along a Dubins curve between two points
 *
 * @param costmap             - a binary two-dimensional array representing an obstacle map
 * @param p1                  - the start position of the Dubins curve
 * @param p2                  - the end position of the Dubins curve
 * @param step_size           - the interval size at which to check for collisions in the costmap (map scale)
 * @param turnRadius          - turning radius of the vehicle (map scale)
 * @param initialHeading      - the start heading of the Dubins curve, in radians
 * @param finalHeading        - the end heading of the Dubins curve, in radians
 * @param headingTolerance    - the amount the end heading can deviate, in radians
 * @param ensureNoCollision   - whether to do collision checking when generating the Dubins curve (this is more performance-heavy)
 * @param retPath             - a pointer to a variable in which to store the interpolated Dubins curve which was checked for collision
 * @return                    - true if a collision is detected along the Dubins curve, false otherwise
 */
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
  vector<pair<double, double>> * retPath);


/**
 * Generate intermediate nodes along a Dubins path segment
 *
 * @param path                - the path along which intermediate nodes will be generated
 * @param pathStepSize        - the step size at which the path was originally interpolated by
 * @param nodeStepSize        - the step size at which each intermediate node will be generated
 * @param initialHeading      - the start heading of the path, in radians
 * @param finalHeading        - the end heading of the path, in radians
 * @param nodeIndeces         - a vector storing the indeces in the original path corresponding to each intermediate node
 * @return                    - a vector of intermediate nodes along a path, each containing a position and heading
 */
vector<std::array<double, 3>> getIntermediateNodes(
  vector<pair<double, double>> & path,
  const double & pathStepSize,
  const double & nodeStepSize,
  const double & initialHeading,
  const double & finalHeading,
  vector<int> & nodeIndeces);

/**
 * Interpolate the original path to include headings and intermediate nodes
 *
 * @param pathWithHeadings    - the variable in which the new path with headings and intermediate nodes will be stored
 * @param oldPath             - the original path
 * @param numSteps            - the number of equally-sized steps to interpolate along the path
 * @param initialHeading      - the start heading of the path, in radians
 * @param finalHeading        - the end heading of the path, in radians
 * @param nodeIndeces         - a vector storing the indeces in the original path corresponding to each node in the new path
 */
void interpolateItsPath(
  vector<std::array<double, 3>> & pathWithHeadings,
  vector<pair<double, double>> & oldPath,
  const int & numSteps,
  const double & initialHeading,
  const double & finalHeading,
  vector<int> & nodeIndeces);

/**
 * Remove redundant nodes along a sequence of nodes representing a Dubins path
 *
 * @param pathWithHeadings    - the sequence of nodes with positions and headings representing a Dubins path
 * @param dubinsPath          - the original Dubins path, from which pathWithHeadings was derived
 * @param nodeIndeces         - a vector storing the indeces in the original Dubins path corresponding to each node in pathWithHeadings
 * @param turnRadius          - turning radius of the vehicle (map scale)
 * @param headingTolerance    - the amount the end heading can deviate, in radians
 * @param costmap             - a binary two-dimensional array representing an obstacle map
 */
vector<pair<double, double>> removeRedundantNodes(
  vector<std::array<double, 3>> & pathWithHeadings,
  const vector<pair<double, double>> & dubinsPath,
  const vector<int> & nodeIndeces,
  const double & turnRadius,
  const double & headingTolerance,
  const vector<vector<int>> & costmap);

/**
 * Get the interpolated Dubins path from a DubinsPath object
 *
 * @param path                - the DubinsPath object from which to generate the interpolated path
 * @param step_size           - the size of a single step
 * @param turnRadius          - turning radius of the vehicle (map scale)
 */
vector<pair<double, double>> interpolate_dubins_path(
  DubinsPath * path,
  const double & step_size,
  const double & turnRadius);

double lerp(double a, double b, double f) {return a + f * (b - a);}

double mod2pi(double theta);

#endif /* DUBINS_HPP */
