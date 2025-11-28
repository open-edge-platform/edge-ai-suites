/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <dlstreamer/gst/videoanalytics/video_frame.h>

#include <unordered_map>
#include <vector>

G_BEGIN_DECLS

typedef struct _GstReID GstReID;
typedef struct _GstReIDClass GstReIDClass;

#define GST_TYPE_REID (gst_reid_get_type())
#define GST_REID(obj) (G_TYPE_CHECK_INSTANCE_CAST((obj), GST_TYPE_REID, GstReID))
#define GST_REID_CLASS(klass) (G_TYPE_CHECK_CLASS_CAST((klass), GST_TYPE_REID, GstReIDClass))
#define GST_IS_REID(obj) (G_TYPE_CHECK_INSTANCE_TYPE((obj), GST_TYPE_REID))
#define GST_IS_REID_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE((klass), GST_TYPE_REID))

// Feature vector structure for ReID
struct FeatureVector {
    std::vector<float> features;
    GstClockTime timestamp;
    uint32_t object_id;
    GVA::Rect<uint32_t> bbox;

    FeatureVector() : timestamp(GST_CLOCK_TIME_NONE), object_id(0), bbox{0, 0, 0, 0} {
    }
    FeatureVector(const std::vector<float> &feat, GstClockTime pts = GST_CLOCK_TIME_NONE, uint32_t id = 0)
        : features(feat), timestamp(pts), object_id(id), bbox{0, 0, 0, 0} {
    }
};

// Object tracking history
struct ObjectHistory {
    uint32_t id;
    std::vector<FeatureVector> feature_history;
    GstClockTime last_seen_timestamp;
    guint last_seen_frame;
    uint32_t consecutive_matches;

    ObjectHistory(uint32_t obj_id)
        : id(obj_id), last_seen_timestamp(GST_CLOCK_TIME_NONE), last_seen_frame(0), consecutive_matches(0) {
    }
};

struct _GstReID {
    GstBaseTransform parent;

    // Properties
    gdouble similarity_threshold;
    gdouble iou_threshold;
    guint max_history_size;
    guint max_objects;
    gchar *tensor_name;
    guint history_timeout_seconds;

    // Internal state
    GstVideoInfo *info;
    guint frame_count;
    guint next_object_id;

    // ReID tracking data
    std::unordered_map<uint32_t, std::shared_ptr<ObjectHistory>> *object_histories;
};

struct _GstReIDClass {
    GstBaseTransformClass parent_class;
};

GType gst_reid_get_type(void);

G_END_DECLS
