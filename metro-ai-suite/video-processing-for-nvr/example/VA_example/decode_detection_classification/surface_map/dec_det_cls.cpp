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

const size_t NUM_STREAMS = 16;
const size_t NUM_STREAMS_INFER = 16;

const std::string DEV_DET= "GPU";
const std::string DEV_CLS= "GPU";

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
    ov::CompiledModel compiled_model = core.compile_model(model, DEV_CLS);
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

    for(int i = 0; i < 4&&i<NUM_STREAMS_INFER; i++) {
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
        attr.OutputHeight = 0;
        attr.OutputWidth = 0;
        attr.OutputBufQueueLength = 0;
        attr.RingBufferSize = 0;
        assert(VPP_DECODE_STREAM_Create(id, &attr) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_SetOutputMode(id, VPP_DECODE_OUTPUT_MODE_PLAYBACK) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Start(id) == VPP_STATUS_SUCCESS);
    }
    
    auto getSurface = [&](int32_t id) {
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
        int skip_frames = 3;
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
                size_t origin_height = vppSurfData.Height;
                size_t origin_width = vppSurfData.Pitches[0];
                // printf("height is %d\n", vppSurfData.Height);
                // printf("width is %d\n", vppSurfData.Pitches[0]);
                size_t batch = 1;
                float scale_x = origin_width / 640.0;
                float scale_y = origin_height / 640.0;
                                
                // Convert NV12 to RGB for classification
                cv::Mat nv12(origin_height + origin_height / 2, origin_width, CV_8UC1, vppSurfData.Y);
                cv::Mat rgb_image;
                cv::Mat input_image;
                cv::cvtColor(nv12, rgb_image, cv::COLOR_YUV2BGR_NV12);
                cv::resize(rgb_image, input_image, cv::Size(640, 640));

                // Detection on GPU
                ov::Tensor input_det_tensor{ov::element::u8, {batch, 640, 640, 3}, input_image.data};
                std::vector<ov::Tensor> input_det_tensors = {input_det_tensor};
                infer_requests_det[id].set_input_tensors(0, input_det_tensors);            
                
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
                
                auto boxes = result_det.first;
                auto indices = result_det.second;
                
                for (size_t i = 0; i < indices.size() && i < 1; i++) {
                    int index = indices[i];
                    cv::Rect box = boxes[index];
                    int left = box.x;
                    int top = box.y;
                    int width = box.width;
                    int height = box.height;

                    // continue;
                    // Classification on NPU
                    int roi_x = std::max(0, left);
                    int roi_y = std::max(0, top);
                    int roi_width = std::min(width, rgb_image.cols - roi_x);
                    int roi_height = std::min(height, rgb_image.rows - roi_y);

                    cv::Mat roi = rgb_image(cv::Rect(roi_x, roi_y, roi_width, roi_height));
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
                    // printf("cls_data is %e\n", cls_data[1]);
                    int cls_id = static_cast<int>(std::max_element(cls_data, cls_data + num_classes) - cls_data);
                    float confidence = cls_data[cls_id];
                    std::ostringstream oss;
                    oss << cls_labels[cls_id] << ": " << confidence;
                    std::string cls_label = oss.str();
                    std::cout << "Inference completed. Class ID: " << cls_id << ", Name: " << cls_labels[cls_id] << ", Confidence: " << confidence << std::endl;
                }
                isFirstRun = false;
                sts = VPP_SYS_UnmapSurface(hdl, &vppSurfData);
            }
            assert(VPP_DECODE_STREAM_ReleaseFrame(id, hdl) == VPP_STATUS_SUCCESS);
        }
    };
    std::vector<std::thread> threads;
    for (int i = 0; i < NUM_STREAMS; i++) {
        threads.push_back(std::thread(getSurface, i));
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
    for (int32_t id = 0; id < NUM_STREAMS; ++id) {
        assert(VPP_DECODE_STREAM_Stop(id) == VPP_STATUS_SUCCESS);
        assert(VPP_DECODE_STREAM_Destroy(id) == VPP_STATUS_SUCCESS);
    }
    fclose(fp);
    VPP_DeInit();
}
