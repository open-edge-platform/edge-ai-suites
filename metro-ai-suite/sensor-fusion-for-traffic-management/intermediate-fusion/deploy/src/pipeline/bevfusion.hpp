// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <opencv2/opencv.hpp>
#include <string>
#include <sycl/sycl.hpp>
#include <thread>
#include <vector>

#include "latency_stats.hpp"
#include "pipeline/calib_metas.hpp"
#include "pipeline/camera_bev_backbone.hpp"
#include "pipeline/fusion_backbone.hpp"
#include "pipeline/lidar_backbone.hpp"

namespace bevfusion {

struct PipelineConfig
{
    CameraBEVConfig camera{};
    LidarConfig lidar{};
    DetectionFusionConfig fusion{};
};

class BEVFusionPipeline {
public:
    struct PerfStats {
        std::size_t frames{0};
        double sum_lidar_ms{0.0};
        double sum_camera_bev_ms{0.0};
        double sum_fusion_ms{0.0};
        double sum_total_ms{0.0};
    };

    BEVFusionPipeline(const PipelineConfig& cfg, sycl::queue& queue)
        : config_(cfg), queue_(queue), lidar_(config_.lidar, queue_),
          cam_bev_(config_.camera, queue_), fusion_(config_.fusion, queue_)
    {
        // Persistent lidar worker thread overlaps lidar inference with the
        // camera backbone on the calling thread. A cv-driven worker avoids
        // per-frame std::async overhead and has run stable on B580 across
        // thousands of samples.
        lidar_thread_ = std::thread([this]() { lidar_worker_loop_(); });
    }

    ~BEVFusionPipeline()
    {
        {
            std::lock_guard<std::mutex> lk(lidar_mtx_);
            lidar_stop_ = true;
        }
        lidar_cv_submit_.notify_one();
        if (lidar_thread_.joinable()) {
            lidar_thread_.join();
        }
    }

    BEVFusionPipeline(const BEVFusionPipeline&) = delete;
    BEVFusionPipeline& operator=(const BEVFusionPipeline&) = delete;

    void reset_perf_stats() { perf_ = {}; }
    void reset_latency_stats()
    {
        latency_.reset();
        lidar_.reset_latency_stats();
        cam_bev_.reset_latency_stats();
        fusion_.reset_latency_stats();
    }

    PerfStats perf_stats() const { return perf_; }
    const perfstats::PipelineLatencyStats& latency_stats() const { return latency_; }

    void print_perf_stats(std::ostream& os = std::cout) const
    {
        if (perf_.frames == 0) {
            os << "[perf] frames=0" << std::endl;
            return;
        }
        const std::ios::fmtflags f = os.flags();
        const std::streamsize p = os.precision();
        const double n = static_cast<double>(perf_.frames);
        os << "[perf] frames=" << perf_.frames
           << ", avg_lidar=" << std::fixed << std::setprecision(3) << (perf_.sum_lidar_ms / n) << " ms"
           << ", avg_camera_bev=" << std::fixed << std::setprecision(3) << (perf_.sum_camera_bev_ms / n) << " ms"
           << ", avg_fusion+post=" << std::fixed << std::setprecision(3) << (perf_.sum_fusion_ms / n) << " ms"
           << ", avg_total=" << std::fixed << std::setprecision(3) << (perf_.sum_total_ms / n) << " ms"
           << std::endl;
        os.flags(f);
        os.precision(p);
    }

    void print_latency_stats(std::ostream& os = std::cout) const
    {
        latency_.print(os, "pipeline");
    }

    std::vector<BBox3D> run(const cv::Mat& image,
                            const std::vector<float>& points,
                            const CalibField_t& calib,
                            const std::string& camera_key = "P2",
                            float ground_z_lidar = 0.0f,
                            bool recompute_camera_metas = true)
    {
        const auto t0 = std::chrono::steady_clock::now();

        // Submit lidar work to the persistent worker thread.
        {
            std::lock_guard<std::mutex> lk(lidar_mtx_);
            lidar_points_ = &points;
            lidar_has_task_ = true;
            lidar_done_ = false;
        }
        lidar_cv_submit_.notify_one();

        // Run camera on the calling thread while lidar runs in parallel.
        const auto tc0 = std::chrono::steady_clock::now();
        auto cam_bev_out = cam_bev_.run(image, calib, camera_key, ground_z_lidar, recompute_camera_metas);
        const auto tc1 = std::chrono::steady_clock::now();
        const double cam_ms = std::chrono::duration<double, std::milli>(tc1 - tc0).count();

        // Wait for lidar result (typically already done; near-zero wait).
        double lidar_ms = 0.0;
        LidarOutputs lidar_out;
        {
            std::unique_lock<std::mutex> lk(lidar_mtx_);
            lidar_cv_done_.wait(lk, [&]() { return lidar_done_; });
            lidar_out = std::move(lidar_result_);
            lidar_ms = lidar_ms_;
        }

        const auto tf0 = std::chrono::steady_clock::now();
        auto boxes = fusion_.run(cam_bev_out.bev, lidar_out.scatter);
        const auto tf1 = std::chrono::steady_clock::now();
        const double fusion_ms = std::chrono::duration<double, std::milli>(tf1 - tf0).count();
        const double total_ms = std::chrono::duration<double, std::milli>(tf1 - t0).count();

        perf_.frames += 1;
        perf_.sum_lidar_ms += lidar_ms;
        perf_.sum_camera_bev_ms += cam_ms;
        perf_.sum_fusion_ms += fusion_ms;
        perf_.sum_total_ms += total_ms;
        latency_.add(lidar_ms, cam_ms, fusion_ms);
        return boxes;
    }

    CameraBEVBackbone& camera_bev() { return cam_bev_; }
    LidarBackbone& lidar() { return lidar_; }
    DetectionFusion& fusion() { return fusion_; }
    const PipelineConfig& config() const { return config_; }

private:
    void lidar_worker_loop_()
    {
        while (true) {
            std::unique_lock<std::mutex> lk(lidar_mtx_);
            lidar_cv_submit_.wait(lk, [&]() { return lidar_has_task_ || lidar_stop_; });
            if (lidar_stop_)
                return;

            const std::vector<float>* pts = lidar_points_;
            lk.unlock();

            const auto tl0 = std::chrono::steady_clock::now();
            auto out = lidar_.run(*pts);
            const auto tl1 = std::chrono::steady_clock::now();

            lk.lock();
            lidar_result_ = std::move(out);
            lidar_ms_ = std::chrono::duration<double, std::milli>(tl1 - tl0).count();
            lidar_has_task_ = false;
            lidar_done_ = true;
            lk.unlock();
            lidar_cv_done_.notify_one();
        }
    }

    PipelineConfig config_;
    sycl::queue& queue_;
    LidarBackbone lidar_;
    CameraBEVBackbone cam_bev_;
    DetectionFusion fusion_;
    PerfStats perf_{};
    perfstats::PipelineLatencyStats latency_{};

    // Lidar worker thread state
    std::thread lidar_thread_;
    std::mutex lidar_mtx_;
    std::condition_variable lidar_cv_submit_;
    std::condition_variable lidar_cv_done_;
    const std::vector<float>* lidar_points_{nullptr};
    LidarOutputs lidar_result_;
    double lidar_ms_{0.0};
    bool lidar_has_task_{false};
    bool lidar_done_{false};
    bool lidar_stop_{false};
};

}  // namespace bevfusion
