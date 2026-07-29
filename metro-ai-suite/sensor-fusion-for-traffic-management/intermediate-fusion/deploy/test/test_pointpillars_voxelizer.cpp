// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pointpillars/voxelizer.hpp"
#include "test_utils.hpp"

#include <sycl/sycl.hpp>

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Args {
    bool synthetic{true};
    bool dump_outputs{false};
    std::string points_path;
    int num_points{0};
    int point_dim{4};
    std::filesystem::path out_dir{"/tmp/pointpillars_voxelizer_out"};
    float pc_range[6] = {0.0f, -51.2f, -5.0f, 102.4f, 51.2f, 3.0f};
    float voxel_size[3] = {0.8f, 0.8f, 8.0f};
    int max_num_pts_per_voxel{100};
    int max_voxels{12000};
};

void print_usage(const char* argv0)
{
    std::cerr << "Usage: " << argv0 << " [--synthetic] "
              << "[--points POINTS.bin --num N] [--dim 4] "
              << "[--max-voxels 12000] [--max-pts-per-voxel 100] "
              << "[--out-dir DIR] [--dump]\n";
}

Args parse_args(int argc, char** argv)
{
    Args args;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error(key + " requires a value");
            }
            return argv[++i];
        };

        if (key == "--help" || key == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else if (key == "--synthetic") {
            args.synthetic = true;
        } else if (key == "--points") {
            args.points_path = next();
            args.synthetic = false;
        } else if (key == "--num") {
            args.num_points = std::atoi(next().c_str());
        } else if (key == "--dim") {
            args.point_dim = std::atoi(next().c_str());
        } else if (key == "--out-dir") {
            args.out_dir = next();
            args.dump_outputs = true;
        } else if (key == "--dump") {
            args.dump_outputs = true;
        } else if (key == "--max-voxels") {
            args.max_voxels = std::atoi(next().c_str());
        } else if (key == "--max-pts-per-voxel") {
            args.max_num_pts_per_voxel = std::atoi(next().c_str());
        } else {
            throw std::runtime_error("Unknown arg: " + key);
        }
    }

    if (!args.synthetic && (args.points_path.empty() || args.num_points <= 0)) {
        throw std::runtime_error("--points mode requires --points and --num");
    }
    return args;
}

std::vector<float> load_points(const std::string& path, int num_points, int point_dim)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("cannot open " + path);
    }

    std::vector<float> points(static_cast<size_t>(num_points) * point_dim);
    file.read(reinterpret_cast<char*>(points.data()),
              static_cast<std::streamsize>(points.size() * sizeof(float)));
    if (!file) {
        throw std::runtime_error("short read on " + path);
    }
    return points;
}

template <typename T>
void dump_bin(const std::filesystem::path& path, const std::vector<T>& values)
{
    std::ofstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("cannot write " + path.string());
    }
    file.write(reinterpret_cast<const char*>(values.data()),
               static_cast<std::streamsize>(values.size() * sizeof(T)));
}

void configure_synthetic(Args& args)
{
    const float pc_range[6] = {0.0f, -1.0f, 0.0f, 2.0f, 1.0f, 1.0f};
    const float voxel_size[3] = {1.0f, 1.0f, 1.0f};
    std::memcpy(args.pc_range, pc_range, sizeof(pc_range));
    std::memcpy(args.voxel_size, voxel_size, sizeof(voxel_size));
    args.point_dim = 4;
    args.max_num_pts_per_voxel = 2;
    args.max_voxels = 4;
    args.num_points = 4;
}

std::vector<float> synthetic_points()
{
    return {
        0.10f, -0.90f, 0.10f, 1.0f,
        1.10f,  0.10f, 0.10f, 2.0f,
       -0.10f,  0.00f, 0.10f, 3.0f,
        2.10f,  0.00f, 0.10f, 4.0f,
    };
}

bool close_enough(float lhs, float rhs)
{
    return std::fabs(lhs - rhs) < 1e-5f;
}

