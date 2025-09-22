/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2024 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#include <sys/timeb.h>

#include <boost/property_tree/json_parser.hpp>
#include <chrono>
#include <mutex>
#include <opencv2/imgproc.hpp>
#include <opencv2/opencv.hpp>

#include "common/base64.hpp"
#include "low_latency_client/grpcClient.hpp"
#include "math.h"
#include "modules/visualization/Plot.h"
#include "utils/displayUtils.hpp"
#include "utils/sys_metrics/cpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_monitor.h"
#include "utils/testUtils.hpp"

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
static const string WINDOWNAME = "Camera + Radar Sensor Fusion";
std::vector<int> cpuMetricsArr;
std::vector<float> gpuMetricsArr;
std::vector<float> timeArr;

std::mutex mtxFrames;
std::condition_variable cvFrames;
int readyFrames = 0;
int currentSyncFrame = 0;

/**
 * @brief parse input local file
 */
void parseInputs(const std::string data_path, std::vector<std::string>& inputs,
                 std::string& mediaType) {
  if (boost::filesystem::exists(data_path)) {
    // is regular file
    if (boost::filesystem::is_directory(data_path)) {
      // use case:
      // multi-sensor inputs, organized as [bgr, radar, depth]
      if (!checkIsFolder(data_path)) {
        HVA_ERROR("path should be valid folder: %s", data_path.c_str());
        HVA_ASSERT(false);
      }

      std::vector<std::string> bgrInputs;
      getAllFiles(data_path + "/bgr", bgrInputs, ".bin");

      std::string path;
      // insert aligned sensor data by sequence
      for (int i = 0; i < bgrInputs.size(); i++) {
        path = parseAbsolutePath(bgrInputs[i]);
        inputs.push_back(path);
      }

      mediaType = "multisensor";
      std::cout << "Load " << inputs.size()
                << " files from folder: " << data_path.c_str()
                << ", mark media type as: " << mediaType << std::endl;
    } else {
      std::cerr << "Unknown data_path is specified: " << data_path.c_str()
                << ", it's neither regular file nor a directory, please check!"
                << std::endl;
      HVA_ASSERT(false);
    }
  } else {
    std::cerr << "File not exists: " << data_path.c_str() << std::endl;
    HVA_ASSERT(false);
  }
}

/**
 * warm up pipelines before running to promote throughputs
 */
void warmup(const std::string& host, const std::string& port,
            const std::string& json) {
  GRPCClient client{host, port};

  std::shared_ptr<hce_ai::ai_inference::Stub> stub = client.connect();
  grpc::ClientContext context;
  std::shared_ptr<
      grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>>
      stream(stub->Run(&context));

  hce_ai::AI_Request request;
  request.set_target("load_pipeline");
  request.set_pipelineconfig(json);
  request.set_suggestedweight(0);

  stream->Write(request);

  // parse ret results
  hce_ai::AI_Response reply;
  std::string reply_msg;
  while (stream->Read(&reply)) {
    std::string msg = reply.message();
    std::cout << msg << std::endl;
  }

  stream->WritesDone();

  grpc::Status status = stream->Finish();
  if (!status.ok()) {
    std::cout << status.error_code() << ": " << status.error_message()
              << std::endl;
  }
}

/**
 * process response parameters
 */
void responseProcess(const hce_ai::AI_Response& reply) {
  for (const auto& pair : reply.responses()) {
    int frameId = atoi((pair.first.c_str()));
    hce_ai::Stream_Response sr = pair.second;

    if (sr.has_binary()) {
      /**
       * msg:
       *  {
       *      "format": "NV12",
       *      "height": "1088",
       *      "width": "1920"
       *  }
       */
      std::string msg = sr.jsonmessages();
      std::string binaryData = sr.binary();

      boost::property_tree::ptree jsonMessage;
      std::stringstream ss(msg);
      boost::property_tree::read_json(ss, jsonMessage);
      size_t height = jsonMessage.get<size_t>("height");
      size_t width = jsonMessage.get<size_t>("width");
      std::string format = jsonMessage.get<std::string>("format");
      std::cout << "received binary data, frameId: " << frameId
                << ", color: " << format << ", height: " << height
                << ", width: " << width
                << ", content size: " << binaryData.size() << std::endl;
    }
  }
}

