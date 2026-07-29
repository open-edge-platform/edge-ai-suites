#pragma once

#include <opencv2/opencv.hpp>

#include <atomic>
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "configs.hpp"


struct CameraVizOptions
{
    int camera_index = 2;         // KITTI default camera P2
    float line_thickness = 2.0f;  // Pixel thickness for box edges
    cv::Scalar default_color{0, 255, 0};
};

struct LidarVizOptions
{
    std::pair<float, float> xlim{0.0f, 102.4f};
    std::pair<float, float> ylim{-51.2f, 51.2f};
    cv::Size canvas_size{800, 800};
    int point_radius = 1;
    int box_thickness = 2;
};

struct VisualizerOptions
{
    bool enable = false;
    bool save_images = false;
    bool save_video = false;
    bool display = false;
    std::filesystem::path output_dir = std::filesystem::path("vis");
    std::string video_name = "bevfusion.mp4";
    double fps = 25.0;
    int max_width = 1280;
    int max_height = 720;
    CameraVizOptions cam_opts;
    LidarVizOptions lidar_opts;
};

class Visualizer
{
public:
    enum class RenderMode {
        Camera,
        Lidar,
        Combined
    };

    explicit Visualizer(const VisualizerOptions &opts);

    bool initialize();
    bool isEnabled() const { return options_.enable; }

    // Returns true if a stop was requested via display window (q/ESC).
    // Unified render entry: select output via mode (default Combined).
    bool render(const ImageData_t &image,
                const lidarVec_t &lidar,
                const std::vector<BBox3D> &boxes,
                const CalibField_t &calib,
                const std::vector<std::string> &class_names,
                const std::string &frame_id = std::string(),
                RenderMode mode = RenderMode::Combined);

    // Returns true if a stop was requested via display window (q/ESC).
    bool renderCamera(const ImageData_t &image,
                      const std::vector<BBox3D> &boxes,
                      const CalibField_t &calib,
                      const std::vector<std::string> &class_names,
                      const std::string &frame_id = std::string());

    bool renderLidar(const lidarVec_t &lidar,
                     const std::vector<BBox3D> &boxes,
                     const std::vector<std::string> &class_names,
                     const std::string &frame_id = std::string());

    bool renderCombined(const ImageData_t &image,
                        const lidarVec_t &lidar,
                        const std::vector<BBox3D> &boxes,
                        const CalibField_t &calib,
                        const std::vector<std::string> &class_names,
                        const std::string &frame_id = std::string());

    void close();

private:
    VisualizerOptions options_;
    bool initialized_ = false;
    bool video_writer_initialized_ = false;
    bool video_needs_resize_ = false;
    bool show_window_ = false;
    cv::Size video_size_;
    cv::VideoWriter video_writer_;

    bool ensureOutputDir_();
    bool initVideoWriter_(const cv::Mat &frame);
    cv::Mat maybeResize_(const cv::Mat &frame);
    bool processFrame_(const cv::Mat &frame, const std::string &frame_id);
    cv::Mat buildCameraFrame_(const ImageData_t &image,
                              const std::vector<BBox3D> &boxes,
                              const CalibField_t &calib,
                              const std::vector<std::string> &class_names);
    cv::Mat buildLidarFrame_(const lidarVec_t &lidar,
                             const std::vector<BBox3D> &boxes,
                             const std::vector<std::string> &class_names);
    cv::Mat buildCombinedFrame_(const ImageData_t &image,
                                const lidarVec_t &lidar,
                                const std::vector<BBox3D> &boxes,
                                const CalibField_t &calib,
                                const std::vector<std::string> &class_names,
                                const std::string &frame_id);
    bool saveImage_(const cv::Mat &frame, const std::string &path);
};

struct AsyncVisualizerOptions
{
    // Max queued frames; when full, drop policy applies.
    size_t max_queue_size = 512;
    bool drop_oldest = true;
};

class AsyncVisualizer
{
public:
    explicit AsyncVisualizer(const VisualizerOptions &vis_opts,
                             const AsyncVisualizerOptions &async_opts = AsyncVisualizerOptions());

    bool initialize();
    bool isEnabled() const { return visualizer_.isEnabled(); }

    // Returns true if the task was accepted (queued); false if dropped.
    bool render(const ImageData_t &image,
                const lidarVec_t &lidar,
                const std::vector<BBox3D> &boxes,
                const CalibField_t &calib,
                const std::vector<std::string> &class_names,
                const std::string &frame_id = std::string(),
                Visualizer::RenderMode mode = Visualizer::RenderMode::Combined);

    bool renderCamera(const ImageData_t &image,
                      const std::vector<BBox3D> &boxes,
                      const CalibField_t &calib,
                      const std::vector<std::string> &class_names,
                      const std::string &frame_id = std::string());

    bool renderLidar(const lidarVec_t &lidar,
                     const std::vector<BBox3D> &boxes,
                     const std::vector<std::string> &class_names,
                     const std::string &frame_id = std::string());

    bool renderCombined(const ImageData_t &image,
                        const lidarVec_t &lidar,
                        const std::vector<BBox3D> &boxes,
                        const CalibField_t &calib,
                        const std::vector<std::string> &class_names,
                        const std::string &frame_id = std::string());

    bool stopRequested() const { return stop_requested_.load(); }
    void close();

private:
    struct Task
    {
        Visualizer::RenderMode mode = Visualizer::RenderMode::Combined;
        ImageData_t image;
        lidarVec_t lidar;
        std::vector<BBox3D> boxes;
        CalibField_t calib;
        std::vector<std::string> class_names;
        std::string frame_id;
    };

    bool enqueue_(Task &&task);
    void workerLoop_();

    Visualizer visualizer_;
    AsyncVisualizerOptions async_opts_;

    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<Task> queue_;
    std::thread worker_;
    std::atomic<bool> running_{false};
    std::atomic<bool> stop_requested_{false};
};
