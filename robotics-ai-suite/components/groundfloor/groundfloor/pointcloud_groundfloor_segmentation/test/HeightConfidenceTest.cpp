// Copyright (C) 2022-2023 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <numeric>
#include <opencv2/opencv.hpp>

#include "groundfloor_segmentation/Monitor.hpp"

namespace perception
{
namespace monitor
{

//
// Test that the height confidence calculation doesn't fail or throw an exception
// Test data is not meaningful, as all pixels in input images have the same value
//
TEST(HeightConfidenceTest, SmokeTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 0; i < 5; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }

  for (int i = 5; i < 25; i++) {
    // Expect the last row to not be reinitalised in C++
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }

  // Test solid image
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 5);
  fill(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 5);
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), 0);

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 0; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }
}

//
// Test behavior if a tower is visible in the image, i.e. same depth, different heights
//
TEST(HeightConfidenceTest, TowerTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  // Test tower
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 8.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  sensor.mHeightImage[3] = 3.0;
  sensor.mHeightImage[8] = 2.0;
  sensor.mHeightImage[13] = 1.0;

  sensor.mDepthImage[3] = 8.0;
  sensor.mDepthImage[8] = 8.0;
  sensor.mDepthImage[13] = 8.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 5; i < 25; i++) {
    if (i == 8 || i == 13) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior if a ramp is visible in the image
//
TEST(HeightConfidenceTest, RampTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  // Test Ramp
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 8.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  sensor.mHeightImage[3] = 3.0;
  sensor.mHeightImage[8] = 2.0;
  sensor.mHeightImage[13] = 1.0;

  sensor.mDepthImage[3] = 10.0;
  sensor.mDepthImage[8] = 9.0;
  sensor.mDepthImage[13] = 8.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 5; i < 25; i++) {
    if (i == 8 || i == 13) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }

  // Test Flat Ramp
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 8.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  sensor.mHeightImage[3] = 1.5;
  sensor.mHeightImage[8] = 1.0;
  sensor.mHeightImage[13] = 0.5;

  sensor.mDepthImage[3] = 20.0;
  sensor.mDepthImage[8] = 15.0;
  sensor.mDepthImage[13] = 10.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 5; i < 25; i++) {
    if (i == 8 || i == 13) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior if floor shows incline
//
TEST(HeightConfidenceTest, InclinedFloorTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(1, 10);
  sensor.mParameters = params;

  // Test inclined floor
  iota(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  reverse(sensor.mHeightImage.begin(), sensor.mHeightImage.end());

  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 0.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());

  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  for (uint32_t i = 0; i < sensor.mHeightImage.size(); i++) {
    sensor.mHeightImage[i] *= 0.1f;
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (uint32_t i = 1; i < sensor.mHeightImage.size(); i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }
}

//
// Test behavior if floor shows decline
//
TEST(HeightConfidenceTest, DeclinedFloorTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(1, 10);
  sensor.mParameters = params;

  // Test declined floor
  iota(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  reverse(sensor.mHeightImage.begin(), sensor.mHeightImage.end());

  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 0.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());

  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  for (uint32_t i = 0; i < sensor.mHeightImage.size(); i++) {
    sensor.mHeightImage[i] *= -0.1f;
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (uint32_t i = 1; i < sensor.mHeightImage.size(); i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }
}

//
// Test behavior if cliff is in front of robot
//
TEST(HeightConfidenceTest, CliffTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(1, 10);
  sensor.mParameters = params;

  // Fill test data with cliff in first pixel
  std::fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), -1.0);

  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 0.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());

  for (uint32_t i = 0; i < sensor.mDepthImage.size(); i++) {
    sensor.mDepthImage[i] = sensor.mDepthImage[i] * 0.1 + params.minDistanceToEgo + 0.01f;
  }

  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (uint32_t i = 1; i < sensor.mHeightImage.size(); i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
  }

  // // Fill test data with cliff in second pixel
  // sensor.mHeightImage[9] = 0;
  // fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  // ASSERT_NO_THROW(sensor.updateConfidenceData());
  // for (int i = 1; i < sensor.mHeightImage.size() ; i++) {
  //   EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
  // }

  // // Fill test data with cliff in third pixel
  // sensor.mHeightImage[8] = 0;
  // fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  // ASSERT_NO_THROW(sensor.updateConfidenceData());
  // for (int i = 1; i < sensor.mHeightImage.size() ; i++) {
  //   EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
  // }

  // // Fill test data with cliff in 8th pixel
  // sensor.mHeightImage[7] = 0;
  // sensor.mHeightImage[6] = 0;
  // sensor.mHeightImage[5] = 0;
  // fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  // ASSERT_NO_THROW(sensor.updateConfidenceData());
  // for (int i = 1; i < sensor.mHeightImage.size() ; i++) {
  //   if (i < 7) {
  //     EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
  //   } else {
  //     EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  //   }
  // }
}

