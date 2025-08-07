// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <spdlog/spdlog.h>

#include <chrono>
#include <unordered_map>

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
#include "tracker/Client.h"
#include "timing.h"

#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc_c.h>
#include <opencv2/imgproc/imgproc.hpp>

#include "univloc_tracking_module.h"

#define INIT_RETRY_THR     5.0
#define GUI_QUEUE_SIZE     1000
#define INIT_ACCEL_THR     0.5

// Time (seconds) of using odom/imu to sustain when visual tracking lost
#define ODOM_SUSTAIN_TIME  5.0
#define IMU_SUSTAIN_TIME   0.5

namespace openvslam {

univloc_tracking_module::univloc_tracking_module(std::shared_ptr<univloc_tracker::Config> cfg,
                                                 camera::base* camera, const ClientID client_id,
                                                 data::map_database* map_db, data::bow_database* bow_db,
                                                 FeatureQueue& feature_queue, RequestQueue& result_queue,
                                                 RequestQueue& reconstruction_queue)
    : tracking_module(cfg, camera, map_db, bow_db),
      feature_queue_(feature_queue),
      result_queue_(result_queue),
      reconstruction_queue_(reconstruction_queue),
      client_id_(client_id),
      timestamp_recently_lost_(0)
{
    spdlog::debug("CONSTRUCT: univloc_tracking_module");
    if (cfg_->gui_) {
        // It takes few seconds to create a window that will be used later as a placeholder for cv::imshow
        spdlog::debug("Creating CV window...");
        cv::namedWindow("keypoints", 1);
        spdlog::debug("Finish creating CV window...");
        gui_queue_ = std::make_unique<VisualizationFrameQueue>(GUI_QUEUE_SIZE);
    }
    switch (tracker_mode_) {
        case tracker_mode_t::Remapping:
        case tracker_mode_t::Mapping:
            tracker_func_mode_ = &univloc_tracking_module::track;
            break;
        case tracker_mode_t::Localization:
            tracker_func_mode_ = &univloc_tracking_module::localization_track;
            break;
        case tracker_mode_t::Relocalization:
            tracker_func_mode_ = &univloc_tracking_module::relocalization_mode;
            break;
        case tracker_mode_t::None:
            throw std::invalid_argument("Invalid mode. Available values: mapping, localization, relocalization");
    }

    num_tracked_lms_thr_ = camera_->use_imu_ ? 10 : 20;
    num_tracked_lms_thr_ = cfg_->use_odom_ && tracker_mode_ == tracker_mode_t::Localization? num_tracked_lms_thr_ / 2 : num_tracked_lms_thr_;

    if (tracker_mode_ == tracker_mode_t::Mapping || tracker_mode_ == tracker_mode_t::Remapping) {
        if (cfg_->use_odom_ && !camera_->use_imu_) {
            track_trans_state_func_ = &univloc_tracking_module::track_trans_state_odom;
        }
        else if (!cfg_->use_odom_ && camera_->use_imu_) {
            track_trans_state_func_ = &univloc_tracking_module::track_trans_state_imu;
        }
        else if (!cfg_->use_odom_ && !camera_->use_imu_) {
            track_trans_state_func_ = &univloc_tracking_module::track_trans_state_basic;
        }
        // we don't support IMU and odometry fusion currently,
        // will fall back to only use odometry as a workaround
        else {
            spdlog::error("Doesn't support IMU and odometry fusion now, will fall back to odom only!");
            track_trans_state_func_ = &univloc_tracking_module::track_trans_state_odom;
        }
    } else if (tracker_mode_ == tracker_mode_t::Localization) {
        if (cfg_->use_odom_) {
            track_trans_state_func_ = &univloc_tracking_module::localization_track_trans_state_odom;
        } else {
            track_trans_state_func_ = &univloc_tracking_module::localization_track_trans_state_basic;
        }
    } else {
        track_trans_state_func_ = &univloc_tracking_module::track_trans_state_basic;
    }

    if (cfg_->use_odom_)
        track_server_localization_ = &univloc_tracking_module::track_server_map_with_odom;
    else
        track_server_localization_ = &univloc_tracking_module::track_server_map;
}

univloc_tracking_module::~univloc_tracking_module()
{
    spdlog::debug("DESTRUCT: univloc_tracking_module");
}

bool univloc_tracking_module::track_current_frame()
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
            if (cfg_->lidar_enable_) {
                succeeded = frame_tracker_.lidar_based_track(*curr_frm_, *last_frm_, velocity_, *last_lidar_frm_, cfg_->tf_lidar_camera_);
                if (!succeeded) {
                    succeeded = frame_tracker_.motion_based_track(*curr_frm_, *last_frm_, velocity_);
                    lidar_pose_failure_count_++;
                }
            } else {
                succeeded = frame_tracker_.motion_based_track(*curr_frm_, *last_frm_, velocity_);
            }
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

int univloc_tracking_module::get_lidar_pose_failure_count()
{
    return lidar_pose_failure_count_;
}

bool univloc_tracking_module::is_coordinate_aligned() const { return coordinate_aligned_; }

void univloc_tracking_module::set_coordinate_aligned(bool val) { coordinate_aligned_ = val; }

void univloc_tracking_module::run()
{
    std::pair<std::shared_ptr<ImageFrame>, std::shared_ptr<data::frame>> input;
    timer_.setName("Tracking Module");
    timer_.start();
    while (true) {
        timer_.startFirstProc("wait for new frame");
        if (!feature_queue_.wait_pop(input)) break;
        curr_frm_ = input.second;
        process_current_frame();
        if (tracking_state_ == tracker_state_t::Tracking || tracking_state_ == tracker_state_t::RecentlyLost) {
            input.first->maybe_pose = curr_frm_->cam_pose_cw_;
            if (cfg_->need_covariance_) input.first->maybe_covariance = curr_frm_->covariance_matrix_;
        } else {
            input.first->maybe_pose = std::nullopt;
            if (cfg_->need_covariance_) {
                Mat66_t cov = Mat66_t::Identity();
                cov.diagonal() *= 1000.0; // use a large number to indicate tracking lost
                input.first->maybe_covariance = cov;
            }
        }
        if (!result_queue_.force_push(input.first)) break;
        if (cfg_->enable_fast_mapping_) {
            if (!reconstruction_queue_.force_push(input.first)) break;
        }

        timer_.endCycle();
    }
    if (cfg_->gui_)
        gui_queue_->close();
    timer_.finish();
    std::cout << timer_.result();
}

void univloc_tracking_module::process_current_frame()
{
    const auto start = std::chrono::system_clock::now();

    // determine if relocalization is needed
    if (camera_->setup_type_ == openvslam::camera::setup_type_t::Monocular &&
        tracker_mode_ == tracker_mode_t::Mapping && cfg_->initialize_by_server_ && is_initializing()) {
        // add current frame to keyframe db to enable requesting relocalization at server
        auto reloc_result = univloc_tracker::Client::get_instance().get_relocalization_results();
        if (reloc_result) {
            // proceed with initializaiton
            timer_.startNextProc("initialize with relocalization");
            spdlog::debug("Start initializing with relocalization!!!!!!!!");
            auto keyframe_msg = reloc_result->keyframes[0];

            // use id to obtain frame and keyframe that are to be relocalized
            std::pair<data::keyframe*, std::shared_ptr<data::frame>> frm_and_keyfrm;
            bool found = get_frm_and_keyfrm(keyframe_msg.mn_id, frm_and_keyfrm);
            if (!found) {
                spdlog::error("Do not find keyframe to be relocalized!");
                return;
            }
            spdlog::debug("Found keyframe to be relocalized!!!!!");
            data::keyframe* p_keyframe = frm_and_keyfrm.first;
            std::shared_ptr<data::frame> p_frame = frm_and_keyfrm.second;
            spdlog::debug("found frame id is {}", p_frame->id_);

            // update pose and landmark
            update_frm_and_keyfrm_using_relocalization(p_keyframe, p_frame, reloc_result);
            monocular_initialization_using_relocalization(p_keyframe, p_frame);
        } else {  // request relocalization
            request_relocalization_from_server();
        }
        return;
    }

    spdlog::debug("feeding new frame! newly creately frame id is {}", curr_frm_->id_);
    std::invoke(tracker_func_mode_, this);

    queue_visualization_frames();

    const auto end = std::chrono::system_clock::now();
    elapsed_ms_ = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
}

void univloc_tracking_module::reset()
{
    spdlog::info("resetting system");
    if (camera_->use_imu_) data::IMU_Preintegration::reset();
    initializer_.reset();
    keyfrm_inserter_.reset();

    mapper_->request_reset();

    bow_db_->clear();
    map_db_->clear();

    tracking_state_ = tracker_state_t::NotInitialized;

    tracked_server_landmarks_.clear();
    // clear queue
    clear_frms_and_keyfrms_to_be_relocalized();
    univloc_tracker::Client::get_instance().clear_relocalization_results();
    if (camera_->use_imu_) imu_mearsurement_vec_.clear();
    // when the system resets, the new coordinate doesn't align with the global map
    coordinate_aligned_ = false;
}

bool univloc_tracking_module::search_server_landmarks()
{
    const static unsigned int min_server_landmarks_num = 100;

    // if (server_landmarks.empty()) return false;
    bool found_proj_candidate = false;
    // temporary variables
    Vec2_t reproj;
    float x_right;
    unsigned int pred_scale_level, observed_server_landmarks_num = 0;

    // Get server landmarks from database
    std::vector<std::shared_ptr<data::landmark>> server_landmarks = map_db_->get_server_landmarks();

    if (server_landmarks.size() < min_server_landmarks_num) {
        spdlog::debug("Not enougn server landmarks for tracking! only {} server landmarks", server_landmarks.size());
        return false;
    }
    spdlog::debug("Get {} server landmarks for tracking!", server_landmarks.size());

    std::vector<data::landmark*> nearby_landmarks;
    nearby_landmarks.resize(server_landmarks.size());
    int idx = -1;

    for (auto lm : server_landmarks) {
        idx++;
        nearby_landmarks[idx] = nullptr;

        if (unlikely(lm->will_be_erased())) continue;

        // check the observability
        if (curr_frm_->can_observe(lm.get(), 0.5, reproj, x_right, pred_scale_level)) {
            // pass the temporary variables
            lm->reproj_in_tracking_ = reproj;
            lm->x_right_in_tracking_ = x_right;
            lm->scale_level_in_tracking_ = pred_scale_level;

            // this landmark is observable from the current frame
            lm->increase_num_observable();

            found_proj_candidate = true;

            nearby_landmarks[idx] = lm.get();

            observed_server_landmarks_num++;

            lm->out_of_local_map_times_ = 0;
            lm->is_observable_in_tracking_ = true;
        } else {
            lm->is_observable_in_tracking_ = false;
        }
    }

    if (unlikely(!found_proj_candidate)) {
        spdlog::debug("Unable to find projection candidate!");
        return false;
    }

    // acquire more 2D-3D matches by projecting the local landmarks to the current frame
    match::projection projection_matcher(0.8);
    const float margin = (curr_frm_->id_ < last_reloc_frm_id_ + 2)
                             ? 20.0
                             : camera_setup_type_margin_;

    unsigned int matched_num = projection_matcher.match_frame_and_landmarks(*curr_frm_, nearby_landmarks, margin);

    spdlog::debug(" {} of {} server landmarks are observed when tracking server map", observed_server_landmarks_num,
                  server_landmarks.size());

    spdlog::debug(" {} of {} server landmarks are succesfully matched ", matched_num, nearby_landmarks.size());

    return matched_num > min_matched_num_thr_;
}

void univloc_tracking_module::count_valid_tracked_server_landmarks()
{
    tracked_server_landmarks_position_.clear();
    for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
        auto lm = curr_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }

