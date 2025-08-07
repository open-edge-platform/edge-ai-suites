// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
#include <chrono>
#include <optional>
#include <string>
#include <vector>
#include <sstream>

#include "sensor_msgs/msg/image.h"
#include <tf2_msgs/msg/tf_message.hpp>
#include <yolo_msgs/msg/yolo_frame.hpp>
#include <yolo_msgs/msg/yolo_detection.hpp>

#include "opencv2/core.hpp"
#include "opencv2/imgproc.hpp"

#include "Constants.hpp"
#include "Detection.hpp"


struct QueryFrame
{
    sensor_msgs::msg::Image::SharedPtr msg;

    optional<sensor_msgs::msg::Image::SharedPtr> msg_depth;

    chrono::time_point<chrono::system_clock> arrival_time;
    chrono::time_point<chrono::system_clock> departure_time;

    optional<geometry_msgs::msg::TransformStamped> image_origin;
    string topic_name;

    struct Detection
    {
        int class_id{ 0 };
        string className{};
        float confidence{ 0.0 };
        cv::Scalar color{};
        cv::Rect box{};
        vector<float> mask{};
        vector<float> pose{};

        string toString()
        {
            stringstream ss;
            ss << "Class: " << className << endl;
            ss << "Confidence: " << confidence << endl;
            ss << "Box: " << box << endl;
            return ss.str();
        }
    };

    vector<Detection> detections;

    QueryFrame( const sensor_msgs::msg::Image::SharedPtr &imgage_msg = nullptr ) : msg( imgage_msg )
    {
        arrival_time = chrono::system_clock::now();
        msg_depth = {};
    };

    shared_ptr<yolo_msgs::msg::YoloFrame> to_YoloFrame( Task task )
    {
        shared_ptr<yolo_msgs::msg::YoloFrame> yoloframe = make_shared<yolo_msgs::msg::YoloFrame>();
        yoloframe->header = msg->header;
        yoloframe->rgb_image = *msg;
        if ( msg_depth.has_value() )
        {
            yoloframe->depth_image = *msg_depth.value();
        }else{
            yoloframe->depth_image = sensor_msgs::msg::Image();
            yoloframe->depth_image.encoding = "";
        }

        if ( image_origin.has_value() )
        {
            yoloframe->camera_transform = image_origin.value();
        }else{
            yoloframe->camera_transform = geometry_msgs::msg::TransformStamped();
            yoloframe->camera_transform.child_frame_id = "";
        }

        yoloframe->task = task_to_string( task );
        vector<yolo_msgs::msg::YoloDetection> yolo_detections;

        for ( auto &detection : detections )
        {
            yolo_msgs::msg::YoloDetection yolo_detection;
            yolo_detection.confidence = detection.confidence;
            yolo_detection.x = detection.box.x;
            yolo_detection.y = detection.box.y;
            yolo_detection.width = detection.box.width;
            yolo_detection.height = detection.box.height;

            if ( task == SEGMENTATION )
            {
                yolo_detection.mask = detection.mask;
            }
            if ( task == POSE )
            {
                vector<float> pose_xy;
                vector<float> pose_visible;
                for ( int i = 0; i < detection.pose.size(); i += 3 )
                {
                    pose_xy.push_back( detection.pose[i + 1] );
                    pose_xy.push_back( detection.pose[i + 2] );
                    pose_visible.push_back( detection.pose[i] );
                }
                yolo_detection.pose_xy = pose_xy;
                yolo_detection.pose_visible = pose_visible;
            }
            if ( task == DETECTION || task == SEGMENTATION )
            {
                yolo_detection.class_name = detection.className;
            }

            yolo_detections.push_back( yolo_detection );
        }
        yoloframe->detections = yolo_detections;

        return yoloframe;
    }

