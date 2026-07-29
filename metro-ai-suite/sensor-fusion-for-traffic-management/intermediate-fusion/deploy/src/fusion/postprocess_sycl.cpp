#include <algorithm>
#include <cmath>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>

#include "postprocess_sycl.hpp"

namespace {

struct TopKEntry
{
    float score;
    int index;
    int cls;
};

struct ScoreGreater
{
    bool operator()(const BBox3D &a, const BBox3D &b) const
    {
        return a.score > b.score;
    }
};

struct ScoreLower
{
    bool operator()(const TopKEntry &a, const TopKEntry &b) const
    {
        return a.score > b.score;
    }
};

struct Float2
{
    float x;
    float y;
};

template <typename T> struct UsmArrayDeleter
{
    sycl::queue *queue = nullptr;
    void operator()(T *ptr) const
    {
        if (ptr != nullptr) {
            sycl::free(ptr, *queue);
        }
    }
};

template <typename T> using UsmSharedArray = std::unique_ptr<T[], UsmArrayDeleter<T>>;

template <typename T> UsmSharedArray<T> makeUsmArray(sycl::queue &queue, size_t count)
{
    if (count == 0) {
        return UsmSharedArray<T>(nullptr, UsmArrayDeleter<T>{&queue});
    }
    void *raw = sycl::malloc_shared(sizeof(T) * count, queue);
    T *ptr = static_cast<T *>(raw);
    if (ptr == nullptr) {
        throw std::runtime_error("Failed to allocate USM shared memory");
    }
    return UsmSharedArray<T>(ptr, UsmArrayDeleter<T>{&queue});
}

template <typename T> inline T *ensureUsmBuffer(UsmSharedArray<T> &buf, size_t &capacity, sycl::queue &queue, size_t count)
{
    if (count > capacity) {
        buf = makeUsmArray<T>(queue, count);
        capacity = count;
    }
    return buf.get();
}

using DifferenceType = std::vector<TopKEntry>::difference_type;

template <typename Cmp>
inline void collectTopkPerClass(const float *heatmap_ptr,
                                unsigned int num_classes,
                                size_t spatial,
                                size_t per_class_keep,
                                float min_threshold,
                                const Cmp &topk_cmp,
                                std::vector<TopKEntry> &host_per_class,
                                std::vector<TopKEntry> &aggregated_host)
{
    aggregated_host.clear();
    aggregated_host.reserve(static_cast<size_t>(num_classes) * per_class_keep);
    host_per_class.clear();
    host_per_class.reserve(per_class_keep);
    const ScoreLower min_heap_cmp{};

    for (unsigned int cls = 0; cls < num_classes; ++cls) {
        host_per_class.clear();
        const float *cls_ptr = heatmap_ptr + static_cast<size_t>(cls) * spatial;
        for (size_t flat = 0; flat < spatial; ++flat) {
            const float value = cls_ptr[flat];
            if (value < min_threshold) {
                continue;
            }
            const TopKEntry entry{value, static_cast<int>(flat), static_cast<int>(cls)};
            if (host_per_class.size() < per_class_keep) {
                host_per_class.push_back(entry);
                std::push_heap(host_per_class.begin(), host_per_class.end(), min_heap_cmp);
                continue;
            }
            if (!host_per_class.empty() && entry.score > host_per_class.front().score) {
                std::pop_heap(host_per_class.begin(), host_per_class.end(), min_heap_cmp);
                host_per_class.back() = entry;
                std::push_heap(host_per_class.begin(), host_per_class.end(), min_heap_cmp);
            }
        }

        if (host_per_class.empty()) {
            continue;
        }

        std::sort(host_per_class.begin(), host_per_class.end(), topk_cmp);
        aggregated_host.insert(aggregated_host.end(), host_per_class.begin(), host_per_class.end());
    }
}

inline void sortCandidates(BBox3D *data, size_t count, sycl::queue & /*queue*/)
{
    if (count == 0) {
        return;
    }
    // data is sycl::malloc_shared (USM shared memory) — directly accessible
    // from the host after the preceding kernel .wait().
    // dpl::sort was removed: DPL 2022.9 instantiates local_accessor<BBox3D>
    // internally, which is incompatible with SYCL 2025.2 headers for
    // non-trivially-constructible types (compile error in accessor.hpp).
    // std::sort is sufficient here; candidate counts are typically small.
    std::sort(data, data + count, ScoreGreater{});
}

inline float fetch_tensor_value(const float *tensor, int H, int W, int channel, int y, int x)
{
    if (tensor == nullptr) {
        return 0.0f;
    }
    const size_t offset = (static_cast<size_t>(channel) * H + y) * W + x;
    return tensor[offset];
}

inline float cross_device(const Float2 &p1, const Float2 &p2, const Float2 &p0)
{
    return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y);
}