        if (!curr_frm_->outlier_flags_.at(idx)) {
            assert(lm->come_from_server());

            auto lm_ptr = map_db_->get_server_landmark(lm->id_);
            assert(lm_ptr);
            // tracked_server_landmarks_[lm_ptr->id_] = lm_ptr;
            lm_ptr->set_existed_in_tracking(true);
            tracked_server_landmarks_position_.push_back(lm_ptr->get_pos_in_world());
            // the observation has been considered as inlier in the pose optimization
            // count up

            // understand better about this part!
            // Got it! not from server is good! change this!
            // need to change later!

            // ++num_tracked_lms_;
            // if (lm->get_num_observed() == 0) new_tracked_server_lms_num++;

            // // increment the number of tracked frame
            // lm->increase_num_observed();

        } else {
            // the observation has been considered as outlier in the pose optimization
            // remove the observation
            curr_frm_->landmarks_.at(idx) = nullptr;
        }
    }

    if (!tracked_server_landmarks_position_.empty())
        tracked_server_landmarks_position_.push_back(curr_frm_->get_cam_center());
}

bool univloc_tracking_module::optimize_current_frame_with_server_map()
{
    std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);

    spdlog::debug("optimize_current_frame_with_server_map");

    search_server_landmarks();
    // optimize the pose
    pose_optimizer_.optimize(*curr_frm_);

    // count up the number of tracked landmarks
    unsigned int new_tracked_server_lms_num = 0;
    num_tracked_lms_ = 0;
    num_tracked_server_lms_ = 0;
    for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
        auto lm = curr_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }

        if (!curr_frm_->outlier_flags_.at(idx)) {
            assert(lm->come_from_server());

            auto lm_ptr = map_db_->get_server_landmark(lm->id_);
            assert(lm_ptr);
            ++num_tracked_server_lms_;
            tracked_server_landmarks_[lm_ptr->id_] = lm_ptr;
            lm_ptr->set_existed_in_tracking(true);
            tracked_server_landmarks_position_.push_back(lm_ptr->get_pos_in_world());
            // the observation has been considered as inlier in the pose optimization
            // count up

            // understand better about this part!
            // Got it! not from server is good! change this!
            // need to change later!

            ++num_tracked_lms_;
            if (lm->get_num_observed() == 0) new_tracked_server_lms_num++;

            // increment the number of tracked frame
            lm->increase_num_observed();

        } else {
            // the observation has been considered as outlier in the pose optimization
            // remove the observation
            curr_frm_->landmarks_.at(idx) = nullptr;
        }
    }

    if (!tracked_server_landmarks_position_.empty())
        tracked_server_landmarks_position_.push_back(curr_frm_->get_cam_center());

    // this valid number is 0
    spdlog::info("valid tracked server landmarks num: {} ", num_tracked_lms_);

    // omit relocalization check for server map tracking
    /*
    // if recently relocalized, use the more strict threshold
    if (curr_frm_->id_ < last_reloc_frm_id_ + camera_->fps_ && num_tracked_lms_ < 2 * num_tracked_lms_thr) {
        spdlog::debug("server map tracking failed: {} matches < {}", num_tracked_lms_, 2 * num_tracked_lms_thr);
        tracked_server_landmarks_.clear();
        return false;
    }
    */

    // check the threshold of the number of tracked landmarks
    // relax the check during localization when using odom
    if (num_tracked_lms_ < num_tracked_lms_thr_) {
        spdlog::debug("server map tracking failed: {} matches < {}", num_tracked_lms_, num_tracked_lms_thr_);
        tracked_server_landmarks_.clear();
        return false;
    }

    spdlog::info("Successfully tracked server map!");

    return true;
}

void univloc_tracking_module::update_frm_and_keyfrm_using_relocalization(data::keyframe* p_keyframe, std::shared_ptr<data::frame> p_frame,
                                                                 univloc_msgs::MapConstPtr map_msg_ptr)
{
    assert(p_keyframe);

    //! processing keyframe message!
    assert(map_msg_ptr->keyframes.size() == 1);
    std::fill(p_frame->landmarks_.begin(), p_frame->landmarks_.end(), nullptr);
    auto keyframe_msg = map_msg_ptr->keyframes[0];
    // process pose data
    Eigen::Matrix4d cam_pose_cw;
    for (int idx = 0; idx < cam_pose_cw.rows(); ++idx)
        for (int idy = 0; idy < cam_pose_cw.cols(); ++idy)
            cam_pose_cw(idx, idy) = keyframe_msg.mv_pose[idx * cam_pose_cw.rows() + idy];
    std::cout << cam_pose_cw << std::endl << "received camera pose!" << std::endl;
    p_keyframe->set_cam_pose(cam_pose_cw);
    // may cause problem
    spdlog::info("updated keyframe from relocalization result");
    int update_size = 0, new_size = 0;
    uint mp_size = map_msg_ptr->landmarks.size();
    for (uint idx = 0; idx < mp_size; ++idx) {
        auto landmark_msg = map_msg_ptr->landmarks[idx];
        if (!map_msg_ptr->only_add_landmarks &&
            (landmark_msg.mn_observed_in_other_keyframe_id > 0 || landmark_msg.mn_replace_other_id > 0))
            continue;

        if (map_db_->get_landmark(landmark_msg.mn_id)) continue;

        std::shared_ptr<Landmark> ptr_server_landmark = map_db_->get_server_landmark(landmark_msg.mn_id);
        if (ptr_server_landmark) {
            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                  (double)landmark_msg.mv_position[2]);
            ptr_server_landmark->set_existed_in_server_map(true);
            ptr_server_landmark->set_pos_in_world(pos_w);
            ptr_server_landmark->set_not_new_created();
            // TODO : update descriptor, may no need.
            update_size++;
            ptr_server_landmark->set_update_from_server(true);
            if (landmark_msg.mn_observed_in_other_keyframe_index < p_keyframe->num_keypts_) {
                p_keyframe->add_landmark(ptr_server_landmark.get(), landmark_msg.mn_observed_in_other_keyframe_index);
                ptr_server_landmark->add_observation(p_keyframe, landmark_msg.mn_observed_in_other_keyframe_index,
                                                     true);
                // set the 2D-3D assocications to the current frame
                p_frame->landmarks_.at(landmark_msg.mn_observed_in_other_keyframe_index) = ptr_server_landmark.get();
                p_frame->outlier_flags_.at(landmark_msg.mn_observed_in_other_keyframe_index) = false;
            }
        } else {
            cv::Mat descriptor(1, landmark_msg.mv_descriptors[0].m_descriptor.size(), CV_8UC1,
                               landmark_msg.mv_descriptors[0].m_descriptor.data());
            Eigen::Vector3d pos_w((double)landmark_msg.mv_position[0], (double)landmark_msg.mv_position[1],
                                  (double)landmark_msg.mv_position[2]);
            Eigen::Vector3d mean_normal((double)landmark_msg.mv_normal_vector[0],
                                        (double)landmark_msg.mv_normal_vector[1],
                                        (double)landmark_msg.mv_normal_vector[2]);

            data::landmark* p_landmark = new data::landmark(landmark_msg.mn_id, landmark_msg.mn_client_id, pos_w,
                                                            descriptor, landmark_msg.mf_max_distance,
                                                            landmark_msg.mf_min_distance, mean_normal, map_db_, true);

            p_landmark->set_ref_keyframe(p_keyframe);
            p_landmark->set_not_new_created();

            new_size++;
            // p_landmark->set_update_from_server(true);
            if (landmark_msg.mn_observed_in_other_keyframe_index < p_keyframe->num_keypts_) {
                p_keyframe->add_landmark(p_landmark, landmark_msg.mn_observed_in_other_keyframe_index);
                p_landmark->add_observation(p_keyframe, landmark_msg.mn_observed_in_other_keyframe_index, true);
                // set the 2D-3D assocications to the current frame
                p_frame->landmarks_.at(landmark_msg.mn_observed_in_other_keyframe_index) = p_landmark;
                p_frame->outlier_flags_.at(landmark_msg.mn_observed_in_other_keyframe_index) = false;
            }

            auto lm_desc = p_landmark->get_descriptor();
            assert(!lm_desc.ptr<uint32_t>());

            if (tracker_mode_ == tracker_mode_t::Localization) {
                std::shared_ptr<Landmark> ptr_server_lm(p_landmark);
                map_db_->add_server_landmark(ptr_server_lm);
            } else {
                map_db_->add_landmark(p_landmark);
            }
        }
    }
    p_frame->set_cam_pose(p_keyframe->get_cam_pose());
    p_frame->ref_keyfrm_ = p_keyframe;

    spdlog::info("created {} landmarks from relocalization result", new_size);
}

