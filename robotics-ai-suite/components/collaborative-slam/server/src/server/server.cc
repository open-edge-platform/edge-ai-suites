// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "server.h"
#include <iostream>
#include <opencv2/core/eigen.hpp>
#include <stdexcept>
#include <time.h>
#include "timing.h"
#include "file_io.h"
//#include <boost/make_shared.hpp>
#include "rclcpp/serialization.hpp"
#include "rclcpp/serialized_message.hpp"
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud.hpp>
#include <geometry_msgs/msg/point32.h>
#include <tf2_ros/transform_broadcaster.h>
#include <tf2/transform_datatypes.h>
#include <tf2_ros/transform_listener.h>
#ifdef PRE_ROS_HUMBLE
#include <tf2_eigen/tf2_eigen.h>
#else
#include <tf2_eigen/tf2_eigen.hpp>
#endif
#include <sstream>
#include <string>
#include <stack>
#include <spdlog/spdlog.h>
#if defined(SPDLOG_VERSION) && (SPDLOG_VERSION >= 10600)
#include <spdlog/cfg/env.h>  // exist in spdlog v1.6+
#define SPDLOG_SUPPORT_ENV
#endif
#include "spdlog/fmt/ostr.h"
#include <fstream>
#include "ServerSystem.h"

#define VISIBLE_LANDMARKS_COLOR    "visible_landmarks_color"
#define CONVEX_COLOR               "convex_color"
#define FIELD_OF_VIEW_COLOR        "field_of_view_color"
#define FREE_VOXEL_PROPORTION_THRE 0.9
#define Z_AXIS_CHANGE_THRE         0.1
#define MAX_NODE_SIZE              32
#define Z_MIN_EXTEND_VOXEL_NUM     1

using namespace cv;

struct Color {
    std::string name;
    int r;
    int g;
    int b;
};

static const std::vector<Color> all_colors = {
    Color{"red", 255, 0, 0}, Color{"blue", 0, 0, 255}, Color{"green", 0, 255, 0}, Color{"pink", 255, 192, 203},
    Color{"yellow", 255, 255, 0}, Color{"hot_pink", 255, 105, 180}, Color{"orange", 255, 165, 0},
    Color{"purple", 128, 0, 128}, Color{"orange_red", 255, 59, 0}, Color{"gold", 255, 215, 0},
    Color{"magenta", 255, 0, 255}, Color{"lime", 0, 128, 0},
    // Color{"cyan", 0, 255, 255},
    Color{"chocolate", 210, 105, 30},
    // Color{"brown", 165, 42, 42},
    // Color{"ghost_white", 248, 248, 255},
    // Color{"azure", 240, 255, 255},
    // Color{"black", 0, 0, 0},
    // Color{"gray", 128, 128, 128},
    // Color{"silver", 192, 192, 192}
};

namespace univloc_server {
Server::Server(Camera_database* cam_db, Bow_vocabulary* bow_vocab, Bow_database* bow_db,
               Map_database* p_map_db_all, rclcpp::Node *node_ptr, const std::shared_ptr<openvslam::config>& cfg)
    : pnh_(node_ptr),
      cfg_(cfg),
      p_all_map_db_(p_map_db_all),
      bow_vocab_(bow_vocab),
      bow_db_(bow_db),
      cam_db_(cam_db)
{
#ifdef SPDLOG_SUPPORT_ENV
    spdlog::cfg::load_env_levels();
#else
    char *loglevel = getenv("SPDLOG_LEVEL");
    if (loglevel)
        spdlog::set_level(spdlog::level::from_str(loglevel));
#endif

    if (cfg_->server_mode_ == "mapping")
        server_mode_ = server_mode_t::Mapping;
    else if (cfg_->server_mode_ == "localization")
        server_mode_ = server_mode_t::Localization;
    else if (cfg_->server_mode_ == "relocalization")
        server_mode_ = server_mode_t::Relocalization;
    else if (cfg_->server_mode_ == "remapping")
        server_mode_ = server_mode_t::Remapping;
    else
        throw std::invalid_argument("Available modes: mapping, localization, relocalization, remapping");

    get_ros_param("visualization_interval", visualization_interval_, 1.0);
    if (visualization_interval_ < 0.01 || visualization_interval_ > 1.0)
        throw std::runtime_error("Visualization interval should be between 0.01 and 1.0 seconds.");
    this->timer_ = pnh_->create_wall_timer(std::chrono::duration<double>(visualization_interval_), std::bind(&univloc_server::Server::ros_publisher, this));
    get_ros_param("near_distance", near_distance_, double(0.1));
    get_ros_param("far_distance", far_distance_, double(8));
    get_ros_param("back_distance", back_distance_, double(0));
    // A parameter relative to keyframe start id

    get_ros_param("delay_time_record_folder", delay_time_record_folder_, std::string(""));
    get_ros_param("save_traj_folder", save_traj_folder_, std::string(""));
    auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
    keypoints_publisher_ = pnh_->create_publisher<visualization_msgs::msg::MarkerArray>("~/keypoints", map_qos);
    keyframes_publisher_ = pnh_->create_publisher<visualization_msgs::msg::MarkerArray>("~/keyframes", map_qos);
    camera_view_publisher_ = pnh_->create_publisher<visualization_msgs::msg::MarkerArray>("~/camera_view",
                                                                                          map_qos);
    tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*pnh_);

    octree_sync_request_ = pnh_->create_subscription<std_msgs::msg::String>(
      "~/octree_sync", 10, std::bind(&Server::octree_sync_callback, this, std::placeholders::_1));

    /*
        Set service message deadline time to 0.5s and use Best Effort policy.
        For the detailed explanations about this kind of parameters, please refer to
        https://docs.ros.org/en/foxy/Concepts/About-Quality-of-Service-Settings.html

        In general, we expect the tracker delivers messages as soon as it receive the
        sending request. And in common scenarios, the time duration of 2 messages
        sent through tracker2server service won't be longer than 0.5s.
    */
    // Indicate if we want to force the best effort ROS service QoS
    // For multiple robots > 2 this should be true
    // Forcing best effort will make problem when syncing octree maps between trackers
    get_ros_param("force_best_effort", force_best_effort_qos_, false);
    rmw_qos_profile_t ros_qos = rmw_qos_profile_services_default;
    auto tracker2server_qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(ros_qos), ros_qos);
    if (force_best_effort_qos_) {
        rmw_time_t deadline_t = {0, 500'000'000};
        tracker2server_qos.best_effort().deadline(deadline_t);
    }
    comm_service_ = pnh_->create_service<univloc_msgs::MapBasedComm>("tracker2server",
                        std::bind(&Server::service_message_callback, this, std::placeholders::_1,
                        std::placeholders::_2), tracker2server_qos.get_rmw_qos_profile());

    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    spdlog::info("Created Server node successfully!");

    if (delay_time_record_folder_ != "") {
        if (check_folder_path(delay_time_record_folder_))
            spdlog::info("delay_time_record_folder: {}", delay_time_record_folder_);
        else
            throw std::runtime_error("Cannot use " + delay_time_record_folder_ + " as delay_time_record_folder");
    }
    if (save_traj_folder_ != "") {
        if (check_folder_path(save_traj_folder_))
            spdlog::info("save_traj_folder: {}", save_traj_folder_);
        else
            throw std::runtime_error("Cannot use " + save_traj_folder_ + " as save_traj_folder");
    }

    camera_fusion_module_ = std::make_unique<CameraFusionModule>(p_all_map_db_, pnh_);

    if (server_mode_ == server_mode_t::Remapping) {
        struct fast_mapping::point_2d remapping_region_vertexes[4];
        for (unsigned int i = 0; i < 4; i++) {
            remapping_region_vertexes[i].x_ = cfg_->remapping_region_vertexes_[2 * i];
            remapping_region_vertexes[i].y_ = cfg_->remapping_region_vertexes_[2 * i + 1];
        }
        remapping_region_ = std::make_unique<fast_mapping::remapping_region>(remapping_region_vertexes);
        if (!remove_pointcloud_within_remapping_region())
            throw std::runtime_error("Failed to remove pointcloud within remapping region!");
    }

    // If in localization or remapping mode, check the client ids for visualization
    if (server_mode_ == server_mode_t::Localization || server_mode_ == server_mode_t::Relocalization ||
        server_mode_ == server_mode_t::Remapping) {
        auto loaded_keyframes_pos_inv = p_all_map_db_->get_loaded_keyframes_pos_inv();
        for (const auto& item : loaded_keyframes_pos_inv) {
            ClientID client_id = item.first;
            if (client_id_color_.find(client_id) == client_id_color_.end())
                add_client_colors(client_id);
        }
    }
}

Server::~Server()
{
    handlers_.clear();
    if (loaded_octree_) {
        loaded_octree_->clear();
    }
    spdlog::debug("DESTRUCT: Server");
}

void Server::shutdown() {
    for (auto& id_client : handlers_) {
        id_client.second.shutdown();
    }
    for (const auto& connecting_thread : connecting_threads_) {
        connecting_thread.second->join();
        spdlog::debug("connecting to tracker (ID:{}) thread exited");
    }
    spdlog::info("shutdown SLAM ServerSystem");
}

void Server::connect_tracker(ClientID client_id)
{
    if (comm_client_map_.find(client_id) == comm_client_map_.end()) {
        spdlog::error("failed to retrieve client {} in comm_client_map_ when connecting to tracker.", client_id);
        return;
    }

    CommClientPtr comm_client = comm_client_map_.at(client_id);
    if (!comm_client) {
        spdlog::error("the client pointer of client {} is nullptr, please debug!", client_id);
        return;
    }

    while (!comm_client->wait_for_service(std::chrono::seconds(1))) {
        spdlog::debug("tracker is not available, connecting again...");

        if (!rclcpp::ok()) {
            spdlog::info("interrupted while connecting to the server node. Exiting.");
            return;
        }
    }

    univloc_msgs::Map connect_msg;
    connect_msg.connecting_request = true;
    connect_msg.mn_client_id = client_id;
    connect_msg.msg_timestamp = rclcpp::Clock().now().seconds();
    send_message(client_id, connect_msg);
    spdlog::info("send back connecting request to tracker node.");

    return;
}

MapID Server::get_running_client_map_id(Keyframe* keyfrm) const
{
    if (p_all_map_db_->is_keyframe_loaded(keyfrm)) {
        spdlog::debug("The keyframe {} with client id {} is loaded from previous map!", keyfrm->id_, keyfrm->client_id_);
        return uint32_t(0xFFFFFFFF);
    }

    if (!handlers_.count(keyfrm->client_id_)) {
        spdlog::debug("There is no client {} running!", keyfrm->client_id_);
        return uint32_t(0xFFFFFFFF);
    }

    return handlers_.at(keyfrm->client_id_).get_map_id();
}

MapID Server::get_running_client_map_id(ClientID client_id) const
{
    if (!handlers_.count(client_id)) {
        spdlog::debug("There is no client {} running!", client_id);
        return uint32_t(0xFFFFFFFF);
    }
    return handlers_.at(client_id).get_map_id();
}

void Server::save_trajectory()
{
    if (save_traj_folder_ == "") return;
    for (auto& id_client : handlers_) {
        id_client.second.save_trajectory(save_traj_folder_);
    }
}

void Server::send_message(ClientID client_id, const univloc_msgs::Map& msg)
{
    if (comm_client_map_.find(client_id) == comm_client_map_.end()) {
        spdlog::warn("failed to retrieve client {} in comm_client_map_.", client_id);
        return;
    }

    CommClientPtr comm_client = comm_client_map_[client_id];
    if (unlikely(!comm_client)) {
        spdlog::error("the client pointer of client {} is nullptr, please debug!", client_id);
        return;
    }

    auto client_message_callback = [](ServiceResponseFuture future) {
        auto result = future.get();
        if (nullptr == result || result->resp_status == false) {
            spdlog::debug("failed to receive response from tracker node.");
            return;
        }
    };

    auto request = std::make_shared<univloc_msgs::MapBasedCommRequest>();
    request->req_map = msg;
    spdlog::debug("Send message to Tracker!");
    auto future_result = comm_client->async_send_request(request, std::move(client_message_callback));

    return;
}

void Server::service_message_callback(const std::shared_ptr<univloc_msgs::MapBasedComm::Request> request,
                      std::shared_ptr<univloc_msgs::MapBasedComm::Response> response)
{
    spdlog::debug("Received message from Tracker!");
    if (request == nullptr) {
        spdlog::debug("error receiving response from tracker node.");
        response->resp_status = false;
        return;
    }
    univloc_msgs::MapConstPtr map_msg_ptr = std::make_shared<univloc_msgs::Map>(std::move(request->req_map));
    process_service_message(map_msg_ptr);
    response->resp_status = true;
}

void Server::add_client_colors(ClientID client_id) {
    client_id_color_.insert({client_id, client_id_to_color(client_id)});
    std::unordered_map<std::string, std_msgs::msg::ColorRGBA> camera_pres_colors;
    camera_pres_colors.insert({VISIBLE_LANDMARKS_COLOR, client_id_to_color(client_id + 2)});
    camera_pres_colors.insert({CONVEX_COLOR, client_id_to_color(client_id + 3)});
    camera_pres_colors.insert({FIELD_OF_VIEW_COLOR, client_id_to_color(client_id + 4)});
    camera_view_color_mapping_.insert({client_id, camera_pres_colors});
}

