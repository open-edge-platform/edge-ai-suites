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

#include "oriented_grasp/oriented_grasp.hpp"

namespace RVCControl
{

geometry_msgs::msg::Quaternion OrientedGrasp::filter_orientation(const geometry_msgs::msg::Quaternion& orientation)
{
   if (!initialized_)
   {
       filtered_orientation_ = orientation;
       initialized_ = true;
   }
   else
   {
       tf2::Quaternion q1, q2, q_result;
       tf2::convert(orientation, q1);
       tf2::convert(filtered_orientation_, q2);

       q_result = q1.slerp(q2, alpha_);
       tf2::convert(q_result, filtered_orientation_);
   }
   return filtered_orientation_;
}

OrientedGrasp::OrientedGrasp()
: pregrasp_distance(0.08), grasp_z_offset(0), targetAcquired(false), canPerformTFTranform(false),
  grasp_distance_threshold(1.03), grasp_min_horizontal_incl(M_PI/4), grasp_vertical_inclination(0),
  grasp_vertical_delta_inclination(1e-2 * (M_PI/180)), grasp_reference_point_x(0), grasp_reference_point_y(0),
  grasp_reference_point_z(0), grasp_polar_coordinate_r(0), grasp_polar_coordinate_theta(4.1),
  grasp_polar_coordinate_phi(1.55), hysteresis_queue_size(1000)
{
    alpha_ = 0.5;
    initialized_ = false;

    RCLCPP_INFO ( rclcpp::get_logger ("NOG" ), "OrientedGrasp" );
}

bool OrientedGrasp::init(rclcpp::Node::SharedPtr node)
{
    auto res = RVCGraspInterface::init(node);
    RCLCPP_INFO ( rclcpp::get_logger ("NOG" ), "OrientedGrasp INIT" );

    node->declare_parameter<double> ( "alphafilter", 0.5 );
    alpha_ = node_->get_parameter ( "alphafilter" ).as_double();

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
    debugCovariancePublisher = node->create_publisher<geometry_msgs::msg::PoseWithCovarianceStamped> (
        "poseCovarianceStamped",
        qos );

    node_->declare_parameter<double>("grasp_distance_threshold", 1.03);
    grasp_distance_threshold = node_->get_parameter("grasp_distance_threshold").as_double();
    node_->declare_parameter<double>("grasp_min_horizontal_incl", M_PI/4);
    grasp_min_horizontal_incl = node_->get_parameter("grasp_min_horizontal_incl").as_double();
    node_->declare_parameter<double>("grasp_vertical_inclination", 40 * (M_PI/180));
    grasp_vertical_inclination = node_->get_parameter("grasp_vertical_inclination").as_double();
    node_->declare_parameter<double>("grasp_vertical_delta_inclination", 1e-2 * (M_PI/180));
    grasp_vertical_delta_inclination = node_->get_parameter("grasp_vertical_delta_inclination").as_double();

    node_->declare_parameter<double>("grasp_polar_coordinate_r", 6.1);
    grasp_polar_coordinate_r = node_->get_parameter("grasp_polar_coordinate_r").as_double();
    // Slightly modify this parameter to differently manage the Yaw threshold:
    // Increase/decrease it to rotate the Yaw threshold clockwise/counterclockwise
    node_->declare_parameter<double>("grasp_polar_coordinate_theta", 4.1);
    grasp_polar_coordinate_theta  = node_->get_parameter("grasp_polar_coordinate_theta").as_double();
    node_->declare_parameter<double>("grasp_polar_coordinate_phi", 1.55);
    grasp_polar_coordinate_phi  = node_->get_parameter("grasp_polar_coordinate_phi").as_double();
    // Convert spherical coordinates  (r, theta, phi) to cartesian coordinates  (x, y, z)
    grasp_reference_point_x = grasp_polar_coordinate_r * sin(grasp_polar_coordinate_phi) * cos(grasp_polar_coordinate_theta);
    grasp_reference_point_y = grasp_polar_coordinate_r * sin(grasp_polar_coordinate_phi) * sin(grasp_polar_coordinate_theta);
    grasp_reference_point_z = grasp_polar_coordinate_r * cos(grasp_polar_coordinate_phi);

    node_->declare_parameter<int>("hysteresis_queue_size", 1000);
    hysteresis_queue_size = node_->get_parameter("hysteresis_queue_size").as_int();

    return res;

}

double OrientedGrasp::computeInclination(const geometry_msgs::msg::Pose pose)
{
   tf2::Quaternion q(pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w);
   tf2::Matrix3x3 m(q);
   double roll, pitch, yaw;
   m.getRPY(roll, pitch, yaw);
   double inclination = std::atan2(std::sqrt(std::pow(std::sin(roll), 2) + std::pow(std::sin(pitch), 2)), std::cos(roll) * std::cos(pitch));
   // If the z-coordinate of the position is negative, the inclination is negative
   if (pose.position.z < 0)
   {
      inclination = -inclination;
   }
   return inclination;
}

geometry_msgs::msg::Pose OrientedGrasp::adjustVerticalInclination(const geometry_msgs::msg::Pose pose)
{
   double inclination = computeInclination(pose);
   const double EXPECTED_INCLINATION = M_PI/2 + grasp_vertical_inclination;
   const double UPPER_LIMIT = EXPECTED_INCLINATION + grasp_vertical_delta_inclination;
   const double LOWER_LIMIT = EXPECTED_INCLINATION - grasp_vertical_delta_inclination;
   if (inclination > UPPER_LIMIT)
   {
      double negativeRotation = -1 * (inclination - UPPER_LIMIT);
      return getRotatedPose(pose, X, negativeRotation);
   }
   else if (inclination < LOWER_LIMIT)
   {
      double positiveRotation = LOWER_LIMIT - inclination;
      return getRotatedPose(pose, X, positiveRotation);
   }
   return pose;
}


geometry_msgs::msg::Pose OrientedGrasp::getRotatedPose(const geometry_msgs::msg::Pose basePose, Axis axis, double rotationAngle)
{
   geometry_msgs::msg::Pose retPose = basePose;

   // Convert the orientation to tf2::Quaternion for easier manipulation
   tf2::Quaternion initialOrientation;
   tf2::convert(basePose.orientation, initialOrientation);

   // Select the axis for the rotation
   tf2::Vector3 axisId;
   if (axis == X)
   {
      axisId = tf2::Vector3(1, 0, 0);
   }
   else if (axis == Y)
   {
      axisId = tf2::Vector3(0, 1, 0);
   }
   else
   {
      axisId = tf2::Vector3(0, 0, 1);
   }
   // Calculate the number of steps and the angle for each step
   int steps = static_cast<int>(std::abs(rotationAngle) / (M_PI/2)) + 1;
   double stepAngle = rotationAngle / steps;
   tf2::Quaternion rotationStep = tf2::Quaternion(axisId, stepAngle);
   // Rotate the pose by the inverse of its current orientation
   tf2::Quaternion inverseInitialOrientation = initialOrientation.inverse();
   tf2::Quaternion poseOrientationRelativeToWorld = inverseInitialOrientation * initialOrientation;
   // Apply the rotation in steps
   tf2::Quaternion newOrientation = poseOrientationRelativeToWorld;
   for (int i = 0; i < steps; ++i)
   {
      newOrientation = newOrientation * rotationStep;
   }
   // If the rotation is greater than π, manually set the orientation to be "upside down"
   if (std::abs(rotationAngle - M_PI) < 1e-3)
   {
      tf2::Quaternion upsideDownOrientation(0, 1, 0, 0); // TODO: is this assumption always correct?
      newOrientation = upsideDownOrientation;
   }
   // Apply the initial orientation to the new pose
   tf2::Quaternion finalOrientation = initialOrientation * newOrientation;
   tf2::convert(finalOrientation, retPose.orientation);
   return retPose;
}

geometry_msgs::msg::Pose OrientedGrasp::ensureHorizontalPose(const geometry_msgs::msg::Pose pose)
{
   // Convert the orientation to a tf2 Quaternion
   geometry_msgs::msg::Pose retPose = pose;
   tf2::Quaternion q(pose.orientation.x, pose.orientation.y,
                     pose.orientation.z, pose.orientation.w);
   // Get the X and Y axes of the pose (in RVIZ: red and green axis)
   tf2::Vector3 x_axis = tf2::quatRotate(q, tf2::Vector3(1, 0, 0));
   tf2::Vector3 y_axis = tf2::quatRotate(q, tf2::Vector3(0, 1, 0));
   // Check the inclination with respect to the Z axis
   double dot_product = x_axis.z();
   double inclination = acos(dot_product);
   // Check if the inclination is within the desired range
   int rotation_count = 0; // Sanity check
   int const MAX_ROTATIONS = 4;
   double const HORIZONTAL_INCLINATION = M_PI/2;
   double const LOWER_INCLINATION_LIMIT = HORIZONTAL_INCLINATION - grasp_min_horizontal_incl;
   double const UPPER_INCLINATION_LIMIT = 2 * HORIZONTAL_INCLINATION - grasp_min_horizontal_incl;
   // Ensure an horizontal position by checking that:
   //  1. The inclination is between a certain range that ensure the gripper not to hit the table
   //  2. The Y-axis >= 0 for avoiding upside down rotation (in RVIZ: green axis always up)
   while (inclination < LOWER_INCLINATION_LIMIT ||
          inclination > UPPER_INCLINATION_LIMIT || y_axis.z() < 0)
   {
      // Limit the number of rotations not to exceed 360 degrees
      if (rotation_count++ > MAX_ROTATIONS)
      {
         RCLCPP_FATAL ( rclcpp::get_logger ("NOG" ),
                        "[Horizontal Inclination] Error: Unable to adjust inclination after rotation > 360 degrees");
         return retPose;
      }
      // Apply 90 degrees rotation around Z axis of the pose (in RVIZ: blue axis)
      tf2::Quaternion q_z_rot;
      q_z_rot.setRPY(0, 0, M_PI/2); // 90 degrees rotation around Z axis
      q = q * q_z_rot; // Apply the rotation
      retPose.orientation = tf2::toMsg(q);
      // Recalculate the X and Y axes and inclination
      x_axis = tf2::quatRotate(q, tf2::Vector3(1, 0, 0));
      y_axis = tf2::quatRotate(q, tf2::Vector3(0, 1, 0));
      dot_product = x_axis.z();
      inclination = acos(dot_product);
   }
   return retPose;
}

std::vector<geometry_msgs::msg::Pose> OrientedGrasp::detectAllPossibleGrasps(const geometry_msgs::msg::Pose  basePose)
{
   // From the basePose, determine all the other possible poses for a cube.
   // The robot can theoretically grasp a cube from any of its faces.
   std::vector<geometry_msgs::msg::Pose> grasps;
   grasps.push_back(getRotatedPose(basePose, X, 0));

   // Generate the poses for: the bottom, front, back, left, and right faces
   //  - Bottom face: rotate 180 degrees around x or y axis
   grasps.push_back(getRotatedPose(basePose, X, M_PI));
   //  - Front face: rotate 90 degrees around x axis
   grasps.push_back(getRotatedPose(basePose, X, M_PI/2));
   //  - Back face: rotate -90 degrees around x axis
   grasps.push_back(getRotatedPose(basePose, X, -M_PI/2));
   //  - Left face: rotate 90 degrees around y axis
   grasps.push_back(getRotatedPose(basePose, Y, M_PI/2));
   //  - Right face: rotate -90 degrees around y axis
   grasps.push_back(getRotatedPose(basePose, Y, -M_PI/2));

   return grasps;
}

double OrientedGrasp::getPoseDistance(const geometry_msgs::msg::Pose poseA,
                                      const geometry_msgs::msg::Pose poseB)
{
   double dx = poseA.position.x - poseB.position.x;
   double dy = poseA.position.y - poseB.position.y;
   double dz = poseA.position.z - poseB.position.z;
   return std::sqrt(dx * dx + dy * dy + dz * dz);
}

int OrientedGrasp::applyHysteresis(const std::vector<geometry_msgs::msg::Pose> poses,
                                   const std::vector<double> dotProducts)
{
   // Sort the dot products and consider only the smallest two
   std::vector<int> index(dotProducts.size());
   std::iota(index.begin(), index.end(), 0);
   std::sort(index.begin(), index.end(), [&dotProducts](int i1, int i2) { return dotProducts[i1] < dotProducts[i2]; });
   int maxIndex = 0;

   if (!lastPoses.empty())
   {
      std::vector<double> similarities;
      for (int i = 0; i < 2; i++)
      {
         auto pose = poses[index[i]];
         double totalSimilarity = 0;
         tf2::Quaternion q1(pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w);
         q1.normalize();
         std::queue<geometry_msgs::msg::Pose> tempQueue = lastPoses;
         while (!tempQueue.empty())
         {
            const auto& historyPose = tempQueue.front();
            tf2::Quaternion q2(historyPose.orientation.x, historyPose.orientation.y, historyPose.orientation.z, historyPose.orientation.w);
            q2.normalize();
            // The dot product of two quaternions is 1 if they share the same orientation,
            // -1 if they have opposite orientations (still fine for us),
            // and 0 if they are 90 degrees apart.
            totalSimilarity += std::abs(q1.dot(q2));
            tempQueue.pop();
         }
         similarities.push_back(totalSimilarity / lastPoses.size());
      }

      // Find the index of the highest similarity
      for (long unsigned int i = 1; i < similarities.size(); i++)
      {
         if (similarities[i] > similarities[maxIndex])
         {
            maxIndex = i;
         }
      }
   }
   // Return the index of the pose with the highest similarity
   return index[maxIndex];
}

geometry_msgs::msg::Pose OrientedGrasp::getBestGrasp(const std::vector<geometry_msgs::msg::Pose> grasps)
{
   std::vector<geometry_msgs::msg::Pose> newPoses;
   std::vector<geometry_msgs::msg::Pose> retPoses;
   std::vector<double> dotProducts;
   geometry_msgs::msg::Pose robotPose;
   // Initialize the position to be the origin of the world frame
   robotPose.position.x = 0.0;
   robotPose.position.y = 0.0;
   robotPose.position.z = 0.1; // Make sure the robot is positioned above the ground
   // Initialize the orientation to be the same as the world frame
   robotPose.orientation.x = 0.0;
   robotPose.orientation.y = 0.0;
   robotPose.orientation.z = 0.0;
   robotPose.orientation.w = 1.0;

   int count = 0;
   int bestPoseId = -1;
   double max_dot_product = std::numeric_limits<double>::infinity();
   // Move backward on xy the z axis for selecting the proper inclination
   tf2::Vector3 z_axis; // The initialization of this variable depends on the object's distance

   for (const auto& cubePose : grasps)
   {
      if (getPoseDistance(robotPose, cubePose) < grasp_distance_threshold)
      {
         z_axis = tf2::Vector3(grasp_reference_point_x/2, grasp_reference_point_y/2, grasp_reference_point_z);
      }
      else
      {
         z_axis = tf2::Vector3(grasp_reference_point_x, grasp_reference_point_y, grasp_reference_point_z);
      }
      tf2::Quaternion cube_orientation;
      tf2::convert(cubePose.orientation, cube_orientation);
      tf2::Vector3 face_normal(0, 0, 1); // Change the direction of the face_normal to point upwards
      face_normal = tf2::quatRotate(cube_orientation, face_normal);
      tf2::Vector3 reference_direction = tf2::Vector3(cubePose.position.x - robotPose.position.x,
                                                      cubePose.position.y - robotPose.position.y,
                                                      cubePose.position.z - robotPose.position.z);
      face_normal.normalize();
      reference_direction.normalize();
       /* Calculate the dot product with the z-axis (check how aligned they are).
          The dot product is used to measure the cosine of the angle between the two vectors:
           - If the dot product is close to 1, it means the vectors are closely aligned.
           - If it's close to -1, it means they are in opposite directions.
           - If it's close to 0, it means the vectors are perpendicular.
        */
      double dot_product = face_normal.dot(z_axis);
      dotProducts.push_back(dot_product);
      if (dot_product < max_dot_product)
      {
         bestPoseId = count;
         max_dot_product = dot_product;
      }
      newPoses.push_back(ensureHorizontalPose(grasps[count]));
      retPoses.push_back(adjustVerticalInclination(newPoses[count]));
      count++;
   }

   if (bestPoseId == -1)
   {
      RCLCPP_ERROR ( node_->get_logger (), "Impossible to determine a grasp!" );
      classIdCurrent = "none"; // Inform the robot to return to safe position
      return grasps[0]; // This grasp will be ignored
   }

   int adjustedBestPoseId = applyHysteresis(retPoses, std::move(dotProducts));
   lastPoses.push(retPoses[bestPoseId]);
   if (lastPoses.size() > hysteresis_queue_size)
   {
      lastPoses.pop();
   }

   return retPoses[adjustedBestPoseId];
}

void OrientedGrasp::OnMessageReceive(rvc_messages::msg::PoseStampedList::SharedPtr msgList)
{
    if (msgList->poses.size() == 0)
    {
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

    auto grasps = detectAllPossibleGrasps(msgPoseStampedOut.pose);
    innerDestinationTCPPose = getBestGrasp(std::move(grasps)); // and assign it to innerDestinationTCPPose

    // Proceed only if a valid grasp has been determined
    if (classIdCurrent != "none")
    {
        // Publish selected pose info
        auto filtered = filter_orientation(innerDestinationTCPPose.orientation);

        geometry_msgs::msg::PoseStamped msg;
        msg.header.stamp = node_->now();
        msg.header.frame_id = base_link;
        msg.pose = innerDestinationTCPPose;
        debugPublisher->publish ( msg );

        innerDestinationTCPPose.orientation = filtered;
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

}

bool OrientedGrasp::getPreGrasp(geometry_msgs::msg::Pose & pose)
{
    pose = outerDestinationTCPPose;
    return true;
}

bool OrientedGrasp::getGrasp(geometry_msgs::msg::Pose & pose)
{
    pose = innerDestinationTCPPose;
    return true;
}

}
#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(RVCControl::OrientedGrasp, RVCControl::RVCGraspInterface)