bool univloc_tracking_module::track_server_map()
{
    bool succeeded = false;
    auto track_motion_start = now();
    succeeded = frame_tracker_.motion_based_track(*curr_frm_, *last_frm_, velocity_);
    auto track_motion_end = now();
    spdlog::debug("motion model cost time {} ms", duration_ms(track_motion_end - track_motion_start));

    if (succeeded) {
        spdlog::debug("motion model match based track server virtual keyframe success!");
        return true;
    } else {
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
        spdlog::debug("motion model match based track server virtual keyframe fail!");
    }

    data::keyframe* virtual_server_keyframe = map_db_->get_server_virtual_keyframe();

    if (!virtual_server_keyframe) {
        spdlog::debug("There is not containing virtual keyframe!");
        return false;
    }
    auto track_bow_start = now();
    succeeded = frame_tracker_.bow_match_based_track(*curr_frm_, *last_frm_, virtual_server_keyframe);
    auto track_bow_end = now();
    spdlog::debug("bow model cost time {} ms", duration_ms(track_bow_end - track_bow_start));

    if (succeeded) {
        count_valid_tracked_server_landmarks();
        spdlog::debug("bow match based track server virtual keyframe success!");
        return true;
    } else {
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
        spdlog::debug("bow match_based track server virtual keyframe failed!");
    }

    auto track_robust_start = now();
    succeeded = frame_tracker_.robust_match_based_track(*curr_frm_, *last_frm_, virtual_server_keyframe);
    auto track_robust_end = now();
    spdlog::debug("robust model cost time {} ms", duration_ms(track_robust_end - track_robust_start));

    if (succeeded) {
        count_valid_tracked_server_landmarks();
        spdlog::debug("robust match based track server virtual keyframe success!");
        return true;
    } else {
        spdlog::debug("robust match based track server virtual keyframe failed!");
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
    }

    return false;
}

/*
    In case all prior track-based methods (motion, odom, bow) fail,
    the probability for robust match to be positive is really low
    compared to the performance cost when using odom. The system
    will rely on odom data until enough visual features are found to
    switch back to visual tracking.
*/
bool univloc_tracking_module::track_server_map_with_odom()
{
    auto track_odom_start = now();
    bool succeeded = false;
    Mat44_t relative_transform_from_odom;
    get_relative_transform_from_odom(relative_transform_from_odom);
    Mat44_t odom_predict_pose = relative_transform_from_odom * first_valid_pose_;

    succeeded = frame_tracker_.odom_based_track(*curr_frm_, *last_frm_, odom_predict_pose);

    auto track_odom_end = now();
    spdlog::debug("odom model cost time {} ms", duration_ms(track_odom_end - track_odom_start));
    if (succeeded) {
        spdlog::debug("odom model tracking success!");
        return true;
    } else {
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
        spdlog::debug("odom model match based track server virtual keyframe fail!");
    }
    auto track_motion_start = now();
    succeeded = frame_tracker_.motion_based_track(*curr_frm_, *last_frm_, velocity_);
    auto track_motion_end = now();
    spdlog::debug("motion model cost time {} ms", duration_ms(track_motion_end - track_motion_start));

    if (succeeded) {
        spdlog::debug("motion model match based track server virtual keyframe success!");
        return true;
    } else {
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
        spdlog::debug("motion model match based track server virtual keyframe fail!");
    }

    data::keyframe* virtual_server_keyframe = map_db_->get_server_virtual_keyframe();

    if (!virtual_server_keyframe) {
        spdlog::debug("There is not containing virtual keyframe!");
        return false;
    }
    auto track_bow_start = now();
    succeeded = frame_tracker_.bow_match_based_track(*curr_frm_, *last_frm_, virtual_server_keyframe);
    auto track_bow_end = now();
    spdlog::debug("bow model cost time {} ms", duration_ms(track_bow_end - track_bow_start));

    if (succeeded) {
        count_valid_tracked_server_landmarks();
        spdlog::debug("bow match based track server virtual keyframe success!");
        return true;
    } else {
        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);
        spdlog::debug("bow match_based track server virtual keyframe failed!");
    }

    return false;
}

void univloc_tracking_module::relocalization_mode() {
    // Lock the map database
    {
        std::scoped_lock<std::mutex> lock(data::map_database::mtx_database_);
        if (univloc_tracker::Client::get_instance().get_relocalization_results()) relocal_num_++;
    }
    request_relocalization_from_server();
    frms_sent_for_relocalization_++;
    spdlog::info("Sent frame {} to server for relocalization.", curr_frm_->id_);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    last_frm_ = curr_frm_;
    spdlog::info("Relocalization success -- relocal request number: {}, relocal success number: {}",
                 frms_sent_for_relocalization_, relocal_num_);
}

void univloc_tracking_module::request_relocalization_from_server()
{
    // request relocalization from server
    auto request_frame = curr_frm_;
    auto frame_to_be_relocalized = std::make_shared<data::frame>(*request_frame);
    auto keyfrm_to_be_relocalized = new (std::nothrow) data::keyframe(*request_frame, map_db_, bow_db_);
    if (unlikely(!keyfrm_to_be_relocalized)) {
        spdlog::warn("{}: failed to allocate memory for keyfrm_to_be_relocalized pointer!", __func__);
        return;
    }

    if (cfg_->use_odom_) {
        keyfrm_to_be_relocalized->odom_ = frame_to_be_relocalized->odom_;
    }
    frame_to_be_relocalized->compute_bow();
    keyfrm_to_be_relocalized->compute_bow();
    spdlog::debug("Relocalize send keyframe id is {}, landmark size: {}", keyfrm_to_be_relocalized->id_,
                  keyfrm_to_be_relocalized->get_landmarks().size());
    univloc_tracker::Client::get_instance().send_relocalization_request_to_server(keyfrm_to_be_relocalized);

    // enqueue the frame and keyframe
    queue_frm_and_keyfrm_to_be_relocalized(keyfrm_to_be_relocalized, frame_to_be_relocalized);
}

bool univloc_tracking_module::retrieve_relocalization_result() {
    auto reloc_result = univloc_tracker::Client::get_instance().get_relocalization_results();
    if (reloc_result) {
        // proceed with initializaiton
        spdlog::debug("Relocalization Success!!!!!!!!");
        auto keyframe_msg = reloc_result->keyframes[0];

        // use id to obtain frame and keyframe that are to be relocalized
        std::pair<data::keyframe*, std::shared_ptr<data::frame>> frm_and_keyfrm;
        bool found = get_frm_and_keyfrm(keyframe_msg.mn_id, frm_and_keyfrm);
        if (!found) {
            spdlog::error("Do not find keyframe to be relocalized!");
            return false;
        }
        data::keyframe* p_keyframe = frm_and_keyfrm.first;
        std::shared_ptr<data::frame> p_frame = frm_and_keyfrm.second;
        spdlog::debug("found frame id is {}", p_frame->id_);

        // update pose and landmark
        update_frm_and_keyfrm_using_relocalization(p_keyframe, p_frame, reloc_result);
        relocal_map_id_ = keyframe_msg.mn_localize_map_id;
        spdlog::debug("relocal id: {} and current id: {}", p_frame->id_, curr_frm_->id_);

        curr_frm_ = p_frame;
        last_keyfrm_ = curr_frm_->ref_keyfrm_;
        last_reloc_frm_id_ = curr_frm_->id_;
        map_db_->origin_keyfrm_ = curr_frm_->ref_keyfrm_;
        if (cfg_->use_odom_) {
            map_db_->odom_origin_keyfrm_ = curr_frm_->ref_keyfrm_;
        }

        update_motion_model();
        univloc_tracker::Client::get_instance().set_session_start_time(reloc_result->session_start_time);
        univloc_tracker::Client::get_instance().get_server_landmarks_using_current_pose(
            velocity_ * curr_frm_->cam_pose_cw_, curr_frm_->id_, relocal_map_id_);

        update_local_map();
        update_map_database();

        // set the reference keyframe and corresponding odom data for odom based tracking and optimization
        // all subsequent frames will use the pose and odom data of the keyframe to adjust its pose
        // in this way, trajectory drift can be effectively eliminated
        if (cfg_->use_odom_ && (camera_->setup_type_ == camera::setup_type_t::Monocular ||
            camera_->setup_type_ == camera::setup_type_t::Stereo ||
            camera_->setup_type_ == camera::setup_type_t::RGBD)) {
            first_valid_odom_ = curr_frm_->odom_;
            first_valid_pose_ = curr_frm_->cam_pose_cw_;
            spdlog::debug("First valid odom and pose data set!");
        }

        // state transition to Tracking mode
        tracking_state_ = tracker_state_t::Tracking;
        relocal_num_++;
        univloc_tracker::Client::get_instance().set_latest_keyfrm_local_id(last_reloc_frm_id_);
        return true;
    }

    return false;
}

