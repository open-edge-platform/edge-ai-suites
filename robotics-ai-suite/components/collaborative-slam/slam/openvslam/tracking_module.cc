// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "tracking_module.h"

#include <spdlog/spdlog.h>

#include <chrono>
#include <unordered_map>
#include <thread>

#include "camera/base.h"
#include "camera/perspective.h"
#include "camera/fisheye.h"
#include "data/bow_database.h"
#include "data/imu.h"
#include "data/odom.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "mapping_module.h"
#include "match/projection.h"
#include "optimize/imu_edge.h"
#include "timing.h"

#define MAX_ACCEPT_MSG_DELAY  5

namespace openvslam {

tracking_module::tracking_module(std::shared_ptr<univloc_tracker::Config> cfg, camera::base* camera,
                                 data::map_database* map_db, data::bow_database* bow_db)
    : cfg_(cfg),
      camera_(camera),
      map_db_(map_db),
      bow_db_(bow_db),
      initializer_(cfg, camera->setup_type_, map_db, bow_db),
      frame_tracker_(&*camera, 10, cfg->use_odom_, cfg->mode_ == "localization", map_db),
      relocalizer_(bow_db_, camera->setup_type_),
      pose_optimizer_(camera->setup_type_, cfg->use_odom_, cfg->mode_ == "localization"),
      keyfrm_inserter_(camera->setup_type_, cfg->depth_threshold_, map_db, bow_db, 0, camera->fps_)
{
    spdlog::debug("CONSTRUCT: tracking_module");

    if (cfg->mode_ == "mapping")
        tracker_mode_ = tracker_mode_t::Mapping;
    else if (cfg->mode_ == "localization")
        tracker_mode_ = tracker_mode_t::Localization;
    else if (cfg->mode_ == "relocalization")
        tracker_mode_ = tracker_mode_t::Relocalization;
    else if (cfg->mode_ == "remapping")
        tracker_mode_ = tracker_mode_t::Remapping;
    else
        throw std::invalid_argument("Available modes: mapping, localization, relocalization, remapping");

    camera_setup_type_margin_ = (camera_->setup_type_ == camera::setup_type_t::RGBD) ? 10.0 : 5.0;
    min_matched_num_thr_ = camera_->use_imu_ ? 10 : 20;
}

tracking_module::~tracking_module()
{
    clear_frms_and_keyfrms_to_be_relocalized();
    spdlog::debug("DESTRUCT: tracking_module");
}

void tracking_module::clear_frms_and_keyfrms_to_be_relocalized()
{
    /*
        Since the keyframes in the "frms_and_keyfrms_to_be_relocalized_" container
        are managed by raw pointers and won't be added into database if failing to
        re-localize, so we need to delete them manually. In addition, the database
        will handle the memory release of keyframes of successfully re-localizing.
    */
    std::scoped_lock<std::mutex> lock(mtx_frm_and_keyfrm_);
    while(!frms_and_keyfrms_to_be_relocalized_.empty()) {
        delete frms_and_keyfrms_to_be_relocalized_.front().first;
        frms_and_keyfrms_to_be_relocalized_.pop_front();
    }
}

void tracking_module::set_odom_data(std::shared_ptr<data::odom> odom_data_buf) { odom_data_buf_ = odom_data_buf; }

void tracking_module::set_imu_data(std::shared_ptr<data::IMU_data> imu_data_buf) { imu_data_buf_ = imu_data_buf; }

void tracking_module::queue_frm_and_keyfrm_to_be_relocalized(data::keyframe* keyfrm, std::shared_ptr<data::frame> frm)
{
    std::scoped_lock<std::mutex> lock(mtx_frm_and_keyfrm_);
    /*
        The "frms_and_keyfrms_to_be_relocalized_" container is designed to
        contain all the frame-keyframe pairs during server relocalization
        and network latency, so based on previous experience, these
        operations will consume around 100ms, so we choose 1 second here to
        save memory space.

        Increase to 5 seconds to handle the service message time delay in
        up to 4 trackers case.
    */
    size_t max_queue_size = MAX_ACCEPT_MSG_DELAY * camera_->fps_;

    frms_and_keyfrms_to_be_relocalized_.emplace_back(std::make_pair(keyfrm, frm));
    if (frms_and_keyfrms_to_be_relocalized_.size() > max_queue_size) {
        /*
            Since the keyframes in the "frms_and_keyfrms_to_be_relocalized_" container
            are managed by raw pointers and won't be added into database if failing to
            re-localize, so we need to delete them manually. In addition, the database
            will handle the memory release of keyframes of successfully re-localizing.
        */
        delete frms_and_keyfrms_to_be_relocalized_.front().first;
        frms_and_keyfrms_to_be_relocalized_.pop_front();
    }
    spdlog::debug("queue keyframe id is {}, src_frm_id is {}", keyfrm->id_, keyfrm->src_frm_id_);
    spdlog::debug("queue keyframe landmark size is {}", keyfrm->get_landmarks().size());
    spdlog::debug("queue frame landmark size is {}", frm->landmarks_.size());
}

bool tracking_module::get_frm_and_keyfrm(KeyframeID id,
                                         std::pair<data::keyframe*, std::shared_ptr<data::frame>>& frm_keyfrm)
{
    std::scoped_lock<std::mutex> lock(mtx_frm_and_keyfrm_);
    spdlog::debug("query id is {}", id);
    while (!frms_and_keyfrms_to_be_relocalized_.empty()) {
        auto pair = frms_and_keyfrms_to_be_relocalized_.front();
        frms_and_keyfrms_to_be_relocalized_.pop_front();
        if (!pair.first)
            continue;

        auto p_keyframe = pair.first;
        auto p_frame = pair.second;
        spdlog::debug("db keyframe id is {}", p_keyframe->id_);
        spdlog::debug("db frame id is {}", p_frame->id_);
        if (p_keyframe->id_ == id) {
            frm_keyfrm = pair;
            spdlog::debug("get keyframe landmark size is {}", p_keyframe->get_landmarks().size());
            spdlog::debug("get frame landmark size is {}", p_frame->landmarks_.size());
            return true;
        }

        /*
            Since the keyframes in the "frms_and_keyfrms_to_be_relocalized_" container
            are managed by raw pointers and won't be added into database if failing to
            re-localize, so we need to delete them manually. In addition, the database
            will handle the memory release of keyframes of successfully re-localizing.
        */
        delete pair.first;
    }
    return false;
}

void tracking_module::monocular_initialization_using_relocalization(data::keyframe* p_keyframe, std::shared_ptr<data::frame> p_frame)
{
    assert(p_keyframe);

    auto init_keyfrm = p_keyframe;

    map_db_->add_keyframe(init_keyfrm);
    map_db_->origin_keyfrm_ = init_keyfrm;
    init_keyfrm->set_origin();  // used in visualization

    local_landmarks_.clear();

    const auto lms = init_keyfrm->get_landmarks();

    for (auto lm : lms) {
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        local_landmarks_.push_back(lm);
    }

    map_db_->set_local_landmarks(local_landmarks_);

    last_reloc_frm_id_ = p_frame->id_;

    ref_keyfrm_ = init_keyfrm;

    last_keyfrm_ = init_keyfrm;

    // just for test, maybe better implementation
    curr_frm_->set_cam_pose(init_keyfrm->get_cam_pose());

    curr_frm_->ref_keyfrm_ = ref_keyfrm_;

    // TODO: clear queue, assume the tracking is good, then clear!
    // pass all of the keyframes to the mapping module
    const auto keyfrms = map_db_->get_all_keyframes();
    for (const auto keyfrm : keyfrms) {
        mapper_->queue_keyframe(keyfrm);
    }

    // state transition to Tracking mode
    tracking_state_ = tracker_state_t::Tracking;

    // update last frame
    last_frm_ = p_frame;
    // it is important to avoid error in update_last_frm func
    last_frm_->ref_keyfrm_ = nullptr;

    initializer_.set_initial_frame_id(last_frm_->id_);

    spdlog::info("Monocular initialization using relocalization result finished!");
}

void tracking_module::set_mapping_module(mapping_module* mapper)
{
    mapper_ = mapper;
    keyfrm_inserter_.set_mapping_module(mapper);
}

void tracking_module::set_mapping_module_status(const bool mapping_is_enabled)
{
    std::lock_guard<std::mutex> lock(mtx_mapping_);
    mapping_is_enabled_ = mapping_is_enabled;
}

bool tracking_module::get_mapping_module_status() const
{
    std::lock_guard<std::mutex> lock(mtx_mapping_);
    return mapping_is_enabled_;
}

std::vector<cv::KeyPoint> tracking_module::get_initial_keypoints() const
{
    return initializer_.get_initial_keypoints();
}

std::vector<int> tracking_module::get_initial_matches() const { return initializer_.get_initial_matches(); }

bool tracking_module::is_initializing() const
{
    return (tracking_state_ == tracker_state_t::NotInitialized || tracking_state_ == tracker_state_t::Initializing ||
            tracking_state_ == tracker_state_t::Lost);
}

void tracking_module::reset()
{
    spdlog::info("resetting system");
    if (camera_->use_imu_) data::IMU_Preintegration::reset();
    initializer_.reset();
    keyfrm_inserter_.reset();

    mapper_->request_reset();

    bow_db_->clear();
    map_db_->clear();

    tracking_state_ = tracker_state_t::NotInitialized;
    // clear queue
    clear_frms_and_keyfrms_to_be_relocalized();
    if (camera_->use_imu_) imu_mearsurement_vec_.clear();
}

void tracking_module::align_state_to_inertial_frame(const Eigen::Matrix3d R_inertial_c0, const double scale)
{
    velocity_.block(0, 3, 3, 1) = velocity_.block(0, 3, 3, 1) * scale;
    auto T = last_frm_->cam_pose_cw_;
    T.block(0, 0, 3, 3) = T.block(0, 0, 3, 3) * R_inertial_c0.transpose();
    T.block(0, 3, 3, 1) = scale * T.block(0, 3, 3, 1);
    last_frm_->set_cam_pose(T);
    last_cam_pose_from_ref_keyfrm_.block(0, 3, 3, 1) = scale * last_cam_pose_from_ref_keyfrm_.block(0, 3, 3, 1);
}

void tracking_module::predict_camerapose_from_imu()
{
    assert(data::IMU_Preintegration::state_ == data::IMU_Preintegration::Initialized);
    Eigen::Matrix4d imu_pose = last_keyfrm_->get_cam_pose_inv() * data::IMU_Preintegration::Tci_;
    Eigen::Vector3d predicted_imu_velocity_ = last_keyfrm_->get_imu_velocity();
    double delta_t = 0;

    auto imu_measurement = imu_mearsurement_vec_.front().second;
    assert(imu_mearsurement_vec_.front().first >= last_keyfrm_->timestamp_);
    for (unsigned int i = 0; i < imu_mearsurement_vec_.size(); i++) {
        if (i == 0) {
            delta_t = imu_mearsurement_vec_[i].first - last_keyfrm_->timestamp_;
            imu_measurement = imu_mearsurement_vec_[i].second - data::IMU_Preintegration::last_bias_;
        } else {
            delta_t = imu_mearsurement_vec_[i].first - imu_mearsurement_vec_[i - 1].first;
            imu_measurement = (imu_mearsurement_vec_[i].second + imu_mearsurement_vec_[i - 1].second) * 0.5 -
                              data::IMU_Preintegration::last_bias_;
        }

        Eigen::Vector3d imu_rotation_speed = imu_measurement.tail(3),
                        imu_accel_world = imu_pose.block(0, 0, 3, 3) * imu_measurement.head(3) + gI;
        imu_pose.block(0, 3, 3, 1) = imu_pose.block(0, 3, 3, 1) + predicted_imu_velocity_ * delta_t +
                                     gI * delta_t * delta_t * 0.5 +
                                     0.5 * imu_pose.block(0, 0, 3, 3) * imu_measurement.head(3) * delta_t * delta_t;
        imu_pose.block(0, 0, 3, 3) = imu_pose.block(0, 0, 3, 3) * skew(imu_rotation_speed * delta_t).exp();

        predicted_imu_velocity_ = predicted_imu_velocity_ + imu_accel_world * delta_t;

        if (i == imu_mearsurement_vec_.size() - 1) {
            delta_t = curr_frm_->timestamp_ - imu_mearsurement_vec_[i].first;
            imu_measurement = imu_mearsurement_vec_[i].second - data::IMU_Preintegration::last_bias_;
            Eigen::Vector3d imu_rotation_speed = imu_measurement.tail(3),
                            imu_accel_world = imu_pose.block(0, 0, 3, 3) * imu_measurement.head(3) + gI;
            imu_pose.block(0, 3, 3, 1) = imu_pose.block(0, 3, 3, 1) + predicted_imu_velocity_ * delta_t +
                                         gI * delta_t * delta_t * 0.5 +
                                         0.5 * imu_pose.block(0, 0, 3, 3) * imu_measurement.head(3) * delta_t * delta_t;
            predicted_imu_velocity_ = predicted_imu_velocity_ + imu_accel_world * delta_t;
            imu_pose.block(0, 0, 3, 3) = imu_pose.block(0, 0, 3, 3) * skew(imu_rotation_speed * delta_t).exp();
        }
    }
    imu_predicted_camera_pose_cw_ = data::IMU_Preintegration::Tci_ * imu_pose.inverse();
    if (curr_frm_->too_few_features_) {
        if (imu_estimated_poses_.empty())
            imu_estimated_poses_.push_back(last_keyfrm_->get_cam_pose_inv() * data::IMU_Preintegration::Tci_);
        imu_estimated_poses_.push_back(imu_pose);
    }
}

std::vector<Eigen::Vector3d> tracking_module::get_local_landmark_positions() const
{
    std::vector<Eigen::Vector3d> local_landmarks;
    for (auto& lm : local_landmarks_) {
        assert(map_db_->get_landmark(lm->id_));
        local_landmarks.push_back(lm->get_pos_in_world());
    }
    return local_landmarks;
}

bool tracking_module::get_odom_data()
{
    timer_.startNextProc("get odometry data");
    Eigen::Matrix4d pose = Eigen::Matrix4d::Identity();
    int get_odom_stat = 1;
    const auto query_start = std::chrono::system_clock::now();
    std::chrono::duration<float, std::milli> query_duration(0.0);
    while ((get_odom_stat = odom_data_buf_->get_odom(curr_frm_->timestamp_, pose)) > 0) {
        const auto query_now = std::chrono::system_clock::now();
        query_duration = query_now - query_start;
        if (query_duration.count() > cfg_->odom_buffer_query_timeout_) {
            spdlog::debug("get_odom_data: query_duration is {}", query_duration.count());
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    if (get_odom_stat == 1) {
        curr_frm_->odom_ = last_odom_pose_;
        spdlog::debug("can't get odom pose for current frame (id: {}), use last odom pose instead", curr_frm_->id_);
        return true;
    } else if (get_odom_stat == 0) {
        // Tco
        curr_frm_->odom_ = pose;
        last_odom_pose_ = pose;
        spdlog::debug("able to get odom pose for current frame (id {}), update last odom pose", curr_frm_->id_);
        return true;
    } else { 
        spdlog::warn("can't get odom pose for current frame (id: {}), return false", curr_frm_->id_);
        return false;
    }
}

bool tracking_module::initialize()
{
    timer_.startNextProc("initialize");
    // try to initialize with the current frame
    initializer_.initialize(*curr_frm_);

    // if initializing was failed -> try to initialize with the next frame
    if (initializer_.get_state() != module::initializer_state_t::Succeeded) {
        return false;
    }

    last_keyfrm_ = curr_frm_->ref_keyfrm_;
    // succeeded
    return true;
}

void tracking_module::get_relative_transform_from_odom(Mat44_t& relative_transform_from_odom)
{
    relative_transform_from_odom = Eigen::Matrix4d::Identity();

    Mat44_t curr_odom = curr_frm_->odom_;
    Mat44_t init_odom = first_valid_odom_;

    // Since we only start tracking when odom data is valid, then the odom should be valid for each frame
    // Because if not valid, it is already set to use last frame's odom in get_odom_data func
    if (curr_odom == Mat44_t::Identity() || init_odom == Mat44_t::Identity()) {
        if (curr_odom == Mat44_t::Identity())
            spdlog::debug("get_relative_transform_from_odom curr_odom is invalid");
        if (init_odom == Mat44_t::Identity())
            spdlog::debug("get_relative_transform_from_odom init_odom is invalid");
    }

    Mat33_t rot_c2_o = curr_odom.block<3, 3>(0, 0);
    Vec3_t trans_c2_o = curr_odom.block<3, 1>(0, 3);
    Mat33_t rot_o_c1 = init_odom.block<3, 3>(0, 0).transpose();
    Vec3_t trans_o_c1 = -rot_o_c1 * init_odom.block<3, 1>(0, 3);

    Mat33_t rot_c2_c1 = rot_c2_o * rot_o_c1;
    Vec3_t trans_c2_c1 = rot_c2_o * trans_o_c1 + trans_c2_o;

    relative_transform_from_odom.block<3, 3>(0, 0) = rot_c2_c1;
    relative_transform_from_odom.block<3, 1>(0, 3) = trans_c2_c1;
}

bool tracking_module::track_current_frame()
{
    bool succeeded = false;

    if (tracking_state_ == tracker_state_t::Tracking) {
        // Tracking mode
        if (cfg_->use_odom_) {
            Mat44_t relative_transform_from_odom;
            get_relative_transform_from_odom(relative_transform_from_odom);
            Mat44_t odom_predict_pose = relative_transform_from_odom * first_valid_pose_;

            succeeded = frame_tracker_.odom_based_track(*curr_frm_, *last_frm_, odom_predict_pose);
            if (!succeeded)
                spdlog::debug("odom model tracking failed!");
            else
                spdlog::debug("odom model tracking success!");
        }
        if (!succeeded && velocity_is_valid_ && last_reloc_frm_id_ + 2 < curr_frm_->id_) {
            // if the motion model is valid
            succeeded = frame_tracker_.motion_based_track(*curr_frm_, *last_frm_, velocity_);
            if (!succeeded)
                spdlog::debug("Motion model tracking failed!");
            else
                spdlog::debug("Motion model tracking success!");
        }
        if (!succeeded && data::IMU_Preintegration::state_ == data::IMU_Preintegration::Initialized) {
            succeeded = frame_tracker_.imu_based_track(*curr_frm_, *last_frm_, imu_predicted_camera_pose_cw_);
            if (!succeeded)
                spdlog::debug("IMU based tracking failed!");
            else
                spdlog::debug("IMU based tracking success!");
        }
        if (!succeeded) {
            succeeded = frame_tracker_.bow_match_based_track(*curr_frm_, *last_frm_, ref_keyfrm_);
            if (!succeeded)
                spdlog::debug("bow_match_based_track failed!");
            else
                spdlog::debug("bow_match_based_track tracking success!");
        }
        if (!succeeded) {
            succeeded = frame_tracker_.robust_match_based_track(*curr_frm_, *last_frm_, ref_keyfrm_);
            if (!succeeded)
                spdlog::debug("robust_match_based_track tracking failed!");
            else
                spdlog::debug("robust_match_based_track tracking success!");
        }
    } else {
        // Lost mode
        // try to relocalize
        spdlog::debug("Trying to relocalize!");
        succeeded = relocalizer_.relocalize(*curr_frm_);
        if (succeeded) {
            last_reloc_frm_id_ = curr_frm_->id_;
        }
    }
    return succeeded;
}

void tracking_module::update_motion_model()
{
    timer_.startNextProc("update motion model");
    if (last_frm_->cam_pose_cw_is_valid_) {
        Mat44_t last_frm_cam_pose_wc = Mat44_t::Identity();
        last_frm_cam_pose_wc.block<3, 3>(0, 0) = last_frm_->get_rotation_inv();
        last_frm_cam_pose_wc.block<3, 1>(0, 3) = last_frm_->get_cam_center();
        velocity_is_valid_ = true;
        velocity_ = curr_frm_->cam_pose_cw_ * last_frm_cam_pose_wc;
    } else {
        velocity_is_valid_ = false;
        velocity_ = Mat44_t::Identity();
    }
}

void tracking_module::apply_landmark_replace()
{
    timer_.startNextProc("apply landmark replace");

    // reset system for monocular camera
    // if (last_frm_->landmarks_.empty()) return;

    for (unsigned int idx = 0; idx < last_frm_->num_keypts_; ++idx) {
        auto lm = last_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }

        auto replaced_lm = lm->get_replaced();
        if (replaced_lm) {
            // spdlog::debug("landmark {} will replace landmark {}", replaced_lm->id_, lm->id_);
            last_frm_->landmarks_.at(idx) = replaced_lm;
        }
    }
}

void tracking_module::update_last_frame()
{
    timer_.startNextProc("update last frame");
    auto last_ref_keyfrm = last_frm_->ref_keyfrm_;
    if (!last_ref_keyfrm && last_frm_->cam_pose_cw_is_valid_) {
        return;
    }
    if (last_ref_keyfrm){
        last_frm_->set_cam_pose(last_cam_pose_from_ref_keyfrm_ * last_ref_keyfrm->get_cam_pose());
    }
}

void tracking_module::get_local_keyframes_poses(std::vector<Eigen::Matrix4d>& poses, bool sort) const
{
    poses.clear();
    if (data::IMU_Preintegration::state_ == data::IMU_Preintegration::IMU_State::Not_Initialized) {
        poses.reserve(local_keyfrms_.size());
        if (sort) {
            std::map<KeyframeID, Eigen::Matrix4d> poses_with_id;
            for (const auto& kf : local_keyfrms_) {
                poses_with_id.emplace(std::make_pair(kf->id_, kf->get_cam_pose_inv()));
            }
            for (const auto& it : poses_with_id) {
                poses.push_back(it.second);
            }
        } else {
            for (const auto& kf : local_keyfrms_) {
                poses.push_back(kf->get_cam_pose_inv());
            }
        }
    } else {
        const int max_tempral_keyframes_num = 25;
        poses.reserve(max_tempral_keyframes_num);
        std::map<KeyframeID, data::keyframe*> tempral_keyfrms;

        tempral_keyfrms[last_keyfrm_->id_] = last_keyfrm_;
        // get last tempral new keyframes
        while (tempral_keyfrms.size() < max_tempral_keyframes_num) {
            auto pre_keyframe = tempral_keyfrms.begin()->second->pre_keyframe_;
            if (pre_keyframe) {
                tempral_keyfrms[pre_keyframe->id_] = pre_keyframe;
            } else {
                break;
            }
        }
        for (const auto& item : tempral_keyfrms) poses.push_back(item.second->get_cam_pose_inv());
    }
}

void tracking_module::get_local_keyframes_poses(std::vector<Eigen::Matrix4d>& covisibility_poses,
                                                std::vector<Eigen::Matrix4d>& non_covisibility_poses) const
{
    unsigned int covisibility_weigth_thr = 10;
    covisibility_poses.clear();
    non_covisibility_poses.clear();
    std::map<KeyframeID, Eigen::Matrix4d> covisibility_poses_with_id, non_covisibility_poses_with_id;
    for (const auto& kf : local_keyfrms_) {
        if (ref_keyfrm_->graph_node_->get_weight(kf) > covisibility_weigth_thr || ref_keyfrm_->id_ == kf->id_)
            covisibility_poses_with_id.emplace(std::make_pair(kf->id_, kf->get_cam_pose_inv()));
        else
            non_covisibility_poses_with_id.emplace(std::make_pair(kf->id_, kf->get_cam_pose_inv()));
    }
    for (const auto& it : covisibility_poses_with_id) covisibility_poses.push_back(it.second);
    for (const auto& it : non_covisibility_poses_with_id) non_covisibility_poses.push_back(it.second);
}

void tracking_module::get_local_landmarks_positions(std::vector<Eigen::Vector3d>& positions) const
{
    positions.clear();
    if (data::IMU_Preintegration::state_ == data::IMU_Preintegration::IMU_State::Not_Initialized) {
        positions.reserve(local_landmarks_.size());
        for (auto& lm : local_landmarks_) {
            positions.push_back(lm->get_pos_in_world());
        }
    } else {
        const int max_tempral_keyframes_num = 25;
        std::map<KeyframeID, data::keyframe*> tempral_keyfrms;

        tempral_keyfrms[last_keyfrm_->id_] = last_keyfrm_;
        // get last tempral new keyframes
        while (tempral_keyfrms.size() < max_tempral_keyframes_num) {
            auto pre_keyframe = tempral_keyfrms.begin()->second->pre_keyframe_;
            if (pre_keyframe) {
                tempral_keyfrms[pre_keyframe->id_] = pre_keyframe;
            } else {
                break;
            }
        }
        std::set<data::landmark*> landmarks;
        for (const auto& item : tempral_keyfrms) {
            auto lms = item.second->get_valid_landmarks();
            for (const auto& lm : lms) landmarks.insert(lm);
        }
        positions.reserve(landmarks.size());
        for (const auto& lm : landmarks) positions.push_back(lm->get_pos_in_world());
    }
}

unsigned int tracking_module::get_num_tracked_lms() const { return num_tracked_lms_; }

void tracking_module::get_tracked_server_landmarks_positions(std::vector<Eigen::Vector3d>& positions) const
{
    positions = tracked_server_landmarks_position_;
}

void tracking_module::get_imu_estimated_poses(std::vector<Eigen::Matrix4d>& poses) const
{
    poses = imu_estimated_poses_;
}

bool tracking_module::optimize_current_frame_with_local_map()
{
    timer_.startNextProc("optimize with local map");
    // acquire more 2D-3D matches by reprojecting the local landmarks to the current frame
    search_local_landmarks();

    // optimize the pose
    // only compute covariance in the last time of calling pose optimizer in mapping mode
    pose_optimizer_.optimize(*curr_frm_, cfg_->need_covariance_);

    // count up the number of tracked landmarks
    num_tracked_lms_ = 0;
    for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
        auto lm = curr_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }

        if (!curr_frm_->outlier_flags_.at(idx)) {
            // the observation has been considered as inlier in the pose optimization
            assert((std::string("Landmark id: ") + std::to_string(lm->id_),
                    lm->has_observation() || lm->come_from_server()));
            // count up
            ++num_tracked_lms_;
            // increment the number of tracked frame
            lm->increase_num_observed();
        } else {
            // the observation has been considered as outlier in the pose optimization
            // remove the observation
            curr_frm_->landmarks_.at(idx) = nullptr;
        }
    }

