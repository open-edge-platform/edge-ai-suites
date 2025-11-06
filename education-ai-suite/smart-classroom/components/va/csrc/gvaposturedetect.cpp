/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "gvaposturedetect.h"
#include "extended_roi.h"

#include <cmath>
#include <fstream>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

GST_DEBUG_CATEGORY(gst_gvaposturedetect_debug);
#define GST_CAT_DEFAULT gst_gvaposturedetect_debug

// Function declarations
static void gst_posture_detect_class_init(GstPostureDetectClass *klass);
static void gst_posture_detect_init(GstPostureDetect *self);
static void gst_posture_detect_finalize(GObject *object);
static gboolean gst_posture_detect_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps);
static GstFlowReturn gst_posture_detect_transform_ip(GstBaseTransform *trans, GstBuffer *buf);

// Data structures
struct Keypoint {
    float x, y;
    float confidence;
};

struct Person {
    std::vector<Keypoint> keypoints;
    float confidence;
};

static void query_inference_interval(GstPostureDetect *self);
static std::string detect_posture(const Person &person);

// YOLO pose keypoint indices
enum YoloKeypoints {
    NOSE = 0,
    LEFT_EYE = 1,
    RIGHT_EYE = 2,
    LEFT_EAR = 3,
    RIGHT_EAR = 4,
    LEFT_SHOULDER = 5,
    RIGHT_SHOULDER = 6,
    LEFT_ELBOW = 7,
    RIGHT_ELBOW = 8,
    LEFT_WRIST = 9,
    RIGHT_WRIST = 10,
    LEFT_HIP = 11,
    RIGHT_HIP = 12,
    LEFT_KNEE = 13,
    RIGHT_KNEE = 14,
    LEFT_ANKLE = 15,
    RIGHT_ANKLE = 16
};

// Posture detection function
static std::string detect_posture(const Person &person) {
    const auto &kpts = person.keypoints;

    assert(kpts.size() == 17);

    // Helper function to calculate angle with vertical vector [0, 1]
    auto angle = [](float vx, float vy) -> float {
        float norm = std::sqrt(vx * vx + vy * vy);
        if (norm == 0) {
            return 0.0f;
        }
        // Dot product with [0, 1] is just vy
        float cos_angle = vy / norm;
        // Clamp to [-1, 1] to avoid numerical issues
        cos_angle = std::max(-1.0f, std::min(1.0f, cos_angle));
        return std::acos(cos_angle) * 180.0f / M_PI; // Convert to degrees
    };

    std::string posture = "sit"; // Default posture
    bool raise_up = false;

    try {
        // Get keypoints using YOLO indices
        auto left_hip = kpts[YoloKeypoints::LEFT_HIP];
        auto right_hip = kpts[YoloKeypoints::RIGHT_HIP];
        auto left_knee = kpts[YoloKeypoints::LEFT_KNEE];
        auto right_knee = kpts[YoloKeypoints::RIGHT_KNEE];
        auto left_shoulder = kpts[YoloKeypoints::LEFT_SHOULDER];
        auto right_shoulder = kpts[YoloKeypoints::RIGHT_SHOULDER];
        auto left_wrist = kpts[YoloKeypoints::LEFT_WRIST];
        auto right_wrist = kpts[YoloKeypoints::RIGHT_WRIST];

        // Check if both legs are visible (confidence > 0.5)
        if (left_hip.confidence > 0.5 && right_hip.confidence > 0.5 && left_knee.confidence > 0.5 &&
            right_knee.confidence > 0.5) {

            // Calculate vectors from hip to knee
            float left_vec_x = left_knee.x - left_hip.x;
            float left_vec_y = left_knee.y - left_hip.y;
            float right_vec_x = right_knee.x - right_hip.x;
            float right_vec_y = right_knee.y - right_hip.y;

            // Calculate angles with vertical
            float left_angle = angle(left_vec_x, left_vec_y);
            float right_angle = angle(right_vec_x, right_vec_y);

            if (left_angle < 30.0f && right_angle < 30.0f) {
                posture = "stand";
            }
        }
        // Check if only left leg is visible
        else if (left_hip.confidence > 0.5 && left_knee.confidence > 0.5) {
            float left_vec_x = left_knee.x - left_hip.x;
            float left_vec_y = left_knee.y - left_hip.y;
            float left_angle = angle(left_vec_x, left_vec_y);

            if (left_angle < 30.0f) {
                posture = "stand";
            }
        }
        // Check if only right leg is visible
        else if (right_hip.confidence > 0.5 && right_knee.confidence > 0.5) {
            float right_vec_x = right_knee.x - right_hip.x;
            float right_vec_y = right_knee.y - right_hip.y;
            float right_angle = angle(right_vec_x, right_vec_y);

            if (right_angle < 30.0f) {
                posture = "stand";
            }
        }
        // Check if only hips are visible (no legs) - assume sitting
        else if (left_hip.confidence > 0.5 && right_hip.confidence > 0.5) {
            posture = "sit";
        }

        // Check for raised hand detection
        // Hand is considered raised if wrist is above shoulder (smaller y value in image coordinates)
        if (left_wrist.confidence > 0.5 && left_shoulder.confidence > 0.5) {
            if (left_wrist.y < left_shoulder.y) {
                raise_up = true;
            }
        }
        if (right_wrist.confidence > 0.5 && right_shoulder.confidence > 0.5) {
            if (right_wrist.y < right_shoulder.y) {
                raise_up = true;
            }
        }
    } catch (const std::exception &e) {
        GST_WARNING("Error detecting posture: %s", e.what());
        posture = "sit";
    }

    // Append raising_hand if detected
    if (raise_up) {
        posture += "_raise_up";
    }

    return posture;
}