bool univloc_tracking_module::is_motion_enough_for_stereo_or_rgbd_input()
{
    if ((tracking_state_ == tracker_state_t::NotInitialized || tracking_state_ == tracker_state_t::Initializing) &&
        (curr_frm_->camera_->setup_type_ == camera::setup_type_t::Stereo_Inertial ||
         curr_frm_->camera_->setup_type_ == camera::setup_type_t::RGBD_Inertial)) {
        double timestamp_interval = 1.0 / camera_->fps_;
        if (!imu_data_buf_->is_imu_data_ready(curr_frm_->timestamp_ - 2.0 * timestamp_interval)) {
            spdlog::info("imu data is not ready for stereo and rgbd input, will skip this frame!");
            return false;
        }
        std::vector<std::pair<double, Eigen::VectorXd>> imu_vec1, imu_vec2;
        Eigen::Vector3d avg_accel1 = Eigen::Vector3d::Zero();
        Eigen::Vector3d avg_accel2 = Eigen::Vector3d::Zero();

        imu_data_buf_->get_imu_data(curr_frm_->timestamp_ - 2.0 * timestamp_interval,
                                    curr_frm_->timestamp_ - timestamp_interval, imu_vec1, false);
        imu_data_buf_->get_imu_data(curr_frm_->timestamp_ - 1.0 * timestamp_interval, curr_frm_->timestamp_, imu_vec2,
                                    false);
        for (auto& imu : imu_vec1) {
            avg_accel1 += imu.second.head(3);
        }
        avg_accel1 = avg_accel1 / imu_vec1.size();
        for (auto& imu : imu_vec2) {
            avg_accel2 += imu.second.head(3);
        }
        avg_accel2 = avg_accel2 / imu_vec2.size();
        if ((avg_accel2 - avg_accel1).norm() < INIT_ACCEL_THR) {
            spdlog::info("not enough acceleration for imu data, will skip this frame!");
            return false;
        }
    }
    return true;
}

tracker_state_t univloc_tracking_module::localization_track_trans_state_basic(bool is_succeeded,
                                                                [[maybe_unused]] std::any& anydata)
{
    return (is_succeeded ? tracker_state_t::Tracking : tracker_state_t::Lost);
}

tracker_state_t univloc_tracking_module::localization_track_trans_state_odom(bool is_succeeded,
                                                                [[maybe_unused]] std::any& anydata)
{
    // When odom data is available and tracking gets lost, use odom to update the pose
    // the system should switch back to visual tracking if possible
    if (is_succeeded) {
        return tracker_state_t::Tracking;
    } else {
        Mat44_t relative_transform_from_odom;
        get_relative_transform_from_odom(relative_transform_from_odom);
        Mat44_t odom_predict_pose = relative_transform_from_odom * first_valid_pose_;

        if (last_tracking_state_ != tracker_state_t::RecentlyLost &&
            last_tracking_state_ != tracker_state_t::Lost) {
            timestamp_recently_lost_ = curr_frm_->timestamp_;
            spdlog::info("tracking recently lost: frame {}", curr_frm_->id_);
        }

        double keep_recently_lost = ODOM_SUSTAIN_TIME;
        if (curr_frm_->timestamp_ - timestamp_recently_lost_ < keep_recently_lost) {
            curr_frm_->set_cam_pose(odom_predict_pose);
            spdlog::debug("failed to track server map, use odom to update the pose", curr_frm_->id_);
            return tracker_state_t::RecentlyLost;
        }
        else {
            return tracker_state_t::Lost;
        }
    }
}

void univloc_tracking_module::localization_track()
{
    camera_->use_imu_ = false;  // Tempral usage!
    // const unsigned int tracked_server_landmarks_thr = 50;

    last_tracking_state_ = tracking_state_;
    // check if pause is requested
    check_and_execute_pause();
    while (is_paused()) {
        timer_.startNextProc("pause");
        std::this_thread::sleep_for(std::chrono::microseconds(5));
    }

    if (cfg_->use_odom_) {
        if (!get_odom_data()) return;
    }

    // Lock the map database
    std::unique_lock<std::mutex> lock(data::map_database::mtx_database_);

    // TODO The following process are redundant with those in process_current_frame()
    if (tracking_state_ != tracker_state_t::Tracking && tracking_state_ != tracker_state_t::RecentlyLost) {
        if (!retrieve_relocalization_result()) {  // request relocalization
            if (frms_sent_for_relocalization_++ % cfg_->trigger_relocalization_request_divisor_ == 0) {
                lock.unlock(); // since request_relocalization_from_server will call sleep function
                request_relocalization_from_server();
            }
            relocal_fail_num_++;
        }
    } else {
        /*
            clear this member variable since we can request relocalization at
            the first time we failed to track.
        */
        frms_sent_for_relocalization_ = 0;

        // make sure landmarks from the server are received
        univloc_tracker::Client::get_instance().process_received_server_landmarks(curr_frm_->id_);
        // apply replace of landmarks observed in the last frame
        apply_landmark_replace();

        // update the camera pose of the last frame
        // because the mapping module might optimize the camera pose of the last frame's reference keyframe
        // update_last_frame();

        // set the reference keyframe of the current frame
        spdlog::info("Started Localization! current frame id is {}", curr_frm_->id_);

        bool succeeded = false;

        auto track_start = now();

        // just using server landmarks
        // this one may not be correct!! check if at first curr_frm_ have any landmarks!
        // for rgbd, sure it does!!
        succeeded = std::invoke(track_server_localization_, this);
        if (succeeded) succeeded = optimize_current_frame_with_server_map();

        // state transition
        std::any anydata;
        tracking_state_ = std::invoke(track_trans_state_func_, this, succeeded, anydata);
        if (anydata.has_value()) {
            succeeded = std::any_cast<bool>(anydata);
        }

        if (tracking_state_ != tracker_state_t::Lost) {
            spdlog::debug("tracking server map");
            update_local_map();
            update_map_database();
            spdlog::debug("tracking server map successfully");

            update_motion_model();
            // clear queue
            clear_frms_and_keyfrms_to_be_relocalized();
            univloc_tracker::Client::get_instance().clear_relocalization_results();
        } else if (last_tracking_state_ != tracker_state_t::Lost) {
            spdlog::warn("tracking lost: frame {}", curr_frm_->id_);
            curr_frm_->cam_pose_cw_is_valid_ = false;
        }

        auto track_end = now();
        spdlog::debug("Localization cost time {} ms", duration_ms(track_end - track_start));

        // tidy up observations
        for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
            if (curr_frm_->landmarks_.at(idx) && curr_frm_->outlier_flags_.at(idx)) {
                curr_frm_->landmarks_.at(idx) = nullptr;
            }
        }

        if (tracking_state_ != tracker_state_t::Lost) {
            timer_.startNextProc("get server landmarks");
            univloc_tracker::Client::get_instance().get_server_landmarks_using_current_pose(
                velocity_ * curr_frm_->cam_pose_cw_, curr_frm_->id_, relocal_map_id_);
        }

        /*
            Temporarily disable insert_new_keyframe in localization mode, since
            it won't bring improvement in our current design but bring random
            memory leak. Will re-enable it if needs to do mapping/localization
            mode switch in the future.
        */
        /*    
        if (tracking_state_ != tracker_state_t::Lost && new_keyframe_is_needed()) {
            // When tracking server map successfully, no local landmarks are tracked, so it is necessary to track
            // them. and meanwhile update local map
            insert_new_keyframe();
            spdlog::info("Localize keyframe size: {}", map_db_->get_num_keyframes());
        }
        */
        if (tracking_state_ == tracker_state_t::Lost) {
            lost_num_++;
        } else {
            success_num_++;
        }
    }

    // use only pose server landmark, so clear database while localize finish
    last_frm_ = curr_frm_;
    spdlog::info("tracking success number: {}, fail number: {}, relocal number: {}, relocal fail number: {}",
                 success_num_, lost_num_, relocal_num_, relocal_fail_num_);
}

tracker_state_t univloc_tracking_module::track_trans_state_basic(bool is_succeeded,
                                                                 [[maybe_unused]] std::any& anydata)
{
    return (is_succeeded ? tracker_state_t::Tracking : tracker_state_t::Lost);
}

