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

#include "Subscribers.h"

#include <opencv2/core/core.hpp>
#include <cv_bridge/cv_bridge.h>

CameraSubscribers::CameraSubscribers(
    std::shared_ptr<rclcpp::Node> node,
    FrameQueue& frame_queue,
    std::function<void(const sensor_msgs::msg::CameraInfo::ConstSharedPtr msg)> setIntrinsics) :
    setIntrinsicsCb_(setIntrinsics),
    frame_queue_(frame_queue)
{
    rclcpp::QoS qos(10);
    auto rmw_qos_profile = qos.get_rmw_qos_profile();

    std::string camera_1_info_topic = node->declare_parameter<std::string>("depth_info_topic", "camera/aligned_depth_to_color/camera_info");

    std::string camera_1_topic = node->declare_parameter<std::string>("depth_topic_1", "camera/aligned_depth_to_color/image_raw");
    std::string camera_2_topic = node->declare_parameter<std::string>("depth_topic_2", "camera_left/aligned_depth_to_color/image_raw");
    std::string camera_3_topic = node->declare_parameter<std::string>("depth_topic_3", "camera_right/aligned_depth_to_color/image_raw");
    std::string camera_4_topic = node->declare_parameter<std::string>("depth_topic_4", "camera_rear/aligned_depth_to_color/image_raw");

    depthCameras_ = node->declare_parameter<int>("depth_cameras", int(1));

    sub_depth_1_.subscribe(node, camera_1_topic, rmw_qos_profile);
    sub_depth_2_.subscribe(node, camera_2_topic, rmw_qos_profile);
    sub_depth_3_.subscribe(node, camera_3_topic, rmw_qos_profile);
    sub_depth_4_.subscribe(node, camera_4_topic, rmw_qos_profile);
    sub_caminfo_.subscribe(node, camera_1_info_topic, rmw_qos_profile);

    if (depthCameras_ == 4)
    {
        sync_4_.reset(new sync4(syncPolicy4(30), sub_caminfo_, sub_depth_1_, sub_depth_2_, sub_depth_3_, sub_depth_4_));
        sync_4_->registerCallback(
            std::bind(
                &CameraSubscribers::depthImgCallback4,
                this,
                std::placeholders::_1,
                std::placeholders::_2,
                std::placeholders::_3,
                std::placeholders::_4,
                std::placeholders::_5));
    }
    else if (depthCameras_ == 3)
    {
        sync_3_.reset(new sync3(syncPolicy3(30), sub_caminfo_ , sub_depth_1_, sub_depth_2_, sub_depth_3_));
        sync_3_->registerCallback(
            std::bind(
                &CameraSubscribers::depthImgCallback3,
                this,
                std::placeholders::_1,
                std::placeholders::_2,
                std::placeholders::_3,
                std::placeholders::_4));
    }
    else if (depthCameras_ == 2)
    {
        sync_2_.reset(new sync2(syncPolicy2(30), sub_caminfo_ , sub_depth_1_, sub_depth_2_));
        sync_2_->registerCallback(
            std::bind(
                &CameraSubscribers::depthImgCallback2,
                this,
                std::placeholders::_1,
                std::placeholders::_2,
                std::placeholders::_3));
    }
    else if (depthCameras_ == 1)
    {
        sync_1_.reset(new sync1(syncPolicy1(100), sub_caminfo_, sub_depth_1_));
        sync_1_->registerCallback(
            std::bind(
                &CameraSubscribers::depthImgCallback1,
                this,
                std::placeholders::_1,
                std::placeholders::_2));
    }
}

void CameraSubscribers::depthImgCallback4(
    const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
    const sensor_msgs::msg::Image::ConstSharedPtr& img1,
    const sensor_msgs::msg::Image::ConstSharedPtr& img2,
    const sensor_msgs::msg::Image::ConstSharedPtr& img3,
    const sensor_msgs::msg::Image::ConstSharedPtr& img4)
{
    if (!intrinsics_)
    {
        setIntrinsicsCb_(info);
        intrinsics_ = true;
    }

    queueImage(img1);
    queueImage(img2);
    queueImage(img3);
    queueImage(img4);
}

void CameraSubscribers::depthImgCallback3(
    const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
    const sensor_msgs::msg::Image::ConstSharedPtr& img1,
    const sensor_msgs::msg::Image::ConstSharedPtr& img2,
    const sensor_msgs::msg::Image::ConstSharedPtr& img3)
{
    if (!intrinsics_)
    {
        setIntrinsicsCb_(info);
        intrinsics_ = true;
    }

    queueImage(img1);
    queueImage(img2);
    queueImage(img3);
}

void CameraSubscribers::depthImgCallback2(
    const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
    const sensor_msgs::msg::Image::ConstSharedPtr& img1,
    const sensor_msgs::msg::Image::ConstSharedPtr& img2)
{
    if (!intrinsics_)
    {
        setIntrinsicsCb_(info);
        intrinsics_ = true;
    }

    queueImage(img1);
    queueImage(img2);
}

void CameraSubscribers::depthImgCallback1(
    const sensor_msgs::msg::CameraInfo::ConstSharedPtr& info,
    const sensor_msgs::msg::Image::ConstSharedPtr& img)
{
    if (!intrinsics_)
    {
        setIntrinsicsCb_(info);
        intrinsics_ = true;
    }
    queueImage(img);
}


void CameraSubscribers::queueImage(const sensor_msgs::msg::Image::ConstSharedPtr& msgD)
{
    cv_bridge::CvImageConstPtr cv_ptrD;

    try {
        cv_ptrD = cv_bridge::toCvCopy(msgD);  //, sensor_msgs::image_encodings::TYPE_16UC1
    } catch (cv_bridge::Exception &e) {
        return;
    }

    std::any cdata = msgD->header;
    double stamp =  rclcpp::Time(msgD->header.stamp).seconds();

    std::shared_ptr<ImageFrame> frame = std::make_shared<ImageFrame>(cv_ptrD->image, stamp, cdata);
    frame_queue_.force_push(frame);
}