void Server::process_service_message(Map_Msg_ConstPtr map_msg_ptr)
{
    ClientID client_id = map_msg_ptr->mn_client_id;
    double time_delay = rclcpp::Clock().now().seconds() - map_msg_ptr->msg_timestamp;
    spdlog::debug("{}: Message delay : {} s", client_id, time_delay);

    if (handlers_.find(client_id) == handlers_.end()) {
        handlers_.emplace(std::piecewise_construct, std::forward_as_tuple(client_id),
                          std::forward_as_tuple(client_id, this));
        if (client_id_color_.find(client_id) == client_id_color_.end())
            add_client_colors(client_id);
    }

    if (map_msg_ptr->connecting_request)
    {
        if (comm_client_map_.find(client_id) == comm_client_map_.end()) {
            spdlog::info("create Map message based client with ID:{} in comm_client_map_.", client_id);

            std::string client_name("server2tracker_");
            client_name += std::to_string(client_id);
            CommClientPtr comm_client_ = pnh_->create_client<univloc_msgs::MapBasedComm>(client_name);
            comm_client_map_[client_id] = comm_client_;
        }

        if (connecting_threads_.find(client_id) != connecting_threads_.end()) {
            spdlog::debug("join the previous connecting thread for client {}.", client_id);
            connecting_threads_[client_id]->join();
        }
        connecting_threads_[client_id] = std::make_unique<std::thread>(&Server::connect_tracker, this, client_id);
        return;
    }

    if (map_msg_ptr->send_camera_info)  // This message is just for sending camera info
    {
        if (map_msg_ptr->camera_info.empty()) {
            spdlog::warn("No camera info in Map.msg while send_camera_info flag is true!");
            return;
        }

        handlers_.at(client_id).set_camera_type(map_msg_ptr->camera_info[0].setup_type);
        save_client_camera(map_msg_ptr);
        return;
    }

    if (map_msg_ptr->is_octree_map_loaded) {
        /*
            This if condition is used to check the multiple clients case.
            We assume the global Octree map is same among all the clients,
            so we only decide to take the first received one to store on
            the server side.
        */
        if (loaded_octree_) {
            spdlog::warn("The loaded octree map should only be sent once from tracker to server! \
                          The current loaded octree map is sent from client {}", client_id);
        }
        else if (server_mode_ == server_mode_t::Localization || server_mode_ == server_mode_t::Remapping) {
            loaded_octree_ = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
            mapmsg_to_param_and_octree(map_msg_ptr, loaded_octree_, loaded_intrinsics_, loaded_octree_cfg_);
            create_octree_related_publishers();
        }
        return;
    }
    else if (server_mode_ == server_mode_t::Remapping && !loaded_octree_) {
        spdlog::warn("Server won't process any message before loading octree map from tracker in remapping mode");
    }

    if (!cam_db_->has_such_client_camera(client_id)) {
        // TODO request camera info through gRPC
        spdlog::warn("No camera info for client {}", client_id);
        return;
    }
    handlers_.at(client_id).receive_map_message(map_msg_ptr);

    // record delay_time for analysis
    if (delay_time_record_folder_ != "") {
        static std::string record_filename =
            delay_time_record_folder_ + "/" + std::to_string((int)rclcpp::Clock().now().seconds()) + ".txt";
        static std::ofstream record_delaytime(record_filename);
        static bool file_init = true;
        if (file_init) {
            spdlog::info("delay time record file: " + record_filename);
            record_delaytime << "delay_time \t Keyframes_size \t MapPoints_size \n";
        }
        file_init = false;
        record_delaytime << time_delay << "\t"
                         << map_msg_ptr->keyframes.size() << "\t"
                         << map_msg_ptr->landmarks.size() << std::endl;
    }
}

void Server::request_octree_from_clients(const std::set<ClientID>& client_ids)
{
    auto start = now();

    univloc_msgs::Map request_octree_msg;
    request_octree_msg.only_add_landmarks = false;
    request_octree_msg.is_relocalization_result = false;
    request_octree_msg.is_request_for_server_landmarks = false;
    request_octree_msg.loop_closure = false;
    request_octree_msg.is_request_octree = true;
    request_octree_msg.is_merged_octree = false;

    for (auto& id_client : handlers_) {
        if (client_ids.count(id_client.first)) {
            send_msg_to_client(id_client.first, request_octree_msg);
            spdlog::info("[{}]: Send request to client {} for its Octree map!", __func__, id_client.first);
        }
    }

    auto end = now();
    spdlog::debug("request_octree_from_clients cost time: {} ms", duration_ms(end - start));
}

void Server::mapmsg_to_param_and_octree(const Map_Msg_ConstPtr map_msg_ptr,
                                        std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree,
                                        struct fast_mapping::camera_intrinsics& octree_intrinsic,
                                        struct fast_mapping::se_cfg& octree_cfg)
{
    auto start = now();

    if (map_msg_ptr->octree_param.size() == 0) {
        spdlog::warn("The size of the container of Octree param shouldn't be 0!");
        return;
    }

    univloc_msgs::OctreeParam octree_param_msg = map_msg_ptr->octree_param[0];

    // camera intrinsics for Octree usage
    octree_intrinsic.width = octree_param_msg.width;
    octree_intrinsic.height = octree_param_msg.height;
    octree_intrinsic.cx = octree_param_msg.cx;
    octree_intrinsic.cy = octree_param_msg.cy;
    octree_intrinsic.fx = octree_param_msg.fx;
    octree_intrinsic.fy = octree_param_msg.fy;

    // Octree configuration
    octree_cfg.compute_size_ratio = octree_param_msg.compute_size_ratio;
    octree_cfg.voxel_per_side = octree_param_msg.voxel_per_side;
    octree_cfg.volume_size_meter = octree_param_msg.volume_size_meter;
    octree_cfg.noise_factor = octree_param_msg.noise_factor;
    octree_cfg.logodds_lower = octree_param_msg.logodds_lower;
    octree_cfg.logodds_upper = octree_param_msg.logodds_upper;
    octree_cfg.zmin = octree_param_msg.zmin;
    octree_cfg.zmax = octree_param_msg.zmax;
    octree_cfg.depth_max_range = octree_param_msg.depth_max_range;
    octree_cfg.correction_threshold = octree_param_msg.correction_threshold;

    if (map_msg_ptr->octree.size() == 0) {
        spdlog::warn("The size of the container of Octree map shouldn't be 0!");
        return;
    }

    // Octree map
    octree->fromROSMsgToOctree(map_msg_ptr->octree[0]);

    // print related parameters loaded from octree map message.
    /*
    std::cout << loaded_intrinsics_ << std::endl;
    std::cout << loaded_octree_cfg_ << std::endl;
    std::cout << "Origin Position: " << loaded_octree_->get_origin_position().transpose() << std::endl;
    std::cout << "Octree Size: " << loaded_octree_->size() << std::endl;
    std::cout << "Octree Dim: " << loaded_octree_->dim() << std::endl;
    std::cout << "Octree Block Buffer Size: " << loaded_octree_->getBlockBuffer().size() << std::endl;
    std::cout << "Octree Node Buffer Size: " << loaded_octree_->getNodesBuffer().size() << std::endl;
    */

    auto end = now();
    spdlog::debug("Construct octree and its related parameters from mapmsg took {} ms", duration_ms(end - start));
}

bool Server::received_all_octrees() const
{
    if (server_mode_ == server_mode_t::Mapping)
        return octree_from_trackers_.size() == 2;
    else if (server_mode_ == server_mode_t::Remapping)
        return octree_from_trackers_.size() == 1;
    return false;
}

void Server::transform_voxel_and_add_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                                      const Eigen::Vector3f& pos_world_to_transform,
                                                      const Eigen::Matrix4d& Tww_aligned_ref,
                                                      const se::Node<SE_FIELD_TYPE>::value_type& origin_voxel_data,
                                                      const std::vector<std::array<int, 4>>& leaf_node_region,
                                                      const int pose_id, bool is_leaf_node, const int side,
                                                      const float min_acceptable_z)
{
    Eigen::Vector3f new_origin = merged_octree->get_origin_position();
    const float voxel_size = merged_octree->dim() / merged_octree->size();
    const float inverse_voxel_size = 1.f / voxel_size;

    // step1: use coordinate transformation matrix to obtain the 3D locations of
    //        voxels in the world coordinate of ref_octree and its octree coordinate

    // apply coordinate transformation to get the world coordinate of ref_octree/ merged octree
    // Pw_ref = Tww_ref_aligned * Pw_aligned
    Eigen::Vector3f pos_world_ref =
        (Tww_aligned_ref.inverse().cast<float>() * pos_world_to_transform.homogeneous()).head(3);
    // obtain the 3D location (unit in meter and voxel) in the octree coordinate of merged octree
    Eigen::Vector3f pos_voxel = pos_world_ref - new_origin;
    Eigen::Vector3i pos_voxel_scaled = (pos_voxel * inverse_voxel_size).array().floor().cast<int>();

    auto is_voxel_within_leaf_node_region = [&leaf_node_region](const Eigen::Vector3i& v) {
        for (const auto& region : leaf_node_region) {
            if ((v.x() >= region[0]) && (v.x() < region[1]) && (v.y() >= region[2]) && (v.y() < region[3])) return true;
        }
        return false;
    };

    /*
        For the region in the xy plane covered by the leaf nodes of reference octree (we consider as free space),
        we don't integrate voxels from leaf nodes of the octree to be aligned since the free space is already set,
        so there is no need for extra operation which might instead mess up the correct representation.
    */
    if (is_leaf_node && is_voxel_within_leaf_node_region(pos_voxel_scaled)) return;

    // step2: check whether voxel is within map boundary, expand octree if needed
    int x_dir = 0, y_dir = 0, z_dir = 0;
    if (!fast_mapping::within_map_boundary(merged_octree, pos_voxel_scaled, x_dir, y_dir, z_dir)) {
        auto new_offset = merged_octree->expand(Eigen::Vector3i(x_dir, y_dir, z_dir));
        // update origin_position_ for octree
        new_origin -= new_offset;
        merged_octree->set_origin_position(new_origin);
        spdlog::debug("octree expanded, new origin is {}", new_origin.transpose());
    }

    // step3: use the voxel's 3D location to fetch voxelblock in the octree
    //        if failed, then insert new voxelblock based on the voxel
    std::vector<se::Node<SE_FIELD_TYPE>*> traversed_nodes;
    traversed_nodes.reserve(merged_octree->max_node_level() + 1);
    const int size = merged_octree->size();
    auto is_voxel_valid = [size](const Eigen::Vector3i& v) {
        return ((v.x() >= 0) && (v.x() < size) && (v.y() >= 0) && (v.y() < size) && (v.z() >= 0) && (v.z() < size));
    };
    const float height = pos_voxel.z();
    // assume the zmin and zmax are the same for trackers
    float zmin = octree_cfg_from_trackers_.begin()->second.zmin - new_origin(2);
    float zmax = octree_cfg_from_trackers_.begin()->second.zmax - new_origin(2);
    if (is_leaf_node) {
        /*
            For leaf node of octree to be aligned, we need to extend the range of [zmin, zmax] to avoid missing data
            since leaf node's height range could have no intersection with [zmin, zmax]. Altough the coordinate of
            the leaf node is within the [zmin, zmax], its sub-space can be extended outside of the range. For zmin,
            extending by 1 voxel to accommodate for precision loss during calculation, meanwhile, make sure larger
            than the minimum acceptable height to avoid constructing map that includes floor; For zmax, extending by
            the leaf node's side to include all the necessary information (its sub-space) needed.
        */
        zmin = std::max(zmin - voxel_size * float(Z_MIN_EXTEND_VOXEL_NUM), min_acceptable_z - new_origin(2));
        zmax += voxel_size * float(side);
    }
    if (height < zmin || height > zmax) return;
    if (!is_voxel_valid(pos_voxel_scaled)) return;

    // if the voxel's probability is below certain threshold, we will store traversed nodes to count free voxels
    // otherwise, there is no need to store traversed nodes
    se::VoxelBlock<SE_FIELD_TYPE>* new_voxel_block = nullptr;
    if (!is_leaf_node) {
        new_voxel_block = merged_octree->fetch(pos_voxel_scaled(0), pos_voxel_scaled(1), pos_voxel_scaled(2));
        if (!new_voxel_block) {
            new_voxel_block =
                merged_octree->insert(pos_voxel_scaled(0), pos_voxel_scaled(1), pos_voxel_scaled(2), pose_id);
        }
    } else {
        new_voxel_block = merged_octree->fetch_and_store_traversed_nodes(pos_voxel_scaled, traversed_nodes);
        if (!new_voxel_block)
            new_voxel_block =
                merged_octree->insert_and_store_traversed_nodes(pos_voxel_scaled, pose_id, traversed_nodes);
    }

    // check whether the voxelblock is valid or not
    if (!new_voxel_block) {
        spdlog::warn("Fetched or inserted voxel block is nullptr, corresponding frame id is {}, pose is \n{}", pose_id,
                     pos_voxel_scaled.transpose());
        return;
    }

    // step4: within the fetched or inserted voxelblock,
    //        find the corresponding child voxel according to its 3D position
    //        if voxel value isn't set before, set value correspondingly;
    //        else skip operation (or use better strategy in the future).
    Eigen::Vector3i coords_offset = pos_voxel_scaled - new_voxel_block->coordinates();
    int new_dataid =
        coords_offset(0) + coords_offset(1) * new_voxel_block->side + coords_offset(2) * new_voxel_block->sideSq;
    se::Node<SE_FIELD_TYPE>::value_type new_voxel_data = new_voxel_block->data(new_dataid);

    /*
        if voxel isn't set before, then its value should be the same as initial value
        TODO may have better fusion algorithm here such as summing up the values from two octrees
    */
    if (int(new_voxel_data.y) == 0 && int(new_voxel_data.x) == 0) {
        new_voxel_block->data(new_dataid, origin_voxel_data);
        // add counter to free voxel count in node class that initializes from zero
        spdlog::debug("traversed_nodes size is {} after fetch or insert voxel block", traversed_nodes.size());
        for (auto& node : traversed_nodes) node->free_voxel_cnt_ += 1;
    }
    spdlog::debug("Finished transforming voxel and add to merged octree");
}

