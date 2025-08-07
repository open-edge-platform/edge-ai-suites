// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include <thread>

#include <algorithm>
#include "moveit2_servo_motion_controller/moveit2_servo_motion_controller.hpp"

static bool exitApp = false;

static const rclcpp::Logger LOGGER = rclcpp::get_logger ( "moveit_servo.pose_tracking_demo" );
using namespace std::chrono_literals;
using namespace std::chrono;


namespace RVCMotionController
{

void Moveit2ServoMotionController::statusCB ( const std_msgs::msg::Int8::ConstSharedPtr msg )
{
    moveit_servo::StatusCode latest_status = static_cast<moveit_servo::StatusCode> ( msg->data );
    if ( latest_status != status_ ) {
        status_ = latest_status;
        const auto& status_str = moveit_servo::SERVO_STATUS_CODE_MAP.at ( status_ );
        RCLCPP_INFO_STREAM ( LOGGER, "Servo status: " << status_str );
    }
}


moveit_msgs::msg::CollisionObject createCollisionBox ( std::string name, float dimx,float dimy, float dimz, float posx, float posy, float posz )
{
    moveit_msgs::msg::CollisionObject collision_object;
    collision_object.header.frame_id = "world";
    collision_object.id = std::move(name);
    shape_msgs::msg::SolidPrimitive primitive;

    // Define the size of the box in meters
    primitive.type = primitive.BOX;
    primitive.dimensions.resize ( 3 );
    primitive.dimensions[primitive.BOX_X] = dimx;
    primitive.dimensions[primitive.BOX_Y] = dimy;
    primitive.dimensions[primitive.BOX_Z] = dimz;

    // Define the pose of the box (relative to the frame_id)
    geometry_msgs::msg::Pose box_pose;
    box_pose.orientation.w = 1.0;
    box_pose.position.x = posx;
    box_pose.position.y = posy;
    box_pose.position.z = posz;

    collision_object.primitives.push_back ( primitive );
    collision_object.primitive_poses.push_back ( box_pose );
    collision_object.operation = collision_object.ADD;

    return collision_object;
}

Moveit2ServoMotionController::Moveit2ServoMotionController ( )
    : initialized(false)
{
}

bool Moveit2ServoMotionController::init ( rclcpp::Node::SharedPtr node )
{
    auto res = RVCMotionControllerInterface::init(node);

    auto servo_parameters = moveit_servo::ServoParameters::makeServoParameters ( node );

    if ( servo_parameters == nullptr ) {
        RCLCPP_FATAL ( LOGGER, "Could not get servo parameters!" );
        return false;
    }

    // Load the planning scene monitor
    planning_scene_monitor::PlanningSceneMonitorPtr planning_scene_monitor =
        std::make_shared<planning_scene_monitor::PlanningSceneMonitor> ( node, "robot_description" );

    if ( !planning_scene_monitor->getPlanningScene() ) {
        RCLCPP_ERROR_STREAM ( LOGGER, "Error in setting up the PlanningSceneMonitor." );
        return false;
    }

    planning_scene_monitor->providePlanningSceneService();
    planning_scene_monitor->startSceneMonitor();
    //planning_scene_monitor->startSceneMonitor("monitored_planning_scene");
    planning_scene_monitor->startWorldGeometryMonitor (
        planning_scene_monitor::PlanningSceneMonitor::DEFAULT_COLLISION_OBJECT_TOPIC,
        planning_scene_monitor::PlanningSceneMonitor::DEFAULT_PLANNING_SCENE_WORLD_TOPIC,
        false /* skip octomap monitor */ );

    RCLCPP_ERROR ( LOGGER, " TOPIC: %s",servo_parameters->joint_topic.c_str() );
    RCLCPP_ERROR ( LOGGER, " COMMAND OUT TOPIC: %s",servo_parameters->command_out_topic.c_str() );
    planning_scene_monitor->startStateMonitor ( servo_parameters->joint_topic );

    planning_scene_monitor->setPlanningScenePublishingFrequency ( 60 );
    planning_scene_monitor->setStateUpdateFrequency ( 60 );
    planning_scene_monitor->providePlanningSceneService();
    planning_scene_monitor->startPublishingPlanningScene ( planning_scene_monitor::PlanningSceneMonitor::UPDATE_SCENE );

    // Wait for Planning Scene Monitor to setup
    if ( !planning_scene_monitor->waitForCurrentRobotState ( node->now(), 5.0 /* seconds */ ) ) {
        RCLCPP_ERROR_STREAM ( LOGGER, "Error waiting for current robot state in PlanningSceneMonitor." );
        return false;
    }


    moveit_msgs::msg::PlanningScene planning_scene;
    node->declare_parameter<std::vector<std::string>>("collision_boxes", std::vector<std::string>());
    auto collision_boxes = node->get_parameter("collision_boxes").as_string_array();

    std::vector<moveit_msgs::msg::CollisionObject> collision_objects;

    for (auto it = begin (collision_boxes); it != end (collision_boxes); ++it) 
    {
        RCLCPP_ERROR( LOGGER, "============> DECLARING %s ", it->c_str());
        node->declare_parameter<std::vector<double>>(*it, std::vector<double>());
        std::vector<double> box3d =  node->get_parameter(*it).as_double_array();

        collision_objects.push_back ( 
            createCollisionBox (*it, box3d.at(0),box3d.at(1),box3d.at(2),box3d.at(3),box3d.at(4),box3d.at(5)));

    }

    planning_scene.world.collision_objects = std::move(collision_objects);

    planning_scene.is_diff = true;
    planning_scene_monitor->newPlanningSceneMessage ( planning_scene );



    poseTracker = std::make_unique<PoseTracking> ( node, servo_parameters, planning_scene_monitor ),

    sub_ = node->create_subscription<std_msgs::msg::Int8> ( servo_parameters->status_topic, 1, std::bind ( &Moveit2ServoMotionController::statusCB, this, std::placeholders::_1 ) );

    robot_model_loader::RobotModelLoader robot_model_loader ( node, "robot_description" );
    auto kinematic_model = robot_model_loader.getModel();
    RCLCPP_INFO ( LOGGER,"Model frame: %s", kinematic_model->getModelFrame().c_str() );

    kinematic_state = std::make_shared<moveit::core::RobotState> ( kinematic_model );

    kinematic_state->setToDefaultValues();

    // resetTargetPose() can be used to clear the target pose and wait for a new one, e.g. when moving between multiple
    // waypoints
    poseTracker->resetTargetPose();

    // Publish target pose
    currentPose.header.stamp = node->now();

    if ( move_to_pose_thread == nullptr )
    {
        move_to_pose_thread = std::make_shared<std::thread> ( [this] 
        {
            pthread_t this_thread = pthread_self();
            pthread_setname_np(this_thread, "PSmove");
            struct sched_param params;
            params.sched_priority = 90;
            int policy;

            int ret = pthread_setschedparam(this_thread, SCHED_FIFO, &params);
            if (ret != 0)
            {
                RCLCPP_ERROR(node_->get_logger(), "Failure setting thread realtime priority. Error code: %d", ret);
            }


            ret = pthread_getschedparam(this_thread, &policy, &params);
            if (ret != 0)
                RCLCPP_ERROR(node_->get_logger(),"moveToPose Couldn't retrieve scheduling parameters");

          // Check the correct policy was applied
            if (policy != SCHED_FIFO)
                RCLCPP_ERROR(node_->get_logger(),"moveToPose: Scheduling is NOT SCHED_FIFO!");
            else
                RCLCPP_ERROR(node_->get_logger(),"moveToPose: SCHED_FIFO OK, priority %i", params.sched_priority);

            while ( !exitApp )
            {
                PoseTrackingStatusCode tracking_status = poseTracker->moveToPose ();
                //RCLCPP_INFO_STREAM_THROTTLE ( node_->get_logger(), *node_->get_clock(), 1000,"Pose tracker exited with status: " <<         POSE_TRACKING_STATUS_CODE_MAP.at ( tracking_status ) );
                RCLCPP_INFO_STREAM ( node_->get_logger(),"Pose tracker exited with status: " << POSE_TRACKING_STATUS_CODE_MAP.at ( tracking_status ) );
                return;
            }
            RCLCPP_INFO ( node_->get_logger(), "moveToPose thread exiting..." );
        } );
    }
#if 1
        auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_default), rmw_qos_profile_default);
