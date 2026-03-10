// Copyright (C) 2022-2023 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>
#include <pcl/common/transforms.h>

#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <opencv2/opencv.hpp>
#include <string>

#include "groundfloor_segmentation/Monitor.hpp"

namespace perception
{
namespace monitor
{

bool compareXYZPoints(const pcl::PointXYZ & p1, const pcl::PointXYZ & p2)
{
  if (p1.x != p2.x) {
    return p1.x < p2.x;
  }

  if (p1.y != p2.y) {
    return p1.y < p2.y;
  }

  return p1.z < p2.z;
}

template <class T>
void readFromFile(const std::string & file, std::vector<T> & output)
{
  std::ifstream is(file);
  std::istream_iterator<T> start(is), end;
  std::vector<T> readVector(start, end);
  output = readVector;
}

void readPointCloudFile(const std::string & file, pcl::PointCloud<pcl::PointXYZ> & output)
{
  std::vector<std::string> lines;
  readFromFile(file, lines);

  for (std::size_t i = 0; i < lines.size(); ++i) {
    std::stringstream ss(lines[i]);
    std::string tmp;
    std::vector<float> coords;
    while (getline(ss, tmp, ',')) {
      float number = std::stof(tmp);
      coords.push_back(number);
    }
    pcl::PointXYZ point(coords[0], coords[1], coords[2]);
    output.push_back(point);
  }
}

TEST(MonitorTest, ClearTest)
{
  ConfigParameters monitorParams;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  Sensor sensor;
  sensor.setResolution(5, 5);

  sensor.mPointCloud.clear();
  sensor.mPointCloud.push_back(pcl::PointXYZ(0, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(0, 0, 1));
  sensor.mPointCloud.push_back(pcl::PointXYZ(0, 0, 2));
  sensor.mPointCloud.push_back(pcl::PointXYZ(0, 0, 3));

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));
}

TEST(MonitorTest, ObjectTest)
{
  ConfigParameters monitorParams;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  Sensor sensor;
  sensor.setResolution(4, 4);

  sensor.mHeightImage = {0, 3, 3, 0, 0, 2, 2, 0, 0, 1, 1, 0, 0, 0, 0, 0};
  sensor.mDepthImage = {5, 2, 2, 5, 4, 2, 2, 4, 3, 2, 2, 3, 2, 2, 2, 2};

  // Row 1
  sensor.mPointCloud.clear();
  sensor.mPointCloud.push_back(pcl::PointXYZ(5, -2, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -1, 3));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 0, 3));
  sensor.mPointCloud.push_back(pcl::PointXYZ(5, 1, 0));
  // Row 2
  sensor.mPointCloud.push_back(pcl::PointXYZ(4, -2, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -1, 2));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 0, 2));
  sensor.mPointCloud.push_back(pcl::PointXYZ(4, 1, 0));
  // Row 3
  sensor.mPointCloud.push_back(pcl::PointXYZ(3, -2, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -1, 1));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 0, 1));
  sensor.mPointCloud.push_back(pcl::PointXYZ(3, 1, 0));
  // Row 4
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -2, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -1, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 1, 0));

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));

  EXPECT_EQ(sensor.mObstaclePoints.size(), 4);

  sort(sensor.mObstaclePoints.begin(), sensor.mObstaclePoints.end(), compareXYZPoints);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].y, -1);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].z, 1);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].y, -1);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].z, 2);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].y, 0);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].z, 1);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].y, 0);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].z, 2);
}

