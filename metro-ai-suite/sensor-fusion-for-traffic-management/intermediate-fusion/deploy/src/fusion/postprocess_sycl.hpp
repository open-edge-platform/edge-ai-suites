#ifndef _POSTPROCESS_SYCL_HPP_
#define _POSTPROCESS_SYCL_HPP_

#include <sycl/sycl.hpp>

#include <memory>
#include <vector>

#include "configs.hpp"


class PostProcessSycl {
  public:
    PostProcessSycl() = delete;
    PostProcessSycl(const PostProcessParams &params, sycl::queue &queue);
    ~PostProcessSycl();

    std::vector<BBox3D>
    decodeTask(const PostProcessInput &input, int batch_size, int H, int W, const TaskConfig &task_cfg, const PostProcessInputChannels &channels);

  private:
    struct ScratchBuffers;

    PostProcessParams params_;
    sycl::queue &queue_;
    std::unique_ptr<ScratchBuffers> scratch_;

    // Non-const: these methods update cached USM scratch buffers in ScratchBuffers
    // to avoid per-frame USM malloc/free inside NMS kernels.
    std::vector<int> runCircleNmsDevice(BBox3D *candidates, size_t cand_count, float distance_thresh, unsigned int max_keep);
    std::vector<int> runRotateNmsDevice(BBox3D *candidates,
                                        size_t cand_count,
                                        const TaskConfig &task_cfg,
                                        float iou_threshold,
                                        unsigned int pre_max,
                                        unsigned int post_max);
};

#endif