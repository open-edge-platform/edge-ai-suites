/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/


#include "modules/tracker.hpp"

#include "modules/vas/components/ot/short_term_imageless_tracker.h"
#include "modules/vas/components/ot/zero_term_chist_tracker.h"
#include "modules/vas/components/ot/zero_term_imageless_tracker.h"


namespace vas{

namespace ot{


Tracker::Tracker(int32_t max_objects, float min_region_ratio_in_boundary, 
                    hce::ai::inference::ColorFormat format, bool tracking_per_class)
    : max_objects_(max_objects), next_id_(1), frame_count_(0),
      min_region_ratio_in_boundary_(min_region_ratio_in_boundary), input_image_format_(format),
      associator_(ObjectsAssociator(tracking_per_class)) {
}

Tracker::~Tracker() {
}

Tracker *Tracker::CreateInstance(InitParameters init_parameters) {
    TRACE("START CreateInstance Tracker");

    Tracker *tracker = nullptr;
    if ((init_parameters.tracking_type == TrackingAlgoType::SHORT_TERM_IMAGELESS)) {
        tracker = new ShortTermImagelessTracker(init_parameters);
    } else if (init_parameters.tracking_type == TrackingAlgoType::ZERO_TERM_COLOR_HISTOGRAM) {
        tracker = new ZeroTermChistTracker(init_parameters);
    } else if (init_parameters.tracking_type == TrackingAlgoType::ZERO_TERM_IMAGELESS) {
        tracker = new ZeroTermImagelessTracker(init_parameters);
    } else {
        throw std::runtime_error("Unsupported tracking type");
    }

    TRACE(" - max_num_objects(%d)", init_parameters.max_num_objects);

    TRACE("END");
    return tracker;
}

/**
 * @brief format tracking result for current frame
 * 
 * @return std::vector<TrackResultContainer> 
 */
std::vector<TrackResultContainer> Tracker::FormatTrackResult() {

    std::vector<TrackResultContainer> result;
    result.reserve(tracklets_.size());
    
    for (auto tracklet = tracklets_.begin(); tracklet != tracklets_.end(); ++tracklet) {

        //
        // do not match any det this time but the status is not marked as `TrackingStatus::LOST`
        // this can happen when m_detection_frame_skip > 1, then the status is between `TrackingStatus::TRACKED` and `TrackingStatus::LOST`
        //
        if ((*tracklet)->id == -1) {
            continue;
        }

        TrackResultContainer tmp;
        tmp.track_id = (*tracklet)->id;
        tmp.obj_label = (*tracklet)->label;
        tmp.obj_label_name = (*tracklet)->label_name;
        tmp.obj_confidence = (*tracklet)->confidence;
        tmp.status = (*tracklet)->status;
        tmp.obj_index = (*tracklet)->association_idx;
        tmp.obj_predicted = (*tracklet)->predicted;
        result.emplace_back(tmp);
    }

    return result;
}

int32_t Tracker::RemoveObject(const int32_t id) {
    if (id == 0)
        return -1;

    for (auto tracklet = tracklets_.begin(); tracklet != tracklets_.end(); ++tracklet) {
        if ((*tracklet)->id == id) {
            tracklet = tracklets_.erase(tracklet);
            return 0;
        }
    }
    return -1;
}

void Tracker::Reset(void) {
    frame_count_ = 0;
    next_id_ = 1;
    tracklets_.clear();
}

int32_t Tracker::GetFrameCount(void) const {
    return frame_count_;
}


void Tracker::SetImageColorFormat(hce::ai::inference::ColorFormat format_in) {
    if (input_image_format_ != format_in) {
        std::cout << "update input image format: " << input_image_format_ << " => " << format_in << std::endl;
        input_image_format_ = format_in;
    }
}

int32_t Tracker::GetNextTrackingID() {
    return next_id_++;
}

void Tracker::IncreaseFrameCount() {
    frame_count_++;
}

void Tracker::ComputeOcclusion() {
    // Compute occlusion ratio
    for (int32_t t0 = 0; t0 < static_cast<int32_t>(tracklets_.size()); ++t0) {
        auto &tracklet0 = tracklets_[t0];
        if (tracklet0->status != ST_TRACKED)
            continue;

        const cv::Rect2f &r0 = tracklet0->trajectory.back();
        float max_occlusion_ratio = 0.0f;
        for (int32_t t1 = 0; t1 < static_cast<int32_t>(tracklets_.size()); ++t1) {
            const auto &tracklet1 = tracklets_[t1];
            if (t0 == t1 || tracklet1->status == ST_LOST)
                continue;

            const cv::Rect2f &r1 = tracklet1->trajectory.back();
            max_occlusion_ratio = std::max(max_occlusion_ratio, (r0 & r1).area() / r0.area()); // different from IoU
        }
        tracklets_[t0]->occlusion_ratio = max_occlusion_ratio;
    }
}

void Tracker::RemoveOutOfBoundTracklets(int32_t input_width, int32_t input_height, bool is_filtered) {
    const cv::Rect2f image_region(0.0f, 0.0f, static_cast<float>(input_width), static_cast<float>(input_height));
    for (auto tracklet = tracklets_.begin(); tracklet != tracklets_.end();) {
        const cv::Rect2f &object_region =
            is_filtered ? (*tracklet)->trajectory_filtered.back() : (*tracklet)->trajectory.back();
        if ((image_region & object_region).area() / object_region.area() <
            min_region_ratio_in_boundary_) { // only 10% is in image boundary
            tracklet = tracklets_.erase(tracklet);
        } else {
            ++tracklet;
        }
    }
}

void Tracker::RemoveDeadTracklets() {
    for (auto tracklet = tracklets_.begin(); tracklet != tracklets_.end();) {
        if ((*tracklet)->status == ST_DEAD) {
            tracklet = tracklets_.erase(tracklet);
        } else {
            ++tracklet;
        }
    }
}

bool Tracker::RemoveOneLostTracklet() {
    for (auto tracklet = tracklets_.begin(); tracklet != tracklets_.end();) {
        if ((*tracklet)->status == ST_LOST) {
            // The first tracklet is the oldest
            tracklet = tracklets_.erase(tracklet);
            return true;
        } else {
            ++tracklet;
        }
    }

    return false;
}

}; // namespace ot
}; // namespace vas