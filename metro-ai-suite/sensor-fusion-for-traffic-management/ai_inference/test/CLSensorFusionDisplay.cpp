/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2024 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <cctype>
#include <cstdlib>
#include <string>
#include <sys/timeb.h>
#include <chrono>
#include <mutex>
#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>
#include <boost/property_tree/json_parser.hpp>

#include "utils/testUtils.hpp"
#include "utils/displayUtils.hpp"

#include "low_latency_client/grpcClient.hpp"
#include "utils/sys_metrics/cpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_monitor.h"
#include "modules/visualization/Plot.h"
#include "modules/visualization/FusionDisplay.h"
#include "math.h"
#include <cctype>

using namespace hce::ai::inference;

#define SHOWGPUMETRIC true

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
std::vector<double> g_latency;
std::vector<double> g_inference_latency;
std::vector<double> g_video_latency;
std::mutex g_mutex;

// system metrics
// GPUMetrics gpuMetrics;
CPUMetrics cpuMetrics;
std::atomic_bool stop_metrics;

// display controller
std::atomic_bool stop_display;

std::mutex g_window_mutex;
static const string WINDOWNAME = "Camera + Lidar Sensor Fusion";
std::vector<int> cpuMetricsArr;
std::vector<float> gpuMetricsArr;

std::mutex mtxFrames;
std::condition_variable cvFrames;
int readyFrames = 0;
int currentSyncFrame = 0;

/**
 * @brief parse input local file
 */
void parseInputs(const std::string data_path, std::vector<std::string> &inputs, std::string &mediaType)
{
    if (boost::filesystem::exists(data_path)) {
        if (mediaType == "image") {
            // use case:
            // traverse image folder as inputs

            if (!checkIsFolder(data_path)) {
                HVA_ERROR("path should be valid folder: %s", data_path.c_str());
                HVA_ASSERT(false);
            }

            getAllFiles(data_path + "/image_2", inputs, ".bin");
            std::sort(inputs.begin(), inputs.end());

            std::cout << "Load " << inputs.size() << " files from folder: " << data_path.c_str() << std::endl;
        }
        else if (mediaType == "multisensor") {
            // use case:
            // multi-sensor inputs, organized as [image_2, velodyne, calib]

            if (!checkIsFolder(data_path)) {
                HVA_ERROR("path should be valid folder: %s", data_path.c_str());
                HVA_ASSERT(false);
            }

            std::vector<std::string> bgrInputs;
            getAllFiles(data_path + "/image_2", bgrInputs, ".bin");
            std::vector<std::string> lidarInputs;
            getAllFiles(data_path + "/velodyne", lidarInputs, ".bin");
            std::vector<std::string> calibInputs;
            getAllFiles(data_path + "/calib", calibInputs, ".txt");

            if (bgrInputs.size() != lidarInputs.size() || bgrInputs.size() != calibInputs.size() || lidarInputs.size() != calibInputs.size()) {
                HVA_ERROR("each sensor input should have equal sizes, but got bgr: %d, lidar: %d, calib: %d", bgrInputs.size(), lidarInputs.size(),
                          calibInputs.size());
                HVA_ASSERT(false);
            }
            std::string path;
            // insert aligned sensor data by sequence
            for (int i = 0; i < lidarInputs.size(); i++) {
                path = parseAbsolutePath(bgrInputs[i]);
                inputs.push_back(path);
                path = parseAbsolutePath(lidarInputs[i]);
                inputs.push_back(path);
                path = parseAbsolutePath(calibInputs[i]);
                inputs.push_back(path);
            }
            std::cout << "Load " << inputs.size() << " files from folder: " << data_path.c_str() << std::endl;
        }
        else {
            std::cerr << "CLSensorFusionDisplay receive unknow media type: " << mediaType.c_str() << std::endl;
            HVA_ASSERT(false);
        }
    }
    else {
        std::cerr << "File not exists: " << data_path.c_str() << std::endl;
        HVA_ASSERT(false);
    }
}


/**
 * @brief processing workload, send requests to ai inference service and then parse the response body
 */
