/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include "modules/visualization/FusionDisplay.h"
#include <vector>
#include <string>
#include <opencv2/opencv.hpp>
#include <math.h>
#include <numeric>

FusionVisualizer::FusionVisualizer(const FusionVisualizerConfig &cfg) : config_(cfg)
{
    // int cam_rows = static_cast<int>(std::ceil(std::sqrt(cfg.camera_count)));
    // int cam_cols = static_cast<int>(std::ceil(cfg.camera_count / (float)cam_rows));
    int cam_rows = cfg.cam_rows;
    int cam_cols = cfg.cam_cols;
    int camera_area_width = cam_cols * cfg.camera_canvas_width;
    int camera_area_height = cam_rows * cfg.camera_canvas_height;

    int fusion_height = std::max(camera_area_height, cfg.lidar_canvas_height);
    int camera_resize_width = cfg.camera_canvas_width;
    int camera_resize_height = cfg.camera_canvas_height;
    int lidar_resize_width = cfg.lidar_canvas_width;
    int lidar_resize_height = cfg.lidar_canvas_height;

    // If the camera area height is not equal to fusion_height, resize proportionally
    if (camera_area_height != fusion_height) {
        double scale = static_cast<double>(fusion_height) / camera_area_height;
        camera_resize_width = static_cast<int>(cfg.camera_canvas_width * scale);
        camera_resize_height = static_cast<int>(cfg.camera_canvas_height * scale);
        config_.camera_canvas_width = camera_resize_width;
        config_.camera_canvas_height = camera_resize_height;
        camera_area_width = cam_cols * camera_resize_width;
        camera_area_height = cam_rows * camera_resize_height;
    }
    // If the lidar area height is not equal to fusion_height, resize proportionally and update config_
    if (lidar_resize_height != fusion_height) {
        double scale = static_cast<double>(fusion_height) / lidar_resize_height;
        lidar_resize_width = static_cast<int>(cfg.lidar_canvas_width * scale);
        lidar_resize_height = fusion_height;
        config_.lidar_canvas_width = lidar_resize_width;
        config_.lidar_canvas_height = lidar_resize_height;
    }

    int fusion_width = camera_area_width + lidar_resize_width;
    fusion_canvas_size_ = cv::Size(fusion_width, fusion_height);

    camera_canvas_infos_.resize(cfg.camera_count);
    for (int i = 0; i < cfg.camera_count; ++i) {
        int row = i / cam_cols;
        int col = i % cam_cols;
        int x = col * camera_resize_width;
        int y = row * camera_resize_height;
        camera_canvas_infos_[i] = cv::Rect(x, y, camera_resize_width, camera_resize_height);
    }

    camera_canvas_roi_ = cv::Rect(0, 0, camera_area_width, camera_area_height);
    lidar_canvas_roi_ = cv::Rect(camera_area_width, 0, lidar_resize_width, lidar_resize_height);

    createLidarBackground();
}

void FusionVisualizer::createLidarBackground()
{
    lidar_bg_template_ = cv::Mat::zeros(config_.lidar_canvas_height, config_.lidar_canvas_width, CV_8UC3);
    drawLidarGridAndFOV(lidar_bg_template_);
}

void FusionVisualizer::drawLidarGridAndFOV(cv::Mat &canvas)
{
    // Axes and Grid
    double x_min = config_.lidar_x_min, x_max = config_.lidar_x_max;
    double y_min = config_.lidar_y_min, y_max = config_.lidar_y_max;
    double step = config_.grid_step;
    int w = canvas.cols, h = canvas.rows;
    cv::Scalar grid_color(180, 180, 180);

    // Grid lines and ticks
    for (double x = x_min; x <= x_max; x += step) {
        int px = static_cast<int>((x - x_min) / (x_max - x_min) * w);
        cv::line(canvas, cv::Point(px, 0), cv::Point(px, h), grid_color, 1);
        // cv::putText(canvas, std::to_string(static_cast<int>(x)), cv::Point(px, h - 10), cv::FONT_HERSHEY_SIMPLEX, 0.5, grid_color, 1);
    }
    for (double y = y_min; y <= y_max; y += step) {
        int py = h - static_cast<int>((y - y_min) / (y_max - y_min) * h);
        cv::line(canvas, cv::Point(0, py), cv::Point(w, py), grid_color, 1);
        cv::putText(canvas, std::to_string(static_cast<int>(y)), cv::Point(5, py - 5), cv::FONT_HERSHEY_SIMPLEX, 0.5, grid_color, 1);
    }

    // // FOV Area
    // if (config_.lidar_view == LidarViewType::FRONT) {
    //     std::vector<cv::Point> fov_pts = {cv::Point(w / 2, h),     cv::Point(w, h),     cv::Point(w, h / 2),
    //                                       cv::Point(w / 2, h / 4), cv::Point(0, h / 2), cv::Point(0, h)};
    //     cv::polylines(canvas, fov_pts, true, cv::Scalar(255, 255, 0), 2);
    //     cv::fillPoly(canvas, std::vector<std::vector<cv::Point>>{fov_pts}, cv::Scalar(255, 255, 0, 30));
    // }
    // else {
    //     // Birdview: Front, Back, Left, Right FOV
    //     cv::rectangle(canvas, cv::Point(0, 0), cv::Point(w - 1, h - 1), cv::Scalar(255, 255, 0), 2);
    //     cv::circle(canvas, cv::Point(w / 2, h / 2), 5, cv::Scalar(255, 255, 255), -1);
    // }
}

