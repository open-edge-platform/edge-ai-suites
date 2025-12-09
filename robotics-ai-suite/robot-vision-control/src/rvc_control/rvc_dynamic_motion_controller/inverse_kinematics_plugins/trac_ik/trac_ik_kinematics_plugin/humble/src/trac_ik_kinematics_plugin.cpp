/********************************************************************************
SPDX-License-Identifier: BSD-3-Clause
SPDX-FileCopyrightText: (C) 2015 TRACLabs, Inc.
Copyright (c) 2015, TRACLabs, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
 are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.

    3. Neither the name of the copyright holder nor the names of its contributors
       may be used to endorse or promote products derived from this software
       without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
********************************************************************************/

#include "rclcpp/rclcpp.hpp"

#include <moveit/kinematics_base/kinematics_base.h>
#include <moveit/robot_model/robot_model.h>
#include <moveit/robot_state/robot_state.h>
#include <urdf/model.h>
#include <algorithm>
#include <kdl/tree.hpp>
#include <kdl_parser/kdl_parser.hpp>
#include <trac_ik/trac_ik.hpp>
#include <trac_ik/trac_ik_kinematics_plugin.hpp>
#include <limits>

#include <tf2_ros/transform_listener.h>
#include <tf2_eigen/tf2_eigen.hpp>
#include <tf2_kdl/tf2_kdl.hpp>