void workload(const std::string &host,
              const std::string &port,
              const std::string &json,
              const std::vector<std::string> &mediaVector,
              unsigned thread_id,
              MessageBuffer_t *pb,
              unsigned repeats,
              unsigned stream_num,
              bool warmup_flag,
              unsigned pipeline_repeats)
{
    GRPCClient client{host, std::to_string(std::stoi(port) + thread_id)};

    std::chrono::time_point<std::chrono::high_resolution_clock> request_sent, response_received, first_response_received;
    std::chrono::milliseconds timeUsed(0);
    std::chrono::milliseconds thisTime(0);
    std::size_t frameCnt(0);

    //
    // start to process
    //

    std::vector<std::string> repeatmediaVector;
    for (unsigned i = 0; i < repeats; ++i) {
        repeatmediaVector.insert(repeatmediaVector.end(), mediaVector.begin(), mediaVector.end());
    }

    std::vector<std::string> inputs;
    // repeat input media for `stream_num` times
    for (unsigned i = 0; i < stream_num; i++) {
        inputs.insert(inputs.end(), repeatmediaVector.begin(), repeatmediaVector.end());
    }
    std::string info = "[thread " + std::to_string(thread_id) + "] Input media size is: " + std::to_string(inputs.size());
    std::cout << info << std::endl;

    std::shared_ptr<hce_ai::ai_inference::Stub> stub = client.connect();
    size_t job_handle = 0;
    int firstResponseIndex = 0;
    float cpuUtilizationVal = 0.0;
    float gpuAllUtilizationVal = 0.0;
    for (unsigned i = 0; i < pipeline_repeats; ++i) {
        grpc::ClientContext context;
        std::shared_ptr<grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>> stream(stub->Run(&context));
        bool isFirst = true;

        if (warmup_flag && job_handle == 0) {
            // warm up pipelines before running to promote throughputs
            hce_ai::AI_Request request;
            request.set_target("load_pipeline");
            request.set_pipelineconfig(json);
            request.set_suggestedweight(0);
            request.set_streamnum(stream_num);

            // Client send requests on specific context
            std::cout << "sending request ====> load_pipeline" << std::endl;
            stream->Write(request);

            hce_ai::AI_Response reply;
            stream->Read(&reply);
            std::cout << "reply: " << reply.message() << ", reply_status: " << reply.status() << std::endl;
            /*
            reply: {
                "description": "Success",
                "request": "load_pipeline",
                "handle": "2147483648"
            }
            success: reply status == 0
            */
            if (reply.status() == 0) {
                boost::property_tree::ptree jsonMessage;
                std::stringstream ss(reply.message());
                boost::property_tree::read_json(ss, jsonMessage);
                job_handle = jsonMessage.get<size_t>("handle");
                std::cout << "pipeline has been loaded, job handle: " << job_handle << std::endl;
            }
        }

        request_sent = std::chrono::high_resolution_clock::now();
        {
            // Data for sending to server
            hce_ai::AI_Request request;
            request.set_target("run");
            request.set_suggestedweight(0);
            request.set_streamnum(stream_num);
            *request.mutable_mediauri() = {inputs.begin(), inputs.end()};
            if (job_handle > 0) {
                std::cout << "sending request ====> pipeline will run on specific jobhandle" << std::endl;
                request.set_jobhandle(job_handle);
            }
            else {
                std::cout << "sending request ====> run" << std::endl;
                request.set_pipelineconfig(json);
            }

            // Client send requests on specific context
            stream->Write(request);
        }


        // parse ret results
        std::thread reader([&]() {
            hce_ai::AI_Response reply;
            std::string reply_msg;
            int reply_status;

            while (stream->Read(&reply)) {
                std::string msg = reply.message();
                // response received
                response_received = std::chrono::high_resolution_clock::now();
                auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - request_sent).count();

                if (isFirst) {
                    std::lock_guard<std::mutex> lg(g_mutex);
                    std::cout << ", thread " << thread_id << ", latency: " << duration << "ms" << std::endl;
                    // g_latency.push_back(duration);
                    first_response_received = response_received;
                    isFirst = false;
                }

                reply_status = reply.status();
                std::cout << "frame index: " << frameCnt << ", reply_status: " << reply_status << std::endl;
                // std::cout << msg << std::endl;

                int getCPUUti = cpuMetrics.cpuUtilization();
                float getGPUUti = gpuBusyValue.load();

                if (thread_id == 0) {
                    cpuMetricsArr.push_back(getCPUUti);
                    gpuMetricsArr.push_back(getGPUUti);
                }

                cpuUtilizationVal += getCPUUti;
                gpuAllUtilizationVal += getGPUUti;

                int fpsCnt = frameCnt - firstResponseIndex;
                frameCnt += 1;
                auto timeElapsed = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - first_response_received).count();
                float curFPS = fpsCnt == 0 ? 0 : fpsCnt * 1000.0 / timeElapsed;
                if (std::isinf(curFPS) || std::isnan(curFPS)) {
                    curFPS = 0.0;
                }
                std::cout << "[thread " << thread_id << "], curFPS: " << curFPS << ", frames: " << frameCnt << std::endl;
                msg = to_string(curFPS).substr(0, 5) + msg;

                if (frameCnt % 100 == 0) {
                    std::string info = "[thread " + std::to_string(thread_id) + "] " + std::to_string(frameCnt) + " frames have been processed.";
                    std::cout << info << std::endl;
                }

                try {
                    // parse response message to MessageBuffer_t
                    unique_lock<mutex> lock(pb->mtx);

                    while (((pb->write_pos + 1) % MAX_MESSAGE_BUFFER_SIZE) == pb->read_pos) {
                        // buffer is full
                        // std::cout << "buffer is full now, producer is waiting
                        // ..." << std::endl;
                        (pb->not_full).wait(lock);
                    }
                    (pb->buffer)[pb->write_pos] = msg;
                    (pb->write_pos)++;

                    if (pb->write_pos == MAX_MESSAGE_BUFFER_SIZE)
                        pb->write_pos = 0;

                    (pb->not_empty).notify_all();
                    lock.unlock();
                }
                catch (const boost::property_tree::ptree_error &e) {
                    std::cerr << "Failed to read response reply: \n" << std::endl;
                    HVA_ASSERT(false);
                }
                catch (boost::exception &e) {
                    std::cerr << "Failed to read response reply: \n" << std::endl;
                    HVA_ASSERT(false);
                }
            }
        });

        reader.join();
        stream->WritesDone();
        grpc::Status status = stream->Finish();
        if (!status.ok()) {
            std::cout << status.error_code() << ": " << status.error_message() << std::endl;
        }

        response_received = std::chrono::high_resolution_clock::now();
        thisTime = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - first_response_received);
        timeUsed = thisTime + timeUsed;

        // std::cout << reply_msg << std::endl;
        std::cout << "request done with " << frameCnt << "frames" << std::endl;

        firstResponseIndex = frameCnt;
    }
    std::cout << "thread id: " << thread_id << std::endl;
    cpuUtilizationVal /= (frameCnt * cpuMetrics.cpuThreads());
    gpuAllUtilizationVal /= frameCnt;
    std::cout << "cpuUtilizationVal: " << cpuUtilizationVal << "%; gpuAllUtilizationVal: " << gpuAllUtilizationVal << "%" << std::endl;
    std::lock_guard<std::mutex> lg(g_mutex);
    g_total.push_back(timeUsed.count());
    g_frameCnt.push_back(frameCnt);
}

