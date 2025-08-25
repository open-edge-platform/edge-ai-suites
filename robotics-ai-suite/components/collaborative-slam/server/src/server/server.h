// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
/*
An universal Server function for multiple robot system. The function is as below:
1, Getting local landmarks(map) and newest keyframe from the slam system , convert them to Ros message and send it to
Server. 2, Receiving updated message(local landmarks and keyframes) from and Server, and then updating slam state.

What you should do is to set the slam system, local landmarks(map) and newest frame source.
*/

#include "config.h"
#include "server/client_handler.h"
#include "server/camera_fusion_module.h"
#include "server/univloc_global_optimization_module.h"
#include <tf2_ros/transform_broadcaster.h>
#include <tf2/transform_datatypes.h>
#include <tf2_ros/transform_listener.h>
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include "std_msgs/msg/string.hpp"

#include <fast_mapping_helper.h>
#include <se/volume_traits.hpp>
#include <se/octree.hpp>
#include <se/node_iterator.hpp>

namespace Camera = openvslam::camera;

namespace openvslam {
class ServerSystem;
}

namespace univloc_server {

typedef rclcpp::Client<univloc_msgs::MapBasedComm>::SharedPtr CommClientPtr;
typedef rclcpp::Service<univloc_msgs::MapBasedComm>::SharedPtr CommServicePtr;
typedef rclcpp::Client<univloc_msgs::MapBasedComm>::SharedFuture ServiceResponseFuture;

enum class server_mode_t { Mapping, Localization, Relocalization, Remapping };

class Server {
public:
    Server(Camera_database* cam_db, Bow_vocabulary* bow_vocab, Bow_database* bow_db, Map_database* p_map_db,
           rclcpp::Node *node_ptr, const std::shared_ptr<openvslam::config>& cfg);
    ~Server();

    void connect_tracker(ClientID client_id);

    void record_mapid_before_optimization(const Keyframe* kf);
    void record_mapid_before_optimization(const MapID map_id);

    MapID get_running_client_map_id(Keyframe* keyfrm) const;
    MapID get_running_client_map_id(ClientID client_id) const;
    void ros_publisher();
    void set_global_optimization_module(openvslam::univloc_global_optimization_module* global_optimizer);
    void pause_process_msg(ClientID client_id, bool wait_until_paused = false);
    void resume_process_msg();
    bool is_paused();
    void set_global_optimized(bool global_optimized = true);
    void pub_client_local_map();
    void post_process_after_loop(ClientID client1, ClientID client2, MapID map1, MapID map2);
    void post_process_after_loop(ClientID client1, ClientID client2);
    void pre_process_before_loop(Keyframe* current_keyframe, Keyframe* loop_keyframe);
    void queue_loaded_keyframe_to_global_optimizer();

    void send_nearby_landmarks_to_client(Keyframe* current_frame);
    std::vector<Mappoint*> get_mappoints_near_camera(Keyframe* current_frame);
    void check_camera_fusion(Keyframe* keyframe);
    void set_map_start_time(MapID map_id, double start_time);
    double get_map_start_time(MapID map_id);
    bool is_running_optimization();
    void save_trajectory();
    Keyframe* get_client_origin_keyframe(const ClientID client_id);
    void shutdown();

    //! octree related functions
    std::unordered_map<ClientID, std::shared_ptr<se::Octree<SE_FIELD_TYPE>>>& get_octree_from_trackers();
    std::unordered_map<ClientID, struct fast_mapping::se_cfg>& get_octree_cfg_from_trackers();
    std::unordered_map<ClientID, struct fast_mapping::camera_intrinsics>& get_octree_intrinsic_from_trackers();
    void request_octree_from_clients(const std::set<ClientID>& client_ids);
    void mapmsg_to_param_and_octree(const Map_Msg_ConstPtr map_msg_ptr,
                                    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree,
                                    struct fast_mapping::camera_intrinsics& octree_intrinsic,
                                    struct fast_mapping::se_cfg& octree_cfg);
    bool received_all_octrees() const;
    void transform_voxel_and_add_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                                  const Eigen::Vector3f& pos_world_to_transform,
                                                  const Eigen::Matrix4d& Tww_aligned_ref,
                                                  const se::Node<SE_FIELD_TYPE>::value_type& origin_voxel_data,
                                                  const std::vector<std::array<int, 4>>& leaf_node_region,
                                                  const int pose_id, bool is_leaf_node, const int side = 0,
                                                  const float min_acceptable_z = 0.0);
    void integrate_voxelblocks_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform,
                                                std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                                const Eigen::Matrix4d& coordinate_transform,
                                                const std::vector<std::array<int, 4>>& leaf_node_region);
    void integrate_leaf_nodes_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform,
                                               std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                               const Eigen::Matrix4d& coordinate_transform,
                                               const std::vector<std::array<int, 4>>& leaf_node_region);
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> compact_merged_octree(
        const std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree);
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merge_octree_from_trackers(
        std::shared_ptr<se::Octree<SE_FIELD_TYPE>> ref_octree,
        std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform, const Eigen::Matrix4d& coordinate_transform);
    void send_merged_octree_to_trackers();
    void create_octree_related_publishers();
    std::mutex octree_mutex_;

    // set transform from the world coordinate of the reference map to the world coordinate of the map to be aligned
    void set_coordinate_transform(ClientID client_id_for_map_to_be_aligned,
                                  const Eigen::Matrix4d transform_ww_aligned_ref);

    //! Functions used in remapping mode
    void remove_clients_pointcloud_outside_remapping_region(); // Pointcloud: keyframes and landmarks

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

