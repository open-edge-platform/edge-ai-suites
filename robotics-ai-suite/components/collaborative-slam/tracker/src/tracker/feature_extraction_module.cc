// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "feature_extraction_module.h"
#include "tracking_module.h"
#include "feature/orb_params.h"
#include "util/image_converter.h"

#include <opencv2/opencv.hpp>

#include <thread>
#include <queue>
using std::priority_queue;

// These parameters were found empirically
#define C_TH_MAX 1000          // Edge points: threshold to determine sharp edges
#define C_TH_MIN 400           // Planar points: threshold to determine planar surface patches
#define MAX_LIDAR_FEATURE 360  // Maximum number of lidar feature points to allow
#define SQ_DIST_TH 0.05        // the squared distance threshold in meter, found empirically
#define LIDAR_FAIL_TH 0.5      // Feature matching failure threshold in meter, found empirically

namespace openvslam {

int feature_extraction_module::lidar_frame_id_ = 0;

feature_extraction_module::feature_extraction_module(std::shared_ptr<univloc_tracker::Config> cfg,
                                                     camera::base* camera, data::bow_vocabulary* bow_vocab,
                                                     RequestQueue& request_queue, FeatureQueue& feature_queue,
                                                     std::shared_ptr<openvslam::util::stereo_rectifier> rectifier)
    : cfg_(cfg),
      camera_(camera),
      bow_vocab_(bow_vocab),
      request_queue_(request_queue),
      feature_queue_(feature_queue),
      rectifier_(rectifier)
{
    init(cfg);
}

feature_extraction_module::feature_extraction_module(std::shared_ptr<univloc_tracker::Config> cfg,
                                                     camera::base* camera, data::bow_vocabulary* bow_vocab,
                                                     RequestQueue& request_queue,
                                                     RequestLidarQueue* ptr_request_lidar_queue,
                                                     FeatureQueue& feature_queue,
                                                     std::shared_ptr<openvslam::util::stereo_rectifier> rectifier)
    : cfg_(cfg),
      camera_(camera),
      bow_vocab_(bow_vocab),
      request_queue_(request_queue),
      ptr_request_lidar_queue_(ptr_request_lidar_queue),
      feature_queue_(feature_queue),
      rectifier_(rectifier)
{
    init(cfg);
}

void feature_extraction_module::init(std::shared_ptr<univloc_tracker::Config> cfg)
{
#ifndef GPU_KERNEL_PATH
    orb_params orb_params(cfg->max_num_keypoints_, cfg->orb_scale_factor_, cfg->orb_num_levels_,
                          cfg->orb_ini_fast_threshold_, cfg->orb_min_fast_threshold_, cfg->mask_rects_);
#endif

    if (camera_->setup_type_ == camera::setup_type_t::Stereo ||
        camera_->setup_type_ == camera::setup_type_t::Stereo_Inertial) {
#ifdef GPU_KERNEL_PATH
        extractor_left_ = new orb_extractor(cfg->max_num_keypoints_, cfg->orb_scale_factor_, cfg->orb_num_levels_,
                                            cfg->orb_ini_fast_threshold_, cfg->orb_min_fast_threshold_, 2,
                                            cfg->mask_rects_);
        extractor_left_->set_gpu_kernel_path(ORBLZE_KERNEL_PATH_STRING);
#else
        extractor_left_ = new orb_extractor(orb_params);
        extractor_right_ = new orb_extractor(orb_params);
#endif
    } else if (camera_->setup_type_ == camera::setup_type_t::Monocular ||
               camera_->setup_type_ == camera::setup_type_t::Monocular_Inertial) {
#ifdef GPU_KERNEL_PATH
        extractor_left_ = new orb_extractor(cfg->max_num_keypoints_, cfg->orb_scale_factor_, cfg->orb_num_levels_,
                                            cfg->orb_ini_fast_threshold_, cfg->orb_min_fast_threshold_, 1,
                                            cfg->mask_rects_);
        extractor_left_->set_gpu_kernel_path(ORBLZE_KERNEL_PATH_STRING);
#else
        extractor_left_ = new orb_extractor(orb_params);
#endif
        // TODO: orb3 use max_num_keypoints_ * 5
        extractor_left_->set_max_num_keypoints(cfg_->max_num_keypoints_ * 2);
    } else if (camera_->setup_type_ == camera::setup_type_t::RGBD ||
               camera_->setup_type_ == camera::setup_type_t::RGBD_Inertial) {
#ifdef GPU_KERNEL_PATH
        extractor_left_ = new orb_extractor(cfg->max_num_keypoints_, cfg->orb_scale_factor_, cfg->orb_num_levels_,
                                            cfg->orb_ini_fast_threshold_, cfg->orb_min_fast_threshold_, 1,
                                            cfg->mask_rects_);
        extractor_left_->set_gpu_kernel_path(ORBLZE_KERNEL_PATH_STRING);
#else
        extractor_left_ = new orb_extractor(orb_params);
#endif
    } else {
        throw std::runtime_error("error camera type, only support 1: Monocular; 2: Stereo; 3: RGBD; 4: RGBD_Inertial; "
                                 "5: Stereo_Inertial; 6: Monocular_Inertial");
    }

    // TODO handle exception of file non-existence
    if (!cfg_->mask_image_path_.empty()) mask_ = cv::imread(cfg_->mask_image_path_, cv::IMREAD_GRAYSCALE);
}

feature_extraction_module::~feature_extraction_module()
{
    delete extractor_left_;
    extractor_left_ = nullptr;
    delete extractor_right_;
    extractor_right_ = nullptr;
}

void feature_extraction_module::set_tracking_module(tracking_module* tracking_module)
{
    tracking_module_ = tracking_module;
}

void feature_extraction_module::run()
{
    timer_.setName("Feature Extraction Module");
    timer_.start();
    std::shared_ptr<ImageFrame> request;
    std::shared_ptr<data::frame> frame;
    while (true) {
        timer_.startFirstProc("wait for new frame");

        if (!request_queue_.wait_pop(request)) break;

        timer_.startNextProc("prepare");
        double timestamp = request->timestamp;

        // recitify stereo input before feature extraction
        cv::Mat img1, img2;
        if (cfg_->is_stereo() && cfg_->enable_rectifier_) {
            rectifier_->rectify(request->image1, request->image2, img1, img2);
        } else if (cfg_->is_rgbd()) {
            /*
                for rgbd, request->image1 is one of the input while constructing frame,
                therefore, we need to save a copy of it.

                It is needed only in case of segmentation. We will make copy
                only in that case to save some of the CPU time.
            */
#ifdef ENABLE_SEMANTIC_SLAM
            img1 = request->image1.clone();
#else
            img1 = request->image1;
#endif
            img2 = request->image2;
        } else {
            /*
                for monocular or stereo input without recification, request->image1 and
                request->image2 are not used for other inputs later. Therefore, no need
                to save a copy, use shallow copy to speed up.
            */
            img1 = request->image1;
            img2 = request->image2;
        }

        util::convert_to_grayscale(img1, camera_->color_order_);

        if (cfg_->is_monocular()) {
            if (!tracking_module_)
                throw std::runtime_error("feature_extraction_module doesn't have the pointer to tracking_module!");
            if (tracking_module_->is_initializing()) {
                timer_.startNextProc("construct mono frame with initialization config");
                extractor_left_->set_max_num_keypoints(cfg_->max_num_keypoints_ * 2);
                frame = std::make_shared<data::frame>(timestamp, extractor_left_, bow_vocab_, &*camera_,
                                                      cfg_->depth_threshold_);
                frame->extract_mono_features(img1, mask_);
            } else {
                timer_.startNextProc("construct mono frame");
                extractor_left_->set_max_num_keypoints(cfg_->max_num_keypoints_);
                frame = std::make_shared<data::frame>(timestamp, extractor_left_, bow_vocab_, &*camera_,
                                                      cfg_->depth_threshold_);
                frame->extract_mono_features(img1, mask_);
            }
        } else if (cfg_->is_stereo()) {
            util::convert_to_grayscale(img2, camera_->color_order_);
            timer_.startNextProc("construct stereo frame");
            frame = std::make_shared<data::frame>(timestamp, extractor_left_, extractor_right_, bow_vocab_,
                                                  &*camera_, cfg_->depth_threshold_);
            frame->extract_stereo_features(img1, img2, mask_);
        } else if (cfg_->is_rgbd()) {
            util::convert_to_true_depth(img2, cfg_->depthmap_factor_);
            timer_.startNextProc("construct RGBD frame");
            frame = std::make_shared<data::frame>(timestamp, extractor_left_, bow_vocab_, &*camera_,
                                                  cfg_->depth_threshold_, request->image1);
            frame->extract_rgbd_features(img1, img2, mask_);
        }

        /*
            In previous operations, img1/2 and request->image1/2 may already differ, for example, in functions like
            convert_to_grayscale and convert_to_true_depth, new memory will be allocated if the data types between
            input and output cv::mat are different.

            In subsequent operations of the current code base, only request->image2 will be used in fast mapping
            module as depth image input, while request->image1 is not used anywhere. Therefore, to avoid duplicated
            processing, we will perform post-processing to make sure that img1/2 and request->image1/2 are the same.

            As the result, for almost all the data after feature extraction module (i.e., inside frame class,
            feature_queue_, result_queue_, reconstruction_queue_), color images are grayscale and the data type of
            depth images are float with meter as the unit, except in case of segmentation, raw color image will be
            used as input for frame constructor and later saved as segment_rgb_ using deep copy.
        */
        request->image1 = img1;
        request->image2 = img2;

        if (cfg_->lidar_enable_) {
            process_lidar_frame(frame, timestamp);
        }
        std::pair<std::shared_ptr<ImageFrame>, std::shared_ptr<data::frame>> pair = std::make_pair(request, frame);
        if (!feature_queue_.wait_push(pair)) break;
        timer_.endCycle();
    }
    timer_.finish();
    std::cout << timer_.result();
}

void feature_extraction_module::process_lidar_frame(std::shared_ptr<data::frame> frame, double& timestamp)
{
    float sync_th = (1.0 / cfg_->camera_fps_) * (1e3);  // ms
    std::shared_ptr<LidarFrame> request_lidar;
    frame->set_lidar_use(true);
    frame->lidar_landmarks_.updated = false;
    while (ptr_request_lidar_queue_->try_pop(request_lidar)) { /* only deal with the latest */
    }
    if (request_lidar) {
        // Lidar data received
        double delta_t_ms = (timestamp - request_lidar->timestamp) * (1e3);
        prev_extracted_lidar_points_.clear();
        prev_extracted_lidar_points_ = extracted_lidar_points_;

        // If received lidar data timestamp is greater than threshold, data is outside
        // acceptable range. So we ignore
        if (std::abs(delta_t_ms) > sync_th) {
            frame->lidar_landmarks_.updated = false;
        } else {
            frame->lidar_landmarks_.updated = true;
            extract_lidar_feature(request_lidar->points2d);
            // in next version place the match feature points in the univloc tracking module.
            // in the mapping module we can use imu data. use IMU to project prev extracted points
            frame->matched_feature_points_ = match_lidar_points(prev_extracted_lidar_points_,
                                                                extracted_lidar_points_);
            frame->lidar_frame_id_ = lidar_frame_id_;
            lidar_frame_id_++;
        }
        frame->lidar_landmarks_.timestamp = request_lidar->timestamp;
    }
}
void feature_extraction_module::extract_lidar_feature(const std::vector<cv::Point2d>& points)
{
    extracted_lidar_points_.clear();
    std::vector<std::set<std::pair<float, int>>> sorted_c;
    calculate_curvature(points, sorted_c);

    for (unsigned int i = 0; i < sorted_c.size(); i++) {
        std::set<std::pair<float, int>>::iterator it = sorted_c[i].begin();
        std::set<std::pair<float, int>>::reverse_iterator it_r = sorted_c[i].rbegin();
        int count = 0;
        while (it != sorted_c[i].end() && it_r != sorted_c[i].rend()) {
            // Planar Points
            if (it->first < C_TH_MIN &&
                !is_close_to_boundary(points[it->second], points[(it->second) - 1], points[(it->second) + 1]) &&
                !is_point_too_close(points[it->second])) {
                extracted_lidar_points_.push_back({points[it->second], lidar_frame_id_});
                count++;
            }
            // Edge Points
            if (it_r->first > C_TH_MAX &&
                !is_close_to_boundary(points[it_r->second], points[(it_r->second) - 1],
                                     points[(it_r->second) + 1]) && !is_point_too_close(points[it_r->second])) {
                extracted_lidar_points_.push_back({points[it_r->second], lidar_frame_id_});
                count++;
            }
            if (count == MAX_LIDAR_FEATURE / 4) break;  // To make sure we get points from each quadrants
            it++;
            it_r++;
        }
    }
}

void feature_extraction_module::calculate_curvature(const std::vector<cv::Point2d>& points,
                                                    std::vector<std::set<std::pair<float, int>>>& sorted_c)
{
    std::set<std::pair<float, int>> quad_i;
    std::set<std::pair<float, int>> quad_ii;
    std::set<std::pair<float, int>> quad_iii;
    std::set<std::pair<float, int>> quad_iv;
    // Based on LOAM implementation, the magic number 5 is chosen.
    for (unsigned int i = 5; i < points.size() - 5; i++) {
        cv::Point2d diffRange = points[i - 5] + points[i - 4] + points[i - 3] + points[i - 2] + points[i - 1] +
                                points[i] * 10 + points[i + 1] + points[i + 2] + points[i + 3] + points[i + 4] +
                                points[i + 5];
        float diff = (diffRange.x * diffRange.x) + (diffRange.y * diffRange.y);
        if (!std::isinf(diff)) {
            if (i < (points.size() / 4) - 5 && !std::isinf(diff)) {
                quad_i.insert({diff, i});
            }

            if (i > (points.size() / 4) + 5 && i < (points.size() / 2) - 5 && !std::isinf(diff)) {
                quad_ii.insert({diff, i});
            }

            if (i > (points.size() / 2) + 5 && i < ((points.size() / 4 + points.size() / 2)) - 5 &&
                !std::isinf(diff)) {
                quad_iii.insert({diff, i});
            }

            if (i > (points.size() / 4 + points.size() / 2) + 5 && i < (points.size()) - 5 && !std::isinf(diff)) {
                quad_iv.insert({diff, i});
            }
        }
    }

    sorted_c.push_back(quad_i);
    sorted_c.push_back(quad_ii);
    sorted_c.push_back(quad_iii);
    sorted_c.push_back(quad_iv);
}

// Check for boundary of occluded region.
// If a depth of a consecutive points are significantly larger than the depth of the current
// point, we can assume it is boundary of occluded region.
bool feature_extraction_module::is_close_to_boundary(const cv::Point2d& p, const cv::Point2d& pm1,
                                                    const cv::Point2d& pp1)
{
    double dx = pp1.x - p.x;
    double dy = pp1.y - p.y;
    double diff = dx * dx + dy * dy;

    double dx_b = pm1.x - p.x;
    double dy_b = pm1.y - p.y;
    double diff_b = dx_b * dx_b + dy_b * dy_b;
    return (diff > SQ_DIST_TH || diff_b > SQ_DIST_TH) ? true : false;
}

// Check to see if any of the surrending point is already selected
bool feature_extraction_module::is_point_too_close(const cv::Point2d& p)
{
    double x = p.x;
    double y = p.y;
    for (unsigned int i = 0; i < extracted_lidar_points_.size(); i++) {
        double x1 = extracted_lidar_points_[i].first.x;
        double y1 = extracted_lidar_points_[i].first.y;
        double dist_sq = (x - x1) * (x - x1) + (y - y1) * (y - y1);
        if (dist_sq < SQ_DIST_TH) return true;
    }
    return false;
}

std::vector<std::tuple<cv::Point2d, cv::Point2d, double>> feature_extraction_module::match_lidar_points(
    std::vector<std::pair<cv::Point2d, int>>& prev, std::vector<std::pair<cv::Point2d, int>>& curr)
{
    std::vector<std::tuple<cv::Point2d, cv::Point2d, double>> matched_points;
    for (unsigned int i = 0; i < prev.size(); i++) {
        std::tuple<cv::Point2d, cv::Point2d, double> temp = knearest_neighbor(prev[i].first, curr, 1);
        matched_points.push_back(temp);
        if (std::get<2>(temp) > LIDAR_FAIL_TH) {
            lidar_feature_failure_count_++;
        }
    }
    return matched_points;
}

int feature_extraction_module::get_lidar_feature_failure_count()
{
    return lidar_feature_failure_count_;
}

std::tuple<cv::Point2d, cv::Point2d, double> feature_extraction_module::knearest_neighbor(
    const cv::Point2d& p1, std::vector<std::pair<cv::Point2d, int>>& points, unsigned int K)
{
    std::tuple<cv::Point2d, cv::Point2d, double> kpoints;
    priority_queue<std::pair<double, int>> max_heap;
    for (unsigned int i = 0; i < points.size(); i++) {
        double dist = (p1.x - points[i].first.x) * (p1.x - points[i].first.x) +
                      (p1.y - points[i].first.y) * (p1.y - points[i].first.y);
        max_heap.push(std::make_pair(dist, i));
        if (max_heap.size() > K) {
            max_heap.pop();
        }
    }
    while (!max_heap.empty()) {
        kpoints = std::make_tuple(p1, points[max_heap.top().second].first, max_heap.top().first);
        max_heap.pop();
    }
    return kpoints;
}

}  // namespace openvslam
