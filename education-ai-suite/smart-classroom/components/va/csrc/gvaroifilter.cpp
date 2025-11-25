/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "gvaroifilter.h"
#include "extended_roi.h"

#include <vector>

GST_DEBUG_CATEGORY(gst_gvaroifilter_debug);
#define GST_CAT_DEFAULT gst_gvaroifilter_debug

// GType registration
G_DEFINE_TYPE(GstROIFilter, gst_roi_filter, GST_TYPE_BASE_TRANSFORM)

// Function declarations
static void gst_roi_filter_class_init(GstROIFilterClass *klass);
static void gst_roi_filter_init(GstROIFilter *self);
static void gst_roi_filter_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void gst_roi_filter_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void gst_roi_filter_finalize(GObject *object);
static gboolean gst_roi_filter_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps);
static GstFlowReturn gst_roi_filter_transform_ip(GstBaseTransform *trans, GstBuffer *buf);

// Helper functions
static void hide_roi(const GVA::RegionOfInterest &roi);
static void restore_all_hidden_rois(const GVA::VideoFrame &video_frame);
static gboolean should_keep_roi(GstROIFilter *self, const GVA::RegionOfInterest &roi);

// Property IDs
enum { PROP_0, PROP_FILTER_LABEL, PROP_CONFIDENCE_THRESHOLD, PROP_MAX_ROIS_NUM };

