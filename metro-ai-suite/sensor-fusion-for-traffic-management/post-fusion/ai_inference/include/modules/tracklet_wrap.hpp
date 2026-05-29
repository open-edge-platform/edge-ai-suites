/*******************************************************************************
 * Copyright (C) 2018-2022 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#ifndef HCE_AI_INF_MODULE_TRACKLET_WRAP_HPP
#define HCE_AI_INF_MODULE_TRACKLET_WRAP_HPP

#include <cstdint>
#include <deque>
#include <opencv2/opencv.hpp>

#include "common/common.hpp"

#include "modules/vas/common.h"
#include "modules/vas/components/ot/kalman_filter/kalman_filter_no_opencv.h"


namespace vas {
namespace ot {

const int32_t kNoMatchDetection = -1;

struct Detection {
    cv::Rect2f rect;
    int32_t class_label = -1;
    std::string class_label_name;
    float confidence;
    int32_t index = -1;
};

// Define `Status` used in vas/ot
// to align with `hce::ai::inference::TrackingStatus`
enum Status {
    ST_NEW = (int)hce::ai::inference::TrackingStatus::NEW,           // new
    ST_TRACKED = (int)hce::ai::inference::TrackingStatus::TRACKED,   // tracked
    ST_LOST = (int)hce::ai::inference::TrackingStatus::LOST,         // lost but still alive (in the detection phase if it configured)
    ST_DEAD = (int)hce::ai::inference::TrackingStatus::DEAD,         // dead
};

/** 
 * @brief convert tracking status to string
 */
inline const char* TrackStatusToString(unsigned status)
{   
    hce::ai::inference::TrackingStatus v = (hce::ai::inference::TrackingStatus)status;
    switch (v)
    {
        case hce::ai::inference::TrackingStatus::NONE:      return "";
        case hce::ai::inference::TrackingStatus::DEAD:      return "DEAD";
        case hce::ai::inference::TrackingStatus::NEW:       return "NEW";
        case hce::ai::inference::TrackingStatus::TRACKED:   return "TRACKED";
        case hce::ai::inference::TrackingStatus::LOST:      return "LOST";
        default:                                            return "[Unknown Status]";
    }
}

class Tracklet {
  public:
    Tracklet();
    virtual ~Tracklet();

  public:
    void ClearTrajectory();
    void InitTrajectory(const cv::Rect2f &bounding_box);
    void AddUpdatedTrajectory(const cv::Rect2f &bounding_box, const cv::Rect2f &corrected_box);
    void UpdateLatestTrajectory(const cv::Rect2f &bounding_box, const cv::Rect2f &corrected_box);
    virtual void RenewTrajectory(const cv::Rect2f &bounding_box);

    virtual std::deque<cv::Mat> *GetRgbFeatures();
    virtual std::string Serialize() const; // Returns key:value with comma separated format

  public:
    int32_t id;                 // track id, if has not been assigned : -1 to 0
    int32_t label;              // detection class_label index
    std::string label_name;     // detection class_label name
    int32_t association_idx;    // matched detection index
    Status status;
    int32_t age;
    float confidence;           // detection confidence

    float occlusion_ratio;
    float association_delta_t;
    int32_t association_fail_count;

    std::deque<cv::Rect2f> trajectory;
    std::deque<cv::Rect2f> trajectory_filtered;
    cv::Rect2f predicted;                      // Result from Kalman prediction. It is for debugging (OTAV)
    mutable std::vector<std::string> otav_msg; // Messages for OTAV
};

class ZeroTermChistTracklet : public Tracklet {
  public:
    ZeroTermChistTracklet();
    virtual ~ZeroTermChistTracklet();

    std::deque<cv::Mat> *GetRgbFeatures() override;

  public:
    int32_t birth_count;
    std::deque<cv::Mat> rgb_features;
    std::unique_ptr<KalmanFilterNoOpencv> kalman_filter;
};

class ZeroTermImagelessTracklet : public Tracklet {
  public:
    ZeroTermImagelessTracklet();
    virtual ~ZeroTermImagelessTracklet();

    void RenewTrajectory(const cv::Rect2f &bounding_box) override;

  public:
    int32_t birth_count;
    std::unique_ptr<KalmanFilterNoOpencv> kalman_filter;
};

class ShortTermImagelessTracklet : public Tracklet {
  public:
    ShortTermImagelessTracklet();
    virtual ~ShortTermImagelessTracklet();

    void RenewTrajectory(const cv::Rect2f &bounding_box) override;

  public:
    std::unique_ptr<KalmanFilterNoOpencv> kalman_filter;
};

}; // namespace ot
}; // namespace vas

#endif //#ifndef HCE_AI_INF_MODULE_TRACKLET_WRAP_HPP
