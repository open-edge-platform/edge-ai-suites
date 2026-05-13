#include "vpp_decode.h"
#include "vpp_postprocessing.h"
#include "vpp_system.h"
#include "vpp_common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <thread>
#include <vector>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <iomanip>
#include "opencv2/opencv.hpp"
#include "openvino/openvino.hpp"
#include "openvino/opsets/opset1.hpp"
#include "openvino/runtime/intel_gpu/ocl/va.hpp"
#include <va/va.h>

using namespace cv;
using namespace ov::preprocess;

const int NUM_STREAMS        = 16;
const int NUM_STREAMS_INFER  = 8;
const size_t ORIGIN_HEIGHT   = 1088;
const size_t ORIGIN_WIDTH    = 1920;
const int DET_INPUT_SIZE     = 640;
const int MAX_ROI_PER_FRAME  = 1;
const std::string LABEL_PATH = "/opt/intel/vppsdk/example/VA_example/imagenet_2012.txt";

const int SKIP_FRAMES = 3;
const int SKIP_FRAMES_CLS = 3;
const bool SAVE_JSON = false;
const bool IFRAME_ONLY = false;

// --- 辅助函数：加载 Label ---
std::vector<std::string> load_labels(const std::string& path) {
    std::vector<std::string> labels;
    std::ifstream f(path);
    std::string line;
    while (std::getline(f, line)) {
        size_t pos = line.find(' ');
        if (pos != std::string::npos) labels.push_back(line.substr(pos + 1));
        else labels.push_back(line);
    }
    if (labels.empty())
        for (int i = 0; i < 1000; i++) labels.push_back("Class_" + std::to_string(i));
    return labels;
}

// --- 模型配置：检测模型 (YOLOv8) ---
// 输入：NV12 双平面 VA surface，OpenVINO GPU 内部完成 NV12→RGB + 归一化
std::shared_ptr<ov::Model> setupDetModel(ov::Core& core, const std::string& path) {
    auto model = core.read_model(path);
    model->reshape({{1, 3, DET_INPUT_SIZE, DET_INPUT_SIZE}});
    PrePostProcessor ppp(model);
    ppp.input().tensor()
        .set_element_type(ov::element::u8)
        .set_color_format(ColorFormat::NV12_TWO_PLANES, {"y", "uv"})
        .set_memory_type(ov::intel_gpu::memory_type::surface);
    ppp.input().preprocess()
        .convert_color(ColorFormat::RGB)
        .convert_element_type(ov::element::f32)
        .scale(255.0f);
    ppp.input().model().set_layout("NCHW");
    return ppp.build();
}

// --- 模型配置：分类模型 (ResNet) ---
// 输入：NV12 双平面 VA surface，OpenVINO GPU 内部完成 NV12→RGB + ImageNet 归一化
std::shared_ptr<ov::Model> setupClsModel(ov::Core& core, const std::string& path) {
    auto model = core.read_model(path);
    model->reshape({ov::PartialShape{1, 3, 224, 224}});
    PrePostProcessor ppp(model);
    ppp.input().tensor()
        .set_element_type(ov::element::u8)
        .set_color_format(ColorFormat::NV12_TWO_PLANES, {"y", "uv"})
        .set_memory_type(ov::intel_gpu::memory_type::surface);
    ppp.input().preprocess()
        .convert_color(ColorFormat::RGB)
        .convert_element_type(ov::element::f32)
        .mean({123.675f, 116.28f, 103.53f})
        .scale({58.395f, 57.12f, 57.375f});
    ppp.input().model().set_layout("NCHW");
    ppp.output().postprocess().custom([](const ov::Output<ov::Node>& node) {
        auto softmax = std::make_shared<ov::opset1::Softmax>(node, 1);
        return softmax->output(0);
    });
    ppp.output().tensor().set_element_type(ov::element::f32);
    return ppp.build();
}

