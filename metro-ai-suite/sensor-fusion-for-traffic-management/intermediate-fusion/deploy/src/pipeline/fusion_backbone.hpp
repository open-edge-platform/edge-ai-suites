#pragma once

#include <array>
#include <vector>
#include <chrono>
#include <iostream>
#include <sstream>
#include <unordered_set>
#include <sycl/sycl.hpp>
#include "bev_fuser.hpp"
#include "bev_head.hpp"
#include "postprocess_sycl.hpp"
#include "pipeline/tensor_view.hpp"
#include "latency_stats.hpp"

namespace bevfusion {

struct DetectionFusionConfig
{
    std::string fuser_model{"../data/v2xfusion/pointpillars/quantized_fuser.xml"};
    std::string head_model{"../data/v2xfusion/pointpillars/quantized_head.xml"};
    ov::Shape camera_bev_shape{1, 80, 128, 128};
    ov::Shape lidar_bev_shape{1, 64, 128, 128};
    PostProcessParams post_params{};
    PostProcessInputChannels channels{2, 1, 3, 2, 2, 5};
    // Labels to suppress from output. Matched against BBox3D::label.
    // Default: bicycle (7) and pedestrian (8).
    std::vector<int> filter_labels{7, 8};

    int batch_size() const
    {
        return static_cast<int>(require_nchw_shape(camera_bev_shape, "camera_bev_shape")[0]);
    }

    int bev_height() const
    {
        return static_cast<int>(require_nchw_shape(camera_bev_shape, "camera_bev_shape")[2]);
    }

    int bev_width() const
    {
        return static_cast<int>(require_nchw_shape(camera_bev_shape, "camera_bev_shape")[3]);
    }

  private:
    static const ov::Shape &require_nchw_shape(const ov::Shape &shape, const char *name)
    {
        if (shape.size() != 4) {
            throw std::runtime_error(std::string(name) + " must be a 4D NCHW shape");
        }
        return shape;
    }
};


class DetectionFusion {
  public:
    DetectionFusion(const DetectionFusionConfig &config, sycl::queue &queue)
        : config_(config), queue_(queue),
          fuser_(config.fuser_model, queue_, true),
          head_(config.head_model, queue_, true),
          post_(config.post_params, queue_),
          filter_labels_set_(config.filter_labels.begin(), config.filter_labels.end())
    {
                validate_shape_compatibility_();
    }

    ~DetectionFusion()
    {
        try {
            if (fused_dev_) {
                sycl::free(fused_dev_, queue_);
                fused_dev_ = nullptr;
                fused_cap_ = 0;
            }
        }
        catch (...) {
        }
    }

    std::vector<BBox3D> postprocess(const HeadResults &heads)
    {
        const int N = config_.batch_size();
        const int H = config_.bev_height();
        const int W = config_.bev_width();
        const auto ch = config_.channels;

        // PostProcessSycl runs GPU kernels that directly access the head output USM shared
        // pointers — no D2H staging is needed.  Both code paths in run() call
        // inferHeadGPU(..., keep_on_gpu=true), so is_gpu_results is always true in normal
        // operation.  queue_.wait_and_throw() in run() ensures all head outputs are coherent
        // in USM shared memory before postprocess() is entered.
        if (!heads.is_gpu_results) {
            throw std::runtime_error(
                "DetectionFusion::postprocess: non-GPU head results are not supported "
                "with PostProcessSycl — head outputs must be in USM shared memory. "
                "Ensure inferHeadGPU is called with keep_on_gpu=true.");
        }

        auto make_task_input = [&](unsigned int task_idx) {
            switch (task_idx) {
                case 0:
                    return PostProcessInput{heads.score_ptr,  heads.reg_ptr,    heads.height_ptr,
                                            heads.dim_ptr,    heads.rot_ptr,    heads.vel_ptr};
                case 1:
                    return PostProcessInput{heads.score2_ptr, heads.reg2_ptr,   heads.height2_ptr,
                                            heads.dim2_ptr,   heads.rot2_ptr,   heads.vel2_ptr};
                default:
                    throw std::runtime_error("Unsupported head task index: " + std::to_string(task_idx));
            }
        };

        std::vector<BBox3D> boxes;
        for (unsigned int task_idx = 0; task_idx < PostProcessParams::kNumTasks; ++task_idx) {
            const TaskConfig &cfg = config_.post_params.task_configs[task_idx];
            auto task_boxes = post_.decodeTask(make_task_input(task_idx), N, H, W, cfg, ch);
            boxes.insert(boxes.end(), task_boxes.begin(), task_boxes.end());
        }
        if (!config_.filter_labels.empty()) {
            boxes.erase(
                std::remove_if(boxes.begin(), boxes.end(), [&](const BBox3D &b) {
                return filter_labels_set_.count(b.label) > 0;
                }),
                boxes.end());
        }
        return boxes;
    }

