// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/frame.h"
#include "camera/equirectangular.h"
#include "camera/fisheye.h"
#include "camera/perspective.h"
#include "data/common.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "orb_extractor.h"
#include "match/stereo.h"
#include "data/imu.h"

#include <thread>

#include <spdlog/spdlog.h>

namespace openvslam {
namespace data {

std::atomic<KeyframeID> frame::next_id_{0};

frame::frame(const keyframe& keyfrm)
    :  // meta information
      id_(next_id_++),
      // databases
      bow_vocab_(keyfrm.get_bow_vocab()),
      timestamp_(keyfrm.timestamp_),
      // camera parameters
      camera_(keyfrm.camera_),
      depth_thr_(keyfrm.depth_thr_),
      // constant observations
      num_keypts_(keyfrm.num_keypts_),
      keypts_(keyfrm.keypts_),
      undist_keypts_(keyfrm.undist_keypts_),
      bearings_(keyfrm.bearings_),
      stereo_x_right_(keyfrm.stereo_x_right_),
      depths_(keyfrm.depths_),
      // BoW, no need for compute_bow
      bow_vec_(keyfrm.bow_vec_),
      bow_feat_vec_(keyfrm.bow_feat_vec_),
      descriptors_(keyfrm.descriptors_.clone()),
      // observations
      landmarks_(keyfrm.get_landmarks()),
      keypt_indices_in_cells_(keyfrm.keypt_indices_in_cells_),
      // ORB scale pyramid
      num_scale_levels_(keyfrm.num_scale_levels_),
      scale_factor_(keyfrm.scale_factor_),
      log_scale_factor_(keyfrm.log_scale_factor_),
      scale_factors_(keyfrm.scale_factors_),
      level_sigma_sq_(keyfrm.level_sigma_sq_),
      inv_level_sigma_sq_(keyfrm.inv_level_sigma_sq_)
{
    outlier_flags_ = std::vector<bool>(num_keypts_, false);
}

frame::frame(const double timestamp, orb_extractor* extractor,
             bow_vocabulary* bow_vocab, camera::base* camera, const float depth_thr)
    : id_(next_id_++),
      bow_vocab_(bow_vocab),
      extractor_(extractor),
      extractor_right_(nullptr),
      timestamp_(timestamp),
      camera_(camera),
      depth_thr_(depth_thr)
{
    // Get ORB scale
    update_orb_info();
}

frame::frame(const double timestamp,
             orb_extractor* extractor_left, orb_extractor* extractor_right, bow_vocabulary* bow_vocab,
             camera::base* camera, const float depth_thr)
    : id_(next_id_++),
      bow_vocab_(bow_vocab),
      extractor_(extractor_left),
      extractor_right_(extractor_right),
      timestamp_(timestamp),
      camera_(camera),
      depth_thr_(depth_thr)
{
    // Get ORB scale
    update_orb_info();
}

frame::frame(const double timestamp,
             orb_extractor* extractor, bow_vocabulary* bow_vocab, camera::base* camera, const float depth_thr,
             const cv::Mat& img_rgb)
    : id_(next_id_++),
      bow_vocab_(bow_vocab),
      extractor_(extractor),
      extractor_right_(nullptr),
      timestamp_(timestamp),
      camera_(camera),
      depth_thr_(depth_thr)
{
    // save rgb image using deep copy in case that it is a keyframe for segmentation
    segment_rgb_ = img_rgb.clone();

    // Get ORB scale
    update_orb_info();
}

void frame::extract_rgbd_features(const cv::Mat& img_gray, const cv::Mat& img_depth, const cv::Mat& mask)
{
    image_ = img_gray;
    const int min_valid_features_thr = 100;
    // Extract ORB feature
#ifdef GPU_KERNEL_PATH
    std::vector<cv::Mat> all_images;
    std::vector<std::vector<cv::KeyPoint>> all_keypts;
    std::vector<cv::Mat> all_descriptors;
    all_images.resize(1);
    all_images[0] = img_gray;
    all_keypts.resize(1);
    all_descriptors.resize(1);

    extractor_->extract(all_images, mask, all_keypts, all_descriptors);

    // Use std::move to avoid copy constructor if possible
    keypts_ = std::move(all_keypts.at(0));
    descriptors_ = std::move(all_descriptors.at(0));
#else
    extract_orb(img_gray, mask);
#endif
    num_keypts_ = keypts_.size();
    if (keypts_.empty()) {
        spdlog::warn("frame {}: cannot extract any keypoints", id_);
    }

    // Undistort keypoints
    camera_->undistort_keypoints(keypts_, undist_keypts_);

    // Calculate disparity from depth
    int valid_features = compute_stereo_from_depth(img_depth);

    if (valid_features < min_valid_features_thr)
        too_few_features_ = true;

    else
        too_few_features_ = false;

    spdlog::debug("frame {} extract {} valid features; {} keypoints; {} descriptors", id_, valid_features, num_keypts_,
                  descriptors_.rows);

    // Convert to bearing vector
    camera_->convert_keypoints_to_bearings(undist_keypts_, bearings_);

    // Initialize association with 3D points
    landmarks_ = std::vector<landmark*>(num_keypts_, nullptr);
    outlier_flags_ = std::vector<bool>(num_keypts_, false);
#ifdef ENABLE_SEMANTIC_SLAM
    segment_outlier_flags_ = std::vector<bool>(num_keypts_, false);
#endif

    // Assign all the keypoints into grid
    assign_keypoints_to_grid(camera_, undist_keypts_, keypt_indices_in_cells_);
}

void frame::extract_stereo_features(const cv::Mat& img_left, const cv::Mat& img_right, const cv::Mat& mask)
{
    image_ = img_left;
    const int min_valid_features_thr = 100;
    // Extract ORB feature
#ifdef GPU_KERNEL_PATH
    std::vector<cv::Mat> stereo_images;
    std::vector<std::vector<cv::KeyPoint>> all_keypts;
    std::vector<cv::Mat> all_descriptors;
    stereo_images.resize(2);
    stereo_images[0] = img_left;
    stereo_images[1] = img_right;
    all_keypts.resize(2);
    all_descriptors.resize(2);

    extractor_->extract(stereo_images, mask, all_keypts, all_descriptors);

    // Use std::move to avoid copy constructor if possible
    keypts_ = std::move(all_keypts.at(0));
    keypts_right_ = std::move(all_keypts.at(1));
    descriptors_ = std::move(all_descriptors.at(0));
    descriptors_right_ = std::move(all_descriptors.at(1));
#else
    std::thread thread_left(&frame::extract_orb, this, std::ref(img_left), std::ref(mask), image_side::Left);
    std::thread thread_right(&frame::extract_orb, this, std::ref(img_right), std::ref(mask), image_side::Right);
    thread_left.join();
    thread_right.join();
#endif
    num_keypts_ = keypts_.size();
    if (keypts_.empty()) {
        spdlog::warn("frame {}: cannot extract any keypoints", id_);
    }

    // Undistort keypoints
    camera_->undistort_keypoints(keypts_, undist_keypts_);  // This camera is the same for left and right image

    // Estimate depth with stereo match
#ifdef GPU_KERNEL_PATH
    std::vector<std::vector<cv::Mat>> all_image_pyramid;
    all_image_pyramid.resize(2);
    extractor_->get_image_pyramid(all_image_pyramid);
    left_image_pyramid_ = std::move(all_image_pyramid.at(0));
    right_image_pyramid_ = std::move(all_image_pyramid.at(1));
#else
    extractor_->get_image_pyramid(left_image_pyramid_);
    extractor_right_->get_image_pyramid(right_image_pyramid_);
#endif
    match::stereo stereo_matcher(left_image_pyramid_, right_image_pyramid_, keypts_,
                                 keypts_right_, descriptors_, descriptors_right_, scale_factors_, inv_scale_factors_,
                                 camera_->focal_x_baseline_, camera_->true_baseline_);
    stereo_matcher.compute(stereo_x_right_, depths_);

    int valid_features = 0;

    for (auto d : depths_) {
        if (d > 0) valid_features++;
    }

    if (valid_features < min_valid_features_thr)
        too_few_features_ = true;

    else
        too_few_features_ = false;

    spdlog::debug("frame {}: extract {} valid features; {} left keypoints; {} right keypoints; {} left descriptors; "
                  "{} right descriptors", id_, valid_features, num_keypts_, keypts_right_.size(), descriptors_.rows,
                  descriptors_right_.rows);

    // Convert to bearing vector
    camera_->convert_keypoints_to_bearings(undist_keypts_, bearings_);

    // Initialize association with 3D points
    landmarks_ = std::vector<landmark*>(num_keypts_, nullptr);
    outlier_flags_ = std::vector<bool>(num_keypts_, false);

    // Assign all the keypoints into grid
    assign_keypoints_to_grid(camera_, undist_keypts_, keypt_indices_in_cells_);
}

void frame::extract_mono_features(const cv::Mat& img_gray, const cv::Mat& mask)
{
    image_ = img_gray;
    // Extract ORB feature
#ifdef GPU_KERNEL_PATH
    std::vector<cv::Mat> all_images;
    std::vector<std::vector<cv::KeyPoint>> all_keypts;
    std::vector<cv::Mat> all_descriptors;
    all_images.resize(1);
    all_images[0] = img_gray;
    all_keypts.resize(1);
    all_descriptors.resize(1);

    extractor_->extract(all_images, mask, all_keypts, all_descriptors);

    // Use std::move to avoid copy constructor if possible
    keypts_ = std::move(all_keypts.at(0));
    descriptors_ = std::move(all_descriptors.at(0));
#else
    extract_orb(img_gray, mask);
#endif
    num_keypts_ = keypts_.size();
    if (keypts_.empty()) {
        spdlog::warn("frame {}: cannot extract any keypoints", id_);
    }

    // Undistort keypoints
    camera_->undistort_keypoints(keypts_, undist_keypts_);

    // Ignore stereo parameters
    stereo_x_right_ = std::vector<float>(num_keypts_, -1);
    depths_ = std::vector<float>(num_keypts_, -1);

    spdlog::debug("frame {} extract {} undistorted keypoints; {} keypoints; {} descriptors", id_, undist_keypts_.size(),
                  num_keypts_, descriptors_.rows);

    // Convert to bearing vector
    camera_->convert_keypoints_to_bearings(undist_keypts_, bearings_);

    // Initialize association with 3D points
    landmarks_ = std::vector<landmark*>(num_keypts_, nullptr);
    outlier_flags_ = std::vector<bool>(num_keypts_, false);

    // Assign all the keypoints into grid
    assign_keypoints_to_grid(camera_, undist_keypts_, keypt_indices_in_cells_);
}

void frame::reset_landmarks_association()
{
    for (auto& lm : landmarks_) lm = nullptr;
}

void frame::set_cam_pose(const Mat44_t& cam_pose_cw)
{
    cam_pose_cw_is_valid_ = true;
    cam_pose_cw_ = cam_pose_cw;
    update_pose_params();
}

void frame::set_cam_pose(const g2o::SE3Quat& cam_pose_cw) { set_cam_pose(util::converter::to_eigen_mat(cam_pose_cw)); }

void frame::update_pose_params()
{
    rot_cw_ = cam_pose_cw_.block<3, 3>(0, 0);
    rot_wc_ = rot_cw_.transpose();
    trans_cw_ = cam_pose_cw_.block<3, 1>(0, 3);
    cam_center_ = -rot_cw_.transpose() * trans_cw_;
}

Vec3_t frame::get_translation() const { return trans_cw_; }

Vec3_t frame::get_cam_center() const { return cam_center_; }

Mat33_t frame::get_rotation_inv() const { return rot_wc_; }

Mat44_t frame::get_cam_pose() const { return cam_pose_cw_; }

std::pair<Mat44_t, int> frame::get_prev_lidar_cam_pose() const { return {prev_lidar_cam_pose_cw_, prev_lidar_id_}; }

Mat33_t frame::get_lidar_pose() const { return lidar_pose_; }

void frame::set_lidar_use(const bool use_lidar) { use_lidar_ = use_lidar; }

bool frame::is_lidar_enable() { return use_lidar_; }

Mat33_t frame::get_imu_rotation() const
{
    return cam_pose_cw_.block(0, 0, 3, 3).transpose() * data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);
}

Vec3_t frame::get_imu_position() const
{
    return cam_pose_cw_.block(0, 0, 3, 3).transpose() * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1) -
           cam_pose_cw_.block(0, 0, 3, 3).transpose() * cam_pose_cw_.block(0, 3, 3, 1);
}

