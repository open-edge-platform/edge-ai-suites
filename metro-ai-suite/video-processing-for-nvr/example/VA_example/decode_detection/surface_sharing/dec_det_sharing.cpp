#include "vpp_decode.h"
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
#include "opencv2/opencv.hpp"
#include "openvino/openvino.hpp"

#include <openvino/runtime/intel_gpu/ocl/va.hpp>
#include <openvino/runtime/intel_gpu/properties.hpp>

using namespace cv;
using namespace dnn;
using namespace ov::preprocess;

const std::string inference_device = "GPU";

size_t origin_height = 1088;
size_t origin_width = 1920;

std::shared_ptr<ov::Model> loadAndPreprocessModel(std::string model_path) {
    ov::Core core;
    std::shared_ptr<ov::Model> model = core.read_model(model_path);
    model->reshape({{1, 640, 640, 3}});
    std::string input_tensor_name = model->input().get_any_name();
    PrePostProcessor ppp = PrePostProcessor(model);
    InputInfo& input_info = ppp.input(input_tensor_name);
    input_info.tensor()
    .set_element_type(ov::element::u8)
    .set_color_format(ov::preprocess::ColorFormat::NV12_TWO_PLANES, {"y", "uv"})
    .set_memory_type(ov::intel_gpu::memory_type::surface)
    .set_spatial_static_shape(origin_height, origin_width);
    input_info.preprocess()
    .convert_color(ColorFormat::RGB)
    .resize(ResizeAlgorithm::RESIZE_NEAREST, 640, 640);
    // .convert_element_type(ov::element::f32)
    // .scale({255.0f, 255.0f, 255.0f});
    input_info.model().set_layout("NHWC");
    model = ppp.build();
    return model;
}

std::pair<std::vector<cv::Rect>, std::vector<int>> postprocess(const ov::Tensor &output, float scale_x, float scale_y) {
    auto output_shape = output.get_shape();
    int rows = output_shape[2];
    int dimensions = output_shape[1];
    float* data = output.data<float>();
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
            int left = int((cx - 0.5 * w) * scale_x);
            int top = int((cy - 0.5 * h) * scale_y);
            int width = int(w * scale_x);
            int height = int(h * scale_y);
            boxes.push_back(Rect(left, top, width, height));
        }
    }
    std::vector<int> indices;
    NMSBoxes(boxes, class_scores, score_threshold, nms_threshold, indices);
    return std::make_pair(boxes, indices);
}

