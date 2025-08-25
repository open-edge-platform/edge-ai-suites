// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "module/initializer.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "initialize/bearing_vector.h"
#include "initialize/perspective.h"
#include "match/area.h"
#include "optimize/global_bundle_adjuster.h"

#include <spdlog/spdlog.h>

#define KEYPTS_NUM_THR          100
#define TIME_DIFF_THR           1.09 // number within range (1.05,1.1) shoule all be fine
#define MONOIMU_INVMED_DEPTH    4.0
#define MONODEF_INVMED_DEPTH    1.0

namespace openvslam {
namespace module {

// better solution is to add the pose and landmark here
// then change the set pose and landmark module will be fine!
initializer::initializer(std::shared_ptr<univloc_tracker::Config> cfg, camera::setup_type_t setup_type,
                         data::map_database* map_db, data::bow_database* bow_db)
    : setup_type_(setup_type),
      map_db_(map_db),
      bow_db_(bow_db),
      initial_pose_(cfg->tf_base_camera_.inverse()),
      num_ransac_iters_(cfg->init_num_ransac_iterations_),
      min_num_triangulated_(cfg->init_num_min_triangulated_pts_),
      parallax_deg_thr_(cfg->init_parallax_deg_threshold_),
      reproj_err_thr_(cfg->init_reprojection_error_threshold_),
      num_ba_iters_(cfg->init_num_ba_iterations_),
      scaling_factor_(cfg->init_scaling_factor_),
      use_odom_(cfg->use_odom_)
{
    spdlog::debug("CONSTRUCT: module::initializer");
}

initializer::~initializer() { spdlog::debug("DESTRUCT: module::initializer"); }

void initializer::reset()
{
    initializer_.reset(nullptr);
    state_ = initializer_state_t::NotReady;
    init_frm_id_ = 0;
}

initializer_state_t initializer::get_state() const { return state_; }

std::vector<cv::KeyPoint> initializer::get_initial_keypoints() const { return init_frm_.keypts_; }

std::vector<int> initializer::get_initial_matches() const { return init_matches_; }

KeyframeID initializer::get_initial_frame_id() const { return init_frm_id_; }

void initializer::set_initial_frame_id(KeyframeID id) { init_frm_id_ = id; }

bool initializer::initialize(data::frame& curr_frm)
{
    switch (setup_type_) {
        case camera::setup_type_t::Monocular:
        case camera::setup_type_t::Monocular_Inertial: {
            // construct an initializer if not constructed
            if (state_ == initializer_state_t::NotReady) {
                // it constantly set earier one frame as init_frame
                // since the curr_frm will be replaced as time moves on
                create_initializer(curr_frm);
                return false;
            }

            // try to initialize
            if (!try_initialize_for_monocular(curr_frm)) {  // get pose and landmarks of curr_frm
                // failed
                return false;
            }

            // create new map if succeeded
            create_map_for_monocular(curr_frm);
            break;
        }
        case camera::setup_type_t::Stereo:
        case camera::setup_type_t::RGBD:
        case camera::setup_type_t::RGBD_Inertial:
        case camera::setup_type_t::Stereo_Inertial: {
            state_ = initializer_state_t::Initializing;

            // try to initialize
            if (!try_initialize_for_stereo(curr_frm)) {
                // failed
                return false;
            }

            // create new map if succeeded
            create_map_for_stereo(curr_frm);
            break;
        }
        default: {
            throw std::runtime_error("Undefined camera setup");
        }
    }

    // check the state is succeeded or not
    if (state_ == initializer_state_t::Succeeded) {
        init_frm_id_ = curr_frm.id_;
        return true;
    } else {
        return false;
    }
}

void initializer::create_initializer(data::frame& curr_frm)
{
    // set the initial frame
    init_frm_ = data::frame(curr_frm);

    // initialize the previously matched coordinates
    prev_matched_coords_.resize(init_frm_.undist_keypts_.size());
    for (unsigned int i = 0; i < init_frm_.undist_keypts_.size(); ++i) {
        prev_matched_coords_.at(i) = init_frm_.undist_keypts_.at(i).pt;
    }

    // initialize matchings (init_idx -> curr_idx)
    std::fill(init_matches_.begin(), init_matches_.end(), -1);

    // build a initializer
    initializer_.reset(nullptr);
    switch (init_frm_.camera_->model_type_) {
        case camera::model_type_t::Perspective:
        case camera::model_type_t::Fisheye: {
            initializer_ = std::unique_ptr<initialize::perspective>(new initialize::perspective(
                init_frm_, num_ransac_iters_, min_num_triangulated_, parallax_deg_thr_, reproj_err_thr_, use_odom_));
            break;
        }
        case camera::model_type_t::Equirectangular: {
            initializer_ = std::unique_ptr<initialize::bearing_vector>(new initialize::bearing_vector(
                init_frm_, num_ransac_iters_, min_num_triangulated_, parallax_deg_thr_, reproj_err_thr_));
            break;
        }
    }

    state_ = initializer_state_t::Initializing;
}

bool initializer::try_initialize_for_monocular(data::frame& curr_frm)
{
    if (state_ != initializer_state_t::Initializing) {
        return false;
    }

    // use similar magic numbers as orb3
    const int keypts_num_thre = KEYPTS_NUM_THR;
    const double time_diff_thre = TIME_DIFF_THR;
    // reset initializer if cannot initialize successfully for too long
    if ((curr_frm.keypts_.size() <= keypts_num_thre) ||
        (setup_type_ == camera::setup_type_t::Monocular_Inertial &&
         (curr_frm.timestamp_ - init_frm_.timestamp_ > time_diff_thre))) {
        reset();
        return false;
    }

    match::area matcher(0.9, true);
    const auto num_matches =
        matcher.match_in_consistent_area(init_frm_, curr_frm, prev_matched_coords_, init_matches_, 100);

    if (num_matches < min_num_triangulated_) {
        std::cout << "Too few num_matches " << num_matches << " below thr " << min_num_triangulated_ << std::endl;
        // rebuild the initializer with the next frame
        reset();
        return false;
    }

    // try to initialize with the current frame
    if (!initializer_) {
        return false;
    }

    return initializer_->initialize(curr_frm, init_matches_);
}

bool initializer::create_map_for_monocular(data::frame& curr_frm)
{
    if (state_ != initializer_state_t::Initializing) {
        return false;
    }

    eigen_alloc_vector<Vec3_t> init_triangulated_pts;
    {
        if (!initializer_) {
            return false;
        }

        init_triangulated_pts = initializer_->get_triangulated_pts();
        const auto is_triangulated = initializer_->get_triangulated_flags();

        // make invalid the matchings which have not been triangulated
        for (unsigned int i = 0; i < init_matches_.size(); ++i) {
            if (init_matches_.at(i) < 0) {
                continue;
            }
            if (is_triangulated.at(i)) {
                continue;
            }
            init_matches_.at(i) = -1;
        }

        // set the camera poses
        /*
           When using imu, after imu initialization, the poses of keyframes are transformed to the
           imu (body) coordinate. In other words, the pose (Tcw) of frame i is T_body_frame_i_body_frame_0.
           Therefore, we will follow the same initialization method as orbslam3 and don't use the
           extrinsic matrix (initial_pose_) to set the initial pose for frames.
        */
        if (curr_frm.camera_->use_imu_)
            init_frm_.set_cam_pose(Mat44_t::Identity());
        else
            init_frm_.set_cam_pose(initial_pose_);
        Mat44_t cam_pose_cw = Mat44_t::Identity();
        cam_pose_cw.block<3, 3>(0, 0) = initializer_->get_rotation_ref_to_cur();
        cam_pose_cw.block<3, 1>(0, 3) = initializer_->get_translation_ref_to_cur();
        if (curr_frm.camera_->use_imu_)
            curr_frm.set_cam_pose(cam_pose_cw);
        else
            curr_frm.set_cam_pose(cam_pose_cw * initial_pose_);

        // destruct the initializer
        initializer_.reset(nullptr);
    }

    // create initial keyframes
    auto init_keyfrm = new data::keyframe(init_frm_, map_db_, bow_db_);
    auto curr_keyfrm = new data::keyframe(curr_frm, map_db_, bow_db_);
    if (use_odom_) {
        init_keyfrm->odom_ = init_frm_.odom_;
        curr_keyfrm->odom_ = curr_frm.odom_;
    }

    // compute BoW representations
    init_keyfrm->compute_bow();
    curr_keyfrm->compute_bow();

    // add the keyframes to the map DB
    map_db_->add_keyframe(init_keyfrm);
    map_db_->add_keyframe(curr_keyfrm);

    // update the frame statistics
    init_frm_.ref_keyfrm_ = init_keyfrm;
    curr_frm.ref_keyfrm_ = curr_keyfrm;
    map_db_->update_frame_statistics(init_frm_, false);
    map_db_->update_frame_statistics(curr_frm, false);

    // assign 2D-3D associations
    [[maybe_unused]] Eigen::Matrix3d rot_init = initial_pose_.inverse().block(0, 0, 3, 3);
    [[maybe_unused]] Eigen::Vector3d trans_init = initial_pose_.inverse().block(0, 3, 3, 1);

    spdlog::debug("init_matches_.size: {}", init_matches_.size());
    for (unsigned int init_idx = 0; init_idx < init_matches_.size(); init_idx++) {
        const auto curr_idx = init_matches_.at(init_idx);
        if (curr_idx < 0) {
            continue;
        }

        // construct a landmark
        data::landmark* lm = nullptr;
        if (curr_frm.camera_->use_imu_)
            lm = new data::landmark(init_triangulated_pts.at(init_idx), curr_keyfrm, map_db_);
        else
            lm = new data::landmark(rot_init * init_triangulated_pts.at(init_idx) + trans_init, curr_keyfrm, map_db_);

        // set the assocications to the new keyframes
        init_keyfrm->add_landmark(lm, init_idx);
        curr_keyfrm->add_landmark(lm, curr_idx);
        lm->add_observation(init_keyfrm, init_idx);
        lm->add_observation(curr_keyfrm, curr_idx);

        init_keyfrm->set_origin();  // Set first keyframe to be origin

        // update the descriptor
        lm->compute_descriptor();
        // update the geometry
        lm->update_normal_and_depth();

        // set the 2D-3D assocications to the current frame
        curr_frm.landmarks_.at(curr_idx) = lm;
        curr_frm.outlier_flags_.at(curr_idx) = false;

        // add the landmark to the map DB
        map_db_->add_landmark(lm);
    }

    // global bundle adjustment
    // pass the first keyframe id to global ba constructor
    const auto global_bundle_adjuster = optimize::global_bundle_adjuster(init_keyfrm->id_, map_db_, num_ba_iters_, true);
    global_bundle_adjuster.optimize(init_keyfrm->id_, nullptr);

    if (use_odom_) {
        if (curr_keyfrm->get_num_tracked_landmarks(1) < min_num_triangulated_) {
            spdlog::info("seems to be wrong initialization, resetting");
            state_ = initializer_state_t::Wrong;
            return false;
        }
    } else {
        // scale the map so that the median of depths is 1.0
        const auto median_depth = init_keyfrm->compute_median_depth(init_keyfrm->camera_->model_type_ ==
                                                                    camera::model_type_t::Equirectangular);
        float inv_median_depth;
        if (setup_type_ == camera::setup_type_t::Monocular_Inertial)
            inv_median_depth = MONOIMU_INVMED_DEPTH / median_depth;
        else
            inv_median_depth = MONODEF_INVMED_DEPTH / median_depth;
        if (curr_keyfrm->get_num_tracked_landmarks(1) < min_num_triangulated_ && median_depth < 0) {
            spdlog::info("seems to be wrong initialization, resetting");
            state_ = initializer_state_t::Wrong;
            return false;
        }
        scale_map(init_keyfrm, curr_keyfrm, inv_median_depth * scaling_factor_);
    }

    // update the current frame pose
    curr_frm.set_cam_pose(curr_keyfrm->get_cam_pose());

    // set the origin keyframe and odom origin keyframe
    map_db_->origin_keyfrm_ = init_keyfrm;
    if (use_odom_) {
        map_db_->odom_origin_keyfrm_ = curr_keyfrm;
    }

    spdlog::info("new map created with {} points: frame {} - frame {}", map_db_->get_num_landmarks(), init_frm_.id_,
                 curr_frm.id_);
    state_ = initializer_state_t::Succeeded;
    return true;
}

void initializer::scale_map(data::keyframe* init_keyfrm, data::keyframe* curr_keyfrm, const double scale)
{
    // scaling keyframes
    Mat44_t cam_pose_cw = curr_keyfrm->get_cam_pose();
    cam_pose_cw.block<3, 1>(0, 3) *= scale;
    curr_keyfrm->set_cam_pose(cam_pose_cw);

    // scaling landmarks
    const auto landmarks = init_keyfrm->get_landmarks();
    for (auto lm : landmarks) {
        if (!lm) {
            continue;
        }
        lm->set_pos_in_world(lm->get_pos_in_world() * scale);
    }
}

bool initializer::try_initialize_for_stereo(data::frame& curr_frm)
{
    if (state_ != initializer_state_t::Initializing) {
        return false;
    }

    // count the number of valid depths
    unsigned int num_valid_depths =
        std::count_if(curr_frm.depths_.begin(), curr_frm.depths_.end(), [](const float depth) { return 0 < depth; });
    return min_num_triangulated_ <= num_valid_depths;
}

bool initializer::create_map_for_stereo(data::frame& curr_frm)
{
    if (state_ != initializer_state_t::Initializing) {
        return false;
    }

    // create an initial keyframe
    if (curr_frm.camera_->use_imu_)
        curr_frm.set_cam_pose(Mat44_t::Identity());
    else
        curr_frm.set_cam_pose(initial_pose_);
    auto curr_keyfrm = new data::keyframe(curr_frm, map_db_, bow_db_);
    if (use_odom_) {
        curr_keyfrm->odom_ = curr_frm.odom_;
    }

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

    // set the origin keyframe and odom origin keyframe
    map_db_->origin_keyfrm_ = curr_keyfrm;
    curr_keyfrm->set_origin();
    if (use_odom_) {
        map_db_->odom_origin_keyfrm_ = curr_keyfrm;
    }

    spdlog::info("new map created with {} points: frame {}", map_db_->get_num_landmarks(), curr_frm.id_);
    state_ = initializer_state_t::Succeeded;
    return true;
}

}  // namespace module
}  // namespace openvslam
