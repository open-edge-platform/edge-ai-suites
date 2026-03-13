// Copyright (c) 2022-2023 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "fuzztest/fuzztest.h"

#include <gtest/gtest.h>

#include <numeric>
#include <opencv2/opencv.hpp>

#include "groundfloor_segmentation/Monitor.hpp"

namespace perception
{
namespace monitor
{

void HeightConfidenceTestFuzzed(float incline, float surfaceHeight, float robotHeight)
{
  ConfigParameters params;
  params.robotHeightMax = robotHeight;
  params.maxSurfaceHeight = surfaceHeight;
  params.maxIncline = incline;

  Sensor sensor;
  sensor.setResolution(10, 10);
  sensor.mParameters = params;

  ASSERT_NO_THROW(sensor.updateConfidenceData());
}

void MonitorTestFuzzedWithRealData(float incline, float surfaceHeight, float robotHeight)
{
  ConfigParameters params;
  params.robotHeightMax = robotHeight;
  params.maxSurfaceHeight = surfaceHeight;
  params.maxIncline = incline;
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

  ASSERT_NO_THROW(perceptionMonitor->execute(sensor));
}

void MonitorTestFuzzed(
  float incline, float surfaceHeight, float robotHeight, std::vector<float> heightData,
  std::vector<float> depthData)
{
  ConfigParameters params;
  params.robotHeightMax = robotHeight;
  params.maxSurfaceHeight = surfaceHeight;
  params.maxIncline = incline;
  auto perceptionMonitor = std::make_shared<PerceptionMonitor>();

  std::size_t cols = 1;
  std::size_t rows = std::min(heightData.size(), depthData.size());

  Sensor sensor;
  sensor.setResolution(cols, rows);
  sensor.mParameters = params;
  sensor.mDepthImage = depthData;
  sensor.mHeightImage = heightData;
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  if (rows > 0) {
    EXPECT_TRUE(perceptionMonitor->execute(sensor));
  } else {
    EXPECT_FALSE(perceptionMonitor->execute(sensor));
  }
}

FUZZ_TEST(FuzzTest, HeightConfidenceTestFuzzed);
FUZZ_TEST(FuzzTest, MonitorTestFuzzedWithRealData);
FUZZ_TEST(FuzzTest, MonitorTestFuzzed);

}  // namespace monitor
}  // namespace perception
