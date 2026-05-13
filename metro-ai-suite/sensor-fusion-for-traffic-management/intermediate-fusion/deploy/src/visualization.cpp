#include "visualization.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>


using CornerArray = std::array<cv::Point3f, 8>;
constexpr float kHalfPi = 1.5707963267948966f;

const std::map<std::string, cv::Scalar> kPalette = {
    // High-contrast BGR colors for readability.
    {"car", cv::Scalar(0, 255, 0)},                    // bright green
    {"truck", cv::Scalar(0, 165, 255)},                // orange
    {"construction_vehicle", cv::Scalar(0, 255, 255)},  // yellow
    {"bus", cv::Scalar(255, 255, 0)},                  // cyan
    {"trailer", cv::Scalar(255, 0, 255)},              // magenta
    {"barrier", cv::Scalar(255, 0, 0)},                // blue
    {"motorcycle", cv::Scalar(180, 0, 180)},           // purple
    {"bicycle", cv::Scalar(0, 0, 255)},                // red
    {"pedestrian", cv::Scalar(255, 255, 255)},         // white
    {"traffic_cone", cv::Scalar(0, 128, 255)},         // amber
};

inline std::string labelName(int label, const std::vector<std::string> &class_names)
{
    if (label >= 0 && label < static_cast<int>(class_names.size())) {
        return class_names[static_cast<size_t>(label)];
    }
    std::ostringstream os;
    os << "id=" << label;
    return os.str();
}

inline std::string boxLabelText(const BBox3D &box, const std::vector<std::string> &class_names)
{
    std::ostringstream os;
    os << labelName(box.label, class_names);
    if (std::isfinite(box.score) && box.score > 0.0f) {
        os << ' ' << std::fixed << std::setprecision(2) << box.score;
    }
    return os.str();
}

inline void drawLabelBox(cv::Mat &img, const cv::Rect &bbox, const std::string &text, const cv::Scalar &color)
{
    if (img.empty() || text.empty()) return;

    // Font scale adapts to bbox height.
    const int h = std::max(1, bbox.height);
    double font_scale = 0.4 + std::min(0.6, static_cast<double>(h) / 300.0);
    font_scale = std::max(0.4, std::min(1.0, font_scale));

    const int font_face = cv::FONT_HERSHEY_SIMPLEX;
    const int thickness = 1;
    int baseline = 0;
    const cv::Size text_size = cv::getTextSize(text, font_face, font_scale, thickness, &baseline);
    const int pad = 3;

    // Prefer top-left of bbox; if not enough space, place below.
    int x = bbox.x;
    int y = bbox.y - (text_size.height + baseline + 2 * pad);
    if (y < 0) {
        y = bbox.y + 1;  // below top edge
    }

    // Clamp x to fit inside image.
    x = std::max(0, std::min(x, img.cols - (text_size.width + 2 * pad)));
    y = std::max(0, std::min(y, img.rows - (text_size.height + baseline + 2 * pad)));

    const cv::Rect bg(x, y, std::min(img.cols - x, text_size.width + 2 * pad),
                      std::min(img.rows - y, text_size.height + baseline + 2 * pad));

    // Solid background for readability.
    cv::rectangle(img, bg, cv::Scalar(0, 0, 0), cv::FILLED);
    // Border in class color.
    cv::rectangle(img, bg, color, 1);

    const cv::Point org(x + pad, y + pad + text_size.height);
    cv::putText(img, text, org, font_face, font_scale, color, thickness, cv::LINE_AA);
}

inline cv::Scalar colorForLabel(int label, const std::vector<std::string> &class_names, const cv::Scalar &fallback)
{
    if (label >= 0 && label < static_cast<int>(class_names.size())) {
        auto it = kPalette.find(class_names[static_cast<size_t>(label)]);
        if (it != kPalette.end()) {
            return it->second;
        }
    }
    return fallback;
}

inline float clamp01(float value)
{
    return std::max(0.0f, std::min(1.0f, value));
}

inline cv::Scalar lerpColor(const cv::Scalar &from, const cv::Scalar &to, float t)
{
    const float alpha = clamp01(t);
    return cv::Scalar(from[0] + (to[0] - from[0]) * alpha,
                      from[1] + (to[1] - from[1]) * alpha,
                      from[2] + (to[2] - from[2]) * alpha);
}

inline cv::Scalar colorForDistance(float distance, float max_distance)
{
    const float normalized = clamp01(max_distance > 1e-3f ? distance / max_distance : 0.0f);

    if (normalized < 0.33f) {
        return lerpColor(cv::Scalar(0, 48, 255), cv::Scalar(0, 220, 255), normalized / 0.33f);
    }
    if (normalized < 0.66f) {
        return lerpColor(cv::Scalar(0, 220, 255), cv::Scalar(0, 255, 120), (normalized - 0.33f) / 0.33f);
    }
    return lerpColor(cv::Scalar(0, 255, 120), cv::Scalar(255, 200, 0), (normalized - 0.66f) / 0.34f);
}

inline cv::Scalar backgroundPointColor(float distance, float max_distance)
{
    return lerpColor(cv::Scalar(42, 42, 48), colorForDistance(distance, max_distance), 0.22f);
}

