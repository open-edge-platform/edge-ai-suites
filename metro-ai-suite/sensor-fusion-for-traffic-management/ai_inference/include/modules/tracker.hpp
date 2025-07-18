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

#ifndef HCE_AI_INF_MODULE_VAS_TRACKER_HPP
#define HCE_AI_INF_MODULE_VAS_TRACKER_HPP

#include <cstdint>
#include <deque>
#include <opencv2/opencv.hpp>

#include "modules/vas/common.h"
#include "modules/vas/components/ot/mtt/objects_associator.h"
#include "modules/vas/common/exception.h"
#include "modules/vas/common/prof.h"

#include "modules/tracklet_wrap.hpp"

#include "common/common.hpp"


namespace vas{

namespace ot{

const int32_t kDefaultMaxNumObjects = -1;
const float kMaxTargetAreaFactor = 0.8f;
const float kMinRegionRatioInImageBoundary = 0.75f; // MIN_REGION_RATIO_IN_IMAGE_BOUNDARY

enum struct TrackingAlgoType {
    ZERO_TERM_IMAGELESS = 0,        // requires object detection run on every frame, track without access to image data
    ZERO_TERM_COLOR_HISTOGRAM,      // requires object detection run on every frame, track with color histogram similarity
    SHORT_TERM_IMAGELESS,           // det interval > 1, extrapolates object trajectory from previous frame(s), track without access to image data.
    // SHORT_TERM_KCFVAR,              // det interval > 1, extrapolates object trajectory from previous frame(s), track with kcfvar
};

struct TrackResultContainer {  // for per-frame results collection
    int32_t track_id = -1;            // tracklet id
    Status status = Status::ST_NEW;   // tracklet status at current frame
    int32_t obj_index = -1;           // the index of matching detected object
    cv::Rect2f obj_predicted;         // Predicted bounding box from Kalman prediction
    double obj_confidence;       // the detection confidence of matching detected object
    int32_t obj_label;                // the class label_id of matching detected object
    std::string obj_label_name;       // the class label_name of matching detected object
};

class Tracker {
  public:

    class InitParameters {
      public:
        TrackingAlgoType tracking_type; // tracking type
        int32_t max_num_objects;
        int32_t max_num_threads; // for Parallelization
        hce::ai::inference::ColorFormat format;
        bool tracking_per_class;

        // Won't be exposed to the external
        float min_region_ratio_in_boundary; // For ST, ZT
    };

  public:
    virtual ~Tracker();

    /**
     * create new object tracker instance
     * @param InitParameters
     */
    static Tracker *CreateInstance(InitParameters init_parameters);

    /**
     * perform tracking
     *
     * @param[in] mat Input frame
     * @param[in] detection Newly detected object data vector which will be added to the tracker. put zero length vector
     *            if there is no new object in the frame.
     * @param[in] delta_t Time passed after the latest call to TrackObjects() in seconds. Use 1.0/FPS in case of
     * constant frame rate
     * @param[out] tracklets Tracked object data vector.
     * @return 0 for success. negative value for failure
     */
    virtual int32_t TrackObjects(const cv::Mat &mat, const std::vector<Detection> &detections,
                                 std::vector<std::shared_ptr<Tracklet>> *tracklets, float delta_t = 0.033f) = 0;

    /**
     * @brief format tracking result for current frame
     * 
     * @return std::vector<TrackResultContainer> 
     */
    std::vector<TrackResultContainer> FormatTrackResult();

    /**
     * remove object
     *
     * @param[in] id Object id for removing. it should be the 'id' value of the Tracklet
     * @return 0 for success. negative value for failure.
     */
    int32_t RemoveObject(const int32_t id);

    /**
     * reset all internal state to its initial.
     *
     * @return 0 for success. negative value for failure.
     */
    void Reset(void);

    /**
     * get cumulated frame number
     *
     * @return 0
     */
    int32_t GetFrameCount(void) const;

    void SetImageColorFormat(hce::ai::inference::ColorFormat format_in);

  protected:
    explicit Tracker(int32_t max_objects, float min_region_ratio_in_boundary, hce::ai::inference::ColorFormat format,
                     bool tracking_per_class = true);
    Tracker() = delete;

    int32_t GetNextTrackingID();
    void IncreaseFrameCount();

    void ComputeOcclusion();

    void RemoveOutOfBoundTracklets(int32_t input_width, int32_t input_height, bool is_filtered = false);
    void RemoveDeadTracklets();
    bool RemoveOneLostTracklet();

  protected:
    int32_t max_objects_; // -1 means no limitation
    int32_t next_id_;
    int32_t frame_count_;

    float min_region_ratio_in_boundary_;
    hce::ai::inference::ColorFormat input_image_format_;

    ObjectsAssociator associator_;
    std::vector<std::shared_ptr<Tracklet>> tracklets_;
};


}; // namespace ot
}; // namespace vas

#endif //#ifndef HCE_AI_INF_MODULE_VAS_TRACKER_HPP