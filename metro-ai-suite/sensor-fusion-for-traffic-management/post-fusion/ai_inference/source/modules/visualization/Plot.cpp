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

#include "modules/visualization/Plot.h"

Plot::Plot(double x_min, double x_max, double y_min, double y_max, double res,
           double grid_step)
    : x_min_(x_min), x_max_(x_max), y_min_(y_min), y_max_(y_max), res_(res),
      grid_step_(grid_step) {
  createBackground();
}

// create a background image for plotting
void Plot::createBackground() {
  // params
  // assert(x_min_ < 0);
  assert(y_min_ < 0);

  width_ = (y_max_ - y_min_) / res_;
  height_ = (x_max_ - x_min_) / res_;

  int grid_step_pixel = grid_step_ / res_;

  int x_min_pixel = x_min_ / res_;
  int x_max_pixel = x_max_ / res_;
  int y_min_pixel = y_min_ / res_;
  int y_max_pixel = y_max_ / res_;

  // create plot image
  background_img_ = Mat::zeros(height_, width_, CV_8UC3);

  // add origin
  origin_row_ = height_ + x_min_pixel;
  origin_col_ = width_ / 2;

  circle(background_img_, Point(origin_col_, origin_row_), 5,
         Scalar(255, 255, 255), -1);

  // add grid
  // -- x
  int x_min_grid = x_min_pixel / grid_step_pixel;
  int x_max_grid = x_max_pixel / grid_step_pixel;

  //  cout << "x_min_grid: " << x_min_grid << endl;
  //  cout << "x_max_grid: " << x_max_grid << endl;

  for (int i = x_min_grid; i <= x_max_grid; i++) {
    int row_ind = origin_row_ - i * grid_step_pixel;
    line(background_img_, Point(0, row_ind), Point(width_, row_ind),
         Scalar(125, 125, 125), 1);

    // add grid scale text
    putText(background_img_, to_string(static_cast<int>(i * grid_step_)),
            Point(0, row_ind - 3), FONT_HERSHEY_SIMPLEX, 0.5,
            Scalar(125, 125, 125));
  }

  // -- y
  int y_min_grid = y_min_pixel / grid_step_pixel;
  int y_max_grid = y_max_pixel / grid_step_pixel;

  //  cout << "y_min_grid: " << y_min_grid << endl;
  //  cout << "y_max_grid: " << y_max_grid << endl;

  for (int i = y_min_grid; i <= y_max_grid; i++) {
    int col_ind = origin_col_ - i * grid_step_pixel;
    line(background_img_, Point(col_ind, 0), Point(col_ind, height_),
         Scalar(125, 125, 125), 1);
  }
  // drawFrontFOV();
  // update to image for plotting
  plot_img_ = background_img_.clone();
}

void Plot::drawFrontFOV() {
 // intel real sense d435i FOV
 // https://www.intelrealsense.com/depth-camera-d435i/
 // FOV(HxV): 69x42
 Mat mask = background_img_.clone();
 std::vector<Point> pts;
 pts.push_back(Point(0,0));
 pts.push_back(Point(600,0));
 pts.push_back(Point(600,64));
 pts.push_back(Point(300,500));
 pts.push_back(Point(0,64));
 
 fillPoly(mask, pts, Scalar(255,255,0), 8,0);
 polylines(mask, pts, true, Scalar(255,255,0), 1,8,0);

 addWeighted(background_img_, 0.8, mask, 0.2,0, background_img_, -1);

}
void Plot::drawBirdViewFOV() {
 // intel real sense d435i FOV
 // https://www.intelrealsense.com/depth-camera-d435i/
 // FOV(HxV): 69x42
 Mat mask = background_img_.clone();
 std::vector<Point> pts;
 pts.push_back(Point(0,0));
 pts.push_back(Point(600,0));
 pts.push_back(Point(600,64));
 pts.push_back(Point(300,500));
 pts.push_back(Point(0,64));


 std::vector<Point> pts_back;
 pts_back.push_back(Point(0,936));
 pts_back.push_back(Point(300,500));
 pts_back.push_back(Point(600,936));
 pts_back.push_back(Point(600,1000));
 pts_back.push_back(Point(0,1000));
 
 fillPoly(mask, pts, Scalar(255,255,0), 8,0);
 polylines(mask, pts, true, Scalar(255,255,0), 1,8,0);

 fillPoly(mask, pts_back, Scalar(255,255,0), 8,0);
 polylines(mask, pts_back, true, Scalar(255,255,0), 1,8,0);
 addWeighted(background_img_, 0.8, mask, 0.2,0, background_img_, -1);

}