CornerArray computeBoxCorners(const BBox3D &box)
{
    // Match LiDARInstance3DBoxes: bottom-centered origin, yaw defined in LiDAR frame (0 points to -y).
    const float dx = box.l;  // forward (x) length
    const float dy = box.w;  // lateral (y) width
    const float dz = box.h;
    const float angle = box.yaw - kHalfPi;
    const float c = std::cos(angle);
    const float s = std::sin(angle);

    const std::array<cv::Point3f, 8> local = {cv::Point3f(0.f, 0.f, 0.f), cv::Point3f(dx, 0.f, 0.f), cv::Point3f(dx, dy, 0.f), cv::Point3f(0.f, dy, 0.f),
                                              cv::Point3f(0.f, 0.f, dz),  cv::Point3f(dx, 0.f, dz),  cv::Point3f(dx, dy, dz),  cv::Point3f(0.f, dy, dz)};

    const cv::Point3f offset(box.x, box.y, box.z);
    CornerArray corners{};
    for (size_t i = 0; i < local.size(); ++i) {
        cv::Point3f p = local[i];
        p.x -= dx * 0.5f;
        p.y -= dy * 0.5f;
        const float rx = c * p.x - s * p.y;
        const float ry = s * p.x + c * p.y;
        corners[i] = cv::Point3f(offset.x + rx, offset.y + ry, offset.z + p.z);
    }
    return corners;
}

const Transform4x4 *findLidarToCamera(const CalibField_t &calib)
{
    auto it = calib.transforms.find("lidar_to_camera");
    if (it != calib.transforms.end()) {
        return &it->second;
    }
    it = calib.transforms.find("Tr_velo_to_cam");
    if (it != calib.transforms.end()) {
        return &it->second;
    }
    return nullptr;
}

const CameraParams *findCameraParams(const CalibField_t &calib, int camera_index)
{
    std::string key = "P" + std::to_string(camera_index);
    auto it = calib.cameraParams.find(key);
    if (it != calib.cameraParams.end()) {
        return &it->second;
    }
    // fallback to the first available
    if (!calib.cameraParams.empty()) {
        return &calib.cameraParams.begin()->second;
    }
    return nullptr;
}

cv::Matx44f toMatx(const Transform4x4 &t)
{
    return cv::Matx44f(t.data[0], t.data[1], t.data[2], t.data[3], t.data[4], t.data[5], t.data[6], t.data[7], t.data[8], t.data[9], t.data[10], t.data[11],
                       t.data[12], t.data[13], t.data[14], t.data[15]);
}

cv::Matx34f toMatx(const CameraParams &k)
{
    return cv::Matx34f(k.intrinsics[0], k.intrinsics[1], k.intrinsics[2], k.intrinsics[3], k.intrinsics[4], k.intrinsics[5], k.intrinsics[6], k.intrinsics[7],
                       k.intrinsics[8], k.intrinsics[9], k.intrinsics[10], k.intrinsics[11]);
}

bool projectPoint(const cv::Point3f &p, const cv::Matx44f &T, const cv::Matx34f &K, cv::Point2f &pix, float &depth)
{
    const cv::Vec4f pw(p.x, p.y, p.z, 1.0f);
    const cv::Vec4f pc = T * pw;
    depth = pc[2];
    if (depth <= 1e-4f) {
        return false;
    }
    const cv::Vec3f uvw = K * pc;
    if (std::fabs(uvw[2]) < 1e-4f) {
        return false;
    }
    pix.x = uvw[0] / uvw[2];
    pix.y = uvw[1] / uvw[2];
    return true;
}

cv::Mat makeBlack(const cv::Size &size)
{
    return cv::Mat(size, CV_8UC3, cv::Scalar(0, 0, 0));
}

void drawBoxEdges(cv::Mat &canvas, const std::array<cv::Point2f, 8> &pts, const cv::Scalar &color, int thickness)
{
    static const int edges[12][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 0}, {4, 5}, {5, 6}, {6, 7}, {7, 4}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};
    for (const auto &e : edges) {
        cv::line(canvas, pts[static_cast<size_t>(e[0])], pts[static_cast<size_t>(e[1])], color, thickness, cv::LINE_AA);
    }
}

void drawBoxEdgesClipped(cv::Mat &canvas, const std::array<cv::Point2f, 8> &pts, const cv::Scalar &color, int thickness)
{
    static const int edges[12][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 0}, {4, 5}, {5, 6}, {6, 7}, {7, 4}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};
    const cv::Rect clip_rect(0, 0, canvas.cols, canvas.rows);
    for (const auto &e : edges) {
        cv::Point p0(static_cast<int>(std::lround(pts[static_cast<size_t>(e[0])].x)),
                     static_cast<int>(std::lround(pts[static_cast<size_t>(e[0])].y)));
        cv::Point p1(static_cast<int>(std::lround(pts[static_cast<size_t>(e[1])].x)),
                     static_cast<int>(std::lround(pts[static_cast<size_t>(e[1])].y)));
        if (cv::clipLine(clip_rect, p0, p1)) {
            cv::line(canvas, p0, p1, color, thickness, cv::LINE_AA);
        }
    }
}

bool pointInsideImage(const cv::Point2f &p, const cv::Size &size)
{
    return p.x >= 0.0f && p.x < static_cast<float>(size.width) && p.y >= 0.0f && p.y < static_cast<float>(size.height);
}

