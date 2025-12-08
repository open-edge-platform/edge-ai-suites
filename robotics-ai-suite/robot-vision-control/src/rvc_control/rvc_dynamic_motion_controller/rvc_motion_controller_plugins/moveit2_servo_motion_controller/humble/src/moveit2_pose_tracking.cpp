/*********************************************************************
 * SPDX-License-Identifier: BSD-3-Clause
 * SPDX-FileCopyrightText: (C) 2020, PickNik Inc.
 * Software License Agreement (BSD License)
 *
 *  Copyright (c) 2020, PickNik Inc.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *   * Neither the name of PickNik Inc. nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 *********************************************************************/

#include "moveit2_servo_motion_controller/moveit2_pose_tracking.hpp"
#include <moveit_servo/servo_parameters.h>

#include <chrono>
//#include <queue>
using namespace std::literals;
using namespace std::chrono_literals;

namespace {
static const rclcpp::Logger LOGGER = rclcpp::get_logger("moveit2_pose_tracking");
constexpr size_t LOG_THROTTLE_PERIOD = 1000;  // sec

// Helper template for declaring and getting ros param
template<typename T>
void declareOrGetParam(
    T & output_value, const std::string & param_name, const rclcpp::Node::SharedPtr & node,
    const rclcpp::Logger & logger, const T default_value = T{})
{
    try
    {
        if (node->has_parameter(param_name))
        {
            node->get_parameter<T>(param_name, output_value);
        }
        else
        {
            output_value = node->declare_parameter<T>(param_name, default_value);
        }
    } catch (const rclcpp::exceptions::InvalidParameterTypeException & e)
    {
        RCLCPP_WARN_STREAM(logger, "InvalidParameterTypeException(" << param_name << "): " << e.what());
        RCLCPP_ERROR_STREAM(
            logger,
            "Error getting parameter \'" << param_name << "\', check parameter type in YAML file");
        throw e;
    }

    RCLCPP_INFO_STREAM(logger, "Found parameter - " << param_name << ": " << output_value);
}

}  // namespace


PoseTracking::PoseTracking(
    const rclcpp::Node::SharedPtr & node, const moveit_servo::ServoParameters::SharedConstPtr & servo_parameters,
    const planning_scene_monitor::PlanningSceneMonitorPtr & planning_scene_monitor)
  : node_(node)
    , servo_parameters_(servo_parameters)
    , publish_period(servo_parameters_->publish_period)
    , planning_scene_monitor_(planning_scene_monitor)
    , loop_rate_(1.0 / publish_period)
    , controllerSpeed(0)    
    , transform_buffer_(node_->get_clock())
    , transform_listener_(transform_buffer_)
    , stop_requested_(false)
    , tfBuffer(node->get_clock(), std::chrono::milliseconds(2))
    , listener(tfBuffer)
    , goalAchieved(false)
    , firstSetTargetReceived(false)
{
    readROSParams();

    robot_model_ = planning_scene_monitor_->getRobotModel();


    // Use the C++ interface that Servo provides
    servo_ = std::make_unique<moveit_servo::Servo>(node_, servo_parameters_, planning_scene_monitor_);
    servo_->start();

    auto qostransientlocal = rclcpp::QoS(
        rclcpp::QoSInitialization::from_rmw(
            rmw_qos_profile_default), rmw_qos_profile_default);
    qostransientlocal.transient_local();


    // Publish outgoing twist commands to the Servo object
    twist_stamped_pub_ = node_->create_publisher<geometry_msgs::msg::TwistStamped>(
        servo_->getParameters()->cartesian_command_in_topic, rclcpp::SystemDefaultsQoS());
    param_subscriber_ = std::make_shared<rclcpp::ParameterEventHandler>(node_);

}

void PoseTracking::setSpeed(const double speed)
{
    controllerSpeed = speed;
    RCLCPP_INFO(node_->get_logger(), "new speed: %f", controllerSpeed);
}

