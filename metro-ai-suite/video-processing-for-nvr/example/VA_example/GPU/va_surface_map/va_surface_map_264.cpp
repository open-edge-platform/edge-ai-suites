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
#include <chrono>
#include <vector>
#include "opencv2/opencv.hpp"
#include "openvino/openvino.hpp"

using namespace cv;
using namespace dnn;
using namespace ov::preprocess;

std::map<std::thread::id, std::deque<int>> thread_deques;
std::vector<int> current_ids(16, 0);

std::string det_model_path="/home/vpp/models/yolov8_int8/yolov8n.xml";
std::string det_model_name="yolov8";

std::shared_ptr<ov::Model> loadAndPreprocessModel(std::string model_path) {
    ov::Core core;
    std::shared_ptr<ov::Model> model = core.read_model(model_path);
    model->reshape({{1, 3, 640, 640}});
    std::string input_tensor_name = model->input().get_any_name();
    PrePostProcessor ppp = PrePostProcessor(model);
    InputInfo& input_info = ppp.input(input_tensor_name);
    input_info.tensor()
    .set_element_type(ov::element::u8)
    .set_color_format(ColorFormat::NV12_TWO_PLANES, {"Y", "UV"})
    .set_spatial_dynamic_shape();
    input_info.preprocess()
    .convert_element_type(ov::element::f32)
    .convert_color(ColorFormat::RGB)
    .resize(ResizeAlgorithm::RESIZE_LINEAR, 640, 640)
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
    float score_threshold = 0.4;
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
    ov::CompiledModel compiled_model_det = core.compile_model(det_model, "GPU", ov::hint::performance_mode(ov::hint::PerformanceMode::THROUGHPUT));
    std::vector<ov::InferRequest> infer_requests_det(16);
    for(int i = 0; i < 16; i++) {
        infer_requests_det[i] = compiled_model_det.create_infer_request();
    }

    VPP_Init();
    for (int32_t id = 0; id < 16; ++id) {
        VPP_DECODE_STREAM_Attr attr;
        attr.CodecStandard = VPP_CODEC_STANDARD_H264;
        attr.OutputFormat = VPP_PIXEL_FORMAT_NV12;
        attr.InputMode = VPP_DECODE_INPUT_MODE_STREAM;
        attr.OutputHeight = 640;
        attr.OutputWidth = 640;
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
        std::thread::id thread_id = std::this_thread::get_id();
        usleep(1'000);
        int i = 0;
        int frame_counter = 0;
        int skip_frames = 4;
        bool isFirstRun = true;
        while (1) {
            VPP_SURFACE_HDL hdl;
            VPP_STATUS sts = VPP_DECODE_STREAM_GetFrame(id, &hdl, 5000);
            if (sts != VPP_STATUS_SUCCESS) {
                break;
            }
            VPP_SURFACE vppSurfData;
            //sts = VPP_SYS_MapSurface(hdl, &vppSurfData);
            
            frame_counter++;
            
            if (frame_counter % skip_frames == 0 && id < 8){
		sts = VPP_SYS_MapSurface(hdl, &vppSurfData);
                size_t origin_height = vppSurfData.Height;
                size_t origin_width = vppSurfData.Width;
                size_t batch = 1;
                float scale_x = origin_width / 640.0;
                float scale_y = origin_height / 640.0;
                ov::Tensor input_det_tensor_y{ov::element::u8, {batch, origin_height, origin_width, 1}, vppSurfData.Y};
                ov::Tensor input_det_tensor_uv{ov::element::u8, {batch, origin_height/2, origin_width/2, 2}, vppSurfData.UV};
                std::vector<ov::Tensor> input_det_tensor_ys = {input_det_tensor_y};
                std::vector<ov::Tensor> input_det_tensor_uvs = {input_det_tensor_uv};
                infer_requests_det[id].set_input_tensors(0, input_det_tensor_ys);
                infer_requests_det[id].set_input_tensors(1, input_det_tensor_uvs);
                infer_requests_det[id].infer();
                
                //Retrieve inference results
                auto output_tensor_det = infer_requests_det[id].get_output_tensor(0);
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
                    attrs.RectAttrs.LineWeight = 9;
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
            sts = VPP_SYS_UnmapSurface(hdl, &vppSurfData);
	    }
            //sts = VPP_SYS_UnmapSurface(hdl, &vppSurfData);
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

    auto dec = [](int32_t id) {
        FILE* fp = fopen("/opt/video/car_1080p.h264", "rb");
        // FILE* fp = fopen("/opt/video/long_time_1080p.h264", "rb");

        const uint64_t size = 1 * 1024 * 1024;
        void* addr = malloc(size);
        while (true) {
            uint64_t sizeTemp = fread(addr, 1, size, fp);
            VPP_DECODE_STREAM_InputBuffer buffer;
            buffer.pAddr = (uint8_t*)addr;
            buffer.Length = sizeTemp;
            buffer.BasePts = 0;
            buffer.FlagEOStream = false;

            if(sizeTemp < size) {
                // buffer.FlagEOStream = true;
            }

            VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);

            if(sizeTemp < size) {
                fseek(fp, 0, SEEK_SET);
            }
        }
        free(addr);
        fclose(fp);
    };
    // Start new thread for feeding input
    std::vector<std::thread> arr_thread;

    for (int32_t id = 0; id < 16; ++id) {
        arr_thread.push_back(std::thread(dec, id));
    }
    // Wait for all feeder threads to finish
    for (int32_t id = 0; id < 16; ++id) {
        arr_thread[id].join();
    }

    usleep(1000);
    for (auto& th : threads) {
        th.join();
    }
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
    VPP_DeInit();
}