tracker_state_t univloc_tracking_module::track_trans_state_odom(bool is_succeeded,
                                                                [[maybe_unused]] std::any& anydata)
{
    // When odom data is available and tracking gets lost, use odom to update the pose
    // the system should switch back to visual tracking if possible
    // this mechanism won't enable within 5.0 sec for Monocular input
    // since we prefer re-initialization in such case
    if (is_succeeded) {
        return tracker_state_t::Tracking;
    }
    else if (camera_->setup_type_ != camera::setup_type_t::Monocular ||
        curr_frm_->id_ - initializer_.get_initial_frame_id() > camera_->fps_ * INIT_RETRY_THR) {
        Mat44_t relative_transform_from_odom;
        get_relative_transform_from_odom(relative_transform_from_odom);
        Mat44_t odom_predict_pose = relative_transform_from_odom * first_valid_pose_;

        curr_frm_->set_cam_pose(odom_predict_pose);
        spdlog::debug("tracking lost, use odom to update the pose");
        return tracker_state_t::Tracking;
    }
    else {
        return tracker_state_t::Lost;
    }

}

tracker_state_t univloc_tracking_module::track_trans_state_imu(bool is_succeeded, std::any& anydata)
{
    if (is_succeeded) {
        return tracker_state_t::Tracking;
    }
    // condition 1: at least finish inertial only optimization once
    // condition 2: at least 1 second has passed since last relocalization
    // condition 3: last tracking state is not tracker_state_t::Lost
    else if (data::IMU_Preintegration::imu_initialize_times_ > 0 &&
        curr_frm_->id_ - last_reloc_frm_id_ > camera_->fps_ &&
        last_tracking_state_ != tracker_state_t::Lost) {

        // show the message of recently lost and check if larger than the threshold
        if (last_tracking_state_ != tracker_state_t::RecentlyLost) {
            timestamp_recently_lost_ = curr_frm_->timestamp_;
            spdlog::info("tracking recently lost: frame {}", curr_frm_->id_);
        } else {
            double keep_recently_lost = IMU_SUSTAIN_TIME;
            if (curr_frm_->timestamp_ - timestamp_recently_lost_ > keep_recently_lost) {
                spdlog::debug("tracking recently lost for {}s, set tracking_state_ to Lost!", keep_recently_lost);
                return tracker_state_t::Lost;
            }
        }

        // predict current frame pose based on imu if recently lost and imu is initialized
        anydata = predict_current_pose_with_imu(*curr_frm_);
        if (!anydata.has_value()) {
            spdlog::warn("no imu measurement for preintegration, thus directly set to lost!");
            return tracker_state_t::Lost;
        }
        return tracker_state_t::RecentlyLost;
    }
    else {
        return tracker_state_t::Lost;
    }
}

void univloc_tracking_module::track()
{
    if (camera_->use_imu_ && mapper_->bad_imu_to_reset_) {
        spdlog::info("tracking: reset map because local mapper set the bad imu flag due to lack of enough motion!");
        reset_requested_ = true;
        return;
    }

    if (tracking_state_ == tracker_state_t::NotInitialized) {
        tracking_state_ = tracker_state_t::Initializing;
    }

    last_tracking_state_ = tracking_state_;

    // check if pause is requested
    check_and_execute_pause();
    while (is_paused()) {
        timer_.startNextProc("pause");
        std::this_thread::sleep_for(std::chrono::microseconds(5));
    }

    // since we may not get odom data for the first several frames due to data setting and ROS tf mechanism
    // thus skip the first several frames to ensure odom is obtained for the first frame to initialize
    if (cfg_->use_odom_) {
        if (!get_odom_data()) return;
    }

    // skip every frames without available IMU data especially during system start
    // due to data setting and ROS tf mechanism
    if (camera_->use_imu_) {
        if (!imu_data_buf_->is_imu_data_ready(curr_frm_->timestamp_)) {
            spdlog::info("imu data is not ready, will skip this frame!");
            return;
        }
        if (!is_motion_enough_for_stereo_or_rgbd_input()) return;
    }

    // Lock the map database
    std::scoped_lock<std::mutex> lock(data::map_database::mtx_database_);

    if (tracking_state_ == tracker_state_t::Initializing) {
        if (!initialize()) {
            return;
        }

        // update the reference keyframe, local keyframes, and local landmarks
        update_local_map();

        // use id to determine which keyframe is the first one and which is the second one
        const auto keyfrms = map_db_->get_all_keyframes();

        // enforce the correct order of keyframes during initialization for monocular case
        [[maybe_unused]] data::keyframe* first_keyframe = nullptr;
        [[maybe_unused]] data::keyframe* second_keyframe = nullptr;
        if (curr_frm_->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial ||
            curr_frm_->camera_->setup_type_ == camera::setup_type_t::Monocular) {
            if (keyfrms.size() != 2) {
                spdlog::error("{}: After monocular initializing, there must be 2 keyframes in map_db_", __func__);
                return;
            }
            first_keyframe = (keyfrms[0]->id_ < keyfrms[1]->id_) ? keyfrms[0] : keyfrms[1];
            second_keyframe = (keyfrms[0]->id_ > keyfrms[1]->id_) ? keyfrms[0] : keyfrms[1];
            spdlog::debug("Successfully initialized Monocular_Inertial with keyframe {} and {}", first_keyframe->id_,
                          second_keyframe->id_);
        }

        if (curr_frm_->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial) {
            if (!first_keyframe || !second_keyframe) {
                spdlog::error("{}: After monocular initializing, first or second keyframes is nullptr", __func__);
                return;
            }

            imu_mearsurement_vec_.clear();
            assert(first_keyframe->timestamp_ < second_keyframe->timestamp_);
            imu_data_buf_->get_imu_data(first_keyframe->timestamp_, second_keyframe->timestamp_, imu_mearsurement_vec_);

            first_keyframe->set_new_imu_bias(VecX_t::Zero(6));
            second_keyframe->set_new_imu_bias(VecX_t::Zero(6));
            auto imu_preintegration_ptr = std::make_shared<data::IMU_Preintegration>(first_keyframe->timestamp_,
                                          second_keyframe->timestamp_, imu_mearsurement_vec_);
            spdlog::info("Initializing keyframe inteval : {} s",
                         second_keyframe->timestamp_ - first_keyframe->timestamp_);

            second_keyframe->set_imu_constraint(first_keyframe, imu_preintegration_ptr);
            first_keyframe->next_keyframe_ = second_keyframe;
            second_keyframe->pre_keyframe_ = first_keyframe;

            second_keyframe->imu_is_initialized_ = false;
            first_keyframe->imu_is_initialized_ = false;
            imu_mearsurement_vec_.clear();
        } else if (curr_frm_->camera_->setup_type_ == camera::setup_type_t::Stereo_Inertial ||
                   curr_frm_->camera_->setup_type_ == camera::setup_type_t::RGBD_Inertial) {
            if (keyfrms.size() != 1) {
                spdlog::error("{}: After RGBD/Stereo initializing, there must be 1 keyframes in map_db_", __func__);
                return;
            }
            keyfrms[0]->set_new_imu_bias(VecX_t::Zero(6));
            keyfrms[0]->imu_is_initialized_ = false;
        }

        // set the reference keyframe and corresponding odom data for odom based tracking and optimization
        // all subsequent frames will use the pose and odom data of the keyframe to adjust its pose
        // in this way, trajectory drift can be effectively eliminated
        if (cfg_->use_odom_ && (camera_->setup_type_ == camera::setup_type_t::Monocular ||
            camera_->setup_type_ == camera::setup_type_t::Stereo ||
            camera_->setup_type_ == camera::setup_type_t::RGBD)) {
            first_valid_odom_ = curr_frm_->odom_;
            first_valid_pose_ = curr_frm_->cam_pose_cw_;
        }

        // pass all of the keyframes to the mapping module
        spdlog::debug("Keyframe is queued to mapping module during initialization.");
        if (curr_frm_->camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial ||
            curr_frm_->camera_->setup_type_ == camera::setup_type_t::Monocular) {
            mapper_->queue_keyframe(first_keyframe);
            mapper_->queue_keyframe(second_keyframe);
        } else {
            for (const auto keyfrm : keyfrms) {
                mapper_->queue_keyframe(keyfrm);
            }
        }

        // state transition to Tracking mode
        spdlog::info("Finish tracking module initialization! current frame id is {}", curr_frm_->id_);
        tracking_state_ = tracker_state_t::Tracking;
    } else {
        // does not understand the purpose of this func?
        // apply replace of landmarks observed in the last frame
        apply_landmark_replace();

        // update the camera pose of the last frame
        // because the mapping module might optimize the camera pose of the last frame's reference keyframe
        update_last_frame();

        // TODO: use imu mearsuments to predict camera pose
        if (camera_->use_imu_) {
            double last_keyframe_timestamp = last_keyfrm_->timestamp_;
            double cur_frame_timestamp = curr_frm_->timestamp_;
            imu_data_buf_->get_imu_data(last_keyframe_timestamp, cur_frame_timestamp, imu_mearsurement_vec_);
            // if (data::IMU_Preintegration::state_ == data::IMU_Preintegration::IMU_State::Initialized) {
            //     predict_camerapose_from_imu();
            // }
        }

        // set the reference keyframe of the current frame
        curr_frm_->ref_keyfrm_ = ref_keyfrm_;
        spdlog::debug("Started tracking! current frame id is {}, ref_keyfrm id is {}", curr_frm_->id_,
                      ref_keyfrm_->id_);

        bool succeeded = false;

        auto track_start = now();

        std::fill(curr_frm_->landmarks_.begin(), curr_frm_->landmarks_.end(), nullptr);

        succeeded = track_current_frame();

        // update the local map and optimize the camera pose of the current frame
        if (succeeded) {
            update_local_map();
            spdlog::debug("tracking local map");
            succeeded = optimize_current_frame_with_local_map();
            spdlog::debug("tracking local map successfully");
        }

        auto track_end = now();
        spdlog::debug("Tracking cost time {} ms", duration_ms(track_end - track_start));

        // state transition
        std::any anydata;
        tracking_state_ = std::invoke(track_trans_state_func_, this, succeeded, anydata);

        // update the motion model
        if (tracking_state_ != tracker_state_t::Lost) {
            update_motion_model();
            // clear queue
            clear_frms_and_keyfrms_to_be_relocalized();
            univloc_tracker::Client::get_instance().clear_relocalization_results();
        }
        // show message if tracking has been lost
        else if (last_tracking_state_ != tracker_state_t::Lost) {
            spdlog::warn("tracking lost: frame {}", curr_frm_->id_);
        }

        // update the frame statistics
        map_db_->update_frame_statistics(*curr_frm_, tracking_state_ == tracker_state_t::Lost);

        // if tracking is failed within 5.0 sec after initialization, reset the system
        // this needs to be changed!
        // initial frame id is not set
        if (tracking_state_ == tracker_state_t::Lost) {
            if (curr_frm_->id_ - initializer_.get_initial_frame_id() < camera_->fps_ * INIT_RETRY_THR &&
                data::IMU_Preintegration::imu_initialize_times_ == 0) {
                timer_.startNextProc("reset for tracking lost after initialization");
                spdlog::info("tracking lost within {} sec after initialization", INIT_RETRY_THR);
                reset_requested_ = true;
                return;
            }
            // if tracking lost when using imu, use relocalization rather than system reset
            // to get better performance on EuRoC dataset
            /*
            else if (data::IMU_Preintegration::imu_initialize_times_ > 0) {
                timer_.startNextProc("reset for tracking lost after IMU initialization");
                reset_requested_ = true;
                return;
            }
            */
        }

        // check to insert the new keyframe derived from the current frame
        if (tracking_state_ == tracker_state_t::Tracking && new_keyframe_is_needed()) {
            // When tracking server map successfully, no local landmarks are tracked, so it is necessary to track
            // them. and meanwhile update local map
            insert_new_keyframe();
            imu_mearsurement_vec_.clear();

        } else if (tracking_state_ == tracker_state_t::RecentlyLost &&
                   data::IMU_Preintegration::imu_initialize_times_ > 0) {
            auto pre_info = std::any_cast<std::pair<std::shared_ptr<data::IMU_Preintegration>, Vec3_t>>(anydata);
            localizing_new_keyframe(*curr_frm_, pre_info);
        }

        // tidy up observations
        for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
            if (curr_frm_->landmarks_.at(idx) && curr_frm_->outlier_flags_.at(idx)) {
                curr_frm_->landmarks_.at(idx) = nullptr;
            }
        }
    }

    // store the relative pose from the reference keyframe to the current frame
    // to update the camera pose at the beginning of the next tracking process
    if (curr_frm_->cam_pose_cw_is_valid_) {
        last_cam_pose_from_ref_keyfrm_ = curr_frm_->cam_pose_cw_ * curr_frm_->ref_keyfrm_->get_cam_pose_inv();
    }

    // update last frame
    if (tracking_state_ == tracker_state_t::Tracking) {
        last_frm_ = curr_frm_;
        // if a lidar frame is updated or recived, we will save the associated pose to this lidar frame
        // for now we are also saving the whole frame data structure
        if (curr_frm_->is_lidar_enable() && curr_frm_->lidar_landmarks_.updated){
            last_lidar_frm_ = curr_frm_;
        }
    }

}  // namespace openvslam

