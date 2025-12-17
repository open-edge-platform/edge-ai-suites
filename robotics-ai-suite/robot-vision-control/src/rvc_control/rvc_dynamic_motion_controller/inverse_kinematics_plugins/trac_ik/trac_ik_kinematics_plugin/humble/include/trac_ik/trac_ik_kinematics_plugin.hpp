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

#ifndef TRAC_IK_KINEMATICS_PLUGIN_
#define TRAC_IK_KINEMATICS_PLUGIN_

#include <moveit/kinematics_base/kinematics_base.h>
#include <kdl/chain.hpp>

namespace trac_ik_kinematics_plugin
{

class TRAC_IKKinematicsPlugin : public kinematics::KinematicsBase
{
  std::vector<std::string> joint_names_;
  std::vector<std::string> link_names_;

  uint num_joints_;
  bool active_; // Internal variable that indicates whether solvers are configured and ready

  KDL::Chain chain;
  bool position_ik_;

  KDL::JntArray joint_min, joint_max;

  std::string solve_type;

public:
  virtual const std::vector<std::string>& getJointNames() const
  {
    return joint_names_;
  }
  virtual const std::vector<std::string>& getLinkNames() const
  {
    return link_names_;
  }


  /** @class
   *  @brief Interface for an TRAC-IK kinematics plugin
   */
  TRAC_IKKinematicsPlugin(): num_joints_(6), active_(false), position_ik_(false), joint_model_group(NULL)  {}

  ~TRAC_IKKinematicsPlugin()
  {
  }

  /**
   * @brief Given a desired pose of the end-effector, compute the joint angles to reach it
   * @param ik_pose the desired pose of the link
   * @param ik_seed_state an initial guess solution for the inverse kinematics
   * @param solution the solution vector
   * @param error_code an error code that encodes the reason for failure or success
   * @return True if a valid solution was found, false otherwise
   */

  // Returns the first IK solution that is within joint limits, this is called by get_ik() service
  virtual bool getPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                     const std::vector<double> &ik_seed_state,
                     std::vector<double> &solution,
                     moveit_msgs::msg::MoveItErrorCodes &error_code,
                     const kinematics::KinematicsQueryOptions &options = kinematics::KinematicsQueryOptions()) const;

  /**
   * @brief Given a desired pose of the end-effector, search for the joint angles required to reach it.
   * This particular method is intended for "searching" for a solutions by stepping through the redundancy
   * (or other numerical routines).
   * @param ik_pose the desired pose of the link
   * @param ik_seed_state an initial guess solution for the inverse kinematics
   * @return True if a valid solution was found, false otherwise
   */
   virtual bool searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                        const std::vector<double> &ik_seed_state,
                        double timeout,
                        std::vector<double> &solution,
                        moveit_msgs::msg::MoveItErrorCodes &error_code,
                        const kinematics::KinematicsQueryOptions &options = kinematics::KinematicsQueryOptions()) const;

  /**
   * @brief Given a desired pose of the end-effector, search for the joint angles required to reach it.
   * This particular method is intended for "searching" for a solutions by stepping through the redundancy
   * (or other numerical routines).
   * @param ik_pose the desired pose of the link
   * @param ik_seed_state an initial guess solution for the inverse kinematics
   * @param the distance that the redundancy can be from the current position
   * @return True if a valid solution was found, false otherwise
   */
  virtual bool searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                        const std::vector<double> &ik_seed_state,
                        double timeout,
                        const std::vector<double> &consistency_limits,
                        std::vector<double> &solution,
                        moveit_msgs::msg::MoveItErrorCodes &error_code,
                        const kinematics::KinematicsQueryOptions &options = kinematics::KinematicsQueryOptions()) const;

  /**
   * @brief Given a desired pose of the end-effector, search for the joint angles required to reach it.
   * This particular method is intended for "searching" for a solutions by stepping through the redundancy
   * (or other numerical routines).
   * @param ik_pose the desired pose of the link
   * @param ik_seed_state an initial guess solution for the inverse kinematics
   * @return True if a valid solution was found, false otherwise
   */
  virtual bool searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                        const std::vector<double> &ik_seed_state,
                        double timeout,
                        std::vector<double> &solution,
                        const IKCallbackFn &solution_callback,
                        moveit_msgs::msg::MoveItErrorCodes &error_code,
                        const kinematics::KinematicsQueryOptions &options = kinematics::KinematicsQueryOptions()) const;

  /**
   * @brief Given a desired pose of the end-effector, search for the joint angles required to reach it.
   * This particular method is intended for "searching" for a solutions by stepping through the redundancy
   * (or other numerical routines).  The consistency_limit specifies that only certain redundancy positions
   * around those specified in the seed state are admissible and need to be searched.
   * @param ik_pose the desired pose of the link
   * @param ik_seed_state an initial guess solution for the inverse kinematics
   * @param consistency_limit the distance that the redundancy can be from the current position
   * @return True if a valid solution was found, false otherwise
   */
  virtual bool searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                        const std::vector<double> &ik_seed_state,
                        double timeout,
                        const std::vector<double> &consistency_limits,
                        std::vector<double> &solution,
                        const IKCallbackFn &solution_callback,
                        moveit_msgs::msg::MoveItErrorCodes &error_code,
                        const kinematics::KinematicsQueryOptions &options = kinematics::KinematicsQueryOptions()) const;

  virtual bool searchPositionIK(const geometry_msgs::msg::Pose &ik_pose,
                        const std::vector<double> &ik_seed_state,
                        double timeout,
                        std::vector<double> &solution,
                        const IKCallbackFn &solution_callback,
                        moveit_msgs::msg::MoveItErrorCodes &error_code,
                        const std::vector<double> &consistency_limits,
                        const kinematics::KinematicsQueryOptions &options) const;


  /**
   * @brief Given a set of joint angles and a set of links, compute their pose
   *
   * This FK routine is only used if 'use_plugin_fk' is set in the 'arm_kinematics_constraint_aware' node,
   * otherwise ROS TF is used to calculate the forward kinematics
   *
   * @param link_names A set of links for which FK needs to be computed
   * @param joint_angles The state for which FK is being computed
   * @param poses The resultant set of poses (in the frame returned by getBaseFrame())
   * @return True if a valid solution was found, false otherwise
   */
  virtual bool getPositionFK(const std::vector<std::string> &link_names,
                     const std::vector<double> &joint_angles,
                     std::vector<geometry_msgs::msg::Pose> &poses) const;

  virtual bool initialize(const rclcpp::Node::SharedPtr &node,
    const moveit::core::RobotModel &robot_model,
    const std::string& group_name,
    const std::string& base_name,
    const std::vector<std::string> &tip_frames,
    double search_discretization);

  virtual bool supportsGroup(const moveit::core::JointModelGroup *,
                             std::string *error_text_out = 0) const 
  {
    (void)error_text_out;
    return true;
  }

private:
  template <class T>
  void getRosParam(const std::string &param, T &val, const T &default_val)
  {
    const std::string prefix = "robot_description_kinematics." + group_name_ + ".";
    if (!node_->has_parameter(prefix + param))
    {
      val = node_->declare_parameter(prefix + param, rclcpp::ParameterValue{default_val}).get<T>();
      return;
    }
    val = node_->get_parameter(prefix + param).get_value<T>();
  }

  const moveit::core::JointModelGroup *joint_model_group;
  int getKDLSegmentIndex(const std::string &name) const;
  std::shared_ptr<TRAC_IK::TRAC_IK> ik_solver;

}; // end class
}

#endif