double PoseTracking::getGripperPositionFeedback()
{
    auto current_state_ = planning_scene_monitor_->getStateMonitor()->getCurrentState();
    auto joint_model_group_ = current_state_->getJointModelGroup(gripper_move_group_name_);

    sensor_msgs::msg::JointState internal_joint_state_;
    internal_joint_state_.name = joint_model_group_->getActiveJointModelNames();
    auto num_joints_ = internal_joint_state_.name.size();

    internal_joint_state_.position.resize(num_joints_);
    internal_joint_state_.velocity.resize(num_joints_);

    current_state_->copyJointGroupPositions(joint_model_group_, internal_joint_state_.position);

    for (std::size_t i = 0; i < num_joints_; ++i)
    {
        // A map for the indices of incoming joint commands
        //joint_state_name_map_[internal_joint_state_.name[i]] = i;
        RCLCPP_DEBUG(
            LOGGER, "DEBUG: %s: %s %f", gripper_move_group_name_.c_str(), internal_joint_state_.name[i].c_str(),
            internal_joint_state_.position[i]);
            if (internal_joint_state_.name[i] == gripper_joint_name_)
                return internal_joint_state_.position[i];
    }
    RCLCPP_WARN(LOGGER,
        "Couldnt find gripper joint in moveit config!");
    return -1.0;
}
PoseTrackingStatusCode PoseTracking::moveToPose()
{
    // Reset stop requested flag before starting motions
    stop_requested_ = false;
    const auto start_time = node_->now();
    const auto target_pose_timeout = 1.0;

    while ((!haveRecentTargetPose(target_pose_timeout) || !haveRecentEndEffectorPose(target_pose_timeout)) &&
        ((node_->now() - start_time).seconds() < target_pose_timeout))
    {
        if (servo_->getCommandFrameTransform(command_frame_transform_))
        {
            command_frame_transform_stamp_ = node_->now();
        }

        std::this_thread::sleep_for(1ms);
    }

    while (rclcpp::ok())
    {
        goalAchieved = satisfiesPoseTolerance();

        // Attempt to update robot pose
        //if (servo_->getCommandFrameTransform(command_frame_transform_))
        if (getCommandFrameTransform(command_frame_transform_))
        {
            command_frame_transform_stamp_ = node_->now();
        }

        if (stop_requested_)
        {
            RCLCPP_INFO_STREAM(LOGGER, "Halting servo motion, a stop was requested.");
            doPostMotionReset();
            return PoseTrackingStatusCode::STOP_REQUESTED;
        }

        // Compute servo command from PID controller output and send it to the Servo object, for execution
        if (haveRecentTargetPose(target_pose_timeout) )
        {
            //sanity check!
            if (firstSetTargetReceived)
                twist_stamped_pub_->publish(*calculateTwistCommand());
        }
        else
        {
            RCLCPP_WARN_STREAM_THROTTLE(LOGGER, *node_->get_clock(), LOG_THROTTLE_PERIOD, "NO RECENT TARGET POSE!");
        }

        if (!loop_rate_.sleep())
        {
            //RCLCPP_WARN_STREAM_THROTTLE(LOGGER, *node_->get_clock(), LOG_THROTTLE_PERIOD, "Target control rate was missed");
            RCLCPP_WARN_STREAM(LOGGER, "POSE TRACKING: Target control rate was missed");
        }
    }

    if (!rclcpp::ok())
    {
        RCLCPP_FATAL(LOGGER, "POSE TRACKING: rclcpp is NOT ok!!!");
    }

    doPostMotionReset();
    return PoseTrackingStatusCode::SUCCESS;
}

void PoseTracking::readROSParams()
{
    const std::string ns = "moveit_servo";

    declareOrGetParam(planning_frame_, ns + ".planning_frame", node_, LOGGER);
    declareOrGetParam(manipulator_move_group_name_, ns + ".move_group_name", node_, LOGGER);
    declareOrGetParam(gripper_move_group_name_, ns + ".gripper_move_group_name", node_, LOGGER);
    declareOrGetParam(gripper_joint_name_, ns + ".gripper_joint_name", node_, LOGGER);
    declareOrGetParam(positional_tolerance(0), ns + ".positional_tolerance.x", node_, LOGGER);
    declareOrGetParam(positional_tolerance(1), ns + ".positional_tolerance.y", node_, LOGGER);
    declareOrGetParam(positional_tolerance(2), ns + ".positional_tolerance.z", node_, LOGGER);
    declareOrGetParam(angular_tolerance, ns + ".angular_tolerance", node_, LOGGER);

    if (!planning_scene_monitor_->getRobotModel()->hasJointModelGroup(manipulator_move_group_name_))
    {
        RCLCPP_ERROR_STREAM(LOGGER, "Unable to find the specified joint model group: " << manipulator_move_group_name_);
    }

    double publish_period;
    declareOrGetParam(publish_period, ns + ".publish_period", node_, LOGGER);
    RCLCPP_INFO(LOGGER, "======================> PUBLISH PERIOD %f", publish_period);


    double windup_limit;
    declareOrGetParam(windup_limit, ns + ".windup_limit", node_, LOGGER);

}