void Server::integrate_voxelblocks_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform,
                                                    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                                    const Eigen::Matrix4d& coordinate_transform,
                                                    const std::vector<std::array<int, 4>>& leaf_node_region)
{
    spdlog::debug("Started iterating voxelblocks of the map to be transformed");
    const int block_side = octree_to_transform->blockSide;
    const float voxel_size = octree_to_transform->dim() / octree_to_transform->size();
    const Eigen::Vector3f origin = octree_to_transform->get_origin_position();

    std::vector<se::VoxelBlock<SE_FIELD_TYPE>*> blocks;
    octree_to_transform->getBlockList(blocks, false);

    Eigen::Vector3f pos_world = Eigen::Vector3f::Zero();
    Eigen::Vector3i coords = Eigen::Vector3i::Zero();
    for (const auto& block : blocks) {
        coords = block->coordinates();
        // for each voxelblock, get access to each child voxel
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                for (int k = 0; k < block_side; ++k) {
                    int vx = coords(0) + i;
                    int vy = coords(1) + j;
                    int vz = coords(2) + k;

                    // get voxel's 3D location in the world coordinate of the input octree
                    // pos_world = origin + coords*voxel_size + offset*voxel_size + 0.5*voxel_size
                    pos_world(0) = origin(0) + float(vx) * voxel_size;
                    pos_world(1) = origin(1) + float(vy) * voxel_size;
                    pos_world(2) = origin(2) + float(vz) * voxel_size;

                    int dataid = i + j * block->side + k * block->sideSq;
                    // get voxel's original data from voxelblock
                    se::Node<SE_FIELD_TYPE>::value_type origin_voxel_data = block->data(dataid);
                    const int pose_id = block->pose_id_;

                    // add individual voxel to the merged octree
                    transform_voxel_and_add_to_merged_octree(merged_octree, pos_world, coordinate_transform,
                                                             origin_voxel_data, leaf_node_region, pose_id, false);
                }
            }
        }
    }
    spdlog::debug("Finished iterating voxelblocks of the map to be transformed");
}

void Server::integrate_leaf_nodes_to_merged_octree(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform,
                                                   std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree,
                                                   const Eigen::Matrix4d& coordinate_transform,
                                                   const std::vector<std::array<int, 4>>& leaf_node_region)
{
    const int block_side = octree_to_transform->blockSide;
    const float voxel_size = octree_to_transform->dim() / octree_to_transform->size();
    const Eigen::Vector3f origin = octree_to_transform->get_origin_position();

    float zmax = octree_cfg_from_trackers_.begin()->second.zmax;
    float voxelblock_side = block_side * voxel_size;
    int voxelblock_num = int(zmax / voxelblock_side);
    float min_acceptable_z = zmax - voxelblock_side * float(voxelblock_num);

    // get the list of non-block leaf nodes of the input octree that meet the data filter requirement
    // since only the leaf nodes whose probability lower than 0 are used to update occupancy map when publishing
    // we will use the same data to merge octree map as well
    std::vector<se::LeafNode<SE_FIELD_TYPE>> nodes;
    auto filter = [](se::Node<SE_FIELD_TYPE>::value_type data) -> bool { return data.x < 0; };
    octree_to_transform->get_leaf_nodes(nodes, filter);

    // iterate through the non-block leaf nodes
    Eigen::Vector3f pos_world = Eigen::Vector3f::Zero();
    for (const auto& node : nodes) {
        int side = node.side;
        if (side > MAX_NODE_SIZE) continue;  // If node side is too coarse, skip it.

        // use leaf node's original data and pose_id_ to set value for each voxel
        se::Node<SE_FIELD_TYPE>::value_type origin_voxel_data = node.data;
        const int pose_id = node.pose_id;

        // for each leaf node, separate it into spatial voxels
        for (int i = 0; i < side; i++) {
            for (int j = 0; j < side; j++) {
                for (int k = 0; k < side; ++k) {
                    int vx = node.coordinates(0) + i;
                    int vy = node.coordinates(1) + j;
                    int vz = node.coordinates(2) + k;

                    // get voxel's 3D location in the world coordinate of the input octree
                    // pos_world = origin + coords*voxel_size + offset*voxel_size + 0.5*voxel_size
                    pos_world(0) = origin(0) + float(vx) * voxel_size;
                    pos_world(1) = origin(1) + float(vy) * voxel_size;
                    pos_world(2) = origin(2) + float(vz) * voxel_size;

                    // for each voxel, add individual voxel to the merged octree
                    transform_voxel_and_add_to_merged_octree(merged_octree, pos_world, coordinate_transform,
                                                             origin_voxel_data, leaf_node_region, pose_id, true, side,
                                                             min_acceptable_z);
                }
            }
        }
    }
}

std::shared_ptr<se::Octree<SE_FIELD_TYPE>> Server::compact_merged_octree(
    const std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree)
{
    // initialize a new octree based on the merged octree
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> compact_octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
    compact_octree->init(octree->size(), octree->dim(), octree->get_origin_position());
    spdlog::debug("origin of processed octree is {}", compact_octree->get_origin_position().transpose());

    Eigen::Vector3f new_origin = compact_octree->get_origin_position();
    const float voxel_size = compact_octree->dim() / compact_octree->size();
    const float inverse_voxel_size = 1.f / voxel_size;

    const float zmin = octree_cfg_from_trackers_.begin()->second.zmin - new_origin(2);
    const float zmax = octree_cfg_from_trackers_.begin()->second.zmax - new_origin(2);

    auto valid_voxel_number_of_node = [voxel_size, inverse_voxel_size, zmin, zmax](int side, int z) {
        const float node_zmin = z * voxel_size;
        const float node_zmax = (z + side) * voxel_size;
        if (node_zmin > zmax || zmin > node_zmax) return 0;
        const float intersect_min = max(zmin, node_zmin);
        const float intersect_max = min(zmax, node_zmax);

        return side * side * int(inverse_voxel_size * (intersect_max - intersect_min));
    };

    // iterate nodes of merged octree from the root node and perform DFS traversal
    se::Node<SE_FIELD_TYPE>* n = octree->root();
    if (!n) {
        spdlog::warn("The merged octree is empty, please check code!");
        return nullptr;
    }

    std::stack<se::Node<SE_FIELD_TYPE>*> st;
    st.push(n);
    while (!st.empty()) {
        se::Node<SE_FIELD_TYPE>* node = st.top();
        st.pop();

        if (node->isLeaf()) {
            // for each voxelblock, directly insert current voxelblock to the new octree
            se::VoxelBlock<SE_FIELD_TYPE>* block = static_cast<se::VoxelBlock<SE_FIELD_TYPE>*>(node);
            const int max_blocks = se::VoxelBlock<SE_FIELD_TYPE>::sideSq * se::VoxelBlock<SE_FIELD_TYPE>::side;
            Eigen::Vector3i coords = block->coordinates();
            auto voxel_block = compact_octree->insert(coords(0), coords(1), coords(2), block->pose_id_);
            std::memcpy(voxel_block->getBlockRawPtr(), block->getBlockRawPtr(),
                        max_blocks * sizeof(*block->getBlockRawPtr()));
            continue;
        }

        // for each non-block node, insert current node to the new octree
        Eigen::Vector3i coords = se::keyops::decode(node->code_);
        auto n =
            compact_octree->insert(coords(0), coords(1), coords(2), se::keyops::level(node->code_), node->pose_id_);
        std::memcpy(n->value_, node->value_, sizeof(node->value_));

        // if the free voxel count value of current node is larger than certain threshold, i.e.,
        // certain proportion of the number of voxels that current node could cover,
        // stop doing traversal for the children of current node
        // TEST TODO determine right strategy with proper coefficient
        // std::cout << "node free cnt " << node->free_voxel_cnt_ << ", required node free cnt "
        //           << valid_voxel_number_of_node(node->side_, coords(2)) << std::endl;
        if (node->free_voxel_cnt_ > static_cast<unsigned int>(FREE_VOXEL_PROPORTION_THRE *
                                                              valid_voxel_number_of_node(node->side_, coords(2)))) {
            // std::cout << "satified!" << std::endl;
            continue;
        }

        // DFS traversal of the octree
        for (int i = 0; i < 8; ++i) {
            if (node->child(i)) st.push(node->child(i));
        }
    }

    return compact_octree;
}

std::shared_ptr<se::Octree<SE_FIELD_TYPE>> Server::merge_octree_from_trackers(
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> ref_octree,
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform, const Eigen::Matrix4d& coordinate_transform)
{
    // step1: initialize a new octree with the same size as the reference octree
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> merged_octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
    merged_octree->init(ref_octree->size(), ref_octree->dim(), ref_octree->get_origin_position());
    spdlog::debug("origin of merged octree is {}", merged_octree->get_origin_position().transpose());

    // step2: traverse reference octree and insert leaf nodes and voxelblocks into merged octree
    se::node_iterator<SE_FIELD_TYPE> it(*ref_octree);
    auto node = it.next();
    const Eigen::Vector3f origin = ref_octree->get_origin_position();
    const float voxel_size = ref_octree->dim() / ref_octree->size();

    // used for remapping mode, check whether covered area of node intersects with remapping region
    auto is_node_intersect_with_remapping_region = [&](double xmin, double xmax, double ymin, double ymax) {
        struct fast_mapping::point_2d node_region_vertexes[4] = {
            {xmin, ymin}, {xmax, ymin}, {xmax, ymax}, {xmin, ymax}};
        auto node_region = std::make_unique<fast_mapping::remapping_region>(node_region_vertexes, false);
        if (remapping_region_->intersect_with_region(*node_region)) return true;
        return false;
    };

    int intersect_node_cnt = 0, instersect_voxelblock_cnt = 0;
    for (; node != nullptr; node = it.next()) {
        if (node->isLeaf()) {  // voxelblock
            auto block = static_cast<se::VoxelBlock<SE_FIELD_TYPE>*>(node);
            const int max_blocks = se::VoxelBlock<SE_FIELD_TYPE>::sideSq * se::VoxelBlock<SE_FIELD_TYPE>::side;
            Eigen::Vector3i coords = block->coordinates();
            // for remapping mode, don't add voxelblocks that intersect with remapping region to merged octree
            if (server_mode_ == server_mode_t::Remapping) {
                Eigen::Vector3f pos_world = origin + voxel_size * coords.cast<float>();
                int side = node->side_;
                if (is_node_intersect_with_remapping_region(pos_world(0), pos_world(0) + voxel_size * float(side),
                                                            pos_world(1), pos_world(1) + voxel_size * float(side))) {
                    ++instersect_voxelblock_cnt;
                    continue;
                }
            }
            auto voxel_block = merged_octree->insert(coords(0), coords(1), coords(2), block->pose_id_);
            std::memcpy(voxel_block->getBlockRawPtr(), block->getBlockRawPtr(),
                        max_blocks * sizeof(*block->getBlockRawPtr()));
        } else {  // node
            Eigen::Vector3i coords = se::keyops::decode(node->code_);
            // for remapping mode, don't add nodes that intersect with remapping region to merged octree
            if (server_mode_ == server_mode_t::Remapping) {
                Eigen::Vector3f pos_world = origin + voxel_size * coords.cast<float>();
                int side = node->side_;
                if (is_node_intersect_with_remapping_region(pos_world(0), pos_world(0) + voxel_size * float(side),
                                                            pos_world(1), pos_world(1) + voxel_size * float(side))) {
                    ++intersect_node_cnt;
                    continue;
                }
            }
            auto n =
                merged_octree->insert(coords(0), coords(1), coords(2), se::keyops::level(node->code_), node->pose_id_);
            std::memcpy(n->value_, node->value_, sizeof(node->value_));
        }
    }
    spdlog::debug("Finished adding reference octree, intersect node cnt: {}, intersect voxelblock cnt: {}",
                 intersect_node_cnt, instersect_voxelblock_cnt);

    // store leaf nodes' region in x-y plane for reference octree
    std::vector<se::LeafNode<SE_FIELD_TYPE>> nodes;
    auto filter = [](se::Node<SE_FIELD_TYPE>::value_type data) -> bool { return data.x < 0; };
    merged_octree->get_leaf_nodes(nodes, filter);

    std::vector<std::array<int, 4>> leaf_node_region;
    for (const auto& node : nodes) {
        int side = node.side;
        if (side > MAX_NODE_SIZE) continue;  // If node side is too coarse, skip it.

        int x_min = node.coordinates(0);
        int x_max = node.coordinates(0) + side;
        int y_min = node.coordinates(1);
        int y_max = node.coordinates(1) + side;
        leaf_node_region.push_back(std::array<int, 4>{x_min, x_max, y_min, y_max});
    }

    // step3: iterate voxelblocks of octree that needs to be transformed and add to merged octree
    auto iterate_block_start = now();
    integrate_voxelblocks_to_merged_octree(octree_to_transform, merged_octree, coordinate_transform, leaf_node_region);
    auto iterate_block_end = now();
    spdlog::debug("Iterating voxelblocks of octree to be transformed and add to merged octree cost time {} ms",
                 duration_ms(iterate_block_start, iterate_block_end));

    // step4: iterate leaf nodes of octree that needs to be transformed and add to merged octree
    //        since leaf nodes already carry all the information need for octree merge,
    //        and internal nodes related to the leaf node will sequentially be created when inserting,
    //        therefore, we won't iterate all the nodes of octree, instead only iterate the leaf nodes
    auto iterate_node_start = now();
    integrate_leaf_nodes_to_merged_octree(octree_to_transform, merged_octree, coordinate_transform, leaf_node_region);
    auto iterate_node_end = now();
    spdlog::debug("Iterating nodes of octree to be transformed and add to merged octree cost time {} ms",
                 duration_ms(iterate_node_start, iterate_node_end));

    return merged_octree;

    // step5: post-processing of the newly merged octree to obtain compact tree structure
    //        by aggregating small voxelblocks into larger leaf nodes (temporarily disabled)
    //        TODO better way to compact octree is to iterate voxelblocks and find the ones with
    //        required number of voxels whose probabilities are below 0, then find their parent
    //        nodes, set corresponding child as nullptr and set value accordingly
    /*
    auto post_process_start = now();
    auto compact_octree = compact_merged_octree(merged_octree);
    auto post_process_end = now();
    spdlog::debug("Compacting merged octree by aggregating voxelblocks cost time {} ms",
                 duration_ms(post_process_start, post_process_end));

    return compact_octree;
    */
}