    constexpr unsigned int num_tracked_lms_thr = 20;

    // if recently relocalized, use the more strict threshold
    if (curr_frm_->id_ < last_reloc_frm_id_ + camera_->fps_ && num_tracked_lms_ < 2 * num_tracked_lms_thr) {
        spdlog::debug("local map tracking failed: {} matches < {}", num_tracked_lms_, 2 * num_tracked_lms_thr);
        return false;
    }

    // check the threshold of the number of tracked landmarks
    if (num_tracked_lms_ < num_tracked_lms_thr) {
        spdlog::debug("local map tracking failed: {} matches < {}", num_tracked_lms_, num_tracked_lms_thr);
        return false;
    }

    return true;
}

bool tracking_module::search_all_landmarks()
{
    unsigned int min_matched_num_thr = camera_->use_imu_ ? 10 : 20;

    for (auto lm : curr_frm_->landmarks_) {
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        // this landmark cannot be reprojected
        // because already observed in the current frame
        lm->is_observable_in_tracking_ = false;
        lm->identifier_in_local_lm_search_ = curr_frm_->id_;

        // this landmark is observable from the current frame
        lm->increase_num_observable();
    }

    // if (server_landmarks.empty()) return false;
    bool found_proj_candidate = false;
    // temporary variables
    Vec2_t reproj;
    float x_right;
    unsigned int pred_scale_level, observerd_local_landmarks_num = 0, observed_server_landmarks_num = 0;

    // Get server landmarks from database
    std::vector<std::shared_ptr<data::landmark>> server_landmarks = map_db_->get_server_landmarks();

    std::vector<data::landmark*> nearby_landmarks;
    nearby_landmarks.resize(server_landmarks.size() + local_landmarks_.size());
    int idx = -1;

    for (auto lm : server_landmarks) {
        idx++;
        nearby_landmarks[idx] = nullptr;
        // avoid the landmarks which cannot be reprojected (== observed in the current frame)
        if (lm->identifier_in_local_lm_search_ == curr_frm_->id_) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        // check the observability
        if (curr_frm_->can_observe(lm.get(), 0.5, reproj, x_right, pred_scale_level)) {
            // pass the temporary variables
            lm->reproj_in_tracking_ = reproj;
            lm->x_right_in_tracking_ = x_right;
            lm->scale_level_in_tracking_ = pred_scale_level;

            // this landmark can be reprojected
            lm->is_observable_in_tracking_ = true;

            // this landmark is observable from the current frame
            lm->increase_num_observable();

            found_proj_candidate = true;

            nearby_landmarks[idx] = lm.get();

            observed_server_landmarks_num++;

            // Used for judging whether server landmarks can be odserved

            lm->out_of_local_map_times_ = 0;

        } else {
            // this landmark cannot be reprojected
            lm->is_observable_in_tracking_ = false;
        }
    }

    for (auto lm : local_landmarks_) {
        idx++;
        nearby_landmarks[idx] = nullptr;
        // avoid the landmarks which cannot be reprojected (== observed in the current frame)
        if (lm->identifier_in_local_lm_search_ == curr_frm_->id_) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        // check the observability
        if (curr_frm_->can_observe(lm, 0.5, reproj, x_right, pred_scale_level)) {
            // pass the temporary variables
            lm->reproj_in_tracking_ = reproj;
            lm->x_right_in_tracking_ = x_right;
            lm->scale_level_in_tracking_ = pred_scale_level;

            // this landmark can be reprojected
            lm->is_observable_in_tracking_ = true;

            // this landmark is observable from the current frame
            lm->increase_num_observable();

            found_proj_candidate = true;

            nearby_landmarks[idx] = lm;

            observerd_local_landmarks_num++;

        } else {
            // this landmark cannot be reprojected
            lm->is_observable_in_tracking_ = false;
        }
    }

    if (!found_proj_candidate) {
        return false;
    }

    // acquire more 2D-3D matches by projecting the local landmarks to the current frame
    match::projection projection_matcher(0.8);
    const float margin = (curr_frm_->id_ < last_reloc_frm_id_ + 2)
                             ? 20.0
                             : ((camera_->setup_type_ == camera::setup_type_t::RGBD) ? 10.0 : 5.0);

    unsigned int matched_num = projection_matcher.match_frame_and_landmarks(*curr_frm_, nearby_landmarks, margin);

    spdlog::debug(" {} of {} local landmarks are obserrved ", observerd_local_landmarks_num, local_landmarks_.size());

    spdlog::debug(" {} of {} server landmarks(not existed in local map) are obserrved ", observed_server_landmarks_num,
                  server_landmarks.size());

    spdlog::debug(" {} of {} landmarks are succesfully matched ", matched_num, nearby_landmarks.size());

    return matched_num > min_matched_num_thr;
}