bool PoseTracking::haveRecentTargetPose(const double timespan)
{
    std::lock_guard<std::mutex> lock(target_pose_mtx_);
    return (node_->now() - target_pose_.header.stamp).seconds() < timespan;
}

bool PoseTracking::haveRecentEndEffectorPose(const double timespan)
{
    return (node_->now() - command_frame_transform_stamp_).seconds() < timespan;
}

bool PoseTracking::satisfiesPoseTolerance()
{
    std::lock_guard<std::mutex> lock(target_pose_mtx_);
    double x_error = target_pose_.pose.position.x - command_frame_transform_.translation()(0);
    double y_error = target_pose_.pose.position.y - command_frame_transform_.translation()(1);
    double z_error = target_pose_.pose.position.z - command_frame_transform_.translation()(2);

    // If uninitialized, likely haven't received the target pose yet.
    if (!angular_error_)
    {
        RCLCPP_WARN_THROTTLE(node_->get_logger(), *node_->get_clock(), 1000,
         "2 ANGULAR ERROR NOT YET COMPUTED!!!");
        return false;
    }

//RCLCPP_INFO(rclcpp::get_logger("X"), "ERRORS: %f %f %f %f ", x_error,y_error,z_error, angular_error_);

    return (std::abs(x_error) < positional_tolerance(0)) && (std::abs(y_error) < positional_tolerance(1)) &&
           (std::abs(z_error) < positional_tolerance(2)) && (std::abs(*angular_error_) < angular_tolerance);
}

void PoseTracking::setTargetPose(const geometry_msgs::msg::PoseStamped::ConstSharedPtr & msg)
{
    firstSetTargetReceived = true;

    std::lock_guard<std::mutex> lock(target_pose_mtx_);
    target_pose_ = *msg;

    if (!angular_error_)
    {
        RCLCPP_WARN(rclcpp::get_logger("X"), "1 ANGULAR ERROR NOT YET COMPUTED!!!");
        goalAchieved = false;
    }
    else
    {
        // recompute goalAchieved, as setTargetPose is called every cycle
        double x_error = target_pose_.pose.position.x - command_frame_transform_.translation()(0);
        double y_error = target_pose_.pose.position.y - command_frame_transform_.translation()(1);
        double z_error = target_pose_.pose.position.z - command_frame_transform_.translation()(2);

        goalAchieved = (std::abs(x_error) < positional_tolerance(0)) && (std::abs(y_error) < positional_tolerance(1)) &&
            (std::abs(z_error) < positional_tolerance(2)) && (std::abs(*angular_error_) < angular_tolerance);    
    }
    

    // If the target pose is not defined in planning frame, transform the target pose.
    if (target_pose_.header.frame_id != planning_frame_)
    {
        try
        {
            geometry_msgs::msg::TransformStamped target_to_planning_frame = transform_buffer_.lookupTransform(
                planning_frame_, target_pose_.header.frame_id, rclcpp::Time(0), rclcpp::Duration(100ms));
            tf2::doTransform(target_pose_, target_pose_, target_to_planning_frame);

            // Prevent doTransform from copying a stamp of 0, which will cause the haveRecentTargetPose check to fail servo motions
            target_pose_.header.stamp = node_->now();
        } catch (const tf2::TransformException & ex)
        {
            RCLCPP_WARN_STREAM(LOGGER, ex.what());
            return;
        }
    }
}