void FusionVisualizer::updateLoading(cv::Mat &img)
{
    for (int idx = 0; idx < camera_canvas_infos_.size(); ++idx) {
        cv::putText(img(camera_canvas_infos_[idx]), "Loading...", cv::Point(camera_canvas_infos_[idx].width / 3, camera_canvas_infos_[idx].height / 2),
                    cv::FONT_HERSHEY_SIMPLEX, 1.0, cv::Scalar(200, 200, 255), 2);
    }
    cv::putText(img(lidar_canvas_roi_), "Loading...", cv::Point(lidar_canvas_roi_.width / 2, lidar_canvas_roi_.height / 3), cv::FONT_HERSHEY_SIMPLEX, 1.0,
                cv::Scalar(200, 200, 255), 2);
}

void FusionVisualizer::updateCamera(int idx, cv::Mat &img, const cv::Mat &camera)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (idx < 0 || idx >= camera_canvas_infos_.size())
        return;
    cv::Mat resized;
    cv::resize(camera, resized, camera_canvas_infos_[idx].size());
    resized.copyTo(img(camera_canvas_infos_[idx]));
}

void FusionVisualizer::drawLidarText(cv::Mat &img,
                                     const std::vector<cv::Point2f> &points,
                                     const std::vector<std::string> &texts,
                                     double font_scale,
                                     const cv::Scalar &color,
                                     int thickness,
                                     int lineType,
                                     bool refresh)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (refresh) {
        img(lidar_canvas_roi_) = lidar_bg_template_.clone();
    }
    if (points.size() != texts.size())
        return;
    // BEV meters->pixel coordinate
    double x_min = config_.lidar_x_min, x_max = config_.lidar_x_max;
    double y_min = config_.lidar_y_min, y_max = config_.lidar_y_max;
    int w = config_.lidar_canvas_width, h = config_.lidar_canvas_height;
    auto bev2pix = [&](const cv::Point2f &pt) -> cv::Point {
        double px = (pt.x - x_min) / (x_max - x_min) * w;
        double py = h - (pt.y - y_min) / (y_max - y_min) * h;
        return cv::Point(static_cast<int>(px + 0.5), static_cast<int>(py + 0.5));
    };
    for (size_t i = 0; i < points.size(); ++i) {
        cv::Point pix = bev2pix(points[i]);
        int baseline = 0;
        cv::Size text_size = cv::getTextSize(texts[i], cv::FONT_HERSHEY_SIMPLEX, font_scale, thickness, &baseline);
        cv::Point text_org(pix.x, std::max(10, pix.y - 6));
        // Draw only in the lidar area
        cv::putText(img(lidar_canvas_roi_), texts[i], text_org, cv::FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, lineType);
    }
}

void FusionVisualizer::drawLidarObjects(cv::Mat &img,
                                        const std::vector<std::vector<cv::Point2f>> &rois,
                                        const std::vector<float> &vx_all,
                                        const std::vector<float> &vy_all,
                                        const cv::Scalar &color,
                                        int thickness,
                                        int lineType,
                                        bool refresh)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (refresh) {
        // lidar_bg_template_.clone().copyTo(fusion_canvas_(lidar_canvas_roi_));
        img(lidar_canvas_roi_) = lidar_bg_template_.clone();
    }

    // BEV meters->pixel coordinate
    double x_min = config_.lidar_x_min, x_max = config_.lidar_x_max;
    double y_min = config_.lidar_y_min, y_max = config_.lidar_y_max;
    int w = lidar_canvas_roi_.width, h = lidar_canvas_roi_.height;
    // x: front and back, y: left and right
    auto bev2pix = [&](const cv::Point2f &pt) -> cv::Point {
        // pt.x: front and back (meters), pt.y: left and right (meters)
        double px = (pt.x - x_min) / (x_max - x_min) * w;
        double py = h - (pt.y - y_min) / (y_max - y_min) * h;
        return cv::Point(static_cast<int>(px + 0.5), static_cast<int>(py + 0.5));
    };

    // Convert all roi points
    std::vector<std::vector<cv::Point>> pixel_rois;
    for (const auto &roi : rois) {
        std::vector<cv::Point> pix_roi;
        for (const auto &pt : roi) {
            pix_roi.push_back(bev2pix(pt));
        }
        pixel_rois.push_back(pix_roi);
    }
    // Transform velocity vector starting point
    std::vector<cv::Point> pixel_centers;
    std::vector<cv::Point> pixel_ends;
    for (size_t i = 0; i < rois.size(); ++i) {
        if (rois[i].size() >= 5 && i < vx_all.size() && i < vy_all.size()) {
            cv::Point2f center = rois[i][4];
            cv::Point2f end(center.x + vx_all[i], center.y + vy_all[i]);
            pixel_centers.push_back(bev2pix(center));
            pixel_ends.push_back(bev2pix(end));
        }
        else {
            pixel_centers.push_back(cv::Point());
            pixel_ends.push_back(cv::Point());
        }
    }

    // Draw target box and speed arrow (pixel coordinates)
    for (size_t i = 0; i < pixel_rois.size(); ++i) {
        if (pixel_rois[i].size() >= 4) {
            cv::rectangle(img(lidar_canvas_roi_), pixel_rois[i][0], pixel_rois[i][2], color, thickness, lineType);
        }
        if (pixel_rois[i].size() >= 5 && i < vx_all.size() && i < vy_all.size()) {
            cv::arrowedLine(img(lidar_canvas_roi_), pixel_centers[i], pixel_ends[i], color, thickness, lineType);
        }
    }
}

