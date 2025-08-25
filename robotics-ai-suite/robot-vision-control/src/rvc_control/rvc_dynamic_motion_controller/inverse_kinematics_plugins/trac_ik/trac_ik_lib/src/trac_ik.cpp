// SPDX-License-Identifier: BSD-3-Clause
// SPDX-FileCopyrightText: (C) 2015 TRACLabs, Inc.
// Copyright (c) 2015, TRACLabs, Inc.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//    * Redistributions of source code must retain the above copyright
//      notice, this list of conditions and the following disclaimer.
//
//    * Redistributions in binary form must reproduce the above copyright
//      notice, this list of conditions and the following disclaimer in the
//      documentation and/or other materials provided with the distribution.
//
//    * Neither the name of the {copyright_holder} nor the names of its
//      contributors may be used to endorse or promote products derived from
//      this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.


#include "trac_ik/trac_ik.hpp"

#include <algorithm>
#include <limits>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "Eigen/Geometry"
#include "kdl_parser/kdl_parser.hpp"
#include "rclcpp/rclcpp.hpp"
#include "urdf/model.h"

namespace TRAC_IK
{
static const rclcpp::Logger LOGGER = rclcpp::get_logger("trac_ik.ros.trac_ik");

TRAC_IK::TRAC_IK(
  const std::string & base_link, const std::string & tip_link,
  const std::string & urdf_xml, double _maxtime, double _eps, SolveType _type)
: notifyFlag(false),
  initialized(false),
  eps(_eps),
  maxtime(std::chrono::duration<double>(_maxtime)),
  solvetype(_type)
{
  urdf::Model robot_model;
  if (!robot_model.initString(urdf_xml)) {
    RCLCPP_FATAL(LOGGER, "Unable to initialize urdf::Model from robot description.");
  }

  RCLCPP_DEBUG(LOGGER, "Reading joints and links from URDF");

  KDL::Tree tree;

  if (!kdl_parser::treeFromUrdfModel(robot_model, tree)) {
    RCLCPP_FATAL(LOGGER, "Failed to extract kdl tree from xml robot description");
  }

  if (!tree.getChain(base_link, tip_link, chain)) {
    RCLCPP_FATAL_STREAM(
      LOGGER, "Couldn't find chain " << base_link.c_str() << " to " << tip_link.c_str());
  }

  std::vector<KDL::Segment> chain_segs = chain.segments;

  urdf::JointConstSharedPtr joint;

  std::vector<double> l_bounds, u_bounds;

  lb.resize(chain.getNrOfJoints());
  ub.resize(chain.getNrOfJoints());

  uint joint_num = 0;
  for (unsigned int i = 0; i < chain_segs.size(); ++i) {
    joint = robot_model.getJoint(chain_segs[i].getJoint().getName());
    if (joint->type != urdf::Joint::UNKNOWN && joint->type != urdf::Joint::FIXED) {
      joint_num++;
      float lower, upper;
      int hasLimits;
      if (joint->type != urdf::Joint::CONTINUOUS) {
        if (joint->safety) {
          lower = std::max(joint->limits->lower, joint->safety->soft_lower_limit);
          upper = std::min(joint->limits->upper, joint->safety->soft_upper_limit);
        } else {
          lower = joint->limits->lower;
          upper = joint->limits->upper;
        }
        hasLimits = 1;
      } else {
        hasLimits = 0;
      }
      if (hasLimits) {
        lb(joint_num - 1) = lower;
        ub(joint_num - 1) = upper;
      } else {
        lb(joint_num - 1) = std::numeric_limits<float>::lowest();
        ub(joint_num - 1) = std::numeric_limits<float>::max();
      }
      RCLCPP_DEBUG_STREAM(
        LOGGER,
        "IK Using joint " << joint->name << " " << lb(joint_num - 1) << " " << ub(joint_num - 1));
    }
  }

  initialize();
  
  task1 = std::thread(&TRAC_IK::runKDL, this);
  task2 = std::thread(&TRAC_IK::runNLOPT, this);  
  
  task1.detach();
  task2.detach();
}


TRAC_IK::TRAC_IK(
  const KDL::Chain & _chain, const KDL::JntArray & _q_min,
  const KDL::JntArray & _q_max, double _maxtime, double _eps, SolveType _type)
: initialized(false),
  chain(_chain),
  lb(_q_min),
  ub(_q_max),
  eps(_eps),
  maxtime(std::chrono::duration<double>(_maxtime)),
  solvetype(_type)
{
  initialize();
  task1 = std::thread(&TRAC_IK::runKDL, this);
  task2 = std::thread(&TRAC_IK::runNLOPT, this);  
  task1.detach();
  task2.detach();
}

void TRAC_IK::initialize()
{
  assert(chain.getNrOfJoints() == lb.data.size());
  assert(chain.getNrOfJoints() == ub.data.size());

  jacsolver.reset(new KDL::ChainJntToJacSolver(chain));
  nl_solver.reset(new NLOPT_IK::NLOPT_IK(chain, lb, ub, maxtime.count(), eps, NLOPT_IK::SumSq));
  iksolver.reset(new KDL::ChainIkSolverPos_TL(chain, lb, ub, maxtime.count(), eps, true, true));

  for (uint i = 0; i < chain.segments.size(); i++) {
    std::string type = chain.segments[i].getJoint().getTypeName();
    if (type.find("Rot") != std::string::npos) {
      if (ub(types.size()) >= std::numeric_limits<float>::max() &&
        lb(types.size()) <= std::numeric_limits<float>::lowest())
      {
        types.push_back(KDL::BasicJointType::Continuous);
      } else {
        types.push_back(KDL::BasicJointType::RotJoint);
      }
    } else if (type.find("Trans") != std::string::npos) {
      types.push_back(KDL::BasicJointType::TransJoint);
    }
  }

  assert(types.size() == static_cast<long unsigned int>(lb.data.size()));  // NOLINT

  initialized = true;
}

bool TRAC_IK::unique_solution(const KDL::JntArray & sol)
{
  for (uint i = 0; i < solutions.size(); i++) {
    if (myEqual(sol, solutions[i])) {
      return false;
    }
  }
  return true;
}

inline void normalizeAngle(double & val, const double & min, const double & max)
{
  if (val > max) {
    // Find actual angle offset
    double diffangle = fmod(val - max, 2 * M_PI);
    // Add that to upper bound and go back a full rotation
    val = max + diffangle - 2 * M_PI;
  }

  if (val < min) {
    // Find actual angle offset
    double diffangle = fmod(min - val, 2 * M_PI);
    // Add that to upper bound and go back a full rotation
    val = min - diffangle + 2 * M_PI;
  }
}

inline void normalizeAngle(double & val, const double & target)
{
  double new_target = target + M_PI;
  if (val > new_target) {
    // Find actual angle offset
    double diffangle = fmod(val - new_target, 2 * M_PI);
    // Add that to upper bound and go back a full rotation
    val = new_target + diffangle - 2 * M_PI;
  }

  new_target = target - M_PI;
  if (val < new_target) {
    // Find actual angle offset
    double diffangle = fmod(new_target - val, 2 * M_PI);
    // Add that to upper bound and go back a full rotation
    val = new_target - diffangle + 2 * M_PI;
  }
}


template<typename T1, typename T2>
bool TRAC_IK::runSolver(
  T1 & solver, T2 & other_solver )
{
  while(true)
  {
    std::unique_lock<std::mutex> lk(mutexWorkers);
    conditionWorkers.wait(lk);
    lk.unlock();
  
  KDL::JntArray q_out;

  std::chrono::duration<double> fulltime(maxtime);
  KDL::JntArray seed = q_init;

  while (true) {

    std::chrono::duration<double> timediff(std::chrono::steady_clock::now() - start_time);

    if (timediff >= fulltime) {
        //RCLCPP_ERROR ( rclcpp::get_logger("track_ik.cpp"),"====> runSolver  FULLTIME REACHED, BREAKING start_time %f timediff %f fulltime %f", start_time,  timediff, fulltime);
        //RCLCPP_ERROR ( rclcpp::get_logger("track_ik.cpp"),"====> runSolver  FULLTIME REACHED, BREAKING ");
      break;
    }

    solver.setMaxtime((fulltime - timediff).count());

    int RC = solver.CartToJnt(seed, p_in_arg, q_out, bounds);
    if (RC >= 0) {
      switch (solvetype) {
        case Manip1:
        case Manip2:
          normalize_limits(q_init, q_out);
          break;
        default:
          normalize_seed(q_init, q_out);
          break;
      }
      mtx_.lock();
      if (unique_solution(q_out)) {
        solutions.push_back(q_out);
        uint curr_size = solutions.size();
        errors.resize(curr_size);
        mtx_.unlock();
        double err, penalty;
        switch (solvetype) {
          case Manip1:
            penalty = manipPenalty(q_out);
            err = penalty * TRAC_IK::ManipValue1(q_out);
            break;
          case Manip2:
            penalty = manipPenalty(q_out);
            err = penalty * TRAC_IK::ManipValue2(q_out);
            break;
          default:
            err = TRAC_IK::JointErr(q_init, q_out);
            break;
        }
        mtx_.lock();
        errors[curr_size - 1] = std::make_pair(err, curr_size - 1);
      }
      mtx_.unlock();
    }

    if (!solutions.empty() && solvetype == Speed) {
      break;
    }

    for (unsigned int j = 0; j < seed.data.size(); j++) {
      if (types[j] == KDL::BasicJointType::Continuous) {
        seed(j) = fRand(q_init(j) - 2 * M_PI, q_init(j) + 2 * M_PI);
      } else {
        seed(j) = fRand(lb(j), ub(j));
      }
    }
  }
  other_solver.abort();

  solver.setMaxtime(fulltime.count());
  notifyFlag = true;
  conditionMain.notify_all();
  }
  return true;
}


void TRAC_IK::normalize_seed(const KDL::JntArray & seed, KDL::JntArray & solution)
{
  // Make sure rotational joint values are within 1 revolution of seed; then
  // ensure joint limits are met.

  for (uint i = 0; i < lb.data.size(); i++) {
    if (types[i] == KDL::BasicJointType::TransJoint) {
      continue;
    }

    double target = seed(i);
    double val = solution(i);

    normalizeAngle(val, target);

    if (types[i] == KDL::BasicJointType::Continuous) {
      solution(i) = val;
      continue;
    }

    normalizeAngle(val, lb(i), ub(i));

    solution(i) = val;
  }
}

void TRAC_IK::normalize_limits(const KDL::JntArray & seed, KDL::JntArray & solution)
{
  // Make sure rotational joint values are within 1 revolution of middle of
  // limits; then ensure joint limits are met.

  for (uint i = 0; i < lb.data.size(); i++) {
    if (types[i] == KDL::BasicJointType::TransJoint) {
      continue;
    }

    double target = seed(i);

    if (types[i] == KDL::BasicJointType::RotJoint && types[i] != KDL::BasicJointType::Continuous) {
      target = (ub(i) + lb(i)) / 2.0;
    }

    double val = solution(i);

    normalizeAngle(val, target);

    if (types[i] == KDL::BasicJointType::Continuous) {
      solution(i) = val;
      continue;
    }

    normalizeAngle(val, lb(i), ub(i));

    solution(i) = val;
  }
}


double TRAC_IK::manipPenalty(const KDL::JntArray & arr)
{
  double penalty = 1.0;
  for (uint i = 0; i < arr.data.size(); i++) {
    if (types[i] == KDL::BasicJointType::Continuous) {
      continue;
    }
    double range = ub(i) - lb(i);
    penalty *= ((arr(i) - lb(i)) * (ub(i) - arr(i)) / (range * range));
  }
  return std::max(0.0, 1.0 - exp(-1 * penalty));
}


double TRAC_IK::ManipValue1(const KDL::JntArray & arr)
{
  KDL::Jacobian jac(arr.data.size());

  jacsolver->JntToJac(arr, jac);

  Eigen::JacobiSVD<Eigen::MatrixXd> svdsolver(jac.data);
  Eigen::MatrixXd singular_values = svdsolver.singularValues();

  double error = 1.0;
  for (unsigned int i = 0; i < singular_values.rows(); ++i) {
    error *= singular_values(i, 0);
  }
  return error;
}

double TRAC_IK::ManipValue2(const KDL::JntArray & arr)
{
  KDL::Jacobian jac(arr.data.size());

  jacsolver->JntToJac(arr, jac);

  Eigen::JacobiSVD<Eigen::MatrixXd> svdsolver(jac.data);
  Eigen::MatrixXd singular_values = svdsolver.singularValues();

  return singular_values.minCoeff() / singular_values.maxCoeff();
}


using namespace std::literals::chrono_literals;
int TRAC_IK::CartToJnt(
  const KDL::JntArray & q_init_arg, const KDL::Frame & p_in, KDL::JntArray & q_out_arg,
  const std::chrono::time_point<std::chrono::steady_clock, std::chrono::duration<double>> start_time_arg,
  const KDL::Twist & _bounds)
{
  if (!initialized) {
    RCLCPP_ERROR(
      LOGGER,
      "TRAC-IK was not properly initialized with a valid chain or limits.  IK cannot proceed");
    return -1;
  }


  nl_solver->reset();
  iksolver->reset();

  solutions.clear();
  errors.clear();

  bounds = _bounds;


  //FIXME:
  q_init = q_init_arg;
  p_in_arg = p_in;
  start_time = start_time_arg;
  notifyFlag = false;



  conditionWorkers.notify_all();
  
  std::unique_lock<std::mutex> lk(mutexMain);
  auto endTime = std::chrono::steady_clock::now() + maxtime;
  //auto endTime = std::chrono::steady_clock::now() + 1ms;
  int counter = 0;
  while(notifyFlag ==false)
  {
    counter ++;
    auto res = conditionMain.wait_until(lk, endTime);
    if (res == std::cv_status::timeout)
    {
        RCLCPP_FATAL(LOGGER,"TIMEOUT in trac_ik waiting for threads!!!");
        break;
    }
    if (notifyFlag == false)
	    RCLCPP_INFO(LOGGER, "SPURIOUS trac_ik waiting for threads, count %d",counter);
  }

  lk.unlock();

  
  if (solutions.empty()) {
    q_out_arg = q_init;
    return -3;
  }

  switch (solvetype) {
    case Manip1:
    case Manip2:
      std::sort(errors.rbegin(), errors.rend());  // rbegin/rend to sort by max
      break;
    default:
      std::sort(errors.begin(), errors.end());
      break;
  }

  q_out_arg = solutions[errors[0].second];

  return solutions.size();
}


TRAC_IK::~TRAC_IK()
{
  if (task1.joinable()) {
    task1.join();
  }
  if (task2.joinable()) {
    task2.join();
  }
}
}  // namespace TRAC_IK