bool computeVisibleProjectedBBox(const std::array<cv::Point2f, 8> &pts, const cv::Size &size, cv::Rect &bbox)
{
    if (size.width <= 0 || size.height <= 0) {
        return false;
    }

    static const int edges[12][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 0}, {4, 5}, {5, 6}, {6, 7}, {7, 4}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};
    const cv::Rect clip_rect(0, 0, size.width, size.height);

    std::vector<cv::Point2f> visible_pts;
    visible_pts.reserve(32);

    for (const auto &p : pts) {
        if (pointInsideImage(p, size)) {
            visible_pts.push_back(p);
        }
    }

    for (const auto &e : edges) {
        cv::Point p0(static_cast<int>(std::lround(pts[static_cast<size_t>(e[0])].x)),
                     static_cast<int>(std::lround(pts[static_cast<size_t>(e[0])].y)));
        cv::Point p1(static_cast<int>(std::lround(pts[static_cast<size_t>(e[1])].x)),
                     static_cast<int>(std::lround(pts[static_cast<size_t>(e[1])].y)));
        if (cv::clipLine(clip_rect, p0, p1)) {
            visible_pts.emplace_back(static_cast<float>(p0.x), static_cast<float>(p0.y));
            visible_pts.emplace_back(static_cast<float>(p1.x), static_cast<float>(p1.y));
        }
    }

    if (visible_pts.empty()) {
        return false;
    }

    float minx = std::numeric_limits<float>::max();
    float miny = std::numeric_limits<float>::max();
    float maxx = -std::numeric_limits<float>::max();
    float maxy = -std::numeric_limits<float>::max();
    for (const auto &p : visible_pts) {
        minx = std::min(minx, p.x);
        miny = std::min(miny, p.y);
        maxx = std::max(maxx, p.x);
        maxy = std::max(maxy, p.y);
    }

    const int x0 = std::max(0, static_cast<int>(std::floor(minx)));
    const int y0 = std::max(0, static_cast<int>(std::floor(miny)));
    const int x1 = std::min(size.width - 1, static_cast<int>(std::ceil(maxx)));
    const int y1 = std::min(size.height - 1, static_cast<int>(std::ceil(maxy)));
    if (x1 < x0 || y1 < y0) {
        return false;
    }

    bbox = cv::Rect(x0, y0, std::max(1, x1 - x0 + 1), std::max(1, y1 - y0 + 1));
    return true;
}

template <size_t N>
bool computeLabelBBoxFromVisiblePoints(const std::array<cv::Point2f, N> &pts, const cv::Size &size, cv::Rect &bbox)
{
    if (size.width <= 0 || size.height <= 0) {
        return false;
    }

    float minx = std::numeric_limits<float>::max();
    float miny = std::numeric_limits<float>::max();
    float maxx = -std::numeric_limits<float>::max();
    float maxy = -std::numeric_limits<float>::max();
    bool has_visible_corner = false;

    for (const auto &p : pts) {
        if (!pointInsideImage(p, size)) {
            continue;
        }
        has_visible_corner = true;
        minx = std::min(minx, p.x);
        miny = std::min(miny, p.y);
        maxx = std::max(maxx, p.x);
        maxy = std::max(maxy, p.y);
    }

    if (!has_visible_corner) {
        return false;
    }

    constexpr int kPad = 2;
    const int x0 = std::max(0, static_cast<int>(std::floor(minx)) - kPad);
    const int y0 = std::max(0, static_cast<int>(std::floor(miny)) - kPad);
    const int x1 = std::min(size.width - 1, static_cast<int>(std::ceil(maxx)) + kPad);
    const int y1 = std::min(size.height - 1, static_cast<int>(std::ceil(maxy)) + kPad);
    if (x1 < x0 || y1 < y0) {
        return false;
    }

    bbox = cv::Rect(x0, y0, std::max(1, x1 - x0 + 1), std::max(1, y1 - y0 + 1));
    return true;
}

struct LidarBoxFootprint
{
    const BBox3D *box = nullptr;
    std::array<cv::Point2f, 4> pixel_poly{};
    cv::Scalar color{0, 255, 0};
};

cv::Point2f toPixel(const cv::Point2f &p, const LidarVizOptions &opts, const cv::Size &size)
{
    const float lateral = (opts.ylim.second - p.y) / (opts.ylim.second - opts.ylim.first);
    const float forward = (p.x - opts.xlim.first) / (opts.xlim.second - opts.xlim.first);
    const float px = lateral * static_cast<float>(size.width - 1);
    const float py = static_cast<float>(size.height - 1) - forward * static_cast<float>(size.height - 1);
    return cv::Point2f(px, py);
}

bool insideRange(const cv::Point3f &p, const LidarVizOptions &opts)
{
    return p.x >= opts.xlim.first && p.x <= opts.xlim.second && p.y >= opts.ylim.first && p.y <= opts.ylim.second;
}

LidarBoxFootprint makeLidarBoxFootprint(const BBox3D &box,
                                        const std::vector<std::string> &class_names,
                                        const LidarVizOptions &opts,
                                        const cv::Size &canvas_size)
{
    LidarBoxFootprint footprint;
    footprint.box = &box;
    footprint.color = colorForLabel(box.label, class_names, cv::Scalar(0, 255, 0));

    const CornerArray corners = computeBoxCorners(box);
    footprint.pixel_poly = {cv::Point2f(corners[0].x, corners[0].y), cv::Point2f(corners[1].x, corners[1].y),
                            cv::Point2f(corners[2].x, corners[2].y), cv::Point2f(corners[3].x, corners[3].y)};
    for (auto &pt : footprint.pixel_poly) {
        pt = toPixel(pt, opts, canvas_size);
    }

    return footprint;
}

void drawEgoMarker(cv::Mat &canvas, const LidarVizOptions &opts)
{
    if (canvas.empty()) return;

    const cv::Point2f ego = toPixel(cv::Point2f(0.0f, 0.0f), opts, canvas.size());
    const int cx = static_cast<int>(std::round(ego.x));
    const int cy = static_cast<int>(std::round(ego.y));
    if (cx < 0 || cy < 0 || cx >= canvas.cols || cy >= canvas.rows) {
        return;
    }

    const int marker_size = std::max(8, std::min(canvas.cols, canvas.rows) / 40);
    const int cross_half = std::max(4, marker_size / 3);
    const int tri_h = marker_size;
    const int tri_w_half = std::max(4, marker_size / 2);

    const cv::Scalar marker_color(0, 255, 255);
    const cv::Scalar border_color(0, 0, 0);

    cv::line(canvas, cv::Point(cx - cross_half, cy), cv::Point(cx + cross_half, cy), marker_color, 2, cv::LINE_AA);
    cv::line(canvas, cv::Point(cx, cy - cross_half), cv::Point(cx, cy + cross_half), marker_color, 2, cv::LINE_AA);

    std::array<cv::Point, 3> tri = {
        cv::Point(cx, cy - tri_h),
        cv::Point(cx - tri_w_half, cy),
        cv::Point(cx + tri_w_half, cy)
    };
    cv::fillConvexPoly(canvas, tri.data(), static_cast<int>(tri.size()), marker_color, cv::LINE_AA);
    cv::line(canvas, tri[0], tri[1], border_color, 1, cv::LINE_AA);
    cv::line(canvas, tri[1], tri[2], border_color, 1, cv::LINE_AA);
    cv::line(canvas, tri[2], tri[0], border_color, 1, cv::LINE_AA);
}