void parseReply(cv::Mat &windowImage,
                FusionVisualizer &visualizer,
                float height_resize_rate,
                float width_resize_rate,
                std::string imsg,
                int frameCnt,
                unsigned thread_id,
                std::string display_type)
{
    if (imsg == "") {
        std::cout << "parse reply done" << std::endl;
        return;
    }
    std::string ifps = imsg.substr(0, 5);
    std::string msg = imsg.substr(5, imsg.length() - 5);

    boost::property_tree::ptree jsonTree;
    std::stringstream ss(msg);
    boost::property_tree::json_parser::read_json(ss, jsonTree);

    int status_int = jsonTree.get<int>("status_code");
    int car_count = 0;
    std::vector<std::vector<cv::Point2f>> roi_all;
    std::vector<std::vector<cv::Point2f>> camera_lidar_roi_all;
    std::vector<float> vx_all;
    std::vector<float> vy_all;
    std::vector<cv::Point2f> point_all;
    vector<std::string> object_all;

    vector<int> roi_arr(4);
    vector<float> lidar_roi_arr(6);
    vector<std::vector<float>> corner_2D_arr;

    double latency;
    double e2eLatency;
    std::chrono::time_point<std::chrono::high_resolution_clock> startTime, endTime;
    if (jsonTree.get<double>("latency")) {
        roi_all.clear();
        latency = jsonTree.get<double>("latency");
        g_latency.push_back(latency);
        e2eLatency = latency;

        if (jsonTree.count("inference_latency") > 0) {
            latency = jsonTree.get<double>("inference_latency");
            g_inference_latency.push_back(latency);
        }

        if (jsonTree.count("video_latency") > 0) {
            latency = jsonTree.get<double>("video_latency");
            g_video_latency.push_back(latency);
        }

        if (0 == status_int) {
            boost::property_tree::ptree roi_info = jsonTree.get_child("roi_info");
            car_count = roi_info.size();
            for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
                auto roi_item = roi_i->second;

                // startTime = roi_item.get<std::chrono::time_point<std::chrono::high_resolution_clock>>("startTime");
                // endTime = roi_item.get<std::chrono::time_point<std::chrono::high_resolution_clock>>("endTime");

                std::string roi_class_name = roi_item.get<string>("roi_class");
                float roi_score = roi_item.get<float>("roi_score");
                int64_t sensor_source = 0;
                if (roi_item.count("sensor_source") > 0) {
                    sensor_source = roi_item.get<int64_t>("sensor_source");
                }

                if ("lidar" != display_type) {
                    boost::property_tree::ptree roi = roi_item.get_child("roi");
                    roi_arr.clear();
                    for (auto roi_j = roi.begin(); roi_j != roi.end(); ++roi_j) {
                        int point = roi_j->second.get_value<int>();
                        roi_arr.push_back(point);
                    }
                    // drawing: roi_class, roi_score, roi_points
                    if (roi_arr.size() != 4) {
                        std::cout << "wrong media roi points" << std::endl;
                    }
                    int x = roi_arr[0], y = roi_arr[1], w = roi_arr[2], h = roi_arr[3];
                    if ((x == 0 && y == 0 && w == 0 && h == 0) || (-1 == sensor_source)) {
                        // all zero, dummy data, ignore
                    }
                    else {
                        int x_resize = x / width_resize_rate;
                        int y_resize = y / height_resize_rate;
                        int w_resize = w / width_resize_rate;
                        int h_resize = h / height_resize_rate;

                        // draw bounding box in front view
                        cv::Point start_point(x_resize, y_resize);
                        cv::Point start_point2(x_resize, max(10, y_resize - 6));
                        cv::Point end_point(x_resize + w_resize, y_resize + h_resize);

                        char objectStr[256];
                        sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);
                        visualizer.drawCameraText(windowImage, thread_id * visualizer.config_.sensor_num + (sensor_source == -1 ? 0 : sensor_source), objectStr,
                                                  start_point2, cv::Scalar{0, 127, 255}, 1, 0.5, cv::LINE_8);
                        visualizer.drawCameraBox(windowImage, thread_id * visualizer.config_.sensor_num + (sensor_source == -1 ? 0 : sensor_source),
                                                 start_point, end_point, cv::Scalar{0, 255, 0}, 1, cv::LINE_8);
                    }

                    if ("media_fusion" == display_type) {
                        // TODO: Update media_fusion case
                        roi_arr.clear();
                        boost::property_tree::ptree camera_lidar_roi = roi_item.get_child("media_birdview_roi");
                        for (auto roi_j = camera_lidar_roi.begin(); roi_j != camera_lidar_roi.end(); ++roi_j) {
                            float point = roi_j->second.get_value<float>();
                            roi_arr.push_back(point);
                        }
                        if (roi_arr.size() != 4) {
                            std::cout << "wrong media lidar roi points" << std::endl;
                        }
                        float camera_lidar_x = roi_arr[0], camera_lidar_y = roi_arr[1], camera_lidar_x_size = roi_arr[2], camera_lidar_y_size = roi_arr[3];
                        if (camera_lidar_x == 0 && camera_lidar_y == 0 && camera_lidar_x_size == 0 && camera_lidar_y_size == 0) {
                            // all zero, dummy data, ignore
                        }
                        else {
                            std::vector<cv::Point2f> points(5);
                            points[0] = cv::Point2f(camera_lidar_x + camera_lidar_x_size / 2, camera_lidar_y - camera_lidar_y_size / 2);
                            points[1] = cv::Point2f(camera_lidar_x + camera_lidar_x_size / 2, camera_lidar_y + camera_lidar_y_size / 2);
                            points[2] = cv::Point2f(camera_lidar_x - camera_lidar_x_size / 2, camera_lidar_y + camera_lidar_y_size / 2);
                            points[3] = cv::Point2f(camera_lidar_x - camera_lidar_x_size / 2, camera_lidar_y - camera_lidar_y_size / 2);
                            points[4] = cv::Point2f(camera_lidar_x, camera_lidar_y);

                            camera_lidar_roi_all.push_back(points);
                        }
                    }
                }

                if ("media" != display_type) {
                    boost::property_tree::ptree lidar_roi = roi_item.get_child("lidar_roi_state");
                    lidar_roi_arr.clear();
                    std::vector<float> corner_2D;
                    for (auto roi_j = lidar_roi.begin(); roi_j != lidar_roi.end(); ++roi_j) {
                        float point = roi_j->second.get_value<float>();
                        lidar_roi_arr.push_back(point);
                    }
                    boost::property_tree::ptree lidar_roi_size = roi_item.get_child("lidar_roi_size");
                    for (auto roi_j = lidar_roi_size.begin(); roi_j != lidar_roi_size.end(); ++roi_j) {
                        float point = roi_j->second.get_value<float>();
                        lidar_roi_arr.push_back(point);
                    }
                    if (lidar_roi_arr.size() != 6) {
                        std::cout << "wrong lidar roi points" << std::endl;
                    }

                    boost::property_tree::ptree lidar_roi_projection_size = roi_item.get_child("lidar_roi_projection_size");
                    bool flag = false;
                    for (auto roi_j = lidar_roi_projection_size.begin(); roi_j != lidar_roi_projection_size.end(); ++roi_j) {
                        float point = roi_j->second.get_value<float>();
                        float point_resize;
                        if (!flag) {
                            point_resize = point / width_resize_rate;
                        }
                        else {
                            point_resize = point / height_resize_rate;
                        }
                        corner_2D.push_back(point_resize);
                        flag = !flag;
                    }
                    if (corner_2D.size() != 16) {
                        std::cout << "wrong lidar roi projection points" << std::endl;
                    }
                    if (corner_2D.size() == 16 && std::accumulate(std::begin(corner_2D), std::end(corner_2D), 0.0) != 0.0) {
                        corner_2D_arr.push_back(corner_2D);
                    }

                    float lidar_class_id = roi_item.get<int>("class_id");
                    std::string likelihood = roi_item.get<std::string>("likelihood");

                    float lidar_x = lidar_roi_arr[0], lidar_y = lidar_roi_arr[1], lidar_z = lidar_roi_arr[2], lidar_length = lidar_roi_arr[3],
                          lidar_width = lidar_roi_arr[4], lidar_height = lidar_roi_arr[5];

                    if (lidar_x == 0 && lidar_y == 0 && lidar_z == 0 && lidar_length == 0 && lidar_width == 0 && lidar_height == 0) {
                        if ((display_type == "media_fusion") && (camera_lidar_roi_all.size() != 0)) {
                            std::vector<cv::Point2f> points = camera_lidar_roi_all[camera_lidar_roi_all.size() - 1];
                            if ((points[4].x > 0) && (points[4].x < 50) && (points[4].y > -10) && (points[4].y < 10)) {
                                vx_all.push_back(0.0);
                                vy_all.push_back(0.0);
                                roi_all.push_back(points);
                                point_all.push_back(points[1]);
                                char objectStr[256];
                                sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);
                                string str = objectStr;
                                object_all.push_back(str);
                            }
                        }
                    }
                    else {
                        std::vector<cv::Point2f> points(5);

                        float temp = lidar_y;
                        lidar_y = lidar_x;
                        lidar_x = -temp;

                        points[0] = cv::Point2f(lidar_x + lidar_length / 2, lidar_y - lidar_width / 2);
                        points[1] = cv::Point2f(lidar_x + lidar_length / 2, lidar_y + lidar_width / 2);
                        points[2] = cv::Point2f(lidar_x - lidar_length / 2, lidar_y + lidar_width / 2);
                        points[3] = cv::Point2f(lidar_x - lidar_length / 2, lidar_y - lidar_width / 2);
                        points[4] = cv::Point2f(lidar_x, lidar_y);

                        vx_all.push_back(0.0);
                        vy_all.push_back(0.0);
                        roi_all.push_back(points);

                        // std::cout << "lidar_x: " << lidar_x << ", lidar_y: " << lidar_y << ", lidar_length: " << lidar_length
                        //           << ", lidar_width: " << lidar_width << ", lidar_z: " << lidar_z << std::endl;

                        if (0 != lidar_class_id) {
                            // Not car, no need to display
                        }
                        else {
                            point_all.push_back(cv::Point2f(lidar_x - lidar_length / 2, lidar_y + lidar_width / 2));
                            char objectStr[256];
                            sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);
                            string str = objectStr;
                            object_all.push_back(str);
                        }
                    }
                }

                if ("media_fusion" == display_type) {
                    visualizer.drawCamera3DBox(windowImage, thread_id * visualizer.config_.sensor_num + (sensor_source == -1 ? 0 : sensor_source),
                                               corner_2D_arr, cv::Scalar{0, 0, 255}, 1, cv::LINE_8);
                }
            }
        }
    }

    if (0 == thread_id) {
        visualizer.refreshLidarCanvas(windowImage);
        if ("media" != display_type) {
            visualizer.drawLidarObjects(windowImage, roi_all, vx_all, vy_all, cv::Scalar{0, 255, 0}, 1, cv::LINE_8, true);

            if ("media_fusion" == display_type) {
                visualizer.drawLidarText(windowImage, point_all, object_all, 0.5, cv::Scalar{0, 127, 255}, 1, cv::LINE_8, false);
            }
        }

        auto font = cv::FONT_HERSHEY_SIMPLEX;
        float fontScale = 0.5;
        int thickness = 1;
        int offset = 20;
        int lineSpace = 5;
        int baseline = 0;
        cv::Size textSize;

        char latencyStr[1024];
        sprintf(latencyStr, "E2E Processing Latency: %.2lf ms", e2eLatency);
        std::string latencyStrStd = latencyStr;

        std::string fpsStr = "FPS: " + ifps;
        std::string frameCntStr = "FrameCnt: " + to_string(frameCnt);

        std::vector<std::string> metrics = {fpsStr, frameCntStr, latencyStrStd};
        visualizer.drawMetrics(windowImage, metrics, 0, offset, fontScale, thickness, lineSpace, {0, 255, 0}, true);
    }
}


