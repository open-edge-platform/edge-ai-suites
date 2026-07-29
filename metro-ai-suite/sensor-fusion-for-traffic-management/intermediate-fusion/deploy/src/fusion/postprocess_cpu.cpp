#include "postprocess_cpu.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

namespace {

struct TopKEntry
{
    float score;
    int index;
    int cls;
};

struct Float2
{
    float x;
    float y;
};

inline float clip_sigmoid(float x, float eps)
{
    const float val = 1.0f / (1.0f + std::exp(-x));
    return std::clamp(val, eps, 1.0f - eps);
}

inline float get_tensor_value(const float *tensor, int channels, int H, int W, int channel, int y, int x)
{
    const size_t offset = (static_cast<size_t>(channel) * H + y) * W + x;
    return tensor[offset];
}

inline float cross(const Float2 &p1, const Float2 &p2, const Float2 &p0)
{
    return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y);
}

inline int check_box2d(const float *const box, const Float2 &p)
{
    const float margin = 1e-2f;
    const float center_x = box[0];
    const float center_y = box[1];
    const float angle_cos = std::cos(-box[6]);
    const float angle_sin = std::sin(-box[6]);
    const float rot_x = (p.x - center_x) * angle_cos + (p.y - center_y) * (-angle_sin);
    const float rot_y = (p.x - center_x) * angle_sin + (p.y - center_y) * angle_cos;
    return (std::fabs(rot_x) < box[3] / 2.0f + margin && std::fabs(rot_y) < box[4] / 2.0f + margin);
}