    // Convenience: fuse + head + postprocess
    std::vector<BBox3D> run(const TensorView &camera_bev, const TensorView &lidar_bev)
    {
        double fuser_ms = 0.0;
        double head_ms = 0.0;

        HeadResults heads;
        try {
            // Zero-copy fast path: if both inputs are USM device pointers, bind them directly into fuser.
            if (camera_bev.is_usm() && lidar_bev.is_usm() && camera_bev.data != nullptr && lidar_bev.data != nullptr) {
                const auto t_fuser0 = std::chrono::steady_clock::now();
                const size_t fused_elems = ov::shape_size(fuser_.getFusedOutputShape());
                if (fused_cap_ < fused_elems) {
                    if (fused_dev_) {
                        sycl::free(fused_dev_, queue_);
                    }
                    fused_dev_ = sycl::malloc_device<float>(fused_elems, queue_);
                    if (!fused_dev_) {
                        throw std::runtime_error("DetectionFusion: failed to allocate fused_dev_");
                    }
                    fused_cap_ = fused_elems;
                }

                FuserInput fin = fuser_.createFuserInputFromPointers(
                    camera_bev.data,
                    lidar_bev.data,
                    fuser_.getCameraBEVInputShape(),
                    fuser_.getLidarInputShape());
                fin.fused_output_ptr = fused_dev_;
                auto fuser_out = fuser_.fuseFeatures(fin);
                const auto t_fuser1 = std::chrono::steady_clock::now();
                fuser_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_fuser1 - t_fuser0).count();

                HeadInput hin;
                if (fuser_out.fused_features_ptr != nullptr) {
                    hin = head_.createHeadInputFromPointer(fuser_out.fused_features_ptr, fuser_out.fused_shape);
                }
                else if (fuser_out.is_gpu_tensor) {
                    hin = head_.createHeadInputFromGPUTensor(fuser_out.gpu_tensor, fuser_out.fused_shape);
                }
                else {
                    throw std::runtime_error("DetectionFusion: zero-copy fuser path returned a host tensor unexpectedly");
                }

                // keep_on_gpu=true => bind outputs to USM shared and return pointer results
                const auto t_head0 = std::chrono::steady_clock::now();
                heads = head_.inferHeadGPU(hin, true);
                const auto t_head1 = std::chrono::steady_clock::now();
                head_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_head1 - t_head0).count();
            }
            else {
                // Fallback: stage to host and use stable host IO.
                run_host_staging_(camera_bev, lidar_bev, heads, fuser_ms, head_ms);
            }
        }
        catch (const std::exception& e) {
            // Last-resort fallback to stable path.
            run_host_staging_(camera_bev, lidar_bev, heads, fuser_ms, head_ms);
            std::cerr << "[warn] zero-copy fusion path failed, fallback to host staging: " << e.what() << std::endl;
        }
        queue_.wait_and_throw();

        const auto t2 = std::chrono::steady_clock::now();
        auto boxes = postprocess(heads);
        const auto t3 = std::chrono::steady_clock::now();