inline bool intersection_device(const Float2 &p1, const Float2 &p0, const Float2 &q1, const Float2 &q0, Float2 &ans)
{
    const bool overlap = (sycl::fmin(p0.x, p1.x) <= sycl::fmax(q0.x, q1.x) && sycl::fmin(q0.x, q1.x) <= sycl::fmax(p0.x, p1.x) &&
                          sycl::fmin(p0.y, p1.y) <= sycl::fmax(q0.y, q1.y) && sycl::fmin(q0.y, q1.y) <= sycl::fmax(p0.y, p1.y));
    if (!overlap) {
        return false;
    }

    const float s1 = cross_device(q0, p1, p0);
    const float s2 = cross_device(p1, q1, p0);
    const float s3 = cross_device(p0, q1, q0);
    const float s4 = cross_device(q1, p1, q0);
    if (!(s1 * s2 > 0 && s3 * s4 > 0)) {
        return false;
    }

    const float s5 = cross_device(q1, p1, p0);
    if (sycl::fabs(s5 - s1) > 1e-8f) {
        const float denom = s5 - s1;
        ans.x = (s5 * q0.x - s1 * q1.x) / denom;
        ans.y = (s5 * q0.y - s1 * q1.y) / denom;
    }
    else {
        const float a0 = p0.y - p1.y;
        const float b0 = p1.x - p0.x;
        const float c0 = p0.x * p1.y - p1.x * p0.y;
        const float a1 = q0.y - q1.y;
        const float b1 = q1.x - q0.x;
        const float c1 = q0.x * q1.y - q1.x * q0.y;
        const float D = a0 * b1 - a1 * b0;
        ans.x = (b0 * c1 - b1 * c0) / D;
        ans.y = (a1 * c0 - a0 * c1) / D;
    }

    return true;
}

inline bool check_box2d_device(const Float2 &center, float dx, float dy, float yaw, const Float2 &p)
{
    const float margin = 1e-2f;
    const float angle_cos = sycl::cos(-yaw);
    const float angle_sin = sycl::sin(-yaw);
    const float rot_x = (p.x - center.x) * angle_cos + (p.y - center.y) * (-angle_sin);
    const float rot_y = (p.x - center.x) * angle_sin + (p.y - center.y) * angle_cos;
    return (sycl::fabs(rot_x) < dx / 2.0f + margin && sycl::fabs(rot_y) < dy / 2.0f + margin);
}

inline void rotate_around_center_device(const Float2 &center, float angle_cos, float angle_sin, Float2 &p)
{
    const float rel_x = p.x - center.x;
    const float rel_y = p.y - center.y;
    const float new_x = rel_x * angle_cos + rel_y * (-angle_sin) + center.x;
    const float new_y = rel_x * angle_sin + rel_y * angle_cos + center.y;
    p = Float2{new_x, new_y};
}

