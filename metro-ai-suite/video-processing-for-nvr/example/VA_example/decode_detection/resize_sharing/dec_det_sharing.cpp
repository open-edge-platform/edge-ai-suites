#include "vpp_decode.h" 
#include "vpp_postprocessing.h"
#include "vpp_system.h"
#include "vpp_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <unistd.h>
#include <thread>
#include <cmath>
#include <iostream>
#include <chrono>
#include <vector>
#include <mutex>
#include <deque>
#include <map>
#include "opencv2/opencv.hpp"
#include "openvino/openvino.hpp"

#include <openvino/runtime/intel_gpu/ocl/va.hpp>
#include <openvino/runtime/intel_gpu/properties.hpp>

using namespace cv;
using namespace dnn;
using namespace ov::preprocess;

// Basic config
const std::string inference_device = "GPU";
const size_t origin_height = 1088;
const size_t origin_width = 1920;
const int target_size = 640;
const size_t num_stream = 16;

// Load model and set NV12(two-planes, VA surface) -> RGB preprocess
std::shared_ptr<ov::Model> loadAndPreprocessModel(std::string model_path) {
    ov::Core core;
    std::shared_ptr<ov::Model> model = core.read_model(model_path);

    model->reshape({{1, 3, target_size, target_size}});

    std::string input_tensor_name = model->input().get_any_name();
    PrePostProcessor ppp = PrePostProcessor(model);
    InputInfo& input_info = ppp.input(input_tensor_name);

    input_info.tensor()
        .set_element_type(ov::element::u8)
        .set_color_format(ov::preprocess::ColorFormat::NV12_TWO_PLANES, {"y", "uv"})
        .set_memory_type(ov::intel_gpu::memory_type::surface)   // zero-copy VA surface
        .set_spatial_static_shape(target_size, target_size)     // VPP already resized to 640x640
        .set_layout("NHWC");

    input_info.preprocess()
        .convert_color(ColorFormat::RGB);

    input_info.model().set_layout("NCHW");

    return ppp.build();
}

