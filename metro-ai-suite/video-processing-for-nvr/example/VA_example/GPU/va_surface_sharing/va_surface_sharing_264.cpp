#include "vpp_decode.h"
#include "vpp_system.h"
#include "vpp_osd.h"
#include "vpp_display.h"
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
std::map<std::thread::id, std::deque<int>> thread_deques;
std::vector<int> current_ids(8, 0);

std::shared_ptr<ov::Model> loadAndPreprocessModel(std::string model_path) {
    ov::Core core;
    std::shared_ptr<ov::Model> model = core.read_model(model_path);
    model->reshape({{1, 3, 640, 640}});
    std::string input_tensor_name = model->input().get_any_name();
    PrePostProcessor ppp = PrePostProcessor(model);
    InputInfo& input_info = ppp.input(input_tensor_name);
    input_info.tensor()
    .set_element_type(ov::element::u8)
    .set_color_format(ov::preprocess::ColorFormat::NV12_TWO_PLANES, {"y", "uv"})
    .set_memory_type(ov::intel_gpu::memory_type::surface)
    .set_spatial_static_shape(1088, 1920);
    input_info.preprocess()
    .convert_color(ColorFormat::RGB)
    .resize(ResizeAlgorithm::RESIZE_NEAREST, 640, 640)
    .convert_element_type(ov::element::f32)
    .scale({255.0f, 255.0f, 255.0f});
    input_info.model().set_layout("NCHW");
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

    // Get avaliable device
    VPP_DISPLAY_Dev *pDevArray = nullptr;
    uint32_t deviceCount;
    assert(VPP_DISPLAY_DEV_GetList(&pDevArray, &deviceCount) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_GetList, DeviceCount: %u \n", deviceCount);
    assert(deviceCount > 0);
    assert(pDevArray != nullptr);
    printf("DevAttrsCount: %u \n", pDevArray->DevAttrsCount);

    // Select first avaliable device and create
    int32_t deviceId = pDevArray->DevId;
    assert(VPP_DISPLAY_DEV_Create(deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Create Done \n");

    //Set device first Attribute
    VPP_DISPLAY_DEV_Attrs *pDisplayAttrsToSet = pDevArray->pDevAttrs;
    VPP_DISPLAY_DEV_SetAttrs(deviceId, pDisplayAttrsToSet);
    printf("VPP_DISPLAY_DEV_SetAttrs Done \n");

    // Get device Attributes
    VPP_DISPLAY_DEV_Attrs *pDisplayAttrs = (VPP_DISPLAY_DEV_Attrs *)malloc(sizeof(VPP_DISPLAY_DEV_Attrs) * pDevArray->DevAttrsCount);
    memset(pDisplayAttrs, 0, sizeof(VPP_DISPLAY_DEV_Attrs)* pDevArray->DevAttrsCount);
    VPP_DISPLAY_DEV_GetAttrs(deviceId, pDisplayAttrs);
    free(pDisplayAttrs);
    printf("VPP_DISPLAY_DEV_GetAttrs Done \n");

    // Create Videolayer
    int32_t videoLayerId = 1;
    assert(VPP_DISPLAY_VIDEOLAYER_Create(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Create Done \n");

    //Set VideoLayer Attributes
    VPP_DISPLAY_VIDEOLAYER_Attrs *pAttrs = (VPP_DISPLAY_VIDEOLAYER_Attrs *)malloc(sizeof(VPP_DISPLAY_VIDEOLAYER_Attrs));
    memset(pAttrs, 0, sizeof(VPP_DISPLAY_VIDEOLAYER_Attrs));
    pAttrs->DisplayRect.X = 0;
    pAttrs->DisplayRect.Y = 0;
    pAttrs->DisplayRect.Width = pDisplayAttrsToSet->HDisplay - pAttrs->DisplayRect.X;
    pAttrs->DisplayRect.Height = pDisplayAttrsToSet->VDisplay - pAttrs->DisplayRect.Y;
    pAttrs->FrameBufferSize.Width = 3840;
    pAttrs->FrameBufferSize.Height = 2160;
    pAttrs->FrameRate = 30;
    assert(VPP_DISPLAY_VIDEOLAYER_SetAttrs(videoLayerId, pAttrs) == VPP_STATUS_SUCCESS);
    free(pAttrs);
    printf("VPP_DISPLAY_VIDEOLAYER_SetAttrs Done \n");

    assert(VPP_DISPLAY_VIDEOLAYER_BindDev(videoLayerId, deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_BindDev Done \n");

    int32_t streamOutRectX[16] = {0, 960, 1920, 2880, 0, 960, 1920, 2880, 0, 960, 1920, 2880, 0, 960, 1920, 2880};
    int32_t streamOutRectY[16] = {0, 0, 0, 0, 540, 540, 540, 540, 1080, 1080, 1080, 1080, 1620, 1620, 1620, 1620};
    for (int32_t i = 0; i < 16; ++i) {
        //Create Stream
        assert(VPP_DISPLAY_STREAM_Create(videoLayerId, i) == VPP_STATUS_SUCCESS);
        printf("VPP_DISPLAY_STREAM_Create Done \n");
        //Set Stream attrs
        VPP_DISPLAY_STREAM_Attrs *pStreamAttrs = (VPP_DISPLAY_STREAM_Attrs *)malloc(sizeof(VPP_DISPLAY_STREAM_Attrs));
        memset(pStreamAttrs, 0, sizeof(VPP_DISPLAY_STREAM_Attrs));
        pStreamAttrs->StreamOutRect.X = streamOutRectX[i];
        pStreamAttrs->StreamOutRect.Y = streamOutRectY[i];
        pStreamAttrs->StreamOutRect.Width = 960;
        pStreamAttrs->StreamOutRect.Height = 540;
        assert(VPP_DISPLAY_STREAM_SetAttrs(videoLayerId, i, pStreamAttrs) == VPP_STATUS_SUCCESS);
        free(pStreamAttrs);
        printf("VPP_DISPLAY_STREAM_SetAttrs Done \n");
        //Set Framerate
        assert(VPP_DISPLAY_STREAM_SetFrameRate(videoLayerId, i, 30) == VPP_STATUS_SUCCESS);
        printf("VPP_DISPLAY_STREAM_SetFrameRate Done \n");
    }

    printf("VPP_DISPLAY_STREAM_SetFrameRate Done \n");
    assert(VPP_DISPLAY_VIDEOLAYER_Start(videoLayerId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_VIDEOLAYER_Start Done \n");
    assert(VPP_DISPLAY_DEV_Start(deviceId) == VPP_STATUS_SUCCESS);
    printf("VPP_DISPLAY_DEV_Start Done \n");

    auto getSurface = [&](int32_t id, int32_t videoLayerId, VPP_StreamIdentifier videoLayerIdentifier) {
        ov::intel_gpu::ocl::VAContext* ptr_context = nullptr;
        ov::CompiledModel* compiled_model = nullptr;
        std::thread::id thread_id = std::this_thread::get_id();
        usleep(1'000'000);
        int i = 0;
        int frame_counter = 0;
        int skip_frames = 5;
        bool isFirstRun = true;
        size_t origin_height = 1088;
        size_t origin_width = 1920;
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
            if (frame_counter % skip_frames == 0 && id < 8){
                if (!compiled_model) {
                    VADisplay disp = vppSurfExport.VADisplay;
                        if (!ptr_context) {
                            ptr_context = new ov::intel_gpu::ocl::VAContext(core, disp);
                            compiled_model =  new ov::CompiledModel(core.compile_model(det_model, *ptr_context));
                        }
                    }
                auto input0 = det_model->get_parameters().at(0);
                auto input1 = det_model->get_parameters().at(1);
                auto shape = input0->get_shape();
                auto height = shape[1];
                auto width = shape[2];
                VASurfaceID va_surface = vppSurfExport.VASurfaceId;
                auto nv12_blob = ptr_context->create_tensor_nv12(height, width, va_surface);
                auto infer_requests_det = compiled_model->create_infer_request();
                infer_requests_det.set_tensor(input0->get_friendly_name(), nv12_blob.first);
                infer_requests_det.set_tensor(input1->get_friendly_name(), nv12_blob.second);
                infer_requests_det.start_async();
                infer_requests_det.wait();
                
                //Retrieve inference results
                auto output_tensor_det = infer_requests_det.get_output_tensor(0);
                auto result_det = postprocess(output_tensor_det, scale_x, scale_y);
                // remove last osd area
                
                if (!isFirstRun) {
                    for(int i : thread_deques[thread_id]) {
                        sts = VPP_OSD_DetachFromStream(i, videoLayerIdentifier);
                        assert(sts == VPP_STATUS_SUCCESS);
                        sts = VPP_OSD_DestroyArea(i);
                        assert(sts == VPP_STATUS_SUCCESS);
                    }
                    // remove id in thread_deques
                    thread_deques[thread_id].clear();
                }
                auto boxes = result_det.first;
                auto indices = result_det.second;
                for (size_t i = 0; i < indices.size(); i++) {
                    int index = indices[i];
                    cv::Rect box = boxes[index];
                    int left = box.x;
                    int top = box.y;
                    int width = box.width;
                    int height = box.height;
                    int centerX = floor(left + width / 2.0);
                    int centerY = floor(top + height / 2.0);
                    float scale_width = 960.0 / origin_width;
                    float scale_height = 540.0 / origin_height;
                    int new_width = static_cast<int>(width * scale_width);
                    int new_height = static_cast<int>(height * scale_height);
                    int new_centerX = static_cast<int>(centerX * scale_width);
                    int new_centerY = static_cast<int>(centerY * scale_height);

                    if (new_height <= 1 || new_width <= 1 || (new_centerX-new_width/2)<0 || (new_centerX+new_width/2)>=960 || (new_centerY-new_height/2)<0 || (new_centerY+new_height/2)>=540 ) {
                        continue;
                    };
                    VPP_OSD_AreaAttrs attrs;
                    attrs.Type = VPP_OSD_AREATYPE::VPP_OSD_AREATYPE_RECTANGLE;
                    attrs.RectAttrs.ForegroundColor.R = 0;
                    attrs.RectAttrs.ForegroundColor.G = 255;
                    attrs.RectAttrs.ForegroundColor.B = 0;
                    attrs.RectAttrs.Fill = false;
                    attrs.RectAttrs.LineWeight = 3;
                    attrs.Size.Width = new_width;
                    attrs.Size.Height = new_height;
                    VPP_OSD_AttachAttr attach_attrs;
                    attach_attrs.RectAttrs.Center.X = new_centerX;
                    attach_attrs.RectAttrs.Center.Y = new_centerY;
                    attach_attrs.RectAttrs.AlphaValue = 1;
                    VPP_STATUS sts;
                    int video_route = id;
                    int cal_id = current_ids[video_route] % 1000 + 1000 * video_route;
                    current_ids[video_route]++;
                    int current_osd_id = cal_id;
                    sts = VPP_OSD_CreateArea(current_osd_id, &attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    sts = VPP_OSD_AttachToStream(current_osd_id, videoLayerIdentifier, &attach_attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    thread_deques[thread_id].push_back(current_osd_id);  
                }
                isFirstRun = false;
            }
            assert(VPP_DISPLAY_STREAM_SendFrame(videoLayerId, id, hdl, 1000) == VPP_STATUS_SUCCESS);
            assert(VPP_DECODE_STREAM_ReleaseFrame(id, hdl) == VPP_STATUS_SUCCESS);
        }
    };
    std::vector<std::thread> threads;
    for (int i = 0; i < 16; i++) {
        VPP_StreamIdentifier videoLayerIdentifier;
        videoLayerIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
        videoLayerIdentifier.DeviceId = videoLayerId;
        videoLayerIdentifier.StreamId = i;
        threads.push_back(std::thread(getSurface, i, videoLayerId, videoLayerIdentifier));
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
    assert(VPP_DISPLAY_VIDEOLAYER_Stop(videoLayerId) == VPP_STATUS_SUCCESS);
    assert(VPP_DISPLAY_DEV_Stop(deviceId) == VPP_STATUS_SUCCESS);
    assert(VPP_DISPLAY_VIDEOLAYER_UnbindDev(videoLayerId, deviceId) == VPP_STATUS_SUCCESS);
    
    for (int32_t id = 0; id < 16; ++id) {
        assert(VPP_DISPLAY_STREAM_Destroy(videoLayerId, id) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Stop(id) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Destroy(id) == VPP_STATUS_SUCCESS);
    }
    assert(VPP_DISPLAY_VIDEOLAYER_Destroy(videoLayerId) == VPP_STATUS_SUCCESS);
    assert(VPP_DISPLAY_DEV_Destroy(deviceId) == VPP_STATUS_SUCCESS);
    VPP_DISPLAY_DEV_ReleaseList(pDevArray, deviceCount);
    fclose(fp);
    VPP_DeInit();
}