struct LegendEntry
{
    std::string label;
    int count = 0;
    cv::Scalar color{255, 255, 255};
};

void drawOverlayPanel(cv::Mat &canvas,
                      const cv::Rect &rect,
                      const cv::Scalar &fill,
                      double alpha,
                      const cv::Scalar &border)
{
    if (canvas.empty()) return;

    const cv::Rect bounds(0, 0, canvas.cols, canvas.rows);
    const cv::Rect clipped = rect & bounds;
    if (clipped.width <= 0 || clipped.height <= 0) {
        return;
    }

    cv::Mat roi = canvas(clipped);
    cv::Mat overlay(roi.size(), roi.type(), fill);
    cv::addWeighted(overlay, alpha, roi, 1.0 - alpha, 0.0, roi);
    cv::rectangle(canvas, clipped, border, 1, cv::LINE_AA);
}

std::vector<LegendEntry> buildLegendEntries(const std::vector<BBox3D> &boxes,
                                            const std::vector<std::string> &class_names)
{
    std::vector<LegendEntry> entries;
    if (!class_names.empty()) {
        std::vector<int> counts(class_names.size(), 0);
        for (const auto &box : boxes) {
            if (box.label >= 0 && box.label < static_cast<int>(class_names.size())) {
                counts[static_cast<size_t>(box.label)]++;
            }
        }

        for (size_t index = 0; index < counts.size(); ++index) {
            if (counts[index] == 0) continue;
            entries.push_back({class_names[index], counts[index], colorForLabel(static_cast<int>(index), class_names, cv::Scalar(255, 255, 255))});
        }
    }

    for (const auto &box : boxes) {
        if (box.label >= 0 && box.label < static_cast<int>(class_names.size())) {
            continue;
        }

        auto it = std::find_if(entries.begin(), entries.end(), [&](const LegendEntry &entry) {
            return entry.label == labelName(box.label, class_names);
        });
        if (it == entries.end()) {
            entries.push_back({labelName(box.label, class_names), 1, cv::Scalar(255, 255, 255)});
        } else {
            it->count += 1;
        }
    }

    std::sort(entries.begin(), entries.end(), [](const LegendEntry &lhs, const LegendEntry &rhs) {
        if (lhs.count != rhs.count) {
            return lhs.count > rhs.count;
        }
        return lhs.label < rhs.label;
    });

    return entries;
}

void drawCombinedHud(cv::Mat &canvas,
                     int bev_offset_x,
                     const std::vector<BBox3D> &boxes,
                     const std::vector<std::string> &class_names,
                     const std::string &frame_id)
{
    if (canvas.empty()) return;

    const std::vector<LegendEntry> entries = buildLegendEntries(boxes, class_names);
    const int padding = 16;

    float score_sum = 0.0f;
    float score_max = 0.0f;
    int scored_boxes = 0;
    for (const auto &box : boxes) {
        if (!std::isfinite(box.score) || box.score <= 0.0f) {
            continue;
        }
        score_sum += box.score;
        score_max = std::max(score_max, box.score);
        scored_boxes += 1;
    }

    const int hud_width = std::min(300, std::max(180, canvas.cols - 2 * padding));
    const cv::Rect hud_rect(padding, padding, hud_width, 96);
    drawOverlayPanel(canvas, hud_rect, cv::Scalar(18, 18, 20), 0.60, cv::Scalar(96, 96, 96));

    cv::putText(canvas, "BEVFusion", cv::Point(hud_rect.x + 12, hud_rect.y + 24),
                cv::FONT_HERSHEY_SIMPLEX, 0.62, cv::Scalar(240, 240, 240), 1, cv::LINE_AA);

    const std::string frame_line = frame_id.empty() ? "Frame: n/a" : ("Frame: " + frame_id);
    cv::putText(canvas, frame_line, cv::Point(hud_rect.x + 12, hud_rect.y + 48),
                cv::FONT_HERSHEY_SIMPLEX, 0.48, cv::Scalar(210, 210, 210), 1, cv::LINE_AA);

    std::ostringstream det_line;
    det_line << "Detections: " << boxes.size() << "   Classes: " << entries.size();
    cv::putText(canvas, det_line.str(), cv::Point(hud_rect.x + 12, hud_rect.y + 70),
                cv::FONT_HERSHEY_SIMPLEX, 0.46, cv::Scalar(200, 200, 200), 1, cv::LINE_AA);

    std::ostringstream score_line;
    if (scored_boxes > 0) {
        score_line << "Score avg/max: " << std::fixed << std::setprecision(2)
                   << (score_sum / static_cast<float>(scored_boxes)) << " / " << score_max;
    } else {
        score_line << "Score avg/max: n/a";
    }
    cv::putText(canvas, score_line.str(), cv::Point(hud_rect.x + 12, hud_rect.y + 90),
                cv::FONT_HERSHEY_SIMPLEX, 0.44, cv::Scalar(190, 190, 190), 1, cv::LINE_AA);

    const int legend_width = std::min(240, std::max(160, canvas.cols - bev_offset_x - 2 * padding));
    if (legend_width < 160) {
        return;
    }

    const size_t max_entries = 6;
    const size_t shown_entries = std::min(max_entries, entries.size());
    const bool has_overflow = entries.size() > shown_entries;
    const int legend_rows = static_cast<int>(shown_entries) + (has_overflow ? 1 : 0);
    const int legend_height = std::max(72, 34 + legend_rows * 22 + 12);
    const int legend_x = std::max(bev_offset_x + padding, canvas.cols - legend_width - padding);
    const cv::Rect legend_rect(legend_x, padding, legend_width, legend_height);
    drawOverlayPanel(canvas, legend_rect, cv::Scalar(18, 18, 20), 0.64, cv::Scalar(96, 96, 96));

    cv::putText(canvas, "Legend", cv::Point(legend_rect.x + 12, legend_rect.y + 24),
                cv::FONT_HERSHEY_SIMPLEX, 0.56, cv::Scalar(240, 240, 240), 1, cv::LINE_AA);

    int text_y = legend_rect.y + 46;
    if (entries.empty()) {
        cv::putText(canvas, "No detections", cv::Point(legend_rect.x + 12, text_y),
                    cv::FONT_HERSHEY_SIMPLEX, 0.46, cv::Scalar(190, 190, 190), 1, cv::LINE_AA);
        return;
    }

    for (size_t index = 0; index < shown_entries; ++index) {
        const LegendEntry &entry = entries[index];
        const cv::Rect swatch(legend_rect.x + 12, text_y - 11, 12, 12);
        cv::rectangle(canvas, swatch, entry.color, cv::FILLED);
        cv::rectangle(canvas, swatch, cv::Scalar(0, 0, 0), 1, cv::LINE_AA);

        std::ostringstream os;
        os << entry.label << " x" << entry.count;
        cv::putText(canvas, os.str(), cv::Point(legend_rect.x + 32, text_y),
                    cv::FONT_HERSHEY_SIMPLEX, 0.46, cv::Scalar(210, 210, 210), 1, cv::LINE_AA);
        text_y += 22;
    }

    if (has_overflow) {
        std::ostringstream os;
        os << "+" << (entries.size() - shown_entries) << " more";
        cv::putText(canvas, os.str(), cv::Point(legend_rect.x + 12, text_y),
                    cv::FONT_HERSHEY_SIMPLEX, 0.44, cv::Scalar(170, 170, 170), 1, cv::LINE_AA);
    }
}