// --- 后处理：YOLOv8（仅处理推理输出的小数组，在 CPU 上，数据量极小）---
std::pair<std::vector<Rect>, std::vector<int>> postprocess(const ov::Tensor& output, float sx, float sy) {
    auto shape = output.get_shape();
    float* data_ptr = const_cast<float*>(output.data<float>());
    Mat out(shape[1], shape[2], CV_32F, data_ptr);
    transpose(out, out);
    std::vector<int> indices;
    std::vector<float> scores;
    std::vector<Rect> boxes;
    for (int i = 0; i < out.rows; i++) {
        Mat probs = out.row(i).colRange(4, out.cols);
        double s; Point id; minMaxLoc(probs, 0, &s, 0, &id);
        if (s > 0.45) {
            float cx = out.at<float>(i, 0), cy = out.at<float>(i, 1);
            float w  = out.at<float>(i, 2), h  = out.at<float>(i, 3);
            boxes.push_back(Rect(int((cx-0.5f*w)*sx), int((cy-0.5f*h)*sy),
                                 int(w*sx), int(h*sy)));
            scores.push_back((float)s);
        }
    }
    dnn::NMSBoxes(boxes, scores, 0.45, 0.5, indices);
    return {boxes, indices};
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        printf("Usage: %s <det_xml> <cls_xml>\n", argv[0]);
        return -1;
    }

    // 0. 设置 VA-API 驱动路径（等效于 source /opt/intel/vppsdk/env.sh）
    setenv("LIBVA_DRIVERS_PATH", "/opt/intel/media/lib64", 0);
    setenv("LIBVA_DRIVER_NAME",  "iHD",                   0);
    setenv("LD_LIBRARY_PATH",
           "/opt/intel/media/lib64:/opt/intel/vppsdk/lib", 0);

    // 1. VPP 先初始化，VPP 内部会创建自己的 VA context
    VPP_Init();

    VPP_DECODE_STREAM_Attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.CodecStandard = VPP_CODEC_STANDARD_H264;
    attr.OutputFormat  = VPP_PIXEL_FORMAT_NV12;
    attr.InputMode     = VPP_DECODE_INPUT_MODE_STREAM;

    // 2. 启动 stream 0，喂数据拿第一帧，通过 ExportSurface 取出 VPP 内部的 VADisplay
    //    必须用同一个 VADisplay 建立 OpenVINO context，VA surface 才能零拷贝共享
    VPP_DECODE_STREAM_Create(0, &attr);
    VPP_DECODE_STREAM_Start(0);

    FILE*    fp         = fopen("/opt/video/car_1080p.h264", "rb");
    uint8_t* stream_buf = (uint8_t*)malloc(1024 * 1024);

    VADisplay va_display = nullptr;
    while (!va_display) {
        size_t len = fread(stream_buf, 1, 1024 * 1024, fp);
        if (len <= 0) { fseek(fp, 0, SEEK_SET); continue; }
        VPP_DECODE_STREAM_InputBuffer in_buf = {stream_buf, (uint32_t)len, 0, false};
        VPP_DECODE_STREAM_FeedInput(0, &in_buf, 1000);

        VPP_SURFACE_HDL hdl;
        if (VPP_DECODE_STREAM_GetFrame(0, &hdl, 500) == VPP_STATUS_SUCCESS) {
            VPP_SURFACE_EXPORT ex;
            if (VPP_SYS_ExportSurface(hdl, &ex) == VPP_STATUS_SUCCESS)
                va_display = (VADisplay)ex.VADisplay;
            VPP_DECODE_STREAM_ReleaseFrame(0, hdl);
        }
    }
    printf("Got VADisplay from VPP: %p\n", va_display);

    // 3. 用 VPP 的 VADisplay 创建 OpenVINO GPU 共享 context 并编译模型
    //    此后 ExportSurface 拿到的 VASurfaceId 与此 context 属于同一 VA context，可零拷贝共享
    ov::Core core;
    auto va_context   = ov::intel_gpu::ocl::VAContext(core, va_display);
    auto det_m        = setupDetModel(core, argv[1]);
    auto cls_m        = setupClsModel(core, argv[2]);
    auto cls_labels   = load_labels(LABEL_PATH);
    auto compiled_det = core.compile_model(det_m, va_context);
    auto compiled_cls = core.compile_model(cls_m, va_context);
    printf("Models compiled on GPU successfully\n");

    // 4. 创建剩余解码 stream 及全部 POSTPROC stream
    for (int i = 1; i < NUM_STREAMS; i++)
        VPP_DECODE_STREAM_Create(i, &attr);

    for (int i = 0; i < NUM_STREAMS; i++) {
        // YOLO 缩放 stream（id = i + 200）：1920x1088 → 640x640，保持 NV12
        VPP_POSTPROC_StreamAttr sYolo;
        memset(&sYolo, 0, sizeof(sYolo));
        sYolo.CropX       = 0;
        sYolo.CropY       = 0;
        sYolo.CropW       = ORIGIN_WIDTH;
        sYolo.CropH       = ORIGIN_HEIGHT;
        sYolo.OutWidth    = DET_INPUT_SIZE;
        sYolo.OutHeight   = DET_INPUT_SIZE;
        sYolo.ColorFormat = VPP_PIXEL_FORMAT_NV12;
        sYolo.Depth       = 3;
        VPP_POSTPROC_STREAM_Create(i + 200, &sYolo);

        // ROI 抠图 stream 池（id = i * MAX_ROI_PER_FRAME + r + 400）
        // 每路视频预建 MAX_ROI_PER_FRAME 个 stream，检测后动态更新裁剪坐标
        for (int r = 0; r < MAX_ROI_PER_FRAME; r++) {
            VPP_POSTPROC_StreamAttr sRoi;
            memset(&sRoi, 0, sizeof(sRoi));
            sRoi.CropX       = 0;
            sRoi.CropY       = 0;
            sRoi.CropW       = ORIGIN_WIDTH;
            sRoi.CropH       = ORIGIN_HEIGHT;
            sRoi.OutWidth    = 224;
            sRoi.OutHeight   = 224;
            sRoi.ColorFormat = VPP_PIXEL_FORMAT_NV12;
            sRoi.Depth       = 2;
            VPP_POSTPROC_STREAM_Create(i * MAX_ROI_PER_FRAME + r + 400, &sRoi);
        }
    }

    // 5. 启动所有 stream（stream 0 已启动，其余逐一启动）
    for (int i = 1; i < NUM_STREAMS; i++)
        VPP_DECODE_STREAM_Start(i);
    for (int i = 0; i < NUM_STREAMS; i++) {
        VPP_POSTPROC_STREAM_Start(i + 200);
        for (int r = 0; r < MAX_ROI_PER_FRAME; r++)
            VPP_POSTPROC_STREAM_Start(i * MAX_ROI_PER_FRAME + r + 400);
    }

    // 6. 每路视频一个推理工作线程
    auto worker = [&](int id) {
        auto req_det = compiled_det.create_infer_request();
        auto req_cls = compiled_cls.create_infer_request();
        int  frame_count  = 0;
        const int32_t yolo_id = id + 200;

        while (true) {
            // --- Step 1: 拿原始解码帧 ---
            VPP_SURFACE_HDL hdl_src;
            VPP_STATUS sts1 = VPP_DECODE_STREAM_GetFrame(id, &hdl_src, 2000);
            if (sts1 != VPP_STATUS_SUCCESS) {
                printf("[DBG][Stream %d] GetFrame failed: %d\n", id, sts1);
                continue;
            }

            if (id < NUM_STREAMS_INFER && ++frame_count % SKIP_FRAMES == 0) {
                printf("[DBG][Stream %d] frame_count=%d, entering infer path\n", id, frame_count);

                // --- Step 2: 送原图给 YOLO 缩放 stream ---
                VPP_STATUS sts2 = VPP_POSTPROC_STREAM_SendFrame(yolo_id, &hdl_src, 100);
                if (sts2 != VPP_STATUS_SUCCESS) {
                    printf("[DBG][Stream %d] YOLO SendFrame failed: %d\n", id, sts2);
                    VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
                    continue;
                }

                // --- Step 3: 拿到 640x640 NV12 缩放帧 ---
                VPP_SURFACE_HDL hdl_640;
                VPP_STATUS sts3 = VPP_POSTPROC_STREAM_GetFrame(yolo_id, &hdl_640, 2000);
                if (sts3 != VPP_STATUS_SUCCESS) {
                    printf("[DBG][Stream %d] YOLO GetFrame failed: %d\n", id, sts3);
                    VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
                    continue;
                }
                printf("[DBG][Stream %d] YOLO GetFrame OK\n", id);

                // --- Step 4: 导出 VA surface，零拷贝送 YOLO 推理 ---
                VPP_SURFACE_EXPORT ex640;
                VPP_SYS_ExportSurface(hdl_640, &ex640);
                auto [y_det, uv_det] = va_context.create_tensor_nv12(
                    DET_INPUT_SIZE, DET_INPUT_SIZE, ex640.VASurfaceId);
                req_det.set_input_tensor(0, y_det);
                req_det.set_input_tensor(1, uv_det);
                req_det.infer();
                printf("[DBG][Stream %d] YOLO infer done\n", id);

                // --- Step 5: YOLO 后处理（读推理结果小数组，CPU）---
                auto det_res = postprocess(
                    req_det.get_output_tensor(0),
                    ORIGIN_WIDTH  / static_cast<float>(DET_INPUT_SIZE),
                    ORIGIN_HEIGHT / static_cast<float>(DET_INPUT_SIZE));

                VPP_POSTPROC_STREAM_ReleaseFrame(yolo_id, &hdl_640);
                printf("[DBG][Stream %d] YOLO detected %zu objects\n", id, det_res.second.size());

                // --- Save detection results to JSON file ---
                if (SAVE_JSON) {
                    std::ofstream json_file;
                    std::string json_name = "det_result_stream_" + std::to_string(id) + "_" + "frame" + "_" + std::to_string(frame_count) + ".json";
                    json_file.open(json_name, std::ios::app);
                    json_file << "{ \"frame\": " << frame_count << ", \"objects\": [";
                    for (size_t k = 0; k < det_res.second.size(); ++k) {
                        Rect box = det_res.first[det_res.second[k]];
                        json_file << "{"
                                  << "\"x\":" << box.x << ","
                                  << "\"y\":" << box.y << ","
                                  << "\"width\":" << box.width << ","
                                  << "\"height\":" << box.height << "}";
                        if (k + 1 < det_res.second.size()) json_file << ",";
                    }
                    json_file << "] }\n";
                    json_file.close();
                }

                // --- Step 6: 对每个 bounding box，GPU 抠图 + 缩放 + ResNet 推理 ---
                int roi_count = 0;
                for (size_t k = 0; k < det_res.second.size() && roi_count < MAX_ROI_PER_FRAME && frame_count % SKIP_FRAMES_CLS == 0; k++) {
                    Rect box = det_res.first[det_res.second[k]];

                    // // 严格边界校验，防止 VPP "Invalid crop params"：
                    // // sy=1088/640≈1.7（非整数），底部坐标经整数截断后容易越界
                    // box.x      = std::max(0, box.x);
                    // box.y      = std::max(0, box.y);
                    // if (box.x >= (int)ORIGIN_WIDTH || box.y >= (int)ORIGIN_HEIGHT) continue;
                    // box.width  = std::min(box.width,  (int)ORIGIN_WIDTH  - box.x);
                    // box.height = std::min(box.height, (int)ORIGIN_HEIGHT - box.y);
                    // if (box.width < 32 || box.height < 32) continue;

                    //dynamic crop is not supported in current VPP version, so we set the crop area to the whole frame and rely on the detection model to do the cropping by setting the input tensor's ROI. This is a workaround and may not be optimal.
                    box.x      = 0;
                    box.y      = 0;
                    box.width  = ORIGIN_WIDTH;
                    box.height = ORIGIN_HEIGHT;

                    int32_t roi_id = id * MAX_ROI_PER_FRAME + roi_count + 400;
                    printf("[DBG][Stream %d] ROI[%d] box=(%d,%d,%d,%d) roi_id=%d\n",
                           id, (int)k, box.x, box.y, box.width, box.height, roi_id);

                    VPP_POSTPROC_StreamAttr sRoi;
                    memset(&sRoi, 0, sizeof(sRoi));
                    sRoi.CropX       = (uint32_t)box.x;
                    sRoi.CropY       = (uint32_t)box.y;
                    sRoi.CropW       = (uint32_t)box.width;
                    sRoi.CropH       = (uint32_t)box.height;
                    sRoi.OutWidth    = 224;
                    sRoi.OutHeight   = 224;
                    sRoi.ColorFormat = VPP_PIXEL_FORMAT_NV12;
                    sRoi.Depth       = 2;

                    VPP_STATUS stsSet = VPP_POSTPROC_STREAM_SetAttr(roi_id, &sRoi);
                    printf("[DBG][Stream %d] ROI[%d] SetAttr CropX=%u CropY=%u CropW=%u CropH=%u ret=%d\n",
                           id, (int)k, sRoi.CropX, sRoi.CropY, sRoi.CropW, sRoi.CropH, stsSet);
                    if (stsSet != VPP_STATUS_SUCCESS) continue;

                    // 送原图 → GPU 裁剪 + 缩放
                    VPP_STATUS stsSend = VPP_POSTPROC_STREAM_SendFrame(roi_id, &hdl_src, 100);
                    printf("[DBG][Stream %d] ROI[%d] SendFrame ret=%d\n", id, (int)k, stsSend);
                    if (stsSend != VPP_STATUS_SUCCESS) continue;

                    VPP_SURFACE_HDL hdl_roi;
                    VPP_STATUS stsGet = VPP_POSTPROC_STREAM_GetFrame(roi_id, &hdl_roi, 2000);
                    printf("[DBG][Stream %d] ROI[%d] GetFrame ret=%d\n", id, (int)k, stsGet);
                    if (stsGet != VPP_STATUS_SUCCESS) continue;

                    // 导出 VA surface，零拷贝送 ResNet 推理
                    VPP_SURFACE_EXPORT exRoi;
                    VPP_SYS_ExportSurface(hdl_roi, &exRoi);
                    auto [y_cls, uv_cls] = va_context.create_tensor_nv12(224, 224, exRoi.VASurfaceId);
                    req_cls.set_input_tensor(0, y_cls);
                    req_cls.set_input_tensor(1, uv_cls);
                    req_cls.infer();

                    // 读分类结果（小数组，CPU）
                    auto out_cls     = req_cls.get_output_tensor(0);
                    const float* d   = out_cls.data<const float>();
                    int cls_id       = std::max_element(d, d + out_cls.get_size()) - d;
                    float confidence = d[cls_id];
                    if (cls_id >= 0 && cls_id < (int)cls_labels.size()) {
                        std::cout << "[Stream " << id << "] Obj Found! Name: "
                                  << cls_labels[cls_id] << " (" << cls_id << "), Conf: "
                                  << std::fixed << std::setprecision(3) << confidence << std::endl;
                    }

                    VPP_POSTPROC_STREAM_ReleaseFrame(roi_id, &hdl_roi);
                    roi_count++;
                }
            }

            // --- Step 7: 释放原始帧 ---
            VPP_DECODE_STREAM_ReleaseFrame(id, hdl_src);
        }
    };

    std::vector<std::thread> threads;
    for (int i = 0; i < NUM_STREAMS; i++) threads.emplace_back(worker, i);

    // 重置文件到头，正式循环喂所有 stream
    fseek(fp, 0, SEEK_SET);
    while (true) {
        size_t len = fread(stream_buf, 1, 1024 * 1024, fp);
        if (len <= 0) { fseek(fp, 0, SEEK_SET); continue; }
        VPP_DECODE_STREAM_InputBuffer vpp_in_buf = {stream_buf, (uint32_t)len, 0, false};
        if (IFRAME_ONLY) {
            // 简单过滤非 I 帧（不保证完全准确，仅示例）
            // Find the first NAL unit (start code 0x000001 or 0x00000001)
            size_t nal_start = 0;
            while (nal_start + 4 < len) {
                if ((stream_buf[nal_start] == 0x00 && stream_buf[nal_start + 1] == 0x00 &&
                     ((stream_buf[nal_start + 2] == 0x01) ||
                      (stream_buf[nal_start + 2] == 0x00 && stream_buf[nal_start + 3] == 0x01)))) {
                    break;
                }
                nal_start++;
            }
            // Find NAL header after start code
            size_t nal_header = nal_start;
            if (nal_header + 4 < len) {
                if (stream_buf[nal_header + 2] == 0x01)
                    nal_header += 3;
                else if (stream_buf[nal_header + 3] == 0x01)
                    nal_header += 4;
                else
                    nal_header = len; // not found
            } else {
                nal_header = len;
            }
            bool is_iframe = false;
            if (nal_header < len) {
                uint8_t nal_unit_type = stream_buf[nal_header] & 0x1F;
                // 0x05 is IDR (I-frame) for H.264
                if (nal_unit_type == 0x05)
                    is_iframe = true;
            }
            if (!is_iframe) continue;
            // Find the end of the current I-frame NAL unit
            size_t nal_end = nal_header + 1;
            while (nal_end + 4 < len) {
                // Look for next NAL start code
                if ((stream_buf[nal_end] == 0x00 && stream_buf[nal_end + 1] == 0x00 &&
                     ((stream_buf[nal_end + 2] == 0x01) ||
                      (stream_buf[nal_end + 2] == 0x00 && stream_buf[nal_end + 3] == 0x01)))) {
                    break;
                }
                nal_end++;
            }
            len = nal_end - nal_start; // Only feed the I-frame NAL unit
            vpp_in_buf = {stream_buf + nal_start, (uint32_t)len, 0, false};
        }
        for (int i = 0; i < NUM_STREAMS; i++) VPP_DECODE_STREAM_FeedInput(i, &vpp_in_buf, -1);
        usleep(33000);
    }

    return 0;
}
