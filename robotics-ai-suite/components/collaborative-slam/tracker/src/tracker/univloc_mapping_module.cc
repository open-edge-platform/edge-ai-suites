// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "mapping_module.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "data/bow_database.h"
#include "tracker/Client.h"
#include "tracking_module.h"
#include "optimize/imu_initializer.h"
#include "data/imu.h"
#include "timing.h"
#include "univloc_mapping_module.h"

#include <spdlog/spdlog.h>
#include <spdlog/fmt/ostr.h>

#define EPSILON                        0.00001
#define TIME_AFTER_INITIALIZING_THR    10.0
#define DISTANCE_THR                   0.02
#define TEMPORAL_WINDOW_SIZE           25

namespace openvslam {

univloc_mapping_module::univloc_mapping_module(data::map_database* map_db, data::bow_database* bow_db, const bool is_monocular, bool use_odom, const bool clean_keyframe)
    : mapping_module(map_db, bow_db, is_monocular, use_odom, clean_keyframe),
      scale_(1.0),
      keyframes_num_for_initializing_imu_(10)
{
    spdlog::debug("CONSTRUCT: univloc_mapping_module");
}

univloc_mapping_module::~univloc_mapping_module() { spdlog::debug("DESTRUCT: univloc_mapping_module"); }

void univloc_mapping_module::populate_sent_landmarks(std::vector<data::landmark*>& landmarks_out)
{
    // The window size of temporal keyframes, we only send landmarks belonging to such keyframes
    data::keyframe* curr_keyfrm = get_cur_keyframe();
    const auto curr_covisibilities = curr_keyfrm->graph_node_->get_covisibilities();

    spdlog::debug("First populate the co-visible landmarks!");
    std::vector<data::keyframe*> associated_keyframes;
    for (auto local_keyfrm : curr_covisibilities) {
        if (unlikely(!local_keyfrm || local_keyfrm->will_be_erased())) {
            continue;
        }

        associated_keyframes.emplace_back(local_keyfrm);
        /*
            Currently we use the same flag as localBA to indicate 
            if the keyframe or landmark have been considered. We
            can do so because the localBA and send_to_server()
            are in the same threads and in both of them we clear
            such flag at the end.
        */
        local_keyfrm->is_considered_ = true;

        const auto landmarks = local_keyfrm->get_landmarks();
        for (auto local_lm : landmarks) {
            if (!local_lm || local_lm->will_be_erased() || local_lm->is_considered_) {
                continue;
            }

            landmarks_out.emplace_back(local_lm);
            local_lm->is_considered_ = true;
        }
    }

    spdlog::debug("Second populate the temporal close landmarks!");
    associated_keyframes.emplace_back(curr_keyfrm);
    int cnt = 0;
    // We only send landmarks belonging to such keyframes in the temporal window
    for (unsigned int i = 1; i < TEMPORAL_WINDOW_SIZE; i++) {
        const auto landmarks = associated_keyframes.back()->get_landmarks();
        for (auto temporal_lm : landmarks) {
            if (!temporal_lm || temporal_lm->will_be_erased() || temporal_lm->is_considered_) {
                continue;
            }

            landmarks_out.emplace_back(temporal_lm);
            ++cnt;
            temporal_lm->is_considered_ = true;
        }

        if (associated_keyframes.back()->pre_keyframe_) {
            if (!associated_keyframes.back()->pre_keyframe_->is_considered_) {
                associated_keyframes.emplace_back(associated_keyframes.back()->pre_keyframe_);
                associated_keyframes.back()->is_considered_ = true;
            }
        } else {
            break;
        }
    }

    spdlog::debug("newly added {} landmarks from temporal window, total landmark size is {}", cnt,
                  landmarks_out.size());

    // reset flags for keyframes and landmarks
    for (auto& keyfrm : associated_keyframes) {
        keyfrm->is_considered_ = false;
    }
    for (auto& lm : landmarks_out) {
        lm->is_considered_ = false;
    }

    return;
}

void univloc_mapping_module::send_to_server(unsigned int optimize_times)
{
    auto start = now();  // Time.now();

    spdlog::debug("Send local map and local keyframes to server!");
    {
        std::vector<data::landmark*> landmarks_out;
        std::vector<data::keyframe*> keyframes_out;

        if (optimize_times) {
            landmarks_out = map_db_->get_all_landmarks();
        } else {
            populate_sent_landmarks(landmarks_out);
        }
        populate_local_keyframes(keyframes_out);
        univloc_tracker::Client::get_instance().queue_send_map(landmarks_out, keyframes_out,
                                                               map_db_->get_erazed_redundant_landmarks_id(),
                                                               map_db_->get_erazed_redundant_keyframes_id());

        map_db_->clear_erazed_redundant_keyframes_id();

        map_db_->clear_erazed_redundant_landmarks_id();
    }

    auto end = now();

    spdlog::debug("Send msg to server cost time: {} ms ", duration_ms(start, end));
}

void univloc_mapping_module::populate_local_keyframes(std::vector<data::keyframe*>& keyframes_out)
{
    std::lock_guard<std::mutex> lock(mtx_keyfrm_queue_);

    // Get local keyframes of the current keyframe
    const auto curr_covisibilities = cur_keyfrm_->graph_node_->get_covisibilities();
    for (auto local_keyfrm : curr_covisibilities) {
        if (!local_keyfrm) {
            continue;
        }
        if (local_keyfrm->will_be_erased()) {
            continue;
        }
        keyframes_out.push_back(local_keyfrm);
    }
    keyframes_out.push_back(cur_keyfrm_);

    return;
}

data::keyframe* univloc_mapping_module::get_cur_keyframe() { return cur_keyfrm_; }

void univloc_mapping_module::pause_tracker()
{
    tracker_->request_pause();
    while (!tracker_->is_paused()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    spdlog::info("Tracking module has been paused!");
}

void univloc_mapping_module::resume_tracker() { tracker_->resume(); }

void univloc_mapping_module::reset()
{
    std::lock_guard<std::mutex> lock(mtx_reset_);
    spdlog::info("reset mapping module");
    keyfrms_queue_.clear();
    local_map_cleaner_->reset();
    univloc_tracker::Client::get_instance().clear_queue();
    reset_is_requested_ = false;
    bad_imu_to_reset_ = false;
}

void univloc_mapping_module::run()
{
    spdlog::info("start mapping module");

    is_terminated_ = false;
    double duration = EPSILON;

    timer_.setName("Mapping Module");
    timer_.start();
    while (true) {
        // waiting time for the other threads
        std::this_thread::sleep_for(std::chrono::milliseconds(5));

        timer_.startFirstProc("check termination, pause and reset");
        // LOCK
        set_keyframe_acceptability(false);

        // check if termination is requested
        if (terminate_is_requested()) {
            // terminate and break
            terminate();
            break;
        }

        // check if pause is requested
        if (pause_is_requested()) {
            bool mapped_new_keyframe = false;
            // if any keyframe is queued, all of them must be processed before the pause
            while (keyframe_is_queued()) {
                // create and extend the map with the new keyframe
                mapping_with_new_keyframe();
                // send the new keyframe to the global optimization module
                mapped_new_keyframe = true;
            }
            // pause and wait
            pause();
            // check if termination or reset is requested during pause
            while (is_paused() && !terminate_is_requested() && !reset_is_requested()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(3));
            }
            if (mapped_new_keyframe) {
                send_to_server();
            }
        }

        // check if reset is requested
        if (reset_is_requested()) {
            // reset, UNLOCK and continue
            reset();
            set_keyframe_acceptability(true);
            continue;
        }

        timer_.startNextProc("check keyframe list and do mapping");
        // if the queue is empty, the following process is not needed
        if (!keyframe_is_queued()) {
            // UNLOCK and continue
            set_keyframe_acceptability(true);
            continue;
        }

        // create and extend the map with the new keyframe
        mapping_with_new_keyframe();
        // send the new keyframe to the global optimization module, not needed in multi-slam system

        // remove_old_map();

        unsigned int optimize_times = 0;
        if (cur_keyfrm_->camera_->use_imu_) {
            update_imu_duration(duration);
            timer_.startNextProc("initialize imu");
            optimize_times = optimize_imu(duration);
        }

        timer_.startNextProc("send keyframe to server");
        send_to_server(optimize_times);

        set_keyframe_acceptability(true);

        timer_.endCycle();
        spdlog::debug("Local mapping successfully finished!");
    }
    timer_.finish();
    std::cout << timer_.result();

    spdlog::info("terminate mapping module");
}

void univloc_mapping_module::update_imu_duration(double& time_after_initializing)
{
    if (map_db_->get_num_keyframes() <= 2)
        return;

    data::keyframe* current = cur_keyfrm_;
    data::keyframe* previous = current->pre_keyframe_;
    data::keyframe* pre_previous = previous->pre_keyframe_;

    if (data::IMU_Preintegration::imu_initialize_times_ > 0) {
        double distance;
        distance = (previous->get_cam_center() - current->get_cam_center()).norm() +
                   (pre_previous->get_cam_center() - previous->get_cam_center()).norm();
        // Experience value from ORB3, only increase the time when movement of robot is large enough
        if (distance > 0.05) {
            time_after_initializing += current->timestamp_ - previous->timestamp_;
        }
        /*
            since we temporarily disable second and third time of imu init for non-monocular case,
            we need to set different threshold for different cases
        */
        int imu_initialize_times_thre;
        if (is_monocular_)
            imu_initialize_times_thre = 3;
        else
            imu_initialize_times_thre = 1;
        // use similar magic numbers as orb3
        if (data::IMU_Preintegration::imu_initialize_times_ < imu_initialize_times_thre &&
            time_after_initializing < TIME_AFTER_INITIALIZING_THR && distance < DISTANCE_THR) {
            spdlog::info("not enough motion for imu initializing, resetting system...");
            bad_imu_to_reset_ = true;
            // reset info will be sent to server and avoid any map merge of current map
            current->bad_imu_to_reset_ = true;
        }
    }

    return;
}

unsigned int univloc_mapping_module::optimize_imu(double& time_after_initializing)
{
    unsigned int optimize_times = 0;

    // first time IMU initialization, the weight of accelerator and gyro
    // are experience values from ORB_SLAM3
    if (data::IMU_Preintegration::imu_initialize_times_ == 0) {
        if (is_monocular_)
            initialize_imu(1.0e10, 1.0e2);
        else
            initialize_imu(1.0e5, 1.0e2);

        // in our current logic the cur_keyfrm_ won't change during IMU initialization
        // and since all the IMU related time parameters are experience value, it has
        // slight impact even the cur_keyfrm_ will be modified by other threads in future
        if (data::IMU_Preintegration::imu_initialize_times_ > 0) {
            time_after_initializing = cur_keyfrm_->timestamp_ - data::IMU_Preintegration::imu_initialize_timestamp_;
            spdlog::debug("initial imu time duration after first initializing: {}", time_after_initializing);
        }

        optimize_times++;
    }
    // second time IMU initialization, the weight of accelerator and gyro
    // are experience values from ORB_SLAM3
    else if (data::IMU_Preintegration::imu_initialize_times_ == 1 &&
        tracker_->tracking_state_ == tracker_state_t::Tracking) {
        if (time_after_initializing > 5.0 && time_after_initializing < 50.0) {
            if (is_monocular_) {
                initialize_imu(1.0e5, 1.0);
                optimize_times++;
            }
            /*
                temporarily disable second and third time of imu init
                for RGBD_Inertial and Stereo_Inertial due to pose jump
            else
                initialize_imu(1.0e5, 1.0);
            */
        }
    }
    // third time IMU initialization, the weight of accelerator and gyro
    // are experience values from ORB_SLAM3
    else if (data::IMU_Preintegration::imu_initialize_times_ == 2 &&
        tracker_->tracking_state_ == tracker_state_t::Tracking) {
        if (time_after_initializing > 15.0 && time_after_initializing < 50.0) {
            if (is_monocular_) {
                initialize_imu(0.0, 0.0);
                optimize_times++;
            }
            /*
                temporarily disable second and third time of imu init
                for RGBD_Inertial and Stereo_Inertial due to pose jump
            else
                initialize_imu(0.0, 0.0);
            */
        }
    }

    // scale refinement based on IMU
    // comment this part due to the result of scale refinement is really bad,
    // will enable it for future usage since the scale recovery in IMU initialization
    // is sometimes not enough. Then this part of code is needed in such cases.
    /*
    if (tracker_->tracking_state_ == tracker_state_t::Tracking &&
        data::IMU_Preintegration::imu_initialize_times_ > 0 &&
        is_monocular_ && (map_db_->get_num_keyframes() <= 200) &&
        ((time_after_initializing > 25.0 && time_after_initializing < 25.5) ||
        (time_after_initializing > 35.0 && time_after_initializing < 35.5) ||
        (time_after_initializing > 45.0 && time_after_initializing < 45.5))) {
        scale_refinement();
        optimize_times++;
    }
    */

    return optimize_times;
}

void univloc_mapping_module::initialize_imu(double acc_weight, double gyro_weight)
{
    spdlog::debug("{}: start imu initialization, times: {}", __func__, data::IMU_Preintegration::imu_initialize_times_);

    if (reset_is_requested())
        return;

    // stage 1:
    // check if the conditions to do imu initialization are satisfied
    // and construct the ordered vector of keyframes from current keyframe
    double min_startup_time;
    unsigned int min_startup_keyfrm_num;
    if (is_monocular_)
    {
        min_startup_time = 2.0;
        min_startup_keyfrm_num = 10;
    } else {
        min_startup_time = 1.0;
        min_startup_keyfrm_num = 10;
    }

    if (map_db_->get_num_keyframes() < min_startup_keyfrm_num)
        return;

    std::vector<data::keyframe*> keyfrms_to_initialize;
    data::keyframe* keyframe_item = cur_keyfrm_;
    while (keyframe_item->pre_keyframe_) {
        keyfrms_to_initialize.emplace_back(keyframe_item);
        keyframe_item = keyframe_item->pre_keyframe_;
    }
    keyfrms_to_initialize.emplace_back(keyframe_item);
    std::reverse(keyfrms_to_initialize.begin(), keyfrms_to_initialize.end());

    double first_keyfrm_timestamp = keyfrms_to_initialize.front()->timestamp_;
    if (keyfrms_to_initialize.back()->timestamp_ - first_keyfrm_timestamp < min_startup_time)
        return;

    KeyframeID max_keyfrm_id;
    auto keyframe_compare = [](const data::keyframe* a, const data::keyframe* b) { return a->id_ < b->id_; };
    auto max_keyfrm_iterator = std::max_element(keyfrms_to_initialize.begin(), keyfrms_to_initialize.end(),
                                                keyframe_compare);
    unsigned int max_index = std::abs(std::distance(keyfrms_to_initialize.begin(), max_keyfrm_iterator));
    if (max_index != keyfrms_to_initialize.size() - 1) {
        spdlog::warn("The last keyframe in vector doesn't have the max ID!");
        spdlog::warn("Vector size: {}, max ID index: {}", keyfrms_to_initialize.size(), max_index);
        return;
    } else {
        max_keyfrm_id = (*max_keyfrm_iterator)->id_;
        spdlog::debug("Vector size: {}, max ID: {}", keyfrms_to_initialize.size(), max_keyfrm_id);
    }

    data::IMU_Preintegration::IMU_State last_imu_state = data::IMU_Preintegration::state_;
    data::IMU_Preintegration::set_imu_state(data::IMU_Preintegration::IMU_State::Initializing);

    // stage 2:
    // compute the initial value of keyframe velocities and rotation matrix
    // between the imu and world coordinate
    if (data::IMU_Preintegration::imu_initialize_times_ == 0) {
        Vec3_t  direction_gravity;
        direction_gravity.setZero();

        for (auto& keyfrm : keyfrms_to_initialize) {
            auto keyfrm_preintegration = keyfrm->get_imu_constraint().second;
            if (!keyfrm_preintegration) {
                spdlog::debug("keyframe {}: doesn't have preintegration in constraint pair", keyfrm->id_);
                continue;
            }

            if (!keyfrm->pre_keyframe_)
                continue;

            direction_gravity -= keyfrm->pre_keyframe_->get_imu_rotation() *
                                 keyfrm_preintegration->get_updated_delta_velocity();
            double delta_time = keyfrm->timestamp_ - keyfrm->pre_keyframe_->timestamp_;
            Vec3_t velocity = (keyfrm->get_imu_position() - keyfrm->pre_keyframe_->get_imu_position()) / delta_time;
            keyfrm->set_imu_velocity(velocity);
            keyfrm->pre_keyframe_->set_imu_velocity(velocity);
        }

        direction_gravity = direction_gravity / direction_gravity.norm();
        Vec3_t gI(0.0, 0.0, -1.0);
        Vec3_t v = gI.cross(direction_gravity);
        const double nv = v.norm();
        const double cosg = gI.dot(direction_gravity);
        const double ang = acos(cosg);
        Vec3_t vzg = v * ang / nv;
        Rwi_ = exp_so3(vzg);
        data::IMU_Preintegration::imu_initialize_timestamp_ = first_keyfrm_timestamp;
    } else {
        Rwi_ = Mat33_t::Identity();
        bias_acc_ = keyfrms_to_initialize.back()->get_imu_bias().head(3);
        bias_gyro_ = keyfrms_to_initialize.back()->get_imu_bias().tail(3);
    }

    // stage 3:
    // do inertial-only optimization
    scale_ = 1.0;
    optimize::inertial_only_optimize(keyfrms_to_initialize, max_keyfrm_id, Rwi_, scale_, bias_acc_, bias_gyro_,
                                          is_monocular_, acc_weight, gyro_weight);

    // stage 4:
    // if scale isn't too small, then apply scale rotation
    // for keyframes and landmarks in map database
    if (scale_ < 0.1) {
        spdlog::info("scale: {} is too small after inertial-only optimization", scale_);
        data::IMU_Preintegration::set_imu_state(last_imu_state);
        return;
    }

    spdlog::info("{}: after inertial only optimization, scale is {}", __func__, scale_);
    spdlog::info("{}: after inertial only optimization, Rwi_ is \n{}", __func__, Rwi_);
    if (fabs(scale_ - 1.0) > EPSILON || !is_monocular_) {
        Mat44_t Twi = Mat44_t::Identity();
        Twi.block(0, 0, 3, 3) = Rwi_.transpose();
        std::scoped_lock<std::mutex> lock(data::map_database::mtx_database_);
        map_db_->apply_scaled_rotation(Twi, scale_);
        tracker_->align_state_to_inertial_frame(Rwi_.transpose(), scale_);
    }

    if (data::IMU_Preintegration::imu_initialize_times_ == 0) {
        for (auto& keyfrm : keyfrms_to_initialize)
            keyfrm->imu_is_initialized_ = true;
        data::IMU_Preintegration::imu_initialize_times_ = 1;
    }

    // stage 5:
    // do visual-inertial optimization
    spdlog::debug("{}: before visual inertial optimization", __func__);
    if (acc_weight > EPSILON) {
        optimize::visual_inertial_optimize(map_db_, max_keyfrm_id, 100, is_monocular_, true,
                                                acc_weight, gyro_weight);
    } else {
        optimize::visual_inertial_optimize(map_db_, max_keyfrm_id, 100, is_monocular_, false);
    }
    spdlog::debug("{}: after visual inertial optimization", __func__);

    // stage 6:
    // clean the remaining keyframes in keyfrms_queue_ and map/bow database (if needed)
    // then set related status flag
    {
        std::scoped_lock<std::mutex> lock(mtx_keyfrm_queue_);
        while (!keyfrms_queue_.empty()) {
            data::keyframe* temp_keyfrm;
            temp_keyfrm = keyfrms_queue_.front();
            keyfrms_queue_.pop_front();

            // in our current logic, such keyframes won't be in the database
            // but delete them from map/bow database for future needs
            bow_db_->erase_keyframe(temp_keyfrm);
            map_db_->erase_keyframe_from_id(temp_keyfrm->id_);
        }
    }

    if (last_imu_state != data::IMU_Preintegration::IMU_State::Not_Initialized) {
        data::IMU_Preintegration::imu_initialize_times_++;
    }
    data::IMU_Preintegration::set_imu_state(data::IMU_Preintegration::IMU_State::Initialized);

    spdlog::debug("{}: finish imu initialization, times: {}", __func__, data::IMU_Preintegration::imu_initialize_times_);
    return;
}

void univloc_mapping_module::scale_refinement()
{
    if (reset_is_requested())
        return;

    // stage 1:
    // construct the ordered vector of keyframes from current keyframe
    std::vector<data::keyframe*> keyfrms_to_initialize;
    data::keyframe* keyframe_item = cur_keyfrm_;
    while (keyframe_item->pre_keyframe_) {
        keyfrms_to_initialize.emplace_back(keyframe_item);
        keyframe_item = keyframe_item->pre_keyframe_;
    }
    keyfrms_to_initialize.emplace_back(keyframe_item);
    std::reverse(keyfrms_to_initialize.begin(), keyfrms_to_initialize.end());

    KeyframeID max_keyfrm_id;
    auto keyframe_compare = [](const data::keyframe* a, const data::keyframe* b) { return a->id_ < b->id_; };
    auto max_keyfrm_iterator = std::max_element(keyfrms_to_initialize.begin(), keyfrms_to_initialize.end(),
                                                keyframe_compare);
    unsigned int max_index = std::abs(std::distance(keyfrms_to_initialize.begin(), max_keyfrm_iterator));
    if (max_index != keyfrms_to_initialize.size() - 1) {
        spdlog::warn("The last keyframe in vector doesn't have the max ID!");
        spdlog::warn("Vector size: {}, max ID index: {}", keyfrms_to_initialize.size(), max_index);
        return;
    } else {
        max_keyfrm_id = (*max_keyfrm_iterator)->id_;
        spdlog::debug("Vector size: {}, max ID: {}", keyfrms_to_initialize.size(), max_keyfrm_id);
    }

    data::IMU_Preintegration::IMU_State last_imu_state = data::IMU_Preintegration::state_;
    data::IMU_Preintegration::set_imu_state(data::IMU_Preintegration::IMU_State::Initializing);

    // stage 2:
    // do inertial-only optimization
    Rwi_ = Mat33_t::Identity();
    scale_ = 1.0;
    optimize::inertial_only_optimize(map_db_, max_keyfrm_id, Rwi_, scale_);

    // stage 3:
    // if scale isn't too small, then apply scale rotation
    // for keyframes and landmarks in map database
    if (scale_ < 0.1) {
        spdlog::info("scale: {} is too small after inertial-only optimization", scale_);
        data::IMU_Preintegration::set_imu_state(last_imu_state);
        return;
    }

    spdlog::info("{}: after inertial only optimization, scale is {}", __func__, scale_);
    if (fabs(scale_ - 1.0) > EPSILON || !is_monocular_) {
        Mat44_t Twi = Mat44_t::Identity();
        Twi.block(0, 0, 3, 3) = Rwi_.transpose();
        std::scoped_lock<std::mutex> lock(data::map_database::mtx_database_);
        map_db_->apply_scaled_rotation(Twi, scale_);
        tracker_->align_state_to_inertial_frame(Rwi_.transpose(), scale_);
    }

    // stage 4:
    // clean the remaining keyframes in keyfrms_queue_ and map/bow database (if needed)
    // then set related status flag
    {
        std::scoped_lock<std::mutex> lock(mtx_keyfrm_queue_);
        while (!keyfrms_queue_.empty()) {
            data::keyframe* temp_keyfrm;
            temp_keyfrm = keyfrms_queue_.front();
            keyfrms_queue_.pop_front();

            // in our current logic, such keyframes won't be in the database
            // but delete them from map/bow database for future needs
            bow_db_->erase_keyframe(temp_keyfrm);
            map_db_->erase_keyframe_from_id(temp_keyfrm->id_);
        }
    }

    return;
}

void univloc_mapping_module::remove_old_map()
{
    if (10 < map_db_->get_num_keyframes() && abort_local_BA_ == false &&
        cur_keyfrm_->id_ - map_db_->origin_keyfrm_->id_ >= keyframes_num_for_initializing_imu_ &&
        !cur_keyfrm_->should_be_fixed_in_optimization_) {
        if (!cur_keyfrm_->camera_->use_imu_ ||
            data::IMU_Preintegration::state_ != data::IMU_Preintegration::IMU_State::Not_Initialized)
            map_db_->remove_old_map();
    }
}

}  // namespace openvslam
