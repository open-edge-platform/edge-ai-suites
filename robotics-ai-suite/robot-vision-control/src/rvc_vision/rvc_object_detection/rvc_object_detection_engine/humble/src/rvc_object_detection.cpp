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

#include "rvc_vision_messages/msg/rotated_bb.hpp"
#include "rvc_vision_messages/msg/rotated_bb_list.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "rclcpp/rclcpp.hpp"
#include "cv_bridge/cv_bridge.h"

#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include <image_transport/image_transport.hpp>

#include <sys/types.h>
#include <unistd.h>
#include "rvc_ai_interface.hpp"
#include "rvc_object_detection.hpp"
#include <pluginlib/class_loader.hpp>

using std::placeholders::_1;
using namespace std::chrono_literals;

volatile bool exitBool = false;

using namespace RVC;

void ObjectDetection::m_image_callback(sensor_msgs::msg::Image::UniquePtr msg)
{
    auto stamp = msg->header.stamp;
    auto frame_id = msg->header.frame_id;
    auto my_cv_ptr = cv_bridge::toCvShare(std::move(msg));
    // auto my_cv_ptr = cv_bridge::toCvCopy(std::move(msg));
    const cv::Mat image = my_cv_ptr->image;

    std::vector<std::vector<float>> detections;

    cv::Mat preprocessedImage;

    if (ai->pre_process_image(image, preprocessedImage) == false)
    {
        RCLCPP_INFO(rclcpp::get_logger("OD"), " pre_process_image FAILED");
        return;
    }

    cv::Mat inferenceResults;

    if (ai->run_inference_pipeline(std::move(preprocessedImage), inferenceResults) == false)
    {
        RCLCPP_INFO(
            rclcpp::get_logger("OD"), " run_inference_pipeline FAILED");
        return;
    }

    rvc_vision_messages::msg::RotatedBBList rotatedBBList;

    if (ai->post_process_image(std::move(inferenceResults), rotatedBBList) == false)
    {
        RCLCPP_INFO(rclcpp::get_logger("OD"), " post_process_image FAILED");
        return;
    }

    rotatedBBList.header.stamp = stamp;
    rotatedBBList.header.frame_id = std::move(frame_id);

    m_rotated_bb_list_msg->publish(rotatedBBList);

    if (publish_inference_images_param)
    {
        cv::cvtColor(image, image, cv::COLOR_BGR2RGB);

        std::vector<rvc_vision_messages::msg::RotatedBB>::iterator roi =
            rotatedBBList.rotated_bb_list.begin();

        for (roi; roi < rotatedBBList.rotated_bb_list.end(); roi++) {
            std::ostringstream text;
            text << roi->object_id << " " <<
                int(roi->confidence_level * 100.0f) << "%";

            cv::putText(
                image, text.str(), cv::Point(roi->cx, roi->cy - 5),
                cv::FONT_HERSHEY_SIMPLEX, 0.5, CV_RGB(255, 255, 0), 1);
            cv::Point2f center(roi->cx, roi->cy);
            cv::RotatedRect rotatedRect(cv::Point2f(roi->cx, roi->cy),
                cv::Size2f(roi->width, roi->height), roi->angle);
            cv::Point2f vertices[4];
            rotatedRect.points(vertices);

            for (int i = 0; i < 4; ++i) {
                cv::line(
                    image, vertices[i], vertices[(i + 1) % 4], cv::Scalar(
                        255, 0,
                        0), 1, cv::LINE_8,
                    0);
            }
        }

        static auto prev_ticks = std::chrono::high_resolution_clock::now();
        static auto averageStartTime = std::chrono::high_resolution_clock::now();
        static int frameRate = 0;
        static float averageFPS = 0.0;
        frameRate++;

        auto now = std::chrono::high_resolution_clock::now();
        auto delta_ticks = now - prev_ticks;
        auto fps = 1000000000.0 / (double) delta_ticks.count();

        if ( (averageStartTime - prev_ticks) > std::chrono::seconds(1))
        {
            averageFPS = (float)frameRate * 1000000000.0 / (now - averageStartTime).count();
            averageStartTime = std::chrono::high_resolution_clock::now();
        }

        prev_ticks = now;
        std::ostringstream text;

        rclcpp::Time time_now = get_clock()->now();
        auto ms = (time_now - stamp).nanoseconds() / 1e6;

        text << fps << " AI FPS, " << averageFPS << " Average, " << ms << " ms latency";

        putText(
            image, text.str(), cv::Point(10, 20), cv::FONT_HERSHEY_SIMPLEX, 0.5,
            CV_RGB(127, 255, 0) );

        sensor_msgs::msg::Image::SharedPtr msgImg =
            cv_bridge::CvImage(std_msgs::msg::Header(), "bgr8", image)
            .toImageMsg();

        m_inference_image_pub_.publish(*msgImg.get() );
    }
}