inline bool intersection(const Float2 &p1, const Float2 &p0, const Float2 &q1, const Float2 &q0, Float2 &ans)
{
    const bool overlap = (std::min(p0.x, p1.x) <= std::max(q0.x, q1.x) && std::min(q0.x, q1.x) <= std::max(p0.x, p1.x) &&
                          std::min(p0.y, p1.y) <= std::max(q0.y, q1.y) && std::min(q0.y, q1.y) <= std::max(p0.y, p1.y));
    if (!overlap) {
        return false;
    }

    float s1 = cross(q0, p1, p0);
    float s2 = cross(p1, q1, p0);
    float s3 = cross(p0, q1, q0);
    float s4 = cross(q1, p1, q0);
    if (!(s1 * s2 > 0 && s3 * s4 > 0)) {
        return false;
    }

    float s5 = cross(q1, p1, p0);
    if (std::fabs(s5 - s1) > 1e-8f) {
        ans.x = (s5 * q0.x - s1 * q1.x) / (s5 - s1);
        ans.y = (s5 * q0.y - s1 * q1.y) / (s5 - s1);
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

inline void rotate_around_center(const Float2 &center, float angle_cos, float angle_sin, Float2 &p)
{
    const float new_x = (p.x - center.x) * angle_cos + (p.y - center.y) * (-angle_sin) + center.x;
    const float new_y = (p.x - center.x) * angle_sin + (p.y - center.y) * angle_cos + center.y;
    p = Float2{new_x, new_y};
}

inline bool devIoU(const float *const box_a, const float *const box_b, float nms_thresh)
{
    const float a_angle = box_a[6];
    const float b_angle = box_b[6];
    const float a_dx_half = box_a[3] * 0.5f;
    const float b_dx_half = box_b[3] * 0.5f;
    const float a_dy_half = box_a[4] * 0.5f;
    const float b_dy_half = box_b[4] * 0.5f;

    Float2 box_a_corners[5];
    Float2 box_b_corners[5];
    Float2 cross_points[16];
    Float2 poly_center{0.0f, 0.0f};
    int cnt = 0;

    box_a_corners[0] = Float2{box_a[0] - a_dx_half, box_a[1] - a_dy_half};
    box_a_corners[1] = Float2{box_a[0] + a_dx_half, box_a[1] - a_dy_half};
    box_a_corners[2] = Float2{box_a[0] + a_dx_half, box_a[1] + a_dy_half};
    box_a_corners[3] = Float2{box_a[0] - a_dx_half, box_a[1] + a_dy_half};

    box_b_corners[0] = Float2{box_b[0] - b_dx_half, box_b[1] - b_dy_half};
    box_b_corners[1] = Float2{box_b[0] + b_dx_half, box_b[1] - b_dy_half};
    box_b_corners[2] = Float2{box_b[0] + b_dx_half, box_b[1] + b_dy_half};
    box_b_corners[3] = Float2{box_b[0] - b_dx_half, box_b[1] + b_dy_half};

    const Float2 center_a{box_a[0], box_a[1]};
    const Float2 center_b{box_b[0], box_b[1]};
    const float a_angle_cos = std::cos(a_angle);
    const float a_angle_sin = std::sin(a_angle);
    const float b_angle_cos = std::cos(b_angle);
    const float b_angle_sin = std::sin(b_angle);

    for (int k = 0; k < 4; ++k) {
        rotate_around_center(center_a, a_angle_cos, a_angle_sin, box_a_corners[k]);
        rotate_around_center(center_b, b_angle_cos, b_angle_sin, box_b_corners[k]);
    }

    box_a_corners[4] = box_a_corners[0];
    box_b_corners[4] = box_b_corners[0];

    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            if (intersection(box_a_corners[i + 1], box_a_corners[i], box_b_corners[j + 1], box_b_corners[j], cross_points[cnt])) {
                poly_center.x += cross_points[cnt].x;
                poly_center.y += cross_points[cnt].y;
                ++cnt;
            }
        }
    }

    for (int k = 0; k < 4; ++k) {
        if (check_box2d(box_a, box_b_corners[k])) {
            poly_center.x += box_b_corners[k].x;
            poly_center.y += box_b_corners[k].y;
            cross_points[cnt++] = box_b_corners[k];
        }
        if (check_box2d(box_b, box_a_corners[k])) {
            poly_center.x += box_a_corners[k].x;
            poly_center.y += box_a_corners[k].y;
            cross_points[cnt++] = box_a_corners[k];
        }
    }

    if (cnt == 0) {
        return false;
    }

    poly_center.x /= cnt;
    poly_center.y /= cnt;

    for (int j = 0; j < cnt - 1; ++j) {
        for (int i = 0; i < cnt - j - 1; ++i) {
            const float ang_i = std::atan2(cross_points[i].y - poly_center.y, cross_points[i].x - poly_center.x);
            const float ang_j = std::atan2(cross_points[i + 1].y - poly_center.y, cross_points[i + 1].x - poly_center.x);
            if (ang_i > ang_j) {
                std::swap(cross_points[i], cross_points[i + 1]);
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
    const float sa = box_a[3] * box_a[4];
    const float sb = box_b[3] * box_b[4];
    const float denom = std::max(sa + sb - s_overlap, 1e-8f);
    const float iou = s_overlap / denom;

    return iou >= nms_thresh;
}

std::vector<TopKEntry>
select_topk(const float *heatmap, unsigned int num_classes, int H, int W, unsigned int max_topk, float sigmoid_eps, bool heatmap_is_logits)
{
    const int HW = H * W;
    std::vector<TopKEntry> selected;
    selected.reserve(static_cast<size_t>(num_classes) * std::min(HW, static_cast<int>(max_topk)));

    std::vector<TopKEntry> per_class;
    per_class.reserve(HW);

    for (unsigned int cls = 0; cls < num_classes; ++cls) {
        per_class.clear();
        const float *cls_ptr = heatmap + static_cast<size_t>(cls) * HW;
        for (int idx = 0; idx < HW; ++idx) {
            const float raw = cls_ptr[idx];
            const float score = heatmap_is_logits ? clip_sigmoid(raw, sigmoid_eps) : raw;
            per_class.push_back({score, idx, static_cast<int>(cls)});
        }
        const size_t keep = std::min(static_cast<size_t>(max_topk), per_class.size());
        if (keep == 0) {
            continue;
        }
        if (keep < per_class.size()) {
            std::nth_element(per_class.begin(), per_class.begin() + keep, per_class.end(),
                             [](const TopKEntry &a, const TopKEntry &b) { return a.score > b.score; });
            per_class.resize(keep);
        }
        selected.insert(selected.end(), per_class.begin(), per_class.end());
    }

    const size_t final_keep = std::min(static_cast<size_t>(max_topk), selected.size());
    if (selected.size() > final_keep && final_keep > 0) {
        std::nth_element(selected.begin(), selected.begin() + final_keep, selected.end(),
                         [](const TopKEntry &a, const TopKEntry &b) { return a.score > b.score; });
        selected.resize(final_keep);
    }
    std::sort(selected.begin(), selected.end(), [](const TopKEntry &a, const TopKEntry &b) { return a.score > b.score; });

    return selected;
}

}  // namespace

PostProcessCPU::PostProcessCPU(const PostProcessParams &params) : params_(params) {}

std::vector<BBox3D> PostProcessCPU::decodeSingleBatch(const PostProcessInput &input,
                                                                   int batch_idx,
                                                                   int H,
                                                                   int W,
                                                                   const TaskConfig &task_cfg,
                                                                   const PostProcessInputChannels &channels) const
{
    std::vector<BBox3D> candidates;
    if (task_cfg.num_classes == 0) {
        return candidates;
    }

    const int spatial = H * W;
    const float *heatmap_ptr = input.heatmap + static_cast<size_t>(batch_idx) * channels.C_hm * spatial;
    const float *reg_ptr = input.reg ? input.reg + static_cast<size_t>(batch_idx) * channels.C_reg * spatial : nullptr;
    const float *height_ptr = input.height ? input.height + static_cast<size_t>(batch_idx) * channels.C_height * spatial : nullptr;
    const float *dim_ptr = input.dim ? input.dim + static_cast<size_t>(batch_idx) * channels.C_dim * spatial : nullptr;
    const float *rot_ptr = input.rot ? input.rot + static_cast<size_t>(batch_idx) * channels.C_rot * spatial : nullptr;
    const float *vel_ptr = input.vel ? input.vel + static_cast<size_t>(batch_idx) * channels.C_vel * spatial : nullptr;

    auto topk_entries = select_topk(heatmap_ptr, task_cfg.num_classes, H, W, params_.max_topk, params_.sigmoid_eps, params_.heatmap_is_logits);
    candidates.reserve(topk_entries.size());

    for (const auto &entry : topk_entries) {
        if (entry.score < params_.score_threshold) {
            continue;
        }
        const int row = entry.index / W;
        const int col = entry.index % W;

        float xs = static_cast<float>(row);
        float ys = static_cast<float>(col);
        if (reg_ptr != nullptr) {
            xs += get_tensor_value(reg_ptr, channels.C_reg, H, W, 0, row, col);
            ys += get_tensor_value(reg_ptr, channels.C_reg, H, W, 1, row, col);
        }
        else {
            xs += 0.5f;
            ys += 0.5f;
        }

        const float x_world = xs * params_.out_size_factor * params_.voxel_size[0] + params_.pc_range_min[0];
        const float y_world = ys * params_.out_size_factor * params_.voxel_size[1] + params_.pc_range_min[1];
        const float z = height_ptr ? get_tensor_value(height_ptr, channels.C_height, H, W, 0, row, col) : 0.0f;

        float dl = dim_ptr ? get_tensor_value(dim_ptr, channels.C_dim, H, W, 0, row, col) : 0.0f;
        float dw = dim_ptr ? get_tensor_value(dim_ptr, channels.C_dim, H, W, 1, row, col) : 0.0f;
        float dh = dim_ptr ? get_tensor_value(dim_ptr, channels.C_dim, H, W, 2, row, col) : 0.0f;
        if (params_.norm_bbox) {
            dl = std::exp(dl);
            dw = std::exp(dw);
            dh = std::exp(dh);
        }

        float rot_sin = 0.0f;
        float rot_cos = 1.0f;
        if (rot_ptr != nullptr) {
            rot_sin = get_tensor_value(rot_ptr, channels.C_rot, H, W, 0, row, col);
            rot_cos = get_tensor_value(rot_ptr, channels.C_rot, H, W, 1, row, col);
        }
        const float yaw = std::atan2(rot_sin, rot_cos);

        float vx = 0.0f;
        float vy = 0.0f;
        if (params_.use_velocity && vel_ptr != nullptr) {
            vx = get_tensor_value(vel_ptr, channels.C_vel, H, W, 0, row, col);
            vy = get_tensor_value(vel_ptr, channels.C_vel, H, W, 1, row, col);
        }

        candidates.push_back({x_world, y_world, z, dl, dw, dh, vx, vy, yaw, entry.cls + static_cast<int>(task_cfg.label_offset), entry.score});
    }

    return candidates;
}

std::vector<int> PostProcessCPU::runCircleNms(const std::vector<BBox3D> &candidates, float distance_thresh, unsigned int max_keep) const
{
    std::vector<int> order(candidates.size());
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(), [&](int lhs, int rhs) { return candidates[lhs].score > candidates[rhs].score; });

    std::vector<int> keep;
    keep.reserve(std::min<size_t>(order.size(), max_keep));
    // Python CenterHead provides min_radius as the squared distance threshold already
    const float radius_sq = distance_thresh;
    std::vector<bool> suppressed(order.size(), false);

    for (size_t i = 0; i < order.size(); ++i) {
        if (suppressed[i]) {
            continue;
        }
        const int idx = order[i];
        keep.push_back(idx);
        if (keep.size() >= max_keep) {
            break;
        }
        for (size_t j = i + 1; j < order.size(); ++j) {
            if (suppressed[j]) {
                continue;
            }
            const int next_idx = order[j];
            const float dx = candidates[idx].x - candidates[next_idx].x;
            const float dy = candidates[idx].y - candidates[next_idx].y;
            if (dx * dx + dy * dy <= radius_sq) {
                suppressed[j] = true;
            }
        }
    }

    return keep;
}

std::vector<int> PostProcessCPU::runRotateNms(const std::vector<BBox3D> &candidates,
                                           const std::vector<BBox3D> &scaled_candidates,
                                           float iou_threshold,
                                           unsigned int pre_max,
                                           unsigned int post_max) const
{
    std::vector<int> order(candidates.size());
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(), [&](int lhs, int rhs) { return candidates[lhs].score > candidates[rhs].score; });

    if (order.size() > pre_max) {
        order.resize(pre_max);
    }

    std::vector<int> keep;
    keep.reserve(std::min(order.size(), static_cast<size_t>(post_max)));

    for (int idx : order) {
        bool suppressed = false;
        for (int kept : keep) {
            const float box_a[7] = {scaled_candidates[idx].x, scaled_candidates[idx].y, scaled_candidates[idx].z,  scaled_candidates[idx].l,
                                    scaled_candidates[idx].w, scaled_candidates[idx].h, scaled_candidates[idx].yaw};
            const float box_b[7] = {scaled_candidates[kept].x, scaled_candidates[kept].y, scaled_candidates[kept].z,  scaled_candidates[kept].l,
                                    scaled_candidates[kept].w, scaled_candidates[kept].h, scaled_candidates[kept].yaw};
            if (devIoU(box_a, box_b, iou_threshold)) {
                suppressed = true;
                break;
            }
        }
        if (!suppressed) {
            keep.push_back(idx);
            if (keep.size() >= post_max) {
                break;
            }
        }
    }

    return keep;
}