// add footprint
void Plot::drawFootprint(const vector<Point2f> &footprint) {
  // convert to image coordinate and draw
  for (int i = 0; i < footprint.size(); i++) {
    Point2f p1 = footprint[i];
    int x1 = origin_col_ - p1.y / res_;
    int y1 = origin_row_ - p1.x / res_;
    Point2f p2 = footprint[(i + 1) % footprint.size()];
    int x2 = origin_col_ - p2.y / res_;
    int y2 = origin_row_ - p2.x / res_;

    line(background_img_, Point(x1, y1), Point(x2, y2), Scalar(255, 255, 255),
         2);
  }
}

// show current plot
void Plot::showPlotImage() { imshow("plot", plot_img_); }

// get current plot
Mat Plot::getPlotImage() { return plot_img_; }

// draw points
// colors: if have multiple classes
void Plot::drawPoints(const vector<Point2f> &points, const vector<Vec3b> colors,
                      double size, bool with_line, bool refresh) {
  if (refresh)
    clear();

  for (int i = 0; i < points.size(); i++) {
    Point2f p = points[i];

    // convert to image coordinate
    int row = origin_row_ - p.x / res_;
    int col = origin_col_ - p.y / res_;

    if (row < 0 || row > height_ || col < 0 || col > width_)
      continue;

    Scalar color = Scalar(colors[i][0], colors[i][1], colors[i][2]);

    circle(plot_img_, Point(col, row), size, color, -1);
  }

  if (with_line) {
    for (int i = 0; i < points.size() - 1; i++) {
      Point2f p1 = points[i];
      Point2f p2 = points[i + 1];

      // convert to image coordinate
      int row1 = origin_row_ - p1.x / res_;
      int col1 = origin_col_ - p1.y / res_;

      int row2 = origin_row_ - p2.x / res_;
      int col2 = origin_col_ - p2.y / res_;

      Scalar color = Scalar(colors[i][0], colors[i][1], colors[i][2]);

      line(plot_img_, Point(col1, row1), Point(col2, row2), color, 2);
    }
  }
}
// draw points
void Plot::drawPoints(const vector<Point2f> &points, const Scalar color,
                      double size, bool with_line, bool refresh) {
  if (refresh)
    clear();

  for (int i = 0; i < points.size(); i++) {
    Point2f p = points[i];

    // convert to image coordinate
    int row = origin_row_ - p.x / res_;
    int col = origin_col_ - p.y / res_;

    if (row < 0 || row > height_ || col < 0 || col > width_)
      continue;

    circle(plot_img_, Point(col, row), size, color, -1);
  }

  if (with_line)
  {
    for (int i = 0; i < points.size() - 1; i++) {

      Point2f p1 = points[i];
      Point2f p2 = points[i + 1];

      // convert to image coordinate
      int row1 = origin_row_ - p1.x / res_;
      int col1 = origin_col_ - p1.y / res_;

      int row2 = origin_row_ - p2.x / res_;
      int col2 = origin_col_ - p2.y / res_;

      line(plot_img_, Point(col1, row1), Point(col2, row2), color, 1);
    }

    Point2f start = points[0];
    Point2f end = points[points.size() - 1];
    int row1 = origin_row_ - start.x / res_;
    int col1 = origin_col_ - start.y / res_;

    int row2 = origin_row_ - end.x / res_;
    int col2 = origin_col_ - end.y / res_;

    line(plot_img_, Point(col1, row1), Point(col2, row2), color, 1);  
  }
}

