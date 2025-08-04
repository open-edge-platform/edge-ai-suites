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

#include "rvc_pose_detector.hpp"

using std::placeholders::_1;
using namespace RVC;

geometry_msgs::msg::Pose PoseDetector::mat44_to_pose(const Eigen::Matrix4f & mat)
{
    // decompose 4x4 matrix to translation and rotation components
    Eigen::Matrix3d rot(mat.topLeftCorner<3, 3>().cast<double>());

    Eigen::Quaterniond rot_q(rot);

    geometry_msgs::msg::Pose out;

    out.orientation = tf2::toMsg(rot_q);

    out.position = tf2::toMsg(Eigen::Vector3d(mat.col(3)[0], mat.col(3)[1], mat.col(3)[2]));

    return out;
}

std::string PoseDetector::mostFrequentClass(std::deque<std::string> dq)
{
    std::sort(dq.begin(), dq.end() );

    int max_count = 1;
    std::string res = dq[0];
    int curr_count = 1;

    for (unsigned i = 1; i < dq.size(); i++)
    {
        if (dq[i] == dq[i - 1])
        {
            curr_count++;
        }
        else
        {
            if (curr_count > max_count)
            {
                max_count = curr_count;
                res = dq[i - 1];
            }

            curr_count = 1;
        }
    }

    if (curr_count > max_count)
    {
        max_count = curr_count;
        res = dq[dq.size() - 1];
    }

    return res;
}

void PoseDetector::SynchronizedCallback(
    const sensor_msgs::msg::PointCloud2::ConstSharedPtr m_last_cloud,
    rvc_vision_messages::msg::RotatedBBList::ConstSharedPtr m_rotated_bb_msg)
{
    rclcpp::Time t1 = this->get_clock()->now();
    rclcpp::Time messageTs = m_last_cloud->header.stamp;

    rvc_messages::msg::PoseStampedList outMsg;
    rvc_messages::msg::PoseStamped poseStamped;
    poseStamped.pose_stamped.header.stamp = now();
    poseStamped.obj_type = "none";
    pcl::PointCloud<PointT>::Ptr cloud(new pcl::PointCloud<PointT>);
    std::string type = "none";

    // check for no ROIs
    if (!m_rotated_bb_msg->rotated_bb_list.empty())
    {
        auto roi = m_rotated_bb_msg->rotated_bb_list.back();
        type = roi.object_id;

        pcl::fromROSMsg(*m_last_cloud, *cloud);

        // grown the BB a bit
        if (roi.width < cloud->width - 2)
        {
            roi.width += 2;
        }

        if (roi.height < cloud->height - 2)
        {
            roi.height += 2;
        }

        // SANITY CHECKS
        if (roi.width > cloud->width)
        {
            roi.width = cloud->width;
        }

        if (roi.height > cloud->height)
        {
            roi.height = cloud->height;
        }

        //FIXME: handle the rotated rectangle!! THIS ASSUMES ANGLE == 0
        roi.angle = 0.0;
        // cropping by resizing in place without allocating new pointcloud
        unsigned long counter = 0;
        unsigned x0 = roi.cx - roi.width / 2.0;
        unsigned y0 = roi.cy - roi.height / 2.0;

        for (unsigned i = x0; i < x0 + roi.width; i++)
        {
            for (unsigned j = y0; j < y0 + roi.height; j++)
            {
                cloud->points[counter] = (*cloud)(i, j);
                counter++;
            }
        }

        cloud->resize((roi.width) * (roi.height));

        rclcpp::Time t2 = get_clock()->now();
        auto it = m_matchers.find(type);

        if (it == m_matchers.end())
        {
            RCLCPP_FATAL(this->get_logger(), "FATAL: RVC Object Detector send an unknown/mismatching object_id \'%s\'!!!", type.c_str());
            return;
        }

        auto res = it->second.match(cloud);

        RCLCPP_DEBUG(
            this->get_logger(), "Matched type %s res=%d, %s:%d",
            type.c_str(), res.matched, __FUNCTION__, __LINE__);

        if (res.matched)
        {
            poseStamped.pose_stamped.pose = mat44_to_pose(res.xform);
            // Note: replacing the corner of the object which is matched by libpcl with the centroid instead
            poseStamped.pose_stamped.pose.position.x = res.position[0];
            poseStamped.pose_stamped.pose.position.y = res.position[1];
            poseStamped.pose_stamped.pose.position.z = res.position[2];
            poseStamped.pose_stamped.header.frame_id = m_rotated_bb_msg->header.frame_id;
        }
        else
        {
            type = "none";
            RCLCPP_DEBUG(this->get_logger(), "NOT MATCHED");
        }

        if (res.registered_cloud != nullptr)
        {
            sensor_msgs::msg::PointCloud2 croppedCloudMsg;
            RCLCPP_DEBUG(this->get_logger(), "Publishing REGISTERED cloud on type %s", type.c_str());
            pcl::toROSMsg(*res.registered_cloud, croppedCloudMsg);

            croppedCloudMsg.header.stamp = now();
            croppedCloudMsg.header.frame_id = m_rotated_bb_msg->header.frame_id;
            m_pub_cloud->publish(croppedCloudMsg);
        }
    }
    else  // no roi published??
    {
        //RCLCPP_INFO(this->get_logger(), "Empty ROI list");
        type = "none";
    }

    classIds.push_back(type);

    poseStamped.obj_type = classIds.empty() ? "none" : mostFrequentClass(classIds);

    outMsg.poses.push_back(poseStamped);
    m_pub_poses->publish(outMsg);

    // 1 sec@30fps long array for walking average...
    // should we put in parameters.yaml, or revise the algo?

    if (classIds.size() > 30)
    {
        classIds.pop_front();
    }
}

