/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <dlstreamer/gst/videoanalytics/video_frame.h>

#include <vector>

G_BEGIN_DECLS

typedef struct _GstPostureDetect GstPostureDetect;
typedef struct _GstPostureDetectClass GstPostureDetectClass;

#define GST_TYPE_POSTURE_DETECT (gst_posture_detect_get_type())
#define GST_POSTURE_DETECT(obj) (G_TYPE_CHECK_INSTANCE_CAST((obj), GST_TYPE_POSTURE_DETECT, GstPostureDetect))
#define GST_POSTURE_DETECT_CLASS(klass)                                                                                \
    (G_TYPE_CHECK_CLASS_CAST((klass), GST_TYPE_POSTURE_DETECT, GstPostureDetectClass))
#define GST_IS_POSTURE_DETECT(obj) (G_TYPE_CHECK_INSTANCE_TYPE((obj), GST_TYPE_POSTURE_DETECT))
#define GST_IS_POSTURE_DETECT_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE((klass), GST_TYPE_POSTURE_DETECT))

struct _GstPostureDetect {
    GstBaseTransform parent;

    // Internal state
    guint frame_count;
    GstVideoInfo *info;
    
    // Inference interval tracking
    guint inference_interval;
};

struct _GstPostureDetectClass {
    GstBaseTransformClass parent_class;
};

GType gst_posture_detect_get_type(void);

G_END_DECLS
