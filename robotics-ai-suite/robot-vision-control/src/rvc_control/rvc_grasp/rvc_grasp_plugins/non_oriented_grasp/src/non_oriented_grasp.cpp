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

#include "non_oriented_grasp/non_oriented_grasp.hpp"

namespace RVCControl {

NonOrientedGrasp::NonOrientedGrasp()
: pregrasp_distance(0.08),
  grasp_z_offset(0),
  targetAcquired(false),  
  canPerformTFTranform(false)
{
    RCLCPP_INFO ( rclcpp::get_logger ("NOG" ), "NonOrientedGrasp" );
}

bool NonOrientedGrasp::init(rclcpp::Node::SharedPtr node)
{
    auto res = RVCGraspInterface::init(node);
    RCLCPP_INFO ( rclcpp::get_logger ("NOG" ), "NonOrientedGrasp INIT" );

    node->declare_parameter<double> ( "pregrasp_distance", 0.08 );
    node->declare_parameter<double> ( "grasp_z_offset", 0.0 );

    pregrasp_distance = node_->get_parameter ( "pregrasp_distance" ).as_double();

    grasp_z_offset = node_->get_parameter ( "grasp_z_offset" ).as_double();

    tfBuffer = std::make_unique<tf2_ros::Buffer> ( node_->get_clock() );
    tfListener = std::make_shared<tf2_ros::TransformListener> ( *tfBuffer );

    auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw( rmw_qos_profile_sensor_data),
                           rmw_qos_profile_sensor_data);

    marker_pub = node->create_publisher
                 < visualization_msgs::msg::Marker > ( "log_visualization_marker", qos );

    marker.header.frame_id = "world";
    marker.header.stamp = node->now ();
    marker.ns = "basic_shapes";
    marker.type = visualization_msgs::msg::Marker::TEXT_VIEW_FACING;
    marker.action = visualization_msgs::msg::Marker::ADD;

    marker.pose.position.x = 0.0;
    marker.pose.position.y = 1.0;
    marker.pose.position.z = 0.8;
    marker.pose.orientation.x = 0.0;
    marker.pose.orientation.y = 0.0;
    marker.pose.orientation.z = 0.0;
    marker.pose.orientation.w = 1.0;

    marker.text = "Object";
    marker.scale.z = 0.07;

    marker.color.r = 0.0f;
    marker.color.g = 1.0f;
    marker.color.b = 0.0f;
    marker.color.a = 1.0;
    debugPublisher = node_->create_publisher<geometry_msgs::msg::PoseStamped> ( "debugPoseStamped", qos );

    return res;

}
void NonOrientedGrasp::OnMessageReceive(rvc_messages::msg::PoseStampedList::SharedPtr msgList)
{
    if (msgList->poses.size() == 0)
    {
        targetAcquired = false;
        return;
    }

    //TODO: handle all the list
    rvc_messages::msg::PoseStamped firstPose = msgList->poses[0];
    targetAcquired = !( classIdCurrent == "none" );
    classIdCurrent = firstPose.obj_type;


    marker.text = classIdCurrent;
    marker_pub->publish ( marker );



    // Sanity Check
    if ((firstPose.pose_stamped.pose.position.x == 0 ) && (firstPose.pose_stamped.pose.position.y == 0 ) &&
            (firstPose.pose_stamped.pose.position.z == 0 ))
    {
        return;
    }

    geometry_msgs::msg::PoseStamped msgPoseStampedOut;

    if ( firstPose.pose_stamped.header.frame_id != base_link )
    {
        if ( !canPerformTFTranform )
        {
            std::string *whyNot  = NULL;
            if ( !tfBuffer->canTransform ( base_link, firstPose.pose_stamped.header.frame_id, rclcpp::Time() ),
                    whyNot )
            {
                std::cout << " CANNOT TRANSFORM: " << *whyNot << "\n";
                RCLCPP_ERROR ( node_->get_logger (), "cannot transform: %s", whyNot->c_str() );
                return ;
            }
        }
        else
        {
            canPerformTFTranform = true;
        }
        try
        {
            tfBuffer->transform ( firstPose.pose_stamped, msgPoseStampedOut, base_link );
        }
        catch ( tf2::TransformException &ex )
        {
            RCLCPP_ERROR ( node_->get_logger (), "Exception: %s\n", ex.what() );
            canPerformTFTranform = false;
            return;
        }
    }
    else
    {
        // Dangerous, in this case we are not ignoring orientation, assuming the AI knows what it is doing...
        RCLCPP_DEBUG_THROTTLE(node_->get_logger(), *node_->get_clock(), 1000,
                             "PUBLISHING UNCONVERTED Pose from AI ");
        msgPoseStampedOut = firstPose.pose_stamped;
    }

     innerDestinationTCPPose = msgPoseStampedOut.pose;


     // Discarding orientation from AI until no more misdetections
     // new grasp orientation will be at a fixed angle towards the surface under the object
     // but in a line between the robot base and the object center.
     double x = innerDestinationTCPPose.position.x;
     double y = innerDestinationTCPPose.position.y;
     tf2::Quaternion quat2, quat;
     quat2.setRPY ( -1.15f, M_PI, -M_PI_2 );
     double yaw2 = atan2 ( y, x );
     quat.setRPY ( 0, 0, yaw2 );
     quat = quat * quat2;
     quat.normalize();
     innerDestinationTCPPose.orientation = tf2::toMsg ( quat );
     innerDestinationTCPPose.position.z += 0.01;

     geometry_msgs::msg::PoseStamped msgDebug;
     msgDebug.header.stamp = node_->now();
     msgDebug.header.frame_id = base_link;
     msgDebug.pose = innerDestinationTCPPose;
     RCLCPP_DEBUG(node_->get_logger(),
                         "received RvcMessagesCallback... PUBLISHING converted debugPublisher ");
     debugPublisher->publish ( msgDebug );

    innerDestinationTCPPose.position.z += grasp_z_offset;

    outerDestinationTCPPose = innerDestinationTCPPose;
    tf2::Matrix3x3 rot_mat_tf2;
    tf2::Quaternion q;
    tf2::fromMsg ( outerDestinationTCPPose.orientation, q );
    q.normalize();
    rot_mat_tf2.setRotation ( q );
    auto rz = rot_mat_tf2.getColumn ( 2 );

    outerDestinationTCPPose.position.x -= rz[0] * pregrasp_distance;
    outerDestinationTCPPose.position.y -= rz[1] * pregrasp_distance;
    outerDestinationTCPPose.position.z -= rz[2] * pregrasp_distance;
    targetAcquired = !( classIdCurrent == "none" );
}

bool NonOrientedGrasp::getPreGrasp(geometry_msgs::msg::Pose & pose)
{
    pose = outerDestinationTCPPose;
    return true;
}

bool NonOrientedGrasp::getGrasp(geometry_msgs::msg::Pose & pose)
{
    pose = innerDestinationTCPPose;
    return true;
}

}
#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(RVCControl::NonOrientedGrasp, RVCControl::RVCGraspInterface)