TEST(MonitorTest, MultiObjectTest)
{
  ConfigParameters monitorParams;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  Sensor sensor;
  sensor.setResolution(4, 4);

  sensor.mHeightImage = {3, 0, 0, 3, 2, 0, 0, 2, 1, 0, 0, 1, 0, 0, 0, 0};
  sensor.mDepthImage = {2, 5, 5, 2, 2, 4, 4, 2, 2, 3, 3, 2, 2, 2, 2, 2};

  // Row 1
  sensor.mPointCloud.clear();
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -2, 3));
  sensor.mPointCloud.push_back(pcl::PointXYZ(5, -1, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(5, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 1, 3));
  // Row 2
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -2, 2));
  sensor.mPointCloud.push_back(pcl::PointXYZ(4, -1, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(4, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 1, 2));
  // Row 3
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -2, 1));
  sensor.mPointCloud.push_back(pcl::PointXYZ(3, -1, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(3, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 1, 1));
  // Row 4
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -2, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, -1, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 0, 0));
  sensor.mPointCloud.push_back(pcl::PointXYZ(2, 1, 0));

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));

  EXPECT_EQ(sensor.mObstaclePoints.size(), 4);
  std::sort(sensor.mObstaclePoints.begin(), sensor.mObstaclePoints.end(), compareXYZPoints);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].y, -2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[0].z, 1);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].y, -2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[1].z, 2);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].y, 1);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[2].z, 1);

  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].x, 2);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].y, 1);
  EXPECT_FLOAT_EQ(sensor.mObstaclePoints[3].z, 2);
}

TEST(MonitorTest, DISABLED_EndToEndTest)
{
  Sensor sensor;
  sensor.setResolution(300, 600);

  readFromFile("./data/depth_matrix.txt", sensor.mDepthImage);
  readFromFile("./data/height_matrix.txt", sensor.mHeightImage);
  readPointCloudFile("./data/point_cloud.txt", sensor.mPointCloud);

  ConfigParameters monitorParams;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));

  // Make sure a minimum amount of filtered points is returned form the passed image
  EXPECT_GE(sensor.mObstaclePoints.size(), 85000);
}

TEST(MonitorTest, RealDataTest)
{
  ConfigParameters params;
  params.maxSurfaceHeight = 0.05;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  cv::FileStorage fs;
  fs.open("data/height_image.yml", cv::FileStorage::READ);
  cv::Mat heightImage;
  fs["heightMat"] >> heightImage;
  fs.release();

  fs.open("data/depth_image.yml", cv::FileStorage::READ);
  cv::Mat depthImage;
  fs["depthMat"] >> depthImage;
  fs.release();

  const std::size_t cols = 320;
  const std::size_t rows = 180;

  ASSERT_EQ(heightImage.total(), cols * rows);
  ASSERT_EQ(depthImage.total(), cols * rows);

  Sensor sensor;
  sensor.setResolution(cols, rows);
  sensor.mParameters = params;
  sensor.mDepthImage = depthImage;
  sensor.mHeightImage = heightImage;
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  for (std::size_t i = 0; i < sensor.mHeightImage.size(); ++i) {
    if (std::isnan(sensor.mHeightImage[i])) {
      sensor.mPointCloud[i] = pcl::PointXYZ(
        std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::quiet_NaN());
    }
  }

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));

  uint32_t numUnknown = 0;
  uint32_t numGround = 0;
  uint32_t numElev = 0;
  uint32_t numObstacle = 0;
  uint32_t numAbove = 0;
  uint32_t numUndefined = 0;
  uint32_t numInvalid = 0;

  for (size_t j = 0; j < cols; j++) {
    for (int i = rows - 1; i >= 0; i--) {
      const unsigned int index = i * cols + j;
      switch (sensor.mLabeledPointCloud[index].label) {
        case PointLabel::UNKNOWN:
          numUnknown++;
          break;
        case PointLabel::GROUND:
          numGround++;
          break;
        case PointLabel::ELEVATED:
          numElev++;
          break;
        case PointLabel::OBSTACLE:
          numObstacle++;
          break;
        case PointLabel::ABOVE:
          numAbove++;
          break;
        case PointLabel::UNDEFINED:
          numUndefined++;
          break;
        case PointLabel::INVALID:
          numInvalid++;
          break;
      }
    }
  }

  ASSERT_EQ(cols * rows, 57600);
  EXPECT_EQ(numUnknown, 0);
  EXPECT_EQ(numGround, 20175);
  EXPECT_EQ(numElev, 2025);
  EXPECT_EQ(numObstacle, 28171);
  EXPECT_EQ(numUndefined, 7229);
  EXPECT_EQ(numInvalid, 0);
  EXPECT_EQ(numAbove, 0);
  EXPECT_EQ(
    numInvalid + numAbove + numUndefined + numObstacle + numElev + numGround + numUnknown,
    cols * rows);
}

}  // namespace monitor
}  // namespace perception
