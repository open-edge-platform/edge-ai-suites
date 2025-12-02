/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "gvareid.h"

#include <cmath>

GST_DEBUG_CATEGORY(gst_gvareid_debug);
#define GST_CAT_DEFAULT gst_gvareid_debug

// GType registration
G_DEFINE_TYPE(GstReID, gst_reid, GST_TYPE_BASE_TRANSFORM)

// Function declarations
static void gst_reid_class_init(GstReIDClass *klass);
static void gst_reid_init(GstReID *self);
static void gst_reid_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void gst_reid_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void gst_reid_finalize(GObject *object);
static gboolean gst_reid_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps);
static GstFlowReturn gst_reid_transform_ip(GstBaseTransform *trans, GstBuffer *buf);

// ReID utility functions
static bool extract_feature_vector(const GVA::Tensor &tensor, std::vector<float> &features);
static double calculate_cosine_similarity(const std::vector<float> &vec1, const std::vector<float> &vec2);
static double calculate_iou(const GVA::Rect<uint32_t> &box1, const GVA::Rect<uint32_t> &box2);
static uint32_t find_best_match(GstReID *self, const FeatureVector &current_feature, guint current_frame);
static uint32_t find_best_iou_match(GstReID *self, const GVA::Rect<uint32_t> &current_bbox, guint current_frame);
static void cleanup_old_histories(GstReID *self, GstClockTime current_pts);
static void update_object_history(GstReID *self, uint32_t object_id, const FeatureVector &feature, guint current_frame);

// Property IDs
enum {
    PROP_0,
    PROP_SIMILARITY_THRESHOLD,
    PROP_IOU_THRESHOLD,
    PROP_MAX_HISTORY_SIZE,
    PROP_MAX_OBJECTS,
    PROP_FEATURE_VECTOR_SIZE,
    PROP_TENSOR_NAME,
    PROP_HISTORY_TIMEOUT
};