bool univloc_tracking_module::initialize()
{
    timer_.startNextProc("initialize");
    // try to initialize with the current frame
    initializer_.initialize(*curr_frm_);

    // if map building was failed -> reset the map database
    if (initializer_.get_state() == module::initializer_state_t::Wrong) {
        // reset
        reset_requested_ = true;
        return false;
    }

    // if initializing was failed -> try to initialize with the next frame
    if (initializer_.get_state() != module::initializer_state_t::Succeeded) {
        return false;
    }

    last_keyfrm_ = curr_frm_->ref_keyfrm_;
    // succeeded
    return true;
}

void univloc_tracking_module::remove_untracked_server_landmarks()
{
    std::vector<LandmarkID> erased_untracked_server_landmarks_id;
    for (auto& lm : tracked_server_landmarks_) {
        if (!lm.second->is_existed_in_tracking()) erased_untracked_server_landmarks_id.push_back(lm.second->id_);
    }

    for (auto id : erased_untracked_server_landmarks_id) tracked_server_landmarks_.erase(id);
}

void univloc_tracking_module::reset_last_tracked_server_landmarks_state()
{
    for (auto& lm : tracked_server_landmarks_) lm.second->set_existed_in_tracking(false);
}

bool univloc_tracking_module::optimize_current_frame_with_all_map()
{
    auto start = now();

    tracked_server_landmarks_.clear();

    tracked_server_landmarks_position_.clear();

    search_all_landmarks();
    // optimize the pose
    pose_optimizer_.optimize(*curr_frm_);

    // count up the number of tracked landmarks
    num_tracked_lms_ = 0;
    num_tracked_server_lms_ = 0;
    for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
        auto lm = curr_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }

        if (!curr_frm_->outlier_flags_.at(idx)) {
            if (lm->come_from_server()) {
                auto lm_ptr = map_db_->get_server_landmark(lm->id_);
                if (!lm_ptr) {  // This server landmark is existed in local map
                    auto p_lm = map_db_->get_landmark(lm->id_);
                    if (!p_lm) {
                        spdlog::warn("This landmark doesn't exist in map database!");
                        if (tracked_server_landmarks_.find(lm->id_) == tracked_server_landmarks_.end()) {
                            spdlog::warn("This landmark doesn't exist in tracked_server_landmarks database!");
                            curr_frm_->landmarks_.at(idx) = nullptr;
                            continue;
                        } else {
                            curr_frm_->landmarks_.at(idx) = nullptr;
                            spdlog::warn("This landmark only exists in tracked_server_landmarks database!");
                            tracked_server_landmarks_[lm->id_]->set_existed_in_tracking(false);
                            continue;
                        }
                    } else {
                        ++num_tracked_server_lms_;
                        p_lm->set_existed_in_tracking(true);
                        tracked_server_landmarks_position_.push_back(p_lm->get_pos_in_world());
                    }
                } else {
                    ++num_tracked_server_lms_;
                    tracked_server_landmarks_[lm_ptr->id_] = lm_ptr;
                    lm_ptr->set_existed_in_tracking(true);
                    tracked_server_landmarks_position_.push_back(lm_ptr->get_pos_in_world());
                }
            }
            // the observation has been considered as inlier in the pose optimization
            assert(!lm->come_from_server() || lm->has_observation());
            // count up

            // understand better about this part!
            // Got it! not form server is good! change this!
            // need to change later!
            if (camera_->setup_type_ == openvslam::camera::setup_type_t::Monocular ||
                camera_->setup_type_ == openvslam::camera::setup_type_t::Monocular_Inertial)
                ++num_tracked_lms_;
            else {
                if (!lm->come_from_server()) ++num_tracked_lms_;
            }
            // increment the number of tracked frame
            lm->increase_num_observed();

        } else {
            // the observation has been considered as outlier in the pose optimization
            // remove the observation
            curr_frm_->landmarks_.at(idx) = nullptr;
        }
    }

    if (!tracked_server_landmarks_position_.empty())
        tracked_server_landmarks_position_.push_back(curr_frm_->get_cam_center());

    auto end = now();
    // this valid number is 0
    spdlog::info("valid tracked landmarks num: {} ", num_tracked_lms_);

    spdlog::info("tracking all map cost time: {} ms ", duration_ms(end - start));

    unsigned int num_tracked_lms_thr = camera_->use_imu_ ? 10 : 20;

    // if recently relocalized, use the more strict threshold
    if (curr_frm_->id_ < last_reloc_frm_id_ + camera_->fps_ && num_tracked_lms_ < 2 * num_tracked_lms_thr) {
        spdlog::debug("server map tracking failed: {} matches < {}", num_tracked_lms_, 2 * num_tracked_lms_thr);
        tracked_server_landmarks_.clear();
        return false;
    }

    // check the threshold of the number of tracked landmarks
    if (num_tracked_lms_ < num_tracked_lms_thr) {
        spdlog::debug("server map tracking failed: {} matches < {}", num_tracked_lms_, num_tracked_lms_thr);
        tracked_server_landmarks_.clear();
        return false;
    }

    return true;
}

void univloc_tracking_module::update_local_map()
{
    timer_.startNextProc("update local map");
    update_local_keyframes();
    update_local_landmarks();
    map_db_->set_local_landmarks(local_landmarks_);
}

