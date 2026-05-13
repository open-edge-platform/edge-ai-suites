#pragma once

#include <chrono>
#include <iostream>
#include <memory>
#include <vector>
#include <numeric>
#include <functional>
#include <stdexcept>
#include <opencv2/opencv.hpp>
#include <sycl/sycl.hpp>
#include "bev_cam.hpp"
#include "bev.h"
#include "camera-geometry.hpp"
#include "pipeline/camera_backbone.hpp"
#include "pipeline/calib_metas.hpp"
#include "pipeline/tensor_view.hpp"
#include "latency_stats.hpp"

namespace bevfusion {

inline Bound make_bev_bound(const types::Float3& bound)
{
    return Bound{bound.x, bound.y, bound.z};
}

struct CameraBEVConfig
{
    CameraConfig cam{};  // camera backbone
    bevfusion::camera::GeometryParameter geom{bevfusion::camera::make_v2xfusion_geometry_parameter()};
    uint32_t camera_channels{80};
    uint32_t depth_channels{90};
    uint32_t feature_h{54};
    uint32_t feature_w{96};
    uint32_t bev_width{128};
    uint32_t bev_height{128};
};

struct CameraBEVOutput
{
    TensorView bev;                                 // camera BEV feature
    std::shared_ptr<std::vector<float>> host_keep;  // if host copy created
};

class CameraBEVBackbone {
  public:
    ~CameraBEVBackbone()
    {
        try {
            if (feat_dev_buf_) {
                sycl::free(feat_dev_buf_, queue_);
                feat_dev_buf_ = nullptr;
                feat_dev_cap_ = 0;
            }
            if (depth_dev_buf_) {
                sycl::free(depth_dev_buf_, queue_);
                depth_dev_buf_ = nullptr;
                depth_dev_cap_ = 0;
            }
            if (bev_dev_) {
                sycl::free(bev_dev_, queue_);
                bev_dev_ = nullptr;
                bev_cap_ = 0;
            }
        }
        catch (...) {
        }
    }

    CameraBEVBackbone(const CameraBEVConfig &config, sycl::queue &queue)
        : config_(config), queue_(queue), cam_(config.cam, queue_), bev_(queue_,
                                                                         config.camera_channels,
                                                                         config.camera_channels,
                                                                         config.geom.image_width,
                                                                         config.geom.image_height,
                                                                         config.feature_w,
                                                                         config.feature_h,
                                                                         make_bev_bound(config.geom.xbound),
                                                                         make_bev_bound(config.geom.ybound),
                                                                         make_bev_bound(config.geom.zbound),
                                                                         make_bev_bound(config.geom.dbound))
    {
        geometry_ = bevfusion::camera::create_geometry(config_.geom, queue_);
        if (!geometry_) {
            throw std::runtime_error("Failed to create camera geometry");
        }
    }

