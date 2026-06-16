#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include <opencv2/core.hpp>

#include "configs.hpp"

namespace bevfusion {

struct CameraMetas
{
    // Row-major; per-camera packed.
    // intrinsics/img_aug/camera2lidar are 4x4 each (16 floats).
    // denorms is 3 floats per camera (normal vector only, matching current SYCL impl).
    std::vector<float> camera2lidar;
    std::vector<float> intrinsics;
    std::vector<float> img_aug;
    std::vector<float> denorms;
};

namespace detail {

inline std::array<float, 16> mat4_identity()
{
    return {1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1};
}

inline std::array<float, 16> mat4_mul(const std::array<float, 16>& A, const std::array<float, 16>& B)
{
    std::array<float, 16> C{};
    for (int r = 0; r < 4; ++r) {
        for (int c = 0; c < 4; ++c) {
            float sum = 0.0f;
            for (int k = 0; k < 4; ++k) sum += A[r * 4 + k] * B[k * 4 + c];
            C[r * 4 + c] = sum;
        }
    }
    return C;
}

inline std::array<float, 16> mat4_inverse_rigid(const std::array<float, 16>& T)
{
    // Historical name; DO NOT assume orthonormal rotation here.
    // In some converted datasets, Tr_velo_to_cam may not be perfectly rigid.
    // We perform an affine inverse: inv([A|t;0|1]) = [A^{-1}|-A^{-1}t;0|1].
    const cv::Matx33f A(
        T[0], T[1], T[2],
        T[4], T[5], T[6],
        T[8], T[9], T[10]);

    const double det = cv::determinant(A);
    if (std::abs(det) < 1e-12) {
        throw std::runtime_error("Singular affine transform in mat4_inverse_rigid");
    }
    const cv::Matx33f Ainv = A.inv();
    const cv::Vec3f t(T[3], T[7], T[11]);
    const cv::Vec3f tinv = -(Ainv * t);

    std::array<float, 16> inv = mat4_identity();
    inv[0] = Ainv(0, 0);
    inv[1] = Ainv(0, 1);
    inv[2] = Ainv(0, 2);
    inv[4] = Ainv(1, 0);
    inv[5] = Ainv(1, 1);
    inv[6] = Ainv(1, 2);
    inv[8] = Ainv(2, 0);
    inv[9] = Ainv(2, 1);
    inv[10] = Ainv(2, 2);
    inv[3] = tinv[0];
    inv[7] = tinv[1];
    inv[11] = tinv[2];
    return inv;
}

inline std::array<float, 16> transform4x4_to_array(const Transform4x4& t)
{
    std::array<float, 16> out{};
    for (int i = 0; i < 16; ++i) out[i] = t.data[i];
    return out;
}

inline std::array<float, 16> kitti_R0_rect_to_mat4(const Transform4x4& R0)
{
    // kitti_loader stores R0_rect in a 4x4 with bottom-right = 1.
    return transform4x4_to_array(R0);
}

inline std::array<float, 16> kitti_Tr_velo_to_cam_to_mat4(const Transform4x4& Tr)
{
    // kitti_loader stores Tr_velo_to_cam as a 4x4 with bottom row [0 0 0 1].
    return transform4x4_to_array(Tr);
}

inline std::array<float, 16> make_intrinsics_4x4_from_P(const CameraParams& P)
{
    // In KITTI, P2 is typically K * [I|t] in rectified camera frame.
    // We take the left 3x3 as K and embed into a 4x4.
    std::array<float, 16> K = mat4_identity();
    K[0] = P.K(0, 0);
    K[1] = P.K(0, 1);
    K[2] = P.K(0, 2);
    K[4] = P.K(1, 0);
    K[5] = P.K(1, 1);
    K[6] = P.K(1, 2);
    K[8] = P.K(2, 0);
    K[9] = P.K(2, 1);
    K[10] = P.K(2, 2);
    return K;
}

inline std::array<float, 16> make_rectified_cam0_to_cam_from_P(const CameraParams& P)
{
    // KITTI projection matrices are 3x4: P = K * [R|t]. For rectified cameras, R=I.
    // The last column encodes translation in rectified cam0 coordinates: p4 = K * t.
    // We recover t = K^{-1} * p4 and build T_cam0->cam.
    const cv::Matx33f K(
        P.K(0, 0), P.K(0, 1), P.K(0, 2),
        P.K(1, 0), P.K(1, 1), P.K(1, 2),
        P.K(2, 0), P.K(2, 1), P.K(2, 2));

    cv::Matx33f Kinv;
    const double det = cv::determinant(K);
    if (std::abs(det) < 1e-12) {
        throw std::runtime_error("Singular camera intrinsic matrix in P*");
    }
    Kinv = K.inv();

    const cv::Vec3f p4(P.K(0, 3), P.K(1, 3), P.K(2, 3));
    const cv::Vec3f t = Kinv * p4;

    auto T = mat4_identity();
    T[3] = t[0];
    T[7] = t[1];
    T[11] = t[2];
    return T;
}

inline cv::Vec4f plane_from_three_points(const cv::Vec3f& p1, const cv::Vec3f& p2, const cv::Vec3f& p3)
{
    const cv::Vec3f v1 = p2 - p1;
    const cv::Vec3f v2 = p3 - p1;
    const cv::Vec3f n = v1.cross(v2);
    const float d = -(n.dot(p1));
    return cv::Vec4f(n[0], n[1], n[2], d);
}

inline cv::Vec3f transform_point(const std::array<float, 16>& T, const cv::Vec3f& p)
{
    const float x = T[0] * p[0] + T[1] * p[1] + T[2] * p[2] + T[3];
    const float y = T[4] * p[0] + T[5] * p[1] + T[6] * p[2] + T[7];
    const float z = T[8] * p[0] + T[9] * p[1] + T[10] * p[2] + T[11];
    return cv::Vec3f(x, y, z);
}

struct ImageResizeCrop
{
    double resize{1.0};
    int resized_width{0};
    int resized_height{0};
    int crop_x{0};
    int crop_y{0};
};

inline ImageResizeCrop compute_image_resize_crop(const cv::Size& raw_image_size,
                                                 int target_w,
                                                 int target_h)
{
    if (raw_image_size.width <= 0 || raw_image_size.height <= 0) {
        throw std::runtime_error("Invalid raw image size");
    }
    if (target_w <= 0 || target_h <= 0) {
        throw std::runtime_error("Invalid target image size");
    }

    const double resize = std::max(static_cast<double>(target_h) / raw_image_size.height,
                                   static_cast<double>(target_w) / raw_image_size.width);
    const int resized_width = static_cast<int>(static_cast<double>(raw_image_size.width) * resize);
    const int resized_height = static_cast<int>(static_cast<double>(raw_image_size.height) * resize);
    const int crop_x = std::max(0, resized_width - target_w) / 2;
    const int crop_y = resized_height - target_h;

    if (resized_width <= 0 || resized_height <= 0) {
        throw std::runtime_error("Invalid resize geometry for image augmentation");
    }

    return ImageResizeCrop{resize, resized_width, resized_height, crop_x, crop_y};
}

}  // namespace detail

// Build the 4 matrices used by CameraBEVBackbone::run() directly from KITTI-style calib.
//
// Assumptions (matches the Python standalone validation transform):
// - Image is scaled by max(target_h/raw_h, target_w/raw_w), then bottom/center cropped.
// - camera2lidar is computed in rectified camera frame: camera_rect -> lidar.
// - denorms provides only the plane normal (a,b,c), consistent with current SYCL ray impl.
//
// If you have a better ground height estimate than 0, pass it in (meters, lidar frame).
inline CameraMetas compute_camera_metas_from_kitti_calib(const CalibField_t& calib,
                                                         const cv::Size& raw_image_size,
                                                         int target_w,
                                                         int target_h,
                                                         int num_camera = 1,
                                                         const std::string& camera_key = "P2",
                                                         float ground_z_lidar = 0.0f)
{
    auto itP = calib.cameraParams.find(camera_key);
    if (itP == calib.cameraParams.end()) {
        throw std::runtime_error("Missing camera params key: " + camera_key);
    }
    auto itR0 = calib.transforms.find("R0_rect");
    if (itR0 == calib.transforms.end()) {
        throw std::runtime_error("Missing transform key: R0_rect");
    }
    auto itTr = calib.transforms.find("Tr_velo_to_cam");
    if (itTr == calib.transforms.end()) {
        // kitti_loader also aliases it as lidar_to_camera
        itTr = calib.transforms.find("lidar_to_camera");
    }
    if (itTr == calib.transforms.end()) {
        throw std::runtime_error("Missing transform key: Tr_velo_to_cam / lidar_to_camera");
    }

    const auto K4 = detail::make_intrinsics_4x4_from_P(itP->second);
    const auto cam0_to_cam = detail::make_rectified_cam0_to_cam_from_P(itP->second);
    const auto R0 = detail::kitti_R0_rect_to_mat4(itR0->second);
    const auto Tr = detail::kitti_Tr_velo_to_cam_to_mat4(itTr->second);
    // Tr_velo_to_cam is for the reference camera; apply rectification then per-camera translation from P*.
    // This keeps extrinsics consistent with the chosen P-key (e.g., P2 for image_2).
    const auto lidar_to_cam_rect = detail::mat4_mul(cam0_to_cam, detail::mat4_mul(R0, Tr));
    const auto cam_rect_to_lidar = detail::mat4_inverse_rigid(lidar_to_cam_rect);

    const auto resize_crop = detail::compute_image_resize_crop(raw_image_size, target_w, target_h);
    auto ida = detail::mat4_identity();
    ida[0] = static_cast<float>(resize_crop.resize);
    ida[5] = static_cast<float>(resize_crop.resize);
    ida[3] = -static_cast<float>(resize_crop.crop_x);
    ida[7] = -static_cast<float>(resize_crop.crop_y);

    // denorms: derive plane normal in camera frame from 3 points on lidar ground plane.
    // Match Python's get_denorm: pick 3 ground points, transform by ego->cam, then denorm = -plane.
    // Here ego==lidar.
    const auto ego_to_cam = lidar_to_cam_rect;  // lidar->camera
    const cv::Vec3f g1(0.0f, 0.0f, ground_z_lidar);
    const cv::Vec3f g2(0.0f, 1.0f, ground_z_lidar);
    const cv::Vec3f g3(1.0f, 1.0f, ground_z_lidar);
    const cv::Vec3f c1 = detail::transform_point(ego_to_cam, g1);
    const cv::Vec3f c2 = detail::transform_point(ego_to_cam, g2);
    const cv::Vec3f c3 = detail::transform_point(ego_to_cam, g3);
    const cv::Vec4f plane = detail::plane_from_three_points(c1, c2, c3);
    const cv::Vec4f denorm = -plane;

    CameraMetas out;
    out.camera2lidar.resize(static_cast<size_t>(num_camera) * 16);
    out.intrinsics.resize(static_cast<size_t>(num_camera) * 16);
    out.img_aug.resize(static_cast<size_t>(num_camera) * 16);
    out.denorms.resize(static_cast<size_t>(num_camera) * 4);

    for (int i = 0; i < num_camera; ++i) {
        std::copy(cam_rect_to_lidar.begin(), cam_rect_to_lidar.end(), out.camera2lidar.begin() + static_cast<size_t>(i) * 16);
        std::copy(K4.begin(), K4.end(), out.intrinsics.begin() + static_cast<size_t>(i) * 16);
        std::copy(ida.begin(), ida.end(), out.img_aug.begin() + static_cast<size_t>(i) * 16);
        out.denorms[static_cast<size_t>(i) * 4 + 0] = denorm[0];
        out.denorms[static_cast<size_t>(i) * 4 + 1] = denorm[1];
        out.denorms[static_cast<size_t>(i) * 4 + 2] = denorm[2];
        out.denorms[static_cast<size_t>(i) * 4 + 3] = denorm[3];
    }
    return out;
}

}  // namespace bevfusion