void univloc_tracking_module::update_map_database()
{
    timer_.startNextProc("update map database");
    spdlog::debug("Start remove out of local map!");
    /*
        Threshold to erase server landmarks and keyframes.
        Currently set to 5 seconds and should keep a slightly
        smaller value to reset is_previously_sent flag of
        landmarks in server side if server only decides to
        send extra landmarks back to tracker.
    */
    unsigned int out_of_local_map_thr = curr_frm_->camera_->fps_ * 5;

    // erase keyframe not in local
    std::vector<data::keyframe*> all_keyframes = map_db_->get_all_keyframes();
    for (size_t id = 0; id < all_keyframes.size(); id++) {
        auto kf = all_keyframes.at(id);
        if (kf->out_of_local_map_times_ > out_of_local_map_thr) {
            kf->prepare_for_erasing(true, true);
        } else {
            kf->out_of_local_map_times_++;
        }
    }

    // erase landmark not in local
    std::vector<std::shared_ptr<data::landmark>> all_server_landmarks = map_db_->get_server_landmarks();
    for (size_t id = 0; id < all_server_landmarks.size(); id++) {
        auto lm = all_server_landmarks.at(id);
        if (lm->out_of_local_map_times_ > out_of_local_map_thr) {
            map_db_->get_server_virtual_keyframe()->erase_landmark(lm.get());
            map_db_->add_erased_server_landmark(lm->id_);
            map_db_->erase_landmark_from_id(lm->id_, false);
        } else {
            lm->out_of_local_map_times_++;
        }
    }
    map_db_->remove_to_be_erased_server_landmarks();
    map_db_->update_server_landmarks_vec();

    spdlog::debug("Finished remove out of local map!");
}

void univloc_tracking_module::update_local_keyframes()
{
    constexpr unsigned int max_num_local_keyfrms = 60;

    // count the number of sharing landmarks between the current frame and each of the neighbor keyframes
    // key: keyframe, value: number of sharing landmarks
    std::unordered_map<data::keyframe*, unsigned int> keyfrm_weights;
    for (unsigned int idx = 0; idx < curr_frm_->num_keypts_; ++idx) {
        auto lm = curr_frm_->landmarks_.at(idx);
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            curr_frm_->landmarks_.at(idx) = nullptr;
            continue;
        }

        const auto observations = lm->get_observations();
        for (const auto& obs : observations) {
            ++keyfrm_weights[obs.first];
        }
    }

    // virtual keyframe don't consider
    keyfrm_weights.erase(map_db_->get_server_virtual_keyframe());

    if (keyfrm_weights.empty()) {
        return;
    }

    // set the aforementioned keyframes as local keyframes
    // and find the nearest keyframe
    unsigned int max_weight = 0;
    data::keyframe* nearest_covisibility = nullptr;

    local_keyfrms_.clear();
    local_keyfrms_.reserve(4 * keyfrm_weights.size());

    for (auto& keyfrm_weight : keyfrm_weights) {
        auto keyfrm = keyfrm_weight.first;
        const auto weight = keyfrm_weight.second;

        if (keyfrm->will_be_erased()) {
            continue;
        }

        local_keyfrms_.push_back(keyfrm);

        keyfrm->out_of_local_map_times_ = 0;

        // avoid duplication
        keyfrm->local_map_update_identifier = curr_frm_->id_;

        // update the nearest keyframe
        if (max_weight < weight) {
            max_weight = weight;
            nearest_covisibility = keyfrm;
        }
    }

    // add the second-order keyframes to the local landmarks
    auto add_local_keyframe = [this](data::keyframe* keyfrm) {
        if (!keyfrm) {
            return false;
        }
        if (keyfrm->will_be_erased()) {
            return false;
        }
        // avoid duplication
        if (keyfrm->local_map_update_identifier == curr_frm_->id_) {
            return false;
        }
        keyfrm->local_map_update_identifier = curr_frm_->id_;
        local_keyfrms_.push_back(keyfrm);

        keyfrm->out_of_local_map_times_ = 0;

        return true;
    };

    size_t local_kf_size = local_keyfrms_.size();
    for (size_t loc = 0; loc < local_kf_size; loc++) {
        if (max_num_local_keyfrms < local_keyfrms_.size()) {
            break;
        }

        auto keyfrm = local_keyfrms_.at(loc);

        // covisibilities of the neighbor keyframe
        const auto neighbors = keyfrm->graph_node_->get_top_n_covisibilities(10);
        for (auto& neighbor : neighbors) {
            if (add_local_keyframe(neighbor)) {
                break;
            }
        }

        // children of the spanning tree
        const auto spanning_children = keyfrm->graph_node_->get_spanning_children();
        for (auto& child : spanning_children) {
            if (add_local_keyframe(child)) {
                break;
            }
        }

        // parent of the spanning tree
        auto parent = keyfrm->graph_node_->get_spanning_parent();
        add_local_keyframe(parent);
    }

    // update the reference keyframe with the nearest one
    if (nearest_covisibility) {
        ref_keyfrm_ = nearest_covisibility;
        curr_frm_->ref_keyfrm_ = ref_keyfrm_;
    }
}

bool univloc_tracking_module::reset_requested() const {
    return reset_requested_;
}

void univloc_tracking_module::set_reset_requested(bool val) {
    reset_requested_ = val;
}

void univloc_tracking_module::update_local_landmarks()
{
    local_landmarks_.clear();

    for (auto keyfrm : local_keyfrms_) {
        const auto lms = keyfrm->get_landmarks();

        for (auto lm : lms) {
            if (!lm) {
                continue;
            }
            if (lm->will_be_erased()) {
                continue;
            }

            // avoid duplication
            if (lm->identifier_in_local_map_update_ == curr_frm_->id_) {
                continue;
            }
            lm->identifier_in_local_map_update_ = curr_frm_->id_;

            local_landmarks_.push_back(lm);

            lm->out_of_local_map_times_ = 0;

            // Set client ID for landmarks, mainly used for visualization
            if (!lm->come_from_server()) lm->client_id_ = client_id_;
        }
    }
}

std::any univloc_tracking_module::predict_current_pose_with_imu(data::frame& frame)
{
    timer_.startNextProc("localize new keyframe with IMU");

    int n1 = imu_mearsurement_vec_.size();
    spdlog::debug("localize new keyframe with IMU, try to get more imu data!");
    // sometimes, the imu and camera timestamp is not ideal
    imu_data_buf_->get_imu_data(last_keyfrm_->timestamp_, frame.timestamp_, imu_mearsurement_vec_);
    int n2 = imu_mearsurement_vec_.size();
    if (n2 - n1) spdlog::debug("localize new keyframe with IMU, got {} more imu data!", n2 - n1);

    if (imu_mearsurement_vec_.size() == 0) {
        spdlog::warn("no imu measurement for imu preintegration!");
        return std::any();
    }

    // Calculate the IMU pre-integration from last keyframe to current frame
    auto imu_preintegration_ptr = std::make_shared<data::IMU_Preintegration>(last_keyfrm_->timestamp_,
                                  frame.timestamp_, imu_mearsurement_vec_);

    // In our current logic, the condition is always false
    if (last_keyfrm_->should_be_fixed_in_optimization_) {
        imu_preintegration_ptr->merge_preintegration(last_keyfrm_->get_imu_constraint().second);
        last_keyfrm_ = last_keyfrm_->pre_keyframe_;
    }

    // Calculate the pose of current frame
    const Vec3_t trans_wb1 = last_keyfrm_->get_imu_position();
    const Mat33_t rot_wb1 = last_keyfrm_->get_imu_rotation();
    const Vec3_t vel_wb1 = last_keyfrm_->get_imu_velocity();
    const VecX_t bias1 = last_keyfrm_->get_imu_bias();
    const double t12 = imu_preintegration_ptr->integration_time_;

    Mat33_t rot_wb2 = normalize_rotation(rot_wb1 * imu_preintegration_ptr->get_delta_rotation(bias1));
    Vec3_t trans_wb2 = trans_wb1 + vel_wb1 * t12 + 0.5 * t12 * t12 * gI +
                       rot_wb1 * imu_preintegration_ptr->get_delta_position(bias1);
    Mat44_t Twi = Mat44_t::Identity();
    Twi.block(0, 0, 3, 3) = rot_wb2;
    Twi.block(0, 3, 3, 1) = trans_wb2;
    Mat44_t pred_cw = data::IMU_Preintegration::Tci_ * Twi.inverse();
    frame.set_cam_pose(pred_cw);
    frame.cam_pose_cw_is_valid_ = false;

    // Calculate the velocity of current frame
    Mat44_t pred_wc = pred_cw.inverse();
    Vec3_t pred_imu_pose = pred_wc.block(0, 0, 3, 3) * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1) -
                           pred_wc.block(0, 0, 3, 3) * pred_cw.block(0, 3, 3, 1);
    Vec3_t pred_vel = (pred_imu_pose - last_keyfrm_->get_imu_position()) / t12;

    return std::make_pair(imu_preintegration_ptr, pred_vel);
}

void univloc_tracking_module::localizing_new_keyframe(
    data::frame& frame, std::pair<std::shared_ptr<data::IMU_Preintegration>, Vec3_t> predict_info)
{
    std::shared_ptr<data::IMU_Preintegration> imu_preintegration_ptr = std::get<0>(predict_info);
    Vec3_t vel_wb = std::get<1>(predict_info);
    VecX_t bias = last_keyfrm_->get_imu_bias();

    // Generate keyframe base on current frame
    /*
        Instead of creating new keyframe object directly, try to reuse the implementation from keyfrm_inserter.
        Since for RGBD and stereo cases, new landmarks will be created. Reuse can help aviod redundant code.
    */
    bool send_to_server = (tracker_mode_ == tracker_mode_t::Mapping ||
                           tracker_mode_ == tracker_mode_t::Remapping);
    auto new_keyframe = keyfrm_inserter_.insert_new_keyframe(frame, send_to_server);
    // follow the same logic of tracking_module::insert_new_keyframe()
    if (new_keyframe) {
        new_keyframe->imu_is_initialized_ = (data::IMU_Preintegration::imu_initialize_times_ > 0);
        new_keyframe->set_imu_velocity(vel_wb);
        new_keyframe->set_new_imu_bias(bias);
        new_keyframe->set_imu_constraint(last_keyfrm_, imu_preintegration_ptr);

        new_keyframe->graph_node_->set_spanning_parent(last_keyfrm_);
        last_keyfrm_->next_keyframe_ = new_keyframe;
        new_keyframe->pre_keyframe_ = last_keyfrm_;
        imu_mearsurement_vec_.clear(); // for insert_new_keyframe, this is defined outside
    }
    // Update the last_keyfrm_ in both mapping and localization mode
    last_keyfrm_ = new_keyframe;

    // Set the reference keyframe with the new keyframe
    ref_keyfrm_ = new_keyframe ? new_keyframe : ref_keyfrm_;

    frame.ref_keyfrm_ = ref_keyfrm_;

    // Enqueue the newly generated keyframe to mapping module, make sure new kf is valid
    if(new_keyframe) keyfrm_inserter_.queue_keyframe(new_keyframe);

    return;
}