void workload(const std::string& host, const std::string& port,
              const std::string& json,
              const std::vector<std::string>& mediaVector, unsigned repeats,
              MessageBuffer_t* pb, unsigned thread_id, unsigned stream_num,
              unsigned pipeline_repeats, bool warmup_flag) {
  GRPCClient client{host, port};

  std::chrono::time_point<std::chrono::high_resolution_clock> request_sent,
      response_received, first_response_received;
  std::chrono::milliseconds timeUsed(0);
  std::chrono::milliseconds thisTime(0);
  std::size_t frameCnt(0);

  std::vector<std::string> repeatmediaVector;
  for (unsigned i = 0; i < repeats; ++i) {
    repeatmediaVector.insert(repeatmediaVector.end(), mediaVector.begin(),
                             mediaVector.end());
  }

  std::vector<std::string> inputs;
  // repeat input media for `stream_num` times
  for (unsigned i = 0; i < stream_num; i++) {
    inputs.insert(inputs.end(), repeatmediaVector.begin(),
                  repeatmediaVector.end());
  }
  std::string info = "[thread " + std::to_string(thread_id) +
                     "] Input media size is: " + std::to_string(inputs.size());
  std::cout << info << std::endl;

  std::shared_ptr<hce_ai::ai_inference::Stub> stub = client.connect();
  size_t job_handle = 0;
  int firstResponseIndex = 0;
  float cpuUtilizationVal = 0.0;
  float gpuAllUtilizationVal = 0.0;
  for (unsigned i = 0; i < pipeline_repeats; ++i) {
    grpc::ClientContext context;
    std::shared_ptr<
        grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>>
        stream(stub->Run(&context));
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
      std::cout << "reply: " << reply.message()
                << ", reply_status: " << reply.status() << std::endl;
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
        std::cout << "pipeline has been loaded, job handle: " << job_handle
                  << std::endl;
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
        std::cout
            << "sending request ====> pipeline will run on specific jobhandle"
            << std::endl;
        request.set_jobhandle(job_handle);
      } else {
        std::cout << "sending request ====> run" << std::endl;
        request.set_pipelineconfig(json);
      }

      // Client send requests on specific context
      stream->Write(request);
    }

    // int gpuCount = gpuMetrics.deviceCount();
    // parse ret results
    std::thread reader([&]() {
      hce_ai::AI_Response reply;
      std::string reply_msg;
      int reply_status;
      while (stream->Read(&reply)) {
        std::string msg = reply.message();
        // response received
        response_received = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
                            response_received - request_sent)
                            .count();

        if (isFirst) {
          std::lock_guard<std::mutex> lg(g_mutex);
          // std::cout << "thread " << thread_id << ", latency: " << duration <<
          // "ms" << std::endl; g_latency.push_back(duration);
          first_response_received = response_received;
          isFirst = false;
        }

        reply_status = reply.status();
        std::cout << "frame index: " << frameCnt
                  << ", reply_status: " << reply_status << std::endl;
        std::cout << msg << std::endl;

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
        auto timeElapsed =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                response_received - first_response_received)
                .count();
        float curFPS = fpsCnt == 0 ? 0 : fpsCnt * 1000.0 / timeElapsed;
        std::cout << "curFPS: " << curFPS << ", frames: " << frameCnt
                  << std::endl;
        msg = to_string(curFPS).substr(0, 5) + msg;

        if (frameCnt % 100 == 0) {
          std::string info = "[thread " + std::to_string(thread_id) + "] " +
                             std::to_string(frameCnt) +
                             " frames have been processed.";
          std::cout << info << std::endl;
        }

        try {
          // parse response message to MessageBuffer_t
          unique_lock<mutex> lock(pb->mtx);

          while (((pb->write_pos + 1) % MAX_MESSAGE_BUFFER_SIZE) ==
                 pb->read_pos) {
            // buffer is full
            // std::cout << "buffer is full now, producer is waiting
            // ..." << std::endl;
            (pb->not_full).wait(lock);
          }
          (pb->buffer)[pb->write_pos] = msg;
          (pb->write_pos)++;

          if (pb->write_pos == MAX_MESSAGE_BUFFER_SIZE) pb->write_pos = 0;

          (pb->not_empty).notify_all();
          lock.unlock();
        } catch (const boost::property_tree::ptree_error& e) {
          std::cerr << "Failed to read response reply: \n" << std::endl;
          HVA_ASSERT(false);
        } catch (boost::exception& e) {
          std::cerr << "Failed to read response reply: \n" << std::endl;
          HVA_ASSERT(false);
        }
      }
    });

    reader.join();
    stream->WritesDone();
    grpc::Status status = stream->Finish();
    if (!status.ok()) {
      std::cout << status.error_code() << ": " << status.error_message()
                << std::endl;
    }

    response_received = std::chrono::high_resolution_clock::now();
    thisTime = std::chrono::duration_cast<std::chrono::milliseconds>(
        response_received - first_response_received);
    timeUsed = thisTime + timeUsed;

    // std::cout << reply_msg << std::endl;
    std::cout << "request done with " << frameCnt << " frames" << std::endl;
    firstResponseIndex = frameCnt;
  }
  std::cout << "thread id: " << thread_id << std::endl;
  cpuUtilizationVal /= (frameCnt * cpuMetrics.cpuThreads());
  gpuAllUtilizationVal /= frameCnt;
  std::cout << "cpuUtilizationVal: " << cpuUtilizationVal
            << "%; gpuAllUtilizationVal: " << gpuAllUtilizationVal << "%"
            << std::endl;
  std::lock_guard<std::mutex> lg(g_mutex);
  g_total.push_back(timeUsed.count());
  g_frameCnt.push_back(frameCnt);
}

