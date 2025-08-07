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

#include "groundfloor_segmentation/Monitor.hpp"

#include <cmath>

namespace perception {
namespace monitor {

float calculateIncline(float deltaHeight, float deltaDepth)
{
  float incline = 0.f;
  if (std::isinf(deltaDepth))
  {
    incline = 0.f;
  }
  else if (std::isnan(deltaDepth))
  {
    if (deltaHeight < 1e-4)
    {
      incline = 0.f;
    }
    else
    {
      incline = 1000.f;
    }
  }
  else if (std::fabs(deltaHeight) < 1e-4)
  {
    incline = 0.f;
  }
  else if (deltaDepth < 1e-4)
  {
    if (deltaHeight < 0)
    {
      incline = -1000.f;
    }
    else
    {
      incline = 1000.f;
    }
  }
  else
  {
    incline = deltaHeight / deltaDepth;
  }
  return incline;
}

bool PerceptionMonitor::execute(Sensor &sensor)
{
  if ((sensor.mHeight > 0) && (sensor.mWidth > 0))
  {
    sensor.updateConfidenceData();
    // combine available probabilities and filter point cloud
    sensor.combine();

    return true;
  }

  return false;
}

bool Sensor::isCliff(const uint32_t rowIndex, const uint32_t colIndex, const float maxInclineVal, bool &runFirstCheck)
{
  bool isCliff = false;

  const uint32_t index = rowIndex * mWidth + colIndex;
  const float currentHeight = mHeightImage[index];
  const float currentDepth = mDepthImage[index];

  if (runFirstCheck)
  {
    runFirstCheck = false;
    // this is the first valid row of the image, i.e. the closest pixels to the robot
    // for this row, the incline could be missleading, if there is an immediate cliff
    // right in front of the robot
    // Therefore, we need to test it on assumption basis that ground floor is around 0

    float incline = calculateIncline(currentHeight, currentDepth);
    if (incline < (-1.f * maxInclineVal))
    {
      // the first pixel indicates a drop of more than the allowed angle --> cliff
      isCliff = true;
    }
  }

  // for pixels not in the bottom row, we can use the already calculated incline
  // however, there could be outliers, hence also check height difference of next and previous pixels

  // following code is just experimental, not for product-use
  // if (mInclineMatrix[index] < (-1.f * maxInclineVal))
  // {
  //   uint32_t k = 2;
  //   while (std::isnan(mHeightImage[(rowIndex - k) * mWidth + colIndex]) && (rowIndex >= k))
  //   {
  //     k++;
  //   }
  //   if (!std::isnan(mHeightImage[(rowIndex - k) * mWidth + colIndex]))
  //   {
  //     const float nextHeight = mHeightImage[(rowIndex - k) * mWidth + colIndex];
  //     if (std::fabs(nextHeight - currentHeight) > 0.02f)
  //     {
  //       isCliff = true;
  //     }
  //   }
  // }

  return isCliff;
}

uint32_t Sensor::getNumHighInlinePixels(const uint32_t rowIndex,
                                        const uint32_t colIndex,
                                        const uint32_t analysisSample,
                                        const float maxInclineVal) const
{
  // get number of pixels with incline outside the accepted range
  // this allows to become more robust against noise
  uint32_t numLowIncline = 0;
  uint32_t numHighIncline = 0;

  uint32_t k = 1;
  while (rowIndex > k && (numLowIncline + numHighIncline) < analysisSample)
  {
    const float nextIncline = std::fabs(mInclineMatrix[(rowIndex - k) * mWidth + colIndex]);
    if (nextIncline > 0. && !std::isnan(mHeightImage[(rowIndex - k) * mWidth + colIndex]))
    {
      if (nextIncline < maxInclineVal)
      {
        numLowIncline++;
      }
      else
      {
        numHighIncline++;
      }
    }
    k++;
  }

  return numHighIncline;
}

void Sensor::calculateInclineMatrix()
{
  std::fill(mInclineMatrix.begin(), mInclineMatrix.end(), 0);

  unsigned int cols = mWidth;
  unsigned int rows = mHeight;

  // Lookahead reduces the noise of the incline
  // But smoothes out edges of objects. So should be chosen carfully
  uint32_t lookAhead = mParameters.inclineLookAhead;

  for (uint32_t j = 0; j < cols; j++)
  {
    float lastHeight = 0.;
    float lastDepth = 0.;

    for (uint32_t i = rows - 1; i > lookAhead; i--)
    {
      const unsigned int index = i * cols + j;
      const float currentHeight = mHeightImage[index];
      const float currentDepth = mDepthImage[index];
      if (!std::isnan(currentHeight))
      {
        {
          uint32_t n = 0;
          bool validFound = false;

          while ((i > lookAhead + n) && !validFound)
          {
            const uint32_t lastIndex = (i - lookAhead - n) * cols + j;
            lastHeight = mHeightImage[lastIndex];
            lastDepth = mDepthImage[lastIndex];

            if (!std::isnan(lastHeight))
            {
              validFound = true;
            }
            n++;
          }

          if (!validFound)
          {
            lastHeight = 0.;
            lastDepth = 0.;
          }
        }

        float deltaHeight = lastHeight - currentHeight;
        float deltaDepth = lastDepth - currentDepth;
        float incline = 1000.f;
        if (deltaDepth > (-1.f * mParameters.overhangingObjectMinDistance))
        {
          incline = calculateIncline(deltaHeight, std::fabs(deltaDepth));
        }
        else
        {
          // this is an overhanging load / object
          // in this case, keep the incline at default value
        }

        mInclineMatrix[index] = incline;

        lastHeight = currentHeight;
        lastDepth = currentDepth;
      }
    }
  }
}

void Sensor::updateConfidenceData()
{
  mObstaclePoints.clear();
  mGroundFloorPoints.clear();

  for (std::size_t i = 0; i < mPointCloud.size(); ++i)
  {
    const auto &point = mPointCloud[i];
    mLabeledPointCloud[i].x = point.x;
    mLabeledPointCloud[i].y = point.y;
    mLabeledPointCloud[i].z = point.z;
    mLabeledPointCloud[i].label = PointLabel::UNKNOWN;
  }

  calculateInclineMatrix();

  calculateHeightProbability();
}

void Sensor::calculateHeightProbability()
{
  std::fill(mHeightConfidenceMatrix.begin(), mHeightConfidenceMatrix.end(), 0.f);
  std::fill(mOnGroundPlane.begin(), mOnGroundPlane.end(), false);

  // convert max_incline angle to value to avoid frequent atan2 calls
  float maxInclineVal = std::fabs(std::tan(mParameters.maxIncline * M_PI / 180.f));

  unsigned int cols = mWidth;
  unsigned int rows = mHeight;

  uint32_t numNanValues = 0u;

  uint32_t numNanValuesOnGP = 0u;
  uint32_t numValuesOnGP = 0u;

  for (uint32_t j = 0; j < cols; j++)
  {
    float surfaceHeightMax = 0;
    std::map<float, float, std::greater<>> surfaceHeights;
    bool on_gp = true;
    bool runFirstPixelCliffCheck = true;

    for (uint32_t i = rows - 1; i > 0; i--)
    {
      // take care of column vs. row-major order
      const uint32_t index = i * cols + j;

      const float currentHeight = mHeightImage[index];
      const float currentDistance = mDepthImage[index];

      // get estimated ground floor height
      float currentFloorHeight = surfaceHeightMax;
      auto iter = surfaceHeights.lower_bound(currentDistance);
      if (iter != surfaceHeights.end())
      {
        currentFloorHeight = iter->second;
      }

      if (on_gp)
      {
        numValuesOnGP++;
      }

      if (std::isnan(currentHeight))
      {
        numNanValues++;
        mLabeledPointCloud[index].label = PointLabel::UNDEFINED;
        if (on_gp)
        {
          numNanValuesOnGP++;
          mHeightConfidenceMatrix[index] = 0.f;
        }
        else
        {
          mHeightConfidenceMatrix[index] = 1.f;
        }
      }
      else if (!(currentHeight > -10 && currentHeight < 100))
      {
        mHeightConfidenceMatrix[index] = 0.f;
        mLabeledPointCloud[index].label = PointLabel::INVALID;
      }
      // Filter ego vehicle
      else if (currentDistance < mParameters.minDistanceToEgo)
      {
        mHeightConfidenceMatrix[index] = 0.f;
        mLabeledPointCloud[index].label = PointLabel::INVALID;
      }
      // Filter ceiling
      else if (currentHeight > mParameters.ceilingHeight + currentFloorHeight)
      {
        mHeightConfidenceMatrix[index] = 0.f;
        mLabeledPointCloud[index].label = PointLabel::ABOVE;
      }
      // Filter points that might be above robot
      else if (currentHeight > mParameters.robotHeightMax + currentFloorHeight)
      {
        mLabeledPointCloud[index].label = PointLabel::ABOVE;
        mHeightConfidenceMatrix[index]
          = std::max(std::min((mParameters.ceilingHeight + currentFloorHeight - currentHeight)
                                / (mParameters.ceilingHeight - mParameters.robotHeightMax),
                              1.0f),
                     0.0f);
      }
      else if (currentHeight > mParameters.maxSurfaceHeight + currentFloorHeight)
      {
        mHeightConfidenceMatrix[index] = 1;
        mLabeledPointCloud[index].label = PointLabel::OBSTACLE;
        on_gp = false;
      }
      else if (currentHeight > -10. && currentHeight < 100.)
      {
        float incline = std::fabs(mInclineMatrix[index]);
        bool cliff = isCliff(i, j, maxInclineVal, runFirstPixelCliffCheck);
        if (on_gp && (incline < maxInclineVal) && !cliff)
        {
          surfaceHeightMax = currentHeight;
          surfaceHeights[currentDistance] = currentHeight;
          mHeightConfidenceMatrix[index] = 0.f;
          mOnGroundPlane[index] = true;
        }
        else
        {
          const uint32_t analysisSample = 10;
          const uint32_t allowedHighInclinePixels = std::ceil(mParameters.acceptableInclineRatio * analysisSample);
          const uint32_t numHighIncline = getNumHighInlinePixels(i, j, analysisSample, maxInclineVal);

          if (on_gp)
          {
            // we arrive here if on_gp but the incline of current pixel is too big
            mOnGroundPlane[index] = true;
            surfaceHeights[currentDistance] = currentHeight;
            currentFloorHeight = currentHeight;
            surfaceHeightMax = currentHeight;
            if (numHighIncline < allowedHighInclinePixels)
            {
              if (cliff)
              {
                surfaceHeightMax = 100.f;
                currentFloorHeight = 100.f;
                surfaceHeights[currentDistance] = 100.f;
                on_gp = false;
                mOnGroundPlane[index] = false;
              }
              else
              {
                // this is supposedly an outlier, do nothing here
              }
            }
            else
            {
              if (mParameters.enhancedRobustness)
              {
                float maxDistance = mParameters.maxSurfaceHeight / maxInclineVal;
                float distance = 0.;
                float start_distance = currentDistance;
                uint32_t k = 1;
                while (distance < maxDistance && on_gp && i > k)
                {
                  float k_height = mHeightImage[(i - k) * cols + j];
                  if (!std::isnan(k_height))
                  {
                    if (std::fabs(surfaceHeightMax - k_height) > mParameters.maxSurfaceHeight)
                    {
                      on_gp = false;
                      // This is the last point of the GP.
                    }
                    distance = mDepthImage[(i - k) * cols + j] - start_distance;
                  }
                  k++;
                }
              }
              else
              {
                on_gp = false;
              }
            }
          }
          else if (mParameters.useExtendedGroundPlane)
          {
            // previous points were not on gp, let's check if we are back on gp
            // this is for points that are close to surfaceHightMax and have shallow incline
            uint32_t k = 1;
            while (std::isnan(mHeightImage[(i + k) * cols + j]) && (i + k < rows))
            {
              ++k;
            }

            if ((std::fabs(surfaceHeightMax - currentHeight) < std::min(0.1f, mParameters.maxSurfaceHeight))
                && (mHeightImage[(i + k) * cols + j] > (currentHeight + 0.02f))
                && ((incline < maxInclineVal) || (numHighIncline < allowedHighInclinePixels)))
            {
              on_gp = true;
              mOnGroundPlane[index] = true;
            }
          }
        }

        if (!on_gp)
        {
          mHeightConfidenceMatrix[index]
            = std::min(1.f, (std::fabs(currentFloorHeight - currentHeight) / std::fabs(mParameters.maxSurfaceHeight)));
        }
      }
      else
      {
        // This should not happen --> Set Probabilty to 1 for safety reasons
        mHeightConfidenceMatrix[index] = 1.;
      }
    }
  }

  // row with i=0 was excluded before as it does not
  // contain info useful for height confidence estimation
  for (uint32_t j = 0; j < cols; j++)
  {
    if (std::isnan(mHeightImage[j]))
    {
      mLabeledPointCloud[j].label = PointLabel::UNDEFINED;
      numNanValues++;
    }
    else
    {
      mLabeledPointCloud[j].label = PointLabel::INVALID;
    }
  }
}

void Sensor::combine()
{
  unsigned int cols = mWidth;
  unsigned int rows = mHeight;

  for (uint32_t i = 0; i < rows; i++)
  {
    for (uint32_t j = 0; j < cols; j++)
    {
      unsigned int index = i * cols + j;

      if (index >= mPointCloud.size() || std::isnan(mPointCloud[index].x))
      {
        // the index might be invalid, skip this pixel
        continue;
      }

      if (mHeightConfidenceMatrix[index] > 0.9)
      {
        mObstaclePoints.push_back(mPointCloud[index]);
        mLabeledPointCloud[index].label = PointLabel::OBSTACLE;
      }
      else if (mHeightConfidenceMatrix[index] > 0)
      {
        mLabeledPointCloud[index].label = PointLabel::ELEVATED;
      }
      else if (mOnGroundPlane[index])
      {
        mGroundFloorPoints.push_back(mPointCloud[index]);
        mLabeledPointCloud[index].label = PointLabel::GROUND;
      }
    }
  }
}

} // namespace monitor
} // namespace perception