PoseDetector::PoseDetector(const rclcpp::NodeOptions & options)
  : Node("rvc_pose_detector", options)
{

#ifndef BUILD_SENSOR_DATA
    auto rmw_qos_profile = rmw_qos_profile_default;
#else
    auto rmw_qos_profile = rmw_qos_profile_sensor_data;
#endif


    auto qos = rclcpp::QoS(
        rclcpp::QoSInitialization::from_rmw(rmw_qos_profile),
        rmw_qos_profile);

    my_callback_group = create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    //my_callback_group = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);

    rclcpp::SubscriptionOptions optionsCallback;
    optionsCallback.callback_group = my_callback_group;

    m_rotated_bb_list_sub.subscribe(this, "detections", rmw_qos_profile, optionsCallback);

    std::string ns = this->get_namespace();
    std::string topic_prefix = std::string ("camera/camera") + ns.substr(1, ns.size() - 1) + std::string("/");

    m_pcl_sub.subscribe(this, topic_prefix + std::string("depth/color/points"), rmw_qos_profile, optionsCallback);

    //synchronizer.reset(new MySync(RVCSyncPolicy(20), m_rotated_bb_list_sub, m_pcl_sub));
    synchronizer.reset(new MySync(RVCSyncPolicy(150), m_pcl_sub, m_rotated_bb_list_sub));
    synchronizer->registerCallback(
        std::bind(
            &PoseDetector::SynchronizedCallback, this, std::placeholders::_1,
            std::placeholders::_2));

    m_pub_poses = this->create_publisher<rvc_messages::msg::PoseStampedList>("object_poses", qos);

    m_pub_cloud = this->create_publisher<sensor_msgs::msg::PointCloud2>(
        "pose_cropped_cloud", qos);

    this->declare_parameter<std::vector<std::string>>("class_name_array", std::vector<std::string>());
    m_obj_classes = get_parameter("class_name_array").as_string_array();


    MatchSettings settings;

    this->declare_parameter<double>("downsampling", 0.006);
    this->declare_parameter<double>("downsample_clouds", 0.006);
    this->declare_parameter<double>("normal_search_radius", 0.005);
    this->declare_parameter<double>("fpfh_search_radius", 0.05);
    this->declare_parameter<double>("stddev_mul_threshold", 1.0);
    this->declare_parameter<double>("z_threshold", 0.7);
    this->declare_parameter<double>("inlier_fraction", 0.47);
    this->declare_parameter<double>("similarity_threshold", 0.9);
    this->declare_parameter<double>("max_corresp_randomness", 214.0);
    this->declare_parameter<double>("max_corresp_distance", 0.1);
    this->declare_parameter<int>("max_iterations", 1000);
    this->declare_parameter<int>("num_samples", 3);
    this->declare_parameter<double>("icp_max_corresp_distance", 0.1);
    this->declare_parameter<double>("icp_xform_epsilon", 0.000000001);
    this->declare_parameter<double>("icp_fitness_epsilon", 0.000006);
    this->declare_parameter<int>("icp_max_iterations", 50);
    this->declare_parameter<std::string>("rvc_use_case_binaries", "rvc_use_case_binaries");

    // load object files into memory
    auto base_path = ament_index_cpp::get_package_share_directory(
        get_parameter("rvc_use_case_binaries").as_string()) + "/pcd_objects/";


    settings.downsampling = get_parameter("downsampling").as_double();
    settings.downsample_clouds = get_parameter("downsample_clouds").as_double();
    settings.normal_search_radius = get_parameter("normal_search_radius").as_double();
    settings.fpfh_search_radius = get_parameter("fpfh_search_radius").as_double();
    settings.stddev_mul_threshold = get_parameter("stddev_mul_threshold").as_double();
    settings.z_threshold = get_parameter("z_threshold").as_double();
    settings.inlier_fraction = get_parameter("inlier_fraction").as_double();
    settings.similarity_threshold = get_parameter("similarity_threshold").as_double();
    settings.max_corresp_randomness = get_parameter("max_corresp_randomness").as_double();
    settings.max_corresp_distance = get_parameter("max_corresp_distance").as_double();
    settings.max_iterations = get_parameter("max_iterations").as_int();
    settings.num_samples = get_parameter("num_samples").as_int();
    settings.icp_max_corresp_distance = get_parameter("icp_max_corresp_distance").as_double();
    settings.icp_xform_epsilon = get_parameter("icp_xform_epsilon").as_double();
    settings.icp_fitness_epsilon = get_parameter("icp_fitness_epsilon").as_double();
    settings.icp_max_iterations = get_parameter("icp_max_iterations").as_int();

    RCLCPP_INFO(this->get_logger(), "PCL Settings:");
    RCLCPP_INFO(this->get_logger(), "\t downsampling %f", settings.downsampling);
    RCLCPP_INFO(this->get_logger(), "\t downsample_clouds %f", settings.downsample_clouds);
    RCLCPP_INFO(this->get_logger(), "\t normal_search_radius %f", settings.normal_search_radius);
    RCLCPP_INFO(this->get_logger(), "\t fpfh_search_radius %f", settings.fpfh_search_radius);
    RCLCPP_INFO(this->get_logger(), "\t stddev_mul_threshold %f", settings.stddev_mul_threshold);
    RCLCPP_INFO(this->get_logger(), "\t z_threshold %f", settings.z_threshold);
    RCLCPP_INFO(this->get_logger(), "\t inlier_fraction %f", settings.inlier_fraction);
    RCLCPP_INFO(this->get_logger(), "\t similarity_threshold %f", settings.similarity_threshold);
    RCLCPP_INFO(this->get_logger(), "\t max_corresp_randomness %f", settings.max_corresp_randomness);
    RCLCPP_INFO(this->get_logger(), "\t max_corresp_distance %f", settings.max_corresp_distance);
    RCLCPP_INFO(this->get_logger(), "\t max_iterations %ld", settings.max_iterations);
    RCLCPP_INFO(this->get_logger(), "\t num_samples %ld", settings.num_samples);
    RCLCPP_INFO(this->get_logger(), "\t icp_max_corresp_distance %f", settings.icp_max_corresp_distance);
    RCLCPP_INFO(this->get_logger(), "\t icp_xform_epsilon %f", settings.icp_xform_epsilon);
    RCLCPP_INFO(this->get_logger(), "\t icp_fitness_epsilon %f", settings.icp_fitness_epsilon);
    RCLCPP_INFO(this->get_logger(), "\t icp_max_iterations %ld", settings.icp_max_iterations);

    RCLCPP_INFO_STREAM(
        get_logger(),
        "Intra-Process is " << ( this->get_node_options().use_intra_process_comms() ? "ON" : "OFF" ) );

    for (auto obj : m_obj_classes)
    {
        auto obj_path = base_path + obj + ".pcd";
        m_matchers.emplace(obj,ObjectMatcher( obj, obj_path, settings));
    }

    RCLCPP_DEBUG(this->get_logger(), "Worker threads created in Ctor");
}


#include "rclcpp_components/register_node_macro.hpp"

// Register the component with class_loader.
// This acts as a sort of entry point, allowing the component to be discoverable when its library
// is being loaded into a running process.
RCLCPP_COMPONENTS_REGISTER_NODE(RVC::PoseDetector)
