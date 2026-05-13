#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <fstream>
#include <string>
#include <vector>

#include "bev.h"
#include "camera-geometry.hpp"
#include "test_utils.hpp"

namespace {

struct SimpleStats {
    float min_v{0.0f};
    float max_v{0.0f};
    double mean_abs{0.0};
};

SimpleStats compute_stats(const std::vector<float>& v) {
    SimpleStats s;
    if (v.empty()) return s;

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

bool load_or_generate_calib(unsigned int num_camera,
                            int image_width,
                            int image_height,
                            std::vector<float>& camera2lidar,
                            std::vector<float>& intrinsics,
                            std::vector<float>& img_aug,
                            std::vector<float>& denorms) {
    try {
        camera2lidar = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera2lidar.bin");
        intrinsics = load_matrix_from_bin("../data/v2xfusion/dump_bins/camera_intrinsics.bin");
        img_aug = load_matrix_from_bin("../data/v2xfusion/dump_bins/img_aug_matrix.bin");
        denorms = load_matrix_from_bin("../data/v2xfusion/dump_bins/denorms.bin");
        return true;
    } catch (...) {
        camera2lidar.resize(num_camera * 16);
        intrinsics.resize(num_camera * 16);
        img_aug.resize(num_camera * 16);
        denorms.resize(num_camera * 4);

        for (unsigned int i = 0; i < num_camera; ++i) {
            auto c2l = generate_test_camera2lidar_matrix(static_cast<int>(i));
            auto intr = generate_test_camera_intrinsics(static_cast<int>(i), image_width, image_height);
            auto aug = generate_test_img_aug_matrix(static_cast<int>(i));
            std::copy(c2l.begin(), c2l.end(), camera2lidar.begin() + i * 16);
            std::copy(intr.begin(), intr.end(), intrinsics.begin() + i * 16);
            std::copy(aug.begin(), aug.end(), img_aug.begin() + i * 16);
        }
        return false;
    }
}

double to_ms(std::chrono::steady_clock::duration d) {
    return std::chrono::duration<double, std::milli>(d).count();
}

bool try_load_bin_f32(const std::string& path, std::vector<float>& out, size_t expected_elems) {
    std::ifstream fin(path, std::ios::binary | std::ios::ate);
    if (!fin.is_open()) return false;

    const std::streamsize bytes = fin.tellg();
    if (bytes < 0) return false;
    if (static_cast<size_t>(bytes) != expected_elems * sizeof(float)) {
        std::cerr << "[warn] " << path << " size mismatch: got " << static_cast<size_t>(bytes)
                  << " bytes, expected " << (expected_elems * sizeof(float)) << " bytes" << std::endl;
        return false;
    }

    fin.seekg(0, std::ios::beg);
    out.resize(expected_elems);
    if (!fin.read(reinterpret_cast<char*>(out.data()), static_cast<std::streamsize>(expected_elems * sizeof(float)))) {
        out.clear();
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    int warmup_iters = 10;
    int iters = 200;

    if (argc >= 2) warmup_iters = std::max(0, std::atoi(argv[1]));
    if (argc >= 3) iters = std::max(1, std::atoi(argv[2]));

    std::cout << "Usage: " << argv[0] << " [warmup_iters=10] [iters=200]" << std::endl;
    std::cout << "Warmup: " << warmup_iters << ", iterations: " << iters << std::endl;

    sycl::queue queue = create_opencl_queue();
    std::cout << "Device: " << queue.get_device().get_info<sycl::info::device::name>() << std::endl;

    // Geometry parameters (match v2xfusion defaults used by other tests).
    auto geom = bevfusion::camera::make_v2xfusion_geometry_parameter();

    auto geometry = bevfusion::camera::create_geometry(geom, queue);
    if (!geometry) {
        std::cerr << "Failed to create geometry" << std::endl;
        return -1;
    }

    std::vector<float> camera2lidar, intrinsics, img_aug, denorms;
    const bool loaded = load_or_generate_calib(geom.num_camera,
                                               geom.image_width,
                                               geom.image_height,
                                               camera2lidar,
                                               intrinsics,
                                               img_aug,
                                               denorms);
    std::cout << (loaded ? "Loaded" : "Generated") << " calibration matrices" << std::endl;

    geometry->update(camera2lidar.data(),
                     intrinsics.data(),
                     img_aug.data(),
                     denorms.data(),
                     &queue);

    auto indices_ptr = geometry->indices();
    auto intervals_ptr = geometry->intervals();
    const uint32_t num_intervals = geometry->num_intervals();

    std::cout << "Geometry: num_intervals=" << num_intervals
              << ", num_indices=" << geometry->num_indices() << std::endl;

    // Input/output tensor shapes.
    const uint32_t N = 1;
    const uint32_t C = 80;
    const uint32_t D = 90;
    const uint32_t H = 54;
    const uint32_t W = 96;
    const uint32_t BEV_W = 128;
    const uint32_t BEV_H = 128;

    const size_t camera_elems = static_cast<size_t>(N) * C * H * W;
    const size_t depth_elems = static_cast<size_t>(N) * D * H * W;
    const size_t bev_elems = static_cast<size_t>(C) * BEV_W * BEV_H;

    std::cout << "camera_elems=" << camera_elems << ", depth_elems=" << depth_elems
              << ", bev_elems=" << bev_elems << std::endl;

    float* d_camera = sycl::malloc_device<float>(camera_elems, queue);
    float* d_depth = sycl::malloc_device<float>(depth_elems, queue);
    float* d_bev = sycl::malloc_device<float>(bev_elems, queue);

    if (!d_camera || !d_depth || !d_bev) {
        std::cerr << "Failed to allocate USM device buffers" << std::endl;
        if (d_camera) sycl::free(d_camera, queue);
        if (d_depth) sycl::free(d_depth, queue);
        if (d_bev) sycl::free(d_bev, queue);
        return -1;
    }

    // Prefer loading inputs from bin files generated by other tests.
    // Fallback: initialize inputs with zeros (still useful for latency testing).
    {
        std::vector<float> camera_host;
        std::vector<float> depth_host;
        const bool loaded_cam = try_load_bin_f32("camera_features.bin", camera_host, camera_elems);
        const bool loaded_dep = try_load_bin_f32("camera_depth_weights.bin", depth_host, depth_elems);

        if (loaded_cam && loaded_dep) {
            std::cout << "Loaded inputs from camera_features.bin and camera_depth_weights.bin" << std::endl;
            queue.memcpy(d_camera, camera_host.data(), camera_elems * sizeof(float));
            queue.memcpy(d_depth, depth_host.data(), depth_elems * sizeof(float));
        } else {
            std::cout << "Input bin files not found (or invalid). Using zero-filled inputs." << std::endl;
            queue.memset(d_camera, 0, camera_elems * sizeof(float));
            queue.memset(d_depth, 0, depth_elems * sizeof(float));
        }
    }
    queue.memset(d_bev, 0, bev_elems * sizeof(float));
    queue.wait_and_throw();

    Bound xBound{geom.xbound.x, geom.xbound.y, geom.xbound.z};
    Bound yBound{geom.ybound.x, geom.ybound.y, geom.ybound.z};
    Bound zBound{geom.zbound.x, geom.zbound.y, geom.zbound.z};
    Bound dBound{geom.dbound.x, geom.dbound.y, geom.dbound.z};

    Bev bev(queue,
            /*inputChannels=*/C,
            /*outputChannels=*/C,
            /*imageWidth=*/geom.image_width,
            /*imageHeight=*/geom.image_height,
            /*featureWidth=*/geom.feat_width,
            /*featureHeight=*/geom.feat_height,
            xBound,
            yBound,
            zBound,
            dBound);

    auto run_once = [&]() -> uint32_t {
        return bev.bevPool(d_camera,
                           d_depth,
                           indices_ptr,
                           intervals_ptr,
                           d_bev,
                           num_intervals,
                           N,
                           C,
                           D,
                           H,
                           W,
                           BEV_W,
                           BEV_H);
    };

    // Warmup.
    for (int i = 0; i < warmup_iters; ++i) {
        const uint32_t rc = run_once();
        queue.wait_and_throw();
        if (rc != 0) {
            std::cerr << "bevPool failed during warmup, rc=" << rc << std::endl;
            sycl::free(d_camera, queue);
            sycl::free(d_depth, queue);
            sycl::free(d_bev, queue);
            return -1;
        }
    }

    // Timed loop.
    std::vector<double> times_ms;
    times_ms.reserve(static_cast<size_t>(iters));

    for (int i = 0; i < iters; ++i) {
        const auto t0 = std::chrono::steady_clock::now();
        const uint32_t rc = run_once();
        queue.wait_and_throw();
        const auto t1 = std::chrono::steady_clock::now();

        if (rc != 0) {
            std::cerr << "bevPool failed, iter=" << i << ", rc=" << rc << std::endl;
            break;
        }

        times_ms.push_back(to_ms(t1 - t0));

        if ((i + 1) % 50 == 0) {
            std::cout << "Progress: " << (i + 1) << "/" << iters
                      << ", last=" << std::fixed << std::setprecision(3) << times_ms.back() << " ms" << std::endl;
        }
    }

    if (times_ms.empty()) {
        std::cerr << "No successful iterations" << std::endl;
        sycl::free(d_camera, queue);
        sycl::free(d_depth, queue);
        sycl::free(d_bev, queue);
        return -1;
    }

    const auto [min_it, max_it] = std::minmax_element(times_ms.begin(), times_ms.end());
    const double sum = std::accumulate(times_ms.begin(), times_ms.end(), 0.0);
    const double avg = sum / static_cast<double>(times_ms.size());

    std::cout << "\n=== BEVPool Latency ===" << std::endl;
    std::cout << "Iters: " << times_ms.size() << std::endl;
    std::cout << "Avg: " << std::fixed << std::setprecision(3) << avg << " ms" << std::endl;
    std::cout << "Min: " << std::fixed << std::setprecision(3) << *min_it << " ms" << std::endl;
    std::cout << "Max: " << std::fixed << std::setprecision(3) << *max_it << " ms" << std::endl;
    std::cout << "Throughput: " << std::fixed << std::setprecision(1) << (1000.0 / avg) << " it/s" << std::endl;

    // Basic output sanity check (copy once).
    std::vector<float> bev_host(bev_elems);
    queue.memcpy(bev_host.data(), d_bev, bev_elems * sizeof(float)).wait();
    auto stats = compute_stats(bev_host);
    std::cout << "bev numel: " << bev_host.size() << ", min=" << stats.min_v << ", max=" << stats.max_v
              << ", mean_abs=" << stats.mean_abs << std::endl;

    sycl::free(d_camera, queue);
    sycl::free(d_depth, queue);
    sycl::free(d_bev, queue);

    return 0;
}
