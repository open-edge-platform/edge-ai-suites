// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include "server/client_handler.h"

#include <list>
#include <shared_mutex>

namespace univloc_server {

class CameraFusionModule {
public:
    void read_config(std::string filename);
    CameraFusionModule(Map_database* map_db, rclcpp::Node *node_ptr);
    void get_relative_transform_from_rosparam(rclcpp::Node *pnh);
    void process_new_keyframe(Keyframe* keyframe);

    //! ROS1 and ROS2 get param

    template <typename T>
    void get_ros_param(std::string name, T& dst)
    {
        //pnh_.param(name, dst, dst);
        get_ros_param(name, dst, dst);
    }

    template <typename T>
    void get_ros_param(std::string name, T& dst, const T& default_value)
    {
        dst = pnh_->declare_parameter(name, default_value);
    }

    void get_ros_param(std::string name, std::string& dst, const char* default_value)
    {
        get_ros_param(name, dst, std::string(default_value));
    }

    void get_ros_param(std::string name, float& dst, double default_value)
    {
        get_ros_param(name, dst, static_cast<float>(default_value));
    }

private:
    using KeyframeQueue = std::list<unsigned int>;
    std::map<ClientID, int> client_group_;
    std::map<int, std::vector<ClientID>> group_clients_;

    std::map<ClientID, Eigen::Affine3d> client_initial_poses_;
    // std::map<ClientID, Eigen::Affine3d> client_estimated_poses_;

    std::map<ClientID, KeyframeQueue> keyframe_queues_;
    std::map<ClientID, std::shared_mutex> keyframe_queue_mutexes_;

    class Constraint {
    public:
        Constraint(int group, ClientID client1, ClientID client2)
            : group(group), small_client(std::min(client1, client2)), large_client(std::max(client1, client2))
        {
        }

        bool operator==(const Constraint& other) const
        {
            return (group == other.group) && (small_client == other.small_client) &&
                   (large_client == other.large_client);
        }

        bool operator<(const Constraint& other) const
        {
            if (group < other.group) return true;
            if (small_client < other.small_client) return true;
            if (large_client < other.large_client) return true;
            return false;
        }

    private:
        int group;
        ClientID small_client;
        ClientID large_client;
    };

    std::map<Constraint, int> constraints_;

    Map_database* map_db_;

    size_t buffer_size_;
    double stamp_diff_threshold_ = 0.0;
    rclcpp::Node *pnh_;
};

}  // namespace univloc_server