// Host/CPU version of devIoUBoxes. Called from CPU-side NMS (runRotateNmsHost).
// Mirrors devIoUBoxes but uses std:: math functions. The algorithm is identical;
// duplication is intentional to keep devIoUBoxes pure-SYCL for GPU kernels.
inline bool hostIoUBoxes(const BBox3D &box_a, const BBox3D &box_b, float nms_thresh)
{
    const float a_dx_half = box_a.l * 0.5f;
    const float a_dy_half = box_a.w * 0.5f;
    const float b_dx_half = box_b.l * 0.5f;
    const float b_dy_half = box_b.w * 0.5f;

    // Circumscribed-circle AABB reject: same as devIoUBoxes.
    {
        const float a_r = std::sqrt(a_dx_half * a_dx_half + a_dy_half * a_dy_half);
        const float b_r = std::sqrt(b_dx_half * b_dx_half + b_dy_half * b_dy_half);
        const float r_sum = a_r + b_r;
        const float dx = box_a.x - box_b.x;
        const float dy = box_a.y - box_b.y;
        if (std::fabs(dx) > r_sum || std::fabs(dy) > r_sum) {
            return false;
        }
    }

    Float2 box_a_corners[5];
    Float2 box_b_corners[5];
    Float2 cross_points[16];
    Float2 poly_center{0.0f, 0.0f};
    int cnt = 0;

    box_a_corners[0] = Float2{box_a.x - a_dx_half, box_a.y - a_dy_half};
    box_a_corners[1] = Float2{box_a.x + a_dx_half, box_a.y - a_dy_half};
    box_a_corners[2] = Float2{box_a.x + a_dx_half, box_a.y + a_dy_half};
    box_a_corners[3] = Float2{box_a.x - a_dx_half, box_a.y + a_dy_half};

    box_b_corners[0] = Float2{box_b.x - b_dx_half, box_b.y - b_dy_half};
    box_b_corners[1] = Float2{box_b.x + b_dx_half, box_b.y - b_dy_half};
    box_b_corners[2] = Float2{box_b.x + b_dx_half, box_b.y + b_dy_half};
    box_b_corners[3] = Float2{box_b.x - b_dx_half, box_b.y + b_dy_half};

    const Float2 center_a{box_a.x, box_a.y};
    const Float2 center_b{box_b.x, box_b.y};
    const float a_cos = std::cos(box_a.yaw);
    const float a_sin = std::sin(box_a.yaw);
    const float b_cos = std::cos(box_b.yaw);
    const float b_sin = std::sin(box_b.yaw);

    auto rot = [](const Float2 &c, float cc, float ss, Float2 &p) {
        const float rx = p.x - c.x;
        const float ry = p.y - c.y;
        p.x = rx * cc - ry * ss + c.x;
        p.y = rx * ss + ry * cc + c.y;
    };
    for (int k = 0; k < 4; ++k) {
        rot(center_a, a_cos, a_sin, box_a_corners[k]);
        rot(center_b, b_cos, b_sin, box_b_corners[k]);
    }
    box_a_corners[4] = box_a_corners[0];
    box_b_corners[4] = box_b_corners[0];

    auto cross = [](const Float2 &p1, const Float2 &p2, const Float2 &p0) {
        return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y);
    };
    auto intersect_seg = [&](const Float2 &p1, const Float2 &p0, const Float2 &q1, const Float2 &q0, Float2 &ans) -> bool {
        const bool overlap = (std::fmin(p0.x, p1.x) <= std::fmax(q0.x, q1.x) && std::fmin(q0.x, q1.x) <= std::fmax(p0.x, p1.x) &&
                              std::fmin(p0.y, p1.y) <= std::fmax(q0.y, q1.y) && std::fmin(q0.y, q1.y) <= std::fmax(p0.y, p1.y));
        if (!overlap) return false;
        const float s1 = cross(q0, p1, p0);
        const float s2 = cross(p1, q1, p0);
        const float s3 = cross(p0, q1, q0);
        const float s4 = cross(q1, p1, q0);
        if (!(s1 * s2 > 0 && s3 * s4 > 0)) return false;
        const float s5 = cross(q1, p1, p0);
        if (std::fabs(s5 - s1) > 1e-8f) {
            const float denom = s5 - s1;
            ans.x = (s5 * q0.x - s1 * q1.x) / denom;
            ans.y = (s5 * q0.y - s1 * q1.y) / denom;
        } else {
            const float a0 = p0.y - p1.y, b0 = p1.x - p0.x, c0 = p0.x * p1.y - p1.x * p0.y;
            const float a1 = q0.y - q1.y, b1 = q1.x - q0.x, c1 = q0.x * q1.y - q1.x * q0.y;
            const float D = a0 * b1 - a1 * b0;
            ans.x = (b0 * c1 - b1 * c0) / D;
            ans.y = (a1 * c0 - a0 * c1) / D;
        }
        return true;
    };
    auto check_in = [](const Float2 &c, float dx, float dy, float yaw, const Float2 &p) -> bool {
        const float margin = 1e-2f;
        const float cc = std::cos(-yaw);
        const float ss = std::sin(-yaw);
        const float rx = (p.x - c.x) * cc + (p.y - c.y) * (-ss);
        const float ry = (p.x - c.x) * ss + (p.y - c.y) * cc;
        return (std::fabs(rx) < dx / 2.0f + margin && std::fabs(ry) < dy / 2.0f + margin);
    };

    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            if (intersect_seg(box_a_corners[i + 1], box_a_corners[i], box_b_corners[j + 1], box_b_corners[j], cross_points[cnt])) {
                poly_center.x += cross_points[cnt].x;
                poly_center.y += cross_points[cnt].y;
                ++cnt;
            }
        }
    }
    for (int k = 0; k < 4; ++k) {
        if (check_in(center_a, box_a.l, box_a.w, box_a.yaw, box_b_corners[k])) {
            poly_center.x += box_b_corners[k].x;
            poly_center.y += box_b_corners[k].y;
            cross_points[cnt++] = box_b_corners[k];
        }
        if (check_in(center_b, box_b.l, box_b.w, box_b.yaw, box_a_corners[k])) {
            poly_center.x += box_a_corners[k].x;
            poly_center.y += box_a_corners[k].y;
            cross_points[cnt++] = box_a_corners[k];
        }
    }
    if (cnt == 0) return false;
    poly_center.x /= static_cast<float>(cnt);
    poly_center.y /= static_cast<float>(cnt);

    for (int pass = 0; pass < cnt - 1; ++pass) {
        for (int i = 0; i < cnt - pass - 1; ++i) {
            const float ai = std::atan2(cross_points[i].y - poly_center.y, cross_points[i].x - poly_center.x);
            const float aj = std::atan2(cross_points[i + 1].y - poly_center.y, cross_points[i + 1].x - poly_center.x);
            if (ai > aj) {
                const Float2 tmp = cross_points[i];
                cross_points[i] = cross_points[i + 1];
                cross_points[i + 1] = tmp;
            }
        }
    }

    float area = 0.0f;
    for (int k = 0; k < cnt - 1; ++k) {
        const Float2 a{cross_points[k].x - cross_points[0].x, cross_points[k].y - cross_points[0].y};
        const Float2 b{cross_points[k + 1].x - cross_points[0].x, cross_points[k + 1].y - cross_points[0].y};
        area += (a.x * b.y - a.y * b.x);
    }
    const float s_overlap = std::fabs(area) * 0.5f;
    const float sa = box_a.l * box_a.w;
    const float sb = box_b.l * box_b.w;
    const float denom = std::fmax(sa + sb - s_overlap, 1e-8f);
    return (s_overlap / denom) >= nms_thresh;
}

