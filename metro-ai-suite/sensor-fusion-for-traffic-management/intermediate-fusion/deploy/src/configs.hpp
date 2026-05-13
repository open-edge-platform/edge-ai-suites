#ifndef _CONFIGS_HPP_
#define _CONFIGS_HPP_

#include <array>
#include <cmath>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

// OpenCV for image processing
#include <opencv2/opencv.hpp>

const unsigned int MAX_DET_NUM = 1000;  // nms_pre_max_size = 1000;
const unsigned int NUM_TASKS = 6;
const unsigned int DET_CHANNEL = 11;
constexpr unsigned int MAX_CLASSES_PER_TASK = 5;

/*************************************************************************************************
 * @brief Basic data structures for 3D object detection post-processing
 *************************************************************************************************/
enum class NmsType {
    kRotate = 0,
    kCircle = 1,
};

struct TaskConfig
{
    const char *name;
    unsigned int num_classes;
    NmsType nms_type;
    float circle_radius;
    std::array<float, MAX_CLASSES_PER_TASK> nms_scale;
    unsigned int label_offset;
};

struct PostProcessInput
{
    const float *heatmap;
    const float *reg;
    const float *height;
    const float *dim;
    const float *rot;
    const float *vel;
};

struct PostProcessInputChannels
{
    int C_reg = 2;
    int C_height = 1;
    int C_dim = 3;
    int C_rot = 2;
    int C_vel = 2;
    int C_hm = 5;
};

class PostProcessParams {
  public:
    unsigned int task_num_stride[NUM_TASKS] = {
        0, 1, 3, 5, 6, 8,
    };
    static const unsigned int num_classes = 10;
    const char *class_name[num_classes] = {"car",        "truck",   "construction_vehicle", "bus",         "trailer", "barrier",
                                           "motorcycle", "bicycle", "pedestrian",           "traffic_cone"};

    static constexpr unsigned int kNumTasks = 2;

    float out_size_factor = 4.0f;
    float voxel_size[2] = {
        0.2f,
        0.2f,
    };
    std::array<float, 3> pc_range_min = {0.0f, -51.2f, -5.0f};
    std::array<float, 3> pc_range_max = {102.4f, 51.2f, 3.0f};
    float score_threshold = 0.1f;
    float sigmoid_eps = 1e-4f;
    float post_center_limit_range[6] = {
        0.0f, -61.2f, -10.0f, 122.4f, 61.2f, 10.0f,
    };
    float nms_iou_threshold = 0.2f;
    unsigned int pre_max_size = MAX_DET_NUM;
    unsigned int nms_post_max_size = 83;
    unsigned int max_topk = 500;
    bool norm_bbox = true;
    bool use_velocity = true;
    bool heatmap_is_logits = false;
    unsigned int code_size = 9;

    std::array<TaskConfig, kNumTasks> task_configs = {
        TaskConfig{"vehicle", 5u, NmsType::kCircle, 4.0f, {1.f, 1.f, 1.f, 1.f, 1.f}, 0u},
        TaskConfig{"vulnerable", 5u, NmsType::kRotate, 0.8f, {1.f, 1.f, 1.f, 2.5f, 4.0f}, 5u},
    };

    PostProcessParams() = default;

    static PostProcessParams bevfusionDefaults() {
        PostProcessParams p;
        p.out_size_factor = 8.0f;
        p.voxel_size[0] = 0.1f;
        p.voxel_size[1] = 0.1f;
        p.norm_bbox = true;
        p.heatmap_is_logits = true;
        return p;
    }

    static PostProcessParams v2xfusionDefaults() {
        return bevfusionDefaults();
    }
};


/*************************************************************************************************
 * @brief Basic data structures for 3D object detection datasets
 *************************************************************************************************/
// 3D bounding box structure
struct BBox3D
{
    float x, y, z;  // Center coordinates
    float l, w, h;  // Length, width, height
    float vx, vy;   // Velocity (if available)
    float yaw;      // Rotation angle
    int label;      // Class label
    float score;    // Confidence score

    BBox3D() : x(0), y(0), z(0), l(0), w(0), h(0), vx(0), vy(0), yaw(0), label(-1), score(0) {}
    BBox3D(float x_, float y_, float z_, float l_, float w_, float h_, float vx_, float vy_, float yaw_, int label_, float score_)
        : x(x_), y(y_), z(z_), l(l_), w(w_), h(h_), vx(vx_), vy(vy_), yaw(yaw_), label(label_), score(score_)
    {
    }
};

/*************************************************************************************************
 * @brief Enhanced data structures for multi-dataset support
 *************************************************************************************************/
// Transformation matrix (4x4) using standard array
struct Transform4x4
{
    float data[16];

    Transform4x4()
    {
        std::memset(data, 0, sizeof(data));
        data[0] = data[5] = data[10] = data[15] = 1.0f;
    }

    float &operator()(int row, int col)
    {
        return data[row * 4 + col];
    }
    const float &operator()(int row, int col) const
    {
        return data[row * 4 + col];
    }
};

using TransformMap_t = std::unordered_map<std::string, Transform4x4>;

// Camera intrinsics matrix (3x4) and distortion parameters
struct CameraParams
{
    float intrinsics[12];  // 3x4 matrix stored row-major

    CameraParams()
    {
        std::memset(intrinsics, 0, sizeof(intrinsics));
    }

    float &K(int row, int col)
    {
        return intrinsics[row * 4 + col];
    }
    const float &K(int row, int col) const
    {
        return intrinsics[row * 4 + col];
    }
};

using CameraParamsMap_t = std::unordered_map<std::string, CameraParams>;

struct CalibField_t
{
    TransformMap_t transforms;
    CameraParamsMap_t cameraParams;
};

// Image data structure
using ImageData_t = cv::Mat;

// Point cloud data - stored as flat array: x,y,z,intensity for each point
using lidarVec_t = std::vector<float>;

// Dataset configuration
struct DatasetConfig
{
    std::string dataset_type;
    std::vector<std::string> camera_folders;
    std::string pointcloud_folder;
    std::string calib_folder;
    std::vector<std::string> label_folders;
    bool images_are_encoded;
    bool has_multiple_cameras;
    bool use_multiple_cameras;

    DatasetConfig() : images_are_encoded(false), has_multiple_cameras(false), use_multiple_cameras(false) {}
};

struct Data_t
{
    ImageData_t img;
    lidarVec_t lidar;
    CalibField_t calib;
    std::vector<BBox3D> labels;
};


#endif  // _COMMON_H_