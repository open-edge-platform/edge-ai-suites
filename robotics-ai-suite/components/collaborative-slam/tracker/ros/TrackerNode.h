// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#pragma once

#include "rosx.h"
#include "univloc_tracker/Tracker.h"

#include <Eigen/Core>
#include <Eigen/Geometry>
#ifdef USE_IMAGE_TRANSPORT
#include <image_transport/image_transport.hpp>
#include <image_transport/subscriber_filter.hpp>
#endif
#include <message_filters/subscriber.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <message_filters/time_synchronizer.h>
#include "sensor_msgs/msg/laser_scan.hpp"

#include <string>
#include <atomic>
#include <memory>


class TrackerNode : public rosx::Node
{
    typedef univloc_tracker::ImageFrame FrameData;

public:
    TrackerNode();

    ~TrackerNode();

    bool init();

    void main_loop();

    void stop();

    uint32_t getReceivedFramesCount() const;

    static const std::string tracker_node_name;

private:
    bool read_config_from_ros(std::string camera_info_topic, std::string right_camera_info_topic);

    rosx::TfLookupResult get_tf_matrix(Eigen::Matrix4d &pose, std::string from, std::string to, rosx::Time stamp,
                                       rosx::Duration timeout = rosx::Duration(0));

    sensor_msgs::CameraInfoPtr get_camera_info_msg_from_topic(std::string camera_info_topic);

    void camera_info_callback(const sensor_msgs::CameraInfoConstPtr msg);

    void accgyr_callback(const sensor_msgs::ImuConstPtr acc_msg, const sensor_msgs::ImuConstPtr gyr_msg);

    void imu_callback(const sensor_msgs::ImuConstPtr imu_msg);

    void rgbd_callback(const sensor_msgs::ImageConstPtr msgRGB, const sensor_msgs::ImageConstPtr msgD);

    void stereo_callback(const sensor_msgs::ImageConstPtr msgLEFT, const sensor_msgs::ImageConstPtr msgRIGHT);

    void monocular_callback(const sensor_msgs::ImageConstPtr msgRGB);

    void lidar_callback(const sensor_msgs::msg::LaserScan::ConstSharedPtr laser_scan);

    void odom_pose(rosx::Time timestamp);

    void publish_pose(const Eigen::Matrix4d &Tcw, const std_msgs::Header &image_header,
                      const Eigen::Matrix<double, 6, 6> &covariance, bool skip_query_transform = false);

    void publish_local_landmarks();

    void publish_tracked_server_landmarks();

    void publish_imu_estimated_trajectory();

    void periodically_print_stats();

    void save_trajectory_to_file(const Eigen::Matrix4d pose, rosx::Time time_stamp) const;

    void publish_imu_states();

    void publish_lidar_states();

    void publish_local_map(const Eigen::Matrix4d &Tcw);

    void publish_volumetric_map();

    void publish_occupancy_map();

    std_msgs::ColorRGBA index_to_color(unsigned int id);

    typedef univloc_tracker::LidarFrame LidarData;

#ifdef USE_IMAGE_TRANSPORT
    typedef image_transport::SubscriberFilter ImageSubscriberFilter;
#else
    typedef message_filters::Subscriber<sensor_msgs::Image> ImageSubscriberFilter;
#endif
    typedef message_filters::sync_policies::ApproximateTime<sensor_msgs::Image, sensor_msgs::Image> sync_policy;
    sync_policy sync_policy_;
    ImageSubscriberFilter sub_image_, sub_depth_, sub_right_image_, sub_mono_;
    message_filters::Synchronizer<sync_policy> image_sync_;
    sensor_msgs::CameraInfoPtr camera_info_msg_;
    std::promise<void> camera_info_ready_promise_;

    rclcpp::Subscription<sensor_msgs::msg::Image>::ConstSharedPtr monocular_sub_;
    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::ConstSharedPtr laser_scan_sub_;
    rclcpp::Subscription<sensor_msgs::msg::Imu>::ConstSharedPtr sub_imu_;
    rclcpp::Publisher<sensor_msgs::msg::PointCloud>::SharedPtr pub_pc_;
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pub_pose_;
    rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr pub_kf_pose_;
    rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr pub_optimized_path_;
    rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr pub_imu_estimated_path_;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr pub_server_landmarks_observation_;
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_local_map_;
    rclcpp::Publisher<univloc_msgs::msg::ImuStatus>::SharedPtr pub_imu_states_;
    rclcpp::Publisher<univloc_msgs::msg::LidarStatus>::SharedPtr pub_lidar_states_;
    typedef message_filters::sync_policies::ApproximateTime<sensor_msgs::msg::Imu, sensor_msgs::msg::Imu> sync_imu_policy;
    sync_imu_policy sync_imu_policy_;
    message_filters::Subscriber<sensor_msgs::msg::Imu> sub_acc_, sub_gyro_;
    message_filters::Synchronizer<sync_imu_policy> imu_sync_;

    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_fused_map_;
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_occupancy_;
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_occupancy_map_;
    rclcpp::TimerBase::SharedPtr check_timer_;
    nav_msgs::msg::OccupancyGrid::SharedPtr grid_template_;

    std::shared_ptr<univloc_tracker::Config> cfg_;

    nav_msgs::Path optimized_path_;

    std::unique_ptr<univloc_tracker::Tracker> tracker_;
    std::atomic<bool> tracker_started_ = false;
    std::string p_image_topic_, p_depth_topic_, p_right_image_topic_;
    std::string p_map_frame_, p_parent_frame_, p_child_frame_;
    std::string p_mask_image_;
    int num_lost_frames_to_reset_ = 0;
    std::string traj_store_path_;
    std::string octree_store_path_;
    bool publish_tf_ = false;
    tf2::Transform last_T_parent_child_;
    double p_accel_measurement_scale_ = 0.0;
    // For imu subscribing
    std::string acc_topic_, gyro_topic_, imu_topic_;
    bool use_lidar_ = false;
    // Statistics of frame counts
    float p_stat_log_interval_ = 3.0f;
    std::atomic_uint stat_received_, stat_processed_, stat_localized_;
    unsigned int stat_total_processed_ = 0, stat_total_localized_ = 0;
};