void Server::send_merged_octree_to_trackers()
{
    spdlog::info("send_merged_octree_to_trackers");

    auto start = now();

    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> ref_octree;
    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> octree_to_transform;
    Eigen::Matrix4d coordinate_transform;

    // for mapping mode, there would be two octrees from two trackers
    // for remapping mode, the reference octree is loaded and there will be only 1 map from octree_from_trackers_
    for (const auto& idx : octree_from_trackers_) {
        std::optional<Eigen::Matrix4d> maybe_transform = handlers_.at(idx.first).get_coordinate_transform_matrix();
        if (!maybe_transform) {
            ref_octree = idx.second;
            spdlog::info("reference octree map from client {}, origin is {}", idx.first,
                         ref_octree->get_origin_position().transpose());
        } else {
            octree_to_transform = idx.second;
            coordinate_transform = *maybe_transform;
            spdlog::info("octree map to be aligned from client {}, origin is {}, coordinate transform is \n {}",
                         idx.first, octree_to_transform->get_origin_position().transpose(), coordinate_transform);
            handlers_.at(idx.first).unset_coordinate_transform_matrix();
        }
    }

    if (server_mode_ == server_mode_t::Remapping) {
        if (!loaded_octree_) {
            spdlog::error("loaded_octree_ doesn't exist, please check code!");
            return;
        }
        ref_octree = loaded_octree_;
        spdlog::info("get reference octree map from loaded octree at remapping mode, origin is {}",
                     ref_octree->get_origin_position().transpose());
    }

    // before octree merge, check the value of coordinate transform matrix to see if it's reliable
    double z_axis_change = coordinate_transform.coeff(2, 3);
    if (z_axis_change > Z_AXIS_CHANGE_THRE) {
        spdlog::warn("The z axis change of coorindate transform is too large to perform octree merge!");
        return;
    }

    // Merge two octrees into a new global octree
    auto merge_octree_start = now();
    auto global_octree = merge_octree_from_trackers(ref_octree, octree_to_transform, coordinate_transform);
    auto merge_octree_end = now();
    spdlog::debug("Merging two octree maps cost time {} ms", duration_ms(merge_octree_start, merge_octree_end));

    univloc_msgs::Map merged_octree_msg;
    merged_octree_msg.only_add_landmarks = false;
    merged_octree_msg.is_relocalization_result = false;
    merged_octree_msg.is_request_for_server_landmarks = false;
    merged_octree_msg.loop_closure = false;
    merged_octree_msg.is_request_octree = false;
    merged_octree_msg.is_merged_octree = true;

    univloc_msgs::Octree octree_msg;
    global_octree->toROSMsg(octree_msg);

    merged_octree_msg.octree.push_back(octree_msg);

    for(const auto& idx : octree_from_trackers_) {
        auto client_id = idx.first;
        send_msg_to_client(client_id, merged_octree_msg);
        spdlog::info("send_merged_octree_to_tracker {}", client_id);
    }

    auto end = now();
    spdlog::debug("Sending the merged octree to trackers cost time {} ms ", duration_ms(start, end));

    octree_from_trackers_.clear();
}

void Server::send_nearby_landmarks_to_client(Keyframe* frame)
{
    assert(frame);
    static int run_times = 0;
    static double cost_time = 0;

    auto client_id = frame->client_id_;
    const int nearby_landmarks_num_thr = 20;
    if (handlers_.find(frame->client_id_) == handlers_.end()) {
        spdlog::error("Client ID {} not found in handlers list!", frame->client_id_);
        return;
    }
    Keyframe* current_frame = handlers_.at(frame->client_id_).get_current_keyframe();
    if (!current_frame) {
        spdlog::error("Frame with lient ID {} not found in handlers list!", frame->client_id_);
        return;
    }

    std::vector<cv::Point3f> point_3d;
    std::vector<cv::Point2f> point_2d, convex_hull;

    if (frame->get_map_id() != current_frame->get_map_id()) {
        spdlog::debug("Will skip sending nearby landmarks because client-{} has changed from map-{} to map-{}",
                      frame->client_id_, frame->get_map_id(), current_frame->get_map_id());
        return;
    }
    spdlog::debug("This frame id: {}, last frame id of relative client: {} ", frame->id_, current_frame->id_);
    {
        // TODO need to lock the map?
        //ros::Time start_time = ros::Time::now();
        auto start_time = now();
        std::vector<Mappoint*> nearby_mappoints = p_all_map_db_->get_landmarks_in_frustum(
            current_frame, point_3d, point_2d, convex_hull, near_distance_, far_distance_, back_distance_);

        if (nearby_mappoints.size() < nearby_landmarks_num_thr) {
            spdlog::debug("{} less than {} nearby landmarks, so we will not send them", nearby_mappoints.size(),
                          nearby_landmarks_num_thr);
            return;
        }
        //ros::Time end_time = ros::Time::now();
        auto end_time = now();

        run_times++;
        cost_time += duration_ms(end_time - start_time);
        spdlog::debug("get_landmarks_in_frustum costs average time: {}", cost_time / run_times);

        univloc_msgs::Map send_landmarks_msg;
        convert_mappoints_to_msg(nearby_mappoints, send_landmarks_msg);

        send_landmarks_msg.only_add_landmarks = true;
        send_landmarks_msg.is_relocalization_result = false;
        send_landmarks_msg.is_request_for_server_landmarks = false;
        send_landmarks_msg.loop_closure = false;
        send_landmarks_msg.is_request_octree = false;
        send_landmarks_msg.is_merged_octree = false;
        send_msg_to_client(client_id, send_landmarks_msg);

        spdlog::debug("Send {} nearby server landmarks to client {}", nearby_mappoints.size(), client_id);
    }
}

void Server::publish_camera_view(Keyframe *kf)
{
    if (camera_view_publisher_->get_subscription_count() == 0)
    {
        spdlog::debug("No subscribe of camera_view! ");
        return;
    }
    static const double half_width = 0.3;
    static const double half_height = 0.24;
    const double offset = -0.08;
    static const std::vector<Eigen::Vector3d> line_strip_points = {Eigen::Vector3d(0, 0, 0),
                                                                   Eigen::Vector3d(-half_width, -half_height, offset),
                                                                   Eigen::Vector3d(-half_width, half_height, offset),
                                                                   Eigen::Vector3d(half_width, half_height, offset),
                                                                   Eigen::Vector3d(half_width, -half_height, offset),
                                                                   Eigen::Vector3d(-half_width, -half_height, offset),
                                                                   Eigen::Vector3d(0, 0, 0)};

    std::vector<cv::Point3f> point_3d;
    std::vector<cv::Point2f> point_2d, convex_hull;

    std::vector<Mappoint*> nearby_mappoints = p_all_map_db_->get_landmarks_in_frustum(
        kf, point_3d, point_2d, convex_hull, near_distance_, far_distance_, back_distance_);
    assert(point_3d.size() == 8);
    assert(point_2d.size() == 8);
    ClientID client_id = kf->client_id_;
    assert(client_id_color_.find(client_id) != client_id_color_.end());

    auto current_keyframe_color = client_id_color_[client_id];
    auto visible_landmarks_color = camera_view_color_mapping_[client_id][VISIBLE_LANDMARKS_COLOR];
    auto convex_color = camera_view_color_mapping_[client_id][CONVEX_COLOR];
    auto field_of_view_color = camera_view_color_mapping_[client_id][FIELD_OF_VIEW_COLOR];
    visualization_msgs::msg::MarkerArray msg;
    visualization_msgs::msg::Marker empty_marker;
    empty_marker.header.stamp = rclcpp::Clock().now();
    std::map<std::string, visualization_msgs::msg::Marker> raycasting_markers, mappoint_markers, convex_markers_;
    visualization_msgs::msg::Marker camera_marker;
    geometry_msgs::msg::Point point;

    empty_marker.id = 0;
    empty_marker.action = 0;  // add or modify
    empty_marker.pose.orientation.w = 1.0;
    empty_marker.scale.x = 0.05;
    empty_marker.scale.y = empty_marker.scale.z = 0.0;

    std::string ns = "camera";
    camera_marker = empty_marker;
    camera_marker.type = visualization_msgs::msg::Marker::LINE_STRIP;
    camera_marker.header.frame_id = "map-" + std::to_string(kf->get_map_id());
    camera_marker.ns = ns;
    camera_marker.color = current_keyframe_color;
    camera_marker.scale.x = 0.1;
    camera_marker.scale.y = 0.1;
    camera_marker.scale.z = 0.1;

    Eigen::Affine3d Twc(kf->get_cam_pose_inv());
    for (const auto& pos_camera : line_strip_points) {
        Eigen::Vector3d pos = Twc * pos_camera;
        point.x = pos[0];
        point.y = pos[1];
        point.z = pos[2];
        camera_marker.points.push_back(point);
    }

    ns = "Raycasting";
    for (int i = 0; i < 4; i++) {
        if (!raycasting_markers.count(ns)) {
            raycasting_markers[ns] = empty_marker;
            raycasting_markers[ns].type = visualization_msgs::msg::Marker::LINE_LIST;
            raycasting_markers[ns].header.frame_id = "map-" + std::to_string(kf->get_map_id());
            raycasting_markers[ns].ns = ns;
            raycasting_markers[ns].color = field_of_view_color;
            raycasting_markers[ns].scale.x = 0.1;
            raycasting_markers[ns].scale.y = 0.1;
            raycasting_markers[ns].scale.z = 0.1;
        }
        point.x = point_3d[2 * i].x;
        point.y = point_3d[2 * i].y;
        point.z = point_3d[2 * i].z;
        raycasting_markers[ns].points.push_back(point);

        point.x = point_3d[2 * i + 1].x;
        point.y = point_3d[2 * i + 1].y;
        point.z = point_3d[2 * i + 1].z;
        raycasting_markers[ns].points.push_back(point);
    }

    for (int i = 0; i < 3; i++) {
        // geometry_msgs::Point point;
        point.x = point_3d[2 * i].x;
        point.y = point_3d[2 * i].y;
        point.z = point_3d[2 * i].z;
        raycasting_markers[ns].points.push_back(point);

        point.x = point_3d[2 * i + 2].x;
        point.y = point_3d[2 * i + 2].y;
        point.z = point_3d[2 * i + 2].z;
        raycasting_markers[ns].points.push_back(point);
    }

    point.x = point_3d[0].x;
    point.y = point_3d[0].y;
    point.z = point_3d[0].z;
    raycasting_markers[ns].points.push_back(point);

    point.x = point_3d[6].x;
    point.y = point_3d[6].y;
    point.z = point_3d[6].z;
    raycasting_markers[ns].points.push_back(point);

    for (int i = 0; i < 3; i++) {
        // geometry_msgs::Point point;
        point.x = point_3d[2 * i + 1].x;
        point.y = point_3d[2 * i + 1].y;
        point.z = point_3d[2 * i + 1].z;
        raycasting_markers[ns].points.push_back(point);

        point.x = point_3d[2 * i + 3].x;
        point.y = point_3d[2 * i + 3].y;
        point.z = point_3d[2 * i + 3].z;
        raycasting_markers[ns].points.push_back(point);
    }

    point.x = point_3d[1].x;
    point.y = point_3d[1].y;
    point.z = point_3d[1].z;
    raycasting_markers[ns].points.push_back(point);
    point.x = point_3d[7].x;
    point.y = point_3d[7].y;
    point.z = point_3d[7].z;
    raycasting_markers[ns].points.push_back(point);

    ns = "mappoint";
    double min_z = 0;
    for (auto mp : nearby_mappoints) {
        if (!mappoint_markers.count(ns)) {
            mappoint_markers[ns] = empty_marker;
            mappoint_markers[ns].type = visualization_msgs::msg::Marker::POINTS;
            mappoint_markers[ns].header.frame_id = "map-" + std::to_string(kf->get_map_id());
            mappoint_markers[ns].ns = ns;
            mappoint_markers[ns].color = visible_landmarks_color;
            mappoint_markers[ns].scale.x = 0.1;
            mappoint_markers[ns].scale.y = 0.1;
            mappoint_markers[ns].scale.z = 0.1;
        }
        // geometry_msgs::Point point;
        auto p = mp->get_pos_in_world();
        point.x = p[0];
        point.y = p[1];
        point.z = p[2];
        mappoint_markers[ns].points.push_back(point);
        if (p[2] < min_z) min_z = p[2];
    }

    ns = "convex";
    if (!convex_markers_.count(ns)) {
        convex_markers_[ns] = empty_marker;
        convex_markers_[ns].type = visualization_msgs::msg::Marker::LINE_STRIP;
        convex_markers_[ns].header.frame_id = "map-" + std::to_string(kf->get_map_id());
        convex_markers_[ns].ns = ns;
        convex_markers_[ns].color = convex_color;
        convex_markers_[ns].scale.x = 0.1;
        convex_markers_[ns].scale.y = 0.1;
        convex_markers_[ns].scale.z = 0.1;
    }

    // geometry_msgs::Point point;
    for (const auto& ch : convex_hull) {
        point.x = ch.x;
        point.y = ch.y;
        point.z = min_z;
        convex_markers_[ns].points.push_back(point);
    }
    point.x = convex_hull[0].x;
    point.y = convex_hull[0].y;
    point.z = min_z;
    convex_markers_[ns].points.push_back(point);

    for (const auto& it : raycasting_markers) {
        msg.markers.push_back(it.second);
    }

    for (const auto& it : mappoint_markers) {
        msg.markers.push_back(it.second);
    }

    for (const auto& it : convex_markers_) {
        msg.markers.push_back(it.second);
    }

    msg.markers.push_back(camera_marker);
    camera_view_publisher_->publish(msg);
    spdlog::debug("Publish camera view for client {}", kf->client_id_);
}

