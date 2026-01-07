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
#include <fstream>
#include "opencv2/opencv.hpp"
#include "openvino/openvino.hpp"

#include <iostream>
#include <chrono>
#include <iomanip>
#include <ctime>

using namespace cv;
using namespace dnn;
using namespace ov::preprocess;

const size_t NUM_STREAMS = 32;
const size_t NUM_STREAMS_INFER = 32;

const std::string DEV_DET= "GPU";
const std::string DEV_CLS= "NPU";

std::map<std::thread::id, std::deque<int>> thread_deques;
std::vector<int> current_ids(NUM_STREAMS, 0);

std::shared_ptr<ov::Model> loadAndPreprocessModel(std::string model_path) {
    ov::Core core;
    std::shared_ptr<ov::Model> model = core.read_model(model_path);
    model->reshape({{1, 640, 640, 3}});
    std::string input_tensor_name = model->input().get_any_name();
    PrePostProcessor ppp = PrePostProcessor(model);
    InputInfo& input_info = ppp.input(input_tensor_name);
    input_info.tensor()
    .set_shape({1, 640, 640, 3})
    .set_layout("NHWC")
    .set_color_format(ov::preprocess::ColorFormat::BGR)
    .set_element_type(ov::element::u8);
    // input_info.preprocess()
    // .convert_element_type(ov::element::f32)
    // .scale({255.0f, 255.0f, 255.0f});
    input_info.model().set_layout("NHWC");
    model = ppp.build();
    return model;
}

std::shared_ptr<ov::Model> loadAndPreprocessClassificationModel(const std::string& model_path) {
    ov::Core core;
    auto model = core.read_model(model_path);
    ov::preprocess::PrePostProcessor ppp(model);
    ppp.input().tensor()
        .set_element_type(ov::element::u8)
        .set_layout("NHWC");
    ppp.input().preprocess()
        .convert_element_type(ov::element::f32);
    ppp.output().tensor().set_element_type(ov::element::f32);   
    model = ppp.build();
    return model;
}

ov::CompiledModel compileClassificationModelForNPU(ov::Core& core, std::shared_ptr<ov::Model> model) {
    ov::CompiledModel compiled_model = core.compile_model(model, DEV_CLS, ov::hint::inference_precision(ov::element::i8));
    return compiled_model;
}

std::vector<std::string> load_imagenet_labels(const std::string& filename) {
    std::vector<std::string> labels;
    std::ifstream infile(filename);
    if (!infile) {
        throw std::runtime_error("Cannot open labels file: " + filename);
    }
    std::string line;
    labels.push_back("");
    while (std::getline(infile, line)) {
        // each line is e.g. "n01440764 tench, Tinca tinca"
        // we want the first name after the synset ID, up to the first comma
        std::istringstream iss(line);
        std::string synset, rest;
        iss >> synset;               // discard the "n01440764"
        std::getline(iss, rest);     // rest == " tench, Tinca tinca"
        // trim leading space
        if (!rest.empty() && rest[0] == ' ') rest.erase(0,1);
        // cut at first comma
        auto pos = rest.find(',');
        if (pos != std::string::npos)
            rest = rest.substr(0, pos);  // "tench"
        labels.push_back(rest);
    }
    return labels;
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

void printWithTimestamp(const std::string& message) {
    return;
    // Get current time
    auto now = std::chrono::system_clock::now();
    auto now_time_t = std::chrono::system_clock::to_time_t(now);
    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                      now.time_since_epoch()) % 1000;

    // Convert to local time
    std::tm* local_time = std::localtime(&now_time_t);

    // Print formatted time with milliseconds
    std::cout << "[" << std::put_time(local_time, "%Y-%m-%d %H:%M:%S")
              << "." << std::setfill('0') << std::setw(3) << now_ms.count()
              << "] " << message << std::endl;
}

