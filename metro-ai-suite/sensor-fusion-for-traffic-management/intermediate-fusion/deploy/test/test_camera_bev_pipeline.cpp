#include <opencv2/opencv.hpp>
#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "pipeline/camera_bev_backbone.hpp"
#include "pipeline/calib_metas.hpp"
#include "test_utils.hpp"

using bevfusion::CameraBEVBackbone;
using bevfusion::CameraBEVConfig;

namespace {

struct SimpleStats {
    float min_v{0.0f};
    float max_v{0.0f};
    double mean_abs{0.0};
};

SimpleStats compute_stats(const std::vector<float> &v)
{
    SimpleStats s;
    if (v.empty())
        return s;

    s.min_v = v[0];
    s.max_v = v[0];
    double sum_abs = 0.0;
    for (float x : v) {
        s.min_v = std::min(s.min_v, x);
        s.max_v = std::max(s.max_v, x);
        sum_abs += std::abs(static_cast<double>(x));
    }
    s.mean_abs = sum_abs / static_cast<double>(v.size());
    return s;
}

}  // namespace

int main(int argc, char *argv[])
{
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <dataset_path> [model_path] [warmup] [--fp32]" << std::endl;
        return -1;
    }

    const std::string dataset_path = argv[1];
    bool use_fp32 = false;
    bool model_path_set = false;
    std::string model_path = "../data/v2xfusion/pointpillars/quantized_camera.xml";
    int warmup = 3;

    for (int i = 2; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--fp32") {
            use_fp32 = true;
            continue;
        }
        if (!model_path_set) {
            model_path = arg;
            model_path_set = true;
            continue;
        }
        warmup = std::max(0, std::stoi(arg));
    }

    if (!model_path_set) {
        model_path = use_fp32 ? "../data/v2xfusion/pointpillars/camera.backbone.onnx"
                       : "../data/v2xfusion/pointpillars/quantized_camera.xml";
    }

    sycl::queue queue = create_opencl_queue();
    auto &ctx_mgr = GPUContextManager::getInstance();
    if (!ctx_mgr.initialize(queue, use_fp32)) {
        std::cerr << "Failed to initialize GPU context manager" << std::endl;
        return -1;
    }

    CameraBEVConfig cfg;
    cfg.cam.model_path = model_path;
    cfg.cam.use_gpu = true;

    CameraBEVBackbone cam_bev(cfg, queue);

    KittiDataLoader loader(dataset_path, KittiDataLoader::createKittiConfig());
    auto samples = loader.getSampleList();
    if (samples.empty()) {
        std::cerr << "No samples found in dataset" << std::endl;
        return -1;
    }

    const int frames_to_run = static_cast<int>(samples.size());
    std::cout << "Config: model_path='" << model_path << "', frames=" << frames_to_run << ", warmup=" << warmup << std::endl;

    // Warmup on the first valid sample (build cache + JIT + geometry update).
    if (warmup > 0) {
        for (const auto &id : samples) {
            Data_t sample = loader.getData(id);
            if (sample.img.empty())
                continue;

            std::cout << "Warmup on sample: " << id << " (iters=" << warmup << ")" << std::endl;
            for (int i = 0; i < warmup; ++i) {
                const bool recompute = (i == 0);
                (void)cam_bev.run(sample.img, sample.calib, "P2", 0.0f, recompute);
                queue.wait_and_throw();
            }
            break;
        }
    }

    // Do not include warmup in latency stats
    cam_bev.reset_latency_stats();

    // Timed runs.
    std::size_t frames_done = 0;
    double sum_ms = 0.0;
    using MsRep = std::chrono::milliseconds::rep;
    MsRep min_ms = 0;
    MsRep max_ms = 0;
    bool did_validate = false;

    for (const auto &id : samples) {
        std::cout << "\n=== Processing sample: " << id << " ===" << std::endl;
        Data_t sample = loader.getData(id);
        if (sample.img.empty()) {
            std::cerr << "Empty image for sample " << id << std::endl;
            continue;
        }

        const bool recompute = (warmup == 0 && frames_done == 0);
        const auto t0 = std::chrono::steady_clock::now();
        auto out = cam_bev.run(sample.img, sample.calib, "P2", 0.0f, recompute);
        queue.wait_and_throw();
        const auto t1 = std::chrono::steady_clock::now();
        const MsRep ms = std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count();

        if (frames_done == 0) {
            min_ms = ms;
            max_ms = ms;
        } else {
            min_ms = std::min(min_ms, ms);
            max_ms = std::max(max_ms, ms);
        }
        sum_ms += static_cast<double>(ms);
        ++frames_done;

        // Validate only once (host copy is expensive and skews perf).
        if (!did_validate) {
            auto bev_host = out.bev.to_host(&queue);
            auto stats = compute_stats(bev_host);
            std::cout << "bev numel: " << bev_host.size() << ", min=" << stats.min_v << ", max=" << stats.max_v
                      << ", mean_abs=" << stats.mean_abs << std::endl;
            did_validate = true;
        }
    }

    if (frames_done == 0) {
        std::cout << "[perf] frames=0" << std::endl;
        return 0;
    }

    std::cout << "[perf] frames=" << frames_done << ", avg_camera_bev=" << (sum_ms / static_cast<double>(frames_done))
              << " ms, min=" << min_ms << " ms, max=" << max_ms << " ms" << std::endl;

    cam_bev.print_latency_stats();

    return 0;
}