void drawLidarGrid(cv::Mat &canvas, const LidarVizOptions &opts)
{
    if (canvas.empty()) return;

    const float grid_step = 10.0f;
    const cv::Scalar grid_color(55, 55, 55);
    const cv::Scalar axis_color(95, 95, 95);
    const cv::Scalar text_color(180, 180, 180);

    auto nearZero = [](float v) {
        return std::fabs(v) < 1e-3f;
    };

    const float y0 = std::ceil(opts.ylim.first / grid_step) * grid_step;
    for (float y = y0; y <= opts.ylim.second + 1e-3f; y += grid_step) {
        cv::Point2f p0 = toPixel(cv::Point2f(opts.xlim.first, y), opts, canvas.size());
        cv::Point2f p1 = toPixel(cv::Point2f(opts.xlim.second, y), opts, canvas.size());
        const bool is_axis = nearZero(y);
        cv::line(canvas, p0, p1, is_axis ? axis_color : grid_color, is_axis ? 2 : 1, cv::LINE_AA);

        const int lx = static_cast<int>(std::round(p0.x)) + 2;
        const int ly = canvas.rows - 6;
        if (lx >= 0 && lx < canvas.cols) {
            std::ostringstream os;
            os << static_cast<int>(std::lround(y)) << "m";
            cv::putText(canvas, os.str(), cv::Point(lx, ly), cv::FONT_HERSHEY_SIMPLEX, 0.35, text_color, 1, cv::LINE_AA);
        }
    }

    const float x0 = std::ceil(opts.xlim.first / grid_step) * grid_step;
    for (float x = x0; x <= opts.xlim.second + 1e-3f; x += grid_step) {
        cv::Point2f p0 = toPixel(cv::Point2f(x, opts.ylim.first), opts, canvas.size());
        cv::Point2f p1 = toPixel(cv::Point2f(x, opts.ylim.second), opts, canvas.size());
        const bool is_axis = nearZero(x);
        cv::line(canvas, p0, p1, is_axis ? axis_color : grid_color, is_axis ? 2 : 1, cv::LINE_AA);

        const int lx = 6;
        const int ly = static_cast<int>(std::round(p0.y)) - 2;
        if (ly > 10 && ly < canvas.rows) {
            std::ostringstream os;
            os << static_cast<int>(std::lround(x)) << "m";
            cv::putText(canvas, os.str(), cv::Point(lx, ly), cv::FONT_HERSHEY_SIMPLEX, 0.35, text_color, 1, cv::LINE_AA);
        }
    }
}