inline bool devIoUBoxes(const BBox3D &box_a, const BBox3D &box_b, float nms_thresh)
{
    const float a_dx_half = box_a.l * 0.5f;
    const float a_dy_half = box_a.w * 0.5f;
    const float b_dx_half = box_b.l * 0.5f;
    const float b_dy_half = box_b.w * 0.5f;

    // Fast circumscribed-circle reject: a rotated rectangle is bounded by a
    // circle of radius 0.5·sqrt(l² + w²) around its center. Two rectangles
    // cannot overlap if their center distance exceeds the sum of these
    // radii on either axis (AABB-of-bounding-circles test). ~10 FLOPs skips
    // the ~200-FLOP polygon clip for the overwhelmingly common non-overlap
    // case in dense NMS (task 1 at threshold=0.1 produces ~450 candidates).
    {
        const float a_r = sycl::sqrt(a_dx_half * a_dx_half + a_dy_half * a_dy_half);
        const float b_r = sycl::sqrt(b_dx_half * b_dx_half + b_dy_half * b_dy_half);
        const float r_sum = a_r + b_r;
        const float dx = box_a.x - box_b.x;
        const float dy = box_a.y - box_b.y;
        if (sycl::fabs(dx) > r_sum || sycl::fabs(dy) > r_sum) {
            return false;
        }
    }

    Float2 box_a_corners[5];
    Float2 box_b_corners[5];
    Float2 cross_points[16];
    Float2 poly_center{0.0f, 0.0f};
    int cnt = 0;

    box_a_corners[0] = Float2{box_a.x - a_dx_half, box_a.y - a_dy_half};
    box_a_corners[1] = Float2{box_a.x + a_dx_half, box_a.y - a_dy_half};
    box_a_corners[2] = Float2{box_a.x + a_dx_half, box_a.y + a_dy_half};
    box_a_corners[3] = Float2{box_a.x - a_dx_half, box_a.y + a_dy_half};

    box_b_corners[0] = Float2{box_b.x - b_dx_half, box_b.y - b_dy_half};
    box_b_corners[1] = Float2{box_b.x + b_dx_half, box_b.y - b_dy_half};
    box_b_corners[2] = Float2{box_b.x + b_dx_half, box_b.y + b_dy_half};
    box_b_corners[3] = Float2{box_b.x - b_dx_half, box_b.y + b_dy_half};

    const Float2 center_a{box_a.x, box_a.y};
    const Float2 center_b{box_b.x, box_b.y};
    const float a_angle_cos = sycl::cos(box_a.yaw);
    const float a_angle_sin = sycl::sin(box_a.yaw);
    const float b_angle_cos = sycl::cos(box_b.yaw);
    const float b_angle_sin = sycl::sin(box_b.yaw);

    for (int k = 0; k < 4; ++k) {
        rotate_around_center_device(center_a, a_angle_cos, a_angle_sin, box_a_corners[k]);
        rotate_around_center_device(center_b, b_angle_cos, b_angle_sin, box_b_corners[k]);
    }

    box_a_corners[4] = box_a_corners[0];
    box_b_corners[4] = box_b_corners[0];

    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            if (intersection_device(box_a_corners[i + 1], box_a_corners[i], box_b_corners[j + 1], box_b_corners[j], cross_points[cnt])) {
                poly_center.x += cross_points[cnt].x;
                poly_center.y += cross_points[cnt].y;
                ++cnt;
            }
        }
    }

    for (int k = 0; k < 4; ++k) {
        if (check_box2d_device(center_a, box_a.l, box_a.w, box_a.yaw, box_b_corners[k])) {
            poly_center.x += box_b_corners[k].x;
            poly_center.y += box_b_corners[k].y;
            cross_points[cnt++] = box_b_corners[k];
        }
        if (check_box2d_device(center_b, box_b.l, box_b.w, box_b.yaw, box_a_corners[k])) {
            poly_center.x += box_a_corners[k].x;
            poly_center.y += box_a_corners[k].y;
            cross_points[cnt++] = box_a_corners[k];
        }
    }

    if (cnt == 0) {
        return false;
    }

    poly_center.x /= static_cast<float>(cnt);
    poly_center.y /= static_cast<float>(cnt);

    for (int pass = 0; pass < cnt - 1; ++pass) {
        for (int i = 0; i < cnt - pass - 1; ++i) {
            const float ang_i = sycl::atan2(cross_points[i].y - poly_center.y, cross_points[i].x - poly_center.x);
            const float ang_j = sycl::atan2(cross_points[i + 1].y - poly_center.y, cross_points[i + 1].x - poly_center.x);
            if (ang_i > ang_j) {
                const Float2 tmp = cross_points[i];
                cross_points[i] = cross_points[i + 1];
                cross_points[i + 1] = tmp;
            }
        }
    }

    float area = 0.0f;
    for (int k = 0; k < cnt - 1; ++k) {
        const Float2 a{cross_points[k].x - cross_points[0].x, cross_points[k].y - cross_points[0].y};
        const Float2 b{cross_points[k + 1].x - cross_points[0].x, cross_points[k + 1].y - cross_points[0].y};
        area += (a.x * b.y - a.y * b.x);
    }

    const float s_overlap = sycl::fabs(area) * 0.5f;
    const float sa = box_a.l * box_a.w;
    const float sb = box_b.l * box_b.w;
    const float denom = sycl::fmax(sa + sb - s_overlap, 1e-8f);
    const float iou = s_overlap / denom;

    return iou >= nms_thresh;
}