void FusionVisualizer::drawCameraText(cv::Mat &img,
                                      int canvas_idx,
                                      const std::string &text,
                                      cv::Point pos,
                                      cv::Scalar color,
                                      int thickness,
                                      double fontScale,
                                      int lineType)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (canvas_idx < 0 || canvas_idx >= camera_canvas_infos_.size())
        return;
    cv::putText(img(camera_canvas_roi_), text, camera_canvas_infos_[canvas_idx].tl() + pos, cv::FONT_HERSHEY_SIMPLEX, fontScale, color, thickness, lineType);
}

// Draw 3D box projection on camera canvas
void FusionVisualizer::drawCamera3DBox(cv::Mat &img,
                                       int canvas_idx,
                                       const std::vector<std::vector<float>> &corners_2d_arr,
                                       cv::Scalar color,
                                       int thickness,
                                       int lineType)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (canvas_idx < 0 || canvas_idx >= camera_canvas_infos_.size())
        return;

    for (int i = 0; i < corners_2d_arr.size(); i++) {
        const std::vector<float> &corners_2d = corners_2d_arr[i];
        // 8 points, each 2 floats
        std::vector<cv::Point> pts(8);
        for (int i = 0; i < 8; ++i) {
            pts[i] =
                camera_canvas_infos_[canvas_idx].tl() + cv::Point(static_cast<int>(corners_2d[2 * i] + 0.5f), static_cast<int>(corners_2d[2 * i + 1] + 0.5f));
        }
        // Define edge connections of 3D box
        const int edges[12][2] = {
            {0, 1}, {1, 2}, {2, 3}, {3, 0},  // bottom
            {4, 5}, {5, 6}, {6, 7}, {7, 4},  // top
            {0, 4}, {1, 5}, {2, 6}, {3, 7}   // vertical
        };
        for (int i = 0; i < 12; ++i) {
            cv::line(img(camera_canvas_roi_), pts[edges[i][0]], pts[edges[i][1]], color, thickness, lineType);
        }
    }
}

void FusionVisualizer::drawCameraBox(cv::Mat &img, int canvas_idx, cv::Point start_point, cv::Point end_point, cv::Scalar color, int thickness, int lineType)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (canvas_idx < 0 || canvas_idx >= camera_canvas_infos_.size())
        return;
    cv::rectangle(img(camera_canvas_roi_), camera_canvas_infos_[canvas_idx].tl() + start_point, camera_canvas_infos_[canvas_idx].tl() + end_point, color,
                  thickness, lineType);
}

void FusionVisualizer::drawMetrics(cv::Mat &img,
                                   const std::vector<std::string> &metrics,
                                   int cols,
                                   int offset,
                                   double fontScale,
                                   int thickness,
                                   int lineSpace,
                                   cv::Scalar color,
                                   bool is_lidar)
{
    std::lock_guard<std::mutex> lock(mtx_);
    int baseline = 0;
    for (const std::string &line : metrics) {
        cv::Size textSize = cv::getTextSize(line, cv::FONT_HERSHEY_SIMPLEX, fontScale, thickness, &baseline);
        if (is_lidar) {
            cv::putText(img(lidar_canvas_roi_), line, cv::Point(lidar_canvas_roi_.width - cols - textSize.width, offset), cv::FONT_HERSHEY_SIMPLEX, fontScale,
                        color, thickness, cv::LINE_8);
        }
        else {
            cv::putText(img(camera_canvas_roi_), line, cv::Point(camera_canvas_roi_.width - cols - textSize.width, offset), cv::FONT_HERSHEY_SIMPLEX, fontScale,
                        color, thickness, cv::LINE_8);
        }
        offset += textSize.height + baseline + lineSpace;
    }
}

void FusionVisualizer::refreshLidarCanvas(cv::Mat &img)
{
    std::lock_guard<std::mutex> lock(mtx_);
    lidar_bg_template_.copyTo(img(lidar_canvas_roi_));
}