geometry_msgs::msg::TwistStamped::ConstSharedPtr PoseTracking::calculateTwistCommand()
{
    // use the shared pool to create a message more efficiently
    auto msg = moveit::util::make_shared_from_pool<geometry_msgs::msg::TwistStamped>();

    // Get twist components from PID controllers
    geometry_msgs::msg::Twist & twist = msg->twist;
    Eigen::Quaterniond q_desired;

    tf2::Vector3 trans2;

    double w, x, y, z;

    // Scope mutex locking only to operations which require access to target pose.
    {
        std::lock_guard<std::mutex> lock(target_pose_mtx_);
        msg->header.frame_id = target_pose_.header.frame_id;
        trans2 = {target_pose_.pose.position.x, target_pose_.pose.position.y, target_pose_.pose.position.z};
        w = target_pose_.pose.orientation.w;
        x = target_pose_.pose.orientation.x;
        y = target_pose_.pose.orientation.y;
        z = target_pose_.pose.orientation.z;
    }
    Eigen::Quaterniond rot2 = {w, x, y, z};
    tf2::Vector3 trans1 =
    {command_frame_transform_.translation()(0), command_frame_transform_.translation()(1),
        command_frame_transform_.translation()(2)};
    auto distance = trans1.distance(trans2);

    double timeperiod = publish_period; //0.002;

    double alpha = 0.0;

    if (controllerSpeed < 0.2)
    {
        RCLCPP_INFO(LOGGER, " WARNING!!! < 0.2 ! setting to 1 controllerSpeed %f", controllerSpeed);
        controllerSpeed = 1.0;
    }

    // \frac{\left(\left(\arctan\left(1-x\right)\right)+1.57\right)}{1.57\cdot\frac{3}{2}}
    alpha = (atan(1.0 - distance * controllerSpeed * 10.0) + M_PI_2) / (M_PI_2 * 3.0 / 2.0);
    //alpha = 1.0 - distance * controllerSpeed * 10.0;

    Eigen::Quaterniond rot1(command_frame_transform_.rotation());

    tf2::Vector3 resTranslation = (1.0 - alpha) * trans1 + alpha * trans2;

    alpha = (atan(1.0 - distance * controllerSpeed * 5.0) + M_PI_2) / (M_PI_2 * 3.0 / 2.0);
    Eigen::Quaterniond resOrientation = rot1.slerp(alpha, rot2);
    resOrientation = resOrientation * command_frame_transform_.rotation().inverse();

    twist.linear.x = (resTranslation[0] - trans1[0]) / timeperiod;
    twist.linear.y = (resTranslation[1] - trans1[1]) / timeperiod;
    twist.linear.z = (resTranslation[2] - trans1[2]) / timeperiod;

    Eigen::AngleAxisd axis_angle(resOrientation);
    twist.angular.x = axis_angle.angle() * axis_angle.axis()[0] / timeperiod;
    twist.angular.y = axis_angle.angle() * axis_angle.axis()[1] / timeperiod;
    twist.angular.z = axis_angle.angle() * axis_angle.axis()[2] / timeperiod;
    angular_error_ = axis_angle.angle();

//RCLCPP_INFO(rclcpp::get_logger("O"), "angle %f axis %f period %f alpha %f", axis_angle.angle(), axis_angle.axis()[0], timeperiod, alpha);
    msg->header.stamp = node_->now();

    return msg;
}

void PoseTracking::stopMotion()
{
    stop_requested_ = true;

    // Send a 0 command to Servo to halt arm motion
    auto msg = moveit::util::make_shared_from_pool<geometry_msgs::msg::TwistStamped>();
    {
        std::lock_guard<std::mutex> lock(target_pose_mtx_);
        msg->header.frame_id = target_pose_.header.frame_id;
    }
    msg->header.stamp = node_->now();
    twist_stamped_pub_->publish(*msg);
}

void PoseTracking::doPostMotionReset()
{
    stopMotion();
    stop_requested_ = false;
    angular_error_ = {};
}

void PoseTracking::resetTargetPose()
{
    std::lock_guard<std::mutex> lock(target_pose_mtx_);
    target_pose_ = geometry_msgs::msg::PoseStamped();
    target_pose_.header.stamp = rclcpp::Time(RCL_ROS_TIME);
}

bool PoseTracking::getCommandFrameTransform(Eigen::Isometry3d & transform)
{
    auto robot_link_command_frame_ = servo_parameters_->ee_frame_name;
    auto planning_frame = servo_parameters_->planning_frame;

    auto current_state_ = planning_scene_monitor_->getStateMonitor()->getCurrentState();
    transform = current_state_->getGlobalLinkTransform(planning_frame).inverse() *
        current_state_->getGlobalLinkTransform(robot_link_command_frame_);
    return true;
}