ObjectDetection::~ObjectDetection()
{
    RCLCPP_DEBUG(rclcpp::get_logger("OD"), "ObjectDetection: destructor called...");
}

ObjectDetection::ObjectDetection(const rclcpp::NodeOptions & options)
  : Node("object_detection", options)
{
    this->declare_parameter<bool>("publish_inference_images", true);
    this->declare_parameter<std::string>("model_name", "yolo_nano");
    this->declare_parameter<std::string>("plugin_name", "RVC_AI::OIInference");

    std::string inference_device;
#ifndef BUILD_SENSOR_DATA
    auto inference_rmw_qos = rmw_qos_profile_default;
#else
    auto inference_rmw_qos = rmw_qos_profile_sensor_data;
#endif

    auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(inference_rmw_qos), inference_rmw_qos);

    auto rmw = qos.get_rmw_qos_profile();
    try {
        publish_inference_images_param = get_parameter("publish_inference_images").as_bool();
        model_name_param = get_parameter("model_name").as_string();

        RCLCPP_INFO(
            this->get_logger(), "\t publish_inference_images %d", publish_inference_images_param);
        RCLCPP_INFO(this->get_logger(), "\t model_name %s", model_name_param.c_str());
        RCLCPP_INFO_STREAM(
            this->get_logger(),
            "Intra-Process is " <<
                ( this->get_node_options().use_intra_process_comms() ? "ON" : "OFF" ) );
    } catch (const std::exception & e) {
        RCLCPP_INFO(
            this->get_logger(), "Exception thrown during init stage with message: %s \n",
            e.what() );
    }

    if (publish_inference_images_param)
    {
        m_inference_image_pub_ = image_transport::create_publisher(
            this,
            "annotated_image",
            inference_rmw_qos);
    }

    rclcpp::SubscriptionOptions optionsCallbackOptions;
    optionsCallbackOptions.callback_group = create_callback_group(
        rclcpp::CallbackGroupType::Reentrant);
    //optionsCallbackOptions.callback_group = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    std::string ns = this->get_namespace();
    std::string topic_prefix = std::string ("camera/camera") + ns.substr(1, ns.size() - 1) + std::string("/");

    m_image_sub = this->create_subscription<sensor_msgs::msg::Image>(
        topic_prefix + std::string("color/image_raw"), qos, std::bind(
            &ObjectDetection::m_image_callback, this,
            _1), optionsCallbackOptions);

    m_rotated_bb_list_msg = this->create_publisher<rvc_vision_messages::msg::RotatedBBList>(
        "detections", qos);

    try {

        RCLCPP_INFO(get_logger(), "Trying to load Inference plugin...");
        pluginlib::ClassLoader<RVC_AI::RVCAIInterface> aiLoader("rvc_ai_interface",
            "RVC_AI::RVCAIInterface");

        auto inference_plugin_name = get_parameter("plugin_name").as_string();
        RCLCPP_INFO(
            get_logger(), "Trying to load Inference plugin name %s...",
            inference_plugin_name.c_str());

        ai = aiLoader.createSharedInstance(inference_plugin_name);

        auto result = ai->init(this, model_name_param);

        if (result != true)
        {
            RCLCPP_INFO(
                get_logger(), "Plugin %s failed to initialize, aborting....",
                inference_plugin_name.c_str());
            exit(0);
        }

        RCLCPP_INFO(get_logger(), "DNN Model %s Loaded.", model_name_param.c_str());
    } catch (const std::exception & e) {
        RCLCPP_INFO(
            this->get_logger(), "Exception thrown during init stage with message: %s \n",
            e.what() );
        exit(0);
    } catch (...) {
        RCLCPP_INFO(
            get_logger(), "Looking for OpenVino Model Files %s FAILED", model_name_param.c_str());
    }

    rclcpp::on_shutdown(
        [&]
        {
            ai->on_shutdown();
        });
}

#include "rclcpp_components/register_node_macro.hpp"

RCLCPP_COMPONENTS_REGISTER_NODE(RVC::ObjectDetection)