bool tracking_module::search_local_landmarks()
{
    // select the landmarks which can be reprojected from the ones observed in the current frame
    for (auto lm : curr_frm_->landmarks_) {
        if (!lm) {
            continue;
        }
        if (unlikely(lm->will_be_erased())) {
            continue;
        }

        // this landmark cannot be reprojected
        // because already observed in the current frame
        lm->is_observable_in_tracking_ = false;
        lm->identifier_in_local_lm_search_ = curr_frm_->id_;

        // this landmark is observable from the current frame
        lm->increase_num_observable();
    }

    bool found_proj_candidate = false;
    // temporary variables
    Vec2_t reproj;
    float x_right;
    unsigned int pred_scale_level, observed_local_landmarks_num = 0;
    for (auto lm : local_landmarks_) {
        // avoid the landmarks which cannot be reprojected (== observed in the current frame)
        if (lm->identifier_in_local_lm_search_ == curr_frm_->id_) {
            continue;
        }
        if (unlikely(lm->will_be_erased())) {
            continue;
        }

        // check the observability
        if (curr_frm_->can_observe(lm, 0.5, reproj, x_right, pred_scale_level)) {
            // pass the temporary variables
            lm->reproj_in_tracking_ = reproj;
            lm->x_right_in_tracking_ = x_right;
            lm->scale_level_in_tracking_ = pred_scale_level;

            // this landmark can be reprojected
            lm->is_observable_in_tracking_ = true;

            // this landmark is observable from the current frame
            lm->increase_num_observable();

            found_proj_candidate = true;

            observed_local_landmarks_num++;
        } else {
            // this landmark cannot be reprojected
            lm->is_observable_in_tracking_ = false;
        }
    }

    if (!found_proj_candidate) {
        return false;
    }

    // acquire more 2D-3D matches by projecting the local landmarks to the current frame
    match::projection projection_matcher(0.8);
    const float margin = (curr_frm_->id_ < last_reloc_frm_id_ + 2)
                             ? 20.0
                             : camera_setup_type_margin_;

    auto matched_num = projection_matcher.match_frame_and_landmarks(*curr_frm_, local_landmarks_, margin);

    spdlog::debug(" {} of {} local landmarks are observed when tracking local map", observed_local_landmarks_num,
                  local_landmarks_.size());

    spdlog::debug(" {} of {} local landmarks are succesfully matched ", matched_num, local_landmarks_.size());

    return matched_num > min_matched_num_thr_;
}

