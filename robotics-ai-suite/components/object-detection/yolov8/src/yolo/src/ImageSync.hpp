// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
#include <functional> 
#include <unordered_map> 
#include <queue>
#include <vector> 
#include <mutex>
#include <iostream>
#include <cmath> 

// The following includes are for ROS2 (Robot Operating System 2) specific types
#include "sensor_msgs/msg/image.hpp" 

class ImageSync
{
public:
    // 1s is 1e9 nanoseconds
    u_int64_t acceptable_synchronization_error_nanoseconds = 1e9 * 0.01;

    function<void( const sensor_msgs::msg::Image::SharedPtr &,
                   const sensor_msgs::msg::Image::SharedPtr & )>
        callback;

private:
    using value_type = std::pair<u_int64_t, u_int32_t>;
    struct MyComparator
    {

        bool operator()( const value_type &a, const value_type &b ) const
        {
            return a.first > b.first;
        }
    };
    u_int32_t counter = 0;
    unordered_map<u_int32_t, sensor_msgs::msg::Image::SharedPtr> rgb_map;
    unordered_map<u_int32_t, sensor_msgs::msg::Image::SharedPtr> depth_map;

    priority_queue<value_type, vector<value_type>, MyComparator> queue_rgb;
    priority_queue<value_type, vector<value_type>, MyComparator> queue_depth;
    mutex queue_mutex;

    void resolve()
    {
        if ( rgb_map.size() > 1000 || depth_map.size() > 1000 )
        {
            cout << "Error memory leak" << endl;
        }

        while ( !( queue_rgb.empty() || queue_depth.empty() ) )
        {
            if ( abs<long>( static_cast<long>( queue_rgb.top().first ) -
                            static_cast<long>( queue_depth.top().first ) ) <
                 acceptable_synchronization_error_nanoseconds )
            {
                callback( rgb_map[queue_rgb.top().second], depth_map[queue_depth.top().second] );
                rgb_map.erase( queue_rgb.top().second );
                depth_map.erase( queue_depth.top().second );
                queue_rgb.pop();
                queue_depth.pop();
            }
            else
            {
                if ( queue_rgb.top().first < queue_depth.top().first )
                {
                    rgb_map[queue_rgb.top().second].reset();
                    rgb_map.erase( queue_rgb.top().second );
                    queue_rgb.pop();
                }
                else
                {
                    depth_map[queue_depth.top().second].reset();
                    depth_map.erase( queue_depth.top().second );
                    queue_depth.pop();
                }
            }
        }
    }

public:
    void callback_rgb( const sensor_msgs::msg::Image::SharedPtr &msg )
    {
        u_int64_t nanoseconds = msg->header.stamp.nanosec + msg->header.stamp.sec * 1e9;
        {
            // Lock for critical section
            std::lock_guard<std::mutex> lock(queue_mutex);
            rgb_map[counter] = msg;
            
            queue_rgb.push( { nanoseconds, counter } );
            counter++;
        }
        resolve();
    }

    void callback_depth( const sensor_msgs::msg::Image::SharedPtr &msg )
    {
        u_int64_t nanoseconds = msg->header.stamp.nanosec + msg->header.stamp.sec * 1e9;
        {
            std::lock_guard<std::mutex> lock(queue_mutex);
            depth_map[counter] = msg;
            queue_depth.push( { nanoseconds, counter } );
            counter++;
        }
        resolve();
    }
};