    static cv::Mat draw_detection( QueryFrame &frame,unsigned char *data, Task task, float mask_opacity = 0.3 )
    {
        cv::Mat image =
            cv::Mat( frame.msg->height, frame.msg->width, CV_8UC3,data);
        //memcpy( image.data, frame.msg->data.data(), frame.msg->step * frame.msg->height );
        for ( auto &detection : frame.detections )
        {
            cv::rectangle( image, detection.box, detection.color, 2 );
            string label = detection.className + ": " + to_string( detection.confidence );
            cv::putText( image, label, cv::Point( detection.box.x, detection.box.y - 5 ),
                         cv::FONT_HERSHEY_SIMPLEX, 0.5, detection.color, 2 );
            if ( task == SEGMENTATION )
            {
                cv::Mat mask_mat = cv::Mat( detection.box.height, detection.box.width, CV_32FC1,
                                            detection.mask.data() );
                cv::Mat mask_mat_8u;
                mask_mat.convertTo( mask_mat_8u, CV_8UC1, 255 );
                cv::Mat colored_mask;
                cv::applyColorMap( mask_mat_8u, colored_mask, cv::COLORMAP_JET );

                for ( size_t i = detection.box.y; i < detection.box.y + detection.box.height; i++ )
                {
                    for ( size_t j = detection.box.x; j < detection.box.x + detection.box.width; j++ )
                    {
                        if ( detection.box.contains( cv::Point( j, i ) ) &&
                             detection.mask[( i - detection.box.y ) * detection.box.width +
                                            ( j - detection.box.x )] > 0.3 )
                        {
                            image.at<cv::Vec3b>( i, j ) =
                                image.at<cv::Vec3b>( i, j ) * ( 1.0 - mask_opacity ) +
                                colored_mask.at<cv::Vec3b>( i - detection.box.y,
                                                            j - detection.box.x ) *
                                    mask_opacity;
                        }
                    }
                }
            }
            if ( task == POSE )
            {
                for ( size_t i = 0; i < pose_points; i++ )
                {
                    cv::circle( image,
                                cv::Point( detection.pose[i * values_per_point + 1],
                                           detection.pose[i * values_per_point + 2] ),
                                3, detection.color, -1 );
                }

                const std::vector<std::vector<unsigned int>> SKELETON = {
                    { 4, 2 },   { 2, 0 },   { 0, 1 },   { 1, 3 },  // head
                    { 10, 8 },  { 8, 6 },                          // left arm
                    { 5, 7 },   { 7, 9 },                          // right arm
                    { 6, 5 },   { 6, 12 },  { 11, 12 }, { 5, 11 }, // body
                    { 12, 14 }, { 14, 16 },                        // left leg
                    { 11, 13 }, { 13, 15 }
                }; // right leg
                cv::Scalar bone_color = cv::Scalar( 0, 0, 255 );
                for ( int i = 0; i < SKELETON.size(); i++ )
                {
                    if ( detection.pose[SKELETON[i][0] * values_per_point] > 0.5 &&
                         detection.pose[SKELETON[i][1] * values_per_point] > 0.5 )
                    {
                        cv::line(
                            image,
                            cv::Point( detection.pose[SKELETON[i][0] * values_per_point + 1],
                                       detection.pose[SKELETON[i][0] * values_per_point + 2] ),
                            cv::Point( detection.pose[SKELETON[i][1] * values_per_point + 1],
                                       detection.pose[SKELETON[i][1] * values_per_point + 2] ),
                            bone_color, 2 );
                    }
                }
            }
        }
        return image;
    }

    sensor_msgs::msg::Image to_image_msg( Task task, float mask_opacity = 0.3 )
    {
        sensor_msgs::msg::Image image_msg;
        image_msg.header = msg->header;
        image_msg.height = msg->height;
        image_msg.width = msg->width;
        image_msg.encoding = "rgb8";
        image_msg.is_bigendian = false;
        image_msg.step = msg->step;
        image_msg.data = vector<unsigned char>( msg->data.data(), msg->data.data() + msg->data.size() );
        
        cv::Mat image = draw_detection( *this,image_msg.data.data(), task, mask_opacity );
        return image_msg;
    }


};
