// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include "camera/base.h"
#include "data/frame.h"
#include "orb_extractor.h"
#include "UserConfig.h"
#include "LoopTimer.h"
#include "util/stereo_rectifier.h"
#include "tracker/QueueTypes.h"

#include <opencv2/core/core.hpp>
#include <opencv2/features2d/features2d.hpp>

#include <memory>
#include <tuple>

namespace openvslam {

class tracking_module;

class feature_extraction_module {
public:
    //! Constructor
    feature_extraction_module(std::shared_ptr<univloc_tracker::Config> cfg, camera::base* camera,
                              data::bow_vocabulary* bow_vocab, RequestQueue& request_queue,
                              FeatureQueue& feature_queue,
                              std::shared_ptr<openvslam::util::stereo_rectifier> rectifier);

    feature_extraction_module(std::shared_ptr<univloc_tracker::Config> cfg, camera::base* camera,
                              data::bow_vocabulary* bow_vocab, RequestQueue& request_queue,
                              RequestLidarQueue* ptr_request_lidar_queue_, FeatureQueue& feature_queue,
                              std::shared_ptr<openvslam::util::stereo_rectifier> rectifier);

    void init(std::shared_ptr<univloc_tracker::Config> cfg);

    //! Destructor
    ~feature_extraction_module();

    feature_extraction_module(const feature_extraction_module&) = delete;
    feature_extraction_module& operator=(const feature_extraction_module&) = delete;

    //! Set the tracking module
    void set_tracking_module(tracking_module* tracking_module);

    void run();

    int get_lidar_feature_failure_count();

protected:
    std::shared_ptr<univloc_tracker::Config> cfg_;
    camera::base* camera_;
    data::bow_vocabulary* bow_vocab_;
    RequestQueue& request_queue_;
    RequestLidarQueue* ptr_request_lidar_queue_ = nullptr;
    FeatureQueue& feature_queue_;

    tracking_module* tracking_module_ = nullptr;

    // ORB extractors
    //! ORB extractor for left/monocular image
    orb_extractor* extractor_left_ = nullptr;
    //! ORB extractor for right image
    orb_extractor* extractor_right_ = nullptr;

    cv::Mat mask_;
    LoopTimer timer_;
    std::shared_ptr<openvslam::util::stereo_rectifier> rectifier_;
    static int lidar_frame_id_;
    std::vector<std::pair<cv::Point2d, int>> extracted_lidar_points_;
    std::vector<std::pair<cv::Point2d, int>> prev_extracted_lidar_points_;
    void extract_lidar_feature(const std::vector<cv::Point2d>& points);
    void process_lidar_frame(std::shared_ptr<data::frame> frame, double& timestamp);
    void calculate_curvature(const std::vector<cv::Point2d>& points,
                             std::vector<std::set<std::pair<float, int>>>& sorted_c);
    std::vector<std::tuple<cv::Point2d, cv::Point2d, double>> match_lidar_points(
        std::vector<std::pair<cv::Point2d, int>>& prev, std::vector<std::pair<cv::Point2d, int>>& curr);
    std::tuple<cv::Point2d, cv::Point2d, double> knearest_neighbor(const cv::Point2d& p1,
                                                                   std::vector<std::pair<cv::Point2d, int>>& points,
                                                                   unsigned int K);
    bool is_close_to_boundary(const cv::Point2d& p, const cv::Point2d& pm1, const cv::Point2d& pp1);
    bool is_point_too_close(const cv::Point2d& p);
    int lidar_feature_failure_count_ = 0;
};

}  // namespace openvslam