std::vector<BBox3D>
PostProcessCPU::decodeTask(const PostProcessInput &input, int batch_size, int H, int W, const TaskConfig &task_cfg, const PostProcessInputChannels &channels) const
{
    std::vector<BBox3D> decoded;
    for (int batch_idx = 0; batch_idx < batch_size; ++batch_idx) {
        auto candidates = decodeSingleBatch(input, batch_idx, H, W, task_cfg, channels);
        if (candidates.empty()) {
            continue;
        }

        std::vector<int> keep_indices;
        if (task_cfg.nms_type == NmsType::kCircle) {
            keep_indices = runCircleNms(candidates, task_cfg.circle_radius, params_.nms_post_max_size);
        }
        else {
            std::vector<BBox3D> scaled = candidates;
            for (auto &cand : scaled) {
                const unsigned int local_label = cand.label - task_cfg.label_offset;
                const float scale = task_cfg.nms_scale[std::min(local_label, MAX_CLASSES_PER_TASK - 1)];
                cand.l *= scale;
                cand.w *= scale;
            }
            keep_indices = runRotateNms(candidates, scaled, params_.nms_iou_threshold, params_.pre_max_size, params_.nms_post_max_size);
        }

        for (int idx : keep_indices) {
            const auto &cand = candidates[idx];
            if (!(cand.x >= params_.post_center_limit_range[0] && cand.x <= params_.post_center_limit_range[3])) {
                continue;
            }
            if (!(cand.y >= params_.post_center_limit_range[1] && cand.y <= params_.post_center_limit_range[4])) {
                continue;
            }
            if (!(cand.z >= params_.post_center_limit_range[2] && cand.z <= params_.post_center_limit_range[5])) {
                continue;
            }

            decoded.emplace_back(cand.x, cand.y, cand.z - cand.h * 0.5f, cand.l, cand.w, cand.h, cand.vx, cand.vy, cand.yaw, static_cast<int>(cand.label),
                                 cand.score);
        }
    }

    return decoded;
}
