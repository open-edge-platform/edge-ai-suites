#pragma once

#include <memory>
#include <opencv2/opencv.hpp>
#include <sycl/sycl.hpp>
#include "bev_cam.hpp"
#include "pipeline/tensor_view.hpp"

namespace bevfusion {

struct CameraConfig
{
    std::string model_path{"../data/v2xfusion/pointpillars/camera.backbone.onnx"};
    bool use_gpu{true};
    // If true (and GPU shared context is available), bind OpenVINO outputs directly to USM device pointers.
    bool zero_copy_outputs{true};
};

struct CameraOutputs
{
    TensorView features;
    TensorView depth;
    // Keep host storage alive when data is owned by vectors
    std::shared_ptr<std::vector<float>> host_features;
    std::shared_ptr<std::vector<float>> host_depth;
};

class CameraBackbone {
  public:
    CameraBackbone(const CameraConfig &config, sycl::queue &queue) : config_(config), queue_(queue), impl_(config.model_path, queue_, config.use_gpu) {}

    CameraOutputs run(const cv::Mat &image)
    {
        auto raw = impl_.processImage(image, config_.zero_copy_outputs);
        CameraOutputs out;
        const std::vector<size_t> cam_shape(raw.camera_shape.begin(), raw.camera_shape.end());
        const std::vector<size_t> dep_shape(raw.depth_shape.begin(), raw.depth_shape.end());
        if (raw.is_usm && raw.camera_ptr != nullptr && raw.depth_ptr != nullptr) {
            out.features = TensorView::FromUSM(raw.camera_ptr, cam_shape, TensorView::Location::USMDevice);
            out.depth = TensorView::FromUSM(raw.depth_ptr, dep_shape, TensorView::Location::USMDevice);
        } else {
            out.host_features = std::make_shared<std::vector<float>>(std::move(raw.camera_features));
            out.host_depth = std::make_shared<std::vector<float>>(std::move(raw.depth_weights));
            out.features = TensorView::FromHost(out.host_features->data(), cam_shape);
            out.depth = TensorView::FromHost(out.host_depth->data(), dep_shape);
        }
        return out;
    }

  private:
    CameraConfig config_;
    sycl::queue &queue_;
    BEVFusionCam impl_;
};

}  // namespace bevfusion