bool validate_synthetic(int voxel_count,
                        const std::vector<float>& features,
                        const std::vector<int>& num_voxels,
                        const std::vector<int>& coors,
                        const pointpillars::VoxelizerConfig& cfg)
{
    if (voxel_count != 2) {
        std::cerr << "Expected 2 valid voxels, got " << voxel_count << "\n";
        return false;
    }

    bool saw_first = false;
    bool saw_second = false;
    const size_t points_per_voxel = static_cast<size_t>(cfg.max_num_points_per_voxel);
    const size_t point_dim = static_cast<size_t>(cfg.point_dim);

    for (int row = 0; row < voxel_count; ++row) {
        const int* coor = coors.data() + row * 4;
        const float* feat = features.data() + static_cast<size_t>(row) * points_per_voxel * point_dim;
        if (coor[0] != 0 || coor[3] != 0 || num_voxels[row] != 1) {
            std::cerr << "Unexpected row metadata at row " << row << "\n";
            return false;
        }
        if (!close_enough(feat[4], 0.0f) || !close_enough(feat[5], 0.0f) ||
            !close_enough(feat[6], 0.0f) || !close_enough(feat[7], 0.0f)) {
            std::cerr << "Padding for row " << row << " was not zeroed\n";
            return false;
        }

        if (coor[1] == 0 && coor[2] == 0) {
            saw_first = close_enough(feat[0], 0.10f) && close_enough(feat[1], -0.90f) &&
                        close_enough(feat[2], 0.10f) && close_enough(feat[3], 1.0f);
        } else if (coor[1] == 1 && coor[2] == 1) {
            saw_second = close_enough(feat[0], 1.10f) && close_enough(feat[1], 0.10f) &&
                         close_enough(feat[2], 0.10f) && close_enough(feat[3], 2.0f);
        } else {
            std::cerr << "Unexpected voxel coordinate: (" << coor[0] << "," << coor[1]
                      << "," << coor[2] << "," << coor[3] << ")\n";
            return false;
        }
    }
    return saw_first && saw_second;
}

}  // namespace

int main(int argc, char** argv)
{
    Args args;
    try {
        args = parse_args(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        print_usage(argv[0]);
        return 2;
    }

    if (args.synthetic) {
        configure_synthetic(args);
    }

    try {
        sycl::queue queue = create_opencl_queue();
        std::cout << "Device: " << queue.get_device().get_info<sycl::info::device::name>() << "\n";

        pointpillars::VoxelizerConfig cfg;
        std::memcpy(cfg.pc_range.data(), args.pc_range, sizeof(args.pc_range));
        std::memcpy(cfg.voxel_size.data(), args.voxel_size, sizeof(args.voxel_size));
        cfg.max_num_points_per_voxel = args.max_num_pts_per_voxel;
        cfg.max_voxels = args.max_voxels;
        cfg.point_dim = args.point_dim;

        pointpillars::Voxelizer voxelizer(queue, cfg);

        std::vector<float> host_points = args.synthetic
            ? synthetic_points()
            : load_points(args.points_path, args.num_points, args.point_dim);

        float* device_points = sycl::malloc_device<float>(host_points.size(), queue);
        if (!device_points) {
            throw std::runtime_error("failed to allocate device point buffer");
        }
        queue.memcpy(device_points, host_points.data(), host_points.size() * sizeof(float)).wait();

        const int voxel_count = voxelizer.run(device_points, args.num_points);
        queue.wait_and_throw();
        std::cout << "voxelizer returned V=" << voxel_count << " (max=" << cfg.max_voxels << ")\n";

        const size_t max_voxels = static_cast<size_t>(cfg.max_voxels);
        const size_t max_points = static_cast<size_t>(cfg.max_num_points_per_voxel);
        const size_t point_dim = static_cast<size_t>(cfg.point_dim);

        std::vector<float> features(max_voxels * max_points * point_dim);
        std::vector<int> num_voxels(max_voxels);
        std::vector<int> coors(max_voxels * 4);
        queue.memcpy(features.data(), voxelizer.features_device(), features.size() * sizeof(float)).wait();
        queue.memcpy(num_voxels.data(), voxelizer.num_voxels_device(), num_voxels.size() * sizeof(int)).wait();
        queue.memcpy(coors.data(), voxelizer.coors_device(), coors.size() * sizeof(int)).wait();

        bool ok = true;
        if (args.synthetic) {
            ok = validate_synthetic(voxel_count, features, num_voxels, coors, cfg);
            std::cout << (ok ? "Synthetic voxelizer check passed" : "Synthetic voxelizer check failed") << "\n";
        }

        if (args.dump_outputs) {
            std::filesystem::create_directories(args.out_dir);
            dump_bin<float>(args.out_dir / "features.bin", features);
            dump_bin<int>(args.out_dir / "num_voxels.bin", num_voxels);
            dump_bin<int>(args.out_dir / "coors.bin", coors);
            std::ofstream meta(args.out_dir / "meta.txt");
            meta << "V=" << voxel_count << "\n";
            meta << "V_max=" << cfg.max_voxels << "\n";
            meta << "N=" << cfg.max_num_points_per_voxel << "\n";
            meta << "C=" << cfg.point_dim << "\n";
            std::cout << "Dumped to " << args.out_dir.string() << "\n";
        }

        sycl::free(device_points, queue);
        return ok ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << "\n";
        return 1;
    }
}
