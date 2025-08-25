// SPDX-License-Identifier: Apache-2.0
// ----------------- BEGIN LICENSE BLOCK ---------------------------------
//
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.
//
// ----------------- END LICENSE BLOCK -----------------------------------

#pragma once

#include <cstdint>
#include <memory>
#include <pcl/common/transforms.h>

namespace perception {
namespace monitor {

struct ConfigParameters
{
  float minDistanceToEgo{0.2f};
  float ceilingHeight{3.0f};
  float robotHeightMax{2.0f};
  float maxSurfaceHeight{0.1f};
  float maxIncline{15.0f};
  float minGapLength{0.15f};
  float maxGapLength{0.5f};
  float overhangingObjectMinDistance{0.05f};
  bool enhancedRobustness{true};
  uint32_t inclineLookAhead{5u};
  float acceptableInclineRatio{0.25f};
  bool evaluateCalibration{false};
  bool useExtendedGroundPlane{false};
};

enum PointLabel : uint32_t
{
  UNKNOWN,   // default value
  UNDEFINED, // NAN pixel
  INVALID,   // measurement is discareded, i.e. outside of vertical FOV or too close
  GROUND,    // ground floor pixel
  ELEVATED,  // not on ground floor but not yet part of a true obstacle
  OBSTACLE,  // obstacle, which the robot should not collide with
  ABOVE,     // pixel above robot height
};

class Sensor
{
public:
  Sensor() = default;

  uint32_t mHeight{0u};
  uint32_t mWidth{0u};

  std::vector<float> mDepthImage;
  std::vector<float> mHeightImage;
  std::vector<float> mHeightConfidenceMatrix;
  std::vector<float> mInclineMatrix;
  std::vector<bool> mOnGroundPlane;
  pcl::PointCloud<pcl::PointXYZ> mPointCloud;
  pcl::PointCloud<pcl::PointXYZ> mObstaclePoints;
  pcl::PointCloud<pcl::PointXYZ> mGroundFloorPoints;
  pcl::PointCloud<pcl::PointXYZL> mLabeledPointCloud;

  ConfigParameters mParameters;

  // update heightConfidence for current sensor data
  void updateConfidenceData();

  // filter point cloud based on current heightConfidence
  void combine();

  void setResolution(uint32_t newWidth, uint32_t newHeight)
  {
    mHeight = newHeight;
    mWidth = newWidth;
    mDepthImage.resize(mHeight * mWidth);
    mHeightImage.resize(mHeight * mWidth);
    mHeightConfidenceMatrix.resize(mHeight * mWidth);
    mInclineMatrix.resize(mHeight * mWidth);
    mOnGroundPlane.resize(mHeight * mWidth);
    mDepthImage.resize(mHeight * mWidth);

    mPointCloud = pcl::PointCloud<pcl::PointXYZ>(mWidth, mHeight);
    mObstaclePoints = pcl::PointCloud<pcl::PointXYZ>(mWidth, mHeight);
    mGroundFloorPoints = pcl::PointCloud<pcl::PointXYZ>(mWidth, mHeight);
    mLabeledPointCloud = pcl::PointCloud<pcl::PointXYZL>(mWidth, mHeight);
  }

private:
  void calculateHeightProbability();
  void calculateInclineMatrix();
  uint32_t getNumHighInlinePixels(const uint32_t rowIndex,
                                  const uint32_t colIndex,
                                  const uint32_t analysisSample,
                                  const float maxInclineVal) const;
  bool isCliff(const uint32_t rowIndex, const uint32_t colIndex, const float maxInclineVal, bool &runFirstCheck);
};

class PerceptionMonitor
{
public:
  PerceptionMonitor() = default;

  bool execute(Sensor &sensor);
};

} // namespace monitor
} // namespace perception