void parseReply(cv::Mat& frame, Plot& pl, float resize_rate, std::string imsg,
                int frameCnt, unsigned thread_id, int raw_image_width,
                int raw_image_height, std::string displayType) {
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
  std::vector<std::vector<cv::Point2f>> camera_radar_roi_all;
  std::vector<float> vx_all;
  std::vector<float> vy_all;
  std::vector<cv::Point2f> point_all;
  vector<std::string> object_all;

  vector<int> roi_arr(4);
  vector<float> radar_roi_arr(6);

  double latency;
  if (jsonTree.count("latency") > 0) {
    roi_all.clear();
    boost::property_tree::ptree roi_info = jsonTree.get_child("roi_info");
    car_count = roi_info.size();
    latency = jsonTree.get<double>("latency");
    g_latency.push_back(latency);
    if (jsonTree.count("inference_latency") > 0) {
      latency = jsonTree.get<double>("inference_latency");
      g_inference_latency.push_back(latency);
    }
    if (jsonTree.count("video_latency") > 0) {
      latency = jsonTree.get<double>("video_latency");
      g_video_latency.push_back(latency);
    }
    for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
      bool isAssociated = false;
      auto roi_item = roi_i->second;

      std::string roi_class_name = roi_item.get<string>("roi_class");

      float roi_score = roi_item.get<float>("roi_score");
      // if (roi_class.size() != 4 && roi_score < 0.8)
      // continue;
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
      if (x == 0 && y == 0 && w == 0 && h == 0) {
        // all zero, dummy data, ignore
      } else {
        int x_resize = x / resize_rate;
        int y_resize = y / resize_rate;
        int w_resize = w / resize_rate;
        int h_resize = h / resize_rate;

        // draw bounding box in front view
        cv::Point start_point(x_resize + raw_image_width * (thread_id % 2),
                              y_resize + raw_image_height * (thread_id / 2));
        cv::Point end_point(
            x_resize + w_resize + raw_image_width * (thread_id % 2),
            y_resize + h_resize + raw_image_height * (thread_id / 2));
        cv::Point start_point2(
            x_resize + raw_image_width * (thread_id % 2),
            max(10, y_resize - 6) + raw_image_height * (thread_id / 2));

        char objectStr[256];
        sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);
        if (displayType != "radar") {
          cv::putText(frame, objectStr, start_point2, cv::FONT_HERSHEY_SIMPLEX,
                      1, cv::Scalar{0, 127, 255}, 2, cv::LINE_8);
          cv::rectangle(frame, start_point, end_point, cv::Scalar{0, 255, 0}, 2,
                        cv::LINE_8);
        }
      }

      roi_arr.clear();
      boost::property_tree::ptree camera_radar_roi =
          roi_item.get_child("media_birdview_roi");
      for (auto roi_j = camera_radar_roi.begin();
           roi_j != camera_radar_roi.end(); ++roi_j) {
        float point = roi_j->second.get_value<float>();
        roi_arr.push_back(point);
      }
      if (roi_arr.size() != 4) {
        std::cout << "wrong media radar roi points" << std::endl;
      }
      float camera_radar_x = roi_arr[0], camera_radar_y = roi_arr[1],
            camera_radar_x_size = roi_arr[2], camera_radar_y_size = roi_arr[3];
      if (camera_radar_x == 0 && camera_radar_y == 0 &&
          camera_radar_x_size == 0 && camera_radar_y_size == 0) {
        // all zero, dummy data, ignore
      } else {
        camera_radar_x_size = 4.2;
        camera_radar_y_size = 1.7;
        camera_radar_y = -camera_radar_y;

        std::vector<cv::Point2f> points(5);

        points[0] = cv::Point2f(camera_radar_x + camera_radar_x_size / 2,
                                camera_radar_y - camera_radar_y_size / 2);
        points[1] = cv::Point2f(camera_radar_x + camera_radar_x_size / 2,
                                camera_radar_y + camera_radar_y_size / 2);
        points[2] = cv::Point2f(camera_radar_x - camera_radar_x_size / 2,
                                camera_radar_y + camera_radar_y_size / 2);
        points[3] = cv::Point2f(camera_radar_x - camera_radar_x_size / 2,
                                camera_radar_y - camera_radar_y_size / 2);
        points[4] = cv::Point2f(camera_radar_x, camera_radar_y);

        camera_radar_roi_all.push_back(points);
      }

      boost::property_tree::ptree radar_roi =
          roi_item.get_child("fusion_roi_state");
      radar_roi_arr.clear();
      for (auto roi_j = radar_roi.begin(); roi_j != radar_roi.end(); ++roi_j) {
        float point = roi_j->second.get_value<float>();
        radar_roi_arr.push_back(point);
      }
      boost::property_tree::ptree radar_roi_size =
          roi_item.get_child("fusion_roi_size");
      for (auto roi_j = radar_roi_size.begin(); roi_j != radar_roi_size.end();
           ++roi_j) {
        float point = roi_j->second.get_value<float>();
        radar_roi_arr.push_back(point);
      }
      // drawing: roi_class, roi_score, roi_points
      if (radar_roi_arr.size() != 6) {
        std::cout << "wrong radar roi points" << std::endl;
      }

      float radar_x = radar_roi_arr[0], radar_y = radar_roi_arr[1],
            vx = radar_roi_arr[2], vy = radar_roi_arr[3],
            xSize = radar_roi_arr[4], ySize = radar_roi_arr[5];
      if (radar_x == 0 && radar_y == 0 && vx == 0 && vy == 0 && xSize == 0 &&
          ySize == 0) {
        if ((displayType == "media_fusion") &&
            (camera_radar_roi_all.size() != 0)) {
          std::vector<cv::Point2f> points =
              camera_radar_roi_all[camera_radar_roi_all.size() - 1];
          if ((points[4].x > 0) && (points[4].x < 50) && (points[4].y > -10) &&
              (points[4].y < 10)) {
            vx_all.push_back(0.0);
            vy_all.push_back(0.0);
            roi_all.push_back(points);
            point_all.push_back(points[1]);
            char objectStr[256];
            sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(),
                    roi_score);
            string str = objectStr;
            object_all.push_back(str);
          }
        }
      } else {
        xSize = 4.2;
        ySize = 1.7;
        radar_y = -radar_y;
        vy = -vy;

        std::vector<cv::Point2f> points(5);
        points[0] = cv::Point2f(radar_x + xSize / 2, radar_y - ySize / 2);
        points[1] = cv::Point2f(radar_x + xSize / 2, radar_y + ySize / 2);
        points[2] = cv::Point2f(radar_x - xSize / 2, radar_y + ySize / 2);
        points[3] = cv::Point2f(radar_x - xSize / 2, radar_y - ySize / 2);
        points[4] = cv::Point2f(radar_x, radar_y);

        vx_all.push_back(vx);
        vy_all.push_back(vy);
        roi_all.push_back(points);

        // if (thread_id == 0) {
        if (displayType == "media_fusion") {
          char objectStr[256];
          sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);
          string str = objectStr;
          if (roi_class_name == "dummy") {
            // Filled with dummy data, no need to display
          } else {
            point_all.push_back(
                cv::Point2f(radar_x + xSize / 2, radar_y + ySize / 2));
            object_all.push_back(str);
          }
        }
        // }
      }
    }
  }

  // pl.clear();
  // if (displayType != "media" && thread_id == 0) {
  //     pl.drawRadarResults(roi_all, vx_all, vy_all, cv::Scalar{0, 255, 0}, 1,
  //     true);
  // }
  // if (0 == thread_id && displayType == "media_fusion" && !object_all.empty())
  // {
  //     pl.drawText(point_all, object_all, cv::Scalar{0, 127, 255}, 1, false);
  // }

  if (0 == thread_id) {
    pl.clear();
    if ("media" != displayType) {
      pl.drawRadarResults(roi_all, vx_all, vy_all, cv::Scalar{0, 255, 0}, 1,
                          true);
      if (!object_all.empty()) {
        pl.drawText(point_all, object_all, 0.5, cv::Scalar{0, 127, 255}, 1,
                    false);
      }
    }

    cv::Mat plot = pl.getPlotImage();
    cv::resize(plot, plot, Size(plot.cols * 2, plot.rows * 2));
    plot.copyTo(
        frame(cv::Rect(frame.cols - plot.cols, 0, plot.cols, plot.rows)));

    auto font = cv::FONT_HERSHEY_SIMPLEX;
    float fontScale = 1;
    int thickness = 2;
    int offset = 1580;
    int lineSpace = 5;
    int baseline = 0;
    cv::Size textSize;
    int cols = plot.cols;

    std::string fpsStr = "FPS: " + ifps;
    std::string frameCntStr = "FrameCnt: " + to_string(frameCnt);

    // show FPS
    textSize = cv::getTextSize(fpsStr, cv::FONT_HERSHEY_SIMPLEX, fontScale,
                               thickness, &baseline);
    cv::putText(frame, fpsStr, cv::Point(frame.cols - cols + 100, offset),
                cv::FONT_HERSHEY_SIMPLEX, fontScale, {0, 255, 0}, thickness,
                cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    textSize = cv::getTextSize(frameCntStr, cv::FONT_HERSHEY_SIMPLEX, fontScale,
                               thickness, &baseline);
    cv::putText(frame, frameCntStr, cv::Point(frame.cols - cols + 100, offset),
                cv::FONT_HERSHEY_SIMPLEX, fontScale, {0, 255, 0}, thickness,
                cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    // show latency
    char latencyStr[1024];
    sprintf(latencyStr, "E2E Processing Latency: %.2lf ms", latency);
    std::string latencyStrStd = latencyStr;
    textSize = cv::getTextSize(latencyStrStd, cv::FONT_HERSHEY_SIMPLEX,
                               fontScale, thickness, &baseline);
    cv::putText(frame, latencyStrStd,
                cv::Point(frame.cols - cols + 100, offset),
                cv::FONT_HERSHEY_SIMPLEX, fontScale, {0, 255, 0}, thickness,
                cv::LINE_8);
  }
}

/**
 * @brief get inference results from MessgeBuffer_t
 */
string replyGet(MessageBuffer_t* cb) {
  std::string reply;
  unique_lock<mutex> lock(cb->mtx);
  while (cb->write_pos == cb->read_pos) {
    // buffer is empty
    if (cb->is_end) return "";
    // std::cout << "buffer is empty, consumer is waiting ..." << std::endl;
    (cb->not_empty).wait(lock);
  }

  reply = (cb->buffer)[cb->read_pos];
  (cb->read_pos)++;

  if (cb->read_pos >= MAX_MESSAGE_BUFFER_SIZE) cb->read_pos = 0;

  (cb->not_full).notify_all();
  lock.unlock();
  return reply;
}

/**
 * @brief for showing metrics on specific image
 * @param image      on screen display image
 */
void plotMetrics(cv::Mat& image, int frame_index, int cols) {
  if (!stop_metrics) {
    // style
    int offset = 1700;
    auto font = cv::FONT_HERSHEY_SIMPLEX;
    float fontScale = 1;
    int thickness = 2;
    int baseline = 0;
    int lineSpace = 5;
    cv::Size textSize;
    //
    // show metrics
    //
    textSize = cv::getTextSize("Intel Distribution of OpenVINO (2025.2.0)",
                               font, fontScale, thickness, &baseline);
    cv::putText(image, "Intel Distribution of OpenVINO (2025.2.0)",
                cv::Point(image.cols - cols + 100, offset), font, fontScale,
                {0, 127, 255}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    textSize = cv::getTextSize("Intel oneMKL (2025.1.0)", font, fontScale,
                               thickness, &baseline);
    cv::putText(image, "Intel oneMKL (2025.1.0)",
                cv::Point(image.cols - cols + 100, offset), font, fontScale,
                {0, 127, 255}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    textSize = cv::getTextSize("NN Model: YOLOX-S", font, fontScale, thickness,
                               &baseline);
    cv::putText(image, "NN Model: YOLOX-S",
                cv::Point(image.cols - cols + 100, offset), font, fontScale,
                {0, 127, 255}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    textSize = cv::getTextSize(cpuMetrics.modelName(), font, fontScale,
                               thickness, &baseline);
    cv::putText(image, cpuMetrics.modelName(),
                cv::Point(image.cols - cols + 100, offset), font, fontScale,
                {0, 127, 255}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    char cpuStr[1024];
    // sprintf(cpuStr, "CPU: %d%%", cpuMetrics.cpuUtilization());
    sprintf(cpuStr, "CPU: %d%%",
            cpuMetricsArr[frame_index] / cpuMetrics.cpuThreads());
    textSize = cv::getTextSize(std::string(cpuStr), font, fontScale, thickness,
                               &baseline);
    cv::putText(image, std::string(cpuStr),
                cv::Point(image.cols - cols + 100, offset), font, fontScale,
                {0, 127, 255}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    // for (int dix = 0; dix < gpuMetrics.deviceCount(); dix++) {
    //     char gpuStr[1024];
    //     // float val = gpuMetrics.gpuAllUtilization(dix);
    //     float val = gpuMetricsArr[frame_index];
    //     // regular user cannot fetch the gpu utilization, shown as -99.9,
    //     then we ignore it. if (val >= 0) {
    //         sprintf(gpuStr, "iGPU: %3.2f%%", val);
    //         cv::putText(image, std::string(gpuStr), cv::Point(115, offset),
    //         font, fontScale, {255, 0, 0}, thickness, cv::LINE_8); offset +=
    //         lineHeight;
    //     }
    // }

    char gpuStr[1024];
    float val = gpuMetricsArr[frame_index];
    if (val >= 0) {
      sprintf(gpuStr, "iGPU: %3.2f%%", val);
      textSize = cv::getTextSize(std::string(gpuStr), font, fontScale,
                                 thickness, &baseline);
      cv::putText(image, std::string(gpuStr),
                  cv::Point(image.cols - cols + 100, offset), font, fontScale,
                  {0, 127, 255}, thickness, cv::LINE_8);
      offset += textSize.height + baseline + lineSpace;
    }
  }
}

void renderOSDImage(cv::Mat raw_image, unsigned thread_id,
                    DisplayParams_t display_params, cv::Mat& windowImage,
                    int frame_index, MessageBuffer_t* db, Plot& pl,
                    std::string displayType, bool show_metrics = false) {
  float frame_height = raw_image.rows;
  cv::Mat plot = pl.getPlotImage();
  cv::resize(raw_image, raw_image,
             Size(plot.rows * raw_image.cols / raw_image.rows, plot.rows));
  cv::resize(plot, plot, Size(plot.cols * 2, plot.rows * 2));
  // cv::hconcat(raw_image, plot, osd_image);

  std::lock_guard<std::mutex> lg(g_window_mutex);
  raw_image.copyTo(
      windowImage(cv::Rect(thread_id % 2 * display_params.frameSize.width,
                           thread_id / 2 * display_params.frameSize.height,
                           raw_image.cols, raw_image.rows)));

  float resize_rate = static_cast<float>(frame_height / plot.rows * 2);
  int raw_image_width = raw_image.cols;
  int raw_image_height = raw_image.rows;

  parseReply(windowImage, pl, resize_rate, replyGet(db), frame_index, thread_id,
             raw_image_width, raw_image_height, displayType);

  if (show_metrics) {
    plotMetrics(windowImage, frame_index, plot.cols);
  }
}

/**
 * @brief on screen display load, to prepare show_image for each channel
 * @param data_path input file path
 * @param j thread id
 * @param dis
 */
void OSDload(const std::vector<std::string>& inputs, unsigned threadNum,
             unsigned thread_id, cv::Mat windowImage,
             DisplayParams_t display_params, MessageBuffer_t* db, Plot& pl,
             const std::string mediaType, std::string displayType,
             bool show_metrics = false, bool saveFlag = false,
             bool logoFlag = true) {
  // locate the pannel for specific thread
  cv::Rect rectFrame =
      cv::Rect(display_params.points[thread_id], display_params.frameSize);

  // query each frame
  cv::VideoWriter video;
  if (thread_id == 0 && saveFlag) {
    std::string filaPath = "./radar.avi";
    video.open(filaPath, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'), 25.0,
               cv::Size(windowImage.cols, windowImage.rows), true);
    if (!video.isOpened()) {
      cerr << "Could not open the output video file for write\n";
      return;
    }
  }
  cv::Mat logo, logoGray, mask, maskInv;
  if (logoFlag) {
    char filePath[512];
    memset(filePath, 0x00, sizeof(filePath));
    readlink("/proc/self/exe", filePath, sizeof(filePath) - 1);
    std::string path = filePath;
    size_t pos = path.rfind('/');
    std::string substr = path.substr(0, pos);
    substr.append("/../../ai_inference/test/demo/intel-logo-4C4R.png");
    logo = cv::imread(substr);
    cv::cvtColor(logo, logoGray, cv::COLOR_BGR2GRAY);
    cv::threshold(logoGray, mask, 80, 255, cv::THRESH_BINARY);
    cv::bitwise_not(mask, maskInv);
  }
  if (mediaType == "multisensor") {
    // decode images
    // need parse radar output from output node and display on birdview
    // each input should be "*.bin", and organized with sequece: [bgr, radar]
    int total_frames = inputs.size();
    for (int i = 0; i < total_frames; i++) {
      char* buffer;
      size_t length;
      readRawDataFromBinary(inputs[i], buffer, length);
      if (length == 0) {
        continue;
      }
      cv::Mat rawData(1, length, CV_8UC1, (void*)buffer);
      cv::Mat decodedImage =
          cv::imdecode(rawData, cv::ImreadModes::IMREAD_COLOR);
      // if (logoFlag) {
      //     cv::Mat roi, roiBg, roiFg, dst;
      //     roi = decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10,
      //     decodedImage.rows - logo.rows - 10, logo.cols, logo.rows));
      //     cv::bitwise_and(roi, roi, roiBg, maskInv);
      //     cv::bitwise_and(logo, logo, roiFg, mask);
      //     cv::add(roiBg, roiFg, dst);
      //     cv::addWeighted(dst, 0.5, roi, 0.5, 0,
      //                     decodedImage(cv::Rect(decodedImage.cols - logo.cols
      //                     - 10, decodedImage.rows - logo.rows - 10,
      //                     logo.cols, logo.rows)));
      // }
      std::unique_lock<std::mutex> lock(mtxFrames);
      cvFrames.wait(lock, [&] { return currentSyncFrame == i; });
      renderOSDImage(decodedImage, thread_id, display_params, windowImage, i,
                     db, pl, displayType, show_metrics);
      readyFrames++;
      if (readyFrames == threadNum) {
        readyFrames = 0;
        currentSyncFrame++;
        cvFrames.notify_all();
      } else {
        cvFrames.wait(lock, [&] { return currentSyncFrame > i; });
      }

      if (thread_id == 0 && logoFlag) {
        cv::Mat roi, roiBg, roiFg, dst;
        roi = windowImage(cv::Rect(windowImage.cols - logo.cols - 20,
                                   windowImage.rows - logo.rows - 100,
                                   logo.cols, logo.rows));
        cv::bitwise_and(roi, roi, roiBg, maskInv);
        cv::bitwise_and(logo, logo, roiFg, mask);
        cv::add(roiBg, roiFg, dst);
        cv::addWeighted(dst, 0.5, roi, 0.5, 0,
                        windowImage(cv::Rect(windowImage.cols - logo.cols - 20,
                                             windowImage.rows - logo.rows - 100,
                                             logo.cols, logo.rows)));
      }
      std::lock_guard<std::mutex> lg(g_window_mutex);
      if (thread_id == 0 && saveFlag) {
        video.write(windowImage);
      }
      delete[] buffer;
    }
  } else {
    std::cerr << "Invalid media type was parsed: " << mediaType << "!"
              << std::endl;
  }

  video.release();

  stop_display = true;
  std::cout << "Display done!" << std::endl;
}

/**
 * @brief use a seperate thread to continuously imshow()
 */
void displayload(cv::Mat windowImage) {
  while (!stop_display) {
    cv::imshow(WINDOWNAME, windowImage);
    cv::waitKey(5);

    // sleep for 30 ms
    sleep(0.03);
  }
}

int getGPUUtilization(int interval = 1) {
  try {
    std::string command = "sudo timeout 1 intel_gpu_top -l -J";
    std::thread gt(runIntelGpuTop, command, interval);

    gt.detach();
    return 0;
  } catch (std::exception const& e) {
    return -1;
  }
}

int main(int argc, char** argv) {
  try {
    // Check command line arguments.
    if (argc < 9 || argc > 14) {
      std::cerr
          << "Usage: CRSensorFusionRadarDisplay <host> <port> <json_file> "
             "<additional_json_file> <total_stream_num> <repeats> <data_path> "
             "<display_type> "
             "[<save_flag: 0 | 1>] [<pipeline_repeats>] [<cross_stream_num>] "
             "[<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]\n"
          << "Example:\n"
          << "    ./CRSensorFusion4C4RDisplay 127.0.0.1 50052 "
             "../../ai_inference/test/configs/raddet/4C4R/"
             "localFusionPipeline.json "
             "../../ai_inference/test/configs/raddet/4C4R/"
             "localFusionPipeline_npu.json 4 1 "
             "/path-to-dataset media_fusion \n"
          << "Or:\n"
          << "    ./CRSensorFusion4C4RDisplay 127.0.0.1 50052 "
             "../../ai_inference/test/configs/raddet/4C4R/"
             "localFusionPipeline.json "
             "../../ai_inference/test/configs/raddet/4C4R/"
             "localFusionPipeline_npu.json 4 1 "
             "/path-to-dataset media \n"
          << "-----------------------------------------------------------------"
             "--------------- \n"
          << "Environment requirement:\n"
          << "   unset http_proxy;unset https_proxy;unset HTTP_PROXY;unset "
             "HTTPS_PROXY   \n"
          << std::endl;
      return EXIT_FAILURE;
    }
    std::string host(argv[1]);
    std::string port(argv[2]);
    std::string jsonFile(argv[3]);
    std::string additionalJsonFile(argv[4]);
    unsigned totalStreamNum(atoi(argv[5]));
    unsigned repeats = atoi(argv[6]);
    std::string dataPath(argv[7]);
    std::string displayType(argv[8]);
    HVA_DEBUG("displayType: %s", displayType);
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
      std::cerr
          << "total-stream-number should be no less than cross-stream-number!"
          << std::endl;
      return EXIT_FAILURE;
    }
    if (totalStreamNum / crossStreamNum * crossStreamNum != totalStreamNum) {
      std::cerr
          << "total-stream-number should be divisible by cross-stream-number!"
          << std::endl;
      return EXIT_FAILURE;
    }

    unsigned threadNum = totalStreamNum / crossStreamNum;
    if (warmupFlag) {
      std::cout << "Warmup workloads with " << threadNum << " threads..."
                << std::endl;
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

    std::string additionalContents;
    std::ifstream inFile(additionalJsonFile, std::ios::in);
    if (inFile) {
      inFile.seekg(0, std::ios::end);
      additionalContents.resize(inFile.tellg());
      inFile.seekg(0, std::ios::beg);
      inFile.read(&additionalContents[0], additionalContents.size());
      inFile.close();
    }
    int datarepeats = repeats;
    // data repeat in pipeline
    if (contents.find("data_repeats_placeholder") != std::string::npos) {
      std::cout << "support data repeats" << std::endl;
      contents =
          std::regex_replace(contents, std::regex("data_repeats_placeholder"),
                             std::to_string(datarepeats));
    }
    std::cout << contents << std::endl;
    if (additionalContents.find("data_repeats_placeholder") !=
        std::string::npos) {
      std::cout << "support data repeats" << std::endl;
      additionalContents = std::regex_replace(
          additionalContents, std::regex("data_repeats_placeholder"),
          std::to_string(datarepeats));
    }
    std::cout << additionalContents << std::endl;
    std::vector<std::thread> vThs;
    std::vector<std::thread> dThs;
    std::thread displayThread;

    if ("media" != displayType && "radar" != displayType &&
        "media_radar" != displayType && "media_fusion" != displayType) {
      cerr << "wrong display type(only support media, radar, media_radar, "
              "media_fusion)."
           << std::endl;
      return EXIT_FAILURE;
    }

    // ---------------------------------------------------------------------------
    //                                 warm up workloads
    //  ---------------------------------------------------------------------------
    // if (warmupFlag) {
    //     std::cout << "Warmup workloads with " << threadNum << " threads..."
    //     << std::endl;
    //     std::chrono::time_point<std::chrono::high_resolution_clock> a, b;
    //     a = std::chrono::high_resolution_clock::now();
    //     for (unsigned i = 0; i < threadNum; ++i) {
    //         if (threadNum - 1 == i) {
    //             std::thread t(warmup, std::ref(host), std::ref(port),
    //             std::ref(additionalContents)); vThs.push_back(std::move(t));
    //         }
    //         else {
    //             std::thread t(warmup, std::ref(host), std::ref(port),
    //             std::ref(contents)); vThs.push_back(std::move(t));
    //         }
    //     }
    //     for (auto &item : vThs) {
    //         item.join();
    //     }
    //     b = std::chrono::high_resolution_clock::now();
    //     auto warmupTime =
    //     std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count();
    //     std::cout << "Warmup done, time: " << warmupTime << " ms" <<
    //     std::endl;
    // }

    // ---------------------------------------------------------------------------
    //                                 init cpu/gpu metrics
    //  ---------------------------------------------------------------------------
    std::cout << "Initialize system metrics for cpu and gpu..." << std::endl;
    // if (SHOWGPUMETRIC)
    //     gpuMetrics.init();
    // get metrics for specific process
    cpuMetrics.init("HceAILLInfServe");  // statistic only HceAIInfServe process
    stop_metrics = false;

    // ---------------------------------------------------------------------------
    //                                 init display
    //  ---------------------------------------------------------------------------
    Plot pl(-50.0, 50.0, -30.0, 30.0, 0.1, 5.0);
    vector<Point2f> footprint;
    footprint.push_back(Point2f(0.2, 0.2));
    footprint.push_back(Point2f(0.2, -0.2));
    footprint.push_back(Point2f(-0.2, -0.2));
    footprint.push_back(Point2f(-0.2, 0.2));

    // pl.drawBirdViewFOV();
    pl.drawFootprint(footprint);

    std::cout << "Initialize display load..." << std::endl;
    FusionType_t fusionType = FusionType_t::FUSION_4C4R;
    DisplayParams_t params =
        prepareDisplayParams(fusionType, threadNum, WINDOWNAME, pl);
    int pannels = params.count;
    cv::Mat windowImage = cv::Mat::zeros(params.mediaFusionSize, CV_8UC3);
    for (size_t j = 0; j < pannels; j++) {
      cv::Rect rectFrame = cv::Rect(params.points[j], params.frameSize);
      cv::putText(windowImage, "Loading...",
                  cv::Point(rectFrame.x + rectFrame.width / 2,
                            rectFrame.y + rectFrame.height / 5),
                  cv::FONT_HERSHEY_SIMPLEX, 1, {0, 255, 0}, 2, cv::LINE_8);
    }
    stop_display = false;

    // ---------------------------------------------------------------------------
    //                                 processing
    //  ---------------------------------------------------------------------------
    std::cout << "Start processing with " << threadNum
              << " threads: total-stream = " << totalStreamNum
              << ", each thread will process " << crossStreamNum << " streams"
              << std::endl;

    vThs.clear();
    dThs.clear();
    std::vector<std::string> inputs;  // paths of input bin files
    std::string mediaType;
    parseInputs(dataPath, inputs, mediaType);

    struct MessageBuffer_t msg_buffer[threadNum];
    for (unsigned i = 0; i < threadNum; ++i) {
      initMessageBuffer(&msg_buffer[i]);
      if (threadNum - 1 == i) {
        std::thread t(workload, std::ref(host), std::ref(port),
                      std::ref(additionalContents), std::ref(inputs), repeats,
                      &msg_buffer[i], i, crossStreamNum, pipeline_repeats,
                      warmupFlag);
        vThs.push_back(std::move(t));
      } else {
        std::thread t(workload, std::ref(host), std::ref(port),
                      std::ref(contents), std::ref(inputs), repeats,
                      &msg_buffer[i], i, crossStreamNum, pipeline_repeats,
                      warmupFlag);
        vThs.push_back(std::move(t));
      }
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
    std::vector<std::string> pipeline_repeatinputs;
    for (unsigned i = 0; i < pipeline_repeats; ++i) {
      pipeline_repeatinputs.insert(pipeline_repeatinputs.end(),
                                   repeatinputs.begin(), repeatinputs.end());
    }
    // continuously update OSD on windowImage
    for (unsigned j = 0; j < threadNum; ++j) {
      bool showMetrics = j == 0;
      std::thread d(OSDload, std::ref(pipeline_repeatinputs), threadNum, j,
                    windowImage, params, &msg_buffer[j], std::ref(pl),
                    mediaType, displayType, showMetrics, saveFlag, logoFlag);
      dThs.push_back(std::move(d));
    }

    for (auto& item : vThs) {
      item.join();
    }

    for (auto& item : dThs) {
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
      std::cout << g_frameCnt[tix] << "frames," << g_total[tix] << " ms"
                << std::endl;
      totalTime += g_total[tix];
      totalFrames += g_frameCnt[tix];
    }
    std::cout << "Total time: " << totalTime << " ms" << std::endl;

    float totalRequests = (float)threadNum * pipeline_repeats;
    float mean =
        totalTime /
        g_total.size();  // mean time for each thread (include all repeats)
    std::cout << "Mean time: " << mean << " ms" << std::endl;
    // float qps = totalRequests / (mean / 1000.0);
    // std::cout << "\n qps: " << qps << std::endl;
    // std::cout << "\n qps per stream: " << qps / totalStreamNum << std::endl;

    /* frames_each_stream / time_each_stream => fps_each_stream */
    float fps = (((float)totalFrames - pipeline_repeats) / totalStreamNum) /
                (mean / 1000.0);
    double latency_sum =
        std::accumulate(std::begin(g_latency), std::end(g_latency), 0.0);
    double latency_ave = latency_sum / g_latency.size();
    double inference_latency_ave = 0.0;
    double video_latency_ave = 0.0;
    if (g_inference_latency.size() > 0) {
      double inference_latency_sum = std::accumulate(
          std::begin(g_inference_latency), std::end(g_inference_latency), 0.0);
      inference_latency_ave =
          inference_latency_sum / g_inference_latency.size();
    }
    if (g_video_latency.size() > 0) {
      double video_latency_sum = std::accumulate(
          std::begin(g_video_latency), std::end(g_video_latency), 0.0);
      video_latency_ave = video_latency_sum / g_video_latency.size();
    }

    std::cout << "\n=================================================\n"
              << std::endl;
    std::cout << "WARMUP: " << std::to_string(warmupFlag) << std::endl;
    std::cout << "fps: " << fps << std::endl;
    std::cout << "average latency " << latency_ave << std::endl;
    std::cout << "video pipeline average latency " << video_latency_ave
              << std::endl;
    std::cout << "inference average latency " << inference_latency_ave
              << std::endl;
    std::cout << "For each repeat: " << threadNum
              << " threads have been processed, total-stream = "
              << totalStreamNum << ", each thread processed " << crossStreamNum
              << " streams" << std::endl;
    std::cout << "fps per stream: " << fps << ", including " << totalFrames
              << " frames" << std::endl;

    std::cout << "\n=================================================\n"
              << std::endl;

    return 0;
  } catch (std::exception const& e) {
    std::cerr << "Error: " << e.what() << std::endl;
    return EXIT_FAILURE;
  }

  return EXIT_SUCCESS;
}

/** reply_msg example:
frame index: 298:
{
    "status_code": "0",
    "description": "succeeded",
    "roi_info": [
        {
            "roi": [
                "268",
                "0",
                "319",
                "249"
            ],
            "feature_vector": "",
            "roi_class": "vehicle",
            "roi_score": "0.99979513883590698",
            "track_id": "4",
            "track_status": "TRACKED",
            "attribute": {
                "color": "",
                "color_score": "0",
                "type": "",
                "type_score": "0"
            }
        },
        {
            "roi": [
                "663",
                "110",
                "905",
                "960"
            ],
            "feature_vector": "",
            "roi_class": "vehicle",
            "roi_score": "0.93957972526550293",
            "track_id": "3",
            "track_status": "TRACKED",
            "attribute": {
                "color": "",
                "color_score": "0",
                "type": "",
                "type_score": "0"
            }
        }
    ]
}
*/
