// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "server/server.h"
#include <iostream>
#include <opencv2/core/eigen.hpp>
#include <time.h>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud.hpp>
#include <geometry_msgs/msg/point32.h>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <string>
#include <string.h>
#include <spdlog/spdlog.h>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace cv;
using namespace std::chrono_literals;

#define SENT_FLAG_RESET_TIME    4.5

namespace univloc_server {

ClientHandler::ClientHandler(ClientID client_id, Server* server)
    : client_id_(client_id),
      server_(server),
      current_keyframe_(nullptr),
      current_session_start_time_(0.),
      merge_times_(0),
      relocalizer_(server_->get_bow_database(), Camera::setup_type_t::RGBD)
{
    spdlog::info("~~~~~~~~~~~~~~~~~Create thread for client {} ~~~~~~~~~~~~~~~~~ ", static_cast<int>(client_id));
    running_ = true;
    requesting_pause_ = false;
    paused_ = false;
    worker_thread_ = std::make_unique<std::thread>(&ClientHandler::worker, this);
    last_msg_id_ = 0;
    map_id_ = 0xFFFFFFFF;
    spdlog::info("~~~~~~~~~~~~~~~~~~Run thread to process message from client {} ~~~~~~~~~~~~~~~~~~",
                 static_cast<int>(client_id));
}

ClientHandler::~ClientHandler()
{
    spdlog::info("~~~~~~~~~~~~~~~~~~Client handler {} cleanup! ~~~~~~~~~~~~~~~~~~",
                 static_cast<int>(client_id_));
}

void ClientHandler::shutdown() {
    running_ = false;
    message_event_.notify_one();
    if (worker_thread_ && worker_thread_->joinable())
        worker_thread_->join();
}

void ClientHandler::save_trajectory(std::string folder)
{
    std::map<MapID, std::ofstream> streams;
    int num = 0;
    auto map_db = server_->get_map_database();
    for (auto kfid : keyframes_) {
        Keyframe* kf = map_db->get_keyframe(kfid);
        if (!kf) continue;
        MapID mapid = kf->get_map_id();
        if (streams.find(mapid) == streams.end()) {
            std::string filename =
                folder + "/client" + std::to_string(get_client_id()) + "map" + std::to_string(mapid) + ".txt";
            streams[mapid] = std::ofstream(filename);
        }
        Eigen::Matrix4d Twc = kf->get_cam_pose_inv();
        Eigen::Matrix3d R = Twc.block(0, 0, 3, 3);
        Eigen::Quaterniond q(R);
        streams[mapid] << std::setprecision(18)
                       << kf->timestamp_ << " "
                       << Twc(0, 3) << " " << Twc(1, 3) << " " << Twc(2, 3) << " "
                       << q.x() << " " << q.y() << " " << q.z() << " " << q.w()
                       << std::endl;
        num++;
    }
    spdlog::debug("Save trajectory for Client {} with {} keyframes", std::to_string(client_id_), num);
}

void ClientHandler::receive_map_message(Map_Msg_ConstPtr msg)
{
    std::unique_lock<std::mutex> lock(message_mutex_);
    message_queue_.push(msg);
    lock.unlock();
    message_event_.notify_one();
}

unsigned int ClientHandler::get_merge_times() { return merge_times_; }

void ClientHandler::increase_merge_times() { merge_times_++; }

void ClientHandler::decrease_merge_times() { merge_times_--; }

MapID ClientHandler::get_map_id() const { return map_id_; }

ClientID ClientHandler::get_client_id() const { return client_id_; }

void ClientHandler::set_map_id(ClientID map_id) { map_id_ = map_id; }

Keyframe* ClientHandler::get_current_keyframe() const
{
    std::shared_lock lock(current_keyframe_mutex_);
    return current_keyframe_;
}

std::vector<Keyframe*> ClientHandler::get_latest_keyframe_of_all_sessions() const
{
    std::shared_lock lock1(current_keyframe_mutex_);
    std::shared_lock lock2(end_keyframe_of_old_sessions_mutex_);
    std::vector<Keyframe*> ret = end_keyframe_of_old_sessions_;
    if (current_keyframe_) ret.push_back(current_keyframe_);
    return ret;
}

void ClientHandler::pause(bool wait_until_paused)
{
    std::unique_lock lock(message_mutex_);
    requesting_pause_ = true;
    lock.unlock();
    message_event_.notify_one();
    if (wait_until_paused)
        while (!paused_) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    spdlog::info(" client {} Paused and left {} msg in the queue", (int)client_id_, message_queue_.size());
}

bool ClientHandler::is_paused() const { return paused_; }

void ClientHandler::resume()
{
    std::unique_lock lock(message_mutex_);
    if (requesting_pause_) {
        requesting_pause_ = false;
        lock.unlock();
        message_event_.notify_one();
        spdlog::info("Resume client {}", client_id_);
    }
    mapid_before_optimization_ = map_id_;
}

int ClientHandler::msg_queue_size() const { return message_queue_.size(); }

double ClientHandler::get_current_session_start_time() { return current_session_start_time_; }

void ClientHandler::record_mapid_before_optimization() { mapid_before_optimization_ = map_id_; }

void ClientHandler::record_mapid_before_optimization(MapID map_id) { mapid_before_optimization_ = map_id; }

MapID ClientHandler::get_mapid_before_optimization() { return mapid_before_optimization_; }

void ClientHandler::process_msg_stored_in_queue(MapID merged_mapid)
{
    std::queue<Map_Msg_ConstPtr> stored_msgs_queue;
    // auto start_time = ros::Time::now();
    auto start_time = now();
    std::unique_lock<std::mutex> message_lock(message_mutex_);

    MapID original_map_id = map_id_;
    // map_id_ = merged_map_id;

    while (!message_queue_.empty()) {
        stored_msgs_queue.push(message_queue_.front());
        message_queue_.pop();
    }
    message_lock.unlock();
    MapID original_mapid = map_id_;
    int stored_msg_size = stored_msgs_queue.size();
    spdlog::info("There exists {} old msg in the queue for client {} to be processed ", stored_msg_size, client_id_);
    while (!stored_msgs_queue.empty()) {
        auto msg = stored_msgs_queue.front();
        stored_msgs_queue.pop();
        if (last_msg_id_ != 0 && msg->msg_id != last_msg_id_ + 1) {
            spdlog::warn("Lose message in client {}  between message {}  and {}", client_id_, last_msg_id_,
                         msg->msg_id);
        }
        last_msg_id_ = msg->msg_id;

        assert(msg->mn_client_id == client_id_);
        merge_times_from_msg_ = static_cast<unsigned int>(msg->merge_times);
        if (msg->session_start_time != current_session_start_time_) {
            register_new_session(msg);
        }

        Keyframe* current_keyframe = process_keyframes(msg);
        if (unlikely(!current_keyframe)) {
            spdlog::warn("There is no new keyframe in the message, which violates the rule. Debug it!");
            continue;
        }
        std::unique_lock lock(current_keyframe_mutex_);
        current_keyframe_ = current_keyframe;
        lock.unlock();
        spdlog::info("Create Keyframe {} in the  process_msg_stored_in_queue", current_keyframe->id_);

        // TODO: change logic for monocular relocalization
        if (!msg->need_relocalization) {
            server_->publish_tf(current_keyframe, client_id_);
            process_mappoints(msg);
        } else {
            spdlog::debug("----------------1 Start relocalization----------------");
            relocalize_monocular_image(msg->msg_timestamp);
            free_current_keyfrm_after_relocalize();
        }
    }

    if (new_keyframes_.size() > 0) {
        // In this procedure, we just queue this new keyframe into bow_db instead of global_optimizer
        for (auto& kf : new_keyframes_) {
            if (kf->get_map_id() == original_mapid) {
                kf->set_map_id(merged_mapid);
                auto lms = kf->get_landmarks();
                for (auto& lm : lms) {
                    if (lm) lm->set_map_id(merged_mapid);
                }
            }
        }
        update_connections();

        queue_new_keyframe_to_bow_db();  //
        for (auto& kf : new_keyframes_) {
            if (kf->get_map_id() == original_map_id) kf->set_map_id(merged_mapid);
        }
        new_keyframes_.clear();
    }

    // ros::Time end_time = ros::Time::now();
    auto end_time = now();
    spdlog::debug("client {} Processed  {} msgs in the queue cost time {} ms", client_id_, stored_msg_size,
                  duration_ms(end_time - start_time));
    spdlog::debug("There still exists {} msg to be processed!", message_queue_.size());
}

void ClientHandler::worker()
{
    spdlog::info("Start handler for client-{}", (int)client_id_);
    double cost_time = 0;
    unsigned int run_times = 0;
    while (rclcpp::ok())
    {  // running_
        std::unique_lock<std::mutex> message_lock(message_mutex_);

        if (unlikely((message_queue_.empty() || paused_) && paused_ == requesting_pause_)) message_event_.wait_for(message_lock, 100ms);

        paused_ = requesting_pause_;

        if (unlikely(message_queue_.empty() || paused_)) {
            continue;
        }
        // ros::Time start_time = ros::Time::now();
        auto start_time = now();
        Map_Msg_ConstPtr msg = message_queue_.front();

        if (unlikely(last_msg_id_ != 0 && msg->msg_id != last_msg_id_ + 1)) {
            spdlog::warn("Lost message in client {}  between message {}  and {}", client_id_, last_msg_id_,
                         msg->msg_id);
        }

        last_msg_id_ = msg->msg_id;

        message_queue_.pop();
        message_lock.unlock();
        assert(msg->mn_client_id == client_id_);

        // deal with special case first
        if (msg->is_request_for_server_landmarks) {
            assert(msg->keyframes.size() == 1);
            /*
                Since tracker will clear server landmarks every 5
                seconds, so we need to reset the is_previously_sent
                flag for all landmarks every 4.5 seconds. We leave
                0.5 seconds for the pre-query logic of tracker and
                network delay.
            */
            if (msg->msg_timestamp - last_sent_flag_reset_timestamp_ > SENT_FLAG_RESET_TIME) {
                server_->get_map_database()->reset_sent_flag_for_all_landmarks();
                last_sent_flag_reset_timestamp_ = msg->msg_timestamp;
            }

            Eigen::Matrix4d cam_pose_cw = Eigen::Matrix4d::Identity();
            arrayToEigen(cam_pose_cw, msg->keyframes[0].mv_pose);
            send_back_server_landmarks(cam_pose_cw, msg->frame_id, msg->keyframes[0].mn_localize_map_id);
            // ros::Time break_time = ros::Time::now();
            auto break_time = now();
            spdlog::debug("Processing request for server landmarks cost time: {} ms",
                          duration_ms(break_time - start_time));
            continue;
        }

        if (msg->is_tracker_octree) {

            if (msg->octree.empty()) {
                spdlog::error("Octree array in Map.msg is empty while is_tracker_octree is set");
                continue;
            }

            struct fast_mapping::camera_intrinsics octree_intrinsic;
            struct fast_mapping::se_cfg octree_cfg;
            auto octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
            spdlog::info("Received octree from client_id {}", msg->mn_client_id);
            server_->mapmsg_to_param_and_octree(msg, octree, octree_intrinsic, octree_cfg);

            const auto client_id = msg->mn_client_id;
            {
                // avoid race condition for two client handlers to add values to containers
                std::scoped_lock lock(server_->octree_mutex_);
                server_->get_octree_from_trackers().emplace(client_id, octree);
                server_->get_octree_cfg_from_trackers().emplace(client_id, octree_cfg);
                server_->get_octree_intrinsic_from_trackers().emplace(client_id, octree_intrinsic);

                if (server_->received_all_octrees()) {
                    spdlog::info("Received octrees from all clients. sending back merged octree");
                    server_->send_merged_octree_to_trackers();
                }
            }
            continue;
        }

        if (msg->need_relocalization) {
            spdlog::debug("{}: msg->need_relocalization is true!", client_id_);
            if (current_keyframe_ && current_keyframe_->graph_node_->get_spanning_parent()) {
                std::unique_lock lock(end_keyframe_of_old_sessions_mutex_);
                if (!end_keyframe_of_old_sessions_.empty() &&
                    current_keyframe_ != end_keyframe_of_old_sessions_.back())
                    end_keyframe_of_old_sessions_.push_back(current_keyframe_);
            }
        } else if (msg->session_start_time != current_session_start_time_) {
            register_new_session(msg);
        }

        std::lock_guard<std::mutex> lock(openvslam::data::map_database::mtx_map_database_[map_id_]);
        std::lock_guard<std::mutex> lock1(
            openvslam::data::map_database::mtx_client_map_database_[std::make_pair(client_id_, map_id_)]);
        // may cause problem
        merge_times_from_msg_ = static_cast<unsigned int>(msg->merge_times);
        Keyframe* current_keyframe = process_keyframes(msg);
        if (unlikely(!current_keyframe)) {
            spdlog::warn("There is no new keyframe in the message, which violates the rule. Debug it!");
            continue;
        }
        std::unique_lock frame_lock(current_keyframe_mutex_);
        current_keyframe_ = current_keyframe;
        frame_lock.unlock();

        // TODO: change logic for monocular relocalization
        if (!msg->need_relocalization) {
            server_->publish_tf(current_keyframe, client_id_);
            process_mappoints(msg);
            update_connections();

            if (new_keyframes_.size() > 0) {
                std::vector<Keyframe*> local_keyfrms;
                //! Just for debugging to show the status!
                // get_local_keyframes(clients_cur_keyframe_[client_id], local_keyfrms);
                // print_keyframes_connections(local_keyfrms);
                queue_new_keyframe_to_global_optimizer();
                new_keyframes_.clear();
            }
        } else {
            spdlog::debug("----------------2 Start relocalization----------------");
            relocalize_monocular_image(msg->msg_timestamp);
            free_current_keyfrm_after_relocalize();
        }

        // ros::Time end_time = ros::Time::now();
        auto end_time = now();
        cost_time += duration_ms(end_time - start_time);
        run_times++;
        spdlog::debug("[Client Handler {}]: utill now processed {} msgs with time cost: {} ms", client_id_, run_times,
                      cost_time);
    }
    spdlog::info("[Client Handler {}]: Totally Processed {} msgs with total time cost: {} ms", client_id_, run_times,
                 cost_time);
}

void ClientHandler::register_new_session(Map_Msg_ConstPtr& msg) {
    // Client has started a new session, we need to register a new map
    map_id_ = server_->get_map_database()->register_new_map_id();
    spdlog::info("Client-{0} starts a new session at {1:09.3f}, registered new map-{2}", client_id_,
        msg->session_start_time, map_id_);
    current_session_start_time_ = msg->session_start_time;
    std::shared_lock lock(current_keyframe_mutex_);
    if (current_keyframe_) {
        std::unique_lock lock(end_keyframe_of_old_sessions_mutex_);
        end_keyframe_of_old_sessions_.push_back(current_keyframe_);
    }
}

Keyframe* ClientHandler::process_keyframes(const Map_Msg_ConstPtr& msg)
{
    spdlog::debug("Processing {} old keyframes", msg->keyframe_updates.size());

    for (const Old_Keyframe_Msg& old_keyframe_msg : msg->keyframe_updates) update_keyframe(old_keyframe_msg);

    spdlog::debug("Processing {} new keyframes", msg->keyframes.size());
    // ros::Time start = ros::Time::now();
    auto start = now();
    Map_database* p_map = server_->get_map_database();
    Keyframe* current_keyframe = nullptr;
    for (const Keyframe_Msg& keyframe_msg : msg->keyframes) {
        if (camera_type_ == Camera::setup_type_t::RGBD || camera_type_ == Camera::setup_type_t::RGBD_Inertial ||
            camera_type_ == Camera::setup_type_t::Stereo_Inertial || camera_type_ == Camera::setup_type_t::Stereo)
            current_keyframe = create_rgbd_keyframe_from_msg(keyframe_msg, msg->need_relocalization);
        else if (camera_type_ == Camera::setup_type_t::Monocular ||
                 camera_type_ == Camera::setup_type_t::Monocular_Inertial) {
            current_keyframe = create_monocular_keyframe_from_msg(keyframe_msg, msg->need_relocalization);
        }

        if (current_keyframe) {
            server_->check_camera_fusion(current_keyframe);
            keyframes_.push_back(current_keyframe->id_);
        }
    }

    auto& erased_keyframesId = msg->erase_keyframes_id;
    for (auto id : erased_keyframesId) {
        spdlog::debug("Erase Keyframe {}", id);
        Keyframe* kf = p_map->get_keyframe(id);
        if (kf) {
            kf->prepare_for_erasing();
        }
    }

    // ros::Time end = ros::Time::now();
    auto end = now();
    spdlog::debug("Processing frames consumes time {} ms", duration_ms(end - start));
    spdlog::debug("There are {} keyframes in map_dataset", p_map->get_num_keyframes());
    return current_keyframe;
}

void ClientHandler::update_keyframe(Keyframe* p_keyframe, const Keyframe_Msg& keyframe_msg)
{
    /*p_keyframe->set_will_be_erazed(keyframe_msg.mbWill_be_erased);
    if (keyframe_msg.mbWill_be_erased) {
        spdlog::debug("Remove keyframe : {}", keyframe_msg.mn_id);
        p_keyframe->prepare_for_erasing();  // Here may occur problem
        return;
    }*/

    assert(merge_times_ >= merge_times_from_msg_);
    // Only if this message  is new to the last loop optimization and don't start a new session when optimization, we
    // will update the pose
    if (merge_times_ == merge_times_from_msg_) {
        Eigen::Matrix4d cam_pose_cw;
        arrayToEigen(cam_pose_cw, keyframe_msg.mv_pose);
        p_keyframe->set_cam_pose(cam_pose_cw);
    }
}

void ClientHandler::update_keyframe(const Old_Keyframe_Msg& msg)
{
    auto p_keyframe = server_->get_map_database()->get_keyframe(msg.mn_id);
    if (!p_keyframe) {
        spdlog::debug(
            "This keyframe {} was not newly created, but also not in mapdateset, maybe it was deleted by the Server or "
            "msg lost!",
            msg.mn_id);
        return;
    }
    assert(merge_times_ >= merge_times_from_msg_);
    // Only if this message  is new to the last loop optimization and don't start a new session when optimization, we
    // will update the pose
    if (merge_times_ == merge_times_from_msg_) {
        Eigen::Matrix4d cam_pose_cw;
        arrayToEigen(cam_pose_cw, msg.mv_pose);
        p_keyframe->set_cam_pose(cam_pose_cw);
    }
}

void ClientHandler::set_camera_type(const unsigned int camera_type_order)
{
    camera_type_ = static_cast<Camera::setup_type_t>(camera_type_order);
    relocalizer_.set_camera_type(camera_type_);
}

Keyframe* ClientHandler::create_monocular_keyframe_from_msg(const Keyframe_Msg& keyframe_msg,
                                                            bool is_relocalization_keyfrm)
{
    uint client_id = keyframe_msg.mn_client_id;

    std::vector<cv::KeyPoint> undist_keypts, keypts;
    unsigned int N_un = keyframe_msg.mv_keypoints.size();
    cv::KeyPoint undist_keypt, keypt;
    keypts.resize(N_un);
    for (unsigned int i = 0; i < N_un; i++) {
        keypt.pt.x = keyframe_msg.mv_keypoints[i].fpoint2fx;
        keypt.pt.y = keyframe_msg.mv_keypoints[i].fpoint2fy;
        keypt.angle = keyframe_msg.mv_keypoints[i].angle;
        keypt.size = keyframe_msg.mv_keypoints[i].size;
        keypt.octave = keyframe_msg.mv_keypoints[i].octave;
        keypts[i] = keypt;
    }

    cv::Mat mv_descriptors;
    Descriptor_Msg TempDesc = keyframe_msg.mv_descriptors[0];
    int iBoundY = static_cast<int>(TempDesc.m_descriptor.size());
    int iBoundX = static_cast<int>(keyframe_msg.mv_descriptors.size());
    mv_descriptors = cv::Mat(iBoundX, iBoundY, 0);

    for (uint idx = 0; idx < keyframe_msg.mv_descriptors.size(); ++idx) {
        Descriptor_Msg DescMsg = keyframe_msg.mv_descriptors[idx];
        for (int idy = 0; idy < iBoundY; ++idy) {
            mv_descriptors.at<uint8_t>(idx, idy) = DescMsg.m_descriptor[idy];
        }
    }
    KeyframeID id = keyframe_msg.mn_id;
    double timestamp = keyframe_msg.md_timestamp;
    KeyframeID src_frm_id = keyframe_msg.mn_src_frame_id;
    float depth_thr = keyframe_msg.mf_depth_thr;
    unsigned int num_scale_levels = keyframe_msg.mn_scale_levels;
    float scale_factor = keyframe_msg.mf_scale_factor;
    Eigen::Matrix4d cam_pose_cw, cam_pose_cw_msg;
    for (int idx = 0; idx < cam_pose_cw.rows(); ++idx)
        for (int idy = 0; idy < cam_pose_cw.cols(); ++idy)
            cam_pose_cw(idx, idy) = (double)keyframe_msg.mv_pose[idx * cam_pose_cw.rows() + idy];
    cam_pose_cw_msg = cam_pose_cw;

    assert(merge_times_ >= merge_times_from_msg_);
    // flag to determine if the keyframe can trigger server optim
    bool available_for_loop_detector = true;
    // If this message is old and no new session is created when optimization, then we should allign the pose to the
    // existed parent frame
    if (merge_times_ > merge_times_from_msg_ && map_id_ == mapid_before_optimization_) {
        // since client hasn't finished update after server optimization
        // then the keyframes from the client should not trigger new server optimization
        // otherwise, it will be difficult to align the pose due to multiple server optims
        available_for_loop_detector = false;
        Keyframe* p_parent = server_->get_map_database()->get_keyframe(keyframe_msg.mn_parent_id);
        if (!p_parent) {
            spdlog::warn("{}: failed to get parent keyframe with id {}", __func__, keyframe_msg.mn_parent_id);
            return nullptr;
        }
        spdlog::debug("merge_times: {}, merge_times_from_msg: {} clientID: {}", merge_times_, merge_times_from_msg_,
                      client_id_);

        spdlog::debug("Keyframe {} Position Before Aligning: {} {} {}", id, cam_pose_cw.inverse()(0, 3),
                      cam_pose_cw.inverse()(1, 3), cam_pose_cw.inverse()(2, 3));

        cam_pose_cw = cam_pose_cw * p_parent->cam_pose_cw_before_BA_.inverse() * p_parent->get_cam_pose();
        spdlog::debug("Position After Aligning: {} {} {}", cam_pose_cw.inverse()(0, 3), cam_pose_cw.inverse()(1, 3),
                      cam_pose_cw.inverse()(2, 3));
    }

    unsigned int num_keypts = keyframe_msg.mn_num_keypoints;
    assert(num_keypts == N_un);
    std::vector<float> stereo_x_right = std::vector<float>(num_keypts, -1);
    std::vector<float> depths = std::vector<float>(num_keypts, -1);

    //! bearing vectors
    openvslam::eigen_alloc_vector<Eigen::Vector3d> bearings_;
    auto camera = server_->get_camera_database()->get_client_camera(keyframe_msg.mn_client_id);

    camera->undistort_keypoints(keypts, undist_keypts);
    camera->convert_keypoints_to_bearings(undist_keypts, bearings_);
    Map_database* p_map = server_->get_map_database();

    auto p_keyframe = new Keyframe(id, src_frm_id, timestamp, cam_pose_cw, camera, depth_thr, num_keypts, keypts,
                                   undist_keypts, bearings_, stereo_x_right, depths, mv_descriptors, num_scale_levels,
                                   scale_factor, server_->get_bow_vocabulary(), server_->get_bow_database(), p_map,
                                   client_id, map_id_);

    if (!is_relocalization_keyfrm) {
        p_keyframe->mdServerTimestamp = rclcpp::Clock().now().seconds();
        p_keyframe->cam_pose_cw_before_BA_ = cam_pose_cw_msg;
        p_map->add_keyframe(p_keyframe);
        new_keyframes_.push_back(p_keyframe);
        // add origin keyframe for each map session!
        if (!p_map->get_origin_keyframe(map_id_)) {
            p_map->add_origin_keyframe(map_id_, p_keyframe);
            p_keyframe->set_origin();
            spdlog::debug("Successfully set origin  keyframe {} for client {}  map {}", p_keyframe->id_,
                          (unsigned int)client_id, (unsigned int)map_id_);
            current_origin_keyframe_ = p_keyframe;
        }

        p_keyframe->available_for_loop_detector_ = available_for_loop_detector;
        p_keyframe->bad_imu_to_reset_ = keyframe_msg.mb_bad_imu_to_reset;

        spdlog::debug("Successfully create keyframe {0} on map-{1} with stamp {2:9.3f}", p_keyframe->id_,
                      p_keyframe->get_map_id(), p_keyframe->timestamp_);
    }

    return p_keyframe;
}

Keyframe* ClientHandler::create_rgbd_keyframe_from_msg(const Keyframe_Msg& keyframe_msg,
                                                       bool is_relocalization_keyfrm)
{
    uint client_id = keyframe_msg.mn_client_id;
    std::vector<cv::KeyPoint> undist_keypts, keypts;
    int N_un = keyframe_msg.mv_keypoints.size();
    cv::KeyPoint undist_keypt, keypt;
    keypts.resize(N_un);
    for (int i = 0; i < N_un; i++) {
        keypt.pt.x = keyframe_msg.mv_keypoints[i].fpoint2fx;
        keypt.pt.y = keyframe_msg.mv_keypoints[i].fpoint2fy;
        keypt.angle = keyframe_msg.mv_keypoints[i].angle;
        keypt.size = keyframe_msg.mv_keypoints[i].size;
        keypt.octave = keyframe_msg.mv_keypoints[i].octave;
        keypts[i] = keypt;
    }

    cv::Mat mv_descriptors;
    Descriptor_Msg TempDesc = keyframe_msg.mv_descriptors[0];
    int iBoundY = static_cast<int>(TempDesc.m_descriptor.size());
    int iBoundX = static_cast<int>(keyframe_msg.mv_descriptors.size());
    mv_descriptors = cv::Mat(iBoundX, iBoundY, 0);
    uint desc_size = keyframe_msg.mv_descriptors.size();
    for (uint idx = 0; idx < desc_size; ++idx) {
        Descriptor_Msg DescMsg = keyframe_msg.mv_descriptors[idx];
        for (int idy = 0; idy < iBoundY; ++idy) {
            mv_descriptors.at<uint8_t>(idx, idy) = DescMsg.m_descriptor[idy];
        }
    }
    KeyframeID id = keyframe_msg.mn_id;
    double timestamp = keyframe_msg.md_timestamp;
    KeyframeID src_frm_id = keyframe_msg.mn_src_frame_id;
    float depth_thr = keyframe_msg.mf_depth_thr;
    unsigned int num_scale_levels = keyframe_msg.mn_scale_levels;
    float scale_factor = keyframe_msg.mf_scale_factor;
    Eigen::Matrix4d cam_pose_cw, cam_pose_cw_msg;
    for (int idx = 0; idx < cam_pose_cw.rows(); ++idx)
        for (int idy = 0; idy < cam_pose_cw.cols(); ++idy)
            cam_pose_cw(idx, idy) = (double)keyframe_msg.mv_pose[idx * cam_pose_cw.rows() + idy];
    cam_pose_cw_msg = cam_pose_cw;

    assert(merge_times_ >= merge_times_from_msg_);
    // flag to determine if the keyframe can trigger server optim
    bool available_for_loop_detector = true;
    // If this message is old and no new session is created when optimization, then we should allign the pose to the
    // existed parent frame
    if (merge_times_ > merge_times_from_msg_ && map_id_ == mapid_before_optimization_) {
        // since client hasn't finished update after server optimization
        // then the keyframes from the client should not trigger new server optimization
        // otherwise, it will be difficult to align the pose due to multiple server optims
        available_for_loop_detector = false;
        // If msg lost, we should use another way to find the relative keyframe to align
        Keyframe* p_parent = server_->get_map_database()->get_keyframe(keyframe_msg.mn_parent_id);
        if (!p_parent) {
            const int trial_times = 10;
            for (unsigned int i = 1; i <= trial_times; i++) {
                p_parent = server_->get_map_database()->get_keyframe(keyframe_msg.mn_parent_id - i);
                if (p_parent && p_parent->get_map_id() == map_id_) break;
                if (keyframe_msg.mn_parent_id == i) break;
            }
        }
        if (unlikely(!p_parent)) {
            spdlog::warn("{}: failed to get parent keyframe with id {}", __func__, keyframe_msg.mn_parent_id);
            return nullptr;
        }

        spdlog::debug("merge_times: {}, merge_times_from_msg: {} clientID: {}", merge_times_, merge_times_from_msg_,
                      client_id_);

        spdlog::debug("Parent keyframe {} Position cam_pose_cw_before_BA_: {} {} {}", keyframe_msg.mn_parent_id,
                      p_parent->cam_pose_cw_before_BA_.inverse()(0, 3),
                      p_parent->cam_pose_cw_before_BA_.inverse()(1, 3),
                      p_parent->cam_pose_cw_before_BA_.inverse()(2, 3));
        spdlog::debug("Parent keyframe {} Position cam_pose_cw_after_BA_: {} {} {}", keyframe_msg.mn_parent_id,
                      p_parent->get_cam_pose_inv()(0, 3), p_parent->get_cam_pose_inv()(1, 3),
                      p_parent->get_cam_pose_inv()(2, 3));

        spdlog::debug("Keyframe {} Position Before Aligning: {} {} {}", id, cam_pose_cw.inverse()(0, 3),
                      cam_pose_cw.inverse()(1, 3), cam_pose_cw.inverse()(2, 3));

        cam_pose_cw = cam_pose_cw * p_parent->cam_pose_cw_before_BA_.inverse() * p_parent->get_cam_pose();
        spdlog::debug("Position After Aligning: {} {} {}", cam_pose_cw.inverse()(0, 3), cam_pose_cw.inverse()(1, 3),
                      cam_pose_cw.inverse()(2, 3));
    }

    std::vector<float> stereo_x_right;
    uint n = keyframe_msg.mv_stereo_x_right.size();
    stereo_x_right.resize(n);
    for (uint idx = 0; idx < n; idx++) {
        stereo_x_right[idx] = keyframe_msg.mv_stereo_x_right[idx];
    }

    unsigned int num_keypts = keyframe_msg.mn_num_keypoints;

    //! bearing vectors
    openvslam::eigen_alloc_vector<Eigen::Vector3d> bearings_;
    auto camera = server_->get_camera_database()->get_client_camera(keyframe_msg.mn_client_id);

    camera->undistort_keypoints(keypts, undist_keypts);

    camera->convert_keypoints_to_bearings(undist_keypts, bearings_);
    Map_database* p_map = server_->get_map_database();

    std::vector<float> depths = std::vector<float>(num_keypts, -1);

    auto p_keyframe = new Keyframe(id, src_frm_id, timestamp, cam_pose_cw, camera, depth_thr, num_keypts, keypts,
                                   undist_keypts, bearings_, stereo_x_right, depths, mv_descriptors, num_scale_levels,
                                   scale_factor, server_->get_bow_vocabulary(), server_->get_bow_database(), p_map,
                                   client_id, map_id_);

    if (!is_relocalization_keyfrm) {
        p_keyframe->mdServerTimestamp = rclcpp::Clock().now().seconds();
        p_keyframe->cam_pose_cw_before_BA_ = cam_pose_cw_msg;
        p_map->add_keyframe(p_keyframe);
        new_keyframes_.push_back(p_keyframe);
        // add origin keyframe for each map!
        if (!p_map->get_origin_keyframe(map_id_)) {
            p_map->add_origin_keyframe(map_id_, p_keyframe);
            p_keyframe->set_origin();
            spdlog::debug("Successfully set origin keyframe {} for client {} map {}", p_keyframe->id_,
                          (unsigned int)client_id, (unsigned int)map_id_);
            current_origin_keyframe_ = p_keyframe;
        }

        p_keyframe->available_for_loop_detector_ = available_for_loop_detector;
        p_keyframe->bad_imu_to_reset_ = keyframe_msg.mb_bad_imu_to_reset;

        spdlog::debug("Successfully create keyframe {0} on map-{1} with stamp {2:9.3f}", p_keyframe->id_,
                      p_keyframe->get_map_id(), p_keyframe->timestamp_);
    }

    return p_keyframe;
}

Keyframe* ClientHandler::get_current_origin_keyframe() { return current_origin_keyframe_; }

void ClientHandler::process_mappoints(const Map_Msg_ConstPtr& msg)
{
    ClientID client_id = msg->mn_client_id;
    static uint total_landmark_size = 0;
    unsigned int num_erase = 0, num_add = 0;
    // ros::Time start = ros::Time::now();
    auto start = now();
    Map_database* p_map = server_->get_map_database();
    for (const Mappoint_Msg& mappoint_msg : msg->landmarks) {
        // assert(!mappoint_msg.mbWill_be_erased);

        Mappoint* landmark = p_map->get_landmark(mappoint_msg.mn_id);

        if (!landmark) {
            Keyframe* p_Refkeyframe = p_map->get_keyframe(mappoint_msg.mn_refer_keyframe_id);
            if (!p_Refkeyframe) {
                spdlog::debug("There is no reference frame {} for this mappoint {}, we will choose another \
                              keyframe as its reference keyframe", mappoint_msg.mn_refer_keyframe_id,
                              mappoint_msg.mn_id);

                for (uint idx : mappoint_msg.mv_observation_keyframe_ids) {
                    p_Refkeyframe = p_map->get_keyframe(idx);
                    if (p_Refkeyframe) break;
                }
                if (!p_Refkeyframe) continue;
            }
            unsigned int num_visible = 0, num_found = 0;
            Eigen::Vector3d pos_w((double)mappoint_msg.mv_position[0], (double)mappoint_msg.mv_position[1],
                                  (double)mappoint_msg.mv_position[2]);
            LandmarkID id = mappoint_msg.mn_id;
            /*
                The mn_first_keyframe_id is always 0 in our current implementation
                So we decide not to pass it over network.
            */
            // KeyframeID mnFirstKFid = mappoint_msg.mn_first_keyframe_id;
            assert(merge_times_ >= merge_times_from_msg_);
            if (merge_times_ > merge_times_from_msg_ && map_id_ == mapid_before_optimization_) {
                auto pose_in_cam = p_Refkeyframe->cam_pose_cw_before_BA_ * pos_w.homogeneous();
                pos_w = (p_Refkeyframe->get_cam_pose_inv() * pose_in_cam).head(3);
            }
            landmark =
                new Mappoint(id, 0, pos_w, p_Refkeyframe, num_visible, num_found, p_map, client_id, map_id_);
            p_map->add_landmark(landmark);
            total_landmark_size++;
            num_add++;
        }

        update_mappoint(mappoint_msg, p_map);
    }

    // Erase rebundant landmarks
    for (auto erase_mappoint_id : msg->erase_landmarks_id) {
        auto lm = p_map->get_landmark(erase_mappoint_id);
        if (lm) lm->prepare_for_erasing();
    }

    // ros::Time end = ros::Time::now();
    auto end = now();
    spdlog::debug("Processed {} landmark messages (cost {} ms). Added {}. Erased {}. Now {} in database",
                  msg->landmarks.size(), duration_ms(end - start), num_add, num_erase, p_map->get_num_landmarks());
    spdlog::debug("There are total_landmark_size {}  mappoints received from client {}", total_landmark_size,
                  client_id_);
}

void ClientHandler::update_mappoint(const Mappoint_Msg& mappoint_msg, Map_database* p_map)
{
    LandmarkID id = mappoint_msg.mn_id;
    Mappoint* p_mappoint = p_map->get_landmark(id);
    if (unlikely(!p_mappoint)) {
        spdlog::critical("No such mappoint {} in map database", id);
        throw std::runtime_error("You should add landmark into database before calling update_mappoint");
    }
    Eigen::Vector3d pos_w((double)mappoint_msg.mv_position[0], (double)mappoint_msg.mv_position[1],
                          (double)mappoint_msg.mv_position[2]);
    assert(merge_times_ >= merge_times_from_msg_);
    if (merge_times_ == merge_times_from_msg_ || map_id_ != mapid_before_optimization_)
        p_mappoint->set_pos_in_world(pos_w);

    uint observation_size = mappoint_msg.mv_observation_keyframe_ids.size();
    Keyframe* p_keyframe = nullptr;
    auto last_observation_id = p_mappoint->get_identifier_last_observation_id();
    for (uint idx = 0; idx < observation_size; idx++) {
        p_keyframe = p_map->get_keyframe(mappoint_msg.mv_observation_keyframe_ids[idx]);
        if (unlikely(!p_keyframe)) {
            // This can happen because we have not yet received some of the latest keyframes at the client side
            // spdlog::debug("Can't find observation frame (ID: {}) for mappoint (ID: {})",
            // mappoint_msg.mv_observation_keyframe_ids[idx],
            //              p_mappoint->id_);
            continue;
        }
        last_observation_id = std::max(last_observation_id, p_keyframe->id_);
        p_mappoint->add_observation(p_keyframe, mappoint_msg.mv_observations_n[idx]);
        p_keyframe->add_landmark(p_mappoint, mappoint_msg.mv_observations_n[idx]);
    }

    // Future choice: To get descriptor from client or to calculate in server?
    /*size_t iBoundY = static_cast<int>(mappoint_msg.m_descriptor.size());
    cv::Mat Descriptor(1, iBoundY, CV_8UC1);
    memcpy(Descriptor.ptr(0), mappoint_msg.m_descriptor.data(), iBoundY * sizeof(uint8_t));
    p_mappoint->set_descriptor(Descriptor);*/
    if (mappoint_msg.mn_replace_other_id > 0) {
        Mappoint* p_replaced_mappoint = p_map->get_landmark(mappoint_msg.mn_replace_other_id);
        if (p_replaced_mappoint) {
            p_replaced_mappoint->replace(p_mappoint);
        }
    }
    p_mappoint->update_normal_and_depth();
    if (!mappoint_msg.mv_observation_keyframe_ids.empty()) p_mappoint->compute_descriptor();
    p_mappoint->set_identifier_last_observation_id(last_observation_id);
}

void ClientHandler::print_keyframes_connections(const std::vector<Keyframe*> keyframes) const
{
    for (auto& keyframe : keyframes) {
        if (!keyframe) continue;
        spdlog::debug("KeyframeID: {}", keyframe->id_);
        if (keyframe->graph_node_->get_spanning_parent()) {
            spdlog::debug("ParentID: {}", keyframe->graph_node_->get_spanning_parent()->id_);
        }
        auto children = keyframe->graph_node_->get_spanning_children();
        for (const auto& child : children) {
            if (child) {
                spdlog::debug("ChildrenID: {}", child->id_);
            }
        }
    }
}

void ClientHandler::update_connections()
{
    for (Keyframe* p_new_keyframe : new_keyframes_)
        if (p_new_keyframe) {
            p_new_keyframe->graph_node_->update_connections();
            /*
                TODO: last_keyframe_ doesn't update in the normal loop which 
                      causes the below if branch always equals to false!
            */
            if (!p_new_keyframe->graph_node_->get_spanning_parent() && !p_new_keyframe->is_origin() &&
                last_keyframe_) {
                p_new_keyframe->graph_node_->set_spanning_parent(last_keyframe_);
                spdlog::warn("This keyframe {} has no parent, which is abnormal ", p_new_keyframe->id_);
                last_keyframe_ = p_new_keyframe;
            }
        }
}

void ClientHandler::queue_new_keyframe_to_global_optimizer()
{
    /*
        The last element in the new_keyframes_ vector is the current keyframe on
        both tracker and server sides (ignore the delay during communication). We
        won't add it to the bow database since we will enqueue it into the global
        optimization module to detect loop closure. Otherwise, the loop closure
        will always happen since itself is also in the bow database.
    */
    if (new_keyframes_.size() > 1) {
        for (size_t i = 0; i < new_keyframes_.size() - 1; i++) {
            spdlog::debug("p_new_keyframe id :{}", new_keyframes_[i]->id_);
            server_->get_bow_database()->add_keyframe(new_keyframes_[i]);
        }
    }

    // only queued into global_optimizer keyframe will execute loop detect
    spdlog::debug("p_new_keyframe id :{}", new_keyframes_[new_keyframes_.size() - 1]->id_);
    server_->get_global_optimizer()->queue_keyframe(new_keyframes_[new_keyframes_.size() - 1]);
}

void ClientHandler::queue_new_keyframe_to_bow_db()
{
    static size_t num = 0;
    for (Keyframe* p_new_keyframe : new_keyframes_) {  // Need a lock ?
        server_->get_bow_database()->add_keyframe(p_new_keyframe);
        spdlog::debug("Totally queued {} keyframes directly to bow_database", num++);
    }
}

void ClientHandler::send_back_server_landmarks(Eigen::Matrix4d curr_pose, KeyframeID curr_id,
                                               unsigned int localize_map_id)
{
    const auto start = std::chrono::system_clock::now();
    // get server landmarks according to current pose
    std::vector<Mappoint*> server_landmarks;
    const int server_landmarks_num_thr = 20;
    // spdlog::debug("This frame id: {}, last frame id of relative client: {} ", frame->id_, current_frame->id_);
    {
        std::vector<cv::Point3f> point_3d;
        std::vector<cv::Point2f> point_2d;
        std::vector<cv::Point2f> convex_hull;
        auto camera = server_->get_camera_database()->get_client_camera(client_id_);
        server_landmarks = server_->p_all_map_db_->get_landmarks_in_frustum(
            curr_pose, camera, localize_map_id, 0, false, point_3d, point_2d, convex_hull, server_->near_distance_,
            server_->far_distance_, server_->back_distance_);
        if (server_landmarks.size() < server_landmarks_num_thr) {
            spdlog::debug("{} less than {} server landmarks, so we will not send them", server_landmarks.size(),
                          server_landmarks_num_thr);
            return;
        }

        // send landmarks back to client
        univloc_msgs::Map send_landmarks_msg;
        server_->convert_mappoints_to_msg(server_landmarks, send_landmarks_msg, true);
        if (send_landmarks_msg.landmarks.empty()) {
            spdlog::debug("total {} landmarks found in frustum but no extra landmarks will be sent");
            return;
        }

        send_landmarks_msg.only_add_landmarks = true;
        send_landmarks_msg.is_relocalization_result = false;
        send_landmarks_msg.is_request_for_server_landmarks = true;
        send_landmarks_msg.frame_id = curr_id;
        send_landmarks_msg.loop_closure = false;
        send_landmarks_msg.is_request_octree = false;
        send_landmarks_msg.is_merged_octree = false;

        spdlog::debug("Send back server landmarks for fame ID : {}", curr_id);
        server_->send_msg_to_client(client_id_, send_landmarks_msg);

        spdlog::debug("Send {} server landmarks to client {}", server_landmarks.size(), client_id_);
    }

    const auto end = std::chrono::system_clock::now();
    elapsed_ms_ = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    spdlog::debug("Send back server landmarks consumes time : {} ms.", elapsed_ms_);
}

void ClientHandler::relocalize_monocular_image([[maybe_unused]] double msg_timestamp)
{
    const auto start = std::chrono::system_clock::now();
    Keyframe* current_keyframe = get_current_keyframe();
    spdlog::debug("{}: keyframe id in relocalize func is : {}", client_id_, current_keyframe->id_);
    // construct frame using keyframe to fit the input of the relocalize function
    auto current_frame = Frame(*current_keyframe);
    MapID reloc_map_id;
    auto succeeded = relocalizer_.relocalize(current_frame, reloc_map_id, server_->p_all_map_db_, server_->bow_vocab_,
                                             server_->near_distance_, server_->far_distance_, server_->back_distance_);
    if (succeeded) {
        // map_id_ = current_frame.get_map_id();
        map_id_ = reloc_map_id;
        current_session_start_time_ = current_keyframe->timestamp_;
        spdlog::debug("relocalization succeeded, Map id is {}!", map_id_);
    } else {
        spdlog::debug("relocalization failed!");
        return;
    }
    // construct keyframe using frame
    // client_id_ need lock? or add client_id to frame
    spdlog::debug("frame id in relocalize func is : {}", current_frame.id_);
    // client_handler should set client_id as well as keyframe
    Keyframe *current_keyframe_after_relocalization = new Keyframe(current_frame, nullptr, nullptr, client_id_, map_id_);
    current_keyframe_after_relocalization->id_ = current_keyframe->id_;
    spdlog::debug("{}: constructed keyframe id: {}", client_id_, current_keyframe_after_relocalization->id_);
    // process keyframe
    std::vector<Keyframe*> relocalization_keyfrm;
    relocalization_keyfrm.push_back(current_keyframe_after_relocalization);
    // process landmark
    std::vector<Mappoint*> relocalization_mappoints;
    const auto lms = current_keyframe_after_relocalization->get_landmarks();

    unsigned int landmark_size = current_keyframe_after_relocalization->get_num_landmarks();
    // add nearby landmarks
    std::vector<cv::Point3f> point_3d;
    std::vector<cv::Point2f> point_2d;
    std::vector<cv::Point2f> convex_hull;
    std::vector<Mappoint*> nearby_landmarks = server_->get_map_database()->get_landmarks_in_frustum(
        current_keyframe_after_relocalization->get_cam_pose(), current_keyframe_after_relocalization->camera_,
        current_keyframe_after_relocalization->get_map_id(), 0, false, point_3d, point_2d, convex_hull,
        server_->near_distance_, server_->far_distance_, server_->back_distance_);
    for (unsigned int idx = 0; idx < nearby_landmarks.size(); ++idx) {
        auto lm = nearby_landmarks.at(idx);
        lm->observed_in_other_keyframe_index_ = landmark_size + 1;
        relocalization_mappoints.push_back(lm);
    }

    spdlog::debug("Sent back from server landmark size : {}", landmark_size);
    for (unsigned int idx = 0; idx < landmark_size; ++idx) {
        auto lm = lms.at(idx);
        if (!lm) {
            continue;
        }
        // TODO: erase this to see the result if the same
        if (unlikely(lm->will_be_erased())) {
            continue;
        }
        lm->observed_in_other_keyframe_index_ = idx;
        relocalization_mappoints.push_back(lm);
    }

    univloc_msgs::Map relocalization_result_msg;
    server_->convert_mappoints_to_msg(relocalization_mappoints, relocalization_result_msg);
    server_->convert_keyframes_to_msg(relocalization_keyfrm, relocalization_result_msg, client_id_);

    relocalization_result_msg.only_add_landmarks = false;
    relocalization_result_msg.is_relocalization_result = true;
    relocalization_result_msg.is_request_for_server_landmarks = false;
    relocalization_result_msg.loop_closure = false;
    relocalization_result_msg.is_request_octree = false;
    relocalization_result_msg.is_merged_octree = false;

    server_->send_msg_to_client(client_id_, relocalization_result_msg);

    delete current_keyframe_after_relocalization;
    current_keyframe_after_relocalization = nullptr;
    relocalization_keyfrm.clear();

    /*
        Reset is_previously_sent flag for all landmarks in map
        database, since if tracker side send a relocalization
        request in localization mode, it may means the tracker
        has reset and clear all the stored landmarks from server.

        Another reason is that, we prefer to send more landmarks
        just after successfully relocalization.
    */
    if (server_->server_mode_ == server_mode_t::Localization) {
        server_->get_map_database()->reset_sent_flag_for_all_landmarks();
        last_sent_flag_reset_timestamp_ = msg_timestamp;
    }

    const auto end = std::chrono::system_clock::now();
    elapsed_ms_ = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    spdlog::debug("Relocalization consumes time : {} ms.", elapsed_ms_);
}

/*
    Manually delete the current_keyframe_ which are constructed for
    the relocalization purpose since they aren't added into database.
*/
void ClientHandler::free_current_keyfrm_after_relocalize() {
    if (current_keyframe_) {
        delete current_keyframe_;
        current_keyframe_ = nullptr;
    }
}

template <typename ArrayT>
void ClientHandler::arrayToEigen(Eigen::Matrix4d& dst, const ArrayT& src) const
{
    int srcid = 0;
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j) dst(i, j) = src[srcid++];
}

std::optional<Eigen::Matrix4d> ClientHandler::get_coordinate_transform_matrix() { return coordinate_transform_; }

void ClientHandler::set_coordinate_transform_matrix(const std::optional<Eigen::Matrix4d>& Tww_aligned_ref)
{
    coordinate_transform_ = Tww_aligned_ref;
}

void ClientHandler::unset_coordinate_transform_matrix() { coordinate_transform_.reset(); }

}  // namespace univloc_server