namespace trac_ik_kinematics_plugin
{

bool TRAC_IKKinematicsPlugin::initialize(const rclcpp::Node::SharedPtr &node,
    const moveit::core::RobotModel &robot_model,
    const std::string& group_name,
    const std::string& base_name,
    const std::vector<std::string> &tip_frames,
    double search_discretization)
{
 

  node_ = node;
  storeValues(robot_model, group_name, base_name, tip_frames, search_discretization);
    joint_model_group = robot_model_->getJointModelGroup(group_name);
    if (!joint_model_group) {
      RCLCPP_ERROR(node_->get_logger(),"TRAC_IK PLUGIN failed to get joint model group");
      return false;
    }


  std::string tip_name = tip_frames[0];

  RCLCPP_INFO_STREAM(rclcpp::get_logger("trac_ik"), "Reading joints and links from URDF");

  KDL::Tree tree;

  auto urdfptr = robot_model_->getURDF();
  if (!kdl_parser::treeFromUrdfModel(*urdfptr, tree))
  {
    RCLCPP_FATAL(node_->get_logger(),"Failed to extract kdl tree from xml robot description");
    return false;
  }

  if (!tree.getChain(base_name, tip_name, chain))
  {
     RCLCPP_FATAL(node_->get_logger(),"Couldn't find chain %s to %s", base_name.c_str(), tip_name.c_str());
    return false;
  }
  num_joints_ = chain.getNrOfJoints();

  std::vector<KDL::Segment> chain_segs = chain.segments;

  urdf::JointConstSharedPtr joint;

  std::vector<double> l_bounds, u_bounds;

  joint_min.resize(num_joints_);
  joint_max.resize(num_joints_);
    joint_names_.clear();

  uint joint_num = 0;
    for (auto *joint_model : joint_model_group->getJointModels())
    {
        float lower, upper;
      RCLCPP_INFO(node_->get_logger(),"joint name %s",joint_model->getName().c_str());
      if (joint_model->getName() != base_frame_ &&
          joint_model->getType() != moveit::core::JointModel::UNKNOWN &&
          joint_model->getType() != moveit::core::JointModel::FIXED)
      {
        joint_names_.push_back(joint_model->getName());
      RCLCPP_INFO(node_->get_logger(),"joint name %s ADDED",joint_model->getName().c_str());
      auto bounds = joint_model->getVariableBounds();
      lower = bounds[0].min_position_;
      upper = bounds[0].max_position_;
      RCLCPP_INFO(node_->get_logger(),"joint name %s lower %f upper %f" , joint_model->getName().c_str(), lower, upper);

        joint_min(joint_num) = lower;
        joint_max(joint_num) = upper;
        joint_num++;

      }
    }

    num_joints_ = joint_names_.size();

    for (auto *link_model : robot_model_->getLinkModels())
    {
      RCLCPP_INFO(node_->get_logger(),"link name %s",link_model->getName().c_str());
      link_names_.push_back(link_model->getName());
    }

#if 0
  for (unsigned int i = 0; i < chain_segs.size(); ++i)
  {

    link_names_.push_back(chain_segs[i].getName());
    joint = robot_model.getJoint(chain_segs[i].getJoint().getName());
    if (joint->type != urdf::Joint::UNKNOWN && joint->type != urdf::Joint::FIXED)
    {
      joint_num++;
      assert(joint_num <= num_joints_);
      float lower, upper;
      int hasLimits;
      joint_names_.push_back(joint->name);
      if (joint->type != urdf::Joint::CONTINUOUS)
      {
        if (joint->safety)
        {
          lower = std::max(joint->limits->lower, joint->safety->soft_lower_limit);
          upper = std::min(joint->limits->upper, joint->safety->soft_upper_limit);
        }
        else
        {
          lower = joint->limits->lower;
          upper = joint->limits->upper;
        }
        hasLimits = 1;
      }
      else
      {
        hasLimits = 0;
      }
      if (hasLimits)
      {
        joint_min(joint_num - 1) = lower;
        joint_max(joint_num - 1) = upper;
      }
      else
      {
        joint_min(joint_num - 1) = std::numeric_limits<float>::lowest();
        joint_max(joint_num - 1) = std::numeric_limits<float>::max();
      }
      RCLCPP_INFO_STREAM(rclcpp::get_logger("IK Using joint "), chain_segs[i].getName() << " " << joint_min(joint_num - 1) << " " << joint_max(joint_num - 1));
    }
  }
#endif


  getRosParam("position_only_ik", position_ik_, false);
  RCLCPP_INFO(rclcpp::get_logger("trac_ik plugin"), "Position only IK: %d", position_ik_);
  getRosParam("solve_type", solve_type, std::string("Speed"));
  RCLCPP_INFO(rclcpp::get_logger("trac_ik plugin"), "Using solve type %s", solve_type.c_str());

  double epsilon = 1e-5;  //Same as MoveIt's KDL plugin

  TRAC_IK::SolveType solvetype;

  if (solve_type == "Manipulation1")
    solvetype = TRAC_IK::Manip1;
  else if (solve_type == "Manipulation2")
    solvetype = TRAC_IK::Manip2;
  else if (solve_type == "Distance")
    solvetype = TRAC_IK::Distance;
  else
  {
    if (solve_type != "Speed")
    {
      RCLCPP_WARN_STREAM(rclcpp::get_logger("trac_ik"), solve_type << " is not a valid solve_type; setting to default: Speed");
    }
    solvetype = TRAC_IK::Speed;
  }

float timeout = 0.0017;
  ik_solver = std::make_shared<TRAC_IK::TRAC_IK>(chain, joint_min, joint_max, timeout, epsilon, solvetype);

  active_ = true;
  return active_;
}


int TRAC_IKKinematicsPlugin::getKDLSegmentIndex(const std::string &name) const
{
  int i = 0;
  while (i < (int)chain.getNrOfSegments())
  {
    if (chain.getSegment(i).getName() == name)
    {
      return i + 1;
    }
    i++;
  }
  return -1;
}


bool TRAC_IKKinematicsPlugin::getPositionFK(const std::vector<std::string> &link_names,
    const std::vector<double> &joint_angles,
    std::vector<geometry_msgs::msg::Pose> &poses) const
{
  if (!active_)
  {
    RCLCPP_ERROR(rclcpp::get_logger("trac_ik"), "kinematics not active");
    return false;
  }
  poses.resize(link_names.size());
  if (joint_angles.size() != num_joints_)
  {
    RCLCPP_ERROR(rclcpp::get_logger("trac_ik"), "Joint angles vector must have size: %d", num_joints_);
    return false;
  }

  KDL::Frame p_out;
  geometry_msgs::msg::PoseStamped pose;
//  tf::Stamped<tf::Pose> tf_pose;

  KDL::JntArray jnt_pos_in(num_joints_);
  for (unsigned int i = 0; i < num_joints_; i++)
  {
    jnt_pos_in(i) = joint_angles[i];
  }

  KDL::ChainFkSolverPos_recursive fk_solver(chain);

  bool valid = true;
  for (unsigned int i = 0; i < poses.size(); i++)
  {
    RCLCPP_INFO(rclcpp::get_logger("trac_ik"), "End effector index: %d", getKDLSegmentIndex(link_names[i]));
    if (fk_solver.JntToCart(jnt_pos_in, p_out, getKDLSegmentIndex(link_names[i])) >= 0)
    {
//    tf2::poseKDLToMsg(p_out, poses[i]);
     poses[i] = tf2::toMsg(p_out);
    }
    else
    {
      RCLCPP_ERROR(rclcpp::get_logger("trac_ik"), "Could not compute FK for %s", link_names[i].c_str());
      valid = false;
    }
  }

  return valid;
}


bool TRAC_IKKinematicsPlugin::getPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    std::vector<double> &solution,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const kinematics::KinematicsQueryOptions &options) const
{
  const IKCallbackFn solution_callback = 0;
  std::vector<double> consistency_limits;

  return searchPositionIK(ik_pose,
                          ik_seed_state,
                          default_timeout_,
                          solution,
                          solution_callback,
                          error_code,
                          consistency_limits,
                          options);
}

