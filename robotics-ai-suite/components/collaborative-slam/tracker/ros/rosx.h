// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <chrono>
#include <string>
#include <rclcpp/rclcpp.hpp>
#include "univloc_msgs/msg/imu_status.hpp"
#include "univloc_msgs/msg/lidar_status.hpp"
#include <geometry_msgs/msg/point32.h>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/pose_with_covariance.hpp>
#include <geometry_msgs/msg/pose_with_covariance_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/point_cloud.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <rclcpp/executors/multi_threaded_executor.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>

#include <tf2_ros/transform_broadcaster.h>
#ifdef PRE_ROS_HUMBLE
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#else
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#endif
#include <tf2/transform_datatypes.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>

// -------------------------------------------------------------------------
// Macros for ROS1-type messages and logs to be able to build in ROS2

// Use this macro to process every message type you need
// e.g. namespace std_msgs { DECLARE_MSG_TYPES(Header) }
#define DECLARE_MSG_TYPES(Name)                       \
    typedef msg::Name Name;                           \
    typedef msg::Name::ConstSharedPtr Name##ConstPtr; \
    typedef msg::Name::SharedPtr Name##Ptr;

#define ROS_DEBUG(fmt, ...) RCLCPP_DEBUG(get_logger(), fmt, ##__VA_ARGS__)
#define ROS_INFO(fmt, ...) RCLCPP_INFO(get_logger(), fmt, ##__VA_ARGS__)
#define ROS_WARN(fmt, ...) RCLCPP_WARN(get_logger(), fmt, ##__VA_ARGS__)
#define ROS_ERROR(fmt, ...) RCLCPP_ERROR(get_logger(), fmt, ##__VA_ARGS__)
#define ROS_FATAL(fmt, ...) RCLCPP_FATAL(get_logger(), fmt, ##__VA_ARGS__)

namespace univloc_msgs {
DECLARE_MSG_TYPES(ImuStatus)
DECLARE_MSG_TYPES(LidarStatus)
}
namespace geometry_msgs {
DECLARE_MSG_TYPES(Point)
DECLARE_MSG_TYPES(PoseStamped)
DECLARE_MSG_TYPES(PoseWithCovarianceStamped)
DECLARE_MSG_TYPES(TransformStamped)
}
namespace nav_msgs {
DECLARE_MSG_TYPES(Path)
}
namespace sensor_msgs {
DECLARE_MSG_TYPES(CameraInfo)
DECLARE_MSG_TYPES(Imu)
DECLARE_MSG_TYPES(Image)
DECLARE_MSG_TYPES(PointCloud)
}
namespace std_msgs {
DECLARE_MSG_TYPES(Header)
DECLARE_MSG_TYPES(ColorRGBA)
}
namespace visualization_msgs {
DECLARE_MSG_TYPES(Marker)
DECLARE_MSG_TYPES(MarkerArray)
}

namespace rosx {

// -------------------------------------------------------------------------
// Rate, Time and Duration
using Rate = rclcpp::Rate;

class Time : public rclcpp::Time {
public:
    Time(rclcpp::Time rhs) : rclcpp::Time(rhs) {}
    using rclcpp::Time::seconds;
    using rclcpp::Time::Time;
    double toSec() { return seconds(); }
};

class Duration : public rclcpp::Duration {
public:
    Duration(int32_t seconds) : rclcpp::Duration(seconds, 0) {}
    Duration(double seconds) : rclcpp::Duration(std::chrono::nanoseconds{static_cast<int64_t>(seconds * 1e9)}) {}
    Duration(rclcpp::Duration rhs) : rclcpp::Duration(rhs) {}
    using rclcpp::Duration::Duration;
    using rclcpp::Duration::seconds;
    double toSec() { return seconds(); }
};

// -------------------------------------------------------------------------
// Functions: init, shutdown, ok, now

inline void init(int argc, char **argv, const std::string &)
{
    rclcpp::init(argc, argv);
}

inline void shutdown() { rclcpp::shutdown(); }

inline bool ok() { return rclcpp::ok(); }

inline Time now() { return rclcpp::Clock().now(); }

// -------------------------------------------------------------------------
// tf utilities

class TfLookupResult {
public:
    TfLookupResult() : result_(SUCCESS) {}

