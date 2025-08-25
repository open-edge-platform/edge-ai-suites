// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
/*
An universal Server function for multiple robot system. The function is as below:
1, Getting local landmarks(map) and newest keyframe from the slam system , convert them to Ros message and send it to
Server. 2, Receiving updated message(local landmarks and keyframes) from and Server, and then updating slam state.

What you should do is to set the slam system, local landmarks(map) and newest frame source.
*/
//#include "univloc_msgs/Map.h"
//#include "univloc_msgs/Keyframe.h"
//#include "univloc_msgs/Landmark.h"
//#include "univloc_msgs/Descriptor.h"
#include "univloc_msgs.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "data/bow_database.h"
#include "data/bow_vocabulary.h"
#include "data/camera_database.h"
#include "camera/base.h"
#include "camera/perspective.h"
#include "camera/fisheye.h"
#include "camera/equirectangular.h"
#include "module/relocalizer.h"
#include "type.h"

#include <atomic>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <map>
#include <queue>
#include <deque>
#include <shared_mutex>
#include "rclcpp/rclcpp.hpp"
#include <boost/shared_ptr.hpp>
#include <fstream>

#define MAPRANGE std::numeric_limits<MapID>::max()
#define KFRANGE std::numeric_limits<uint16_t>::max()
#define MPRANGE std::numeric_limits<uint32_t>::max()
#define UIDRANGE std::numeric_limits<uint32_t>::max()

namespace Camera = openvslam::camera;

typedef openvslam::data::frame Frame;
typedef openvslam::data::keyframe Keyframe;
typedef openvslam::data::landmark Mappoint;
typedef openvslam::camera::base Camera_base;
typedef openvslam::data::map_database Map_database;
typedef openvslam::data::camera_database Camera_database;
typedef openvslam::data::bow_vocabulary Bow_vocabulary;
typedef openvslam::data::bow_database Bow_database;
typedef boost::shared_ptr<Map_database> Map_database_ptr;
typedef boost::shared_ptr<Keyframe> Keyframe_ptr;
typedef boost::shared_ptr<Mappoint> Mappoint_ptr;

typedef univloc_msgs::Map Map_Msg;
typedef univloc_msgs::CameraInfo Camera_Info_Msg;
typedef univloc_msgs::Landmark Mappoint_Msg;
typedef univloc_msgs::Keyframe Keyframe_Msg;
typedef univloc_msgs::KeyframeUpdate Old_Keyframe_Msg;
typedef univloc_msgs::Descriptor Descriptor_Msg;
typedef univloc_msgs::MapConstPtr Map_Msg_ConstPtr;
typedef univloc_msgs::MapPtr Map_Msg_Ptr;
typedef std::pair<size_t, size_t> Idpair;
typedef boost::shared_ptr<Keyframe_Msg> Keyframe_Msg_ptr;
typedef boost::shared_ptr<Mappoint_Msg> Mappoint_Msg_ptr;

namespace univloc_server {

class Server;

class ClientHandler {
public:
    ClientHandler(ClientID client_id, Server* server);

    ~ClientHandler();

    void receive_map_message(Map_Msg_ConstPtr msg);

    MapID get_map_id() const;

    ClientID get_client_id() const;

    void set_map_id(ClientID map_id);

    Keyframe* get_current_keyframe() const;

    std::vector<Keyframe*> get_latest_keyframe_of_all_sessions() const;

    void pause(bool wait_until_paused = false);

    bool is_paused() const;

    void resume();

    void lock_current_keyframe();

    int msg_queue_size() const;

    unsigned int get_merge_times();

    void increase_merge_times();

    void decrease_merge_times();

    void process_msg_stored_in_queue(MapID merged_mapid);

    void record_mapid_before_optimization();

    void record_mapid_before_optimization(MapID map_id);

    double get_current_session_start_time();

    MapID get_mapid_before_optimization();

    void set_camera_type(const unsigned int camera_type_order);

    void save_trajectory(std::string folder);

    void shutdown();

    Keyframe* get_current_origin_keyframe();

    // Get transform from the world coordinate of the reference map to the world coordinate of the map to be aligned
    std::optional<Eigen::Matrix4d> get_coordinate_transform_matrix();

    // Set transform from the world coordinate of the reference map to the world coordinate of the map to be aligned
    void set_coordinate_transform_matrix(const std::optional<Eigen::Matrix4d>& Tww_aligned_ref);

    void unset_coordinate_transform_matrix();

private:
    void worker();

    template <typename ArrayT>
    void arrayToEigen(Eigen::Matrix4d& dst, const ArrayT& src) const;

    ClientID client_id_;
    MapID map_id_;
    Server* server_;

    std::atomic<MapID> mapid_before_optimization_;

    uint last_msg_id_;

    std::unique_ptr<std::thread> worker_thread_;
    std::atomic<bool> running_;

    std::queue<Map_Msg_ConstPtr> message_queue_;
    bool requesting_pause_, paused_;
    mutable std::mutex message_mutex_;  // protect above queue and bools
    std::condition_variable message_event_;

    Keyframe* current_keyframe_;
    mutable std::shared_mutex current_keyframe_mutex_;
    double current_session_start_time_;
    std::vector<Keyframe*> end_keyframe_of_old_sessions_;  // for stats & visualization only
    mutable std::shared_mutex end_keyframe_of_old_sessions_mutex_;

    std::unique_ptr<ClientID> relative_map_id_;
    std::vector<Keyframe*> new_keyframes_;

    // if merge_times_from_msg < merge_times_, it means the message is old
    std::atomic<unsigned int> merge_times_;
    std::atomic<unsigned int> merge_times_from_msg_;
    Camera::setup_type_t camera_type_ = Camera::setup_type_t::RGBD;

    //! relocalizer
    openvslam::module::relocalizer relocalizer_;
    //! elapsed microseconds for each relocalization process
    double elapsed_ms_ = 0.0;

    Keyframe* process_keyframes(const Map_Msg_ConstPtr& msg);
    void process_mappoints(const Map_Msg_ConstPtr& msg);
    Keyframe* create_rgbd_keyframe_from_msg(const Keyframe_Msg& msg, bool is_relocalization_keyfrm = false);
    Keyframe* create_monocular_keyframe_from_msg(const Keyframe_Msg& msg, bool is_relocalization_keyfrm = false);

    void update_keyframe(Keyframe* pKF, const Keyframe_Msg& msg);
    void update_keyframe(const Old_Keyframe_Msg& msg);

    void update_mappoint(const Mappoint_Msg& msg, Map_database* map_ptr);
    void update_connections();
    void queue_new_keyframe_to_global_optimizer();
    void queue_new_keyframe_to_bow_db();
    void register_new_session(Map_Msg_ConstPtr& msg);

    void print_keyframes_connections(const std::vector<Keyframe*> keyframes) const;

    // add relocalization module for monocular camera
    void relocalize_monocular_image(double msg_timestamp);

    void free_current_keyfrm_after_relocalize();

    // should be only used for sending back server landmarks in localization mode
    void send_back_server_landmarks(Eigen::Matrix4d curr_pose, KeyframeID curr_id, unsigned int localize_map_id);

    Keyframe* last_keyframe_ = nullptr;

    std::vector<KeyframeID> keyframes_;
    Keyframe* current_origin_keyframe_ = nullptr;

    double last_sent_flag_reset_timestamp_ = 0;

    // Transform from the world coordinate of the reference map to the world coordinate of the map to be aligned.
    std::optional<Eigen::Matrix4d> coordinate_transform_ = std::nullopt;
};

}  // namespace univloc_server