static void gst_roi_filter_class_init(GstROIFilterClass *klass) {
    GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
    GstElementClass *element_class = GST_ELEMENT_CLASS(klass);
    GstBaseTransformClass *base_transform_class = GST_BASE_TRANSFORM_CLASS(klass);

    gobject_class->set_property = gst_roi_filter_set_property;
    gobject_class->get_property = gst_roi_filter_get_property;
    gobject_class->finalize = gst_roi_filter_finalize;

    // Install properties
    g_object_class_install_property(
        gobject_class, PROP_FILTER_LABEL,
        g_param_spec_string("label", "Filter Label", "Comma-separated labels to filter (NULL means all labels)", NULL,
                            (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_CONFIDENCE_THRESHOLD,
                                    g_param_spec_double("confidence-threshold", "Confidence Threshold",
                                                        "Minimum confidence threshold", 0.0, 1.0, 0.0,
                                                        (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_MAX_ROIS_NUM,
                                    g_param_spec_uint("max-rois-num", "Maximum ROIs Number",
                                                      "Maximum number of ROIs to keep (0 means no limit)", 0, G_MAXUINT,
                                                      0, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    gst_element_class_set_static_metadata(element_class, "ROI Filter", "Filter/Analyzer/Video",
                                          "Filter regions of interest based on label, confidence, and count",
                                          "Intel Corporation");

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("src", GST_PAD_SRC, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("sink", GST_PAD_SINK, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    base_transform_class->set_caps = GST_DEBUG_FUNCPTR(gst_roi_filter_set_caps);
    base_transform_class->transform_ip = GST_DEBUG_FUNCPTR(gst_roi_filter_transform_ip);

    GST_DEBUG_CATEGORY_INIT(gst_gvaroifilter_debug, "gvaroifilter", 0, "ROI Filter");
}

static void gst_roi_filter_init(GstROIFilter *self) {
    self->filter_label = nullptr;
    self->confidence_threshold = 0.0;
    self->max_rois_num = 0;
    self->info = nullptr;
    self->frame_count = 0;
    self->filter_labels = new std::vector<std::string>();
}

static void gst_roi_filter_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    GstROIFilter *self = GST_ROI_FILTER(object);

    switch (prop_id) {
    case PROP_FILTER_LABEL:
        g_free(self->filter_label);
        self->filter_label = g_value_dup_string(value);

        // Parse comma-separated labels
        self->filter_labels->clear();
        if (self->filter_label) {
            std::string filter_labels_str(self->filter_label);
            size_t pos = 0;
            while (pos < filter_labels_str.length()) {
                size_t comma_pos = filter_labels_str.find(',', pos);
                size_t end_pos = (comma_pos == std::string::npos) ? filter_labels_str.length() : comma_pos;

                std::string label = filter_labels_str.substr(pos, end_pos - pos);
                // Trim whitespace
                size_t start = label.find_first_not_of(" \t");
                size_t end = label.find_last_not_of(" \t");
                if (start != std::string::npos && end != std::string::npos) {
                    self->filter_labels->push_back(label.substr(start, end - start + 1));
                }

                if (comma_pos == std::string::npos) {
                    break;
                }
                pos = comma_pos + 1;
            }
        }
        break;
    case PROP_CONFIDENCE_THRESHOLD:
        self->confidence_threshold = g_value_get_double(value);
        break;
    case PROP_MAX_ROIS_NUM:
        self->max_rois_num = g_value_get_uint(value);
        break;
    default:
        G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
        break;
    }
}

static void gst_roi_filter_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    GstROIFilter *self = GST_ROI_FILTER(object);

    switch (prop_id) {
    case PROP_FILTER_LABEL:
        g_value_set_string(value, self->filter_label);
        break;
    case PROP_CONFIDENCE_THRESHOLD:
        g_value_set_double(value, self->confidence_threshold);
        break;
    case PROP_MAX_ROIS_NUM:
        g_value_set_uint(value, self->max_rois_num);
        break;
    default:
        G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
        break;
    }
}

static void gst_roi_filter_finalize(GObject *object) {
    GstROIFilter *self = GST_ROI_FILTER(object);

    g_free(self->filter_label);

    if (self->info) {
        gst_video_info_free(self->info);
        self->info = nullptr;
    }

    if (self->filter_labels) {
        delete self->filter_labels;
        self->filter_labels = nullptr;
    }

    G_OBJECT_CLASS(gst_roi_filter_parent_class)->finalize(object);
}

static gboolean gst_roi_filter_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps) {
    GstROIFilter *self = GST_ROI_FILTER(trans);

    // Create or update video info from input caps
    if (!self->info) {
        self->info = gst_video_info_new();
    }

    if (!gst_video_info_from_caps(self->info, incaps)) {
        GST_ERROR_OBJECT(self, "Failed to parse video info from input caps");
        return FALSE;
    }

    return TRUE;
}

// ROI hiding: set bounding box to zero
static void hide_roi(const GVA::RegionOfInterest &roi) {
    // Check if bbox backup already exists in ROI parameters
    bool bbox_backup_exists = false;
    for (GList *l = roi.get_params(); l; l = g_list_next(l)) {
        GstStructure *structure = GST_STRUCTURE(l->data);
        const gchar *name = gst_structure_get_name(structure);
        if (g_strcmp0(name, "bbox_bk") == 0) {
            bbox_backup_exists = true;
            break;
        }
    }

    GstAnalyticsODMtdData *data = get_mtd_data_from_roi(roi);

    if (!bbox_backup_exists) {
        GstStructure *bbox_backup = gst_structure_new(
            "bbox_bk", "format", G_TYPE_STRING, "bbox_bk", "orig_x", G_TYPE_UINT, data->x, "orig_y", G_TYPE_UINT,
            data->y, "orig_w", G_TYPE_UINT, data->w, "orig_h", G_TYPE_UINT, data->h, "orig_r", G_TYPE_DOUBLE,
            static_cast<gdouble>(data->r), "orig_label", G_TYPE_UINT, data->object_type, NULL);
        g_list_append(roi.get_params(), bbox_backup);
        GST_DEBUG("Created bbox backup in ROI params: %u,%u,%u,%u\n", data->x, data->y, data->w, data->h);
    }

    data->x = 0;
    data->y = 0;
    data->w = 0;
    data->h = 0;
    data->r = 0;
    data->object_type = 0;

    GstVideoRegionOfInterestMeta *meta = roi._meta();
    if (meta) {
        meta->x = 0;
        meta->y = 0;
        meta->w = 0;
        meta->h = 0;
        meta->roi_type = 0;
    }
}

// ROI restoration: bounding box coordinates
static void restore_all_hidden_rois(const GVA::VideoFrame &video_frame) {
    auto regions = video_frame.regions();
    for (auto &roi : regions) {
        GstStructure *bbox_backup = nullptr;

        for (GList *l = roi.get_params(); l; l = g_list_next(l)) {
            GstStructure *structure = GST_STRUCTURE(l->data);
            const gchar *name = gst_structure_get_name(structure);
            if (g_strcmp0(name, "bbox_bk") == 0) {
                bbox_backup = structure;
                break;
            }
        }

        // Restore bounding box coordinates
        if (bbox_backup) {
            GstAnalyticsODMtdData *data = get_mtd_data_from_roi(roi);

            guint orig_x, orig_y, orig_w, orig_h, orig_label;
            gdouble orig_r;
            if (gst_structure_get_uint(bbox_backup, "orig_x", &orig_x) &&
                gst_structure_get_uint(bbox_backup, "orig_y", &orig_y) &&
                gst_structure_get_uint(bbox_backup, "orig_w", &orig_w) &&
                gst_structure_get_uint(bbox_backup, "orig_h", &orig_h) &&
                gst_structure_get_double(bbox_backup, "orig_r", &orig_r) &&
                gst_structure_get_uint(bbox_backup, "orig_label", &orig_label)) {

                data->x = orig_x;
                data->y = orig_y;
                data->w = orig_w;
                data->h = orig_h;
                data->r = static_cast<gfloat>(orig_r);
                data->object_type = orig_label;
                GST_DEBUG("Restored bbox from ROI params: %u,%u,%u,%u\n", data->x, data->y, data->w, data->h);

                GstVideoRegionOfInterestMeta *meta = roi._meta();
                if (meta) {
                    meta->x = orig_x;
                    meta->y = orig_y;
                    meta->w = orig_w;
                    meta->h = orig_h;
                    meta->roi_type = orig_label;
                }
            }
        }
    }
}

// Check if ROI should be kept based on label and confidence
static gboolean should_keep_roi(GstROIFilter *self, const GVA::RegionOfInterest &roi) {
    // Check confidence threshold
    if (roi.confidence() < self->confidence_threshold) {
        return FALSE;
    }

    // Check label filter
    if (self->filter_label && !self->filter_labels->empty()) {
        std::string roi_label = roi.label();

        // Check if roi_label matches any of the filter labels
        bool label_matched = false;
        for (const auto &filter_label : *self->filter_labels) {
            if (roi_label == filter_label) {
                label_matched = true;
                break;
            }
        }

        if (!label_matched) {
            return FALSE;
        }
    }

    return TRUE;
}

static GstFlowReturn gst_roi_filter_transform_ip(GstBaseTransform *trans, GstBuffer *buf) {
    GstROIFilter *self = GST_ROI_FILTER(trans);
    self->frame_count++;

    GVA::VideoFrame video_frame(buf, self->info);

    // Restore all hidden ROIs first
    restore_all_hidden_rois(video_frame);

    // Step 1: Filter by label and confidence
    for (const auto &roi : video_frame.regions()) {
        if (!should_keep_roi(self, roi)) {
            hide_roi(roi);
        }
    }

    // Step 2: Filter by count, keep highest confidence ones
    if (self->max_rois_num > 0) {
        std::vector<GVA::RegionOfInterest> current_regions;

        for (const auto &roi : video_frame.regions()) {
            auto rect = roi.rect();
            // Only include ROIs that are not hidden
            if (rect.x != 0 || rect.y != 0 || rect.w != 0 || rect.h != 0) {
                current_regions.push_back(roi);
            }
        }

        if (current_regions.size() > self->max_rois_num) {
            // Sort ROIs by confidence (highest first)
            std::sort(current_regions.begin(), current_regions.end(),
                      [](const GVA::RegionOfInterest &a, const GVA::RegionOfInterest &b) {
                          return a.confidence() > b.confidence();
                      });

            // Hide ROIs beyond the limit
            for (size_t i = self->max_rois_num; i < current_regions.size(); ++i) {
                hide_roi(current_regions[i]);
            }

            GST_DEBUG_OBJECT(self, "Count filtering: kept %u ROIs with highest confidence from %zu", self->max_rois_num,
                             current_regions.size());
        }
    }

    return GST_FLOW_OK;
}