    TfLookupResult(std::string error) : error_(error)
    {
        if (error.find("into the future") != std::string::npos) {
            result_ = FUTURE;
        } else if (error.find("into the past") != std::string::npos) {
            result_ = PAST;
        } else {
            result_ = OTHER;
        }
    }

    operator bool() const { return result_ == SUCCESS; }

    bool past() const { return result_ == PAST; }

    bool future() const { return result_ == FUTURE; }

    std::string error() const { return error_; }

private:
    enum { SUCCESS, PAST, FUTURE, OTHER } result_;
    std::string error_;
};

template<typename T>
size_t getNumSubscribers(const T &pub)
{
    return pub->get_subscription_count();
}

class Node: public rclcpp::Node
{
public:
    Node([[maybe_unused]] const std::string &node_name)
        : rclcpp::Node(node_name),
          tf_buffer_(this->get_clock()),
          tf_listener_(tf_buffer_),
          tf_broadcaster_(*this)
    {}

    virtual ~Node() =default;

    template <typename ParamT>
    void get_ros_param(std::string name, ParamT &dst, const ParamT &default_value)
    {
        dst = declare_parameter(name, default_value);
    }

    template <typename ParamT>
    void get_ros_param(std::string name, ParamT &dst)
    {
        get_ros_param(name, dst, dst);
    }

    void get_ros_param(std::string name, std::string &dst, const char *default_value)
    {
        get_ros_param(name, dst, std::string(default_value));
    }

    void get_ros_param(std::string name, float &dst, double default_value)
    {
        get_ros_param(name, dst, static_cast<float>(default_value));
    }

    template <typename TimeT>
    void publish_transform(tf2::Transform transform, TimeT stamp, std::string parent, std::string child)
    {
        geometry_msgs::TransformStamped msg;
        tf2::Transform tf(transform);
        msg.transform = tf2::toMsg(tf);
        msg.header.frame_id = parent;
        msg.child_frame_id = child;
        msg.header.stamp = stamp;
        tf_broadcaster_.sendTransform(msg);
    }

    // Get the source to target transform of current timestamp through the info within "timeout" after
    // TF lookup time duration: | (stamp) ------ (stamp+timeout) |
    rosx::TfLookupResult get_transform(tf2::Stamped<tf2::Transform> &transform, std::string target, std::string source,
                                       rosx::Time stamp, rosx::Duration timeout = rosx::Duration(0))
    {
        try {
            geometry_msgs::TransformStamped tf_msg;
            tf_msg = tf_buffer_.lookupTransform(target, source, stamp, timeout);
            tf2::fromMsg(tf_msg, transform);
            return rosx::TfLookupResult();
        } catch (tf2::TransformException &e) {
            return rosx::TfLookupResult(e.what());
        }
    }

    // Get the source to target transform of current timestamp through the info within "timeout" ago
    // TF lookup time duration: | (stamp-timeout) ------ (stamp) |
    rosx::TfLookupResult get_transform(tf2::Stamped<tf2::Transform> &transform, std::string target, rosx::Time t_stamp,
                                       std::string source, rosx::Time s_stamp, std::string tf_fix_frame,
                                       rosx::Duration timeout = rosx::Duration(0))
    {
        try {
            geometry_msgs::TransformStamped tf_msg;
            tf_msg = tf_buffer_.lookupTransform(target, t_stamp, source, s_stamp, tf_fix_frame, timeout);
            tf2::fromMsg(tf_msg, transform);
            return rosx::TfLookupResult();
        } catch (tf2::TransformException &e) {
            return rosx::TfLookupResult(e.what());
        }
    }

    tf2_ros::Buffer tf_buffer_;
    tf2_ros::TransformListener tf_listener_;
    tf2_ros::TransformBroadcaster tf_broadcaster_;
};

}  // namespace rosx