protected:
    friend ClientHandler;
    Map_database* get_map_database() const { return p_all_map_db_; }
    Bow_vocabulary* get_bow_vocabulary() const { return bow_vocab_; }
    Bow_database* get_bow_database() const { return bow_db_; }
    Camera_database* get_camera_database() const { return cam_db_; }
    openvslam::univloc_global_optimization_module* get_global_optimizer() const { return global_optimizer_; }
    void publish_tf(Keyframe* frame, ClientID client_id);
    std_msgs::msg::ColorRGBA client_id_to_color(ClientID id);
    void add_client_colors(ClientID client_id);

private:
    rclcpp::Node *pnh_;
    const std::shared_ptr<openvslam::config> cfg_;
    server_mode_t server_mode_ = server_mode_t::Mapping;

    CommServicePtr comm_service_ = nullptr;
    bool force_best_effort_qos_ = false;

    bool is_request_octree_ = false;
    bool is_merged_octree_ = false;
    bool global_optimized_ = false;
    std::string delay_time_record_folder_;
    // Near landmarks and far landmarks distance threshold
    double near_distance_ = 0.0, far_distance_ = 0.0, back_distance_ = 0.0;
    // const unsigned int process_delay_ = 5;
    openvslam::univloc_global_optimization_module* global_optimizer_ = nullptr;
    std::map<MapID, double> map_start_time_;
    // Camera-baselink extrinsic parameters
    // TODO sending message to client should be executed by ClientHandler
    std::unordered_map<ClientID, CommClientPtr> comm_client_map_;
    std::unordered_map<ClientID, std::unique_ptr<std::thread>> connecting_threads_;
    openvslam::ServerSystem* slam_system_ = nullptr;

    Map_database* p_all_map_db_;
    std::unique_ptr<CameraFusionModule> camera_fusion_module_;

    //! BoW vocabulary
    Bow_vocabulary* bow_vocab_ = nullptr;

    //! BoW database
    Bow_database* bow_db_ = nullptr;

    Camera_database* cam_db_ = nullptr;

    //! Octree map and related parameters
    struct fast_mapping::se_cfg loaded_octree_cfg_;
    struct fast_mapping::camera_intrinsics loaded_intrinsics_;
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> loaded_octree_;
    std::unique_ptr<fast_mapping::remapping_region> remapping_region_;
    std::unordered_map<ClientID, std::shared_ptr<se::Octree<SE_FIELD_TYPE>>> octree_from_trackers_;
    // octree_cfg_from_trackers_ is used to get zmin and zmax in the code, may used for other usage later
    std::unordered_map<ClientID, struct fast_mapping::se_cfg> octree_cfg_from_trackers_;
    // octree_intrinsic_from_trackers_ is not used in the code, added here for future usage
    std::unordered_map<ClientID, struct fast_mapping::camera_intrinsics> octree_intrinsic_from_trackers_;

    //! interval for publishing to visuaization topic
    double visualization_interval_ = 1.0;

    std::string map_out_topic_name_, map_in_topic_name_;
    rclcpp::Publisher <visualization_msgs::msg::MarkerArray>::SharedPtr keypoints_publisher_;
    rclcpp::Publisher <visualization_msgs::msg::MarkerArray>::SharedPtr keyframes_publisher_;
    rclcpp::Publisher <visualization_msgs::msg::MarkerArray>::SharedPtr camera_view_publisher_;
    rclcpp::Publisher <visualization_msgs::msg::MarkerArray>::SharedPtr pub_octree_map_;
    rclcpp::Publisher <nav_msgs::msg::OccupancyGrid>::SharedPtr pub_occupancy_map_;
    std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
    rclcpp::TimerBase::SharedPtr timer_;

    nav_msgs::msg::OccupancyGrid::SharedPtr grid_template_;

    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr octree_sync_request_;

    std::unordered_map<ClientID, ClientHandler> handlers_;

    // Instead of calculating color on every ROS publish (which is quite frequent)
    // calculate it only once new client has been added.
    std::unordered_map<ClientID, std_msgs::msg::ColorRGBA> client_id_color_;
    std::unordered_map<ClientID, std::unordered_map<std::string, std_msgs::msg::ColorRGBA>> camera_view_color_mapping_;

    Map_Msg map_msg_;
    std::string save_traj_folder_;

    void send_message(ClientID client_id, const univloc_msgs::Map& msg);
    void service_message_callback(const std::shared_ptr<univloc_msgs::MapBasedComm::Request> request,
                          std::shared_ptr<univloc_msgs::MapBasedComm::Response> response);
    void process_service_message(Map_Msg_ConstPtr pMsg);
    void get_local_keyframes_and_mappoints(Keyframe* cur_keyframe, std::vector<Keyframe*>& local_keyframes,
                                           std::vector<Mappoint*>& local_mappoints);

    void convert_mappoints_to_msg(std::vector<Mappoint*> landmarks_buff, univloc_msgs::Map& msg_out,
                                  bool only_send_extra = false);
    void convert_keyframes_to_msg(std::vector<Keyframe*> keyframes_buff, univloc_msgs::Map& msg_out,
                                  ClientID client_id);
    void save_client_camera(Map_Msg_ConstPtr map_camerainfo_msg);
    //! Send message to specific client
    void send_msg_to_client(ClientID client_id, univloc_msgs::Map& msg_to_be_sent);

    void publish_keypoints();
    void publish_keyframes();
    void publish_octree_map();
    void publish_occupancy_map();
    void send_updatedstate_to_client(ClientID client_id, bool is_loop_closure = true);
    void publish_camera_view(Keyframe *kf);

    void octree_sync_callback(const std_msgs::msg::String::SharedPtr msg);

    //! Functions used in remapping mode
    bool remove_pointcloud_within_remapping_region(); // Pointcloud: keyframes and landmarks
};

}  // namespace univloc_server
