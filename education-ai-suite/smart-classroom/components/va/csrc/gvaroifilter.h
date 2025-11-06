/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <dlstreamer/gst/videoanalytics/video_frame.h>

#include <vector>

G_BEGIN_DECLS

typedef struct _GstROIFilter GstROIFilter;
typedef struct _GstROIFilterClass GstROIFilterClass;

#define GST_TYPE_ROI_FILTER (gst_roi_filter_get_type())
#define GST_ROI_FILTER(obj) (G_TYPE_CHECK_INSTANCE_CAST((obj), GST_TYPE_ROI_FILTER, GstROIFilter))
#define GST_ROI_FILTER_CLASS(klass) (G_TYPE_CHECK_CLASS_CAST((klass), GST_TYPE_ROI_FILTER, GstROIFilterClass))
#define GST_IS_ROI_FILTER(obj) (G_TYPE_CHECK_INSTANCE_TYPE((obj), GST_TYPE_ROI_FILTER))
#define GST_IS_ROI_FILTER_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE((klass), GST_TYPE_ROI_FILTER))

struct _GstROIFilter {
    GstBaseTransform parent;

    // Properties
    gchar *filter_label;          // Label to filter (NULL means all labels)
    gdouble confidence_threshold; // Minimum confidence threshold
    guint max_rois_num;           // Maximum number of ROIs to keep

    // Internal state
    GstVideoInfo *info;
    guint frame_count;
    std::vector<std::string> *filter_labels;
};

struct _GstROIFilterClass {
    GstBaseTransformClass parent_class;
};

GType gst_roi_filter_get_type(void);

G_END_DECLS