cv::Mat Visualizer::buildCameraFrame_(const ImageData_t &image,
                                      const std::vector<BBox3D> &boxes,
                                      const CalibField_t &calib,
                                      const std::vector<std::string> &class_names)
{
    const CameraVizOptions &opts = options_.cam_opts;
    const cv::Size default_size = image.empty() ? cv::Size(1242, 375) : image.size();
    cv::Mat canvas;
    if (image.empty()) {
        canvas = makeBlack(default_size);
    }
    else if (image.channels() == 3) {
        canvas = image.clone();
    }
    else {
        cv::cvtColor(image, canvas, cv::COLOR_GRAY2BGR);
    }

    const Transform4x4 *lidar_to_cam = findLidarToCamera(calib);
    const CameraParams *cam_params = findCameraParams(calib, opts.camera_index);
    if (lidar_to_cam == nullptr || cam_params == nullptr) {
        return canvas;  // no calibration, just return the blank/copy
    }

    const cv::Matx44f T = toMatx(*lidar_to_cam);
    const cv::Matx34f K = toMatx(*cam_params);

    for (const auto &box : boxes) {
        CornerArray corners = computeBoxCorners(box);
        std::array<cv::Point2f, 8> proj{};
        bool valid = true;
        float min_depth = std::numeric_limits<float>::max();
        for (size_t i = 0; i < corners.size(); ++i) {
            float depth = 0.0f;
            if (!projectPoint(corners[i], T, K, proj[i], depth)) {
                valid = false;
                break;
            }
            min_depth = std::min(min_depth, depth);
        }
        if (!valid || min_depth <= 0.0f) {
            continue;
        }

        const cv::Scalar color = colorForLabel(box.label, class_names, opts.default_color);
        drawBoxEdgesClipped(canvas, proj, color, static_cast<int>(std::round(opts.line_thickness)));

        // Draw class label near the box (only when class names are provided).
        if (!class_names.empty()) {
            cv::Rect bbox;
            if (computeLabelBBoxFromVisiblePoints(proj, canvas.size(), bbox)) {
                drawLabelBox(canvas, bbox, boxLabelText(box, class_names), color);
            }
        }
    }

    return canvas;
}

cv::Mat Visualizer::buildLidarFrame_(const lidarVec_t &lidar,
                                     const std::vector<BBox3D> &boxes,
                                     const std::vector<std::string> &class_names)
{
    const LidarVizOptions &opts = options_.lidar_opts;
    const cv::Size canvas_size = opts.canvas_size.area() > 0 ? opts.canvas_size : cv::Size(800, 800);
    cv::Mat canvas = makeBlack(canvas_size);
    cv::Mat point_layer(canvas_size, CV_8UC3, cv::Scalar(0, 0, 0));

    drawLidarGrid(canvas, opts);

    const float max_distance = std::sqrt(std::max(std::fabs(opts.xlim.first), std::fabs(opts.xlim.second)) *
                                             std::max(std::fabs(opts.xlim.first), std::fabs(opts.xlim.second)) +
                                         std::max(std::fabs(opts.ylim.first), std::fabs(opts.ylim.second)) *
                                             std::max(std::fabs(opts.ylim.first), std::fabs(opts.ylim.second)));

    std::vector<LidarBoxFootprint> footprints;
    footprints.reserve(boxes.size());
    for (const auto &box : boxes) {
        footprints.push_back(makeLidarBoxFootprint(box, class_names, opts, canvas_size));
    }

    // draw points
    for (size_t i = 0; i + 3 < lidar.size(); i += 4) {
        cv::Point3f p(lidar[i], lidar[i + 1], lidar[i + 2]);
        if (!insideRange(p, opts)) {
            continue;
        }

        const cv::Point2f pix = toPixel(cv::Point2f(p.x, p.y), opts, canvas_size);
        const float distance = std::sqrt(p.x * p.x + p.y * p.y);

        cv::circle(point_layer, pix, opts.point_radius, backgroundPointColor(distance, max_distance), cv::FILLED, cv::LINE_AA);
    }

    cv::addWeighted(canvas, 1.0, point_layer, 0.38, 0.0, canvas);

    // draw boxes on BEV (use bottom face)
    for (const auto &footprint : footprints) {
        const cv::Rect clip_rect(0, 0, canvas.cols, canvas.rows);
        for (int i = 0; i < 4; ++i) {
            cv::Point p0(static_cast<int>(std::lround(footprint.pixel_poly[static_cast<size_t>(i)].x)),
                         static_cast<int>(std::lround(footprint.pixel_poly[static_cast<size_t>(i)].y)));
            cv::Point p1(static_cast<int>(std::lround(footprint.pixel_poly[static_cast<size_t>((i + 1) % 4)].x)),
                         static_cast<int>(std::lround(footprint.pixel_poly[static_cast<size_t>((i + 1) % 4)].y)));
            if (cv::clipLine(clip_rect, p0, p1)) {
                cv::line(canvas, p0, p1, cv::Scalar(0, 0, 0), opts.box_thickness + 2, cv::LINE_AA);
                cv::line(canvas, p0, p1, footprint.color, opts.box_thickness, cv::LINE_AA);
            }
        }

        cv::Rect bbox;
        if (computeLabelBBoxFromVisiblePoints(footprint.pixel_poly, canvas.size(), bbox) && footprint.box != nullptr) {
            drawLabelBox(canvas, bbox, boxLabelText(*footprint.box, class_names), footprint.color);
        }
    }

    drawEgoMarker(canvas, opts);

    return canvas;
}

cv::Mat Visualizer::buildCombinedFrame_(const ImageData_t &image,
                                        const lidarVec_t &lidar,
                                        const std::vector<BBox3D> &boxes,
                                        const CalibField_t &calib,
                                        const std::vector<std::string> &class_names,
                                        const std::string &frame_id)
{
    cv::Mat cam = buildCameraFrame_(image, boxes, calib, class_names);
    cv::Mat bev = buildLidarFrame_(lidar, boxes, class_names);

    if (cam.empty()) {
        cam = makeBlack(cv::Size(640, 480));
    }
    if (bev.empty()) {
        bev = makeBlack(cv::Size(640, 480));
    }

    const int target_height = cam.rows;
    const double scale = static_cast<double>(target_height) / static_cast<double>(bev.rows);
    cv::Mat bev_resized;
    cv::resize(bev, bev_resized, cv::Size(static_cast<int>(std::round(bev.cols * scale)), target_height));

    cv::Mat combined(cv::Size(cam.cols + bev_resized.cols, target_height), CV_8UC3, cv::Scalar(0, 0, 0));
    cam.copyTo(combined(cv::Rect(0, 0, cam.cols, cam.rows)));
    bev_resized.copyTo(combined(cv::Rect(cam.cols, 0, bev_resized.cols, bev_resized.rows)));
    drawCombinedHud(combined, cam.cols, boxes, class_names, frame_id);

    return combined;
}