static void gst_reid_class_init(GstReIDClass *klass) {
    GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
    GstElementClass *element_class = GST_ELEMENT_CLASS(klass);
    GstBaseTransformClass *base_transform_class = GST_BASE_TRANSFORM_CLASS(klass);

    gobject_class->set_property = gst_reid_set_property;
    gobject_class->get_property = gst_reid_get_property;
    gobject_class->finalize = gst_reid_finalize;

    // Install properties
    g_object_class_install_property(gobject_class, PROP_SIMILARITY_THRESHOLD,
                                    g_param_spec_double("similarity-threshold", "Similarity Threshold",
                                                        "Cosine similarity threshold for ReID matching (0.0-1.0)", 0.0,
                                                        1.0, 0.7,
                                                        (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_IOU_THRESHOLD,
                                    g_param_spec_double("iou-threshold", "IOU Threshold",
                                                        "IOU threshold for spatial matching fallback (0.0-1.0)", 0.0,
                                                        1.0, 0.3,
                                                        (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_MAX_HISTORY_SIZE,
                                    g_param_spec_uint("max-history-size", "Maximum History Size",
                                                      "Maximum number of feature vectors to keep per object", 1, 100,
                                                      10, (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_MAX_OBJECTS,
                                    g_param_spec_uint("max-objects", "Maximum Objects",
                                                      "Maximum number of objects to track simultaneously", 1, 1000, 100,
                                                      (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_TENSOR_NAME,
                                    g_param_spec_string("tensor-name", "Tensor Name",
                                                        "Name of tensor containing ReID features", "reid_embedding",
                                                        (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    g_object_class_install_property(gobject_class, PROP_HISTORY_TIMEOUT,
                                    g_param_spec_uint("history-timeout", "History Timeout",
                                                      "Time in seconds after which object history is cleaned up", 1,
                                                      86400, 3600,
                                                      (GParamFlags)(G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS)));

    gst_element_class_set_static_metadata(element_class, "ReID Tracker", "Filter/Analyzer/Video",
                                          "Person Re-Identification tracker using feature vectors",
                                          "Intel Corporation");

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("src", GST_PAD_SRC, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("sink", GST_PAD_SINK, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    base_transform_class->set_caps = GST_DEBUG_FUNCPTR(gst_reid_set_caps);
    base_transform_class->transform_ip = GST_DEBUG_FUNCPTR(gst_reid_transform_ip);

    GST_DEBUG_CATEGORY_INIT(gst_gvareid_debug, "gvareid", 0, "ReID Tracker");
}

static void gst_reid_init(GstReID *self) {
    self->similarity_threshold = 0.7;
    self->iou_threshold = 0.3;
    self->max_history_size = 10;
    self->max_objects = 100;
    self->tensor_name = g_strdup("reid_embedding");
    self->history_timeout_seconds = 3600;

    self->info = nullptr;
    self->frame_count = 0;
    self->next_object_id = 1;

    self->object_histories = new std::unordered_map<uint32_t, std::shared_ptr<ObjectHistory>>();
}

static void gst_reid_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    GstReID *self = GST_REID(object);

    switch (prop_id) {
    case PROP_SIMILARITY_THRESHOLD:
        self->similarity_threshold = g_value_get_double(value);
        break;
    case PROP_IOU_THRESHOLD:
        self->iou_threshold = g_value_get_double(value);
        break;
    case PROP_MAX_HISTORY_SIZE:
        self->max_history_size = g_value_get_uint(value);
        break;
    case PROP_MAX_OBJECTS:
        self->max_objects = g_value_get_uint(value);
        break;
    case PROP_TENSOR_NAME:
        g_free(self->tensor_name);
        self->tensor_name = g_value_dup_string(value);
        break;
    case PROP_HISTORY_TIMEOUT:
        self->history_timeout_seconds = g_value_get_uint(value);
        break;
    default:
        G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
        break;
    }
}

static void gst_reid_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    GstReID *self = GST_REID(object);

    switch (prop_id) {
    case PROP_SIMILARITY_THRESHOLD:
        g_value_set_double(value, self->similarity_threshold);
        break;
    case PROP_IOU_THRESHOLD:
        g_value_set_double(value, self->iou_threshold);
        break;        
    case PROP_MAX_HISTORY_SIZE:
        g_value_set_uint(value, self->max_history_size);
        break;
    case PROP_MAX_OBJECTS:
        g_value_set_uint(value, self->max_objects);
        break;
    case PROP_TENSOR_NAME:
        g_value_set_string(value, self->tensor_name);
        break;
    case PROP_HISTORY_TIMEOUT:
        g_value_set_uint(value, self->history_timeout_seconds);
        break;
    default:
        G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
        break;
    }
}

static void gst_reid_finalize(GObject *object) {
    GstReID *self = GST_REID(object);

    g_free(self->tensor_name);

    if (self->info) {
        gst_video_info_free(self->info);
        self->info = nullptr;
    }

    delete self->object_histories;

    G_OBJECT_CLASS(gst_reid_parent_class)->finalize(object);
}

static gboolean gst_reid_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps) {
    GstReID *self = GST_REID(trans);

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

// Extract feature vector from tensor data
static bool extract_feature_vector(const GVA::Tensor &tensor, std::vector<float> &features) {
    features.clear();

    try {
        auto tensor_data = tensor.data<float>();
        features = tensor_data;

        // Normalize the feature vector
        float norm = 0.0f;
        for (float val : features) {
            norm += val * val;
        }
        norm = std::sqrt(norm);

        if (norm > 0.0f) {
            for (float &val : features) {
                val /= norm;
            }
        }

        return true;

    } catch (const std::exception &e) {
        GST_ERROR("Error extracting feature vector: %s", e.what());
        features.clear();
        return false;
    }
}

// Calculate cosine similarity between two feature vectors
static double calculate_cosine_similarity(const std::vector<float> &vec1, const std::vector<float> &vec2) {
    if (vec1.size() != vec2.size() || vec1.empty()) {
        return 0.0;
    }

    double dot_product = 0.0;
    for (size_t i = 0; i < vec1.size(); ++i) {
        dot_product += vec1[i] * vec2[i];
    }

    return dot_product;
}

// Calculate Intersection over Union (IOU) between two bounding boxes
static double calculate_iou(const GVA::Rect<uint32_t> &box1, const GVA::Rect<uint32_t> &box2) {
    double x1 = std::max(box1.x, box2.x);
    double y1 = std::max(box1.y, box2.y);
    double x2 = std::min(box1.x + box1.w, box2.x + box2.w);
    double y2 = std::min(box1.y + box1.h, box2.y + box2.h);

    if (x2 <= x1 || y2 <= y1) {
        return 0.0;
    }

    double intersection_area = (x2 - x1) * (y2 - y1);

    double box1_area = box1.w * box1.h;
    double box2_area = box2.w * box2.h;
    double union_area = box1_area + box2_area - intersection_area;

    if (union_area <= 0.0) {
        return 0.0;
    }

    return intersection_area / union_area;
}

// Find the best matching object ID for a given feature vector
static uint32_t find_best_match(GstReID *self, const FeatureVector &current_feature, guint current_frame) {
    double best_similarity = 0.0;
    uint32_t best_match_id = 0;

    for (const auto &pair : *self->object_histories) {
        const auto &history = pair.second;

        // Skip if this ID was already assigned in the current frame
        if (history->last_seen_frame >= current_frame) {
            continue;
        }

        // Calculate average similarity with recent feature vectors
        double avg_similarity = 0.0;
        int count = 0;

        // Use the most recent features for matching (up to 3)
        size_t start_idx = history->feature_history.size() > 3 ? history->feature_history.size() - 3 : 0;

        for (size_t i = start_idx; i < history->feature_history.size(); ++i) {
            double similarity =
                calculate_cosine_similarity(current_feature.features, history->feature_history[i].features);
            avg_similarity += similarity;
            count++;
        }

        if (count > 0) {
            avg_similarity /= count;

            if (avg_similarity > best_similarity) {
                best_similarity = avg_similarity;
                best_match_id = history->id;
            }
        }
    }

    // Return match only if above threshold
    if (best_similarity >= self->similarity_threshold) {
        GST_DEBUG_OBJECT(self, "Found match: ID %u with similarity %.3f", best_match_id, best_similarity);
        return best_match_id;
    }

    GST_DEBUG_OBJECT(self, "No match found, best similarity %.3f", best_similarity);
    return 0; // No match found
}

// Find the best matching object ID based on IOU
static uint32_t find_best_iou_match(GstReID *self, const GVA::Rect<uint32_t> &current_bbox, guint current_frame) {
    double best_iou = 0.0;
    uint32_t best_match_id = 0;

    for (const auto &pair : *self->object_histories) {
        const auto &history = pair.second;

        // Skip if this ID was already assigned in the current frame
        if (history->last_seen_frame >= current_frame) {
            continue;
        }

        if (history->feature_history.empty()) {
            continue;
        }

        // Use the most recent bounding box for IOU matching
        const GVA::Rect<uint32_t> &last_bbox = history->feature_history.back().bbox;

        double iou = calculate_iou(current_bbox, last_bbox);
        if (iou > best_iou) {
            best_iou = iou;
            best_match_id = history->id;
        }
    }

    // Return match only if above threshold
    if (best_iou >= self->iou_threshold) {
        GST_DEBUG_OBJECT(self, "Found IOU match: ID %u with IOU %.3f", best_match_id, best_iou);
        return best_match_id;
    }

    GST_DEBUG_OBJECT(self, "No IOU match found, best IOU %.3f", best_iou);
    return 0; // No match found
}

// Clean up old object histories based on timeout
static void cleanup_old_histories(GstReID *self, GstClockTime current_pts) {
    if (!GST_CLOCK_TIME_IS_VALID(current_pts)) {
        return;
    }

    GstClockTime timeout_duration = self->history_timeout_seconds * GST_SECOND;

    auto it = self->object_histories->begin();
    while (it != self->object_histories->end()) {
        if (GST_CLOCK_TIME_IS_VALID(it->second->last_seen_timestamp) &&
            current_pts - it->second->last_seen_timestamp > timeout_duration) {
            GST_DEBUG_OBJECT(self, "Removing expired object ID %u", it->first);
            it = self->object_histories->erase(it);
        } else {
            ++it;
        }
    }
}

// Update object history with new feature vector
static void update_object_history(GstReID *self, uint32_t object_id, const FeatureVector &feature,
                                  guint current_frame) {
    auto it = self->object_histories->find(object_id);

    if (it == self->object_histories->end()) {
        // Create new history for this object
        auto new_history = std::make_shared<ObjectHistory>(object_id);
        new_history->feature_history.push_back(feature);
        new_history->last_seen_timestamp = feature.timestamp;
        new_history->last_seen_frame = current_frame;
        (*self->object_histories)[object_id] = new_history;

        GST_DEBUG_OBJECT(self, "Created new history for object ID %u", object_id);
    } else {
        // Update existing history
        auto &history = it->second;
        history->last_seen_timestamp = feature.timestamp;
        history->last_seen_frame = current_frame;
        history->consecutive_matches++;

        // Add new feature vector
        history->feature_history.push_back(feature);

        // Limit history size
        if (history->feature_history.size() > self->max_history_size) {
            history->feature_history.erase(history->feature_history.begin());
        }

        GST_DEBUG_OBJECT(self, "Updated history for object ID %u (matches: %u, history size: %zu)", object_id,
                         history->consecutive_matches, history->feature_history.size());
    }
}

static GstFlowReturn gst_reid_transform_ip(GstBaseTransform *trans, GstBuffer *buf) {
    GstReID *self = GST_REID(trans);
    self->frame_count++;

    GstClockTime buffer_pts = GST_BUFFER_PTS(buf);

    GVA::VideoFrame video_frame(buf, self->info);
    auto regions = video_frame.regions();

    GST_DEBUG_OBJECT(self, "Processing frame %u with %zu ROIs (PTS: %" GST_TIME_FORMAT ")", self->frame_count,
                     regions.size(), GST_TIME_ARGS(buffer_pts));

    // Clean up old histories periodically
    if (self->frame_count % 3000 == 0) { // Every 100 seconds at 30fps
        cleanup_old_histories(self, buffer_pts);
    }

    for (auto &roi : regions) {
        bool found_reid_tensor = false;
        FeatureVector current_feature;

        for (GList *l = roi.get_params(); l; l = g_list_next(l)) {
            GstStructure *s = GST_STRUCTURE(l->data);
            GVA::Tensor tensor(s);
            std::string tensor_layer_name = tensor.layer_name();

            // Check if this tensor contains ReID features
            if (tensor_layer_name.find("reid_embedding") != std::string::npos ||
                (self->tensor_name && tensor.name() == std::string(self->tensor_name))) {
                std::vector<float> features;
                if (extract_feature_vector(tensor, features)) {
                    current_feature = FeatureVector(features, buffer_pts);
                    current_feature.bbox = roi.rect();
                    found_reid_tensor = true;

                    GST_DEBUG_OBJECT(self, "Extracted %zu-dimensional feature vector from tensor '%s'", features.size(),
                                     tensor.name().c_str());
                    break;
                }
            }
        }

        if (!found_reid_tensor) {
            continue;
        }

        // Try to find matching object using ReID embedding
        uint32_t matched_id = find_best_match(self, current_feature, self->frame_count);

        // If ReID matching failed, try IOU-based spatial matching
        if (matched_id == 0) {
            matched_id = find_best_iou_match(self, roi.rect(), self->frame_count);
        }

        uint32_t assigned_id;
        if (matched_id > 0) {
            assigned_id = matched_id;
        } else {
            assigned_id = self->next_object_id++;

            // Limit number of tracked objects
            if (self->object_histories->size() >= self->max_objects) {
                // Remove oldest object
                auto oldest_it = std::min_element(
                    self->object_histories->begin(), self->object_histories->end(), [](const auto &a, const auto &b) {
                        return a.second->last_seen_timestamp < b.second->last_seen_timestamp;
                    });

                if (oldest_it != self->object_histories->end()) {
                    GST_DEBUG_OBJECT(self, "Removing oldest object ID %u to make space", oldest_it->first);
                    self->object_histories->erase(oldest_it);
                }
            }

            GST_DEBUG_OBJECT(self, "Assigned new ID %u to object", assigned_id);
        }

        // Set the object ID
        roi.set_object_id(assigned_id);

        // Update feature vector with assigned ID
        current_feature.object_id = assigned_id;

        // Update object history
        update_object_history(self, assigned_id, current_feature, self->frame_count);
    }

    GST_DEBUG_OBJECT(self, "Completed ReID processing for frame %u: %zu active histories", self->frame_count,
                     self->object_histories->size());

    return GST_FLOW_OK;
}