void frame::update_orb_info()
{
    num_scale_levels_ = extractor_->get_num_scale_levels();
    scale_factor_ = extractor_->get_scale_factor();
    log_scale_factor_ = std::log(scale_factor_);
    scale_factors_ = extractor_->get_scale_factors();
    inv_scale_factors_ = extractor_->get_inv_scale_factors();
    level_sigma_sq_ = extractor_->get_level_sigma_sq();
    inv_level_sigma_sq_ = extractor_->get_inv_level_sigma_sq();
}

void frame::compute_bow()
{
    if (bow_vec_.empty()) {
#ifdef USE_DBOW2
        bow_vocab_->transform(util::converter::to_desc_vec(descriptors_), bow_vec_, bow_feat_vec_, 4);
#else
        bow_vocab_->transform(descriptors_, 4, bow_vec_, bow_feat_vec_);
#endif
    }
}

bool frame::can_observe(landmark* lm, const float ray_cos_thr, Vec2_t& reproj, float& x_right,
                        unsigned int& pred_scale_level) const
{
    const Vec3_t pos_w = lm->get_pos_in_world();

    const bool in_image = camera_->reproject_to_image(rot_cw_, trans_cw_, pos_w, reproj, x_right);
    if (!in_image) {
        return false;
    }

    const Vec3_t cam_to_lm_vec = pos_w - cam_center_;
    const auto cam_to_lm_dist = cam_to_lm_vec.norm();
    if (!lm->is_inside_in_orb_scale(cam_to_lm_dist)) {
        return false;
    }

    const Vec3_t obs_mean_normal = lm->get_obs_mean_normal();
    const auto ray_cos = cam_to_lm_vec.dot(obs_mean_normal) / cam_to_lm_dist;
    if (ray_cos < ray_cos_thr) {
        return false;
    }

    pred_scale_level = lm->predict_scale_level(cam_to_lm_dist, this);
    return true;
}

