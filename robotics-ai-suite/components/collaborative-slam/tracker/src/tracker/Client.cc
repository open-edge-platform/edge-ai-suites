// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "Client.h"
#include "camera/perspective.h"
#include "camera/fisheye.h"
#include "timing.h"
#include "data/imu.h"

#include <opencv2/core/eigen.hpp>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/serialization.hpp"
#include "rclcpp/serialized_message.hpp"

#include <spdlog/spdlog.h>

#include <functional>
#include <iostream>
#include <cstdlib>
#include <memory>
#include <time.h>

using namespace cv;

namespace univloc_tracker {

bool kfcomp(Keyframe* kf1, Keyframe* kf2) { return kf1->id_ < kf2->id_; }
bool mpcomp(Landmark* mp1, Landmark* mp2) { return mp1->id_ < mp2->id_; }

Client& Client::get_instance()
{
    static Client instance;
    return instance;
}

void Client::initialize(ConfigConstPtr cfg, Map_database* p_map_db, Camera::base* camera,
          openvslam::data::bow_vocabulary* bow_vocab, openvslam::data::bow_database* bow_db,
          std::shared_ptr<rclcpp::Node> node_ptr)
{
    client_id_ = cfg->client_id_;
    min_keyframes_before_informing_server_ = cfg->min_keyframes_before_informing_server_;
    p_map_db_ = p_map_db;
    camera_ = camera;
    bow_vocab_ = bow_vocab;
    bow_db_ = bow_db;
    node_ptr_ = node_ptr;
    if (cfg->mode_ == "localization" || cfg->mode_ == "relocalization")
        servise_message_mode_ = &Client::process_service_message_localization;
    else
        servise_message_mode_ = &Client::process_service_message;

    timespec ts;
    ts.tv_sec = 0;
    ts.tv_nsec = 0;
    clock_gettime(CLOCK_REALTIME, &ts);
    auto start_id = static_cast<uint64_t>(ts.tv_sec * 1'000'000'000 + ts.tv_nsec);
    auto bits_shift = (sizeof(KeyframeID) - sizeof(ClientID)) * 8;
    start_id = (((uint64_t)client_id_) << bits_shift) | (start_id & ((1ULL << bits_shift) - 1));

    Landmark::initial_start_id(start_id);
    Keyframe::initial_start_id(start_id);

    std::string service_name("server2tracker_");
    service_name += std::to_string(client_id_);
    rmw_qos_profile_t ros_qos = rmw_qos_profile_services_default;
    auto tracker2server_qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(ros_qos), ros_qos);
    if (cfg->force_best_effort_qos_) {
        // Set service message deadline time to 0.5s
        rmw_time_t deadline_t = {0, 500'000'000};
        tracker2server_qos.best_effort().deadline(deadline_t);
    }

    comm_client_ = node_ptr_->create_client<univloc_msgs::MapBasedComm>("tracker2server",
                       tracker2server_qos.get_rmw_qos_profile());
    comm_service_ = node_ptr_->create_service<univloc_msgs::MapBasedComm>(service_name,
                        std::bind(&Client::service_message_callback, this, std::placeholders::_1,
                        std::placeholders::_2));

    spdlog::info("Client {} is initialized!", client_id_);
}

Client::~Client() {}

void Client::connect_server()
{
    if (!comm_client_) {
        spdlog::error("Map message based client is not set on tracker node!");
        return;
    }

    bool loaded_octree_map_sent = false;
    while (running_) {
        while (!comm_client_->wait_for_service(std::chrono::seconds(1))) {
            connected_ = false;
            loaded_octree_map_sent = false;
            spdlog::debug("server is not available, connecting again...");

            if (!running_) {
                spdlog::info("interrupted while connecting to the server node. Exiting.");
                return;
            }
        }

        if (!connected_) {
            univloc_msgs::Map connect_msg;
            connect_msg.connecting_request = true;
            connect_msg.mn_client_id = client_id_;
            connect_msg.msg_id = ++message_id_;
            connect_msg.msg_timestamp = current_server_time();
            send_message(connect_msg);
            spdlog::debug("send connecting request to server node.");

            // Send the pre-constructed Octree map to server if needed
            if (octree_map_msg_ && octree_param_msg_ && !loaded_octree_map_sent) {
                spdlog::info("send loaded octree map to server node in remapping mode.");
                send_loaded_octree_map_msg();
                loaded_octree_map_sent = true;
            }
        }

        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

bool Client::connected() const
{
    return connected_;
}

void Client::receive_relocalization_results(univloc_msgs::MapConstPtr msg)
{
    std::lock_guard<std::mutex> lock(mtx_relocalization_);
    relocalization_results_.push(msg);
}

univloc_msgs::MapConstPtr Client::get_relocalization_results()
{
    std::lock_guard<std::mutex> lock(mtx_relocalization_);
    if (!relocalization_results_.empty()) {
        auto relocalization_result = relocalization_results_.front();
        uint kf_size = relocalization_result->keyframes.size();
        spdlog::debug("keyframe size {}, first id: {}", kf_size, relocalization_result->keyframes[0].mn_id);
        relocalization_results_.pop();
        return relocalization_result;
    } else {
        return NULL;
    }
}

void Client::clear_relocalization_results()
{
    std::lock_guard<std::mutex> lock(mtx_relocalization_);
    relocalization_results_ = {};
}

void Client::update_local_map_from_server(univloc_msgs::MapConstPtr map_msg_ptr)
{
    // For future use if optimization is needed!
    std::lock_guard<std::mutex> lock(openvslam::data::map_database::mtx_database_);

    assert(!map_msg_ptr->only_add_landmarks);

    std::optional<Eigen::Matrix4d> Tww_aligned_ref = std::nullopt;
    if (!map_msg_ptr->keyframe_updates.empty()) {
        if (map_msg_ptr->keyframe_updates.size() > 1) {
            spdlog::warn("There should be only one msg for coordinate transform, please check server implementation!");
        } else {
            Eigen::Matrix4d transform = Eigen::Matrix4d::Identity();
            auto update_keyframe_msg = map_msg_ptr->keyframe_updates[0];
            for (int idx = 0; idx < transform.rows(); ++idx) {
                for (int idy = 0; idy < transform.cols(); ++idy) {
                    transform(idx, idy) = update_keyframe_msg.mv_pose[idx * transform.rows() + idy];
                }
            }
            Tww_aligned_ref = std::make_optional<Eigen::Matrix4d>(transform);
        }
    }

    /*
        During map merge, for the map to be aligned, Tww_aligned_ref is not empty. Therefore, when
        tracker's local map is about to transform coordinate, will skip processing frames in fast mapping.
    */
    if (p_fast_mapping_module_ && Tww_aligned_ref) p_fast_mapping_module_->set_skip_processing_frame(true);

    //! processing keyframe message!
    // using server states to replace local keyframe state
    std::vector<Keyframe*> updated_keyframes;
    KeyframeID max_keyframe_id = 0, updated_keyframes_num = 0,
                 min_keyframe_id = std::numeric_limits<KeyframeID>::max();
    if (map_msg_ptr->keyframes.size() > 0) {
        uint kf_size = map_msg_ptr->keyframes.size();
        assert(kf_size > 0);
        updated_keyframes.resize(kf_size);
        for (uint i = 0; i < kf_size; ++i) {
            updated_keyframes[i] = nullptr;
            auto keyframe_msg = map_msg_ptr->keyframes[i];
            auto p_keyframe = p_map_db_->get_keyframe(keyframe_msg.mn_id);
            if (!p_keyframe) continue;
            Eigen::Matrix4d cam_pose_cw;

            max_keyframe_id = std::max(keyframe_msg.mn_id, max_keyframe_id);
            min_keyframe_id = std::min(keyframe_msg.mn_id, min_keyframe_id);

            for (int idx = 0; idx < cam_pose_cw.rows(); ++idx)
                for (int idy = 0; idy < cam_pose_cw.cols(); ++idy)
                    cam_pose_cw(idx, idy) = keyframe_msg.mv_pose[idx * cam_pose_cw.rows() + idy];
            p_keyframe->cam_pose_wc_before_replacing_ = p_keyframe->get_cam_pose_inv();
            spdlog::debug("Keyframe {} Position Before Replacing: {} {} {}", p_keyframe->id_,
                          p_keyframe->cam_pose_wc_before_replacing_(0, 3),
                          p_keyframe->cam_pose_wc_before_replacing_(1, 3),
                          p_keyframe->cam_pose_wc_before_replacing_(2, 3));

            p_keyframe->set_cam_pose(cam_pose_cw);

            if (openvslam::data::IMU_Preintegration::imu_initialize_times_ > 0) {
                Eigen::Matrix3d rot_correct = p_keyframe->get_rotation().transpose() *
                                              p_keyframe->cam_pose_wc_before_replacing_.block(0, 0, 3, 3).transpose();
                p_keyframe->set_imu_velocity(rot_correct * p_keyframe->get_imu_velocity());
            }

            spdlog::debug("Position After Replacing: {} {} {}", p_keyframe->get_cam_pose_inv()(0, 3),
                          p_keyframe->get_cam_pose_inv()(1, 3), p_keyframe->get_cam_pose_inv()(2, 3));
            p_keyframe->set_update_from_server(true);
            updated_keyframes[i] = p_keyframe;
            updated_keyframes_num++;
        }
    }

    spdlog::debug("received keyframes num from server: {}", map_msg_ptr->keyframes.size());
    spdlog::debug("max_keyframe_id: {}", max_keyframe_id);
    spdlog::debug("updated_keyframes size: {}", updated_keyframes_num);

    assert(updated_keyframes_num > 0);

    int replaced_landmarks_num = 0, updated_lanmarks_num = 0;
    uint mp_size = map_msg_ptr->landmarks.size();
    assert(mp_size > 0);
    std::vector<Landmark*> updated_landmarks;
    for (uint idx = 0; idx < mp_size; ++idx) {
        auto landmark_msg = map_msg_ptr->landmarks[idx];
        auto p_landmark = p_map_db_->get_landmark(landmark_msg.mn_id);
        if (p_landmark) {
            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                  (double)landmark_msg.mv_position[2]);
            p_landmark->set_pos_in_world(pos_w);
            p_landmark->set_update_from_server(true);
            updated_landmarks.push_back(p_landmark);
            p_landmark->update_normal_and_depth();

            updated_lanmarks_num++;
        } else {
            if (landmark_msg.mn_replace_other_id <= 0 && landmark_msg.mn_observed_in_other_keyframe_id <= 0) continue;

            cv::Mat descriptor(1, landmark_msg.mv_descriptors[0].m_descriptor.size(), CV_8UC1,
                               landmark_msg.mv_descriptors[0].m_descriptor.data());

            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                  (double)landmark_msg.mv_position[2]);
            Eigen::Vector3d mean_normal((double)landmark_msg.mv_normal_vector[0],
                                        (double)landmark_msg.mv_normal_vector[1],
                                        (double)landmark_msg.mv_normal_vector[2]);
            auto p_landmark =
                new Landmark(landmark_msg.mn_id, landmark_msg.mn_client_id, pos_w, descriptor,
                             landmark_msg.mf_max_distance, landmark_msg.mf_min_distance, mean_normal, p_map_db_, true);
            p_landmark->set_update_from_server(true);
            p_landmark->update_normal_and_depth();
            updated_landmarks.push_back(p_landmark);
            p_landmark->set_not_new_created();
            // Replace existed landmarks, this will occur after GBA in server
            // Process replaced or new observed landmarks from server
            if (landmark_msg.mn_replace_other_id > 0) {
                auto p_replaced_landmark = p_map_db_->get_landmark(landmark_msg.mn_replace_other_id);
                if (p_replaced_landmark) {
                    p_replaced_landmark->replace(p_landmark);
                    p_landmark->update_normal_and_depth();
                    p_map_db_->add_landmark(p_landmark);
                    replaced_landmarks_num++;
                }
            } else if (landmark_msg.mn_observed_in_other_keyframe_id > 0) {
                // Add observed other landmarks from server
                auto p_keyframe = p_map_db_->get_keyframe(landmark_msg.mn_observed_in_other_keyframe_id);
                if (!p_keyframe) continue;
                p_keyframe->add_landmark(p_landmark, landmark_msg.mn_observed_in_other_keyframe_index);
                p_map_db_->add_landmark(p_landmark);
                p_landmark->add_observation(p_keyframe, landmark_msg.mn_observed_in_other_keyframe_index);
                p_landmark->update_normal_and_depth();
            }
        }
    }

    spdlog::info("updated_landmarks_num: {}", updated_lanmarks_num);
    spdlog::info("replaced_landmarks_num: {}", replaced_landmarks_num);

    // propgate to update other keyframe pose
    spdlog::info("min updated keyframe id: {}", min_keyframe_id);
    spdlog::info("max updated keyframe id: {}", max_keyframe_id);

    if (max_keyframe_id != 0) {
        Keyframe* newest_update_frame = p_map_db_->get_keyframe(max_keyframe_id);
        int aligned_keyframe_num = 0;
        auto keyframes = p_map_db_->get_all_keyframes();
        for (auto p_keyframe : keyframes) {
            if (p_keyframe->is_update_from_server()) continue;
            auto pose_now = p_keyframe->get_cam_pose();
            p_keyframe->cam_pose_wc_before_replacing_ = p_keyframe->get_cam_pose_inv();
            p_keyframe->set_cam_pose(pose_now * newest_update_frame->cam_pose_wc_before_replacing_ *
                                     newest_update_frame->get_cam_pose());

            if (openvslam::data::IMU_Preintegration::imu_initialize_times_ > 0) {
                Eigen::Matrix3d rot_correct =
                    newest_update_frame->get_rotation().transpose() *
                    newest_update_frame->cam_pose_wc_before_replacing_.block(0, 0, 3, 3).transpose();
                p_keyframe->set_imu_velocity(rot_correct * p_keyframe->get_imu_velocity());
            }

            spdlog::debug("Keyframe {} Position Before Aligning: {} {} {}", p_keyframe->id_,
                          p_keyframe->cam_pose_wc_before_replacing_(0, 3),
                          p_keyframe->cam_pose_wc_before_replacing_(1, 3),
                          p_keyframe->cam_pose_wc_before_replacing_(2, 3));
            spdlog::debug("Position After Aligning: {} {} {}", p_keyframe->get_cam_pose_inv()(0, 3),
                          p_keyframe->get_cam_pose_inv()(1, 3), p_keyframe->get_cam_pose_inv()(2, 3));
            aligned_keyframe_num++;
        }
        spdlog::info("aligned  keyframes_num: {}", aligned_keyframe_num);

        int aligned_landmarks_num = 0;
        auto landmarks = p_map_db_->get_all_landmarks();

        for (auto& lm : landmarks) {
            if (!lm || lm->will_be_erased()) continue;

            if (!lm->is_update_from_server()) {
                auto ref_keyframe = lm->get_ref_keyframe();
                if (ref_keyframe) {
                    auto T_cw = ref_keyframe->cam_pose_wc_before_replacing_.inverse();
                    auto pos_in_ref =
                        (T_cw.block(0, 0, 3, 3) * lm->get_pos_in_world() + T_cw.block(0, 3, 3, 1)).homogeneous();
                    auto current_T_wc = ref_keyframe->get_cam_pose_inv();
                    lm->set_pos_in_world(
                        (current_T_wc.block(0, 0, 3, 3) * pos_in_ref + current_T_wc.block(0, 3, 3, 1)));
                    lm->update_normal_and_depth();

                    aligned_landmarks_num++;
                }
            }
        }
        spdlog::info("aligned_landmarks_num: {}", aligned_landmarks_num);
    }

    // After updating, reset the update_from_server flag
    for (auto& item : updated_keyframes) {
        if (item) item->set_update_from_server(false);
    }
    for (auto& item : updated_landmarks) {
        if (item) item->set_update_from_server(false);
    }

    // Update octree with the new keyframes
    /*
       Temporarily disable tracker updating its local octree using optimized keyframes and coordinate transform
       because slight change of position after updating can cause the node to fall into a nearby region which
       will lead to a diverged occupancy map. A better way would be to split into smallest voxels and do correction
       TODO for map merge case, better to do on server side; for loop correction case, ok to do on tracker side
    if (p_fast_mapping_module_) {
        p_fast_mapping_module_->set_coordinate_transform_matrix(Tww_aligned_ref);
        p_fast_mapping_module_->update_octree_from_server(updated_keyframes);
    }
    */

    // in the case of map merge, after tracker's map merged with global map, the coordinate is aligned
    if (!map_msg_ptr->loop_closure) {
        dynamic_cast<openvslam::univloc_tracking_module*>(p_tracking_module_)->set_coordinate_aligned(true);
    }
}

void Client::set_latest_keyfrm_local_id(KeyframeID id) {
    latest_keyfrm_localization_id_ = id;
}

void Client::process_received_server_landmarks(KeyframeID id) {
    std::lock_guard<std::mutex> lock(received_msgs_mtx_);
    univloc_msgs::MapConstPtr map_msg_ptr;
    KeyframeID start_id = latest_keyfrm_localization_id_;
    while (start_id < id && received_map_msgs_.size() > 0) {
        if (received_map_msgs_.find(start_id) == received_map_msgs_.end()) {
            start_id++;
            continue;
        }
        map_msg_ptr = received_map_msgs_[start_id];
        update_server_landmarks(map_msg_ptr);
        received_map_msgs_.erase(start_id);
        latest_keyfrm_localization_id_ = start_id;
        start_id++;
    }
    spdlog::debug("Requested ID {} : Returned ID {} : last returned ID {}", id, start_id, latest_keyfrm_localization_id_);
}

void Client::update_server_landmarks(univloc_msgs::MapConstPtr map_msg_ptr)
{
    int new_added_server_landmarks_num = 0, updated_server_landmarks_num = 0;

    uint32_t lms_size = map_msg_ptr->landmarks.size();
    for (uint idx = 0; idx < lms_size; ++idx) {
        auto landmark_msg = map_msg_ptr->landmarks[idx];
        if (!map_msg_ptr->only_add_landmarks &&
            (landmark_msg.mn_observed_in_other_keyframe_id > 0 || landmark_msg.mn_replace_other_id > 0))
            continue;
        // if this landmark existed in the map database, it can't be treated as a server landmark
        if (p_map_db_->get_landmark(landmark_msg.mn_id)) continue;

        std::shared_ptr<Landmark> ptr_server_landmark = p_map_db_->get_server_landmark(landmark_msg.mn_id);
        if (ptr_server_landmark) {
            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                    (double)landmark_msg.mv_position[2]);
            ptr_server_landmark->set_existed_in_server_map(true);
            ptr_server_landmark->set_pos_in_world(pos_w);
            ptr_server_landmark->set_not_new_created();
            updated_server_landmarks_num++;

            // if the server landmark is in the fov, it should not be deleted
            ptr_server_landmark->out_of_local_map_times_ = 0;

            // TODO : update descriptor, may no need.
        } else {
            cv::Mat descriptor(1, landmark_msg.mv_descriptors[0].m_descriptor.size(), CV_8UC1,
                                landmark_msg.mv_descriptors[0].m_descriptor.data());

            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                    (double)landmark_msg.mv_position[2]);
            Eigen::Vector3d mean_normal((double)landmark_msg.mv_normal_vector[0],
                                        (double)landmark_msg.mv_normal_vector[1],
                                        (double)landmark_msg.mv_normal_vector[2]);
            ptr_server_landmark = std::make_shared<Landmark>(
                landmark_msg.mn_id, landmark_msg.mn_client_id, pos_w, descriptor, landmark_msg.mf_max_distance,
                landmark_msg.mf_min_distance, mean_normal, p_map_db_, true);
            ptr_server_landmark->set_not_new_created();
            ptr_server_landmark->set_existed_in_server_map(true);

            auto lm_desc = ptr_server_landmark->get_descriptor();

            if (!lm_desc.ptr<uint32_t>()) {
                spdlog::debug(
                    "Invalid descriptor of this new created landmark, so we will not add it into the map "
                    "database!");
                continue;
            }

            p_map_db_->add_server_landmark(ptr_server_landmark);
            new_added_server_landmarks_num++;
        }
    }

    p_map_db_->remove_to_be_erased_server_landmarks();

    p_map_db_->update_server_landmarks_vec();

    if (p_map_db_->get_num_keyframes() > 0) create_virtual_server_keyframe();

    spdlog::debug("new added server landmarks_num: {}", new_added_server_landmarks_num);
    spdlog::debug("updated_server_landmarks_num: {}", updated_server_landmarks_num);
}