//
// Test behavior if floor shows incline and there is a tower present
//
TEST(HeightConfidenceTest, DeclinedFloorTowerTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  for (int x = 0; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = (x - 5.0) / 10;
    }
  }

  sensor.mHeightImage[3] = 0.3;
  sensor.mHeightImage[8] = 0.15;
  sensor.mHeightImage[13] = 0.08;

  for (int x = 0; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mDepthImage[x * 5 + y] = (5 - x) * 10;
    }
  }

  sensor.mDepthImage[3] = 14.0;
  sensor.mDepthImage[8] = 14.0;
  sensor.mDepthImage[13] = 14.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    if (i == 8 || i == 13) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior if floor shows decline with a ramp following
//
TEST(HeightConfidenceTest, DeclinedFloorRampTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  for (int x = 0; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = (x - 5.0) / 10;
    }
  }

  sensor.mHeightImage[3] = 0.3;
  sensor.mHeightImage[8] = 0.15;
  sensor.mHeightImage[13] = 0.08;

  for (int x = 0; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mDepthImage[x * 5 + y] = (5 - x) * 10;
    }
  }

  sensor.mDepthImage[3] = 34.0;
  sensor.mDepthImage[8] = 24.0;
  sensor.mDepthImage[13] = 14.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    if (i == 8 || i == 13) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior if there is an overhanging load, i.e. distance first increases, then decreases for increasing height
//
TEST(HeightConfidenceTest, OverhangTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  for (int x = 0; x < 2; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = 2.0 - x;
      sensor.mDepthImage[x * 5 + y] = 50.0;
    }
  }

  sensor.mHeightImage[2] = 1.2;
  sensor.mHeightImage[7] = 0.8;
  sensor.mHeightImage[12] = 0.4;

  for (int x = 2; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mDepthImage[x * 5 + y] = (5 - x) * 10;
    }
  }

  sensor.mDepthImage[2] = 15.0;
  sensor.mDepthImage[7] = 15.0;
  sensor.mDepthImage[12] = 15.0;

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    if (i <= 9 || i == 12) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior if there is an overhanging load, i.e. distance first increases, then decreases for increasing height
// Here: surface is declining
//
TEST(HeightConfidenceTest, OverhangTestWithDeclineSurface)
{
  ConfigParameters params;
  params.minDistanceToEgo = 0.001f;
  params.robotHeightMax = 0.3f;
  params.maxSurfaceHeight = 0.0f;

  Sensor sensor;
  sensor.setResolution(1, 30);
  sensor.mParameters = params;

  for (std::size_t i = 0; i < sensor.mHeightImage.size(); ++i) {
    sensor.mDepthImage[i] = 3.3f - i * 0.1f;
    sensor.mHeightImage[i] = -0.3f + i * 0.01f;
  }

  for (std::size_t i = 0; i < 10; ++i) {
    sensor.mDepthImage[i] = 0.4f;
    sensor.mHeightImage[i] = 0.31f - i * 0.01f;
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (std::size_t i = 10; i < sensor.mHeightImage.size(); ++i) {
    EXPECT_FLOAT_EQ(sensor.mHeightConfidenceMatrix[i], 0.f);
  }

  for (std::size_t i = 3; i < 10; ++i) {
    EXPECT_FLOAT_EQ(sensor.mHeightConfidenceMatrix[i], 1.f);
    EXPECT_EQ(sensor.mLabeledPointCloud[i].label, 5);
  }
}

//
// Test behavior if there is slot present in the environment (i.e. narrow gap between two obstacles)
//
TEST(HeightConfidenceTest, SlitTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  for (int x = 0; x < 3; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = 3.0 - x;
      sensor.mDepthImage[x * 5 + y] = 15.0;
    }
  }

  for (int x = 3; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mDepthImage[x * 5 + y] = (5 - x) * 10;
    }
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    if (i <= 14) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test behavior for a ceiling, which should be removed
//
TEST(HeightConfidenceTest, CeilingTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  for (int x = 0; x < 3; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = 20.0;
      sensor.mDepthImage[x * 5 + y] = x * 10;
    }
  }

  for (int x = 3; x < 5; x++) {
    for (int y = 0; y < 5; y++) {
      sensor.mHeightImage[x * 5 + y] = 0.0;
      sensor.mDepthImage[x * 5 + y] = (5 - x) * 10;
    }
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }
}

