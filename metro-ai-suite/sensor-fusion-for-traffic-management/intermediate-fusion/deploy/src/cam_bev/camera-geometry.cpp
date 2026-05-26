/*
 * SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include <sycl/sycl.hpp>
#include <oneapi/dpl/algorithm>
#include <oneapi/dpl/execution>

#include "camera-geometry.hpp"
// #include "tensor.hpp"

namespace bevfusion {
namespace camera {

struct GeometryParameterExtra : public GeometryParameter { 
  float D;
  types::Float3 dx;
  types::Float3 bx;
  types::Int3 nx;
  // Ray-related parameters
  types::Float3 dbound_rays;       // [near, far, step] for ray method
  sycl::float3* denorms;           // Normal vector data

  bool use_rays_method() const {
    return fusion_method == FusionMethod::V2XFUSION;
  }
};

// SYCL helper functions
inline float dot(const sycl::float4& T, const sycl::float3& p) { 
  return T.x() * p.x() + T.y() * p.y() + T.z() * p.z(); 
}
inline float dot4(const sycl::float4& T, const sycl::float4& p) { 
  return T.x() * p.x() + T.y() * p.y() + T.z() * p.z() + T.w() * p.w(); 
}

inline float project(const sycl::float4& T, const sycl::float3& p) {
  return T.x() * p.x() + T.y() * p.y() + T.z() * p.z() + T.w();
}

inline sycl::float3 inverse_project(const sycl::float4* T, const sycl::float3& p) {
  sycl::float3 r;
  r.x() = p.x() - T[0].w();
  r.y() = p.y() - T[1].w();
  r.z() = p.z() - T[2].w();
  return sycl::float3(dot(T[0], r), dot(T[1], r), dot(T[2], r));
}

// Host function for matrix inversion
static void matrix_inverse_4x4(const float* m, float* inv) {
  double det = m[0] * (m[5] * m[10] - m[9] * m[6]) - m[1] * (m[4] * m[10] - m[6] * m[8]) + m[2] * (m[4] * m[9] - m[5] * m[8]);
  double invdet = 1.0 / det;
  inv[0] = (m[5] * m[10] - m[9] * m[6]) * invdet;
  inv[1] = (m[2] * m[9] - m[1] * m[10]) * invdet;
  inv[2] = (m[1] * m[6] - m[2] * m[5]) * invdet;
  inv[3] = m[3];
  inv[4] = (m[6] * m[8] - m[4] * m[10]) * invdet;
  inv[5] = (m[0] * m[10] - m[2] * m[8]) * invdet;
  inv[6] = (m[4] * m[2] - m[0] * m[6]) * invdet;
  inv[7] = m[7];
  inv[8] = (m[4] * m[9] - m[8] * m[5]) * invdet;
  inv[9] = (m[8] * m[1] - m[0] * m[9]) * invdet;
  inv[10] = (m[0] * m[5] - m[4] * m[1]) * invdet;
  inv[11] = m[11];
  inv[12] = m[12];
  inv[13] = m[13];
  inv[14] = m[14];
  inv[15] = m[15];
}

static void matrix_inverse_affine_4x4_v2x(const float* m, float* inv) {
    // ---------- 1) Read R (3×3) row-major ----------
    double R[9];
    R[0] = m[0];  R[1] = m[1];  R[2] = m[2];    // Row 0
    R[3] = m[4];  R[4] = m[5];  R[5] = m[6];    // Row 1
    R[6] = m[8];  R[7] = m[9];  R[8] = m[10];   // Row 2

    // ---------- 2) Calculate determinant of R ----------
    double det = R[0] * (R[4] * R[8] - R[5] * R[7])
               - R[1] * (R[3] * R[8] - R[5] * R[6])
               + R[2] * (R[3] * R[7] - R[4] * R[6]);

    if (fabs(det) < 1e-12) {
        for (int i = 0; i < 16; ++i) inv[i] = (i % 5 == 0) ? 1.0f : 0.0f;
        return;
    }

    double invdet = 1.0 / det;

    // ---------- 3) Calculate R⁻¹ ----------
    double Rinv[9];
    Rinv[0] =  (R[4] * R[8] - R[5] * R[7]) * invdet;
    Rinv[1] = -(R[1] * R[8] - R[2] * R[7]) * invdet;
    Rinv[2] =  (R[1] * R[5] - R[2] * R[4]) * invdet;

    Rinv[3] = -(R[3] * R[8] - R[5] * R[6]) * invdet;
    Rinv[4] =  (R[0] * R[8] - R[2] * R[6]) * invdet;
    Rinv[5] = -(R[0] * R[5] - R[2] * R[3]) * invdet;

    Rinv[6] =  (R[3] * R[7] - R[4] * R[6]) * invdet;
    Rinv[7] = -(R[0] * R[7] - R[1] * R[6]) * invdet;
    Rinv[8] =  (R[0] * R[4] - R[1] * R[3]) * invdet;

    // ---------- 4) Read translation vector t (row-major) ----------
    double t[3];
    t[0] = m[3];   // Row 0 Col 3: -0.196185
    t[1] = m[7];   // Row 1 Col 3: -2.05623
    t[2] = m[11];  // Row 2 Col 3: 6.47943

    // ---------- 5) Calculate -R⁻¹ * t ----------
    double nt[3];
    nt[0] = -(Rinv[0] * t[0] + Rinv[1] * t[1] + Rinv[2] * t[2]);
    nt[1] = -(Rinv[3] * t[0] + Rinv[4] * t[1] + Rinv[5] * t[2]);
    nt[2] = -(Rinv[6] * t[0] + Rinv[7] * t[1] + Rinv[8] * t[2]);

    // ---------- 6) Write result back to inv (row-major) ----------
    // Row 0
    inv[0]  = static_cast<float>(Rinv[0]);  
    inv[1]  = static_cast<float>(Rinv[1]);  
    inv[2]  = static_cast<float>(Rinv[2]);  
    inv[3]  = static_cast<float>(nt[0]);    // Translation part

    // Row 1
    inv[4]  = static_cast<float>(Rinv[3]);  
    inv[5]  = static_cast<float>(Rinv[4]);  
    inv[6]  = static_cast<float>(Rinv[5]);  
    inv[7]  = static_cast<float>(nt[1]);    // Translation part

    // Row 2
    inv[8]  = static_cast<float>(Rinv[6]);  
    inv[9]  = static_cast<float>(Rinv[7]);  
    inv[10] = static_cast<float>(Rinv[8]);  
    inv[11] = static_cast<float>(nt[2]);    // Translation part

    // Row 3
    inv[12] = 0.0f;
    inv[13] = 0.0f;
    inv[14] = 0.0f;
    inv[15] = 1.0f;
}

class GeometryImplement : public Geometry {
 public:
  GeometryImplement(sycl::queue& q) : queue_(q) {}

  virtual ~GeometryImplement() {
    free_excess_memory();
  }

  bool init(GeometryParameter param) {
    static_cast<GeometryParameter&>(param_) = param;
    param_.D = param_.dbound.z;
    param_.bx = types::Float3(param_.xbound.x + param_.xbound.z / 2.0f, param_.ybound.x + param_.ybound.z / 2.0f,
                              param_.zbound.x + param_.zbound.z / 2.0f);

    param_.dx = types::Float3(param_.xbound.z, param_.ybound.z, param_.zbound.z);
    param_.nx = types::Int3(static_cast<int>(std::round((param_.xbound.y - param_.xbound.x) / param_.xbound.z)),
                            static_cast<int>(std::round((param_.ybound.y - param_.ybound.x) / param_.ybound.z)),
                            static_cast<int>(std::round((param_.zbound.y - param_.zbound.x) / param_.zbound.z)));

    float w_interval = (param_.image_width - 1.0f) / (param_.feat_width - 1.0f);
    float h_interval = (param_.image_height - 1.0f) / (param_.feat_height - 1.0f);
    numel_frustum_ = param_.feat_width * param_.feat_height * param_.D;
    numel_geometry_ = numel_frustum_ * param_.num_camera;
#ifdef _DEBUG
std::cout << "=== Geometry Parameters Debug ===" << std::endl;
std::cout << "X bound: [" << param_.xbound.x << ", " << param_.xbound.y << "], step: " << param_.xbound.z << std::endl;
std::cout << "Y bound: [" << param_.ybound.x << ", " << param_.ybound.y << "], step: " << param_.ybound.z << std::endl;
std::cout << "Z bound: [" << param_.zbound.x << ", " << param_.zbound.y << "], step: " << param_.zbound.z << std::endl;
std::cout << "D bound: [" << param_.dbound.x << ", " << param_.dbound.y << "], step: " << param_.dbound.z << std::endl;

std::cout << "Computed parameters:" << std::endl;
std::cout << "D: " << param_.D << std::endl;
std::cout << "nx: [" << param_.nx.x << ", " << param_.nx.y << ", " << param_.nx.z << "]" << std::endl;
std::cout << "dx: [" << param_.dx.x << ", " << param_.dx.y << ", " << param_.dx.z << "]" << std::endl;
std::cout << "bx: [" << param_.bx.x << ", " << param_.bx.y << ", " << param_.bx.z << "]" << std::endl;

// Check for invalid values
if (param_.D == 0) {
    std::cout << "ERROR: D is 0!" << std::endl;
}
if (param_.nx.x <= 0 || param_.nx.y <= 0 || param_.nx.z <= 0) {
    std::cout << "ERROR: Invalid nx values!" << std::endl;
}
#endif

    try {
      // Allocate device memory
      keep_count_ = sycl::malloc_device<unsigned int>(1, queue_);
      frustum_ = sycl::malloc_device<sycl::float3>(numel_frustum_, queue_);
      geometry_ = sycl::malloc_device<int32_t>(numel_geometry_, queue_);
      ranks_ = sycl::malloc_device<int32_t>(numel_geometry_, queue_);
      indices_ = sycl::malloc_device<int32_t>(numel_geometry_, queue_);
      interval_starts_ = sycl::malloc_device<int32_t>(numel_geometry_, queue_);
      interval_starts_size_ = sycl::malloc_device<int32_t>(1, queue_);
      intervals_ = sycl::malloc_device<types::Int3>(numel_geometry_, queue_);

      bytes_of_matrix_ = param_.num_camera * 4 * 4 * sizeof(float);
      camera2lidar_ = sycl::malloc_device<float>(param_.num_camera * 16, queue_);
      camera_intrinsics_inverse_ = sycl::malloc_device<float>(param_.num_camera * 16, queue_);
      img_aug_matrix_inverse_ = sycl::malloc_device<float>(param_.num_camera * 16, queue_);
      ego2camera_ = sycl::malloc_device<float>(param_.num_camera * 16, queue_); 
      // Allocate host memory
      counter_host_ = sycl::malloc_host<int32_t>(1, queue_);
      camera_intrinsics_inverse_host_ = sycl::malloc_host<float>(param_.num_camera * 16, queue_);
      img_aug_matrix_inverse_host_ = sycl::malloc_host<float>(param_.num_camera * 16, queue_);
      ego2camera_host_ = sycl::malloc_host<float>(param_.num_camera * 16, queue_);

      // Create frustum
      if (param_.use_rays_method())
      //v2xfusion ray method
      {
        std::cout << "Initializing V2XFusion geometry with ray method" << std::endl;
        // Calculate ray-related memory size
        rays_numel_ = param_.feat_height * param_.feat_width;
        frustum_rays_numel_ = param_.D * param_.feat_height * param_.feat_width;

        // Allocate ray-related memory
        rays_ = sycl::malloc_device<sycl::float4>(rays_numel_, queue_);
        frustum_rays_ = sycl::malloc_device<sycl::float4>(frustum_rays_numel_, queue_);
        denorms_device_ = sycl::malloc_device<sycl::float4>(param_.num_camera, queue_);

        // Initialize ray data
        create_rays();
        create_frustum_rays();
      }
      else
      {
        std::cout << "Initializing BEVFusion geometry with frustum method" << std::endl;
        // Use bevfusion original frustum method 
        create_frustum(w_interval, h_interval);
      }

      return true;
    } catch (const sycl::exception& e) {
      std::cerr << "[camera::Geometry] init failed with SYCL exception: " << e.what() << std::endl;
      return false;
    }
  }

    void create_rays() {
        auto feat_height = param_.feat_height;
        auto feat_width = param_.feat_width;
        auto og_height = param_.image_height;
        auto og_width = param_.image_width;
        auto rays = rays_;
        
        queue_.parallel_for(sycl::range<2>(feat_height, feat_width), 
            [=](sycl::id<2> idx) {
            int iy = idx[0];
            int ix = idx[1];
            unsigned int offset = iy * feat_width + ix;
        // Use float math to avoid requiring fp64 on OpenCL devices.
        float x_step = (feat_width == 1) ? 0.0f : float(og_width - 1) / float(feat_width - 1);
        float y_step = (feat_height == 1) ? 0.0f : float(og_height - 1) / float(feat_height - 1);

        float x_coord = sycl::fma(float(ix), x_step, 0.0f);
        float y_coord = sycl::fma(float(iy), y_step, 0.0f);
            
            rays[offset] = sycl::float4(x_coord, y_coord, 1.0f, 1.0f);
            }).wait();
    }

    void create_frustum_rays() {
      auto D = param_.dbound.z;
        auto feat_height = param_.feat_height;
        auto feat_width = param_.feat_width;
        auto og_height = param_.image_height;
        auto og_width = param_.image_width;
      float dbound_min = 0.0f;
      float dbound_max = 1.0f;
        auto frustum_rays = frustum_rays_;
        
        queue_.parallel_for(sycl::range<3>(D, feat_height, feat_width), 
            [=](sycl::id<3> idx) {
            int id = idx[0];
            int iy = idx[1];
            int ix = idx[2];
            unsigned int offset = (id * feat_height + iy) * feat_width + ix;
            
        // Use float math to avoid requiring fp64 on OpenCL devices.
        float x_coord = float(ix) * float(og_width - 1) / float(feat_width - 1);
        float y_coord = float(iy) * float(og_height - 1) / float(feat_height - 1);

        float depth_ratio;
        if (D == 1) {
          depth_ratio = 0.0f;
            } else {
          depth_ratio = float(id) / float(D);
            }
            
        float alpha = 1.5f;
        depth_ratio = sycl::pow(depth_ratio, alpha);
        float d_coord = dbound_min + depth_ratio * (dbound_max - dbound_min);
            
            frustum_rays[offset] = sycl::float4(x_coord, y_coord, d_coord, 1.0f);
            }).wait();
    }
    void create_frustum(float w_interval, float h_interval) {
        auto D = param_.D;
        auto feat_height = param_.feat_height;
        auto feat_width = param_.feat_width;
        auto dbound_x = param_.dbound.x;
        auto dbound_z = param_.dbound.z;
        auto frustum = frustum_;
        queue_.parallel_for(sycl::range<3>(D, feat_height, feat_width), [=](sycl::id<3> idx) {
            int id = idx[0];
            int iy = idx[1];
            int ix = idx[2];
            unsigned int offset = (id * feat_height + iy) * feat_width + ix;
            frustum[offset] = sycl::float3(ix * w_interval, iy * h_interval, dbound_x + id * dbound_z);
        }).wait();
        queue_.parallel_for(sycl::range<1>(numel_frustum_), [=](sycl::id<1> tid) {
            sycl::float3 point = frustum[tid];
        }).wait();
    }

    virtual void update(const float* camera2lidar, const float* camera_intrinsics, const float* img_aug_matrix,const float* denorms =nullptr,
                        sycl::queue* q = nullptr) override {
        if (!frustum_) {
            throw std::runtime_error("Excess memory has been freed, update call is not logical");
        }
        if (param_.use_rays_method()) {
            if (!denorms) {
                throw std::runtime_error("V2XFusion method requires denorms parameter");
            }
            if (!rays_) {
                throw std::runtime_error("V2XFusion: Excess memory has been freed, update call is not logical");
            }
        } else {
            if (!frustum_) {
                throw std::runtime_error("BEVFusion: Excess memory has been freed, update call is not logical");
            }
        }

        sycl::queue& current_queue = q ? *q : queue_;

        // Compute inverse matrices on host
        for (unsigned int icamera = 0; icamera < param_.num_camera; ++icamera) {
            unsigned int offset = icamera * 16;
            matrix_inverse_affine_4x4_v2x(camera_intrinsics + offset, camera_intrinsics_inverse_host_ + offset);
            matrix_inverse_affine_4x4_v2x(img_aug_matrix + offset, img_aug_matrix_inverse_host_ + offset);
            matrix_inverse_affine_4x4_v2x(camera2lidar + offset, ego2camera_host_ + offset); // Calculate inverse of camera2lidar matrix
        }
        // Copy matrices to device
        current_queue.memcpy(camera2lidar_, camera2lidar, bytes_of_matrix_);
        current_queue.memcpy(camera_intrinsics_inverse_, camera_intrinsics_inverse_host_, bytes_of_matrix_);
        current_queue.memcpy(img_aug_matrix_inverse_, img_aug_matrix_inverse_host_, bytes_of_matrix_);
        current_queue.memcpy(ego2camera_, ego2camera_host_, bytes_of_matrix_);
        current_queue.memset(keep_count_, 0, sizeof(unsigned int));
        current_queue.wait();

        // Compute geometry
        if (param_.use_rays_method()) {
            std::cout << "Using V2XFusion ray-based geometry computation" << std::endl;
            queue_.memcpy(denorms_device_, denorms, 
                        param_.num_camera * sizeof(sycl::float4)).wait();
            
            // Use ray method to compute geometry
            compute_geometry_rays();
        } else {
            std::cout << "Using BEVFusion frustum-based geometry computation" << std::endl;
            compute_geometry();
        }
        // Copy counter back to host to get valid count
        current_queue.memcpy(counter_host_, keep_count_, sizeof(unsigned int)).wait();
        unsigned int valid_count = *counter_host_;

        #ifdef _DEBUG
        std::cout << "Total geometry points: " << numel_geometry_ << std::endl;
        std::cout << "Valid points (keep_count): " << valid_count << std::endl;
        #endif

        // Initialize indices array (0, 1, 2, ..., numel_geometry_-1)
        auto indices = indices_;
        auto ranks = ranks_;
        auto numel_geometry = numel_geometry_;
        current_queue.parallel_for(sycl::range<1>(numel_geometry), [=](sycl::id<1> idx) {
            indices[idx] = static_cast<int>(idx);
        }).wait();

        auto policy = oneapi::dpl::execution::make_device_policy(current_queue);
        oneapi::dpl::sort_by_key(policy, 
                                ranks_, ranks_ + numel_geometry_, 
                                indices_);

        unsigned int remain_ranks = numel_geometry_ - *counter_host_;
        unsigned int threads = *counter_host_ - 1;
        
        current_queue.memset(interval_starts_size_, 0, sizeof(int32_t));
        current_queue.memset(interval_starts_, 0, sizeof(int32_t));

        // Find interval starts
        auto interval_starts_size = interval_starts_size_;
        auto interval_starts = interval_starts_;
        auto threads_local = threads;
        auto remain_ranks_local = remain_ranks;
        if (threads_local > 0) {
            current_queue.parallel_for(sycl::range<1>(threads_local), [=](sycl::id<1> idx) {
                unsigned int i = remain_ranks_local + 1 + idx;
                if (ranks[i] != ranks[i - 1]) {
                    auto ref = sycl::atomic_ref<int32_t, 
                                                sycl::memory_order::relaxed, 
                                                sycl::memory_scope::device>(interval_starts_size[0]);
                    unsigned int offset = ref.fetch_add(1);
                    interval_starts[offset + 1] = idx + 1;
                }
            }).wait();
        }

        current_queue.memcpy(counter_host_, interval_starts_size_, sizeof(unsigned int)).wait();
        n_intervals_ = *counter_host_ + 1;

        // Sort interval starts
        std::sort(policy, interval_starts_, interval_starts_ + n_intervals_);

        // Collect intervals
        auto interval_starts_local = interval_starts_;
        auto geometry = geometry_;
        auto intervals = intervals_;
        auto n_intervals_local = n_intervals_;
        auto numel_geometry_local = numel_geometry_;
        current_queue.parallel_for(sycl::range<1>(n_intervals_local), [=](sycl::id<1> i) {
          types::Int3 val;
          val.x = static_cast<int>(interval_starts_local[i] + remain_ranks_local);
          val.y = static_cast<int>((i < n_intervals_local - 1) ? (interval_starts_local[i + 1] + remain_ranks_local) : (numel_geometry_local - 1));
          val.z = static_cast<int>(geometry[indices[interval_starts_local[i] + remain_ranks_local]]);
          intervals[i] = val;
        }).wait();
    }

    void compute_geometry_rays() {
        auto rays = rays_;
        auto frustum_rays = frustum_rays_;
        auto geometry = geometry_;
        auto ranks = ranks_;
        auto indices = indices_;
        auto keep_count = keep_count_;
        auto camera_intrinsics_inverse = camera_intrinsics_inverse_;
        auto img_aug_matrix_inverse = img_aug_matrix_inverse_;
        auto camera2ego = camera2lidar_;
        auto denorms = denorms_device_;
        auto param = param_;
        unsigned int numel_frustum = frustum_rays_numel_;
        auto ego2camera = ego2camera_;

        unsigned int original_numel_geometry = numel_geometry_;

        // Step1: compute all points
        queue_.parallel_for(sycl::range<1>(numel_frustum), [=](sycl::id<1> tid) {
            int total_idx = tid[0];
            int d_idx = total_idx / (param.feat_height * param.feat_width);
            int spatial_idx = total_idx % (param.feat_height * param.feat_width);
            int h_idx = spatial_idx / param.feat_width;
            int w_idx = spatial_idx % param.feat_width;
            
            for (int icamera = 0; icamera < param.num_camera; ++icamera) {
                // compute original index
                int original_idx = icamera * numel_frustum + tid[0];

                sycl::float4* img_aug_inv = reinterpret_cast<sycl::float4*>(img_aug_matrix_inverse) + icamera * 4;
                sycl::float4* cam_intrins_inv = reinterpret_cast<sycl::float4*>(camera_intrinsics_inverse) + icamera * 4;
                sycl::float4* cam2ego_ptr = reinterpret_cast<sycl::float4*>(camera2ego) + icamera * 4;
                sycl::float4* ego2cam_ptr = reinterpret_cast<sycl::float4*>(ego2camera) + icamera * 4;

                sycl::float4 origin_homo(0, 0, 0, 1);
                sycl::float3 O(
                    dot4(ego2cam_ptr[0], origin_homo),
                    dot4(ego2cam_ptr[1], origin_homo),
                    dot4(ego2cam_ptr[2], origin_homo)
                );

                // Step2. Get and normalize the normal vector
                sycl::float4 denorm_vec = denorms[icamera];
                sycl::float3 n(denorm_vec.x(), denorm_vec.y(), denorm_vec.z());
                
                float norm = sycl::sqrt(n.x() * n.x() + n.y() * n.y() + n.z() * n.z());
                if (norm < 1e-6f) {
                    ranks[original_idx] = 0; 
                    geometry[original_idx] = 0;
                    continue;
                }
                
                n = sycl::float3(n.x() / norm, n.y() / norm, n.z() / norm);

                
                // Step3: compute depth planes
                sycl::float3 P0 = O + param.dbound.x * n;
                sycl::float3 P1 = O + param.dbound.y * n;

                // Step4: get corresponding ray point
                int ray_idx = h_idx * param.feat_width + w_idx;
                sycl::float4 ray_point = rays[ray_idx];
                
                // Step5: compute combined transformation matrix: intrinsic_inv @ ida_inv
                sycl::float4 combined_matrix[4];
                for (int i = 0; i < 4; ++i) {
                    for (int j = 0; j < 4; ++j) {
                        float sum = 0.0f;
                        for (int k = 0; k < 4; ++k) {
                            sum += cam_intrins_inv[i][k] * img_aug_inv[k][j];
                        }
                        combined_matrix[i][j] = sum;
                    }
                }

                // Apply transformation: rays @ combined_matrix
                sycl::float3 ray_cam = sycl::float3(
                    dot4(combined_matrix[0], ray_point),
                    dot4(combined_matrix[1], ray_point),
                    dot4(combined_matrix[2], ray_point)
                );

                // Step6: normalize ray direction
                float ray_norm = sycl::sqrt(ray_cam.x() * ray_cam.x() + ray_cam.y() * ray_cam.y() + ray_cam.z() * ray_cam.z());
                if (ray_norm < 1e-6f) {
                    ranks[original_idx] = 0;
                    geometry[original_idx] = 0;
                    continue;
                }
                sycl::float3 dirs = ray_cam / ray_norm;

                // Step7: compute ray-plane intersection parameters
                float n_dot_P0 = n.x() * P0.x() + n.y() * P0.y() + n.z() * P0.z();
                float n_dot_P1 = n.x() * P1.x() + n.y() * P1.y() + n.z() * P1.z();
                float n_dot_dirs = n.x() * dirs.x() + n.y() * dirs.y() + n.z() * dirs.z();
                
                if (sycl::fabs(n_dot_dirs) < 1e-6f) {
                    ranks[original_idx] = 0;
                    geometry[original_idx] = 0;
                    continue;
                }
                
                float t0 = n_dot_P0 / n_dot_dirs;
                float t1 = n_dot_P1 / n_dot_dirs;

                // Step8: construct point using frustum_rays
                sycl::float4 frustum_point = frustum_rays[tid[0]];
                
                float gap = t0 - t1;
                float new_depth = (t0 - frustum_point.z() * gap) * dirs.z();

                sycl::float4 points = sycl::float4(
                    frustum_point.x(),
                    frustum_point.y(),
                    new_depth,
                    1.0f
                );
                
                // Step9: apply IDA inverse transformation
                sycl::float4 points_ida = sycl::float4(
                    dot4(img_aug_inv[0], points),
                    dot4(img_aug_inv[1], points),
                    dot4(img_aug_inv[2], points),
                    1.0f
                );
                            
                // Step10: perspective projection
                points_ida.x() *= points_ida.z();
                points_ida.y() *= points_ida.z();

                // Step11: final transformation to ego coordinate system
                sycl::float4 final_matrix[4];
                for (int i = 0; i < 4; ++i) {
                    for (int j = 0; j < 4; ++j) {
                        float sum = 0.0f;
                        for (int k = 0; k < 4; ++k) {
                            sum += cam2ego_ptr[i][k] * cam_intrins_inv[k][j];
                        }
                        final_matrix[i][j] = sum;
                    }
                }
            
                sycl::float3 ego_point = sycl::float3(
                    dot4(final_matrix[0], points_ida),
                    dot4(final_matrix[1], points_ida),
                    dot4(final_matrix[2], points_ida)
                );

                // Step12: compute grid coordinates
                sycl::int3 coords;
                coords.x() = static_cast<int>(sycl::floor((ego_point.x() - (param.bx.x - param.dx.x / 2.0f)) / param.dx.x));
                coords.y() = static_cast<int>(sycl::floor((ego_point.y() - (param.bx.y - param.dx.y / 2.0f)) / param.dx.y));
                coords.z() = static_cast<int>(sycl::floor((ego_point.z() - (param.bx.z - param.dx.z / 2.0f)) / param.dx.z));
    
                // Step13: boundary check
                bool kept = (coords.x() >= 0) && (coords.x() < param.nx.x) &&
                        (coords.y() >= 0) && (coords.y() < param.nx.y) &&
                        (coords.z() >= 0) && (coords.z() < param.nx.z);

                if (kept) {

                    unsigned int rank_value = coords.z() * (param.nx.x * param.nx.y) +
                                            coords.x() * param.nx.y +
                                            coords.y();


                    ranks[original_idx] = rank_value;
                    geometry[original_idx] = rank_value;

                    auto ref = sycl::atomic_ref<unsigned int,
                                            sycl::memory_order::relaxed,
                                            sycl::memory_scope::device>(keep_count[0]);
                    ref.fetch_add(1);
                } else {
                    ranks[original_idx] = -1;
                    geometry[original_idx] = -1;
                }
            }
        }).wait();

    }

    void compute_geometry()
        {
        // Capture all needed member variables as local variables
        auto frustum = frustum_;
        auto geometry = geometry_;
        auto ranks = ranks_;
        auto keep_count = keep_count_;
        auto camera2lidar = camera2lidar_;
        auto camera_intrinsics_inverse = camera_intrinsics_inverse_;
        auto img_aug_matrix_inverse = img_aug_matrix_inverse_;
        auto param = param_;
        unsigned int numel_frustum = numel_frustum_;
        queue_.parallel_for(sycl::range<1>(numel_frustum), [=](sycl::id<1> tid)
                            {
            sycl::float3 point = frustum[tid];
            bool debug_this_point = (tid[0] < 5);
            for (int icamera = 0; icamera < param.num_camera; ++icamera) {
                sycl::float4* img_aug_inv = reinterpret_cast<sycl::float4*>(img_aug_matrix_inverse) + icamera * 4;
                sycl::float4* cam_intrins_inv = reinterpret_cast<sycl::float4*>(camera_intrinsics_inverse) + icamera * 4;
                sycl::float4* cam2lidar_ptr = reinterpret_cast<sycl::float4*>(camera2lidar) + icamera * 4;
                sycl::float3 projed = inverse_project(img_aug_inv, point);
               

                projed.x() *= projed.z();
                projed.y() *= projed.z();
              
                projed = sycl::float3(dot(cam_intrins_inv[0], projed),
                                    dot(cam_intrins_inv[1], projed),
                                    dot(cam_intrins_inv[2], projed));
                                    
                projed = sycl::float3(project(cam2lidar_ptr[0], projed),
                                    project(cam2lidar_ptr[1], projed),
                                    project(cam2lidar_ptr[2], projed));
                                    
               
                int _pid = icamera * numel_frustum + tid[0];
                sycl::int3 coords;

                coords.x() = static_cast<int>(sycl::floor((projed.x() - (param.bx.x - param.dx.x / 2.0f)) / param.dx.x));
                coords.y() = static_cast<int>(sycl::floor((projed.y() - (param.bx.y - param.dx.y / 2.0f)) / param.dx.y));
                coords.z() = static_cast<int>(sycl::floor((projed.z() - (param.bx.z - param.dx.z / 2.0f)) / param.dx.z));
                geometry[_pid] = (coords.z() * param.geometry_dim.z * param.geometry_dim.y + coords.x()) * param.geometry_dim.x + coords.y();
                bool kept = coords.x() >= 0 && coords.y() >= 0 && coords.z() >= 0 &&
                        coords.x() < param.nx.x && coords.y() < param.nx.y && coords.z() < param.nx.z;
        #ifdef _DEBUG
                    if (debug_this_point && icamera == 0) {

                        sycl::ext::oneapi::experimental::printf("Point %d: projed=(%f,%f,%f), coords=(%d,%d,%d), kept=%d\n",
                            (int)tid[0], projed.x(), projed.y(), projed.z(), 
                            coords.x(), coords.y(), coords.z(), kept ? 1 : 0);
                    }
        #endif
                if (!kept) {
                ranks[_pid] = 0;
                } else {
                auto ref = sycl::atomic_ref<unsigned int,
                                            sycl::memory_order::relaxed,
                                            sycl::memory_scope::device>(keep_count[0]);
                ref.fetch_add(1);
                ranks[_pid] = (coords.x() * param.nx.y + coords.y()) * param.nx.z + coords.z();
                }
            } })
            .wait();
    }

  virtual void free_excess_memory() override {
    if (counter_host_) {
      sycl::free(counter_host_, queue_);
      counter_host_ = nullptr;
    }
    if (keep_count_) {
      sycl::free(keep_count_, queue_);
      keep_count_ = nullptr;
    }
    if (frustum_) {
      sycl::free(frustum_, queue_);
      frustum_ = nullptr;
    }
    if (geometry_) {
      sycl::free(geometry_, queue_);
      geometry_ = nullptr;
    }
    if (ranks_) {
      sycl::free(ranks_, queue_);
      ranks_ = nullptr;
    }
    if (interval_starts_) {
      sycl::free(interval_starts_, queue_);
      interval_starts_ = nullptr;
    }
    if (interval_starts_size_) {
      sycl::free(interval_starts_size_, queue_);
      interval_starts_size_ = nullptr;
    }
    if (camera2lidar_) {
      sycl::free(camera2lidar_, queue_);
      camera2lidar_ = nullptr;
    }
    if (camera_intrinsics_inverse_) {
      sycl::free(camera_intrinsics_inverse_, queue_);
      camera_intrinsics_inverse_ = nullptr;
    }
    if (img_aug_matrix_inverse_) {
      sycl::free(img_aug_matrix_inverse_, queue_);
      img_aug_matrix_inverse_ = nullptr;
    }
    if (camera_intrinsics_inverse_host_)
    {
      sycl::free(camera_intrinsics_inverse_host_, queue_);
      camera_intrinsics_inverse_host_ = nullptr;
    }
    if (img_aug_matrix_inverse_host_)
    {
      sycl::free(img_aug_matrix_inverse_host_, queue_);
      img_aug_matrix_inverse_host_ = nullptr;
    }
    if (rays_)
    {
      sycl::free(rays_, queue_);
      rays_ = nullptr;
    }
    if (frustum_rays_)
    {
      sycl::free(frustum_rays_, queue_);
      frustum_rays_ = nullptr;
    }
    if (denorms_device_)
    {
      sycl::free(denorms_device_, queue_);
      denorms_device_ = nullptr;
    }
      if (ego2camera_) {
      sycl::free(ego2camera_, queue_);
      ego2camera_ = nullptr;
    }
    if (ego2camera_host_) {
      sycl::free(ego2camera_host_, queue_);
      ego2camera_host_ = nullptr;
    }
  }

  virtual unsigned int num_intervals() override { return n_intervals_; }
  virtual unsigned int num_indices() override { return numel_geometry_; }
  virtual types::Int3* intervals() override { return intervals_; }
  virtual unsigned int* indices() override { return reinterpret_cast<unsigned int*>(indices_); }

 private:
  sycl::queue& queue_;
  size_t bytes_of_matrix_ = 0;
  float* camera2lidar_ = nullptr;
  float* camera_intrinsics_inverse_ = nullptr;
  float* img_aug_matrix_inverse_ = nullptr;
  float* camera_intrinsics_inverse_host_ = nullptr;
  float* img_aug_matrix_inverse_host_ = nullptr;

  sycl::float3* frustum_ = nullptr;
  unsigned int numel_frustum_ = 0;

  unsigned int n_intervals_ = 0;
  unsigned int numel_geometry_ = 0;
  int32_t* geometry_ = nullptr;
  int32_t* ranks_ = nullptr;
  int32_t* indices_ = nullptr;
  types::Int3* intervals_ = nullptr;
  int32_t* interval_starts_ = nullptr;
  int32_t* interval_starts_size_ = nullptr;
  unsigned int* keep_count_ = nullptr;
  int32_t* counter_host_ = nullptr;
  GeometryParameterExtra param_;
  // bool auto_free_memory_ = false;
  float* ego2camera_ = nullptr; 
  float* ego2camera_host_ = nullptr; 
  // Ray-related members
  sycl::float4* rays_ = nullptr;           // Ray data [H, W, 4]
  sycl::float4* frustum_rays_ = nullptr;   // Frustum rays [D, H, W, 4]
  sycl::float4* denorms_device_ = nullptr; // Device-side normal vectors
  unsigned int rays_numel_ = 0;
  unsigned int frustum_rays_numel_ = 0;
};

std::shared_ptr<Geometry> create_geometry(GeometryParameter param, sycl::queue& q) {
  std::shared_ptr<GeometryImplement> instance(new GeometryImplement(q));
  if (!instance->init(param)) {
    instance.reset();
  }
  return instance;
}

};  // namespace camera
};  // namespace bevfusion