    // Synchronous run: geometry prep -> camera backbone infer -> bev_pool.
    // If recompute_metas is false, reuses cached metas/geometry (saves ~1-2ms/frame).
    // Throws if recompute_metas=false but no cache exists or inputs differ from cache.
    CameraBEVOutput run(const cv::Mat &image,
                        const CalibField_t &calib,
                        const std::string &camera_key = "P2",
                        float ground_z_lidar = 0.0f,
                        bool recompute_metas = true)
    {
        if (image.empty()) {
            throw std::runtime_error("CameraBEVBackbone::run requires a non-empty image");
        }

        if (recompute_metas) {
            cached_metas_ = bevfusion::compute_camera_metas_from_kitti_calib(
                calib, image.size(),
                static_cast<int>(config_.geom.image_width),
                static_cast<int>(config_.geom.image_height),
                static_cast<int>(config_.geom.num_camera),
                camera_key, ground_z_lidar);
            cached_camera_key_ = camera_key;
            cached_ground_z_lidar_ = ground_z_lidar;
            cached_raw_image_size_ = image.size();
            cached_target_w_ = static_cast<int>(config_.geom.image_width);
            cached_target_h_ = static_cast<int>(config_.geom.image_height);
            cached_num_camera_ = static_cast<int>(config_.geom.num_camera);
            cached_valid_ = true;
        } else {
            if (!cached_valid_) {
                throw std::runtime_error("CameraBEVBackbone: recompute_metas=false but no cached metas exist");
            }
            if (cached_camera_key_ != camera_key || cached_num_camera_ != static_cast<int>(config_.geom.num_camera) ||
                cached_target_w_ != static_cast<int>(config_.geom.image_width) || cached_target_h_ != static_cast<int>(config_.geom.image_height) ||
                cached_raw_image_size_ != image.size() || cached_ground_z_lidar_ != ground_z_lidar) {
                throw std::runtime_error("CameraBEVBackbone: cache mismatch; call with recompute_metas=true to refresh");
            }
            if (!cached_geometry_valid_) {
                throw std::runtime_error("CameraBEVBackbone: recompute_metas=false but no cached geometry exists");
            }
        }

        if (cached_metas_.camera2lidar.empty() || cached_metas_.intrinsics.empty() || cached_metas_.img_aug.empty()) {
            throw std::runtime_error("CameraBEVBackbone: empty cached calibration matrices");
        }

        const auto t_geom0 = std::chrono::steady_clock::now();
        if (recompute_metas) {
            geometry_->update(cached_metas_.camera2lidar.data(), cached_metas_.intrinsics.data(),
                              cached_metas_.img_aug.data(), cached_metas_.denorms.data(), &queue_);
            cached_indices_ptr_ = geometry_->indices();
            cached_intervals_ptr_ = geometry_->intervals();
            cached_num_intervals_ = geometry_->num_intervals();
            cached_geometry_valid_ = true;
        }
        const auto t_geom1 = std::chrono::steady_clock::now();

        const auto t_cam0 = std::chrono::steady_clock::now();
        auto cam_out = cam_.run(image);

        float *feat_dev = ensure_device_buffer(cam_out.features, feat_dev_buf_, feat_dev_cap_);
        float *depth_dev = ensure_device_buffer(cam_out.depth, depth_dev_buf_, depth_dev_cap_);
        const auto t_cam1 = std::chrono::steady_clock::now();

        const auto t_pool0 = std::chrono::steady_clock::now();
        const size_t bev_elems = static_cast<size_t>(config_.camera_channels) * config_.bev_width * config_.bev_height;
        ensure_bev_buffer(bev_elems);

        uint32_t result = bev_.bevPool(feat_dev, depth_dev, cached_indices_ptr_, cached_intervals_ptr_,
                                       bev_dev_, cached_num_intervals_, 1, config_.camera_channels,
                                       config_.depth_channels, config_.feature_h, config_.feature_w,
                                       config_.bev_width, config_.bev_height);
        if (result != 0) {
            throw std::runtime_error("bevPool failed with code " + std::to_string(result));
        }

        queue_.wait_and_throw();
        const auto t_pool1 = std::chrono::steady_clock::now();

        const double geom_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_geom1 - t_geom0).count();
        const double cam_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_cam1 - t_cam0).count();
        const double bevpool_ms = std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(t_pool1 - t_pool0).count();
        latency_.add(geom_ms, cam_ms, bevpool_ms);

        CameraBEVOutput out;
        out.bev = TensorView::FromUSM(bev_dev_, {1, config_.camera_channels, config_.bev_height, config_.bev_width}, TensorView::Location::USMDevice);
        return out;
    }

    const CameraBEVConfig &config() const
    {
        return config_;
    }

    void reset_latency_stats()
    {
        latency_.reset();
    }

    const perfstats::CameraLatencyStats &latency_stats() const
    {
        return latency_;
    }

    void print_latency_stats(std::ostream &os = std::cout, const std::string &label = "camera_bev") const
    {
        latency_.print(os, label);
    }

  private:
    float *ensure_device_buffer(const TensorView &tv, float *&buf, size_t &cap)
    {
        const size_t elems = tv.numel();
        if (elems == 0)
            throw std::runtime_error("CameraBEVBackbone: empty tensor");
        if (tv.is_usm())
            return tv.data;
        if (cap < elems) {
            if (buf)
                sycl::free(buf, queue_);
            buf = sycl::malloc_device<float>(elems, queue_);
            cap = elems;
        }
        // No .wait() needed: the in-order queue guarantees the memcpy
        // completes before any subsequently-submitted kernel reads buf.
        queue_.memcpy(buf, tv.data, elems * sizeof(float));
        return buf;
    }

    void ensure_bev_buffer(size_t elems)
    {
        if (bev_cap_ < elems) {
            if (bev_dev_)
                sycl::free(bev_dev_, queue_);
            bev_dev_ = sycl::malloc_device<float>(elems, queue_);
            bev_cap_ = elems;
        }
    }

    CameraBEVConfig config_;
    sycl::queue &queue_;
    CameraBackbone cam_;
    std::shared_ptr<bevfusion::camera::Geometry> geometry_;
    Bev bev_;

    CameraMetas cached_metas_{};
    bool cached_valid_{false};
    std::string cached_camera_key_{};
    float cached_ground_z_lidar_{0.0f};
    cv::Size cached_raw_image_size_{};
    int cached_target_w_{0};
    int cached_target_h_{0};
    int cached_num_camera_{0};

    unsigned int *cached_indices_ptr_{nullptr};
    types::Int3 *cached_intervals_ptr_{nullptr};
    uint32_t cached_num_intervals_{0};
    bool cached_geometry_valid_{false};

    float *feat_dev_buf_{nullptr};
    size_t feat_dev_cap_{0};
    float *depth_dev_buf_{nullptr};
    size_t depth_dev_cap_{0};
    float *bev_dev_{nullptr};
    size_t bev_cap_{0};

    perfstats::CameraLatencyStats latency_{};
};

}  // namespace bevfusion