// YOLO postprocess: output [1,84,8400] -> boxes + NMS indices (in 640x640 space)
std::pair<std::vector<cv::Rect>, std::vector<int>> postprocess(const ov::Tensor &output) {
    auto output_shape = output.get_shape();
    float* data = (float*)output.data();
    Mat output_buffer(output_shape[1], output_shape[2], CV_32F, data);
    transpose(output_buffer, output_buffer);

    float score_threshold = 0.3;
    float nms_threshold = 0.7;
    std::vector<int> class_ids;
    std::vector<float> class_scores;
    std::vector<Rect> boxes;

    for (int i = 0; i < output_buffer.rows; i++) {
        Mat classes_scores = output_buffer.row(i).colRange(4, 84);
        Point class_id;
        double maxClassScore;
        minMaxLoc(classes_scores, 0, &maxClassScore, 0, &class_id);

        if (maxClassScore > score_threshold) {
            class_scores.push_back(maxClassScore);
            class_ids.push_back(class_id.x);

            float cx = output_buffer.at<float>(i, 0);
            float cy = output_buffer.at<float>(i, 1);
            float w = output_buffer.at<float>(i, 2);
            float h = output_buffer.at<float>(i, 3);

            boxes.push_back(Rect(int(cx - 0.5 * w), int(cy - 0.5 * h), int(w), int(h)));
        }
    }

    std::vector<int> indices;
    NMSBoxes(boxes, class_scores, score_threshold, nms_threshold, indices);
    return std::make_pair(boxes, indices);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <model_path>" << std::endl;
        return 1;
    }
    std::string det_model_path = argv[1];
    ov::Core core;
    std::shared_ptr<ov::Model> det_model = loadAndPreprocessModel(det_model_path);

    VPP_Init();  // must be called before any VPP API

    VPP_StreamIdentifier ppManualIds[num_stream];

    // Create all pipelines: decode(H264->NV12) + VPP postproc(manual resize to 640x640 NV12)
    for (int32_t id = 0; id < num_stream; ++id) {
        VPP_DECODE_STREAM_Attr dAttr;
        memset(&dAttr, 0, sizeof(dAttr));
        dAttr.CodecStandard = VPP_CODEC_STANDARD_H264;
        dAttr.OutputFormat = VPP_PIXEL_FORMAT_NV12;
        dAttr.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
        VPP_DECODE_STREAM_Create(id, &dAttr);

        VPP_POSTPROC_StreamAttr sAttrManual;
        memset(&sAttrManual, 0, sizeof(sAttrManual));
        sAttrManual.CropX = 0;
        sAttrManual.CropY = 0;
        sAttrManual.CropW = origin_width;
        sAttrManual.CropH = origin_height;
        sAttrManual.OutWidth = target_size;
        sAttrManual.OutHeight = target_size;
        sAttrManual.ColorFormat = VPP_PIXEL_FORMAT_NV12;
        sAttrManual.Rotate = false;
        sAttrManual.Angle = VPP_POSTPROC_ROTATE_0;
        sAttrManual.Denoise = 0;
        sAttrManual.Depth = 3;
        int32_t pp_manual_id = id + 200;
        VPP_POSTPROC_STREAM_Create(pp_manual_id, &sAttrManual);

        ppManualIds[id] = {VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM, VPP_ID_NOT_APPLICABLE, pp_manual_id};

        VPP_DECODE_STREAM_Start(id);
        VPP_POSTPROC_STREAM_Start(pp_manual_id);
    }

    // Shared OpenVINO context/model across threads; protected by a mutex
    ov::intel_gpu::ocl::VAContext* shared_ctx = nullptr;
    ov::CompiledModel* shared_model = nullptr;
    std::mutex infer_mtx;
    bool ctx_initialized = false;

    auto getSurface = [&](int32_t id) {
        int32_t manual_id = id + 200;
        int frame_counter = 0;
        const int skip_frames = 3;  // infer every 3 frames

        while (1) {
            VPP_SURFACE_HDL hdl_src;
            if (VPP_DECODE_STREAM_GetFrame(id, &hdl_src, 5000) != VPP_STATUS_SUCCESS) continue;

            if (++frame_counter % skip_frames == 0 && id < num_stream) {
                VPP_SURFACE vppSrc;
                if (VPP_SYS_MapSurface(hdl_src, &vppSrc) != VPP_STATUS_SUCCESS) {
                    VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
                    continue;
                }

                int src_h = vppSrc.Height;
                int src_w = vppSrc.Pitches[0];
                Mat nv12_src(src_h + src_h / 2, src_w, CV_8UC1, vppSrc.Y);
                Mat full_bgr;
                cvtColor(nv12_src, full_bgr, COLOR_YUV2BGR_NV12);

                // Send decoded frame to VPP postproc (manual) to resize to 640x640 NV12
                if (VPP_POSTPROC_STREAM_SendFrame(manual_id, &hdl_src, 100) != VPP_STATUS_SUCCESS) {
                    VPP_SYS_UnmapSurface(hdl_src, &vppSrc);
                    VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
                    continue;
                }

                VPP_SYS_UnmapSurface(hdl_src, &vppSrc);

                VPP_SURFACE_HDL hdl_scaled;
                if (VPP_POSTPROC_STREAM_GetFrame(manual_id, &hdl_scaled, 5000) != VPP_STATUS_SUCCESS) {
                    VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
                    continue;
                }

                VPP_SURFACE_EXPORT vppExport;
                vppExport.Type = VPP_SURFACE_EXPORT_TYPE_VA;
                VPP_SYS_ExportSurface(hdl_scaled, &vppExport);

                std::lock_guard<std::mutex> lock(infer_mtx);

                // Lazy init: create VAContext + compile model only once
                if (!ctx_initialized) {
                    try {
                        shared_ctx = new ov::intel_gpu::ocl::VAContext(core, vppExport.VADisplay);
                        shared_model = new ov::CompiledModel(core.compile_model(det_model, *shared_ctx));
                        ctx_initialized = true;
                        printf("OpenVINO context initialized successfully\n");
                    } catch (const std::exception& e) {
                        printf("Failed to initialize OpenVINO context: %s\n", e.what());
                        VPP_POSTPROC_STREAM_ReleaseFrame(manual_id, &hdl_scaled);
                        continue;
                    }
                }

                try {
                    // Zero-copy NV12 tensor from VA surface
                    auto nv12_blob = shared_ctx->create_tensor_nv12(target_size, target_size, vppExport.VASurfaceId);
                    auto infer_req = shared_model->create_infer_request();
                    auto params = det_model->get_parameters();

                    infer_req.set_tensor(params.at(0)->get_friendly_name(), nv12_blob.first);
                    infer_req.set_tensor(params.at(1)->get_friendly_name(), nv12_blob.second);

                    infer_req.infer();

                    auto result = postprocess(infer_req.get_output_tensor(0));

                    auto boxes = result.first;
                    auto indices = result.second;
                    for (size_t i = 0; i < indices.size(); i++) {
                        int index = indices[i];
                        Rect box = boxes[index];
                        printf("Stream %d Detected box: index=%d, left=%d, top=%d, width=%d, height=%d\n",
                               id, index, box.x, box.y, box.width, box.height);
                    }
                } catch (const std::exception& e) {
                    printf("Stream %d inference error: %s\n", id, e.what());
                }

                VPP_POSTPROC_STREAM_ReleaseFrame(manual_id, &hdl_scaled);
                VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
            } else {
                VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
            }
        }
    };

    std::vector<std::thread> threads;
    for (int i = 0; i < num_stream; i++) threads.push_back(std::thread(getSurface, i));

    // Feed the same H264 stream data into all decoders
    FILE* fp = fopen("/opt/video/car_1080p.h264", "rb");
    const uint64_t b_size = 1024 * 1024;
    void* addr = malloc(b_size);

    while (true) {
        uint64_t s_temp = fread(addr, 1, b_size, fp);
        if (s_temp <= 0) {
            fseek(fp, 0, SEEK_SET);
            continue;
        }

        VPP_DECODE_STREAM_InputBuffer buffer = {(uint8_t*)addr, s_temp, 0, false};

        std::thread* arrThread[num_stream];
        for (int32_t id = 0; id < num_stream; ++id) {
            auto feed = [=]() {VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);};
            arrThread[id] = new std::thread(feed);
        }
        for (int32_t id = 0; id < num_stream; ++id) {
            arrThread[id]->join();
            delete(arrThread[id]);
        }
    }

    VPP_DeInit();
    return 0;
}