bool TRAC_IKKinematicsPlugin::searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    double timeout,
    std::vector<double> &solution,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const kinematics::KinematicsQueryOptions &options) const
{
  const IKCallbackFn solution_callback = 0;
  std::vector<double> consistency_limits;

  return searchPositionIK(ik_pose,
                          ik_seed_state,
                          timeout,
                          solution,
                          solution_callback,
                          error_code,
                          consistency_limits,
                          options);
}

bool TRAC_IKKinematicsPlugin::searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    double timeout,
    const std::vector<double> &consistency_limits,
    std::vector<double> &solution,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const kinematics::KinematicsQueryOptions &options) const
{
  const IKCallbackFn solution_callback = 0;
  return searchPositionIK(ik_pose,
                          ik_seed_state,
                          timeout,
                          solution,
                          solution_callback,
                          error_code,
                          consistency_limits,
                          options);
}

bool TRAC_IKKinematicsPlugin::searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    double timeout,
    std::vector<double> &solution,
    const IKCallbackFn &solution_callback,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const kinematics::KinematicsQueryOptions &options) const
{
  std::vector<double> consistency_limits;
  return searchPositionIK(ik_pose,
                          ik_seed_state,
                          timeout,
                          solution,
                          solution_callback,
                          error_code,
                          consistency_limits,
                          options);
}

bool TRAC_IKKinematicsPlugin::searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    double timeout,
    const std::vector<double> &consistency_limits,
    std::vector<double> &solution,
    const IKCallbackFn &solution_callback,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const kinematics::KinematicsQueryOptions &options) const
{
  return searchPositionIK(ik_pose,
                          ik_seed_state,
                          timeout,
                          solution,
                          solution_callback,
                          error_code,
                          consistency_limits,
                          options);
}

bool TRAC_IKKinematicsPlugin::searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
    const std::vector<double> &ik_seed_state,
    double timeout,
    std::vector<double> &solution,
    const IKCallbackFn &solution_callback,
    moveit_msgs::msg::MoveItErrorCodes &error_code,
    const std::vector<double> &consistency_limits,
    const kinematics::KinematicsQueryOptions &options) const
{
//  RCLCPP_INFO(rclcpp::get_logger("trac_ik"), "searchPositionIK. timeout %f",timeout);
  (void)timeout;
  (void)consistency_limits;
  (void)options;
  
  if (!active_)
  {
    RCLCPP_ERROR(rclcpp::get_logger("tracikplug"),"kinematics not active");
    error_code.val = error_code.NO_IK_SOLUTION;
    return false;
  }

  if (ik_seed_state.size() != num_joints_)
  {
    RCLCPP_ERROR_STREAM(rclcpp::get_logger("trac_ik"), "Seed state must have size " << num_joints_ << " instead of size " << ik_seed_state.size());
    error_code.val = error_code.NO_IK_SOLUTION;
    return false;
  }

  KDL::Frame frame;
  tf2::fromMsg(ik_pose, frame);

  KDL::JntArray in(num_joints_), out(num_joints_);

  for (uint z = 0; z < num_joints_; z++)
    in(z) = ik_seed_state[z];

  KDL::Twist bounds = KDL::Twist::Zero();

  if (position_ik_)
  {
    bounds.rot.x(std::numeric_limits<float>::max());
    bounds.rot.y(std::numeric_limits<float>::max());
    bounds.rot.z(std::numeric_limits<float>::max());
  }

    auto start_time = std::chrono::time_point<std::chrono::steady_clock, std::chrono::duration<double>>(                                                                                     
        std::chrono::steady_clock::now());    
  int rc = ik_solver->CartToJnt(in, frame, out,start_time, bounds);


  solution.resize(num_joints_);

  if (rc >= 0)
  {
    for (uint z = 0; z < num_joints_; z++)
      solution[z] = out(z);
    // check for collisions if a callback is provided
    if (solution_callback)
    {
      solution_callback(ik_pose, solution, error_code);
      if (error_code.val == moveit_msgs::msg::MoveItErrorCodes::SUCCESS)
      {
        RCLCPP_INFO_STREAM(rclcpp::get_logger("trac_ik"), "Solution passes callback");
        return true;
      }
      else
      {
        RCLCPP_INFO_STREAM(rclcpp::get_logger("trac_ik"), "Solution has error code ");
        return false;
      }
    }
    else
    {
      return true; // no collision check callback provided
    }
  }

  error_code.val = moveit_msgs::msg::MoveItErrorCodes::NO_IK_SOLUTION;
  return false;
}

} // end namespace

//register TRAC_IKKinematicsPlugin as a KinematicsBase implementation
#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(trac_ik_kinematics_plugin::TRAC_IKKinematicsPlugin, kinematics::KinematicsBase);