constexpr size_t kMaskWordBits = 64;

void build_circle_mask(sycl::queue &queue, const BBox3D *boxes, size_t cand_count, float radius_sq, uint64_t *mask, size_t col_blocks, sycl::event &dependent)
{
    if (cand_count == 0 || col_blocks == 0) {
        return;
    }

    dependent = queue.parallel_for(sycl::range<2>(cand_count, col_blocks), [=](sycl::item<2> item) {
        const size_t row = item.get_id(0);
        const size_t block = item.get_id(1);
        const float x_row = boxes[row].x;
        const float y_row = boxes[row].y;
        const size_t start = block * kMaskWordBits;
        uint64_t block_mask = 0;

        for (size_t bit = 0; bit < kMaskWordBits; ++bit) {
            const size_t col = start + bit;
            if (col >= cand_count) {
                break;
            }
            if (col <= row) {
                continue;
            }
            const float dx = x_row - boxes[col].x;
            const float dy = y_row - boxes[col].y;
            if (dx * dx + dy * dy <= radius_sq) {
                block_mask |= (1ULL << bit);
            }
        }

        mask[row * col_blocks + block] = block_mask;
    });
}

void build_rotate_mask(sycl::queue &queue,
                       const BBox3D *boxes,
                       size_t cand_count,
                       float iou_threshold,
                       uint64_t *mask,
                       size_t col_blocks,
                       sycl::event &dependent)
{
    if (cand_count == 0 || col_blocks == 0) {
        return;
    }

    dependent = queue.parallel_for(sycl::range<2>(cand_count, col_blocks), [=](sycl::item<2> item) {
        const size_t row = item.get_id(0);
        const size_t block = item.get_id(1);
        const BBox3D row_box = boxes[row];
        const size_t start = block * kMaskWordBits;
        uint64_t block_mask = 0;

        for (size_t bit = 0; bit < kMaskWordBits; ++bit) {
            const size_t col = start + bit;
            if (col >= cand_count) {
                break;
            }
            if (col <= row) {
                continue;
            }
            if (devIoUBoxes(row_box, boxes[col], iou_threshold)) {
                block_mask |= (1ULL << bit);
            }
        }

        mask[row * col_blocks + block] = block_mask;
    });
}

std::vector<int> compress_mask(const uint64_t *mask, size_t cand_count, size_t col_blocks, unsigned int max_keep)
{
    if (cand_count == 0 || col_blocks == 0 || max_keep == 0) {
        return {};
    }

    std::vector<int> keep;
    keep.reserve(std::min(static_cast<size_t>(max_keep), cand_count));
    std::vector<uint64_t> remv(col_blocks, 0);

    for (size_t i = 0; i < cand_count; ++i) {
        const size_t nblock = i / kMaskWordBits;
        const size_t inblock = i % kMaskWordBits;
        if (remv[nblock] & (1ULL << inblock)) {
            continue;
        }
        keep.push_back(static_cast<int>(i));
        if (keep.size() >= max_keep) {
            break;
        }
        const uint64_t *row_mask = mask + i * col_blocks;
        for (size_t j = nblock; j < col_blocks; ++j) {
            remv[j] |= row_mask[j];
        }
    }

    return keep;
}

}  // namespace

struct PostProcessSycl::ScratchBuffers
{
    explicit ScratchBuffers(sycl::queue &queue) : queue_(queue) {}

    sycl::queue &queue_;
    size_t topk_capacity = 0;
    size_t bbox_capacity = 0;
    size_t counter_capacity = 0;
    UsmSharedArray<TopKEntry> topk_entries;
    UsmSharedArray<BBox3D> candidate_entries;
    UsmSharedArray<uint32_t> counter_entries;
    std::vector<TopKEntry> host_per_class;
    std::vector<TopKEntry> aggregated_host;

    // Cached NMS scratch buffers — reused across frames to avoid per-frame
    // USM malloc/free inside runCircleNmsDevice / runRotateNmsDevice.
    size_t nms_mask_capacity = 0;
    UsmSharedArray<uint64_t> nms_mask_buf;
    size_t scaled_box_capacity = 0;
    UsmSharedArray<BBox3D> scaled_box_buf;
};

PostProcessSycl::PostProcessSycl(const PostProcessParams &params, sycl::queue &queue)
    : params_(params), queue_(queue), scratch_(std::make_unique<ScratchBuffers>(queue))
{
}

PostProcessSycl::~PostProcessSycl() = default;