Visualizer::Visualizer(const VisualizerOptions &opts)
    : options_(opts)
{
}

bool Visualizer::ensureOutputDir_()
{
    if (!(options_.save_images || options_.save_video)) return true;
    std::error_code ec;
    std::filesystem::create_directories(options_.output_dir, ec);
    if (ec) {
        std::cerr << "[vis] Failed to create output_dir: " << options_.output_dir << ", error=" << ec.message() << std::endl;
        return false;
    }
    return true;
}

bool Visualizer::initialize()
{
    if (!options_.enable) return true;
    if (!ensureOutputDir_()) return false;
    initialized_ = true;
    return true;
}

bool Visualizer::initVideoWriter_(const cv::Mat &frame)
{
    if (!options_.save_video) return true;
    if (frame.empty()) return false;

    const int max_w = options_.max_width > 0 ? options_.max_width : frame.cols;
    const int max_h = options_.max_height > 0 ? options_.max_height : frame.rows;
    const double scale_w = static_cast<double>(max_w) / static_cast<double>(frame.cols);
    const double scale_h = static_cast<double>(max_h) / static_cast<double>(frame.rows);
    const double scale = std::min(1.0, std::min(scale_w, scale_h));
    if (scale < 1.0) {
        video_needs_resize_ = true;
        video_size_ = cv::Size(std::max(1, static_cast<int>(frame.cols * scale)),
                               std::max(1, static_cast<int>(frame.rows * scale)));
        video_size_.width &= ~1;
        video_size_.height &= ~1;
        std::cout << "[vis] Downscale video to: " << video_size_.width << "x" << video_size_.height << std::endl;
    } else {
        video_needs_resize_ = false;
        video_size_ = cv::Size(frame.cols, frame.rows);
    }

    std::filesystem::path video_path = options_.output_dir / options_.video_name;

    bool opened = false;
    {
        const int fourcc = cv::VideoWriter::fourcc('a', 'v', 'c', '1');
        video_writer_.open(video_path.string(), fourcc, options_.fps, video_size_, true);
        opened = video_writer_.isOpened();
        if (opened) std::cout << "[vis] Codec: avc1 (H.264)" << std::endl;
    }
    if (!opened) {
        const int fourcc = cv::VideoWriter::fourcc('m', 'p', '4', 'v');
        video_writer_.open(video_path.string(), fourcc, options_.fps, video_size_, true);
        opened = video_writer_.isOpened();
        if (opened) std::cout << "[vis] Codec: mp4v" << std::endl;
    }
    if (!opened) {
        // Switch container to AVI for MJPG.
        video_path = options_.output_dir / "bevfusion.avi";
        const int fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
        video_writer_.open(video_path.string(), fourcc, options_.fps, video_size_, true);
        opened = video_writer_.isOpened();
        if (opened) std::cout << "[vis] Codec: MJPG (AVI fallback)" << std::endl;
    }

    if (!opened) {
        std::cerr << "[vis] Failed to open video writer (tried avc1/mp4v/MJPG). Output path: "
                  << video_path << std::endl;
        return false;
    }

    std::cout << "[vis] Writing video to: " << video_path << std::endl;
    video_writer_initialized_ = true;
    return true;
}

cv::Mat Visualizer::maybeResize_(const cv::Mat &frame)
{
    if (!video_needs_resize_) return frame;
    cv::Mat out;
    cv::resize(frame, out, video_size_, 0.0, 0.0, cv::INTER_AREA);
    return out;
}

bool Visualizer::saveImage_(const cv::Mat &frame, const std::string &path)
{
    if (frame.empty() || path.empty()) return false;
    return cv::imwrite(path, frame);
}

bool Visualizer::processFrame_(const cv::Mat &frame, const std::string &frame_id)
{
    if (frame.empty()) {
        std::cerr << "[vis] Empty visualization frame" << std::endl;
        return false;
    }

    if (options_.display) {
        const char* disp = std::getenv("DISPLAY");
        const char* wayland = std::getenv("WAYLAND_DISPLAY");
        show_window_ = (disp && *disp) || (wayland && *wayland);
        if (show_window_) {
            cv::namedWindow("bevfusion", cv::WINDOW_NORMAL);
        } else {
            std::cout << "[vis] --display requested but no DISPLAY/WAYLAND found; skip cv::imshow()" << std::endl;
        }
        options_.display = show_window_;
    }

    if (options_.save_video && !video_writer_initialized_) {
        if (!initVideoWriter_(frame)) {
            return false;
        }
    }

    cv::Mat out_frame = options_.save_video ? maybeResize_(frame) : frame;

    if (options_.save_images && !frame_id.empty()) {
        std::filesystem::path img_path = options_.output_dir / ("frame_" + frame_id + ".png");
        saveImage_(out_frame, img_path.string());
    }

    if (options_.save_video && video_writer_initialized_) {
        video_writer_.write(out_frame);
    }

    if (options_.display && show_window_) {
        cv::imshow("bevfusion", out_frame);
        const int key = cv::waitKey(1);
        if (key == 27 || key == 'q' || key == 'Q') {
            std::cout << "[vis] Stop requested by user" << std::endl;
            return true;
        }
    }

    return false;
}

bool Visualizer::renderCamera(const ImageData_t &image,
                              const std::vector<BBox3D> &boxes,
                              const CalibField_t &calib,
                              const std::vector<std::string> &class_names,
                              const std::string &frame_id)
{
    return render(image, lidarVec_t{}, boxes, calib, class_names, frame_id, RenderMode::Camera);
}