void Server::check_camera_fusion(Keyframe* keyframe) { camera_fusion_module_->process_new_keyframe(keyframe); }

void Server::save_client_camera(Map_Msg_ConstPtr map_camerainfo_msg)
{
    if (cam_db_->has_such_client_camera(map_camerainfo_msg->mn_client_id)) return;
    Camera_Info_Msg camerainfo_msg = map_camerainfo_msg->camera_info[0];

    std::string camera_name = camerainfo_msg.camera_typename + std::to_string(map_camerainfo_msg->mn_client_id);

    const auto camera_setup_type = static_cast<Camera::setup_type_t>(camerainfo_msg.setup_type);

    const auto camera_color_order = static_cast<Camera::color_order_t>(camerainfo_msg.color_order);

    const auto camera_model_type = static_cast<Camera::model_type_t>(camerainfo_msg.model_type);

    Camera::base* camera = nullptr;

    try {
        switch (camera_model_type) {
            case Camera::model_type_t::Perspective: {
                camera = new Camera::perspective(
                    camera_name, camera_setup_type, camera_color_order, camerainfo_msg.cols, camerainfo_msg.rows,
                    camerainfo_msg.fps, (double)camerainfo_msg.fx, (double)camerainfo_msg.fy,
                    (double)camerainfo_msg.cx, (double)camerainfo_msg.cy, (double)camerainfo_msg.k1,
                    (double)camerainfo_msg.k2, (double)camerainfo_msg.p1, (double)camerainfo_msg.p2,
                    (double)camerainfo_msg.k3, camerainfo_msg.focal_x_baseline);
                camera->show_parameters();
                cam_db_->add_client_camera(map_camerainfo_msg->mn_client_id, camera);
                break;
            }
            case Camera::model_type_t::Fisheye: {
                camera = new Camera::fisheye(
                    camera_name, camera_setup_type, camera_color_order, camerainfo_msg.cols, camerainfo_msg.rows,
                    camerainfo_msg.fps, (double)camerainfo_msg.fx, (double)camerainfo_msg.fy,
                    (double)camerainfo_msg.cx, (double)camerainfo_msg.cy, (double)camerainfo_msg.k1,
                    (double)camerainfo_msg.k2, (double)camerainfo_msg.p1, (double)camerainfo_msg.p2,
                    camerainfo_msg.focal_x_baseline);
                camera->show_parameters();
                cam_db_->add_client_camera(map_camerainfo_msg->mn_client_id, camera);
                break;
            }
            case Camera::model_type_t::Equirectangular: {
                // camera_ = new camera::equirectangular(yaml_node_);
                break;
            }
        }
    }

    catch (const std::exception& e) {
        spdlog::debug("failed in loading camera model parameters: {}", e.what());
        if (camera) {
            delete camera;
            camera = nullptr;
        }
        throw;
    }
    spdlog::debug("~~~~~~~~~~~~~~~~~Successfully save camera from client {}~~~~~~~~~~~~~~~~~ ",
                  static_cast<int>(map_camerainfo_msg->mn_client_id));
}

void Server::get_local_keyframes_and_mappoints(Keyframe* cur_keyframe, std::vector<Keyframe*>& local_keyframes,
                                               std::vector<Mappoint*>& local_mappoints)
{
    assert(cur_keyframe);
    auto map_id = cur_keyframe->get_map_id();
    auto id = cur_keyframe->id_ + 1;
    const int max_local_keyframes_size = 200, try_times = 500;

    for (int i = 0; i < try_times; i++) {
        id--;

        auto keyfrm = p_all_map_db_->get_keyframe(id);

        if (keyfrm && !keyfrm->will_be_erased() && keyfrm->get_map_id() == map_id) {  // no need to judge client id
            local_keyframes.push_back(keyfrm);
        }

        if (id == 0 || local_keyframes.size() >= max_local_keyframes_size) break;
    }

    unsigned int identifier = (unsigned int)(rclcpp::Clock().now().seconds() * 10000);
    for (auto keyframe : local_keyframes) {
        if (!keyframe) continue;

        const auto lms = keyframe->get_landmarks();
        for (auto lm : lms) {
            if (!lm || lm->will_be_erased() || lm->identifier_in_local_map_update_ == identifier) {
                continue;
            }

            lm->identifier_in_local_map_update_ = identifier;

            local_mappoints.push_back(lm);
        }
    }

    spdlog::debug("Get {} landmarks", local_mappoints.size());
}

void Server::send_updatedstate_to_client(ClientID client_id, bool is_loop_closure)
{
    std::vector<Keyframe*> local_keyfrms;
    std::vector<Mappoint*> local_mappoints;
    if (handlers_.find(client_id) == handlers_.end()) {
        spdlog::debug("No client {}, it's not normal, please debug!", client_id);
        return;
    }
    Keyframe* cur_keyframe = handlers_.at(client_id).get_current_keyframe();
    if (!cur_keyframe) {
        spdlog::debug("No cur_keyframe for client {}, it's not normal, please debug!", client_id);
        return;
    }
    cur_keyframe->graph_node_->update_connections();
    get_local_keyframes_and_mappoints(cur_keyframe, local_keyfrms, local_mappoints);
    assert(!local_mappoints.empty() || local_keyfrms.size() > 0);

    univloc_msgs::Map send_updatestate_msg;
    convert_mappoints_to_msg(local_mappoints, send_updatestate_msg);
    convert_keyframes_to_msg(local_keyfrms, send_updatestate_msg, client_id);

    univloc_msgs::KeyframeUpdate keyframe_update_msg;
    std::optional<Eigen::Matrix4d> coordinate_transform = handlers_.at(client_id).get_coordinate_transform_matrix();
    if (coordinate_transform) {
        spdlog::warn(
            "The world coordinate of the reference map to the world coordinate of the map to be aligned is \n {}",
            *coordinate_transform);
        for (int idx = 0; idx < (*coordinate_transform).rows(); ++idx)
            for (int idy = 0; idy < (*coordinate_transform).cols(); ++idy)
                keyframe_update_msg.mv_pose[idx * (*coordinate_transform).rows() + idy] =
                    (*coordinate_transform)(idx, idy);
        send_updatestate_msg.keyframe_updates.emplace_back(std::move(keyframe_update_msg));
    }

    // false means not only sending landmarks to client. Also sending covisibilities
    send_updatestate_msg.only_add_landmarks = false;
    send_updatestate_msg.is_relocalization_result = false;
    send_updatestate_msg.is_request_for_server_landmarks = false;
    send_updatestate_msg.loop_closure = is_loop_closure;
    send_updatestate_msg.is_request_octree = false;
    send_updatestate_msg.is_merged_octree = false;
    send_msg_to_client(client_id, send_updatestate_msg);
}

// Should add map ID in the parameters?
void Server::post_process_after_loop(ClientID, ClientID, MapID map1, MapID map2)
{
    //ros::Time start = ros::Time::now();
    auto start = now();
    MapID merged_map_id = std::min(map1, map2);
    bool is_loop_closure = (map1 == map2);

    for (auto& id_client : handlers_) {
        auto& client_handler = id_client.second;
        if (client_handler.get_map_id() == map1 || client_handler.get_map_id() == map2) {
            client_handler.increase_merge_times();
            client_handler.process_msg_stored_in_queue(merged_map_id);
            // If client starts a new session when optimization,  we won't send the updated message
            if (client_handler.get_map_id() == client_handler.get_mapid_before_optimization()) {
                send_updatedstate_to_client(id_client.first, is_loop_closure);
                client_handler.set_map_id(merged_map_id);
            } else
                client_handler.decrease_merge_times();
            client_handler.resume();
        }
    }

    // update map start time
    if (map1 != map2) {
        /*
            Here we will merge two maps, so we will first unset the flag of orgin keyframe for the map
            with larger ID, then erase the origin keyframe of such map from the origin keyframe unordered
            map from map database. And finally unregister such map ID.
        */
        MapID larger_map_id = std::max(map1, map2);
        MapID smaller_map_id = std::min(map1, map2);
        auto origin_keyfrm_max = p_all_map_db_->get_origin_keyframe(larger_map_id);
        p_all_map_db_->erase_origin_keyframe(larger_map_id);
        p_all_map_db_->unregister_map_id(larger_map_id);
        if (origin_keyfrm_max) {
            origin_keyfrm_max->clear_origin();
            spdlog::warn("Erase origin keyframe {} of client {} from the unregistered map {}!", origin_keyfrm_max->id_,
                         origin_keyfrm_max->client_id_, larger_map_id);
        }

        /*
            Since the origin keyframe for the unregistered map now belongs to a new map after merging,
            then set its spanning parent to the origin keyframe of the map merged to.

            TODO: There should be better solution to merge spanning trees of two maps.
        */
        auto origin_keyfrm_min = p_all_map_db_->get_origin_keyframe(smaller_map_id);
        if (origin_keyfrm_max) {
            origin_keyfrm_max->graph_node_->set_spanning_parent(origin_keyfrm_min);
            spdlog::info("Set spanning parent for keyframe {} to the origin keyframe {}!", origin_keyfrm_max->id_,
                         origin_keyfrm_max->graph_node_->get_spanning_parent()->id_);
        }
    }

    //ros::Time end = ros::Time::now();
    auto end = now();
    spdlog::info("post_process_after_loop cost time: {} ms",duration_ms(end - start));
}
Keyframe* Server::get_client_origin_keyframe(const ClientID client_id)
{
    return handlers_.at(client_id).get_current_origin_keyframe();
}

void Server::post_process_after_loop(ClientID client1, ClientID client2)
{
    //ros::Time start = ros::Time::now();
    auto start = now();
    MapID map1 = handlers_.at(client1).get_map_id(), map2 = handlers_.at(client2).get_map_id();

    for (auto& id_client : handlers_) {
        auto& client_handler = id_client.second;
        if (id_client.first == client1 || id_client.first == client2) {
            client_handler.increase_merge_times();
            client_handler.process_msg_stored_in_queue(client_handler.get_map_id());
            // If client starts a new session when optimization,  we won't send the updated message
            if (client_handler.get_map_id() == client_handler.get_mapid_before_optimization()) {
                send_updatedstate_to_client(id_client.first);
            } else
                client_handler.decrease_merge_times();
            client_handler.resume();
        }
    }

    // update map start time
    if (map1 != map2) {
        /*
            Here we will merge two maps, so we will first unset the flag of orgin keyframe for the map
            with larger ID, then erase the origin keyframe of such map from the origin keyframe unordered
            map from map database. And finally unregister such map ID.
        */
        MapID larger_map_id = std::max(map1, map2);
        MapID smaller_map_id = std::min(map1, map2);
        auto origin_keyfrm_max = p_all_map_db_->get_origin_keyframe(larger_map_id);
        p_all_map_db_->erase_origin_keyframe(larger_map_id);
        p_all_map_db_->unregister_map_id(larger_map_id);
        if (origin_keyfrm_max) {
            origin_keyfrm_max->clear_origin();
            spdlog::warn("Erase origin keyframe {} of client {} from the unregistered map {}!", origin_keyfrm_max->id_,
                         origin_keyfrm_max->client_id_, larger_map_id);
        }

        /*
            Since the origin keyframe for the unregistered map now belongs to a new map after merging,
            then set its spanning parent to the origin keyframe of the map merged to.

            TODO: There should be better solution to merge spanning trees of two maps.
        */
        auto origin_keyfrm_min = p_all_map_db_->get_origin_keyframe(smaller_map_id);
        if (origin_keyfrm_max) {
            origin_keyfrm_max->graph_node_->set_spanning_parent(origin_keyfrm_min);
            spdlog::info("Set spanning parent for keyframe {} to the origin keyframe {}!", origin_keyfrm_max->id_,
                         origin_keyfrm_max->graph_node_->get_spanning_parent()->id_);
        }
    }

    //ros::Time end = ros::Time::now();
    auto end = now();
    spdlog::info("post_process_after_loop cost time: {} ms", duration_ms(end - start));
}