std::vector<BBox3D>
PostProcessSycl::decodeTask(const PostProcessInput &input, int batch_size, int H, int W, const TaskConfig &task_cfg, const PostProcessInputChannels &channels)
{
    if (batch_size <= 0 || task_cfg.num_classes == 0 || H == 0 || W == 0) {
        return {};
    }

    const size_t spatial = static_cast<size_t>(H) * W;
    const size_t per_class_keep = std::min(static_cast<size_t>(params_.max_topk), spatial);
    if (per_class_keep == 0) {
        return {};
    }

    std::vector<BBox3D> decoded;
    decoded.reserve(params_.nms_post_max_size * static_cast<size_t>(task_cfg.num_classes));

    auto &scratch = *scratch_;
    scratch.host_per_class.clear();
    scratch.host_per_class.reserve(per_class_keep);
    using DifferenceType = std::vector<TopKEntry>::difference_type;

    const bool heatmap_is_logits = params_.heatmap_is_logits;
    const float sigmoid_eps = params_.sigmoid_eps;
    const float voxel_x = params_.voxel_size[0];
    const float voxel_y = params_.voxel_size[1];
    const float out_factor = params_.out_size_factor;
    const float pc_range_x = params_.pc_range_min[0];
    const float pc_range_y = params_.pc_range_min[1];
    const float score_threshold = params_.score_threshold;
    const float prob_threshold = std::clamp(score_threshold, sigmoid_eps, 1.0f - sigmoid_eps);
    const float hm_filter_threshold = heatmap_is_logits ? std::log(prob_threshold / (1.0f - prob_threshold)) : prob_threshold;
    const bool norm_bbox = params_.norm_bbox;
    const bool use_velocity = params_.use_velocity;
    const auto topk_cmp = [](const TopKEntry &a, const TopKEntry &b) { return a.score > b.score; };


    for (int batch_idx = 0; batch_idx < batch_size; ++batch_idx) {
        const float *heatmap_ptr = input.heatmap + static_cast<size_t>(batch_idx) * channels.C_hm * spatial;
        const float *reg_ptr = input.reg ? input.reg + static_cast<size_t>(batch_idx) * channels.C_reg * spatial : nullptr;
        const float *height_ptr = input.height ? input.height + static_cast<size_t>(batch_idx) * channels.C_height * spatial : nullptr;
        const float *dim_ptr = input.dim ? input.dim + static_cast<size_t>(batch_idx) * channels.C_dim * spatial : nullptr;
        const float *rot_ptr = input.rot ? input.rot + static_cast<size_t>(batch_idx) * channels.C_rot * spatial : nullptr;
        const float *vel_ptr = input.vel ? input.vel + static_cast<size_t>(batch_idx) * channels.C_vel * spatial : nullptr;

        collectTopkPerClass(heatmap_ptr, task_cfg.num_classes, spatial, per_class_keep, hm_filter_threshold, topk_cmp, scratch.host_per_class,
                            scratch.aggregated_host);

        if (scratch.aggregated_host.empty()) {
            continue;
        }

        size_t final_keep = std::min(static_cast<size_t>(params_.max_topk), scratch.aggregated_host.size());
        if (final_keep == 0) {
            continue;
        }
        if (final_keep < scratch.aggregated_host.size()) {
            std::nth_element(scratch.aggregated_host.begin(), scratch.aggregated_host.begin() + static_cast<DifferenceType>(final_keep),
                             scratch.aggregated_host.end(), topk_cmp);
        }
        std::sort(scratch.aggregated_host.begin(), scratch.aggregated_host.begin() + static_cast<DifferenceType>(final_keep), topk_cmp);

        TopKEntry *aggregated_ptr = ensureUsmBuffer<TopKEntry>(scratch.topk_entries, scratch.topk_capacity, queue_, final_keep);
        queue_.memcpy(aggregated_ptr, scratch.aggregated_host.data(), final_keep * sizeof(TopKEntry)).wait();

        BBox3D *candidate_ptr = ensureUsmBuffer<BBox3D>(scratch.candidate_entries, scratch.bbox_capacity, queue_, final_keep);
        uint32_t *count_ptr = ensureUsmBuffer<uint32_t>(scratch.counter_entries, scratch.counter_capacity, queue_, 1);
        queue_.memset(count_ptr, 0, sizeof(uint32_t)).wait();

        const size_t spatial_size = spatial;
        const uint32_t max_candidates = static_cast<uint32_t>(final_keep);
        queue_
            .parallel_for(
                sycl::range<1>(final_keep),
                [=](sycl::item<1> item) {
                    const size_t idx = item.get_id(0);
                    const TopKEntry entry = aggregated_ptr[idx];
                    const float heat = entry.score;  // logits or probabilities based on params
                    if (heat < hm_filter_threshold) {
                        return;
                    }
                    float prob = heat;
                    if (heatmap_is_logits) {
                        prob = 1.0f / (1.0f + sycl::exp(-heat));
                    }
                    const float clipped_prob = sycl::fmin(sycl::fmax(prob, sigmoid_eps), 1.0f - sigmoid_eps);
                    if (clipped_prob < score_threshold) {
                        return;
                    }
                    const int row = entry.index / W;
                    const int col = entry.index % W;
                    const size_t base = static_cast<size_t>(row) * W + col;

                    float xs = static_cast<float>(row);
                    float ys = static_cast<float>(col);
                    if (reg_ptr != nullptr) {
                        xs += reg_ptr[0 * spatial_size + base];
                        ys += reg_ptr[1 * spatial_size + base];
                    }
                    else {
                        xs += 0.5f;
                        ys += 0.5f;
                    }

                    const float x_world = xs * out_factor * voxel_x + pc_range_x;
                    const float y_world = ys * out_factor * voxel_y + pc_range_y;
                    const float z_center = (height_ptr != nullptr) ? height_ptr[base] : 0.0f;

                    float dl = (dim_ptr != nullptr) ? dim_ptr[0 * spatial_size + base] : 0.0f;
                    float dw = (dim_ptr != nullptr) ? dim_ptr[1 * spatial_size + base] : 0.0f;
                    float dh = (dim_ptr != nullptr) ? dim_ptr[2 * spatial_size + base] : 0.0f;
                    if (norm_bbox) {
                        dl = sycl::exp(dl);
                        dw = sycl::exp(dw);
                        dh = sycl::exp(dh);
                    }

                    float rot_sin = 0.0f;
                    float rot_cos = 1.0f;
                    if (rot_ptr != nullptr) {
                        rot_sin = rot_ptr[0 * spatial_size + base];
                        rot_cos = rot_ptr[1 * spatial_size + base];
                    }
                    const float yaw = sycl::atan2(rot_sin, rot_cos);

                    float vx = 0.0f;
                    float vy = 0.0f;
                    if (use_velocity && vel_ptr != nullptr) {
                        vx = vel_ptr[0 * spatial_size + base];
                        vy = vel_ptr[1 * spatial_size + base];
                    }
                    const BBox3D candidate{x_world,     y_world, z_center, dl,  dw,
                                           dh,          vx,      vy,       yaw, static_cast<int>(entry.cls) + static_cast<int>(task_cfg.label_offset),
                                           clipped_prob};
                    auto counter =
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(
                            *count_ptr);
                    const uint32_t slot = counter.fetch_add(1u);
                    if (slot >= max_candidates) {
                        return;
                    }
                    candidate_ptr[slot] = candidate;
                })
            .wait();

        uint32_t candidate_count_val = 0;
        queue_.memcpy(&candidate_count_val, count_ptr, sizeof(uint32_t)).wait();
        candidate_count_val = std::min(candidate_count_val, max_candidates);
        const size_t candidate_count = static_cast<size_t>(candidate_count_val);

        if (candidate_count == 0) {
            continue;
        }

        // Sort candidates by score (descending). Use device policy on GPU for large batches; host sort otherwise.
        sortCandidates(candidate_ptr, candidate_count, queue_);

        std::vector<int> keep_indices;
        if (task_cfg.nms_type == NmsType::kCircle) {
            keep_indices = runCircleNmsDevice(candidate_ptr, candidate_count, task_cfg.circle_radius, params_.nms_post_max_size);
        }
        else {
            keep_indices =
                runRotateNmsDevice(candidate_ptr, candidate_count, task_cfg, params_.nms_iou_threshold, params_.pre_max_size, params_.nms_post_max_size);
        }

        if (keep_indices.empty()) {
            continue;
        }

        decoded.reserve(decoded.size() + keep_indices.size());
        for (int idx : keep_indices) {
            const BBox3D &cand = candidate_ptr[idx];
            if (cand.x < params_.post_center_limit_range[0] || cand.x > params_.post_center_limit_range[3]) {
                continue;
            }
            if (cand.y < params_.post_center_limit_range[1] || cand.y > params_.post_center_limit_range[4]) {
                continue;
            }
            if (cand.z < params_.post_center_limit_range[2] || cand.z > params_.post_center_limit_range[5]) {
                continue;
            }

            decoded.emplace_back(cand.x, cand.y, cand.z - cand.h * 0.5f, cand.l, cand.w, cand.h, cand.vx, cand.vy, cand.yaw, cand.label, cand.score);
        }
    }

    return decoded;
}

