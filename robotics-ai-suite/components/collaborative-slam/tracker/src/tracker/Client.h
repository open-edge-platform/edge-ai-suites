// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
/*
An universal client function for multiple robot system. The function is as below:
1, Getting local landmarks(map) and local keyframe from the slam system , convert them to Ros message and send it to
server. 2, Receiving updated message(local landmarks and keyframes) from and server, and then updating slam state.

What you should do is to set the slam system, local landmarks(map) and local keyframe source.
*/

#include <rclcpp/rclcpp.hpp>

#include "camera/base.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "tracking_module.h"
#include "mapping_module.h"
#include "univloc_msgs.h"
#include "tracker/fast_mapping_module.h"
#include "univloc_tracker/Tracker.h"
#include "univloc_tracking_module.h"

#include <atomic>
#include <memory>
#include <queue>

namespace Camera = openvslam::camera;

#define MAPRANGE std::numeric_limits<uint8_t>::max()
#define KFRANGE std::numeric_limits<uint16_t>::max()
#define MPRANGE std::numeric_limits<uint32_t>::max()
#define UIDRANGE std::numeric_limits<uint32_t>::max()

typedef openvslam::tracking_module Tracking_module;
typedef openvslam::mapping_module Mapping_module;
typedef openvslam::data::frame Frame;
typedef openvslam::data::keyframe Keyframe;
typedef openvslam::data::landmark Landmark;
typedef openvslam::data::map_database Map_database;
typedef fast_mapping::fast_mapping_module FastMapping_module;

namespace univloc_tracker {

typedef rclcpp::Client<univloc_msgs::MapBasedComm>::SharedPtr CommClientPtr;
typedef rclcpp::Service<univloc_msgs::MapBasedComm>::SharedPtr CommServicePtr;
typedef rclcpp::Client<univloc_msgs::MapBasedComm>::SharedFuture ServiceResponseFuture;

class Client {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    ~Client();
    Client(const Client&)=delete;
    Client& operator=(const Client&)=delete;

    static Client& get_instance();
    void initialize(ConfigConstPtr cfg, Map_database* p_map_db, Camera::base* camera,
                    openvslam::data::bow_vocabulary* bow_vocab, openvslam::data::bow_database* bow_db,
                    std::shared_ptr<rclcpp::Node> node_ptr);

    void set_tracking_module(Tracking_module* p_tracking_module);
    void set_mapping_module(Mapping_module* p_mapping_module);
    void set_fast_mapping_module(FastMapping_module* p_fast_mapping_module);

    void connect_server();
    void run();
    void terminate();
    bool connected() const;

    void convert_landmarks_to_msg(const std::vector<Landmark*>& lmbuffer, univloc_msgs::Map& msg_out);
    void convert_keyframes_to_msg(const std::vector<Keyframe*>& kfbuffer, univloc_msgs::Map& msg_out);

    void convert_erased_id_to_msg(std::vector<KeyframeID>& keyframes, std::vector<LandmarkID>& landmarks,
                                  univloc_msgs::Map& msg_out);


    void queue_send_map(const std::vector<Landmark*>& landmarks, const std::vector<Keyframe*>& keyframes,
                        const std::vector<LandmarkID>& landmarks_id, const std::vector<KeyframeID>& keyframes_id);

    void clear_queue();

    void increase_merge_times();

    void merge_to_be_sent_map(std::vector<Keyframe*>& sent_keyframes, std::vector<Landmark*>& sent_landmarks,
                              std::vector<LandmarkID>& sent_erased_landmarks_id,
                              std::vector<KeyframeID>& sent_erased_keyframes_id);

    std::queue<univloc_msgs::MapConstPtr> relocalization_results_;

    void receive_relocalization_results(univloc_msgs::MapConstPtr msg);

    univloc_msgs::MapConstPtr get_relocalization_results();

    void clear_relocalization_results();
    ClientID get_client_id() const;

    void send_relocalization_request_to_server(Keyframe* keyfrm_to_be_relocalized);
    void get_server_landmarks_using_current_pose(Eigen::Matrix4d curr_pose, KeyframeID curr_id,
                                                 unsigned int relocal_map_id);
    void set_session_start_time(double start_time);

    void process_received_server_landmarks(KeyframeID id);
    void set_latest_keyfrm_local_id(KeyframeID id);

    void send_octree_to_server(univloc_msgs::Octree& octree_msg);

    //! Pre-constructed Octree map
    univloc_msgs::OctreePtr octree_map_msg_;

    //! Pre-constructed Octree parameters
    univloc_msgs::OctreeParamPtr octree_param_msg_;

private:
    Client() {}

    ClientID client_id_ {0};
    std::shared_ptr<rclcpp::Node> node_ptr_ = nullptr;
    CommClientPtr comm_client_ = nullptr;
    CommServicePtr comm_service_ = nullptr;

    int min_keyframes_before_informing_server_ {1};

    std::atomic<bool> running_ {false};
    std::atomic<bool> connected_ {false};

    std::unique_ptr<std::thread> connecting_thread_ = nullptr;
    std::unordered_map<KeyframeID, univloc_msgs::MapConstPtr> received_map_msgs_;
    std::mutex received_msgs_mtx_;
    KeyframeID latest_keyfrm_localization_id_ = 0;

    Tracking_module* p_tracking_module_ = nullptr;
    Mapping_module* p_mapping_module_ = nullptr;
    FastMapping_module* p_fast_mapping_module_ = nullptr;
    Map_database* p_map_db_ = nullptr;
    Camera::base* camera_ = nullptr;
    std::atomic<unsigned int> message_id_ {0};

    mutable std::mutex request_pause_sending_mtx_;
    bool request_pause_sending_msg_ {false};
    bool sending_msg_paused_ {false};
    double session_start_time_ {0.0};

    //! BoW vocabulary
    openvslam::data::bow_vocabulary* bow_vocab_ = nullptr;

    //! BoW database
    openvslam::data::bow_database* bow_db_ = nullptr;

    std::atomic<unsigned int> merge_times_ {0};
    std::mutex sent_map_queue_mtx_;
    std::queue<std::vector<Landmark*>> landmarks_to_be_sent_;
    std::queue<std::vector<Keyframe*>> keyframes_to_be_sent_;
    std::queue<std::vector<LandmarkID>> erased_landmarks_id_;
    std::queue<std::vector<KeyframeID>> erased_keyframes_id_;

    std::mutex mtx_relocalization_;

    typedef void(Client::*service_message_mode)(univloc_msgs::MapConstPtr);
    void send_message(const univloc_msgs::Map& msg);
    void service_message_callback(const std::shared_ptr<univloc_msgs::MapBasedComm::Request> request,
                          std::shared_ptr<univloc_msgs::MapBasedComm::Response> response);
    void process_service_message(univloc_msgs::MapConstPtr map_msg_ptr);
    void process_service_message_localization(univloc_msgs::MapConstPtr map_msg_ptr);
    void process_keyframes();
    void process_landmarks();
    void request_pause_sending_msg();
    void send_camera_info_msg();
    void send_loaded_octree_map_msg();
    bool sending_msg_is_paused() const;
    void update_local_map_from_server(univloc_msgs::MapConstPtr map_msg_ptr);
    void update_server_landmarks(univloc_msgs::MapConstPtr map_msg_ptr);
    service_message_mode servise_message_mode_ = &Client::process_service_message;
    void resume_sending_msg();
    void create_virtual_server_keyframe();
    double current_server_time();
};

}  // namespace univloc_tracker