void Server::pre_process_before_loop(Keyframe* current_keyframe, Keyframe* loop_keyframe)
{
    //ros::Time start_time = ros::Time::now();
    auto start_time = now();
    MapID map1 = current_keyframe->get_map_id(), map2 = loop_keyframe->get_map_id();
    for (auto& id_client : handlers_) {
        auto& client_handler = id_client.second;

        if (client_handler.get_map_id() == map1 || client_handler.get_map_id() == map2) {
            pause_process_msg(id_client.first, true);
            client_handler.record_mapid_before_optimization();
        }
    }

    //ros::Time end_time = ros::Time::now();
    auto end_time = now();
    spdlog::info("pre_process_before_loop comsumes time: {} s", duration_ms(end_time - start_time));
}

void Server::record_mapid_before_optimization(const Keyframe* kf)
{
    assert(kf);
    if (handlers_.find(kf->client_id_) == handlers_.end()) {
        spdlog::error("Handler with client ID {} not found!", kf->client_id_);
        return;
    }
    handlers_.at(kf->client_id_).record_mapid_before_optimization(kf->get_map_id());
}

void Server::record_mapid_before_optimization(const MapID map_id)
{
    for (auto& id_client : handlers_) {
        auto& client_handler = id_client.second;
        if (client_handler.get_map_id() == map_id) {
            client_handler.record_mapid_before_optimization();
        }
    }
}

void Server::set_global_optimized(bool global_optimized) { global_optimized_ = global_optimized; }

void Server::send_msg_to_client(ClientID client_id, univloc_msgs::Map& msg_to_be_sent)
{
    spdlog::debug("Start sending map message to client: {}", client_id);
    msg_to_be_sent.mn_client_id = client_id;
    msg_to_be_sent.merge_times = handlers_.at(client_id).get_merge_times();
    msg_to_be_sent.session_start_time = handlers_.at(client_id).get_current_session_start_time();

    spdlog::debug("Send {} updated keyframe message to client: {}", msg_to_be_sent.keyframes.size(), client_id);
    if (unlikely(msg_to_be_sent.landmarks.empty())) {
        if (!msg_to_be_sent.is_request_octree && !msg_to_be_sent.is_merged_octree) {
            spdlog::error("Sending a message with no landmark - should be a bug");
        }
        else if (msg_to_be_sent.is_merged_octree) {
            spdlog::debug("Send merged octree nodes {} voxel blocks {} to client {}",
                msg_to_be_sent.octree[0].nodes.size(), msg_to_be_sent.octree[0].blocks.size(), client_id);
        }
    } else {
        spdlog::debug("Send {} updated landmarks message to client: {}", msg_to_be_sent.landmarks.size(),
                      client_id);
    }

    send_message(client_id, msg_to_be_sent);
    spdlog::debug("Send map message to client {} successfully!", client_id);
}

void Server::convert_mappoints_to_msg(std::vector<Mappoint*> mappoints, univloc_msgs::Map& msg_out,
                                      bool only_send_extra)
{
    //ros::Time start = ros::Time::now();
    auto start = now();
    Mappoint* p_cur_mappoint;
    uint size = mappoints.size();
    spdlog::debug("start convert server mappoints size: {}", size);

    for (uint i = 0; i < size; i++) {
        Mappoint_Msg mappoint_msg;
        p_cur_mappoint = mappoints[i];
        if (only_send_extra) {
            if (p_cur_mappoint->get_previously_sent_flag()) {
                continue;
            } else {
                p_cur_mappoint->set_previously_sent_flag(true);
            }
        }

        ClientID mappoint_client_id = p_cur_mappoint->client_id_;
        mappoint_msg.mn_id = p_cur_mappoint->id_;
        mappoint_msg.mn_client_id = mappoint_client_id;
        Eigen::Vector3d position_in_world = p_cur_mappoint->get_pos_in_world();
        mappoint_msg.mv_position[0] = (float)position_in_world[0];
        mappoint_msg.mv_position[1] = (float)position_in_world[1];
        mappoint_msg.mv_position[2] = (float)position_in_world[2];

        mappoint_msg.mn_replace_other_id = p_cur_mappoint->replace_other_id_;
        mappoint_msg.mn_observed_in_other_keyframe_id = p_cur_mappoint->observed_in_other_keyframe_id_;
        mappoint_msg.mn_observed_in_other_keyframe_index = p_cur_mappoint->observed_in_other_keyframe_index_;
        p_cur_mappoint->replace_other_id_ = 0;
        p_cur_mappoint->observed_in_other_keyframe_id_ = 0;

        // If the last landmark observation is far behind current frame, it means this landmark is not observerd by
        // current frame, so we need to send its descriptor Has problem , we need to find out those landmarks which may
        // not in the client local map, if sent not correctly, it may cause a mistake, so we send this msg anyway if
        // (p_cur_mappoint->get_identifier_last_observation_id() != cur_frame_id) {
        cv::Mat descriptor = p_cur_mappoint->get_descriptor();
        const size_t descriptors_cols = descriptor.cols;
        mappoint_msg.mv_descriptors.resize(1);

        if (descriptors_cols != mappoint_msg.mv_descriptors[0].m_descriptor.size()) {
            spdlog::warn("descriptor of landmark {} has wrong size {}", p_cur_mappoint->id_, descriptors_cols);
            continue;
        }
        memcpy(mappoint_msg.mv_descriptors[0].m_descriptor.data(), descriptor.ptr(0), descriptors_cols);
        mappoint_msg.mf_max_distance = p_cur_mappoint->get_max_valid_distance();
        mappoint_msg.mf_min_distance = p_cur_mappoint->get_min_valid_distance();
        Eigen::Vector3d mean_norm = p_cur_mappoint->get_obs_mean_normal();
        mappoint_msg.mv_normal_vector.resize(3);
        mappoint_msg.mv_normal_vector[0] = mean_norm[0];
        mappoint_msg.mv_normal_vector[1] = mean_norm[1];
        mappoint_msg.mv_normal_vector[2] = mean_norm[2];
        //}
        msg_out.landmarks.emplace_back(std::move(mappoint_msg));
    }
    //ros::Time finish = ros::Time::now();
    auto finish = now();
    spdlog::debug("convert {} mappoints to msg consumes: {} ms.", msg_out.landmarks.size(),
                  duration_ms(finish - start));
}

void Server::convert_keyframes_to_msg(std::vector<Keyframe*> keyframes, univloc_msgs::Map& msg_out,
                                      ClientID client_id)
{
    //ros::Time start = ros::Time::now();
    auto start = now();
    Keyframe_Msg keyframe_msg;
    Keyframe* cur_keyframe;
    uint size = keyframes.size();
    spdlog::debug("start convert keyframes size {}", size);
    for (uint i = 0; i < size; i++) {
        cur_keyframe = keyframes[i];
        const ClientID keyframe_client_id = cur_keyframe->client_id_;
        keyframe_msg.mn_id = static_cast<KeyframeID>(cur_keyframe->id_);
        if (p_all_map_db_->is_keyframe_loaded(cur_keyframe)) {
            spdlog::debug("keyframe {} is loaded from previous map, won't convert to msg!", cur_keyframe->id_);
            continue;
        }
        if (client_id != keyframe_client_id) {
            spdlog::debug("keyframe {} belongs to client {}, not {}, won't convert to msg!", cur_keyframe->id_,
                          keyframe_client_id, client_id);
            continue;
        }
        keyframe_msg.mn_client_id = static_cast<ClientID>(keyframe_client_id);
        {
            Eigen::Matrix4d pose = cur_keyframe->get_cam_pose();
            int mk = 0;
            for (int mi = 0; mi < 4; ++mi)
                for (int mj = 0; mj < 4; ++mj) keyframe_msg.mv_pose[mk++] = pose(mi, mj);
        }
        keyframe_msg.md_timestamp = cur_keyframe->timestamp_;
        keyframe_msg.mn_localize_map_id = cur_keyframe->get_map_id();
        msg_out.keyframes.emplace_back(std::move(keyframe_msg));
    }
    //ros::Time finish = ros::Time::now();
    auto finish = now();
    spdlog::debug("Converting {} keyframes to msg consumes {} s", msg_out.keyframes.size(),
                  duration_ms(finish - start));
    spdlog::debug("convert keyframes finished");
}

void Server::pause_process_msg(ClientID client_id, bool wait_until_paused)
{
    spdlog::info("!~~~~~~~~~~~~~~~Start pausing msg processing~~~~~~~~~~~~~~~!");
    handlers_.at(client_id).pause();
    if (!wait_until_paused) return;
    while (!handlers_.at(client_id).is_paused()) std::this_thread::sleep_for(std::chrono::milliseconds(1));
}

void Server::resume_process_msg()
{
    spdlog::info("!~~~~~~~~~~~~~~~Resuming msg processing~~~~~~~~~~~~~~~!");
    for (auto& it : handlers_) it.second.resume();
}

bool Server::is_paused()
{
    bool paused = true;
    for (auto& it : handlers_)
        paused = paused && it.second.is_paused();
    return paused;
}

void Server::set_global_optimization_module(openvslam::univloc_global_optimization_module* global_optimizer)
{
    global_optimizer_ = global_optimizer;
}

void Server::ros_publisher()
{
    publish_keypoints();
    publish_keyframes();
    if (pub_octree_map_ && pub_occupancy_map_) {
        publish_octree_map();
        publish_occupancy_map();
    }

    /*
        Here we publish the pose of origin keyframe for loaded maps as the
        transform from map-{ID} to server frame to indicate the fixed frames.

        Without the below code block, the Rviz window can't find the fixed frame
        for the loaded keyframe/landmark map. So we need to publish a transform
        for the loaded map to TF tree.
    */
    if (!cfg_->load_map_path_.empty()) {
        auto all_origin_keyfrms = p_all_map_db_->get_all_origin_keyframes();
        for (const auto& id_keyfrm : all_origin_keyfrms) {
            if (p_all_map_db_->is_keyframe_loaded(id_keyfrm.second))
                publish_tf(id_keyfrm.second, id_keyfrm.second->client_id_);
        }
    }
}

void Server::publish_keypoints()
{
    visualization_msgs::msg::MarkerArray msg;
    geometry_msgs::msg::Point point;
    rclcpp::Time stamp = rclcpp::Clock().now();
    if (keypoints_publisher_->get_subscription_count() == 0)
    {
        return;
    }
    static int last_max_map_id = 0;
    msg.markers.resize(last_max_map_id + 1);
    auto landmarks = p_all_map_db_->get_all_landmarks();
    for (const auto& lm : landmarks) {
        auto client_id = lm->client_id_;
        int map_id = static_cast<int>(lm->get_map_id());
        if (map_id > last_max_map_id) {
            last_max_map_id = map_id;
            msg.markers.resize(last_max_map_id + 1);
        }
        auto pos = lm->get_pos_in_world();
        point.x = pos[0];
        point.y = pos[1];
        point.z = pos[2];
        msg.markers[map_id].points.push_back(point);
        msg.markers[map_id].colors.push_back(client_id_color_[client_id]);
        // msg.markers[map_id].ns = "client-" + std::to_string(client_id);
    }
    static std::string last_stats;
    std::stringstream ss;
    ss << "Keypoint stats: (" << landmarks.size() << " in database)\n";
    for (size_t map_id = 0; map_id < msg.markers.size(); ++map_id) {
        auto& marker = msg.markers[map_id];
        marker.header.stamp = stamp;
        marker.header.frame_id = "map-" + std::to_string(map_id);
        marker.ns = marker.header.frame_id;
        marker.id = 0;
        marker.type = visualization_msgs::msg::Marker::POINTS;
        if (marker.points.empty())
            marker.action = 2;  // delete
        else
            marker.action = 0;  // add or modify
        marker.pose.orientation.w = 1.0;
        marker.scale.x = marker.scale.y = 0.03;
        // marker.color = client_id_to_color(static_cast<ClientID>(map_id));
        ss << "  " << marker.header.frame_id << ": " << marker.points.size() << " keypoints\n";
    }
    if (msg.markers.size() > 0)
        keypoints_publisher_->publish(msg);
    std::string stats = ss.str();
    if (stats != last_stats) {
        spdlog::debug(stats);
        last_stats = stats;
    }
}