/**
 * @brief get inference results from MessgeBuffer_t
 */
string replyGet(MessageBuffer_t *cb)
{
    std::string reply;
    unique_lock<mutex> lock(cb->mtx);
    while (cb->write_pos == cb->read_pos) {
        // buffer is empty
        if (cb->is_end)
            return "";
        // std::cout << "buffer is empty, consumer is waiting ..." << std::endl;
        (cb->not_empty).wait(lock);
    }

    reply = (cb->buffer)[cb->read_pos];
    (cb->read_pos)++;

    if (cb->read_pos >= MAX_MESSAGE_BUFFER_SIZE)
        cb->read_pos = 0;

    (cb->not_full).notify_all();
    lock.unlock();
    return reply;
}

/**
 * @brief for showing metrics on specific image
 * @param image      on screen display image
 */
void plotMetrics(cv::Mat &windowImage, FusionVisualizer &visualizer, int frame_index)
{
    if (!stop_metrics) {
        // style
        int offset = 20;
        auto font = cv::FONT_HERSHEY_SIMPLEX;
        float fontScale = 0.5;
        int thickness = 1;
        int baseline = 0;
        int lineSpace = 5;
        cv::Size textSize;
        //
        // show metrics
        //
        char cpuStr[1024];
        sprintf(cpuStr, "CPU: %d%%", cpuMetricsArr[frame_index] / cpuMetrics.cpuThreads());
        std::vector<std::string> metrics = {"Intel Distribution of OpenVINO (2025.2.0)", "Intel oneMKL (2025.2.0)", "NN Model: YOLOX-S", cpuMetrics.modelName(),
                                            std::string(cpuStr)};
        char gpuStr[1024];
        float val = gpuMetricsArr[frame_index];
        // regular user cannot fetch the gpu utilization, shown as -99.9, then we ignore it.
        if (val >= 0) {
            sprintf(gpuStr, "GPU: %3.2f%%", val);
            metrics.push_back(std::string(gpuStr));
        }
        visualizer.drawMetrics(windowImage, metrics, 0, offset, fontScale, thickness, lineSpace, {255, 0, 0}, false);
    }
}