std::vector<unsigned int> frame::get_keypoints_in_cell(const float ref_x, const float ref_y, const float margin,
                                                       const int min_level, const int max_level) const
{
    return data::get_keypoints_in_cell(camera_, undist_keypts_, keypt_indices_in_cells_, ref_x, ref_y, margin,
                                       min_level, max_level);
}

Vec3_t frame::triangulate_stereo(const unsigned int idx) const
{
    assert(camera_->setup_type_ != camera::setup_type_t::Monocular &&
           camera_->setup_type_ != camera::setup_type_t::Monocular_Inertial);

    switch (camera_->model_type_) {
        case camera::model_type_t::Perspective: {
            auto camera = static_cast<camera::perspective*>(camera_);

            const float depth = depths_.at(idx);
            if (0.0 < depth) {
                const float x = undist_keypts_.at(idx).pt.x;
                const float y = undist_keypts_.at(idx).pt.y;
                const float unproj_x = (x - camera->cx_) * depth * camera->fx_inv_;
                const float unproj_y = (y - camera->cy_) * depth * camera->fy_inv_;
                const Vec3_t pos_c{unproj_x, unproj_y, depth};

                // Convert from camera coordinates to world coordinates
                return rot_wc_ * pos_c + cam_center_;
            } else {
                return Vec3_t::Zero();
            }
        }
        case camera::model_type_t::Fisheye: {
            auto camera = static_cast<camera::fisheye*>(camera_);

            const float depth = depths_.at(idx);
            if (0.0 < depth) {
                const float x = undist_keypts_.at(idx).pt.x;
                const float y = undist_keypts_.at(idx).pt.y;
                const float unproj_x = (x - camera->cx_) * depth * camera->fx_inv_;
                const float unproj_y = (y - camera->cy_) * depth * camera->fy_inv_;
                const Vec3_t pos_c{unproj_x, unproj_y, depth};

                // Convert from camera coordinates to world coordinates
                return rot_wc_ * pos_c + cam_center_;
            } else {
                return Vec3_t::Zero();
            }
        }
        case camera::model_type_t::Equirectangular: {
            throw std::runtime_error("Not implemented: Stereo or RGBD of equirectangular camera model");
        }
    }

    return Vec3_t::Zero();
}

