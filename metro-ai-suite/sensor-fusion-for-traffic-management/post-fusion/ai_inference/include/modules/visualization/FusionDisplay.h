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

#ifndef FUSION_DISPLAY_H
#define FUSION_DISPLAY_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <string>
#include <mutex>

enum class LidarViewType { FRONT, BIRDVIEW };

struct FusionVisualizerConfig
{
    int camera_count = 4;
    int cam_rows = 2;
    int cam_cols = 2;
    int sensor_num = 4;  // number of camera sensors to display in one thread
    int camera_canvas_width = 640;
    int camera_canvas_height = 480;
    int lidar_canvas_width = 360;
    int lidar_canvas_height = 480;
    LidarViewType lidar_view = LidarViewType::FRONT;
    double lidar_x_min = 0, lidar_x_max = 80;
    double lidar_y_min = -30, lidar_y_max = 30;
    double grid_step = 5.0;
    std::string window_name = "Fusion Visualizer";
    std::string fusion_type = "1C1L";  // 1C1L, 2C1L, 2C2L, 4C2L, 4C4L, 8C2L, 8C4L, 12C2L, 12C4L
};


class FusionVisualizer {
  public:
    FusionVisualizer(const FusionVisualizerConfig &cfg);
    void updateLoading(cv::Mat &img);
    void updateCamera(int idx, cv::Mat &img, const cv::Mat &camera);
    void drawLidarText(cv::Mat &img,
                       const std::vector<cv::Point2f> &points,
                       const std::vector<std::string> &texts,
                       double font_scale,
                       const cv::Scalar &color,
                       int thickness,
                       int lineType,
                       bool refresh);
    void drawLidarObjects(cv::Mat &img,
                          const std::vector<std::vector<cv::Point2f>> &rois,
                          const std::vector<float> &vx_all,
                          const std::vector<float> &vy_all,
                          const cv::Scalar &color,
                          int thickness,
                          int lineType,
                          bool refresh);
    void drawCameraText(cv::Mat &img, int canvas_idx, const std::string &text, cv::Point pos, cv::Scalar color, int thickness, double fontScale, int lineType);

    // Draw 3D box projection on camera canvas
    // corners_2d: 8*2 float vector, [x0,y0,x1,y1,...,x7,y7]
    void drawCamera3DBox(cv::Mat &img, int canvas_idx, const std::vector<std::vector<float>> &corners_2d_arr, cv::Scalar color, int thickness, int lineType);

    void drawCameraBox(cv::Mat &img, int canvas_idx, cv::Point start_point, cv::Point end_point, cv::Scalar color, int thickness, int lineType);

    // Draw metrics information on the fusion canvas
    // metrics: One string per line, cols is the width of the right margin
    void drawMetrics(cv::Mat &img,
                     const std::vector<std::string> &metrics,
                     int cols = 0,
                     int offset = 20,
                     double fontScale = 0.5,
                     int thickness = 1,
                     int lineSpace = 5,
                     cv::Scalar color = cv::Scalar(255, 0, 0),
                     bool is_lidar = true);

    void refreshLidarCanvas(cv::Mat &img);

    const std::vector<cv::Rect> &getCameraCanvasInfos() const
    {
        return camera_canvas_infos_;
    }
    const cv::Size getFusionCanvasSize() const
    {
        return fusion_canvas_size_;
    }
    const cv::Rect getCameraCanvasROI() const
    {
        return camera_canvas_roi_;
    }
    const cv::Rect getLidarCanvasROI() const
    {
        return lidar_canvas_roi_;
    }

  public:
    FusionVisualizerConfig config_;
    std::vector<cv::Rect> camera_canvas_infos_;  // roi info of different camera canvas in fusion_canvas_
    cv::Rect lidar_canvas_roi_;                  // roi info of lidar canvas in fusion_canvas_
    cv::Rect camera_canvas_roi_;                 // roi info of total camera canvas in fusion_canvas_
    cv::Size fusion_canvas_size_;                // size of fusion canvas

  private:
    std::mutex mtx_;
    cv::Mat lidar_bg_template_;  // background template for lidar canvas

    // cv::Mat fusion_canvas_;  // fusion canvas for displaying all camera and lidar
    // cv::Mat camera_canvas_;  // canvas for all cameras
    // cv::Mat lidar_canvas_;   // lidar canvas

    void createLidarBackground();
    void drawLidarGridAndFOV(cv::Mat &canvas);
};

#endif  // FUSION_DISPLAY_H