bool tracking_module::new_keyframe_is_needed() const
{
    if (!mapping_is_enabled_) {
        return false;
    }

    // Add new keyframe to allow switching back to visual tracking when possible
    // The magic number is set according to the number used in VIO mode below
    if (cfg_->use_odom_) {
        if (curr_frm_->timestamp_ - last_keyfrm_->timestamp_ >= 0.5) {
            if (mapper_->get_keyframe_acceptability()) return true;
        }
    }

    if (camera_->use_imu_) {
        //! Before IMU is initialized, the time interval between consecutive keyframes should be limited
        if (data::IMU_Preintegration::imu_initialize_times_ == 0) {
            if (curr_frm_->timestamp_ - last_keyfrm_->timestamp_ >= 0.25)
                return true;
            else
                return false;
        } else if (curr_frm_->timestamp_ - last_keyfrm_->timestamp_ >= 0.5) {
            if (mapper_->get_keyframe_acceptability()) return true;
        }
    }

    if (!mapper_->get_keyframe_acceptability()) {
        return false;
    }

    // cannnot insert the new keyframe in a second after relocalization
    const auto num_keyfrms = map_db_->get_num_keyframes();
    if (camera_->fps_ < num_keyfrms && curr_frm_->id_ < last_reloc_frm_id_ + camera_->fps_) {
        return false;
    }

    // check the new keyframe is needed
    return keyfrm_inserter_.new_keyframe_is_needed(*curr_frm_, num_tracked_lms_, *ref_keyfrm_);
}

