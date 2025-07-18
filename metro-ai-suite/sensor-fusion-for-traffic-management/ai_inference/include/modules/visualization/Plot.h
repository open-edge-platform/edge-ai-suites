/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023-2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef PLOT_H
#define PLOT_H

#include <iostream>
#include <math.h>
#include <opencv2/opencv.hpp>

using namespace cv;
using namespace std;

class Plot {
public:
  Plot(double x_min, double x_max, double y_min, double y_max, double res,
       double grid_step);

  void showPlotImage();
  Mat getPlotImage();

  void drawPoints(const vector<Point2f> &points, const vector<Vec3b> colors,
                  double size, bool with_line = false, bool refresh = true);
  void drawPoints(const vector<Point2f> &points, const Scalar color,
                  double size, bool with_line, bool refresh);
  void drawPoints(const vector<Point2f> &points, const Scalar color,
                  double size, bool refresh = true);
  void drawBoundingBox(const vector<Point2f> &points, const Scalar color,double size,bool refresh);
  void drawBoundingBoxes(const vector<vector<Point2f>> &rois, const Scalar color,double size,bool refresh);
  void drawRadarResults(const vector<vector<Point2f>> &rois, const vector<float>& vx_all, const vector<float>& vy_all,const Scalar color,double size,bool refresh);
  void drawFootprint(const vector<Point2f> &footprint);
  
  void drawSpeed(const Point2f start, float vx, float vy, const Scalar color, double size);

  void drawText(const std::vector<cv::Point2f>& point_all, const vector<std::string>& object_all, const double fontScale, const Scalar color, double size, bool refresh);

  void clear();
  void drawFrontFOV();
  void drawBirdViewFOV();

private:
  void createBackground();


  double res_;       // pixel to meter, e.g., 1 pixel = 0.1 m
  double x_min_;     // min value on x-axis (base_footprint frame)
  double x_max_;     // max value on x-axis (base_footprint frame)
  double y_min_;     // min value on y-axis (base_footprint frame)
  double y_max_;     // max value on y-axis (base_footprint frame)
  double grid_step_; // step for one grid in meters

  int width_;  // image width
  int height_; // image height

  int origin_row_; // row index for frame origin
  int origin_col_; // col index for frame origin

  Mat background_img_;
  Mat plot_img_;
};

#endif // PLOT_H