int main(int argc, char* argv[])
{
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <model_path>" << std::endl;
        return 1;
    }
    std::string det_model_path = argv[1];
    std::shared_ptr<ov::Model> det_model = loadAndPreprocessModel(det_model_path);
    ov::Core core;
    VPP_Init();
    for (int32_t id = 0; id < 16; ++id) {
        VPP_DECODE_STREAM_Attr attr;
        attr.CodecStandard = VPP_CODEC_STANDARD_H264;
        attr.OutputFormat = VPP_PIXEL_FORMAT_NV12;
        attr.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
        attr.OutputHeight = 0;
        attr.OutputWidth = 0;
        attr.OutputBufQueueLength = 0;
        attr.RingBufferSize = 0;
        assert(VPP_DECODE_STREAM_Create(id, &attr) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_SetOutputMode(id, VPP_DECODE_OUTPUT_MODE_PLAYBACK) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Start(id) == VPP_STATUS_SUCCESS);
    }

    auto getSurface = [&](int32_t id) {
        ov::intel_gpu::ocl::VAContext* ptr_context = nullptr;
        ov::CompiledModel* compiled_model = nullptr;
        std::thread::id thread_id = std::this_thread::get_id();
        usleep(1'000'000);
        int i = 0;
        int frame_counter = 0;
        int skip_frames = 3;
        bool isFirstRun = true;
        float scale_x = origin_width / 640.0;
        float scale_y = origin_height / 640.0;
        while (1) {
            VPP_SURFACE_HDL hdl;
            VPP_STATUS sts = VPP_DECODE_STREAM_GetFrame(id, &hdl, 5000);
            if (sts != VPP_STATUS_SUCCESS) {
                continue;
            }
            VPP_SURFACE_EXPORT vppSurfExport;
            vppSurfExport.Type = VPP_SURFACE_EXPORT_TYPE_VA;
            VPP_SYS_ExportSurface(hdl, &vppSurfExport);
            frame_counter++;
            if (frame_counter % skip_frames == 0 && id < 16){
                if (!compiled_model) {
                    VADisplay disp = vppSurfExport.VADisplay;
                        if (!ptr_context) {
                            ptr_context = new ov::intel_gpu::ocl::VAContext(core, disp);
                            compiled_model =  new ov::CompiledModel(core.compile_model(det_model, *ptr_context, ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY)));
                        }
                    }
                auto input0 = det_model->get_parameters().at(0);
                auto input1 = det_model->get_parameters().at(1);
                auto shape = input0->get_shape();
                auto height = origin_height;
                auto width = origin_width;
                VASurfaceID va_surface = vppSurfExport.VASurfaceId;
                auto nv12_blob = ptr_context->create_tensor_nv12(height, width, va_surface);
                auto infer_requests_det = compiled_model->create_infer_request();
                infer_requests_det.set_tensor(input0->get_friendly_name(), nv12_blob.first);
                infer_requests_det.set_tensor(input1->get_friendly_name(), nv12_blob.second);
                infer_requests_det.infer();
                // infer_requests_det.start_async();
                // infer_requests_det.wait();
                
                //Retrieve inference results
                auto output_tensor_det = infer_requests_det.get_output_tensor(0);
                auto result_det = postprocess(output_tensor_det, scale_x, scale_y);
                // remove last osd area
          
                auto boxes = result_det.first;
                auto indices = result_det.second;
                for (size_t i = 0; i < indices.size(); i++) {
                    int index = indices[i];
                    cv::Rect box = boxes[index];
                    int left = box.x;
                    int top = box.y;
                    int width = box.width;
                    int height = box.height; 
                    
                    printf("Detected box: index=%d, left=%d, top=%d, width=%d, height=%d\n", index, left, top, width, height);
                }
                isFirstRun = false;
            }
            assert(VPP_DECODE_STREAM_ReleaseFrame(id, hdl) == VPP_STATUS_SUCCESS);
        }
    };
    std::vector<std::thread> threads;
    for (int i = 0; i < 16; i++) {
        threads.push_back(std::thread(getSurface, i));
    }
    FILE* fp = fopen("/opt/video/car_1080p.h264", "rb");

    const uint64_t size = 1 * 1024 * 1024;
    void* addr = malloc(size);
    while (true) {
        uint64_t sizeTemp = fread(addr, 1, size, fp);
        VPP_DECODE_STREAM_InputBuffer buffer;
        buffer.pAddr = (uint8_t*)addr;
        buffer.Length = sizeTemp;
        buffer.BasePts = 0;
        buffer.FlagEOStream = false;

        // if(sizeTemp < size) {
        //     buffer.FlagEOStream = true;
        // }
    	std::thread* arrThread[16];
        for (int32_t id = 0; id < 16; ++id) {
            auto feed = [=]() {VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);};
            arrThread[id] = new std::thread(feed);
        }
        for (int32_t id = 0; id < 16; ++id) {
            arrThread[id]->join();
            delete(arrThread[id]);
        }
        if(sizeTemp < size) {
            fseek(fp, 0, SEEK_SET);
        }
    }

    usleep(10000000);
    for (auto& th : threads) {
        th.join();
    }
    free(addr);
    for (int32_t id = 0; id < 16; ++id) {
        assert(VPP_DECODE_STREAM_Stop(id) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Destroy(id) == VPP_STATUS_SUCCESS);
    }
    fclose(fp);
    VPP_DeInit();
}
