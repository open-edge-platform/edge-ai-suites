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

#pragma once

#include <rclcpp/rclcpp.hpp>
#include <rclcpp/time.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <std_srvs/srv/empty.hpp>

#include <message_filters/subscriber.h>
#include <message_filters/time_synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>

#include <condition_variable>
#include <mutex>
#include <queue>
#include <thread>

#include "DataQueue.h"
#include "ImageFrame.h"

#define ROS_INFO_THROTTLE(sec, ...) RCUTILS_LOG_INFO_THROTTLE(RCUTILS_STEADY_TIME, sec, __VA_ARGS__)

class CameraSubscribers
{
    using FrameQueue = DataQueue<std::shared_ptr<ImageFrame>>;

public:
    // Syncing policies for multiple camera support
    typedef message_filters::sync_policies::ApproximateTime<
        sensor_msgs::msg::CameraInfo,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image> syncPolicy4;
    typedef message_filters::Synchronizer<syncPolicy4> sync4;
    std::shared_ptr<sync4> sync_4_;

    typedef message_filters::sync_policies::ApproximateTime<
        sensor_msgs::msg::CameraInfo,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image> syncPolicy3;
    typedef message_filters::Synchronizer<syncPolicy3> sync3;
    std::shared_ptr<sync3> sync_3_;

    typedef message_filters::sync_policies::ApproximateTime<
        sensor_msgs::msg::CameraInfo,
        sensor_msgs::msg::Image,
        sensor_msgs::msg::Image> syncPolicy2;
    typedef message_filters::Synchronizer<syncPolicy2> sync2;
    std::shared_ptr<sync2> sync_2_;

    typedef message_filters::sync_policies::ApproximateTime<
        sensor_msgs::msg::CameraInfo,
        sensor_msgs::msg::Image> syncPolicy1;
    typedef message_filters::Synchronizer<syncPolicy1> sync1;
    std::shared_ptr<sync1> sync_1_;

    CameraSubscribers(
        std::shared_ptr<rclcpp::Node> node,
        FrameQueue& frames,
        std::function<void(const sensor_msgs::msg::CameraInfo::ConstSharedPtr)> setIntrinsics);

private:

    // Multiple Camera callback functions.
    void depthImgCallback4(
        const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
        const sensor_msgs::msg::Image::ConstSharedPtr& img1,
        const sensor_msgs::msg::Image::ConstSharedPtr& img2,
        const sensor_msgs::msg::Image::ConstSharedPtr& img3,
        const sensor_msgs::msg::Image::ConstSharedPtr& img4);

    void depthImgCallback3(
        const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
        const sensor_msgs::msg::Image::ConstSharedPtr& img1,
        const sensor_msgs::msg::Image::ConstSharedPtr& img2,
        const sensor_msgs::msg::Image::ConstSharedPtr& img3);

    void depthImgCallback2(
        const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
        const sensor_msgs::msg::Image::ConstSharedPtr& img1,
        const sensor_msgs::msg::Image::ConstSharedPtr& img2);

    void depthImgCallback1(
        const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
        const sensor_msgs::msg::Image::ConstSharedPtr& img);

    void queueImage(const sensor_msgs::msg::Image::ConstSharedPtr& msgD);

    // Callback for setting the intrinsics
    std::function<void(const sensor_msgs::msg::CameraInfo::ConstSharedPtr)> setIntrinsicsCb_;

    // Camera Info subscriber
    message_filters::Subscriber<sensor_msgs::msg::CameraInfo> sub_caminfo_;

    // Depth image subscribers
    message_filters::Subscriber<sensor_msgs::msg::Image> sub_depth_1_;
    message_filters::Subscriber<sensor_msgs::msg::Image> sub_depth_2_;
    message_filters::Subscriber<sensor_msgs::msg::Image> sub_depth_3_;
    message_filters::Subscriber<sensor_msgs::msg::Image> sub_depth_4_;

    // Received intrinsics
    bool intrinsics_ = false;

    // queue of images
    FrameQueue& frame_queue_;

    // Number of cameras
    int depthCameras_;
};