void renderOSDImage(cv::Mat &raw_image,
                    cv::Mat &windowImage,
                    FusionVisualizer &visualizer,
                    unsigned thread_id,
                    float height_resize_rate,
                    float width_resize_rate,
                    int frame_index,
                    std::string display_type,
                    MessageBuffer_t *db,
                    bool show_metrics = false)
{
    std::lock_guard<std::mutex> lg(g_window_mutex);

    for (int j = 0; j < visualizer.config_.sensor_num; ++j) {
        visualizer.updateCamera(thread_id * visualizer.config_.sensor_num + j, windowImage, raw_image);
    }

    parseReply(windowImage, visualizer, height_resize_rate, width_resize_rate, replyGet(db), frame_index, thread_id, display_type);

    if (show_metrics) {
        plotMetrics(windowImage, visualizer, frame_index);
    }
}

/**
 * @brief on screen display load, to prepare show_image for each channel
 * @param data_path input file path
 * @param j thread id
 * @param dis
 */
void OSDload(const std::vector<std::string> &inputs,
             unsigned threadNum,
             unsigned thread_id,
             std::string display_type,
             FusionVisualizer &visualizer,
             cv::Mat &windowImage,
             MessageBuffer_t *db,
             const std::string mediaType,
             bool show_metrics = false,
             bool saveFlag = false,
             bool logoFlag = true)
{
    // query each frame
    cv::VideoWriter video;
    if (saveFlag) {
        std::string filaPath = "./lidar.avi";
        video.open(filaPath, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'), 25.0, visualizer.getFusionCanvasSize(), true);
        if (!video.isOpened()) {
            cerr << "Could not open the output video file for write\n";
            return;
        }
    }
    cv::Mat img, logo, logoGray, mask, maskInv;
    if (logoFlag) {
        char filePath[512];
        memset(filePath, 0x00, sizeof(filePath));
        ssize_t len = readlink("/proc/self/exe", filePath, sizeof(filePath) - 1);
        if (len != -1) {
            filePath[len] = '\0';
        }
        else {
            std::cerr << "Failed to read /proc/self/exe" << std::endl;
            return;
        }
        std::string path = filePath;
        size_t pos = path.rfind('/');
        std::string substr = path.substr(0, pos);
        substr.append("/../../ai_inference/test/demo/intel-logo-4C4R.png");
        img = cv::imread(substr);
        if ("1C1L" == visualizer.config_.fusion_type || "2C1L" == visualizer.config_.fusion_type || "3C1L" == visualizer.config_.fusion_type ||
            "2C2L" == visualizer.config_.fusion_type) {
            cv::resize(img, logo, cv::Size(), 0.25, 0.25, cv::INTER_AREA);
        }
        else if ("4C1L" == visualizer.config_.fusion_type || "6C1L" == visualizer.config_.fusion_type || "3C1L" == visualizer.config_.fusion_type ||
                 "4C2L" == visualizer.config_.fusion_type || "4C4L" == visualizer.config_.fusion_type) {
            cv::resize(img, logo, cv::Size(), 0.5, 0.5, cv::INTER_AREA);
        }
        else {
            logo = img;
        }
        cv::cvtColor(logo, logoGray, cv::COLOR_BGR2GRAY);
        cv::threshold(logoGray, mask, 80, 255, cv::THRESH_BINARY);
        cv::bitwise_not(mask, maskInv);
    }

    int total_frames = inputs.size();
    if (mediaType == "image") {
        total_frames = inputs.size();
    }
    else if (mediaType == "multisensor") {
        total_frames = inputs.size() / 3;  // multisensor inputs, organized as [image_2, velodyne, calib]
    }
    else {
        std::cerr << "Invalid media type was parsed: " << mediaType << "!" << std::endl;
    }

    for (int i = 0; i < total_frames; i++) {
        char *buffer;
        size_t length;
        if (mediaType == "image") {
            readRawDataFromBinary(inputs[i], buffer, length);
        }
        else if (mediaType == "multisensor") {
            readRawDataFromBinary(inputs[i * 3], buffer, length);
        }
        else {
            std::cerr << "Invalid media type was parsed: " << mediaType << "!" << std::endl;
        }
        if (length == 0) {
            continue;
        }
        cv::Mat rawData(1, length, CV_8UC1, (void *)buffer);
        cv::Mat decodedImage = cv::imdecode(rawData, cv::ImreadModes::IMREAD_COLOR);

        std::unique_lock<std::mutex> lock(mtxFrames);
        cvFrames.wait(lock, [&] { return currentSyncFrame == i; });

        // if (logoFlag) {
        //     cv::Mat roi, roiBg, roiFg, dst;
        //     roi = decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10, decodedImage.rows - logo.rows - 10, logo.cols, logo.rows));
        //     cv::bitwise_and(roi, roi, roiBg, maskInv);
        //     cv::bitwise_and(logo, logo, roiFg, mask);
        //     cv::add(roiBg, roiFg, dst);
        //     cv::addWeighted(dst, 0.5, roi, 0.5, 0,
        //                     decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10, decodedImage.rows - logo.rows - 10, logo.cols, logo.rows)));
        // }

        float height_resize_rate = static_cast<float>(decodedImage.rows) / visualizer.config_.camera_canvas_height;
        float width_resize_rate = static_cast<float>(decodedImage.cols) / visualizer.config_.camera_canvas_width;
        renderOSDImage(decodedImage, windowImage, visualizer, thread_id, height_resize_rate, width_resize_rate, i, display_type, db, show_metrics);

        readyFrames++;
        if (readyFrames == threadNum) {
            readyFrames = 0;
            currentSyncFrame++;
            cvFrames.notify_all();
        }
        else {
            cvFrames.wait(lock, [&] { return currentSyncFrame > i; });
        }

        if (thread_id == 0 && logoFlag) {
            cv::Mat roi, roiBg, roiFg, dst;
            roi = windowImage(cv::Rect(windowImage.cols - logo.cols - 20, windowImage.rows - logo.rows - 20, logo.cols, logo.rows));
            cv::bitwise_and(roi, roi, roiBg, maskInv);
            cv::bitwise_and(logo, logo, roiFg, mask);
            cv::add(roiBg, roiFg, dst);
            cv::addWeighted(dst, 0.5, roi, 0.5, 0,
                            windowImage(cv::Rect(windowImage.cols - logo.cols - 20, windowImage.rows - logo.rows - 20, logo.cols, logo.rows)));
        }
        std::lock_guard<std::mutex> lg(g_window_mutex);
        if (thread_id == 0 && saveFlag) {
            video.write(windowImage);
        }
        delete[] buffer;
    }

    video.release();

    stop_display = true;
    std::cout << "Display done!" << std::endl;
}

/**
 * @brief use a seperate thread to continuously imshow()
 */
void displayload(cv::Mat &windowImage)
{
    while (!stop_display) {
        cv::imshow(WINDOWNAME, windowImage);
        cv::waitKey(5);
    }
}

int getGPUUtilization(int interval = 1)
{
    try {
        std::string command = "sudo timeout 1 xpu-smi stats -d 0 -j";
        std::thread gt(runXpuSmi, command, interval);

        gt.detach();
        return 0;
    }
    catch (std::exception const &e) {
        return -1;
    }
}

std::string toUpper(const std::string &str)
{
    std::string upper_str = str;
    std::transform(upper_str.begin(), upper_str.end(), upper_str.begin(), ::toupper);
    return upper_str;
}

int initVisualizationCfg(FusionVisualizerConfig &cfg, std::string &visualizationType)
{
    cfg.lidar_view = LidarViewType::FRONT;
    cfg.lidar_x_min = -30;
    cfg.lidar_x_max = 30;
    cfg.lidar_y_min = 0;
    cfg.lidar_y_max = 80;
    cfg.grid_step = 5;
    if ("1C1L" == toUpper(visualizationType)) {
        cfg.camera_count = 1;
        cfg.cam_cols = 1;
        cfg.cam_rows = 1;
        cfg.sensor_num = 1;
        cfg.fusion_type = "1C1L";
    }
    else if ("2C1L" == toUpper(visualizationType)) {
        cfg.camera_count = 2;
        cfg.cam_cols = 2;
        cfg.cam_rows = 1;
        cfg.sensor_num = 2;
        cfg.fusion_type = "2C1L";
    }
    else if ("3C1L" == toUpper(visualizationType)) {
        cfg.camera_count = 3;
        cfg.cam_cols = 1;
        cfg.cam_rows = 3;
        cfg.sensor_num = 3;
        cfg.fusion_type = "3C1L";
    }
    else if ("4C1L" == toUpper(visualizationType)) {
        cfg.camera_count = 4;
        cfg.cam_cols = 2;
        cfg.cam_rows = 2;
        cfg.sensor_num = 4;
        cfg.fusion_type = "4C1L";
    }
    else if ("6C1L" == toUpper(visualizationType)) {
        cfg.camera_count = 6;
        cfg.cam_cols = 2;
        cfg.cam_rows = 3;
        cfg.sensor_num = 6;
        cfg.fusion_type = "6C1L";
    }
    else if ("2C2L" == toUpper(visualizationType)) {
        cfg.camera_count = 2;
        cfg.cam_cols = 2;
        cfg.cam_rows = 1;
        cfg.sensor_num = 1;
        cfg.fusion_type = "2C2L";
    }
    else if ("4C2L" == toUpper(visualizationType)) {
        cfg.camera_count = 4;
        cfg.cam_cols = 2;
        cfg.cam_rows = 2;
        cfg.sensor_num = 2;
        cfg.fusion_type = "4C2L";
    }
    else if ("4C4L" == toUpper(visualizationType)) {
        cfg.camera_count = 4;
        cfg.cam_cols = 2;
        cfg.cam_rows = 2;
        cfg.sensor_num = 1;
        cfg.fusion_type = "4C4L";
    }
    else if ("8C2L" == toUpper(visualizationType)) {
        cfg.camera_count = 8;
        cfg.cam_cols = 4;
        cfg.cam_rows = 2;
        cfg.sensor_num = 4;
        cfg.fusion_type = "8C2L";
    }
    else if ("8C4L" == toUpper(visualizationType)) {
        cfg.camera_count = 8;
        cfg.cam_cols = 2;
        cfg.cam_rows = 4;
        cfg.sensor_num = 2;
        cfg.fusion_type = "8C4L";
    }
    else if ("12C2L" == toUpper(visualizationType)) {
        cfg.camera_count = 12;
        cfg.cam_cols = 3;
        cfg.cam_rows = 4;
        cfg.sensor_num = 6;
        cfg.fusion_type = "12C2L";
    }
    else if ("12C4L" == toUpper(visualizationType)) {
        cfg.camera_count = 12;
        cfg.cam_cols = 3;
        cfg.cam_rows = 4;
        cfg.sensor_num = 3;
        cfg.fusion_type = "12C4L";
    }
    else {
        std::cerr << "Invalid visualization type was parsed: " << visualizationType << "!" << std::endl;
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (argc < 9 || argc > 14) {
            std::cerr << "Usage: CLSensorFusionDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <display_type> <visualization_type>"
                         "[<save_flag: 0 | 1>] [<pipeline_repeats>] [<cross_stream_num>] [<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]\n"
                      << "Example:\n"
                      << "    ./CLSensorFusionDisplay 127.0.0.1 50052 ../../ai_inference/test/configs/raddet/localFusionPipeline.json 1 1 "
                         "/path/to/dataset media_fusion 1C1L\n"
                      << "-------------------------------------------------------------------------------- \n"
                      << "Environment requirement:\n"
                      << "   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset HTTPS_PROXY   \n"
                      << std::endl;
            return EXIT_FAILURE;
        }
        std::string host(argv[1]);
        std::string port(argv[2]);
        std::string jsonFile(argv[3]);
        unsigned totalStreamNum(atoi(argv[4]));
        unsigned repeats = atoi(argv[5]);
        std::string dataPath(argv[6]);
        std::string displayType(argv[7]);
        std::string visualizationType(argv[8]);
        HVA_DEBUG("displayType: %s", displayType);
        HVA_DEBUG("visualizationType: %s", visualizationType);
        HVA_DEBUG("dataPath: %s", dataPath.c_str());

        // optional args
        unsigned pipeline_repeats = 1;
        unsigned crossStreamNum = 1;
        bool warmupFlag = true;
        bool saveFlag = false;
        bool logoFlag = true;

        if (argc == 10) {
            saveFlag = bool(atoi(argv[9]));
        }
        if (argc == 11) {
            saveFlag = bool(atoi(argv[9]));
            pipeline_repeats = atoi(argv[10]);
        }
        if (argc == 12) {
            saveFlag = bool(atoi(argv[9]));
            pipeline_repeats = atoi(argv[10]);
            crossStreamNum = atoi(argv[11]);
        }
        if (argc == 13) {
            saveFlag = bool(atoi(argv[9]));
            pipeline_repeats = atoi(argv[10]);
            crossStreamNum = atoi(argv[11]);
            warmupFlag = bool(atoi(argv[12]));
        }
        if (argc == 14) {
            saveFlag = bool(atoi(argv[9]));
            pipeline_repeats = atoi(argv[10]);
            crossStreamNum = atoi(argv[11]);
            warmupFlag = bool(atoi(argv[12]));
            logoFlag = bool(atoi(argv[13]));
        }

        // for sanity check
        if (totalStreamNum < crossStreamNum) {
            std::cerr << "total-stream-number should be no less than cross-stream-number!" << std::endl;
            return EXIT_FAILURE;
        }
        if (totalStreamNum / crossStreamNum * crossStreamNum != totalStreamNum) {
            std::cerr << "total-stream-number should be divisible by cross-stream-number!" << std::endl;
            return EXIT_FAILURE;
        }

        unsigned threadNum = totalStreamNum / crossStreamNum;
        if (warmupFlag) {
            std::cout << "Warmup workloads with " << threadNum << " threads..." << std::endl;
        }

        std::string contents;
        std::ifstream in(jsonFile, std::ios::in);
        if (in) {
            in.seekg(0, std::ios::end);
            contents.resize(in.tellg());
            in.seekg(0, std::ios::beg);
            in.read(&contents[0], contents.size());
            in.close();
        }

        std::vector<std::thread> vThs;
        std::vector<std::thread> dThs;
        std::thread displayThread;

        if ("media" != displayType && "lidar" != displayType && "media_lidar" != displayType && "media_fusion" != displayType) {
            cerr << "wrong display type(only support media, lidar, media_lidar, media_fusion)." << std::endl;
            return EXIT_FAILURE;
        }

        // ---------------------------------------------------------------------------
        //                                 init cpu/gpu metrics
        //  ---------------------------------------------------------------------------
        std::cout << "Initialize system metrics for cpu and gpu..." << std::endl;
        // if (SHOWGPUMETRIC)
        //     gpuMetrics.init();
        // get metrics for specific process
        // cpuMetrics.init("HceAILLInfServe");  // statistic only HceAIInfServe process
        cpuMetrics.init();  // for C+L, we may create multiple HceAIInfServe process, need to monitor all HceAIInfServe process
        stop_metrics = false;

        // ---------------------------------------------------------------------------
        //                                 init display
        //  ---------------------------------------------------------------------------

        FusionVisualizerConfig cfg;
        initVisualizationCfg(cfg, visualizationType);

        FusionVisualizer visualizer(cfg);
        cv::Mat windowImage = cv::Mat::zeros(visualizer.fusion_canvas_size_.height, visualizer.fusion_canvas_size_.width, CV_8UC3);
        visualizer.updateLoading(windowImage);
        stop_display = false;

        // ---------------------------------------------------------------------------
        //                                 processing
        //  ---------------------------------------------------------------------------
        std::cout << "Start processing with " << threadNum << " threads: total-stream = " << totalStreamNum << ", each thread will process " << crossStreamNum
                  << " streams" << std::endl;

        vThs.clear();
        dThs.clear();
        std::vector<std::string> inputs;        // paths of input bin files
        std::string mediaType = "multisensor";  // default media type is multisensor, can be image, multisensor
        if ("media" == displayType) {
            mediaType = "image";  // media display type, only image is supported
        }
        parseInputs(dataPath, inputs, mediaType);

        struct MessageBuffer_t msg_buffer[threadNum];
        for (unsigned i = 0; i < threadNum; ++i) {
            initMessageBuffer(&msg_buffer[i]);
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(inputs), i, &msg_buffer[i], repeats, crossStreamNum,
                          warmupFlag, pipeline_repeats);  // workload for ai inference
            vThs.push_back(std::move(t));
        }

        int interval = 1;
        if (getGPUUtilization(interval) < 0) {
            std::cerr << "Error: Get GPU utilization error." << std::endl;
            return EXIT_FAILURE;
        }
        sleep(2);

        // start to display
        displayThread = std::thread(displayload, std::ref(windowImage));

        std::vector<std::string> repeatinputs;
        for (unsigned i = 0; i < repeats; ++i) {
            repeatinputs.insert(repeatinputs.end(), inputs.begin(), inputs.end());
        }
        std::vector<std::string> pipeline_repeat_inputs;
        for (unsigned i = 0; i < pipeline_repeats; ++i) {
            pipeline_repeat_inputs.insert(pipeline_repeat_inputs.end(), repeatinputs.begin(), repeatinputs.end());
        }
        // TODO: continuously update OSD on windowImage
        for (unsigned j = 0; j < threadNum; ++j) {
            bool showMetrics = j == 0;
            std::thread d(OSDload, std::ref(pipeline_repeat_inputs), threadNum, j, displayType, std::ref(visualizer), std::ref(windowImage), &msg_buffer[j],
                          mediaType, showMetrics, saveFlag, logoFlag);
            dThs.push_back(std::move(d));
        }

        for (auto &item : vThs) {
            item.join();
        }

        for (auto &item : dThs) {
            item.join();
        }

        displayThread.join();

        // passively stopped
        if (false == stop_metrics) {
            stop_metrics = true;
        }
        // ---------------------------------------------------------------------------
        //                                 performance check
        //  ---------------------------------------------------------------------------
        float totalTime = 0;
        std::size_t totalFrames = 0;
        std::lock_guard<std::mutex> lg(g_mutex);
        std::cout << "Time used by each thread: " << std::endl;
        for (std::size_t tix = 0; tix < g_total.size(); tix++) {
            std::cout << g_frameCnt[tix] << "frames," << g_total[tix] << " ms" << std::endl;
            totalTime += g_total[tix];
            totalFrames += g_frameCnt[tix];
        }
        std::cout << "Total time: " << totalTime << " ms" << std::endl;

        float totalRequests = (float)threadNum * pipeline_repeats;
        float mean = totalTime / g_total.size();  // mean time for each thread (include all repeats)
        std::cout << "Mean time: " << mean << " ms" << std::endl;
        // float qps = totalRequests / (mean / 1000.0);
        // std::cout << "\n qps: " << qps << std::endl;
        // std::cout << "\n qps per stream: " << qps / totalStreamNum << std::endl;

        /* frames_each_stream / time_each_stream => fps_each_stream */
        float fps = (((float)totalFrames - pipeline_repeats) / totalStreamNum) / (mean / 1000.0);
        double latency_sum = std::accumulate(std::begin(g_latency), std::end(g_latency), 0.0);
        double latency_ave = latency_sum / g_latency.size();
        double inference_latency_ave = 0.0;
        double video_latency_ave = 0.0;
        if (g_inference_latency.size() > 0) {
            double inference_latency_sum = std::accumulate(std::begin(g_inference_latency), std::end(g_inference_latency), 0.0);
            inference_latency_ave = inference_latency_sum / g_inference_latency.size();
        }
        if (g_video_latency.size() > 0) {
            double video_latency_sum = std::accumulate(std::begin(g_video_latency), std::end(g_video_latency), 0.0);
            video_latency_ave = video_latency_sum / g_video_latency.size();
        }

        std::cout << "\n=================================================\n" << std::endl;
        std::cout << "WARMUP: " << std::to_string(warmupFlag) << std::endl;
        std::cout << "fps: " << fps << std::endl;
        std::cout << "average latency " << latency_ave << std::endl;
        std::cout << "video pipeline average latency " << video_latency_ave << std::endl;
        std::cout << "inference average latency " << inference_latency_ave << std::endl;
        std::cout << "For each repeat: " << threadNum << " threads have been processed, total-stream = " << totalStreamNum << ", each thread processed "
                  << crossStreamNum << " streams" << std::endl;
        std::cout << "fps per stream: " << fps << ", including " << totalFrames << " frames" << std::endl;

        std::cout << "\n=================================================\n" << std::endl;

        return 0;
    }
    catch (std::exception const &e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