data::keyframe* tracking_module::create_map_for_stereo(data::frame& curr_frm)
{
    auto curr_keyfrm = new data::keyframe(curr_frm, map_db_, bow_db_);

    // compute BoW representation
    curr_keyfrm->compute_bow();
    // add to the map DB
    map_db_->add_keyframe(curr_keyfrm);

    // update the frame statistics
    curr_frm.ref_keyfrm_ = curr_keyfrm;
    map_db_->update_frame_statistics(curr_frm, false);

    for (unsigned int idx = 0; idx < curr_frm.num_keypts_; ++idx) {
        // add a new landmark if tht corresponding depth is valid
        const auto z = curr_frm.depths_.at(idx);
        if (z <= 0
#ifdef ENABLE_SEMANTIC_SLAM
            || curr_frm.segment_outlier_flags_[idx]
#endif
        ) {
            continue;
        }

        // build a landmark
        const Vec3_t pos_w = curr_frm.triangulate_stereo(idx);
        auto lm = new data::landmark(pos_w, curr_keyfrm, map_db_);

        // set the associations to the new keyframe
        lm->add_observation(curr_keyfrm, idx);
        curr_keyfrm->add_landmark(lm, idx);

        // update the descriptor
        lm->compute_descriptor();
        // update the geometry
        lm->update_normal_and_depth();

        // set the 2D-3D associations to the current frame
        curr_frm.landmarks_.at(idx) = lm;
        curr_frm.outlier_flags_.at(idx) = false;

        // add the landmark to the map DB
        map_db_->add_landmark(lm);
    }

    // set the origin keyframe
    curr_keyfrm->should_be_fixed_in_optimization_ = true;

    return curr_keyfrm;
}