bool Visualizer::renderLidar(const lidarVec_t &lidar,
                             const std::vector<BBox3D> &boxes,
                             const std::vector<std::string> &class_names,
                             const std::string &frame_id)
{
    return render(ImageData_t{}, lidar, boxes, CalibField_t{}, class_names, frame_id, RenderMode::Lidar);
}

bool Visualizer::renderCombined(const ImageData_t &image,
                                const lidarVec_t &lidar,
                                const std::vector<BBox3D> &boxes,
                                const CalibField_t &calib,
                                const std::vector<std::string> &class_names,
                                const std::string &frame_id)
{
    return render(image, lidar, boxes, calib, class_names, frame_id, RenderMode::Combined);
}

bool Visualizer::render(const ImageData_t &image,
                        const lidarVec_t &lidar,
                        const std::vector<BBox3D> &boxes,
                        const CalibField_t &calib,
                        const std::vector<std::string> &class_names,
                        const std::string &frame_id,
                        RenderMode mode)
{
    if (!options_.enable) return false;
    if (!initialized_ && !initialize()) return false;

    switch (mode) {
    case RenderMode::Camera:
        return processFrame_(buildCameraFrame_(image, boxes, calib, class_names), frame_id);
    case RenderMode::Lidar:
        return processFrame_(buildLidarFrame_(lidar, boxes, class_names), frame_id);
    case RenderMode::Combined:
    default:
        return processFrame_(buildCombinedFrame_(image, lidar, boxes, calib, class_names, frame_id), frame_id);
    }
}

void Visualizer::close()
{
    if (video_writer_initialized_) {
        video_writer_.release();
        video_writer_initialized_ = false;
    }
    if (options_.display && show_window_) {
        cv::destroyWindow("bevfusion");
    }
}

AsyncVisualizer::AsyncVisualizer(const VisualizerOptions &vis_opts,
                                 const AsyncVisualizerOptions &async_opts)
    : visualizer_(vis_opts),
      async_opts_(async_opts)
{
}

bool AsyncVisualizer::initialize()
{
    if (!visualizer_.isEnabled()) return true;
    if (!visualizer_.initialize()) return false;
    running_.store(true);
    worker_ = std::thread(&AsyncVisualizer::workerLoop_, this);
    return true;
}

bool AsyncVisualizer::enqueue_(Task &&task)
{
    if (!visualizer_.isEnabled()) return false;
    if (!running_.load()) return false;

    std::unique_lock<std::mutex> lock(mutex_);
    if (queue_.size() >= async_opts_.max_queue_size) {
        if (async_opts_.drop_oldest) {
            queue_.pop_front();
        } else {
            return false;
        }
    }
    queue_.emplace_back(std::move(task));
    lock.unlock();
    cv_.notify_one();
    return true;
}

bool AsyncVisualizer::render(const ImageData_t &image,
                             const lidarVec_t &lidar,
                             const std::vector<BBox3D> &boxes,
                             const CalibField_t &calib,
                             const std::vector<std::string> &class_names,
                             const std::string &frame_id,
                             Visualizer::RenderMode mode)
{
    Task task;
    task.mode = mode;
    task.image = image;
    task.lidar = lidar;
    task.boxes = boxes;
    task.calib = calib;
    task.class_names = class_names;
    task.frame_id = frame_id;
    return enqueue_(std::move(task));
}

bool AsyncVisualizer::renderCamera(const ImageData_t &image,
                                   const std::vector<BBox3D> &boxes,
                                   const CalibField_t &calib,
                                   const std::vector<std::string> &class_names,
                                   const std::string &frame_id)
{
    return render(image, lidarVec_t{}, boxes, calib, class_names, frame_id, Visualizer::RenderMode::Camera);
}

bool AsyncVisualizer::renderLidar(const lidarVec_t &lidar,
                                  const std::vector<BBox3D> &boxes,
                                  const std::vector<std::string> &class_names,
                                  const std::string &frame_id)
{
    return render(ImageData_t{}, lidar, boxes, CalibField_t{}, class_names, frame_id, Visualizer::RenderMode::Lidar);
}

bool AsyncVisualizer::renderCombined(const ImageData_t &image,
                                     const lidarVec_t &lidar,
                                     const std::vector<BBox3D> &boxes,
                                     const CalibField_t &calib,
                                     const std::vector<std::string> &class_names,
                                     const std::string &frame_id)
{
    return render(image, lidar, boxes, calib, class_names, frame_id, Visualizer::RenderMode::Combined);
}

void AsyncVisualizer::workerLoop_()
{
    // Use while(true): the inner break condition drains the queue before exiting.
    // while(running_.load()) would exit immediately when close() sets running_=false,
    // abandoning any pending render/save tasks.
    while (true) {
        Task task;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [&]() { return !running_.load() || !queue_.empty(); });
            if (!running_.load() && queue_.empty()) {
                break;  // shutdown signal received AND queue fully drained
            }
            task = std::move(queue_.front());
            queue_.pop_front();
        }

        bool stop = false;
        switch (task.mode) {
        case Visualizer::RenderMode::Camera:
            stop = visualizer_.renderCamera(task.image, task.boxes, task.calib, task.class_names, task.frame_id);
            break;
        case Visualizer::RenderMode::Lidar:
            stop = visualizer_.renderLidar(task.lidar, task.boxes, task.class_names, task.frame_id);
            break;
        case Visualizer::RenderMode::Combined:
        default:
            stop = visualizer_.renderCombined(task.image, task.lidar, task.boxes, task.calib, task.class_names, task.frame_id);
            break;
        }

        if (stop) {
            stop_requested_.store(true);
        }
    }
}

void AsyncVisualizer::close()
{
    if (!visualizer_.isEnabled()) return;
    running_.store(false);
    cv_.notify_all();
    if (worker_.joinable()) {
        worker_.join();
    }
    visualizer_.close();
}