//
// Test behavior for some corner cases
//
TEST(HeightConfidenceTest, CornerCases)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(5, 5);
  sensor.mParameters = params;

  // Test empty image
  sensor.mDepthImage.resize(25, std::numeric_limits<float>::infinity());
  sensor.mDepthImage.resize(25, std::numeric_limits<float>::infinity());
  sensor.mHeightConfidenceMatrix.resize(25, 15);

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }

  // Test NaN
  fill(
    sensor.mHeightImage.begin(), sensor.mHeightImage.end(),
    std::numeric_limits<float>::quiet_NaN());
  fill(
    sensor.mDepthImage.begin(), sensor.mDepthImage.end(), std::numeric_limits<float>::quiet_NaN());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }

  // Test partial NaN
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0);
  fill(
    sensor.mHeightImage.begin() + 15, sensor.mHeightImage.end(),
    std::numeric_limits<float>::quiet_NaN());
  fill(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 0);
  fill(
    sensor.mDepthImage.begin() + 8, sensor.mDepthImage.end() - 4,
    std::numeric_limits<float>::quiet_NaN());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }

  // Test mixed NaN / Infiinity
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0);
  fill(
    sensor.mHeightImage.begin() + 15, sensor.mHeightImage.end() - 4,
    std::numeric_limits<float>::quiet_NaN());
  fill(
    sensor.mHeightImage.end() - 4, sensor.mHeightImage.end(),
    std::numeric_limits<float>::infinity());
  fill(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 0);
  fill(
    sensor.mDepthImage.begin() + 8, sensor.mDepthImage.end() - 6,
    std::numeric_limits<float>::infinity());
  fill(
    sensor.mDepthImage.end() - 5, sensor.mDepthImage.end(),
    std::numeric_limits<float>::quiet_NaN());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  ASSERT_NO_THROW(sensor.updateConfidenceData());
  for (int i = 5; i < 25; i++) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
  }
}

//
// Test behavior for objects with minimum height
//
TEST(HeightConfidenceTest, MinHeightTest)
{
  ConfigParameters params;

  Sensor sensor;
  sensor.setResolution(1, 25);
  sensor.mParameters = params;

  // Test tower
  fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
  iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 1.0);
  reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  sensor.mDepthImage[11] = sensor.mDepthImage[12];
  sensor.mHeightImage[11] = sensor.mHeightImage[12] + 0.05;
  sensor.mDepthImage[10] = sensor.mDepthImage[11];
  sensor.mHeightImage[10] = sensor.mHeightImage[12] + 0.1;
  sensor.mDepthImage[9] = sensor.mDepthImage[11];
  sensor.mHeightImage[9] = sensor.mHeightImage[12] + 0.11;

  for (int i = 9; i >= 0; i--) {
    sensor.mDepthImage[i] = sensor.mDepthImage[11];
    sensor.mHeightImage[i] = sensor.mHeightImage[i + 1] + (0.1);
  }

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 24; i > 5; i--) {
    if (i <= 10) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    } else if (i == 11) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0.5);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    }
  }
}