void tracking_module::insert_new_keyframe()
{
    timer_.startNextProc("insert new keyframe");

    bool send_to_server = ((tracker_mode_ == tracker_mode_t::Mapping ) ||
                           ( tracker_mode_ == tracker_mode_t::Remapping));
    const auto ref_keyfrm = keyfrm_inserter_.insert_new_keyframe(*curr_frm_, send_to_server);

    if (camera_->use_imu_ && ref_keyfrm) {
        ref_keyfrm->set_new_imu_bias(data::IMU_Preintegration::last_bias_);

        int n1 = imu_mearsurement_vec_.size();

        spdlog::debug("Try to get more imu data!");

        // sometimes, the imu and camera timestamp is not ideal
        imu_data_buf_->get_imu_data(last_keyfrm_->timestamp_, ref_keyfrm->timestamp_, imu_mearsurement_vec_);

        int n2 = imu_mearsurement_vec_.size();

        if (n2 - n1) spdlog::debug("Got {} more imu data during insert new keyframe!", n2 - n1);

        auto imu_preintegration_ptr = std::make_shared<data::IMU_Preintegration>(
            last_keyfrm_->timestamp_, ref_keyfrm->timestamp_, imu_mearsurement_vec_);

        // set imu related member variables, first calculate the imu velocity
        ref_keyfrm->imu_is_initialized_ = (data::IMU_Preintegration::imu_initialize_times_ > 0);
        Vec3_t velocity = Vec3_t::Zero();
        if (ref_keyfrm->imu_is_initialized_) {
            const double t12 = imu_preintegration_ptr->integration_time_;
            velocity = (ref_keyfrm->get_imu_position() - last_keyfrm_->get_imu_position()) / t12;
            // The following way of velocity calculation isn't stable due to drift
            // const Mat33_t rot_wb1 = last_keyfrm_->get_imu_rotation();
            // const Vec3_t velocity1 = last_keyfrm_->get_imu_velocity();
            // velocity2 = velocity1 + gI * t12 + rot_wb1 * imu_preintegration_ptr->get_updated_delta_velocity();
        }
        ref_keyfrm->set_imu_velocity(velocity);
        ref_keyfrm->set_new_imu_bias(last_keyfrm_->get_imu_bias());
        ref_keyfrm->set_imu_constraint(last_keyfrm_, imu_preintegration_ptr);

        last_keyfrm_->next_keyframe_ = ref_keyfrm;
        ref_keyfrm->pre_keyframe_ = last_keyfrm_;

        spdlog::debug("Create imu constraint between keyframe {} and {}", last_keyfrm_->id_, ref_keyfrm->id_);
    }
    // Update the last_keyfrm_ in both mapping and localization mode
    last_keyfrm_ = ref_keyfrm;

    // Set the reference keyframe with the new keyframe
    ref_keyfrm_ = ref_keyfrm ? ref_keyfrm : ref_keyfrm_;

    curr_frm_->ref_keyfrm_ = ref_keyfrm_;

    // queue keyframe after preintegration is done, make sure new keyframe is valid
    if (camera_->use_imu_ && ref_keyfrm) keyfrm_inserter_.queue_keyframe(ref_keyfrm);
}

void tracking_module::request_pause()
{
    std::lock_guard<std::mutex> lock1(mtx_pause_);
    pause_is_requested_ = true;
}

bool tracking_module::pause_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    return pause_is_requested_;
}

bool tracking_module::is_paused() const
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    return is_paused_;
}

void tracking_module::resume()
{
    std::lock_guard<std::mutex> lock(mtx_pause_);

    is_paused_ = false;
    pause_is_requested_ = false;

    spdlog::info("resume tracking module");
}

bool tracking_module::check_and_execute_pause()
{
    std::lock_guard<std::mutex> lock(mtx_pause_);
    if (pause_is_requested_) {
        is_paused_ = true;
        spdlog::info("pause tracking module");
        return true;
    } else {
        return false;
    }
}

}  // namespace openvslam