void univloc_tracking_module::visualize_keypoints()
{
    std::shared_ptr<data::frame> curr_frame;
    while (!gui_queue_->closed()) {
        if (gui_queue_->wait_pop(curr_frame)) {
            timer_.startNextProc("visualize keypoints");
            // plot keypoints
            // not tracked kpts are red, local tracked are green, and server tracked are blue
            std::vector<cv::KeyPoint> unmatched_keypts, outlier_keypts, server_keypts, local_keypts;
            for (unsigned int idx = 0; idx < curr_frame->num_keypts_; ++idx) {
                auto lm = curr_frame->landmarks_.at(idx);
                if (!lm) {
                    if (curr_frame->outlier_flags_.at(idx)) {
                        outlier_keypts.push_back(curr_frame->keypts_.at(idx));
                    } else {
                        unmatched_keypts.push_back(curr_frame->keypts_.at(idx));
                    }
                } else if (lm->come_from_server()) {
                    server_keypts.push_back(curr_frame->keypts_.at(idx));
                } else {
                    local_keypts.push_back(curr_frame->keypts_.at(idx));
                }
            }

            // get server landmark from map db
            std::vector<std::shared_ptr<data::landmark>> server_landmarks = map_db_->get_server_landmarks();
            std::vector<cv::KeyPoint> project_keypts;
            Mat33_t K;
            if (camera_->model_type_ == camera::model_type_t::Perspective) {
                K = static_cast<camera::perspective*>(camera_)->eigen_cam_matrix_;
                // spdlog::debug("K is {}, {}, {}, {}", K(0,0), K(1,1), K(0,2), K(1,2));
                // std::cout << "K is " << K << std::endl;
            } else if (camera_->model_type_ == camera::model_type_t::Fisheye) {
                K = static_cast<camera::fisheye*>(camera_)->eigen_cam_matrix_;
            } else {
                spdlog::warn("Not using perspective or Fisheye camera model!");
            }

            for (auto lm : server_landmarks) {
                // coodinate transformation
                Vec3_t cam_loc = K * (curr_frame->cam_pose_cw_.block(0, 0, 3, 3) * lm->get_pos_in_world() +
                                    curr_frame->cam_pose_cw_.block(0, 3, 3, 1));
                Vec3_t pos_c = curr_frame->cam_pose_cw_.block(0, 0, 3, 3) * lm->get_pos_in_world() +
                            curr_frame->cam_pose_cw_.block(0, 3, 3, 1);
                double z = pos_c[2];
                if (z < 0) {
                    continue;
                }
                float u = cam_loc[0] / cam_loc[2];
                float v = cam_loc[1] / cam_loc[2];

                if (u > 0 && u < camera_->cols_ && v > 0 && v < camera_->rows_) {
                    // spdlog::debug("cam loc is {}, {}, {}", cam_loc[0], cam_loc[1], cam_loc[2]);
                    // std::cout << "Tcw is " << curr_frm_->cam_pose_cw_ << std::endl;
                    // std::cout << "landmark loc " << lm->get_pos_in_world() << std::endl;
                    project_keypts.push_back(cv::KeyPoint(curr_frame->image_.cols + u, v, 1.0));
                }
            }

            /*
                Instead of cloning the frame twice and drawing on them
                and then combine them to a single image (which is 2 more copies),
                combine the image into a single one right at start and continue
                drawing directly on it. Instead of 4, there are 2 frame copies.
                NOTE: Offset for the second image (server one) needs to be taken into
                consideration.
            */
            cv::Mat combine_img = combine_images(curr_frame->image_, curr_frame->image_);
            cv::drawKeypoints(combine_img, unmatched_keypts, combine_img, cvScalar(245, 143, 41));
            cv::drawKeypoints(combine_img, outlier_keypts, combine_img, cvScalar(0, 255, 255));
            cv::drawKeypoints(combine_img, local_keypts, combine_img, cvScalar(0, 255, 0));
            cv::drawKeypoints(combine_img, server_keypts, combine_img, cvScalar(0, 0, 255));

            std::string state = "";
            if (tracker_mode_ == tracker_mode_t::Localization) {
                if (tracking_state_ == tracker_state_t::Tracking) {
                    if (last_tracking_state_ == tracker_state_t::Tracking) {
                        state = "Tracking";
                    } else {
                        state = "Relocalization Success";
                    }
                } else {
                    if (last_tracking_state_ == tracker_state_t::Lost) {
                        state = "Request Relocalization";
                    } else {
                        state = "Lost";
                    }
                }
            } else if (tracker_mode_ == tracker_mode_t::Relocalization) {
                state = "Relocalizing";
            } else {
                if (tracking_state_ == tracker_state_t::Lost) {
                    state = "Lost";
                } else if (tracking_state_ == tracker_state_t::Tracking) {
                    state = "Tracking";
                } else {
                    state = "Initializing";
                }
            }

            cv::putText(combine_img, " state : " + state, cv::Point(10, 10), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(0, 255, 0),
                        1);
            cv::putText(combine_img, "unmatched : " + std::to_string(unmatched_keypts.size()),
                        cv::Point(10, curr_frame->image_.rows - 10), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(245, 143, 41), 1);
            cv::putText(combine_img, "     outlier : " + std::to_string(outlier_keypts.size()),
                        cv::Point(10, curr_frame->image_.rows - 30), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(0, 255, 255), 1);
            cv::putText(combine_img, "       local : " + std::to_string(local_keypts.size()),
                        cv::Point(10, curr_frame->image_.rows - 70), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(0, 255, 0), 1);
            cv::putText(combine_img, "     server : " + std::to_string(server_keypts.size()),
                        cv::Point(10, curr_frame->image_.rows - 50), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(0, 0, 255), 1);

            cv::drawKeypoints(combine_img, project_keypts, combine_img, cvScalar(0, 0, 255));
            cv::putText(combine_img,
                        "server landmark : " + std::to_string(server_landmarks.size()) +
                            " (in current frame : " + std::to_string(project_keypts.size()) + ")",
                        cv::Point(curr_frame->image_.cols + 10, curr_frame->image_.rows - 10), CV_FONT_HERSHEY_COMPLEX, 0.4, cvScalar(0, 0, 255), 1);

            std::string imu_state;
            if (!camera_->use_imu_) {
                imu_state = "IMU State: Not use!";
            } else {
                if (data::IMU_Preintegration::state_ == data::IMU_Preintegration::IMU_State::Not_Initialized)
                    imu_state = "IMU State: Not_Initialized";
                else
                    imu_state = "IMU State: Initialized";
            }
            cv::putText(combine_img, imu_state, cv::Point(combine_img.cols * 0.5 - 150, 30), CV_FONT_HERSHEY_COMPLEX, 0.8,
                        cvScalar(0, 255, 0), 0);

            if (tracker_mode_ == tracker_mode_t::Localization) {
                // plot matching valid kpts
                for (unsigned int idx = 0; idx < curr_frame->num_keypts_; ++idx) {
                    auto lm = curr_frame->landmarks_.at(idx);
                    if (!lm) continue;

                    auto kpt = curr_frame->keypts_.at(idx);

                    Vec3_t cam_loc = K * (curr_frame->cam_pose_cw_.block(0, 0, 3, 3) * lm->get_pos_in_world() +
                                        curr_frame->cam_pose_cw_.block(0, 3, 3, 1));
                    float u = cam_loc[0] / cam_loc[2];
                    float v = cam_loc[1] / cam_loc[2];

                    cv::line(combine_img, cv::Point(kpt.pt.x, kpt.pt.y), cv::Point(u + curr_frame->image_.cols, v),
                            cvScalar(245, 143, 41), 1);
                }
            }

            cv::imshow("keypoints", combine_img);
            cv::waitKey(1);
        }
    }

    gui_queue_->clean();
    spdlog::info("Finished with visualization thread!");

}

cv::Mat univloc_tracking_module::combine_images(cv::Mat img1, cv::Mat img2)
{
    int height = img1.rows;
    int width = img1.cols;
    // Create a new 3 channel image
    cv::Mat DispImage = cv::Mat::zeros(cv::Size(width * 2, height), CV_8UC1);

    cv::Rect ROI1(0, 0, width, height);
    img1.copyTo(DispImage(ROI1));

    cv::Rect ROI2(width, 0, width, height);
    img2.copyTo(DispImage(ROI2));

    return DispImage;
}

void univloc_tracking_module::queue_visualization_frames() {
    if (!cfg_->gui_) return;

    gui_queue_->try_push(curr_frm_);
}

}  // namespace openvslam