//
// Test if pitch is properly detected and handled by heightconfidence
//
TEST(HeightConfidenceTest, RotationTest)
{
  ConfigParameters params;
  params.evaluateCalibration = true;
  params.minDistanceToEgo = 0.f;

  float angleDeg = params.maxIncline - 1;
  for (int l = 0; l < 29; l++) {
    Sensor sensor;

    sensor.mParameters = params;

    sensor.setResolution(1, 250);

    // Test tower
    fill(sensor.mHeightImage.begin(), sensor.mHeightImage.end(), 0.0);
    iota(sensor.mDepthImage.begin(), sensor.mDepthImage.end(), 1.);
    reverse(sensor.mDepthImage.begin(), sensor.mDepthImage.end());
    fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

    for (auto l = 0; l < 250; l++) {
      sensor.mDepthImage[l] = sensor.mDepthImage[l] * 0.1;
    }

    float mRealDistanceToObstacle = sensor.mDepthImage[11];

    sensor.mDepthImage[10] = sensor.mDepthImage[11];
    sensor.mHeightImage[10] = sensor.mHeightImage[12] + 0.101;

    for (int i = 9; i >= 0; i--) {
      sensor.mDepthImage[i] = sensor.mDepthImage[11];
      sensor.mHeightImage[i] = sensor.mHeightImage[i + 1] + (0.1);
    }

    // We pitch the camera (depth - x, height - z) --> this means we also have
    // to invert the sign of the angle

    float angleRad = angleDeg / 180. * M_PI * -1.f;
    for (int i = 249; i > 0; i--) {
      float x = sensor.mDepthImage[i];
      float z = sensor.mHeightImage[i];
      // printf(
      //   "%i %f %f (%f %f) ",i, angleDeg, angleRad, sensor.mDepthImage[i],sensor.mHeightImage[i]);
      sensor.mDepthImage[i] = cos(angleRad) * x + sin(angleRad) * z;
      sensor.mHeightImage[i] = -1. * sin(angleRad) * x + cos(angleRad) * z;

      // printf("(%f %f)\n",sensor.mDepthImage[i],sensor.mHeightImage[i]);
    }

    ASSERT_NO_THROW(sensor.updateConfidenceData());

    float minDistanceToObstacle = 100.;
    for (int i = 249; i > 5; i--) {
      if (sensor.mHeightConfidenceMatrix[i] > 0.9) {
        minDistanceToObstacle = std::min(sensor.mDepthImage[i], minDistanceToObstacle);
      }
    }

    EXPECT_LE(minDistanceToObstacle, mRealDistanceToObstacle);

    angleDeg = angleDeg - 1.;
  }
}

//
// Test behavior if there is a obstacle in front of a wall, which has no visible connection to ground floor
//
TEST(HeightConfidenceTest, FlyingObstacleInFrontOfWall)
{
  ConfigParameters params;
  params.robotHeightMax = 100.f;
  params.ceilingHeight = 100.f;

  Sensor sensor;
  sensor.setResolution(1, 20);
  sensor.mParameters = params;

  sensor.mHeightImage = {10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  sensor.mDepthImage = {10, 10, 10, 10, 5, 5, 5, 5, 10, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0};
  fill(sensor.mHeightConfidenceMatrix.begin(), sensor.mHeightConfidenceMatrix.end(), -1);

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  for (int i = 19; i > 0; i--) {
    if (i >= 10) {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 0);
    } else {
      EXPECT_EQ(sensor.mHeightConfidenceMatrix[i], 1);
    }
  }
}

//
// Test behavior for real data recordings
//
TEST(HeightConfidenceTest, RealDataTest)
{
  ConfigParameters params;
  params.maxSurfaceHeight = 0.05;

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

  ASSERT_NO_THROW(sensor.updateConfidenceData());

  // overhanging obstacle
  std::size_t j = 138;
  for (std::size_t i = rows - 1; i > 99; i--) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i * cols + j], 0.f);
  }
  for (std::size_t i = 99; i > 96; i--) {
    EXPECT_GE(sensor.mHeightConfidenceMatrix[i * cols + j], 0.1f);
  }
  for (std::size_t i = 96; i > 0; i--) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i * cols + j], 1.f);
  }

  // small obstacle on ground
  j = 174;
  for (std::size_t i = rows - 1; i > 119; i--) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i * cols + j], 0.f);
  }
  for (std::size_t i = 119; i > 95; i--) {
    EXPECT_GE(sensor.mHeightConfidenceMatrix[i * cols + j], 0.001f);
  }
  for (std::size_t i = 95; i > 0; i--) {
    EXPECT_EQ(sensor.mHeightConfidenceMatrix[i * cols + j], 1.f);
  }
}

}  // namespace monitor
}  // namespace perception