void Server::publish_keyframes()
{
    if (keyframes_publisher_->get_subscription_count() == 0) return;
    visualization_msgs::msg::MarkerArray msg;
    rclcpp::Time stamp = rclcpp::Clock().now();
    visualization_msgs::msg::Marker empty_marker;
    std::map<std::string, visualization_msgs::msg::Marker> loop_markers, multi_camera_markers;

    static const double half_width = 0.24;
    static const double half_height = 0.18;
    // Set the value of visualization_size to 0.05m to make the lines which depict the keyframes
    // thinner so that we can see the trajectory of the keyframe clearly.
    const double offset = 0.03, visualization_size = 0.05;
    // std::lock_guard<std::mutex> lock(openvslam::data::map_database::mtx_database_);
    // Previously, we use line strip points (p1-p2-p3-p4-p5-p6-p7...pN) to draw each keyframe and to connect to the
    // next. This will cause the simliar issue like https://github.com/ros-visualization/rviz/issues/1107. So we decide
    // to use line list point (p1-p2,p2-p3,p3-p4,p4-p5...pN) to do the same thing.
    static const std::vector<Eigen::Vector3d> line_list_points = {Eigen::Vector3d(0, 0, 0),
                                                                  Eigen::Vector3d(-half_width, -half_height, offset),
                                                                  Eigen::Vector3d(-half_width, half_height, offset),
                                                                  Eigen::Vector3d(-half_width, half_height, offset),
                                                                  Eigen::Vector3d(half_width, half_height, offset),
                                                                  Eigen::Vector3d(half_width, half_height, offset),
                                                                  Eigen::Vector3d(half_width, -half_height, offset),
                                                                  Eigen::Vector3d(half_width, -half_height, offset),
                                                                  Eigen::Vector3d(-half_width, -half_height, offset),
                                                                  Eigen::Vector3d(0, 0, 0)};
    //visualization_msgs::MarkerArray msg;
    //ros::Time stamp = ros::Time::now();

    //visualization_msgs::Marker empty_marker;
    empty_marker.header.stamp = stamp;
    empty_marker.id = 0;
    empty_marker.action = 0;  // add or modify
    empty_marker.pose.orientation.w = 1.0;
    empty_marker.scale.x = visualization_size;
    empty_marker.scale.y = empty_marker.scale.z = 0.0;  // scale.y/z will be ignored
    //std::map<std::string, visualization_msgs::Marker> loop_markers, multi_camera_markers;

    static std::string last_stats;
    std::stringstream ss;
    ss << "Keyframe stats: (" << p_all_map_db_->get_num_keyframes() << " in database)\n";
    /*
        Previous implementation of recursive keyframe loop
        was not displaying entire trajectory in case a keyframe
        does not have a spanning parent.
        Current approach is more robust, but entire trajectory
        will be shown.

        NOTE: map_database offers the call get_all_keyframes_map(MapID map_id)
        but we are not using it since it contains the lock while it loops through
        entire keyframes and blocks other threads (that are doing actual computing).
        This thread is only for publishing keyframes so we can afford additional loop.
    */
    std::unordered_map<KeyframeID, Keyframe*> all_keyframes = p_all_map_db_->get_all_keyframes_map();
    for (auto& it : handlers_) {  // for each client
        auto client_id = it.first;
        const std::vector<Keyframe*> session_end_keyframes = it.second.get_latest_keyframe_of_all_sessions();
        uint32_t session_size = session_end_keyframes.size();
        bool camera_view_shown = false;
        for (size_t session_id = 0; session_id < session_size; ++session_id) {  // for each session
            if (!camera_view_shown) {
                publish_camera_view(session_end_keyframes[session_size - 1]);
                camera_view_shown = true;
            }
            Keyframe* end_frame = session_end_keyframes[session_id];
            visualization_msgs::msg::Marker session_marker = empty_marker;
            session_marker.type = visualization_msgs::msg::Marker::LINE_LIST;
            session_marker.header.frame_id = "map-" + std::to_string(end_frame->get_map_id());
            session_marker.ns = "client-" + std::to_string(client_id) + '-' + std::to_string(session_id);
            session_marker.color = client_id_color_[client_id];

            std::map<KeyframeID, Keyframe*> keyframes_map;
            for (const auto& id_keyframe : all_keyframes) {
                if (id_keyframe.second->get_map_id() == end_frame->get_map_id() && id_keyframe.second->client_id_ == client_id)
                    keyframes_map.insert(std::pair<KeyframeID, Keyframe*>(id_keyframe.first, id_keyframe.second));
            }

            std::map<KeyframeID, Keyframe*>::reverse_iterator it = keyframes_map.rbegin();
            // The number of line list points must be even, so we need to insert a point at the beginning and end of it
            // to connect the centers of adjacent keyframes.
            geometry_msgs::msg::Point first_point;
            Eigen::Affine3d first_Twc(it->second->get_cam_pose_inv());
            Eigen::Vector3d first_pos = first_Twc * Eigen::Vector3d(0, 0, 0);
            first_point.x = first_pos[0];
            first_point.y = first_pos[1];
            first_point.z = first_pos[2];
            session_marker.points.push_back(first_point);

            while (it != keyframes_map.rend()) {
                Keyframe* frame = it->second;

                Eigen::Affine3d Twc(frame->get_cam_pose_inv());
                for (const auto& pos_camera : line_list_points) {
                    Eigen::Vector3d pos = Twc * pos_camera;
                    geometry_msgs::msg::Point point;
                    point.x = pos[0];
                    point.y = pos[1];
                    point.z = pos[2];
                    session_marker.points.push_back(point);
                }

                auto loop_keyframes = frame->graph_node_->get_loop_edges();
                for (const auto& loop_keyframe : loop_keyframes) {
                    std::string ns = "loop-" + std::to_string(std::min(client_id, loop_keyframe->client_id_)) + "-" +
                                     std::to_string(std::max(client_id, loop_keyframe->client_id_)) +
                                     "  MapID: " + std::to_string(frame->get_map_id());
                    if (loop_markers.find(ns) == loop_markers.end()) {
                        loop_markers[ns] = empty_marker;
                        loop_markers[ns].type = visualization_msgs::msg::Marker::LINE_LIST;
                        loop_markers[ns].header.frame_id = "map-" + std::to_string(loop_keyframe->get_map_id());
                        loop_markers[ns].ns = ns;
                        loop_markers[ns].color = client_id_color_[client_id];
                        loop_markers[ns].scale.x = visualization_size;
                    }
                    Eigen::Vector3d loop_keyframe_position = loop_keyframe->get_cam_pose_inv().block(0, 3, 3, 1);
                    geometry_msgs::msg::Point point;
                    point.x = Twc.translation()[0];
                    point.y = Twc.translation()[1];
                    point.z = Twc.translation()[2];
                    loop_markers[ns].points.push_back(point);

                    point.x = loop_keyframe_position[0];
                    point.y = loop_keyframe_position[1];
                    point.z = loop_keyframe_position[2];
                    loop_markers[ns].points.push_back(point);
                }

                if (frame->graph_node_->has_front_rear_camera_constraint()) {
                    auto multi_camera_id_keyframe = frame->graph_node_->get_front_rear_camera_constraint();
                    auto kf = multi_camera_id_keyframe.second;
                    if (kf->get_map_id() == frame->get_map_id() && kf->client_id_ < frame->client_id_) {
                        std::string ns = "MultiCamera-" + std::to_string(kf->client_id_) + "-" +
                                         std::to_string(frame->client_id_) +
                                         "  MapID: " + std::to_string(frame->get_map_id());
                        if (multi_camera_markers.find(ns) == multi_camera_markers.end()) {
                            multi_camera_markers[ns] = empty_marker;
                            multi_camera_markers[ns].type = visualization_msgs::msg::Marker::LINE_LIST;
                            multi_camera_markers[ns].header.frame_id = "map-" + std::to_string(kf->get_map_id());
                            multi_camera_markers[ns].ns = ns;
                            multi_camera_markers[ns].color = client_id_color_[frame->client_id_];
                            multi_camera_markers[ns].scale.x = visualization_size;
                        }
                        Eigen::Vector3d multi_camera_keyframe_position = kf->get_cam_pose_inv().block(0, 3, 3, 1);
                        geometry_msgs::msg::Point point;
                        point.x = Twc.translation()[0];
                        point.y = Twc.translation()[1];
                        point.z = Twc.translation()[2];
                        multi_camera_markers[ns].points.push_back(point);

                        point.x = multi_camera_keyframe_position[0];
                        point.y = multi_camera_keyframe_position[1];
                        point.z = multi_camera_keyframe_position[2];
                        multi_camera_markers[ns].points.push_back(point);
                    }
                }

                it++;
            }

            if (session_marker.points.size() == 0) continue;

            auto point_size = session_marker.points.size();
            geometry_msgs::msg::Point last_point;
            last_point.x = session_marker.points[point_size - 1].x;
            last_point.y = session_marker.points[point_size - 1].y;
            last_point.z = session_marker.points[point_size - 1].z;
            session_marker.points.push_back(last_point);

            msg.markers.push_back(session_marker);
            ss << "  client-" << static_cast<int>(client_id) << " session-" << session_id << ": "
               << (session_marker.points.size() - 2) / line_list_points.size() << " keyframes"
               << " in " << session_marker.header.frame_id << "\n";
        }
    }

    auto loaded_keyframes_pos_inv = p_all_map_db_->get_loaded_keyframes_pos_inv();
    for (const auto& item : loaded_keyframes_pos_inv) {
        ClientID client_id = item.first;
        visualization_msgs::msg::Marker loaded_marker = empty_marker;
        loaded_marker.type = visualization_msgs::msg::Marker::LINE_LIST;
        loaded_marker.header.frame_id = "map-0";  // TODO: chenge map id
        loaded_marker.ns = "client-" + std::to_string(client_id);
        loaded_marker.color = client_id_color_[client_id];
        loaded_marker.scale.x = visualization_size;

        // The number of line list points must be even, so we need to insert a point at the beginning and end of it
        // to connect the centers of adjacent keyframes.
        geometry_msgs::msg::Point first_point;
        Eigen::Affine3d first_Twc(item.second[0]);
        Eigen::Vector3d first_pos = first_Twc * Eigen::Vector3d(0, 0, 0);
        first_point.x = first_pos[0];
        first_point.y = first_pos[1];
        first_point.z = first_pos[2];
        loaded_marker.points.push_back(first_point);

        for (auto& pose : item.second) {
            Eigen::Affine3d Twc(pose);
            for (const auto& pos_camera : line_list_points) {
                Eigen::Vector3d pos = Twc * pos_camera;
                geometry_msgs::msg::Point point;
                point.x = pos[0];
                point.y = pos[1];
                point.z = pos[2];
                loaded_marker.points.push_back(point);
            }
        }

        if (loaded_marker.points.size() == 0) continue;

        auto point_size = loaded_marker.points.size();
        geometry_msgs::msg::Point last_point;
        last_point.x = loaded_marker.points[point_size - 1].x;
        last_point.y = loaded_marker.points[point_size - 1].y;
        last_point.z = loaded_marker.points[point_size - 1].z;
        loaded_marker.points.push_back(last_point);

        msg.markers.push_back(loaded_marker);
        ss << "Loaded client-" << static_cast<int>(client_id) << "  " << item.second.size() << " keyframes /n";
    }

    for (const auto& it : loop_markers) {
        msg.markers.push_back(it.second);
        ss << "  Loop edges between " << it.first << ": " << it.second.points.size() / 2 << "\n";
    }

    for (const auto& it : multi_camera_markers) {
        msg.markers.push_back(it.second);
        ss << "  Multi-camera edges between " << it.first << ": " << it.second.points.size() / 2 << "\n";
    }

    keyframes_publisher_->publish(msg);
    std::string stats = ss.str();
    if (stats != last_stats) {
        spdlog::debug(stats);
        last_stats = stats;
    }
}

void Server::publish_octree_map()
{
    if (pub_octree_map_->get_subscription_count() == 0) return;

    const int block_side = loaded_octree_->blockSide;
    const unsigned int octree_size = loaded_octree_->size();
    const float octree_dim = loaded_octree_->dim();
    const double voxel_dim = octree_dim / octree_size;

    auto set_marker_scale = [](visualization_msgs::msg::Marker &marker, double scale)
    {
        marker.scale.x = marker.scale.y = marker.scale.z = scale;
    };
    auto set_marker_color = [](visualization_msgs::msg::Marker &marker, float r, float g, float b, float a = 1.0)
    {
        marker.color.r = r; marker.color.g = g; marker.color.b = b; marker.color.a = a;
    };

    visualization_msgs::msg::Marker empty_marker;
    empty_marker.header.frame_id = "map-0";
    empty_marker.header.stamp = rclcpp::Clock().now();
    empty_marker.id = 0;
    empty_marker.type = visualization_msgs::msg::Marker::CUBE_LIST;
    empty_marker.action = visualization_msgs::msg::Marker::ADD;
    empty_marker.pose.orientation.w = 1.0;
    set_marker_scale(empty_marker, voxel_dim);
    set_marker_color(empty_marker, 1.0, 1.0, 1.0, 1.0); // white

    // Fused Markers
    visualization_msgs::msg::MarkerArray msg_fused;
    msg_fused.markers.resize(1, empty_marker);
    auto fused_marker = msg_fused.markers.begin();
    fused_marker->ns = "octree_map_loaded";

    // Iterate through the list of blocks
    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    loaded_octree_->getBlockList(blocks, false);

    const Eigen::Vector3f origin_position = loaded_octree_->get_origin_position();
    geometry_msgs::msg::Point origin;
    origin.x = origin_position(0);
    origin.y = origin_position(1);
    origin.z = origin_position(2);

    geometry_msgs::msg::Point center;
    for (const auto& block : blocks) {
        Eigen::Vector3i coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;

                center.x = origin.x + (vx + 0.5) * voxel_dim;
                center.y = origin.y + (vy + 0.5) * voxel_dim;
                center.z = origin.z + (coords.z() + 0.5) * voxel_dim;
                int dataid = i + j * block->side;
                if (dataid >= static_cast<int>(block->side * block->sideSq)) break;

                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    se::Node<SE_FIELD_TYPE>::value_type data = block->data(dataid);
                    const float prob = data.x;
                    if (prob > fast_mapping::unknown_upper)
                    {
                        fused_marker->points.push_back(center);
                    }
                }
            }
        }
    }

    fast_mapping::add_color_to_marker_points(*fused_marker, "z", -1., 4.);
    /*
        Color the voxel blocks within the remapping region brown. Currently
        we don't check if the voxel block is whithin the range on Z axis
        since the octree map loaded from the tracker side is naturally
        generated within such range on Z axis.
    */
    if (server_mode_ == server_mode_t::Remapping) {
        std_msgs::msg::ColorRGBA remapping_region_color;
        remapping_region_color.a = 0.5;
        remapping_region_color.r = 165 / 255.;
        remapping_region_color.g = 42 / 255.;
        remapping_region_color.b = 42 / 255.;
        size_t size = fused_marker->points.size();
        for (unsigned int i = 0; i < size; i++) {
            struct fast_mapping::point_2d voxel_2d_point = {fused_marker->points[i].x, fused_marker->points[i].y};
            if (remapping_region_->within_remapping_region(voxel_2d_point)) {
                fused_marker->colors[i] = remapping_region_color;
            }
        }
    }
    pub_octree_map_->publish(msg_fused);
}