std::vector<int> PostProcessSycl::runCircleNmsDevice(BBox3D *candidates, size_t cand_count, float distance_thresh, unsigned int max_keep)
{
    if (cand_count == 0 || max_keep == 0) {
        return {};
    }

    const size_t col_blocks = (cand_count + kMaskWordBits - 1) / kMaskWordBits;
    if (col_blocks == 0) {
        return {};
    }

    // Reuse cached mask buffer: avoids a sycl::malloc_shared / sycl::free every frame.
    uint64_t *mask = ensureUsmBuffer<uint64_t>(scratch_->nms_mask_buf, scratch_->nms_mask_capacity, queue_, cand_count * col_blocks);
    sycl::event mask_event;
    // circle_radius is already stored as r² (Python CenterHead convention, same as CPU impl).
    // build_circle_mask receives it as radius_sq directly — do NOT square again.
    build_circle_mask(queue_, candidates, cand_count, distance_thresh, mask, col_blocks, mask_event);
    mask_event.wait();
    return compress_mask(mask, cand_count, col_blocks, max_keep);
}

// CPU-side rotate NMS. For small cand_count (typical <= 500 in PointPillars task 1), the
// GPU kernel launch + synchronization overhead (~1.8ms baseline on DG2) dominates
// the actual compute; running the same algorithm on the CPU is 5-10x faster.
// Candidates are in USM shared memory (host-accessible after the preceding
// decode_kernel .wait()), so there is no extra host↔device transfer.
static std::vector<int> runRotateNmsHost(const BBox3D *candidates,
                                         size_t cand_count,
                                         const TaskConfig &task_cfg,
                                         float iou_threshold,
                                         unsigned int pre_max,
                                         unsigned int post_max)
{
    if (cand_count == 0 || post_max == 0) {
        return {};
    }
    const size_t cand_limit = std::min(static_cast<size_t>(pre_max), cand_count);

    // Scale (l,w) per nms_scale[label], same as GPU scale kernel.
    std::vector<BBox3D> scaled(cand_limit);
    for (size_t i = 0; i < cand_limit; ++i) {
        BBox3D box = candidates[i];
        unsigned int local_label = 0;
        if (box.label >= static_cast<int>(task_cfg.label_offset)) {
            local_label = static_cast<unsigned int>(box.label) - task_cfg.label_offset;
        }
        const unsigned int max_label = MAX_CLASSES_PER_TASK - 1;
        if (local_label > max_label) local_label = max_label;
        const float s = task_cfg.nms_scale[local_label];
        box.l *= s;
        box.w *= s;
        scaled[i] = box;
    }

    // Greedy NMS: candidates are already sorted by score descending.
    std::vector<int> keep;
    keep.reserve(post_max);
    std::vector<uint8_t> suppressed(cand_limit, 0);
    for (size_t i = 0; i < cand_limit; ++i) {
        if (suppressed[i]) continue;
        keep.push_back(static_cast<int>(i));
        if (keep.size() >= post_max) break;
        for (size_t j = i + 1; j < cand_limit; ++j) {
            if (suppressed[j]) continue;
            if (hostIoUBoxes(scaled[i], scaled[j], iou_threshold)) {
                suppressed[j] = 1;
            }
        }
    }
    return keep;
}