#ifndef GPU_KERNEL_PATH
void frame::extract_orb(const cv::Mat& img, const cv::Mat& mask, const image_side& img_side)
{
    switch (img_side) {
        case image_side::Left: {
            extractor_->extract(img, mask, keypts_, descriptors_);
            break;
        }
        case image_side::Right: {
            extractor_right_->extract(img, mask, keypts_right_, descriptors_right_);
            break;
        }
    }
}
#endif

int frame::compute_stereo_from_depth(const cv::Mat& right_img_depth)
{
    assert(camera_->setup_type_ == camera::setup_type_t::RGBD);

    // Initialize with invalid value
    stereo_x_right_ = std::vector<float>(num_keypts_, -1);
    depths_ = std::vector<float>(num_keypts_, -1);
    int valid_depth = 0;
    for (unsigned int idx = 0; idx < num_keypts_; idx++) {
        const auto& keypt = keypts_.at(idx);
        const auto& undist_keypt = undist_keypts_.at(idx);

        const float x = keypt.pt.x;
        const float y = keypt.pt.y;

        const float depth = right_img_depth.at<float>(y, x);

        if (depth <= 0 || std::isnan(depth)) {
            continue;
        }
        valid_depth++;
        depths_.at(idx) = depth;
        stereo_x_right_.at(idx) = undist_keypt.pt.x - camera_->focal_x_baseline_ / depth;
    }
    return valid_depth;
}

}  // namespace data
}  // namespace openvslam