#else
        auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_sensor_data), rmw_qos_profile_sensor_data);
#endif

    gripper_controller_goal_pub =
        node_->create_publisher<std_msgs::msg::Float64MultiArray>( "gripper_forward_command_controller/commands", qos );

    initialized = res;
    return res;
}

Moveit2ServoMotionController::~Moveit2ServoMotionController()
{
    exitApp = true;
    // Make sure the tracker is stopped and clean up
    move_to_pose_thread->join();

}

void Moveit2ServoMotionController::setControllerSpeed ( const  double controllerSpeed )
{
    poseTracker->setSpeed(controllerSpeed);
}

void Moveit2ServoMotionController::sendGoal ( const geometry_msgs::msg::Pose destPose )
{
    if (!initialized)
    {
        RCLCPP_INFO ( node_->get_logger(), "Moveit2ServoMotionController: GOAL CONTROLLER NOT INITIALIZED!");
        return;
    }

    current_control_mode = TCP_CONTROL_MODE;
    lastTCPGoal = destPose;

    currentPose.pose= destPose;
    currentPose.header.frame_id = "base_link";
    currentPose.header.stamp = node_->now();
    const geometry_msgs::msg::PoseStamped::ConstSharedPtr msg = std::make_shared<const geometry_msgs::msg::PoseStamped> ( currentPose );

    poseTracker->setTargetPose ( msg );
}

bool Moveit2ServoMotionController::isGoalNear()
{
    if (!initialized)
    {
        std::cout << "GOAL CONTROLLER NOT INITIALIZED!\n";
        return false;
    }
    RCLCPP_DEBUG_THROTTLE(node_->get_logger(), *node_->get_clock(), 1000, "Moveit2ServoMotionController::isGoalNear(): RESULT: %d", poseTracker->isGoalAchieved());
    return poseTracker->isGoalAchieved();
}

void Moveit2ServoMotionController::sendGoal ( const std::vector<vector6d_t> dest, const bool recomputeTraj )
{
    (void)dest;
    (void)recomputeTraj;
    if (!initialized)
    {
        std::cout << "GOAL CONTROLLER NOT INITIALIZED!\n";
        return;
    }

    RCLCPP_FATAL ( node_->get_logger(), "===================> Moveit2ServoMotionController::sendGoal JOINT MODE Unimplemented !!!" );
}
void Moveit2ServoMotionController::sendGripperPosition(double pos)
{
    std_msgs::msg::Float64MultiArray gripperPositionMsg;
    gripperPositionMsg.data.push_back ( pos );
    gripper_controller_goal_pub->publish ( gripperPositionMsg );

}

}
#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(RVCMotionController::Moveit2ServoMotionController, RVCMotionController::RVCMotionControllerInterface)