        const double post_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t3 - t2).count();
        latency_.add(fuser_ms, head_ms, post_ms);

        return boxes;
    }

    void reset_latency_stats()
    {
        latency_.reset();
    }

    const perfstats::FusionLatencyStats &latency_stats() const
    {
        return latency_;
    }

    void print_latency_stats(std::ostream &os = std::cout, const std::string &label = "fusion") const
    {
        latency_.print(os, label);
    }

  private:
    static std::string shape_to_string_(const ov::Shape &shape)
    {
        std::ostringstream os;
        os << "[";
        for (size_t i = 0; i < shape.size(); ++i) {
            if (i != 0)
                os << ", ";
            os << shape[i];
        }
        os << "]";
        return os.str();
    }

    void validate_shape_compatibility_() const
    {
        const auto fuser_camera_shape = fuser_.getCameraBEVInputShape();
        const auto fuser_lidar_shape = fuser_.getLidarInputShape();
        const auto fuser_output_shape = fuser_.getFusedOutputShape();
        const auto head_input_shape = head_.getFuserInputShape();

        if (config_.camera_bev_shape != fuser_camera_shape) {
            throw std::runtime_error("DetectionFusion camera shape mismatch: config=" +
                                     shape_to_string_(config_.camera_bev_shape) + ", fuser=" +
                                     shape_to_string_(fuser_camera_shape));
        }
        if (config_.lidar_bev_shape != fuser_lidar_shape) {
            throw std::runtime_error("DetectionFusion lidar shape mismatch: config=" +
                                     shape_to_string_(config_.lidar_bev_shape) + ", fuser=" +
                                     shape_to_string_(fuser_lidar_shape));
        }
        if (fuser_output_shape != head_input_shape) {
            throw std::runtime_error("DetectionFusion fused/head shape mismatch: fuser=" +
                                     shape_to_string_(fuser_output_shape) + ", head=" +
                                     shape_to_string_(head_input_shape));
        }
        if (config_.camera_bev_shape.size() != 4 || config_.lidar_bev_shape.size() != 4) {
            throw std::runtime_error("DetectionFusion expects 4D NCHW config shapes");
        }
        if (config_.camera_bev_shape[0] != config_.lidar_bev_shape[0] ||
            config_.camera_bev_shape[2] != config_.lidar_bev_shape[2] ||
            config_.camera_bev_shape[3] != config_.lidar_bev_shape[3]) {
            throw std::runtime_error("DetectionFusion camera/lidar BEV shapes must have matching N/H/W: camera=" +
                                     shape_to_string_(config_.camera_bev_shape) + ", lidar=" +
                                     shape_to_string_(config_.lidar_bev_shape));
        }
    }

    // Shared host-staging fallback: stage both BEV tensors to host, run fuser + head inference.
    // Used by both the non-USM-input branch and the zero-copy exception handler in run().
    void run_host_staging_(const TensorView &camera_bev, const TensorView &lidar_bev,
                           HeadResults &heads, double &fuser_ms, double &head_ms)
    {
        const auto t_fuser0 = std::chrono::steady_clock::now();
        auto cam_host = camera_bev.to_host(&queue_);
        auto lidar_host = lidar_bev.to_host(&queue_);
        ov::Tensor fused_tensor = fuser_.fuseHostToOvTensor(cam_host, lidar_host, true);
        const auto t_fuser1 = std::chrono::steady_clock::now();
        fuser_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_fuser1 - t_fuser0).count();
        HeadInput head_input = head_.createHeadInputFromGPUTensor(fused_tensor, fused_tensor.get_shape());
        const auto t_head0 = std::chrono::steady_clock::now();
        heads = head_.inferHeadGPU(head_input, true);
        const auto t_head1 = std::chrono::steady_clock::now();
        head_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_head1 - t_head0).count();
    }

    DetectionFusionConfig config_;
    sycl::queue &queue_;
    BEVFusionFuser fuser_;
    BEVFusionHead head_;
    PostProcessSycl post_;

    perfstats::FusionLatencyStats latency_{};

    float* fused_dev_{nullptr};
    size_t fused_cap_{0};
    std::unordered_set<int> filter_labels_set_;
};

}  // namespace bevfusion