void Client::create_virtual_server_keyframe()
{
    spdlog::debug("Start creating virtual keyframe!");

    const static unsigned int min_lms_num = 200;

    auto server_landmarks = p_map_db_->get_server_landmarks();

    if (server_landmarks.size() < min_lms_num) {
        spdlog::debug("Too few server landmarks for creating virtual server keyframe!");
        p_map_db_->update_server_virtual_keyframe(nullptr);
        return;
    }

    std::vector<cv::KeyPoint> keypts, undist_keypts;

    size_t num_keypts = server_landmarks.size();

    std::vector<float> stereo_x_right(num_keypts, 0), depths(num_keypts, 0);

    std::vector<Landmark*> lm_vec(num_keypts, nullptr);
    cv::Mat descriptors(num_keypts, 32, CV_8U);
    openvslam::eigen_alloc_vector<Eigen::Vector3d> bearings;
    bearings.resize(num_keypts);

    auto newest_keyframe = p_map_db_->get_keyframe(p_map_db_->get_max_keyframe_id());
    if (!newest_keyframe) {
        spdlog::info("Failed to get the newest keyframe from map database!");
        return;
    }

    auto camera_pose = newest_keyframe->get_cam_pose();

    unsigned int idx = 0;
    for (auto lm : server_landmarks) {
        descriptors.row(idx) = lm->get_descriptor();
        Eigen::Vector3d lm_in_camera =
            camera_pose.block(0, 0, 3, 3) * lm->get_pos_in_world() + camera_pose.block(0, 3, 3, 1);

        // It should not judge whether in front of camera, beacuse the pose is not accuracy enough.
        // whether the server landmarks in virtual keyframe should be judge in the server
        lm_vec[idx] = lm.get();
        lm_in_camera = lm_in_camera / lm_in_camera[2];
        bearings[idx] = lm_in_camera / lm_in_camera.head(2).norm();

        idx++;
    }

    Keyframe* server_virtual_keyframe =
        new Keyframe(0, 0, newest_keyframe->timestamp_, camera_pose, newest_keyframe->camera_,
                     newest_keyframe->depth_thr_, num_keypts, keypts, undist_keypts, bearings, stereo_x_right, depths,
                     descriptors, newest_keyframe->num_scale_levels_, newest_keyframe->scale_factor_, bow_vocab_, bow_db_, p_map_db_);

    for (unsigned int i = 0; i < num_keypts; i++) {
        if (lm_vec[i]) {
            server_virtual_keyframe->add_landmark(lm_vec[i], i);
            lm_vec[i]->add_observation(server_virtual_keyframe, i);
        }
    }

    if (p_map_db_->get_server_virtual_keyframe())
        p_map_db_->get_server_virtual_keyframe()->prepare_for_erasing(true, true);

    p_map_db_->update_server_virtual_keyframe(server_virtual_keyframe);
}