// draw points with one color
void Plot::drawPoints(const vector<Point2f> &points, const Scalar color,
                      double size, bool refresh) {
  if (refresh)
    clear();

  for (int i = 0; i < points.size(); i++) {
    Point2f p = points[i];

    // convert to image coordinate
    int row = origin_row_ - p.x / res_;
    int col = origin_col_ - p.y / res_;

    if (row < 0 || row > height_ || col < 0 || col > width_)
      continue;

    circle(plot_img_, Point(col, row), size, color, -1);
  }
}
// draw bounding box
void Plot::drawBoundingBox(const vector<Point2f> &points, const Scalar color,  double size, bool refresh) {
  if (refresh)
    clear();
  Point2f pt1 = points[0];
  Point2f pt2 = points[2];

  int pt1_row = origin_row_ - pt1.x / res_;
  int pt1_col = origin_col_ - pt1.y / res_;

  int pt2_row = origin_row_ - pt2.x / res_;
  int pt2_col = origin_col_ - pt2.y / res_;

  rectangle(plot_img_, Point(pt1_col, pt1_row), Point(pt2_col, pt2_row), color, size);
}

void Plot::drawBoundingBoxes(const vector<vector<Point2f>> &rois, const Scalar color,double size,bool refresh)
{
  if (refresh)
    clear();

  vector<Point2f> roi(4);
  for (int i = 0; i < rois.size(); i++)
  {
    roi = rois[i];
    Point2f pt1 = roi[0];
    Point2f pt2 = roi[2];

    int pt1_row = origin_row_ - pt1.x / res_;
    int pt1_col = origin_col_ - pt1.y / res_;

    int pt2_row = origin_row_ - pt2.x / res_;
    int pt2_col = origin_col_ - pt2.y / res_;

    rectangle(plot_img_, Point(pt1_col, pt1_row), Point(pt2_col, pt2_row), color, size);
  }
}
 void Plot::drawRadarResults(const vector<vector<Point2f>> &rois, const vector<float>& vx_all, const vector<float>& vy_all, const Scalar color,double size,bool refresh){
    if (refresh)
    clear();

  vector<Point2f> roi(6);
  for (int i = 0; i < rois.size(); i++)
  {
    roi = rois[i];
    Point2f pt1 = roi[0];
    Point2f pt2 = roi[2];

    Point2f center = roi[4];

    int pt1_row = origin_row_ - pt1.x / res_;
    int pt1_col = origin_col_ - pt1.y / res_;

    int pt2_row = origin_row_ - pt2.x / res_;
    int pt2_col = origin_col_ - pt2.y / res_;

    rectangle(plot_img_, Point(pt1_col, pt1_row), Point(pt2_col, pt2_row), color, size);
    cv::Scalar speed_color = cv::Scalar{64, 224, 205};
    drawSpeed(center, vx_all[i], vy_all[i], speed_color, size);
  }
 }
void Plot::drawSpeed(const Point2f start, float vx, float vy, const Scalar color, double size){

  // float speed_abs = sqrt(vx*vx+vy*vy);
  Point2f end(start.x+vx, start.y+vy);
  int start_row = origin_row_ - start.x / res_;
  int start_col = origin_col_ - start.y / res_;

  int end_row = origin_row_ - end.x / res_;
  int end_col = origin_col_ - end.y / res_;
  arrowedLine(plot_img_, Point(start_col, start_row), Point(end_col, end_row), color, size);

 }

void Plot::drawText(const std::vector<cv::Point2f>& point_all, const vector<std::string>& object_all, const double fontScale, const Scalar color, double size, bool refresh) {
  if (refresh) {
    clear();
  }
  cv::Point2f point;
  std::string objectStr;
  for (int i = 0; i < point_all.size(); i++) {
    cv::Point2f pt1 = point_all[i];
    objectStr = object_all[i];

    int pt1_row = origin_row_ - pt1.x / res_;
    int pt1_col = origin_col_ - pt1.y / res_;

    cv::putText(plot_img_, objectStr, cv::Point(pt1_col, max(10, pt1_row - 6)), cv::FONT_HERSHEY_SIMPLEX, fontScale, color, size, cv::LINE_8);
  }
}

// clear drawings
void Plot::clear() { plot_img_ = background_img_.clone(); }

//// clear drawings
// void Plot::initbg() { plot_img_ = background_img_.clone(); }