int main(int argc, char* argv[])
{
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <det_model_path> <cls_model_path>" << std::endl;
        return 1;
    }
    std::string det_model_path = argv[1];
    std::string cls_model_path = argv[2];
    std::shared_ptr<ov::Model> det_model = loadAndPreprocessModel(det_model_path);
    std::shared_ptr<ov::Model> cls_model = loadAndPreprocessClassificationModel(cls_model_path);
    
    ov::Core core;
    auto cls_labels = load_imagenet_labels("/opt/intel/vppsdk/example/VA_example/imagenet_2012.txt");
    // ov::CompiledModel compiled_model_det = core.compile_model(det_model, DEV_DET);
    std::vector<ov::CompiledModel> vec_compiled_model_det(NUM_STREAMS_INFER);
    std::vector<ov::InferRequest> infer_requests_det(NUM_STREAMS_INFER);

    for(int i = 0; i < 4; i++) {
        vec_compiled_model_det[i] = core.compile_model(det_model, DEV_DET);
    }
    for(int i = 0; i < NUM_STREAMS_INFER; i++) {
        infer_requests_det[i] = vec_compiled_model_det[i * 4 / NUM_STREAMS_INFER].create_infer_request();
    }

    VPP_Init();
    for (int32_t id = 0; id < NUM_STREAMS; ++id) {
        VPP_DECODE_STREAM_Attr attr;
        attr.CodecStandard = VPP_CODEC_STANDARD_H265;
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

    int32_t streamOutRectX[NUM_STREAMS];
    int32_t streamOutRectY[NUM_STREAMS];
    const size_t widthStream = 960/2;
    const size_t heightStream = 540/2;
    for (int32_t i = 0; i < NUM_STREAMS; ++i) {
        streamOutRectX[i] = i * widthStream % 3840;
        streamOutRectY[i] = i * widthStream / 3840 * heightStream;
    }
    for (int32_t i = 0; i < NUM_STREAMS; ++i) {
        //Create Stream
        assert(VPP_DISPLAY_STREAM_Create(videoLayerId, i) == VPP_STATUS_SUCCESS);
        printf("VPP_DISPLAY_STREAM_Create Done \n");
        //Set Stream attrs
        VPP_DISPLAY_STREAM_Attrs *pStreamAttrs = (VPP_DISPLAY_STREAM_Attrs *)malloc(sizeof(VPP_DISPLAY_STREAM_Attrs));
        memset(pStreamAttrs, 0, sizeof(VPP_DISPLAY_STREAM_Attrs));
        pStreamAttrs->StreamOutRect.X = streamOutRectX[i];
        pStreamAttrs->StreamOutRect.Y = streamOutRectY[i];
        pStreamAttrs->StreamOutRect.Width = widthStream;
        pStreamAttrs->StreamOutRect.Height = heightStream;
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
        ov::CompiledModel compiled_model_cls;
        ov::InferRequest infer_request_cls;
        if (id < NUM_STREAMS_INFER) {
            compiled_model_cls = compileClassificationModelForNPU(core, cls_model);
            infer_request_cls = compiled_model_cls.create_infer_request();
        }
        usleep(1'000'000);
        int i = 0;
        int frame_counter = 0;
        int skip_frames = 6;
        bool isFirstRun = true;
        while (1) {
            VPP_SURFACE_HDL hdl;
            if (id == 0) {
                printWithTimestamp("Waiting for frame...");
            }
            VPP_STATUS sts = VPP_DECODE_STREAM_GetFrame(id, &hdl, 5000);
            if (sts != VPP_STATUS_SUCCESS) {
                continue;
            }
            VPP_SURFACE vppSurfData;
            if (id == 0) {
                printWithTimestamp("Got frame");
            }
            frame_counter++;
            
            if (frame_counter % skip_frames == 0 && id < NUM_STREAMS_INFER){
                sts = VPP_SYS_MapSurface(hdl, &vppSurfData);
                
                if (id == 0) {
                    printWithTimestamp("Map frame done");
                }
                size_t origin_height = vppSurfData.Pitches[1];
                size_t origin_width = vppSurfData.Pitches[0];
                // printf("height is %d\n", vppSurfData.Pitches[1]);
                // printf("width is %d\n", vppSurfData.Pitches[0]);
                size_t batch = 1;
                float scale_x = origin_width / 640.0;
                float scale_y = origin_height / 640.0;
                                
                // Convert NV12 to RGB for classification
                // cv::Mat y_plane(origin_height, origin_width, CV_8UC1, vppSurfData.Y);
                // cv::Mat uv_plane(origin_height / 2, origin_width / 2, CV_8UC2, vppSurfData.UV);
                cv::Mat nv12(origin_height + origin_height / 2, origin_width, CV_8UC1, vppSurfData.Y);
                //std::memcpy(nv12.data, y_plane.data, static_cast<size_t>(origin_height) * origin_width);
                //std::memcpy(nv12.data + origin_height * origin_width, uv_plane.data, static_cast<size_t>(origin_height / 2) * (origin_width / 2) * 2);
                cv::Mat input_image;
                cv::cvtColor(nv12, input_image, cv::COLOR_YUV2BGR_NV12);

                #if 0
                // Detection on GPU
                ov::Tensor input_det_tensor_y{ov::element::u8, {batch, origin_height, origin_width, 1}, vppSurfData.Y};
                ov::Tensor input_det_tensor_uv{ov::element::u8, {batch, origin_height/2, origin_width/2, 2}, vppSurfData.UV};
                std::vector<ov::Tensor> input_det_tensor_ys = {input_det_tensor_y};
                std::vector<ov::Tensor> input_det_tensor_uvs = {input_det_tensor_uv};
                infer_requests_det[id].set_input_tensors(0, input_det_tensor_ys);
                infer_requests_det[id].set_input_tensors(1, input_det_tensor_uvs);
                #else
                // Detection on GPU
                ov::Tensor input_det_tensor{ov::element::u8, {batch, origin_height, origin_width, 3}, input_image.data};
                std::vector<ov::Tensor> input_det_tensors = {input_det_tensor};
                infer_requests_det[id].set_input_tensors(0, input_det_tensors);            
                #endif
                
                if (id == 0) {
                    printWithTimestamp("Detection ...");
                }
                infer_requests_det[id].infer();
                if (id == 0) {
                    printWithTimestamp("Detection done");
                }
                // Retrieve detection results
                auto output_tensor_det = infer_requests_det[id].get_output_tensor(0);
                auto result_det = postprocess(output_tensor_det, scale_x, scale_y);
                
                if (id == 0) {
                    printWithTimestamp("Postprocess done");
                }
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
                if (id == 0) {
                    printWithTimestamp("Remove OSD done");
                }
                
                auto boxes = result_det.first;
                auto indices = result_det.second;

                
                
                for (size_t i = 0; i < indices.size() && i < 1; i++) {
                    int index = indices[i];
                    cv::Rect box = boxes[index];
                    int left = box.x;
                    int top = box.y;
                    int width = box.width;
                    int height = box.height;
                    
                    // Draw detection bounding box
                    int centerX = floor(left + width / 2.0);
                    int centerY = floor(top + height / 2.0);
                    float scale_width = (float)widthStream / vppSurfData.Width;
                    float scale_height = (float)heightStream / vppSurfData.Height;
                    int new_width = static_cast<int>(width * scale_width);
                    int new_height = static_cast<int>(height * scale_height);
                    int new_centerX = static_cast<int>(centerX * scale_width);
                    int new_centerY = static_cast<int>(centerY * scale_height);
                    
                    if (new_height <= 1 || new_width <= 1 || (new_centerX-new_width/2)<0 || (new_centerX+new_width/2)>=widthStream || (new_centerY-new_height/2)<0 || (new_centerY+new_height/2)>=heightStream ) {
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
                    
                    int video_route = id;
                    int cal_id = current_ids[video_route] % 1000 + 1000 * video_route;
                    current_ids[video_route]++;
                    int current_osd_id = cal_id;
                    
                    sts = VPP_OSD_CreateArea(current_osd_id, &attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    sts = VPP_OSD_AttachToStream(current_osd_id, videoLayerIdentifier, &attach_attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    thread_deques[thread_id].push_back(current_osd_id);
                    
                    if (id == 0) {
                        printWithTimestamp("Attach roi done");
                    }
                    // continue;
                    // Classification on NPU
                    int roi_x = std::max(0, left);
                    int roi_y = std::max(0, top);
                    int roi_width = std::min(width, input_image.cols - roi_x);
                    int roi_height = std::min(height, input_image.rows - roi_y);
                    
                    cv::Mat roi = input_image(cv::Rect(roi_x, roi_y, roi_width, roi_height));
                    cv::Mat resized_roi;
                    cv::resize(roi, resized_roi, cv::Size(224, 224));
                    // resized_roi.convertTo(resized_roi, CV_8UC3);
                    
                    ov::Tensor input_tensor = ov::Tensor(ov::element::u8, {1, 224, 224, 3}, resized_roi.data);
                    
                    std::string input_tensor_name = compiled_model_cls.input().get_any_name();
                    infer_request_cls.set_tensor(input_tensor_name, input_tensor);
                    
                    if (id == 0) {
                        printWithTimestamp("cls preprocess done");
                    }
                    infer_request_cls.infer();
                    
                    if (id == 0) {
                        printWithTimestamp("cls inference done");
                    }
                    auto output_tensor_cls = infer_request_cls.get_output_tensor(0);
                    float* cls_data = output_tensor_cls.data<float>();
                    size_t num_classes = output_tensor_cls.get_size();
                    printf("cls_data is %e\n", cls_data[1]);
                    int cls_id = static_cast<int>(std::max_element(cls_data, cls_data + num_classes) - cls_data);
                    float confidence = cls_data[cls_id];
                    std::ostringstream oss;
                    oss << cls_labels[cls_id] << ": " << confidence;
                    std::string cls_label = oss.str();
                    std::cout << "Inference completed. Class ID: " << cls_id << ", Name: " << cls_labels[cls_id] << ", Confidence: " << confidence << std::endl;

                    // Draw classification label
                    int label_width = (cls_label.length() * 12 + 1) & ~1;
                    int label_height = 30 % 2 == 0 ? 30 : 30 + 1;
                    cv::Mat label_image(label_height, label_width, CV_8UC4, cv::Scalar(0, 0, 0, 0));
                    cv::putText(label_image, cls_label, cv::Point(10, 20), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0, 255, 0, 255), 1);
                    
                    static std::mutex buffer_mutex;
                    static std::map<int, std::vector<uint8_t>> planar_buffers;
                    
                    std::vector<cv::Mat> channels(3);
                    cv::split(label_image, channels);
                    std::vector<uint8_t> planar_data;
                    for (int i = 0; i < 3; i++) {
                        planar_data.insert(planar_data.end(), channels[i].datastart, channels[i].dataend);
                    }
                    
                    std::unique_lock<std::mutex> lock(buffer_mutex);
                    int label_osd_id = (current_ids[id]++ % 900) + 1000 * (id + 1) + 10000;
                    planar_buffers[label_osd_id] = std::move(planar_data);
                    
                    VPP_OSD_AreaAttrs label_attrs = {};
                    label_attrs.Type = VPP_OSD_AREATYPE_BITMAP;
                    label_attrs.BitmapAttrs.Format = VPP_PIXEL_FORMAT_RGBP;
                    label_attrs.BitmapAttrs.BufferAddr = planar_buffers[label_osd_id].data();
                    label_attrs.Size.Width = label_image.cols;
                    label_attrs.Size.Height = label_image.rows;
                    
                    if (label_attrs.Size.Width % 2 != 0 || label_attrs.Size.Height % 2 != 0) {
                        std::cerr << "Invalid OSD bitmap dimensions: " << label_attrs.Size.Width << "x" << label_attrs.Size.Height << std::endl;
                        continue;
                    }
                    
                    int max_x = widthStream - label_attrs.Size.Width / 2;
                    int max_y = heightStream - label_attrs.Size.Height / 2;
                    new_centerX = std::clamp(new_centerX, label_attrs.Size.Width / 2, max_x);
                    new_centerY = std::clamp(new_centerY - 20, label_attrs.Size.Height / 2, max_y);
                    
                    VPP_OSD_AttachAttr label_attach_attrs;
                    label_attach_attrs.BitmapAttrs.Center.X = new_centerX;
                    label_attach_attrs.BitmapAttrs.Center.Y = new_centerY;
                    label_attach_attrs.BitmapAttrs.AlphaValue = 1;
                    
                    sts = VPP_OSD_CreateArea(label_osd_id, &label_attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    sts = VPP_OSD_AttachToStream(label_osd_id, videoLayerIdentifier, &label_attach_attrs);
                    assert(sts == VPP_STATUS_SUCCESS);
                    thread_deques[thread_id].push_back(label_osd_id);
                    
                    if (id == 0) {
                        printWithTimestamp("attach cls done");
                    }
                }
                isFirstRun = false;
                sts = VPP_SYS_UnmapSurface(hdl, &vppSurfData);
            }
            assert(VPP_DISPLAY_STREAM_SendFrame(videoLayerId, id, hdl, 1000) == VPP_STATUS_SUCCESS);
            assert(VPP_DECODE_STREAM_ReleaseFrame(id, hdl) == VPP_STATUS_SUCCESS);
        }
    };
    std::vector<std::thread> threads;
    for (int i = 0; i < NUM_STREAMS; i++) {
        VPP_StreamIdentifier videoLayerIdentifier;
        videoLayerIdentifier.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
        videoLayerIdentifier.DeviceId = videoLayerId;
        videoLayerIdentifier.StreamId = i;
        threads.push_back(std::thread(getSurface, i, videoLayerId, videoLayerIdentifier));
    }
    FILE* fp = fopen("/opt/video/car_1080p.h265", "rb");

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
            //buffer.FlagEOStream = true;
        }

    	std::thread* arrThread[NUM_STREAMS];
        for (int32_t id = 0; id < NUM_STREAMS; ++id) {
            auto feed = [=]() {VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);};
            arrThread[id] = new std::thread(feed);
        }
        for (int32_t id = 0; id < NUM_STREAMS; ++id) {
            arrThread[id]->join();
            delete(arrThread[id]);
        }


        //for (int32_t id = 0; id < NUM_STREAMS; ++id) {
        //VPP_DECODE_STREAM_FeedInput(id, &buffer, -1);
        //}
        if(sizeTemp < size) {
            //break;
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
    for (int32_t id = 0; id < NUM_STREAMS; ++id) {
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