void Client::process_service_message(univloc_msgs::MapConstPtr map_msg_ptr)
{
    auto start = now();
    uint8_t msg_client_id = map_msg_ptr->mn_client_id;

    if (msg_client_id != client_id_) return;

    if (unlikely(map_msg_ptr->connecting_request)) {
        connected_ = true;
        spdlog::info("tracker establish bi-directional communication with server successfully");
        return;
    }

    spdlog::debug("map_msg_ptr->session_start_time: {},session_start_time_ : {} ", map_msg_ptr->session_start_time,
                 session_start_time_);
    if (std::abs(map_msg_ptr->session_start_time - session_start_time_) > 0.00001 &&
        !map_msg_ptr->is_relocalization_result) {
        if (!map_msg_ptr->only_add_landmarks) {
            merge_times_++;
            assert(map_msg_ptr->merge_times == merge_times_);
        }
        return;
    }

    // Push message to the fast mapping queue - might contain an octree request or merged octree!
    if (p_fast_mapping_module_) {
        if (map_msg_ptr->is_request_octree || map_msg_ptr->is_merged_octree) {
            p_fast_mapping_module_->queue_map_message(map_msg_ptr);
        }
    }

    if (map_msg_ptr->is_relocalization_result) {
        spdlog::debug("Received relocalization message from server!");
        receive_relocalization_results(map_msg_ptr);
    } else {
        if (!map_msg_ptr->only_add_landmarks) {
            merge_times_++;
            assert(map_msg_ptr->merge_times == merge_times_);
            // This message is used to replace all the local map status, so we need to pause the local mapping
            // module
            spdlog::debug("This message is for updating all local map! merge_times: {}", merge_times_);
            // Pause the mapping module
            p_mapping_module_->request_pause();
            request_pause_sending_msg();
            while (!p_mapping_module_->is_paused() || !sending_msg_is_paused()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            update_local_map_from_server(map_msg_ptr);
            // resume the mapping module and sending map
            resume_sending_msg();
            p_mapping_module_->resume(false);  // false means not clearing the stored database queue
        } else
            spdlog::debug("This message is for adding visible server map!");

        std::lock_guard<std::mutex> lock(openvslam::data::map_database::mtx_database_);
        update_server_landmarks(map_msg_ptr);

        spdlog::debug("local_server_landmarks_size : {} .", p_map_db_->get_server_landmarks().size());
    }

    auto end = now();
    spdlog::debug("Processing msg from server consumes time : {} ms.", duration_ms(start, end));
}

void Client::process_service_message_localization(univloc_msgs::MapConstPtr map_msg_ptr) {

    auto start = now();
    uint8_t msg_client_id = map_msg_ptr->mn_client_id;

    if (msg_client_id != client_id_) return;

    if (unlikely(map_msg_ptr->connecting_request)) {
        connected_ = true;
        spdlog::info("tracker establish bi-directional communication with server successfully");
        return;
    }

    if (map_msg_ptr->is_relocalization_result) {
        spdlog::debug("Received relocalization message from server!");
        receive_relocalization_results(map_msg_ptr);
    } else {
        std::lock_guard<std::mutex> lock(received_msgs_mtx_);
        spdlog::debug("Received ID {}", map_msg_ptr->frame_id);
        received_map_msgs_[map_msg_ptr->frame_id] = map_msg_ptr;

        spdlog::debug("local_server_landmarks_size : {} .", p_map_db_->get_server_landmarks().size());
    }

    auto end = now();
    spdlog::debug("Processing msg from server consumes time : {} ms.", duration_ms(start, end));
}

void Client::convert_erased_id_to_msg(std::vector<KeyframeID>& keyframes, std::vector<LandmarkID>& landmarks,
                                      univloc_msgs::Map& msg_out)
{
    uint erased_kf_size = keyframes.size(), erased_ld_size = landmarks.size();
    spdlog::debug("erased keyframe size: {}; erased landmark size: {}", erased_kf_size, erased_ld_size);
    msg_out.erase_keyframes_id.resize(erased_kf_size);
    for (uint i = 0; i < erased_kf_size; i++) {
        msg_out.erase_keyframes_id[i] = static_cast<KeyframeID>(keyframes[i]);
    }

    msg_out.erase_landmarks_id.resize(erased_ld_size);
    for (uint i = 0; i < erased_ld_size; i++) {
        msg_out.erase_landmarks_id[i] = static_cast<LandmarkID>(landmarks[i]);
    }
}

void Client::convert_landmarks_to_msg(const std::vector<Landmark*>& landmarks_out, univloc_msgs::Map& msg_out)
{
    auto start = now();

    Landmark* p_cur_landmark = nullptr;
    uint size = landmarks_out.size();
    spdlog::debug("start convert landmarks size: {}", size);

    for (uint i = 0; i < size; i++) {
        univloc_msgs::Landmark landmark_msg;
        p_cur_landmark = landmarks_out[i];
        if (!p_cur_landmark) continue;

        if (p_cur_landmark->being_sliding_out_ || p_cur_landmark->will_be_erased()) continue;
        landmark_msg.mn_id = p_cur_landmark->id_;
        landmark_msg.mn_client_id = client_id_;

        landmark_msg.mn_replace_other_id = p_cur_landmark->replace_other_id_;
        p_cur_landmark->replace_other_id_ = 0;

        auto position_in_world = p_cur_landmark->get_pos_in_world();
        landmark_msg.mv_position[0] = (float)position_in_world[0];
        landmark_msg.mv_position[1] = (float)position_in_world[1];
        landmark_msg.mv_position[2] = (float)position_in_world[2];

        Keyframe* ref_keyframe = p_cur_landmark->get_ref_keyframe();
        if (!ref_keyframe) {
            spdlog::debug("This landmark {} has no reference keyframe: ", p_cur_landmark->id_);
            continue;
        }

        landmark_msg.mn_refer_keyframe_id = ref_keyframe->id_;

        std::map<Keyframe*, unsigned int> observations = p_cur_landmark->get_observations();
        for (std::map<Keyframe*, unsigned int>::const_iterator mit = observations.begin(); mit != observations.end();
             mit++) {
            landmark_msg.mv_observation_keyframe_ids.push_back(mit->first->id_);
            landmark_msg.mv_observations_n.push_back(mit->second);
        }

        msg_out.landmarks.emplace_back(std::move(landmark_msg));
    }

    auto finish = now();
    spdlog::debug("really converted landmarks size is {}", msg_out.landmarks.size());
    spdlog::debug("Converting landmarks consumes time : {} ms", duration_ms(start, finish));
}

void Client::convert_keyframes_to_msg(const std::vector<Keyframe*>& keyframes_out, univloc_msgs::Map& msg_out)
{
    auto start = now();
    Keyframe* cur_keyframe;
    uint size = keyframes_out.size();

    auto cv_keypoint_to_msg = [](const cv::KeyPoint& kp) {
        univloc_msgs::CvKeypoint msg;
        msg.fpoint2fx = kp.pt.x;
        msg.fpoint2fy = kp.pt.y;
        msg.angle = kp.angle;
        msg.octave = kp.octave;
        msg.response = (u_int8_t)kp.response;
        msg.size = (u_int8_t)kp.size;
        return msg;
    };

    spdlog::debug("start convert keyframes size {}", size);
    for (uint i = 0; i < size; i++) {
        univloc_msgs::Keyframe keyframe_msg;
        univloc_msgs::KeyframeUpdate keyframe_update_msg;

        cur_keyframe = keyframes_out[i];
        if (!cur_keyframe) continue;
        if (cur_keyframe->being_sliding_out_) continue;
        if (cur_keyframe->is_origin()) {
            session_start_time_ = cur_keyframe->timestamp_;
        }

        assert(!cur_keyframe->will_be_erased());
        if (!cur_keyframe->is_new_created()) {
            if (cur_keyframe->graph_node_->get_spanning_parent()) {
                keyframe_update_msg.mn_parent_id =
                    cur_keyframe->graph_node_->get_spanning_parent()->id_;
            }
            keyframe_update_msg.mn_id = cur_keyframe->id_;
            auto pose = cur_keyframe->get_cam_pose();
            for (int idx = 0; idx < pose.rows(); ++idx)
                for (int idy = 0; idy < pose.cols(); ++idy)
                    keyframe_update_msg.mv_pose[idx * pose.rows() + idy] = pose(idx, idy);
            auto children = cur_keyframe->graph_node_->get_spanning_children();
            for (const auto& child : children) {
                if (child) {
                    keyframe_update_msg.mv_children_ids.push_back(child->id_);
                }
            }
            msg_out.keyframe_updates.emplace_back(std::move(keyframe_update_msg));
            continue;
        }

        cur_keyframe->set_not_new_created();
        keyframe_msg.mn_id = cur_keyframe->id_;
        keyframe_msg.mn_client_id = client_id_;
        keyframe_msg.mb_bad_imu_to_reset = cur_keyframe->bad_imu_to_reset_;

        if (cur_keyframe->graph_node_->get_spanning_parent()) {
            keyframe_msg.mn_parent_id = cur_keyframe->graph_node_->get_spanning_parent()->id_;
        }

        auto children = cur_keyframe->graph_node_->get_spanning_children();
        for (const auto& child : children) {
            if (child) {
                keyframe_msg.mv_children_ids.push_back(child->id_);
            }
        }

        auto pose = cur_keyframe->get_cam_pose();
        for (int idx = 0; idx < pose.rows(); ++idx)
            for (int idy = 0; idy < pose.cols(); ++idy)
                keyframe_msg.mv_pose[idx * pose.rows() + idy] = pose(idx, idy);

        keyframe_msg.mf_depth_thr = cur_keyframe->depth_thr_;

        keyframe_msg.mn_num_keypoints = cur_keyframe->num_keypts_;
        keyframe_msg.md_timestamp = cur_keyframe->timestamp_;

        for (uint idx = 0; idx < cur_keyframe->undist_keypts_.size(); ++idx) {
            keyframe_msg.mv_keypoints.push_back(cv_keypoint_to_msg(cur_keyframe->keypts_[idx]));
        }
        int descriptors_num = cur_keyframe->descriptors_.rows;
        int descriptors_cols = cur_keyframe->descriptors_.cols;

        for (int idx = 0; idx < descriptors_num; ++idx) {
            univloc_msgs::Descriptor MsgDesc;
            if (descriptors_cols != MsgDesc.m_descriptor.size()) {
                spdlog::warn("descriptor {} of keyframe {} has wrong size {}", idx, cur_keyframe->id_,
                             descriptors_cols);
                continue;
            }
            memcpy(MsgDesc.m_descriptor.data(), cur_keyframe->descriptors_.ptr(idx), descriptors_cols);
            keyframe_msg.mv_descriptors.push_back(MsgDesc);
        }

        keyframe_msg.mn_scale_levels = static_cast<int8_t>(cur_keyframe->num_scale_levels_);
        keyframe_msg.mf_scale_factor = cur_keyframe->scale_factor_;
        keyframe_msg.mf_log_scale_factor = cur_keyframe->log_scale_factor_;
        uint stereo_x_right_size = cur_keyframe->stereo_x_right_.size();
        keyframe_msg.mv_stereo_x_right.resize(stereo_x_right_size);
        for (uint idx = 0; idx < stereo_x_right_size; ++idx)
            keyframe_msg.mv_stereo_x_right[idx] = cur_keyframe->stereo_x_right_[idx];

        msg_out.keyframes.emplace_back(std::move(keyframe_msg));
    }

    auto finish = now();
    spdlog::debug("really convert keyframes size {}", msg_out.keyframes.size());
    spdlog::debug("Converting keyframes to msg consumes {} ms.", duration_ms(start, finish));
}

void Client::request_pause_sending_msg()
{
    std::unique_lock<std::mutex> lock_pause_sending(request_pause_sending_mtx_);
    request_pause_sending_msg_ = true;
}
void Client::resume_sending_msg()
{
    std::unique_lock<std::mutex> lock_pause_sending(request_pause_sending_mtx_);
    request_pause_sending_msg_ = false;
}

ClientID Client::get_client_id() const { return client_id_; }

void Client::increase_merge_times() { merge_times_++; }

void Client::queue_send_map(const std::vector<Landmark*>& landmarks, const std::vector<Keyframe*>& keyframes,
                            const std::vector<LandmarkID>& landmarks_id,
                            const std::vector<KeyframeID>& keyframes_id)
{
    std::unique_lock<std::mutex> lock(sent_map_queue_mtx_);
    landmarks_to_be_sent_.push(landmarks);
    keyframes_to_be_sent_.push(keyframes);
    erased_landmarks_id_.push(landmarks_id);
    erased_keyframes_id_.push(keyframes_id);
}

bool Client::sending_msg_is_paused() const
{
    std::unique_lock<std::mutex> lock_pause_sending(request_pause_sending_mtx_);
    return sending_msg_paused_;
}

void Client::get_server_landmarks_using_current_pose(Eigen::Matrix4d curr_pose, KeyframeID curr_id,
                                                     unsigned int relocal_map_id)
{
    // just send current pose to the server
    std::this_thread::sleep_for(std::chrono::milliseconds(5));

    // may need to wait
    if (unlikely(!connected_)) return;

    auto start = now();

    // std::vector<Keyframe*> sent_keyframes;
    // sent_keyframes.push_back(keyfrm_to_be_relocalized);

    univloc_msgs::Map get_server_landmarks_msg;
    univloc_msgs::Keyframe keyframe_msg;
    keyframe_msg.mn_localize_map_id = relocal_map_id;
    for (int idx = 0; idx < curr_pose.rows(); ++idx)
        for (int idy = 0; idy < curr_pose.cols(); ++idy)
            keyframe_msg.mv_pose[idx * curr_pose.rows() + idy] = curr_pose(idx, idy);
    get_server_landmarks_msg.keyframes.emplace_back(std::move(keyframe_msg));

    get_server_landmarks_msg.need_relocalization = false;
    get_server_landmarks_msg.is_request_for_server_landmarks = true;
    get_server_landmarks_msg.is_tracker_octree = false;
    get_server_landmarks_msg.mn_client_id = client_id_;
    get_server_landmarks_msg.msg_id = ++message_id_;
    get_server_landmarks_msg.msg_timestamp = current_server_time();
    get_server_landmarks_msg.session_start_time = session_start_time_;
    get_server_landmarks_msg.merge_times = merge_times_;
    get_server_landmarks_msg.frame_id = curr_id;
    spdlog::debug("Send request of server landmarks for frame {}", curr_id);

    send_message(get_server_landmarks_msg);

    auto end = now();

    spdlog::debug("Send current pose to server cost time: {} ms ", duration_ms(end - start));
}

void Client::send_relocalization_request_to_server(Keyframe* keyfrm_to_be_relocalized)
{
    assert(keyfrm_to_be_relocalized);
    std::this_thread::sleep_for(std::chrono::milliseconds(5));

    // may need to wait
    if (!connected_) return;

    auto start = now();

    spdlog::debug("Send relocalization single keyframe to server!");

    univloc_msgs::Map request_relocalization_msg;
    std::vector<Keyframe*> sent_keyframes;
    sent_keyframes.push_back(keyfrm_to_be_relocalized);
    convert_keyframes_to_msg(sent_keyframes, request_relocalization_msg);

    request_relocalization_msg.need_relocalization = true;
    request_relocalization_msg.is_request_for_server_landmarks = false;
    request_relocalization_msg.is_tracker_octree = false;
    request_relocalization_msg.mn_client_id = client_id_;
    request_relocalization_msg.msg_id = ++message_id_;
    request_relocalization_msg.msg_timestamp = current_server_time();
    request_relocalization_msg.session_start_time = session_start_time_;
    request_relocalization_msg.merge_times = merge_times_;

    send_message(request_relocalization_msg);

    auto end = now();

    spdlog::debug("Send relocalization single keyframe to server cost time: {} ms ", duration_ms(end - start));
}

void Client::send_octree_to_server(univloc_msgs::Octree& octree_msg)
{
    // may need to wait
    if (unlikely(!connected_)) {
        spdlog::error("Client disconnected, please debug");
        return;
    }

    spdlog::info("Send octree from client {} to server!", client_id_);

    auto start = now();

    univloc_msgs::Map send_octree_msg;
    send_octree_msg.need_relocalization = false;
    send_octree_msg.is_request_for_server_landmarks = false;
    send_octree_msg.is_tracker_octree = true;
    send_octree_msg.mn_client_id = client_id_;
    send_octree_msg.msg_id = ++message_id_;
    send_octree_msg.msg_timestamp = current_server_time();
    send_octree_msg.session_start_time = session_start_time_;
    send_octree_msg.merge_times = merge_times_;

    univloc_msgs::OctreeParamPtr octree_param_msg = std::make_shared<univloc_msgs::OctreeParam>();

    // camera intrinsics for Octree usage
    auto intrinsics = p_fast_mapping_module_->get_camera_intrinsics();
    octree_param_msg->width = intrinsics.width;
    octree_param_msg->height = intrinsics.height;
    octree_param_msg->cx = intrinsics.cx;
    octree_param_msg->cy = intrinsics.cy;
    octree_param_msg->fx = intrinsics.fx;
    octree_param_msg->fy = intrinsics.fy;

    // Octree configuration
    auto octree_cfg = p_fast_mapping_module_->get_octree_cfg();
    octree_param_msg->compute_size_ratio = octree_cfg.compute_size_ratio;
    octree_param_msg->voxel_per_side = octree_cfg.voxel_per_side;
    octree_param_msg->volume_size_meter = octree_cfg.volume_size_meter;
    octree_param_msg->noise_factor = octree_cfg.noise_factor;
    octree_param_msg->logodds_lower = octree_cfg.logodds_lower;
    octree_param_msg->logodds_upper = octree_cfg.logodds_upper;
    octree_param_msg->zmin = octree_cfg.zmin;
    octree_param_msg->zmax = octree_cfg.zmax;
    octree_param_msg->depth_max_range = octree_cfg.depth_max_range;
    octree_param_msg->correction_threshold = octree_cfg.correction_threshold;

    send_octree_msg.octree_param.emplace_back(*octree_param_msg);
    send_octree_msg.octree.push_back(std::move(octree_msg));
    send_message(send_octree_msg);

    auto end = now();
    spdlog::debug("Send octree to server cost time: {} ms ", duration_ms(start, end));
}

void Client::terminate() { running_ = false; }

void Client::run()
{
    running_ = true;
    static bool camera_info_sent = false;

    connecting_thread_ = std::make_unique<std::thread>(&Client::connect_server, &get_instance());

    while (running_) {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        if (unlikely(!running_))
            break;

        {
            std::unique_lock<std::mutex> lock_pause_sending(request_pause_sending_mtx_);
            sending_msg_paused_ = request_pause_sending_msg_;
            if (unlikely(sending_msg_paused_)) {
                continue;
            }
        }

        if (unlikely(!connected_)) {
            camera_info_sent = false;
            continue;
        }

        // Tell the server I exist and send the camera information meanswhile! only used
        // for recording message bag.
        if (camera_ && !camera_info_sent) {
            send_camera_info_msg();
            camera_info_sent = true;
        }

        // Do not send if there is only 1 keyframe in the database, otherwise there will
        // be frequent messages
        int num_total_keyframes = p_map_db_->get_num_keyframes();
        if (num_total_keyframes <= min_keyframes_before_informing_server_) {
            continue;
        }

        while (!keyframes_to_be_sent_.empty()) {
            auto start = now();

            std::unique_lock<std::mutex> lock(sent_map_queue_mtx_);

            auto sent_keyframes = keyframes_to_be_sent_.front();
            auto sent_landmarks = landmarks_to_be_sent_.front();
            auto sent_erased_landmarks_id = erased_landmarks_id_.front();
            auto sent_erased_keyframes_id = erased_keyframes_id_.front();
            keyframes_to_be_sent_.pop();
            landmarks_to_be_sent_.pop();
            erased_keyframes_id_.pop();
            erased_landmarks_id_.pop();

            // TODO: sending multiple msgs at a time
            /*std::vector<Keyframe*> sent_keyframes;
            std::vector<Landmark*> sent_landmarks;
            std::vector<unsigned int> sent_erased_landmarks_id;
            std::vector<unsigned int> sent_erased_keyframes_id;
            merge_to_be_sent_map(sent_keyframes, sent_landmarks, sent_erased_landmarks_id,
                                 sent_erased_keyframes_id);*/

            lock.unlock();
            univloc_msgs::Map global_optimization_msg;
            convert_keyframes_to_msg(sent_keyframes, global_optimization_msg);
            convert_landmarks_to_msg(sent_landmarks, global_optimization_msg);
            convert_erased_id_to_msg(sent_erased_keyframes_id, sent_erased_landmarks_id, global_optimization_msg);

            global_optimization_msg.need_relocalization = false;
            global_optimization_msg.is_request_for_server_landmarks = false;
            global_optimization_msg.is_tracker_octree = false;
            global_optimization_msg.mn_client_id = client_id_;
            global_optimization_msg.msg_id = ++message_id_;
            global_optimization_msg.msg_timestamp = current_server_time();
            global_optimization_msg.session_start_time = session_start_time_;
            global_optimization_msg.merge_times = merge_times_;
            send_message(global_optimization_msg);
            auto end = now();
            spdlog::debug("Sending {}th msg cost time {} ms", message_id_, duration_ms(end - start));
        }
    }
    connecting_thread_->join();
    spdlog::debug("connecting to server thread exited");
}

void Client::send_camera_info_msg()
{
    univloc_msgs::CameraInfo camerainfo_msg;
    univloc_msgs::Map map_camerainfo_msg;
    map_camerainfo_msg.send_camera_info = true;
    map_camerainfo_msg.mn_client_id = client_id_;

    if (camera_->model_type_ == Camera::model_type_t::Perspective) {
        Camera::perspective* perspective_camera = dynamic_cast<Camera::perspective*>(camera_);
        camerainfo_msg.camera_typename = perspective_camera->name_;
        camerainfo_msg.fx = perspective_camera->fx_;
        camerainfo_msg.fy = perspective_camera->fy_;
        camerainfo_msg.cx = perspective_camera->cx_;
        camerainfo_msg.cy = perspective_camera->cy_;
        camerainfo_msg.k1 = perspective_camera->k1_;
        camerainfo_msg.k2 = perspective_camera->k2_;
        camerainfo_msg.k3 = perspective_camera->k3_;
        camerainfo_msg.p1 = perspective_camera->p1_;
        camerainfo_msg.p2 = perspective_camera->p2_;
        camerainfo_msg.fps = perspective_camera->fps_;
        camerainfo_msg.cols = perspective_camera->cols_;
        camerainfo_msg.rows = perspective_camera->rows_;
        camerainfo_msg.focal_x_baseline = perspective_camera->focal_x_baseline_;
        camerainfo_msg.setup_type = static_cast<int>(perspective_camera->setup_type_);
        camerainfo_msg.color_order = static_cast<int>(perspective_camera->color_order_);
        camerainfo_msg.model_type = static_cast<int>(camera_->model_type_);
    } else if (camera_->model_type_ == Camera::model_type_t::Fisheye) {
        Camera::fisheye* fisheye_camera = dynamic_cast<Camera::fisheye*>(camera_);
        camerainfo_msg.camera_typename = fisheye_camera->name_;
        camerainfo_msg.fx = fisheye_camera->fx_;
        camerainfo_msg.fy = fisheye_camera->fy_;
        camerainfo_msg.cx = fisheye_camera->cx_;
        camerainfo_msg.cy = fisheye_camera->cy_;
        camerainfo_msg.k1 = fisheye_camera->k1_;
        camerainfo_msg.k2 = fisheye_camera->k2_;
        camerainfo_msg.p1 = fisheye_camera->k3_;
        camerainfo_msg.p2 = fisheye_camera->k4_;
        camerainfo_msg.fps = fisheye_camera->fps_;
        camerainfo_msg.cols = fisheye_camera->cols_;
        camerainfo_msg.rows = fisheye_camera->rows_;
        camerainfo_msg.focal_x_baseline = fisheye_camera->focal_x_baseline_;
        camerainfo_msg.setup_type = static_cast<int>(fisheye_camera->setup_type_);
        camerainfo_msg.color_order = static_cast<int>(fisheye_camera->color_order_);
        camerainfo_msg.model_type = static_cast<int>(camera_->model_type_);
    }

    map_camerainfo_msg.camera_info.emplace_back(std::move(camerainfo_msg));
    map_camerainfo_msg.msg_timestamp = current_server_time();
    send_message(map_camerainfo_msg);
}

void Client::send_loaded_octree_map_msg()
{
    univloc_msgs::Map loaded_octree_map_msg;

    loaded_octree_map_msg.is_octree_map_loaded = true;
    loaded_octree_map_msg.mn_client_id = client_id_;
    loaded_octree_map_msg.msg_id = ++message_id_;
    loaded_octree_map_msg.msg_timestamp = current_server_time();
    loaded_octree_map_msg.octree_param.emplace_back(*octree_param_msg_);
    loaded_octree_map_msg.octree.emplace_back(*octree_map_msg_);

    send_message(loaded_octree_map_msg);
}

void Client::merge_to_be_sent_map(std::vector<Keyframe*>& sent_keyframes, std::vector<Landmark*>& sent_landmarks,
                                  std::vector<LandmarkID>& sent_erased_landmarks_id,
                                  std::vector<KeyframeID>& sent_erased_keyframes_id)
{
    assert(keyframes_to_be_sent_.size() > 0);
    if (keyframes_to_be_sent_.size() == 1) {
        sent_keyframes = keyframes_to_be_sent_.front();
        sent_landmarks = landmarks_to_be_sent_.front();
        sent_erased_landmarks_id = erased_landmarks_id_.front();
        sent_erased_keyframes_id = erased_keyframes_id_.front();
        keyframes_to_be_sent_.pop();
        landmarks_to_be_sent_.pop();
        erased_keyframes_id_.pop();
        erased_landmarks_id_.pop();
        return;
    } else {
        spdlog::debug("Sent {} msgs at one time", keyframes_to_be_sent_.size());
        // TODO: use unordered map
        std::set<LandmarkID> erased_landmarks_id_set;
        std::set<KeyframeID> erased_keyframes_id_set;

        bool (*kf_cm)(Keyframe*, Keyframe*) = kfcomp;
        std::set<Keyframe*, bool (*)(Keyframe*, Keyframe*)> keyframes_set(kf_cm);

        bool (*mp_cm)(Landmark*, Landmark*) = mpcomp;
        std::set<Landmark*, bool (*)(Landmark*, Landmark*)> landmarks_set(mp_cm);

        while (!keyframes_to_be_sent_.empty()) {
            auto& kfs = keyframes_to_be_sent_.front();
            auto& lms = landmarks_to_be_sent_.front();
            auto& erase_mp_ids = erased_landmarks_id_.front();
            auto& erase_kf_ids = erased_keyframes_id_.front();

            for (auto& item : kfs) {
                if (!keyframes_set.count(item)) keyframes_set.insert(item);
            }
            for (auto& item : lms) {
                if (!landmarks_set.count(item)) landmarks_set.insert(item);
            }

            // May no need, for the erased items won't duplicate
            sent_erased_landmarks_id.reserve(sent_erased_landmarks_id.size() + erase_mp_ids.size());
            sent_erased_landmarks_id.insert(sent_erased_landmarks_id.end(), erase_mp_ids.begin(), erase_mp_ids.end());

            sent_erased_keyframes_id.reserve(sent_erased_keyframes_id.size() + erase_kf_ids.size());
            sent_erased_keyframes_id.insert(sent_erased_keyframes_id.end(), erase_kf_ids.begin(), erase_kf_ids.end());

            keyframes_to_be_sent_.pop();
            landmarks_to_be_sent_.pop();
            erased_keyframes_id_.pop();
            erased_landmarks_id_.pop();
        }
        sent_keyframes.reserve(keyframes_set.size());
        for (auto& item : keyframes_set) sent_keyframes.push_back(item);

        sent_landmarks.reserve(landmarks_set.size());
        for (auto& item : landmarks_set) sent_landmarks.push_back(item);
    }
}

void Client::clear_queue()
{
    std::unique_lock<std::mutex> lock(sent_map_queue_mtx_);
    while (!landmarks_to_be_sent_.empty()) landmarks_to_be_sent_.pop();
    while (!keyframes_to_be_sent_.empty()) keyframes_to_be_sent_.pop();
    while (!erased_landmarks_id_.empty()) erased_landmarks_id_.pop();
    while (!erased_keyframes_id_.empty()) erased_keyframes_id_.pop();
}

void Client::set_tracking_module(Tracking_module* p_tracking_module) { p_tracking_module_ = p_tracking_module; }

void Client::set_mapping_module(Mapping_module* p_mapping_module) { p_mapping_module_ = p_mapping_module; }

void Client::set_fast_mapping_module(FastMapping_module* p_fast_mapping_module)
{
    p_fast_mapping_module_ = p_fast_mapping_module;
}

double Client::current_server_time()
{
    // TODO estimate time offset between server and client
    return rclcpp::Clock().now().seconds();
}

void Client::send_message(const univloc_msgs::Map& msg)
{
    auto request = std::make_shared<univloc_msgs::MapBasedCommRequest>();

    auto client_message_callback = [](ServiceResponseFuture future) {
        auto result = future.get();
        if (nullptr == result || result->resp_status == false) {
            spdlog::debug("failed to receive response from server node.");
            return;
        }
    };

    request->req_map = msg;
    spdlog::debug("Send message to Server!");
    auto result = comm_client_->async_send_request(request, std::move(client_message_callback));
}

void Client::service_message_callback(const std::shared_ptr<univloc_msgs::MapBasedComm::Request> request,
                      std::shared_ptr<univloc_msgs::MapBasedComm::Response> response)
{
    spdlog::debug("Received message from Server!");
    if (request == nullptr) {
        spdlog::debug("error receiving response from server node.");
        response->resp_status = false;
        return;
    }
    univloc_msgs::MapConstPtr map_msg_ptr = std::make_shared<univloc_msgs::Map>(std::move(request->req_map));
    std::invoke(servise_message_mode_, this, map_msg_ptr);
    response->resp_status = true;
}

void Client::set_session_start_time(double start_time) { session_start_time_ = start_time; }

}  // namespace univloc_tracker
