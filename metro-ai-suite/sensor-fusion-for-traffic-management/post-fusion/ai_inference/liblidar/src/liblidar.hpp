/*
 * Copyright 2018-2019 Autoware Foundation. All rights reserved.
 * Copyright (c) 2019-2021 Intel Corporation (oneAPI modifications)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef LIBLIDAR_H
#define LIBLIDAR_H

#include <memory>
#include <vector>
#include <string>
#include <cmath>


namespace pointpillars {


/**
 * 3D-Object representation
 */
struct ObjectDetection
{
    ObjectDetection() : x(0.f), y(0.f), z(0.f), length(1.f), width(1.f), height(1.f), yaw(1.f), class_id(0), likelihood(1.f) {}

    ObjectDetection(float _x, float _y, float _z, float _l, float _w, float _h, float _yaw, int _class_id, float _likelihood)
        : x(_x), y(_y), z(_z), length(_l), width(_w), height(_h), yaw(_yaw), class_id(_class_id), likelihood(_likelihood)
    {
    }

    float x;
    float y;
    float z;
    float length;
    float width;
    float height;
    float yaw;
    int class_id;
    float likelihood;

    std::vector<float> class_probabilities;
};

/**
 * Anchor representation
 */
struct Anchor
{
    /**
     * @brief Constructor
     * @param[in] _x Size along x
     * @param[in] _y Size along y
     * @param[in] _z Size along z
     */
    Anchor(float _x, float _y, float _z) : x(_x), y(_y), z(_z), dz(0.){};

    /**
     * @brief Constructor
     * @param[in] _x Size along x
     * @param[in] _y Size along y
     * @param[in] _z Size along z
     * @param[in] _dz Position in z
     */
    Anchor(float _x, float _y, float _z, float _dz) : x(_x), y(_y), z(_z), dz(_dz){};

    float x{1.f};
    float y{1.f};
    float z{1.f};
    float dz{0.f};
};

struct AnchorGridConfig
{
    float min_x_range{0.0f};  // defines the area covered
    float max_x_range{1.0f};  // defines the area covered
    float min_y_range{0.0f};  // defines the area covered
    float max_y_range{1.0f};  // defines the area covered
    float min_z_range{0.0f};  // defines the area covered
    float max_z_range{1.0f};  // defines the area covered

    float x_stride{0.01f};  // spacing between anchors along x
    float y_stride{0.01f};  // spacing between anchors along y

    std::vector<Anchor> anchors = {Anchor(1.0f, 2.0f, 1.5f)};
    std::vector<float> rotations = {0.f, M_PI_2};  // The set of rotations to in which the anchors should be generated
};

struct PointPillarsConfig
{
    std::string pfe_model_file{"pfe"};
    std::string rpn_model_file{"rpn"};
    float min_x_range{0.f};      // defines the area covered by the algorithm
    float max_x_range{69.12f};   // defines the area covered by the algorithm
    float min_y_range{-39.68f};  // defines the area covered by the algorithm
    float max_y_range{39.68f};   // defines the area covered by the algorithm
    float min_z_range{-3.0f};    // defines the area covered by the algorithm
    float max_z_range{1.0f};     // defines the area covered by the algorithm
    float rpn_scale{0.5f};       // The scaling factor that the RPN is applying = 1 / (final convolution stride)
    float pillar_x_size{0.16f};  // pillar voxelization size along X
    float pillar_y_size{0.16f};  // pillar voxelization size along Y
    float pillar_z_size{4.0f};   // pillar voxelization size along Z
    float x_stride{0.32f};       // spacing between pillars along x
    float y_stride{0.32f};       // spacing between pillars along y
    std::size_t max_num_pillars{12000};
    std::size_t num_classes{1};
    std::vector<Anchor> anchors = {Anchor(1.6f, 3.9f, 1.56f)};
    std::vector<std::string> classes = {"Car"};
    std::size_t max_num_points_per_pillar{100};
    std::size_t pillar_features{64};
    std::size_t grid_x_size{432};  // (max_x_range - min_x_range) / pillar_x_size
    std::size_t grid_y_size{496};  // (max_y_range - min_y_range) / pillar_y_size
    std::size_t grid_z_size{1};    // (max_z_range - min_z_range) / pillar_z_size
};

// Main PointPillars class with PIMPL pattern
class PointPillars {
  public:
    PointPillars() = delete;

    /**
     * @brief Constructor
     * @param[in] score_threshold Score threshold for filtering output
     * @param[in] nms_overlap_threshold IOU threshold for NMS
     * @param[in] config PointPillars net configuration file
     * @param[in] device PointPillars net execution device
     */
    PointPillars(const float score_threshold, const float nms_threshold, const PointPillarsConfig &config, const std::string &device);

    ~PointPillars();

    /**
     * @brief Call PointPillars to perform the end-to-end object detection chain
     * @param[in] in_points_array Pointcloud array
     * @param[in] in_num_points Number of points
     * @param[in] detections Network output bounding box list
     * @details This is the main public interface to run the algorithm
     */
    void Detect(const float *in_points_array, const int in_num_points, std::vector<ObjectDetection> &detections, size_t *dur = NULL);

  private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

}  // namespace pointpillars

#endif  // LIBLIDAR_H
