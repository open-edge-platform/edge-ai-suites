#ifndef _POSTPROCESS_CPU_HPP_
#define _POSTPROCESS_CPU_HPP_

#include <vector>
#include "configs.hpp"

class PostProcessCPU {
  private:
    PostProcessParams params_;

  public:
    PostProcessCPU() = delete;
    explicit PostProcessCPU(const PostProcessParams &params);
    ~PostProcessCPU() = default;

    std::vector<BBox3D>
    decodeTask(const PostProcessInput &input, int batch_size, int H, int W, const TaskConfig &task_cfg, const PostProcessInputChannels &channels) const;

  private:
    std::vector<BBox3D>
    decodeSingleBatch(const PostProcessInput &input, int batch_idx, int H, int W, const TaskConfig &task_cfg, const PostProcessInputChannels &channels) const;
    std::vector<int> runCircleNms(const std::vector<BBox3D> &candidates, float radius, unsigned int max_keep) const;
    std::vector<int> runRotateNms(const std::vector<BBox3D> &candidates,
                                  const std::vector<BBox3D> &scaled_candidates,
                                  float iou_threshold,
                                  unsigned int pre_max,
                                  unsigned int post_max) const;
};

#endif