// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "camera_fusion_module.h"
#include "Eigen/Core"

#include <spdlog/spdlog.h>
#include "rclcpp/rclcpp.hpp"

namespace {
struct Item {
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    ClientID client_id;
    int group;
    Eigen::Matrix4d pose;
};
}

namespace univloc_server {
CameraFusionModule::CameraFusionModule(Map_database* map_db, rclcpp::Node *node_ptr) : map_db_(map_db), pnh_(node_ptr)
{
    int buffer_size;
    get_ros_param("camera_fusion_buffer_size", buffer_size, int(20));
    buffer_size_ = (size_t)buffer_size;
    get_ros_param("camera_fusion_stamp_diff_threshold", stamp_diff_threshold_, double(0.03));
    if (stamp_diff_threshold_ < 0)
        throw std::invalid_argument("camera_fusion_stamp_diff_threshold cannot be negative value!");
    spdlog::info("camera_fusion_stamp_diff_threshold: {}", stamp_diff_threshold_);
    std::string config_filepath;
    get_relative_transform_from_rosparam(pnh_);

    // read_config(config_filepath);
}

void CameraFusionModule::get_relative_transform_from_rosparam(rclcpp::Node *pnh)
{
    std::vector<Item> items = {Item{0, 1, Eigen::Matrix4d::Identity()},  Item{1, 1, Eigen::Matrix4d::Identity()},
                               Item{2, 2, Eigen::Matrix4d::Identity()},  Item{3, 2, Eigen::Matrix4d::Identity()},
                               Item{4, 3, Eigen::Matrix4d::Identity()},  Item{5, 3, Eigen::Matrix4d::Identity()},
                               Item{6, 4, Eigen::Matrix4d::Identity()},  Item{7, 4, Eigen::Matrix4d::Identity()},
                               Item{8, 5, Eigen::Matrix4d::Identity()},  Item{9, 5, Eigen::Matrix4d::Identity()},
                               Item{10, 6, Eigen::Matrix4d::Identity()}, Item{11, 6, Eigen::Matrix4d::Identity()},
                               Item{12, 7, Eigen::Matrix4d::Identity()}, Item{13, 7, Eigen::Matrix4d::Identity()},
                               Item{14, 8, Eigen::Matrix4d::Identity()}, Item{15, 8, Eigen::Matrix4d::Identity()}};

    for (const auto &item : items) {
        ClientID client_id = item.client_id;
        int group = item.group;
        keyframe_queues_[client_id] = KeyframeQueue();
        client_group_[client_id] = group;
        if (group_clients_.find(group) == group_clients_.end()) group_clients_[group] = std::vector<ClientID>();
        group_clients_[group].push_back(client_id);
        client_initial_poses_[client_id] = item.pose;
    }

    int constraint_id = 0;
    for (const auto &it : group_clients_) {
        int group = it.first;
        for (ClientID client1 : it.second) {
            for (ClientID client2 : it.second) {
                if (client2 <= client1) continue;
                constraints_.emplace(Constraint(group, client1, client2), constraint_id);
                std::vector<double> T_vec;
                std::string rospara_name = "Tc" + std::to_string(client1) + "c" + std::to_string(client2);
                if (pnh->get_parameter(rospara_name, T_vec))
                {
                    spdlog::debug("rospara_name: {}", rospara_name);
                    Eigen::Vector3d t(T_vec[0], T_vec[1], T_vec[2]), r(T_vec[3], T_vec[4], T_vec[5]);
                    // For RPY
                    Eigen::AngleAxisd rollAngle(r[0], Eigen::Vector3d::UnitX());
                    Eigen::AngleAxisd pitchAngle(r[1], Eigen::Vector3d::UnitY());
                    Eigen::AngleAxisd yawAngle(r[2], Eigen::Vector3d::UnitZ());

                    Eigen::Matrix3d rotationMatrix =
                        rollAngle.toRotationMatrix() * pitchAngle.toRotationMatrix() * yawAngle.toRotationMatrix();

                    Eigen::Matrix4d Transform_c = Eigen::Matrix4d::Identity();
                    Transform_c.block(0, 0, 3, 3) = rotationMatrix;
                    Transform_c.block(0, 3, 3, 1) = t;

                    Eigen::Affine3d relative_pose(Transform_c);
                    map_db_->add_constraint(constraint_id, relative_pose);
                    constraint_id++;
                }
            }
        }
    }
}

void CameraFusionModule::read_config(std::string filename)
{
    // TODO read from yaml
    (void)(filename);

    std::vector<Item> items = {Item{0, 1, Eigen::Matrix4d::Identity()}, Item{1, 1, Eigen::Matrix4d::Identity()}};
    for (const auto &item : items) {
        ClientID client_id = item.client_id;
        int group = item.group;
        keyframe_queues_[client_id] = KeyframeQueue();
        client_group_[client_id] = group;
        if (group_clients_.find(group) == group_clients_.end()) group_clients_[group] = std::vector<ClientID>();
        group_clients_[group].push_back(client_id);
        client_initial_poses_[client_id] = item.pose;
    }

    int constraint_id = 0;
    for (const auto &it : group_clients_) {
        int group = it.first;
        for (ClientID client1 : it.second) {
            for (ClientID client2 : it.second) {
                if (client2 <= client1) continue;
                constraints_.emplace(Constraint(group, client1, client2), constraint_id);
                Eigen::Affine3d relative_pose(client_initial_poses_[client1].inverse() *
                                              client_initial_poses_[client2]);
                map_db_->add_constraint(constraint_id, relative_pose);
                spdlog::debug("add_constraint {} for client {} and {}", constraint_id, (int)client1, (int)client2);
                constraint_id++;
            }
        }
    }
}

void CameraFusionModule::process_new_keyframe(Keyframe* keyframe)
{
    ClientID client1 = keyframe->client_id_;
    if (client_group_.find(client1) == client_group_.end()) {
        spdlog::warn("Skip un-configurated client {}", client1);
        return;
    }
    int group = client_group_.at(client1);
    // Update buffer
    {
        std::unique_lock lock(keyframe_queue_mutexes_[client1]);
        KeyframeQueue& buffer = keyframe_queues_[client1];
        buffer.push_back(keyframe->id_);
        while (buffer.size() > buffer_size_) buffer.pop_front();
    }

    // Find matched keyframe
    spdlog::debug("Looking for camera fuse");
    for (ClientID client2 : group_clients_[group]) {
        if (client2 == client1) continue;
        std::shared_lock lock(keyframe_queue_mutexes_[client2]);
        KeyframeQueue& buffer = keyframe_queues_[client2];
        for (auto kf_id : buffer) {
            Keyframe* kf2 = map_db_->get_keyframe(kf_id);
            if (!kf2) continue;
            // if (keyframe->get_map_id() < kf2->get_map_id()) continue;
            double timediff = std::abs(kf2->timestamp_ - keyframe->timestamp_);
            if (timediff < stamp_diff_threshold_) {
                spdlog::debug("Constrain client-{} keyframe {} with client{} keyframe {} (stamp diff {} ms)",
                              keyframe->client_id_, keyframe->id_, kf2->client_id_, kf2->id_, timediff * 1000);
                auto constraint_id = constraints_.at(Constraint(group, client1, client2));
                keyframe->graph_node_->add_constraint_edge(constraint_id, kf2);
                kf2->graph_node_->add_constraint_edge(constraint_id, keyframe);
                if (keyframe->client_id_ > kf2->client_id_) {
                    spdlog::debug("Relative pose in map {} and map {}", keyframe->get_map_id(), kf2->get_map_id());
                    spdlog::debug("Traj Length1: {}, Traj length2: {}",
                                  keyframe->get_cam_pose_inv().block(0, 3, 3, 1).norm(),
                                  kf2->get_cam_pose_inv().block(0, 3, 3, 1).norm());
                } else {
                    spdlog::debug("Relative pose in map {} and map {}", kf2->get_map_id(), keyframe->get_map_id());
                    spdlog::debug("Traj Length1: {}, Traj length2: {}",
                                  kf2->get_cam_pose_inv().block(0, 3, 3, 1).norm(),
                                  keyframe->get_cam_pose_inv().block(0, 3, 3, 1).norm());
                }
            }
        }
    }
}
}  // namespace univloc_server