void Server::publish_occupancy_map()
{
    if (pub_occupancy_map_->get_subscription_count() == 0) return;

    const int block_side = loaded_octree_->blockSide;
    const unsigned int octree_size = loaded_octree_->size();
    const float octree_dim = loaded_octree_->dim();
    const double voxel_dim = octree_dim / octree_size;

    const Eigen::Vector3f origin_position = loaded_octree_->get_origin_position();
    geometry_msgs::msg::Point origin;
    origin.x = origin_position(0);
    origin.y = origin_position(1);
    origin.z = origin_position(2);

    // Allocate or expand the occupancy grid
    if (!grid_template_->data.size()) {

        nav_msgs::msg::OccupancyGrid &og = *grid_template_;
        og.info.resolution =  voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        uint64_t data_size = (uint64_t) og.info.width * (uint64_t) og.info.height;
        og.data.resize(data_size, fast_mapping::unknown_prob);
    }

    if (octree_size != grid_template_->info.width) {

        auto grid_template_new = std::make_shared<nav_msgs::msg::OccupancyGrid>();
        nav_msgs::msg::OccupancyGrid &og = *grid_template_new;
        og.info.resolution = voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        uint64_t data_size = (uint64_t) og.info.width * (uint64_t) og.info.height;
        og.data.resize(data_size, fast_mapping::unknown_prob);
        int dx = std::nearbyint((grid_template_->info.origin.position.x - og.info.origin.position.x) /
                                og.info.resolution);
        int dy = std::nearbyint((grid_template_->info.origin.position.y - og.info.origin.position.y) /
                                og.info.resolution);
        if (dx < 0 && dy < 0) {
            spdlog::warn("Error: enlarged octree does not cover the old one");
            return;
        }
        for (unsigned int y = 0; y < grid_template_->info.height; ++y) {
            std::memcpy(&og.data[(y + dy) * og.info.width + dx],
                &grid_template_->data[y * grid_template_->info.width],
                grid_template_->info.width * sizeof(og.data[0]));
        }
        grid_template_ = grid_template_new;
    }

    nav_msgs::msg::OccupancyGrid og = *grid_template_;
    og.header.frame_id = "map-0";
    og.header.stamp = rclcpp::Clock().now();

    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    loaded_octree_->getBlockList(blocks, false);

    // Iterate through the list of blocks and update occupied space.
    geometry_msgs::msg::Point center;
    for (const auto &block : blocks) {
        auto coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;
                if (vx < 0 || vy < 0) break;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;

                center.x = origin.x + (vx + 0.5) * voxel_dim;
                center.y = origin.y + (vy + 0.5) * voxel_dim;
                center.z = origin.z + (coords.z() + 0.5) * voxel_dim;

                int dataid = i + j * block->side;
                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    /*
                        temporarily extend the range for height check because during octree merge,
                        we use a larger range of (zmin, zmax) to accept input voxel, therefore,
                        here we need to align with the setting and manually extend the range
                    */
                    if (center.z >= (cfg_->server_zmax_ + 1.5 * block_side * voxel_dim) ||
                        center.z <= (cfg_->server_zmin_ - 1.5 * block_side * voxel_dim))
                        continue;

                    const size_t index = vy * og.info.width + vx;
                    if (index >= og.data.size()) break;

                    auto &ogdata = og.data[index];

                    const float prob = block->data(dataid).x;
                    if (prob > fast_mapping::unknown_upper) ogdata = fast_mapping::occupied_prob; // Occupied
                    /*
                        temporarily change the value of fast_mapping::unknown_lower to 0.0,
                        because after octree merge, we need to use newly created voxelblocks to indicate the
                        free space area, so we use the same threshold as the following LeafNode filter
                    */
                    else if (prob < fast_mapping::unknown_lower) {
                        // If unknown, mark as free space
                        if (ogdata == fast_mapping::unknown_prob) ogdata = fast_mapping::free_prob;
                    }
                }
            }
        }
    }

    // Iterate through the list of non-block leaf nodes that meet the data filter requirement
    // and update the free space of the occupancy map
    std::vector<se::LeafNode<SE_FIELD_TYPE>> nodes;
    auto filter = [](se::Node<SE_FIELD_TYPE>::value_type data)->bool { return data.x < 0; };
    loaded_octree_->get_leaf_nodes(nodes, filter);

    for (const auto& node : nodes) {
        int side = node.side;
        if (side > MAX_NODE_SIZE) continue; // If node side is too coarse, skip it.

        for (int i = 0; i < side; i++) {
            for (int j = 0; j < side; j++) {
                int vx = node.coordinates(0) + i;
                int vy = node.coordinates(1) + j;
                if (vx < 0 || vy < 0) continue;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;
                const size_t index = vy * og.info.width + vx;
                if(index >= og.data.size()) break;
                auto &ogdata = og.data[index];
                // If unknow, mark as free space
                if (ogdata == fast_mapping::unknown_prob) ogdata = fast_mapping::free_prob;
            }
        }
    }
    pub_occupancy_map_->publish(og);
}

void Server::publish_tf(Keyframe* frame, ClientID client_id)
{
    std::string parent_frame = "map-" + std::to_string(frame->get_map_id());
    std::string child_frame = "tracker-" + std::to_string(client_id);

    geometry_msgs::msg::TransformStamped send_transform_msg;
    Eigen::Affine3d pose(frame->get_cam_pose_inv());
    send_transform_msg = tf2::eigenToTransform(pose);
    rclcpp::Time stamp(frame->timestamp_);
    send_transform_msg.header.frame_id = parent_frame;
    if (p_all_map_db_->is_keyframe_loaded(frame)) {
        send_transform_msg.child_frame_id = "server";
        send_transform_msg.header.stamp = rclcpp::Clock().now();
    } else {
        send_transform_msg.child_frame_id = child_frame;
        send_transform_msg.header.stamp = stamp;
    }
    tf_broadcaster_->sendTransform(send_transform_msg);
}

void Server::octree_sync_callback(const std_msgs::msg::String::SharedPtr msg)
{
    if (msg->data == "octree_sync") {
        std::vector<ClientID> ids;
        bool map_merge_happen = false;
        // If map merge occured, then two clients will have the same map ID
        for (auto& id_client : handlers_)
            ids.push_back(id_client.first);
        for (uint32_t i = 0; (ids.size() > 1 && i < (ids.size() - 1)); i++) {
            unsigned int map_id = get_running_client_map_id(ids[i]);
            for (uint32_t j = i + 1; j < ids.size(); j++) {
                if (map_id == get_running_client_map_id(ids[j])) {
                    request_octree_from_clients({ids[i], ids[j]});
                    map_merge_happen = true;
                }
            }
        }
        if (!map_merge_happen)
            spdlog::warn("Got request for octree sync, but map merge did not occur. Ignoring request!");
    } else {
        spdlog::warn("Got {} message over ROS octree sync topic, but did not match required string!", msg->data);
    }
}

bool Server::is_running_optimization() { return global_optimizer_->is_running_optimization(); }

std_msgs::msg::ColorRGBA Server::client_id_to_color(ClientID id)
{
    Color color = all_colors[(id) % all_colors.size()];
    std_msgs::msg::ColorRGBA rgba;
    rgba.r = color.r / 255.;
    rgba.g = color.g / 255.;
    rgba.b = color.b / 255.;
    rgba.a = 1.0;
    return rgba;
}

std::unordered_map<ClientID, std::shared_ptr<se::Octree<SE_FIELD_TYPE>>>& Server::get_octree_from_trackers()
{
    return octree_from_trackers_;
}

std::unordered_map<ClientID, struct fast_mapping::se_cfg>& Server::get_octree_cfg_from_trackers()
{
    return octree_cfg_from_trackers_;
}

std::unordered_map<ClientID, struct fast_mapping::camera_intrinsics>& Server::get_octree_intrinsic_from_trackers()
{
    return octree_intrinsic_from_trackers_;
}

void Server::create_octree_related_publishers()
{
    auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
    pub_octree_map_ = pnh_->create_publisher<visualization_msgs::msg::MarkerArray>("~/fused_map",
                                                                                   map_qos);
    pub_occupancy_map_ = pnh_->create_publisher<nav_msgs::msg::OccupancyGrid>("~/map", map_qos);
    grid_template_ = std::make_shared<nav_msgs::msg::OccupancyGrid>();
}

bool Server::remove_pointcloud_within_remapping_region()
{
    if (!p_all_map_db_ || !remapping_region_) {
        spdlog::error("Map database or remapping region hasn't been constructed before removing pintcloud!");
        return false;
    }

    // First to remove landmarks within remapping region
    std::vector<LandmarkID> removed_landmarks;
    auto all_landmarks = p_all_map_db_->get_all_landmarks();
    for (auto& landmark : all_landmarks) {
        Eigen::Vector3d lm_pose = landmark->get_pos_in_world();
        if (remapping_region_->within_remapping_region({lm_pose[0], lm_pose[1]})) {
            removed_landmarks.emplace_back(landmark->id_);
            landmark->prepare_for_erasing();
        }
    }

    // Second to remove keyframes within remapping region
    std::vector<KeyframeID> removed_keyframes;
    auto all_keyframes = p_all_map_db_->get_all_keyframes();

    for (auto& keyframe : all_keyframes) {
        Eigen::Matrix4d keyfrm_Twc = keyframe->get_cam_pose_inv();
        Eigen::Vector3d keyfrm_pose = keyfrm_Twc.block<3, 1>(0, 3);
        if (remapping_region_->within_remapping_region({keyfrm_pose[0], keyfrm_pose[1]})) {
            removed_keyframes.emplace_back(keyframe->id_);
            keyframe->prepare_for_erasing_remapping();
        }
    }

    // Third to manage the corner case if all the landmarks and keyframes are removed for a specific map
    std::set<MapID> all_map_ids = p_all_map_db_->get_all_registered_map_ids();
    for (auto& map_id : all_map_ids) {
        std::map<LandmarkID, openvslam::data::landmark*> landmarks_for_map;
        p_all_map_db_->get_all_landmarks_map(landmarks_for_map, map_id);
        if (!landmarks_for_map.empty()) continue;

        std::map<KeyframeID, openvslam::data::keyframe*> keyframes_for_map;
        p_all_map_db_->get_all_keyframes_map(keyframes_for_map, map_id);
        if (!keyframes_for_map.empty()) continue;

        p_all_map_db_->unregister_map_id(map_id);
    }

    // Print log info fot the debugging
    spdlog::info("Totally removed {} landmarks and {} keyframes within the remapping region!",
                  removed_landmarks.size(), removed_keyframes.size());

    return true;
}

void Server::remove_clients_pointcloud_outside_remapping_region()
{
    if (!p_all_map_db_ || !remapping_region_) {
        spdlog::error("Map database or remapping region has been destructed before removing pintcloud!");
        return;
    }

    // First to remove landmarks outside of the remapping region
    std::vector<LandmarkID> removed_landmarks;
    auto all_landmarks = p_all_map_db_->get_all_landmarks();
    for (auto& landmark : all_landmarks) {
        Eigen::Vector3d lm_pose = landmark->get_pos_in_world();
        if (!p_all_map_db_->is_landmark_loaded(landmark) &&
            !remapping_region_->within_remapping_region({lm_pose[0], lm_pose[1]})) {
            removed_landmarks.emplace_back(landmark->id_);
            landmark->prepare_for_erasing();
        }
    }

    // Second to remove keyframes outside of the remapping region
    std::vector<KeyframeID> removed_keyframes;
    auto all_keyframes = p_all_map_db_->get_all_keyframes();

    for (auto& keyframe : all_keyframes) {
        Eigen::Matrix4d keyfrm_Twc = keyframe->get_cam_pose_inv();
        Eigen::Vector3d keyfrm_pose = keyfrm_Twc.block<3, 1>(0, 3);
        if (!p_all_map_db_->is_keyframe_loaded(keyframe) &&
            !remapping_region_->within_remapping_region({keyfrm_pose[0], keyfrm_pose[1]})) {
            removed_keyframes.emplace_back(keyframe->id_);
            keyframe->prepare_for_erasing_remapping();
        }
    }

    // Third to manage the corner case if all the landmarks and keyframes are removed for a specific map
    // Disable this currently since we are closing the program after saving the keyframe/landmark map
    /*
    std::set<MapID> all_map_ids = p_all_map_db_->get_all_registered_map_ids();
    for (auto& map_id : all_map_ids) {
        std::map<LandmarkID, openvslam::data::landmark*> landmarks_for_map;
        p_all_map_db_->get_all_landmarks_map(landmarks_for_map, map_id);
        if (!landmarks_for_map.empty()) continue;

        std::map<KeyframeID, openvslam::data::keyframe*> keyframes_for_map;
        p_all_map_db_->get_all_keyframes_map(keyframes_for_map, map_id);
        if (!keyframes_for_map.empty()) continue;

        p_all_map_db_->unregister_map_id(map_id);
    }
    */

    // Print log info fot the debugging
    spdlog::info("Totally removed {} client landmarks and {} client keyframes outside the remapping region!",
                  removed_landmarks.size(), removed_keyframes.size());
}

void Server::set_coordinate_transform(ClientID client_id_for_map_to_be_aligned,
                                      const Eigen::Matrix4d transform_ww_aligned_ref)
{
    std::optional<Eigen::Matrix4d> Tww_aligned_ref = std::make_optional<Eigen::Matrix4d>(transform_ww_aligned_ref);
    handlers_.at(client_id_for_map_to_be_aligned).set_coordinate_transform_matrix(Tww_aligned_ref);
}

}  // namespace univloc_server