// GType registration
G_DEFINE_TYPE(GstPostureDetect, gst_posture_detect, GST_TYPE_BASE_TRANSFORM)

static void gst_posture_detect_class_init(GstPostureDetectClass *klass) {
    GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
    GstElementClass *element_class = GST_ELEMENT_CLASS(klass);
    GstBaseTransformClass *base_transform_class = GST_BASE_TRANSFORM_CLASS(klass);

    gobject_class->finalize = gst_posture_detect_finalize;

    gst_element_class_set_static_metadata(element_class, "Posture Detection", "Filter/Analyzer/Video",
                                          "Analyzes YOLO pose keypoints to determine sitting/standing postures",
                                          "Intel Corporation");

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("src", GST_PAD_SRC, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    gst_element_class_add_pad_template(
        element_class, gst_pad_template_new("sink", GST_PAD_SINK, GST_PAD_ALWAYS, gst_caps_from_string("ANY")));

    base_transform_class->set_caps = GST_DEBUG_FUNCPTR(gst_posture_detect_set_caps);
    base_transform_class->transform_ip = GST_DEBUG_FUNCPTR(gst_posture_detect_transform_ip);

    GST_DEBUG_CATEGORY_INIT(gst_gvaposturedetect_debug, "gvaposturedetect", 0, "Posture Detection");
}

static void gst_posture_detect_init(GstPostureDetect *self) {
    self->frame_count = 0;
    self->info = nullptr;
    self->inference_interval = 1; // Default to every frame
}

static void gst_posture_detect_finalize(GObject *object) {
    GstPostureDetect *self = GST_POSTURE_DETECT(object);

    if (self->info) {
        gst_video_info_free(self->info);
        self->info = nullptr;
    }

    G_OBJECT_CLASS(gst_posture_detect_parent_class)->finalize(object);
}

static gboolean gst_posture_detect_set_caps(GstBaseTransform *trans, GstCaps *incaps, GstCaps *outcaps) {
    GstPostureDetect *self = GST_POSTURE_DETECT(trans);

    // Create or update video info from input caps
    if (!self->info) {
        self->info = gst_video_info_new();
    }

    if (!gst_video_info_from_caps(self->info, incaps)) {
        GST_ERROR_OBJECT(self, "Failed to parse video info from input caps");
        return FALSE;
    }

    // Query inference interval from upstream elements
    query_inference_interval(self);

    return TRUE;
}

// Function to query inference interval from upstream gvadetect element
static void query_inference_interval(GstPostureDetect *self) {
    GstElement *element = GST_ELEMENT(self);
    GstPad *sinkpad = GST_BASE_TRANSFORM_SINK_PAD(self);
    GstPad *peer_pad = gst_pad_get_peer(sinkpad);

    self->inference_interval = 1; // Default

    if (peer_pad) {
        GstElement *peer_element = gst_pad_get_parent_element(peer_pad);

        // Walk upstream to find gvadetect element
        while (peer_element) {
            gchar *element_name = gst_element_get_name(peer_element);
            if (g_str_has_prefix(element_name, "gvadetect") || g_str_has_prefix(element_name, "gvainference")) {

                // Query inference-interval property
                GValue interval_value = G_VALUE_INIT;
                g_value_init(&interval_value, G_TYPE_UINT);

                g_object_get_property(G_OBJECT(peer_element), "inference-interval", &interval_value);
                self->inference_interval = g_value_get_uint(&interval_value);

                GST_DEBUG_OBJECT(self, "Found inference interval: %u from element %s", self->inference_interval,
                                 element_name);

                g_value_unset(&interval_value);
                g_free(element_name);
                gst_object_unref(peer_element);
                break;
            }

            g_free(element_name);

            // Continue upstream
            GstPad *next_sinkpad = gst_element_get_static_pad(peer_element, "sink");
            gst_object_unref(peer_element);

            if (next_sinkpad) {
                GstPad *next_peer = gst_pad_get_peer(next_sinkpad);
                gst_object_unref(next_sinkpad);

                if (next_peer) {
                    peer_element = gst_pad_get_parent_element(next_peer);
                    gst_object_unref(next_peer);
                } else {
                    break;
                }
            } else {
                break;
            }
        }

        gst_object_unref(peer_pad);
    }
}

static GstFlowReturn gst_posture_detect_transform_ip(GstBaseTransform *trans, GstBuffer *buf) {
    GstPostureDetect *self = GST_POSTURE_DETECT(trans);

    self->frame_count++;

    GVA::VideoFrame video_frame(buf, self->info);
    auto regions = video_frame.regions();

    // Check if this is an inference frame
    gboolean is_inference_frame = ((self->frame_count - 1) % self->inference_interval) == 0;

    // Perform posture detection and count postures
    int stand_count = 0;
    int sit_count = 0;
    int raise_up_count = 0;

    for (auto &roi : regions) {
        Person person;
        person.confidence = roi.confidence();

        // Extract keypoints from tensors attached to this ROI
        bool has_keypoints = false;
        for (GList *l = roi.get_params(); l; l = g_list_next(l)) {
            GstStructure *s = GST_STRUCTURE(l->data);
            GVA::Tensor tensor(s);
            if (!tensor.is_detection() && tensor.format() == "keypoints") {
                auto keypoints_data = tensor.data<float>();
                auto confidence = tensor.get_vector<float>("confidence");
                auto dims = tensor.dims();

                if (dims.size() >= 2) {
                    size_t points_num = dims[0];
                    size_t point_dimension = dims[1];
                    auto roi_rect = roi.rect();

                    person.keypoints.resize(points_num);
                    for (size_t i = 0; i < points_num; ++i) {
                        person.keypoints[i].x = keypoints_data[point_dimension * i];
                        person.keypoints[i].y = keypoints_data[point_dimension * i + 1];
                        person.keypoints[i].confidence = (confidence.size() > i) ? confidence[i] : 1.0f;

                        auto x = roi_rect.x + person.keypoints[i].x * roi_rect.w;
                        auto y = roi_rect.y + person.keypoints[i].y * roi_rect.h;
                        // Validate keypoint is within ROI bounds
                        float tolerance_x = roi_rect.w * 0.2f;
                        float tolerance_y = roi_rect.h * 0.2f;
                        if (x < roi_rect.x - tolerance_x || x > roi_rect.x + roi_rect.w + tolerance_x ||
                            y < roi_rect.y - tolerance_y || y > roi_rect.y + roi_rect.h + tolerance_y) {
                            // Keypoint is outside ROI bounds, reduce confidence
                            person.keypoints[i].confidence *= 0.1f;
                        }
                    }
                    has_keypoints = true;
                }
                break;
            }
        }

        // Detect posture and update ROI label
        std::string posture = "no_keypoints";
        if (has_keypoints) {
            posture = detect_posture(person);
            roi._meta()->roi_type = g_quark_from_string(posture.c_str());

            GstAnalyticsODMtdData *data = get_mtd_data_from_roi(roi);
            data->object_type = g_quark_from_string(posture.c_str());
        }

        // Update posture counts
        if (posture.starts_with("stand")) {
            stand_count++;
        } else if (posture.starts_with("sit")) {
            sit_count++;
        }
        if (posture.ends_with("raise_up")) {
            raise_up_count++;
        }
    }

    // Add a 0x0 watermark region at top-left corner for posture count display
    std::string count_text = "Sit: " + std::to_string(sit_count) + " | Stand: " + std::to_string(stand_count) +
                             " | Raise Up: " + std::to_string(raise_up_count);
    auto count_region = video_frame.add_region(0, 0, 0, 0, "", 0.0f);
    GstStructure *count_gst_structure = gst_structure_new_empty("count_text");
    GVA::Tensor count_tensor(count_gst_structure);
    count_tensor.set_string("label", count_text);
    count_region.add_tensor(count_tensor);

    return GST_FLOW_OK;
}