std::vector<int> PostProcessSycl::runRotateNmsDevice(BBox3D *candidates,
                                                 size_t cand_count,
                                                 const TaskConfig &task_cfg,
                                                 float iou_threshold,
                                                 unsigned int pre_max,
                                                 unsigned int post_max)
{
    if (cand_count == 0 || post_max == 0) {
        return {};
    }

    // For typical cand counts (<= 1024 on PointPillars task 1), CPU-side NMS is faster
    // than the GPU mask-kernel path because the kernel launch + sync overhead
    // (~1.8ms on DG2) dominates the O(N²/64) work. The circumscribed-circle
    // AABB reject (hostIoUBoxes line 224) keeps the worst case bounded.
    constexpr size_t kHostNmsThreshold = 1024;
    const size_t effective_cand = std::min(static_cast<size_t>(pre_max), cand_count);
    if (effective_cand <= kHostNmsThreshold) {
        return runRotateNmsHost(candidates, cand_count, task_cfg, iou_threshold, pre_max, post_max);
    }

    // Legacy GPU path: retained for very large cand counts where N²/64 dominates
    // launch overhead. Not normally hit in the current pipeline.
    const size_t cand_limit = effective_cand;
    const auto nms_scale = task_cfg.nms_scale;
    const unsigned int label_offset = task_cfg.label_offset;

    BBox3D *scaled_ptr = ensureUsmBuffer<BBox3D>(scratch_->scaled_box_buf, scratch_->scaled_box_capacity, queue_, cand_limit);
    queue_
        .parallel_for(sycl::range<1>(cand_limit),
                      [=](sycl::item<1> item) {
                          const size_t idx = item.get_id(0);
                          BBox3D box = candidates[idx];
                          unsigned int local_label = 0;
                          if (box.label >= static_cast<int>(label_offset)) {
                              local_label = static_cast<unsigned int>(box.label) - label_offset;
                          }
                          const unsigned int max_label = MAX_CLASSES_PER_TASK - 1;
                          if (local_label > max_label) {
                              local_label = max_label;
                          }
                          const float scale = nms_scale[local_label];
                          box.l *= scale;
                          box.w *= scale;
                          scaled_ptr[idx] = box;
                      })
        .wait();

    const size_t col_blocks = (cand_limit + kMaskWordBits - 1) / kMaskWordBits;
    if (col_blocks == 0) {
        return {};
    }

    uint64_t *mask = ensureUsmBuffer<uint64_t>(scratch_->nms_mask_buf, scratch_->nms_mask_capacity, queue_, cand_limit * col_blocks);
    sycl::event mask_event;
    build_rotate_mask(queue_, scaled_ptr, cand_limit, iou_threshold, mask, col_blocks, mask_event);
    mask_event.wait();
    return compress_mask(mask, cand_limit, col_blocks, post_max);
}
