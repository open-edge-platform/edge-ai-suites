/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023-2024 Intel Corporation.
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
#include "modules/inference_util/radar/radar_tracking_helper.hpp"
#include "modules/visualization/Plot.h"
#include "utils/displayUtils.hpp"
#include "utils/sys_metrics/cpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_metrics_warpper.hpp"
#include "utils/testUtils.hpp"

using namespace hce::ai::inference;

#define SHOWGPUMETRIC true

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
std::vector<float> g_latency;
std::mutex g_mutex;

// system metrics
GPUMetrics gpuMetrics;
CPUMetrics cpuMetrics;
std::atomic_bool stop_metrics;

// display controller
std::atomic_bool stop_display;

std::mutex g_window_mutex;
static const string WINDOWNAME = "Camera + Radar Sensor Fusion";
std::vector<int> cpuMetricsArr;
std::vector<float> gpuMetricsArr;
std::vector<float> timeArr;

/**
 * @brief parse input local file
 */
void parseInputs(const std::string data_path, std::vector<std::string>& inputs,
                 std::string& mediaType) {
  if (boost::filesystem::exists(data_path)) {
    if (boost::filesystem::is_directory(data_path)) {
      // use case:
      // multi-sensor inputs, organized as [bgr, radar, depth]

      if (!checkIsFolder(data_path)) {
        HVA_ERROR("path should be valid folder: %s", data_path.c_str());
        HVA_ASSERT(false);
      }

      std::vector<std::string> bgrInputs;
      getAllFiles(data_path + "/bgr", bgrInputs, ".bin");
      std::vector<std::string> radarInputs;
      getAllFiles(data_path + "/radar", radarInputs, ".bin");

      if (bgrInputs.size() != radarInputs.size()) {
        HVA_ERROR(
            "each sensor input should have equal sizes, but got bgr: %d, "
            "radar: %d",
            bgrInputs.size(), radarInputs.size());
        HVA_ASSERT(false);
      }
      std::string path;
      // insert aligned sensor data by sequence
      for (int i = 0; i < radarInputs.size(); i++) {
        path = parseAbsolutePath(bgrInputs[i]);
        inputs.push_back(path);
        path = parseAbsolutePath(radarInputs[i]);
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

      // example for processing NV12 binary data
      // cv::Mat nv12Image = cv::Mat(height * 3/2, width, CV_8UC1,
      // (void*)binaryData.c_str()); cv::Mat bgrImage; cv::cvtColor(nv12Image,
      // bgrImage, cv::COLOR_YUV2BGR_NV12); std::string snapshotSavePath =
      // "/home/intel/jiaojiao/debug/" + std::to_string(frameId) + ".jpg";
      // std::cout << "saving images to: " << snapshotSavePath <<
      //             ", height: " << bgrImage.rows << ", width: " <<
      //             bgrImage.cols << std::endl;
      // cv::imwrite(snapshotSavePath, bgrImage);
    }
  }
}

void workload(const std::string& host, const std::string& port,
              const std::string& json,
              const std::vector<std::string>& mediaVector, unsigned repeats,
              MessageBuffer_t* pb, unsigned thread_id, unsigned stream_num,
              bool warmup_flag) {
  GRPCClient client{host, port};

  std::chrono::time_point<std::chrono::high_resolution_clock> request_sent,
      response_received;
  std::chrono::milliseconds timeUsed(0);
  std::chrono::milliseconds thisTime(0);
  std::size_t frameCnt(0);
  bool isFirst = true;

  std::vector<std::string> inputs;
  // repeat input media for `stream_num` times
  for (unsigned i = 0; i < stream_num; i++) {
    inputs.insert(inputs.end(), mediaVector.begin(), mediaVector.end());
  }
  std::string info = "[thread " + std::to_string(thread_id) +
                     "] Input media size is: " + std::to_string(inputs.size());
  std::cout << info << std::endl;

  std::shared_ptr<hce_ai::ai_inference::Stub> stub = client.connect();
  size_t job_handle = 0;
  for (unsigned i = 0; i < repeats; ++i) {
    grpc::ClientContext context;
    std::shared_ptr<
        grpc::ClientReaderWriter<hce_ai::AI_Request, hce_ai::AI_Response>>
        stream(stub->Run(&context));

    if (warmup_flag) {
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
          std::cout << ", thread " << thread_id << ", latency: " << duration
                    << "ms" << std::endl;
          // g_latency.push_back(duration);
          isFirst = false;
        }

        reply_status = reply.status();
        std::cout << "frame index: " << frameCnt
                  << ", reply_status: " << reply_status << std::endl;
        std::cout << msg << std::endl;

        frameCnt += 1;
        float curFPS = frameCnt * 1000.0 / duration;
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
        response_received - request_sent);
    timeUsed = thisTime + timeUsed;

    // std::cout << reply_msg << std::endl;
    std::cout << "request done with " << frameCnt << "frames" << std::endl;
  }

  std::lock_guard<std::mutex> lg(g_mutex);
  g_total.push_back(timeUsed.count());
  g_frameCnt.push_back(frameCnt);
}
void parsePCL(cv::Mat& frame, Plot& pl, float resize_rate, std::string imsg,
              int frameCnt, std::string display_type) {
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

  vector<float> rangeFloats;
  vector<float> aoaVars;
  vector<cv::Point2f> pointsAll;

  if (jsonTree.count("num") > 0) {
    // roi_all.clear();
    boost::property_tree::ptree roi_info = jsonTree.get_child("pcl");
    // car_count = roi_info.size();
    for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
      // bool isAssociated = false;
      auto roi_item = roi_i->second;

      float rangeFloat = roi_item.get<float>("rangeFloat");
      float aoa = roi_item.get<float>("aoaVar");
      // std::cout<<"rangeFloat: "<<rangeFloat<<" aoa: "<<aoa<<std::endl;
      rangeFloats.push_back(rangeFloat);
      aoaVars.push_back(aoa);

      float x = rangeFloat * cos(aoa * M_PI / 180);
      float y = rangeFloat * sin(aoa * M_PI / 180);
      pointsAll.push_back(cv::Point2f(x, -y));
    }
  }

  // std::cout<<"points number: "<<point_all.size()<<std::endl;

  pl.clear();
  pl.drawPoints(pointsAll, cv::Scalar{0, 255, 0}, 3, true);

  cv::Mat plot = pl.getPlotImage();
  plot.copyTo(frame(cv::Rect(frame.cols - plot.cols, 0, plot.cols, plot.rows)));

  // // }
  // // show FPS
  // cv::putText(frame, "FPS: " + ifps, cv::Point(frame.cols - 100, 20),
  // cv::FONT_HERSHEY_SIMPLEX, 0.5, {0, 255, 0}, 1, cv::LINE_8);
  // cv::putText(frame, "FrameCnt: " + to_string(frameCnt), cv::Point(frame.cols
  // - 130, 40), cv::FONT_HERSHEY_SIMPLEX, 0.5, {0, 255, 0}, 1, cv::LINE_8);
}
void parseClustering(cv::Mat& frame, Plot& pl, float resize_rate,
                     std::string imsg, int frameCnt, std::string display_type) {
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

  vector<float> xCenters;
  vector<float> yCenters;
  vector<cv::Point2f> pointsAll;
  vector<float> vxs;
  vector<float> vys;

  if (jsonTree.count("num") > 0) {
    // roi_all.clear();
    boost::property_tree::ptree roi_info = jsonTree.get_child("clusters");

    for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
      auto roi_item = roi_i->second;

      float xCenter = roi_item.get<float>("xCenter");
      float yCenter = roi_item.get<float>("yCenter");

      float avgVel = roi_item.get<float>("avgVel");
      // float azimuth = atan(xCenter/yCenter);
      float azimuth, vx, vy;

      avgVel = -avgVel;
      // image coordinates
      float x = xCenter;
      float y = -yCenter;
      azimuth = atan2(y, x);
      vx = avgVel * cos(azimuth);
      vy = avgVel * sin(azimuth);
      // vy =-vy;
      xCenters.push_back(xCenter);
      yCenters.push_back(yCenter);

      pointsAll.push_back(cv::Point2f(x, y));
      vxs.push_back(vx);
      vys.push_back(vy);

      // std::cout<<"x: "<<x<<" y: "<<y<<" vx: "<<vx<<" vy: "<<vy<<std::endl;
    }
  }

  // std::cout<<"points number: "<<point_all.size()<<std::endl;

  pl.clear();
  pl.drawPoints(pointsAll, cv::Scalar{0, 255, 0}, 3, true);

  // draw speed of pointsALl
  for (auto i = 0; i < pointsAll.size(); i++) {
    cv::Scalar speed_color = cv::Scalar{64, 224, 205};
    pl.drawSpeed(pointsAll[i], vxs[i], vys[i], speed_color, 1);
  }

  cv::Mat plot = pl.getPlotImage();
  plot.copyTo(frame(cv::Rect(frame.cols - plot.cols, 0, plot.cols, plot.rows)));
}
void parseReply(cv::Mat& frame, Plot& pl, float resize_rate, std::string imsg,
                int frameCnt, std::string display_type) {
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

  if (jsonTree.count("roi_info") > 0) {
    roi_all.clear();
    boost::property_tree::ptree roi_info = jsonTree.get_child("roi_info");
    car_count = roi_info.size();
    for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
      bool isAssociated = false;
      auto roi_item = roi_i->second;

      // if ("media" != display_type) {
      boost::property_tree::ptree radar_roi =
          roi_item.get_child("fusion_roi_state");
      radar_roi_arr.clear();
      for (auto roi_j = radar_roi.begin(); roi_j != radar_roi.end(); ++roi_j) {
        // if (fabs(roi_j->second.get_value<float>()) < 1e-6)
        //     continue;
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
      if (radar_x != 0 && radar_y != 0 && vx != 0 && vy != 0 && xSize != 0 &&
          ySize != 0) {
        xSize = 4.2;
        ySize = 1.7;

        radar_y = -radar_y;
        vy = -vy;

        // std::cout<<"radar_x: "<<radar_x<<" radar_y: "<<radar_y<<" vx:
        // "<<vx<<" vy: "<<vy<<std::endl;

        std::vector<cv::Point2f> points(5);
        // radar_x, radar_y are the center coordinates of the rectangle
        // (points[0])-------(points[1])
        //     |                  |
        //     |   (points[4])    |
        //     |                  |
        // (points[3])-------(points[2])

        points[0] = cv::Point2f(radar_x + xSize / 2, radar_y - ySize / 2);
        points[1] = cv::Point2f(radar_x + xSize / 2, radar_y + ySize / 2);
        points[2] = cv::Point2f(radar_x - xSize / 2, radar_y + ySize / 2);
        points[3] = cv::Point2f(radar_x - xSize / 2, radar_y - ySize / 2);
        points[4] = cv::Point2f(radar_x, radar_y);

        vx_all.push_back(vx);
        vy_all.push_back(vy);
        roi_all.push_back(points);

        // point_all.push_back(cv::Point2f(radar_x + xSize, radar_y + ySize));
        point_all.push_back(cv::Point2f(radar_x, radar_y));
      }
    }
  }

  // std::cout<<"points number: "<<point_all.size()<<std::endl;

  pl.clear();
  pl.drawRadarResults(roi_all, vx_all, vy_all, cv::Scalar{0, 255, 0}, 1, true);
  // pl.drawPoints(point_all, cv::Scalar{255, 0, 0}, 3, true);

  cv::Mat plot = pl.getPlotImage();
  plot.copyTo(frame(cv::Rect(frame.cols - plot.cols, 0, plot.cols, plot.rows)));

  // }
  // show FPS
  cv::putText(frame, "FPS: " + ifps, cv::Point(frame.cols - 100, 20),
              cv::FONT_HERSHEY_SIMPLEX, 0.5, {0, 255, 0}, 1, cv::LINE_8);
  cv::putText(frame, "FrameCnt: " + to_string(frameCnt),
              cv::Point(frame.cols - 130, 40), cv::FONT_HERSHEY_SIMPLEX, 0.5,
              {0, 255, 0}, 1, cv::LINE_8);
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
void plotMetrics(cv::Mat& image, int frame_index) {
  if (!stop_metrics) {
    // style
    int offset = 20;
    auto font = cv::FONT_HERSHEY_SIMPLEX;
    float fontScale = 0.5;
    float thickness = 1;
    int baseline = 0;
    int lineHeight = 20;

    //
    // show metrics
    //
    // cv::putText(image, cpuMetrics.modelName(), cv::Point(50, offset), font,
    // fontScale, {255, 0, 0}, thickness, cv::LINE_8);
    cv::putText(image, cpuMetrics.modelName(), cv::Point(50, offset), font,
                fontScale, {255, 0, 0}, thickness, cv::LINE_8);
    offset += lineHeight;

    char cpuStr[1024];
    // sprintf(cpuStr, "CPU: %d%%", cpuMetrics.cpuUtilization());
    sprintf(cpuStr, "CPU: %d%%",
            cpuMetricsArr[frame_index] / cpuMetrics.cpuThreads());
    cv::putText(image, std::string(cpuStr), cv::Point(115, offset), font,
                fontScale, {255, 0, 0}, thickness, cv::LINE_8);
    offset += lineHeight;

    for (int dix = 0; dix < gpuMetrics.deviceCount(); dix++) {
      char gpuStr[1024];
      // float val = gpuMetrics.gpuAllUtilization(dix);
      float val = gpuMetricsArr[frame_index];
      // regular user cannot fetch the gpu utilization, shown as -99.9, then we
      // ignore it.
      if (val >= 0) {
        sprintf(gpuStr, "iGPU: %3.2f%%", val);
        cv::putText(image, std::string(gpuStr), cv::Point(115, offset), font,
                    fontScale, {255, 0, 0}, thickness, cv::LINE_8);
        offset += lineHeight;
      }
    }

    cv::putText(image, "NN Model: YOLOX-S", cv::Point(50, offset), font,
                fontScale, {255, 0, 0}, thickness, cv::LINE_8);
    offset += lineHeight;
    cv::putText(image, "Intel oneMKL (2025.1.0)", cv::Point(50, offset), font,
                fontScale, {255, 0, 0}, thickness, cv::LINE_8);
    offset += lineHeight;
    cv::putText(image, "Intel Distribution of OpenVINO (2025.2.0)",
                cv::Point(50, offset), font, fontScale, {255, 0, 0}, thickness,
                cv::LINE_8);
  }
}

void renderOSDImage(cv::Mat raw_image, cv::Mat& osd_image, int frame_index,
                    std::string display_type, MessageBuffer_t* db, Plot& pl,
                    bool show_metrics = false) {
  float frame_height = raw_image.rows;
  cv::Mat plot = pl.getPlotImage();
  cv::resize(raw_image, raw_image,
             Size(plot.rows * raw_image.cols / raw_image.rows, plot.rows));
  cv::hconcat(raw_image, plot, osd_image);

  float resize_rate = static_cast<float>(frame_height / plot.rows);
  if (display_type == "tracking") {
    parseReply(osd_image, pl, resize_rate, replyGet(db), frame_index,
               display_type);
  } else if (display_type == "pcl") {
    parsePCL(osd_image, pl, resize_rate, replyGet(db), frame_index,
             display_type);
  } else if (display_type == "clustering") {
    parseClustering(osd_image, pl, resize_rate, replyGet(db), frame_index,
                    display_type);
  }

  // if (show_metrics) {
  //     plotMetrics(osd_image, frame_index);
  // }
}

/**
 * @brief on screen display load, to prepare show_image for each channel
 * @param data_path input file path
 * @param j thread id
 * @param dis
 */
void OSDload(const std::vector<std::string>& inputs, unsigned thread_id,
             std::string display_type, cv::Mat windowImage,
             DisplayParams_t display_params, MessageBuffer_t* db, Plot& pl,
             const std::string mediaType, bool show_metrics = false,
             bool saveFlag = false, bool logoFlag = true) {
  // locate the pannel for specific thread
  cv::Rect rectFrame =
      cv::Rect(display_params.points[thread_id], display_params.frameSize);

  // query each frame
  cv::VideoWriter video;
  if (saveFlag) {
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
    substr.append("/../../ai_inference/test/demo/logo.png");
    logo = cv::imread(substr);
    cv::cvtColor(logo, logoGray, cv::COLOR_BGR2GRAY);
    cv::threshold(logoGray, mask, 125, 255, cv::THRESH_BINARY);
    cv::bitwise_not(mask, maskInv);
  }
  if (mediaType == "multisensor") {
    // decode images
    // need parse radar output from output node and display on birdview
    // each input should be "*.bin", and organized with sequece: [bgr, radar]
    int total_frames = inputs.size() / 2;
    for (int i = 0; i < total_frames; i++) {
      char* buffer;
      size_t length;
      readRawDataFromBinary(inputs[i * 2], buffer, length);
      if (length == 0) {
        continue;
      }
      cv::Mat rawData(1, length, CV_8UC1, (void*)buffer);
      cv::Mat decodedImage =
          cv::imdecode(rawData, cv::ImreadModes::IMREAD_COLOR);
      if (logoFlag) {
        cv::Mat roi, roiBg, roiFg, dst;
        roi = decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10,
                                    decodedImage.rows - logo.rows - 10,
                                    logo.cols, logo.rows));
        cv::bitwise_and(roi, roi, roiBg, maskInv);
        cv::bitwise_and(logo, logo, roiFg, mask);
        cv::add(roiBg, roiFg, dst);
        cv::addWeighted(
            dst, 0.5, roi, 0.5, 0,
            decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10,
                                  decodedImage.rows - logo.rows - 10, logo.cols,
                                  logo.rows)));
      }

      cv::Mat osd_image;
      renderOSDImage(decodedImage, osd_image, i, display_type, db, pl,
                     show_metrics);
      std::lock_guard<std::mutex> lg(g_window_mutex);
      osd_image.copyTo(windowImage);

      if (saveFlag) {
        video.write(osd_image);
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

    // sleep for 33 ms
    sleep(0.03);
  }
}

int main(int argc, char** argv) {
  try {
    // Check command line arguments.
    if (argc != 8 && argc != 9 && argc != 10) {
      std::cerr << "Usage: CRSensorFusionRadarDisplay <host> <port> "
                   "<json_file> <total_stream_num> <repeats> <data_path> "
                   "<media_type> [<cross_stream_num>] [<warmup_flag: 0 | 1>]\n"
                << "Example:\n"
                << "    ./CRSensorFusionRadarDisplay 127.0.0.1 50052 "
                   "../../ai_inference/test/configs/raddet/"
                   "localRadarPipeline_savepcl.json 1 1 /path/to/dataset pcl \n"
                << "Or:\n"
                << "    ./CRSensorFusionRadarDisplay 127.0.0.1 50052 "
                   "../../ai_inference/test/configs/raddet/"
                   "localRadarPipeline_saveClustering.json 1 1 "
                   "/path/to/dataset clustering \n"
                << "Or:\n"
                << "    ./CRSensorFusionRadarDisplay 127.0.0.1 50052 "
                   "../../ai_inference/test/configs/raddet/"
                   "localRadarPipeline.json 1 1 /path/to/dataset tracking \n"
                << "-----------------------------------------------------------"
                   "--------------------- \n"
                << "Environment requirement:\n"
                << "   unset http_proxy;unset https_proxy;unset "
                   "HTTP_PROXY;unset HTTPS_PROXY   \n"
                << std::endl;
      return EXIT_FAILURE;
    }
    std::string host(argv[1]);
    std::string port(argv[2]);
    std::string jsonFile(argv[3]);
    unsigned totalStreamNum(atoi(argv[4]));
    unsigned repeats = atoi(argv[5]);
    std::string dataPath(argv[6]);
    // std::string mediaType(argv[7]);
    std::string displayType(argv[7]);
    HVA_DEBUG("displayType: %s", displayType);
    HVA_DEBUG("dataPath: %s", dataPath.c_str());
    bool saveFlag = true;
    bool logoFlag = true;

    // optional args
    unsigned crossStreamNum = 1;
    bool warmupFlag = true;
    if (argc >= 9) {
      crossStreamNum = atoi(argv[8]);
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
      if (argc == 10) {
        warmupFlag = bool(atoi(argv[9]));
      }
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

    std::vector<std::thread> vThs;
    std::vector<std::thread> dThs;
    std::thread displayThread;

    if ("tracking" != displayType && "pcl" != displayType &&
        "clustering" != displayType) {
      cerr << "wrong display type(only support tracking, pcl, clustering)."
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
    //     for(unsigned i =0; i < threadNum; ++i){
    //         std::thread t(warmup, std::ref(host), std::ref(port),
    //         std::ref(contents)); vThs.push_back(std::move(t));
    //     }
    //     for(auto& item: vThs){
    //         item.join();
    //     }
    //     b = std::chrono::high_resolution_clock::now();
    //     auto warmupTime =
    //     std::chrono::duration_cast<std::chrono::milliseconds>(b - a).count();
    //     std::cout << "Warmup done, time: "<< warmupTime << " ms"<< std::endl;
    // }

    // ---------------------------------------------------------------------------
    //                                 init cpu/gpu metrics
    //  ---------------------------------------------------------------------------
    std::cout << "Initialize system metrics for cpu and gpu..." << std::endl;
    if (SHOWGPUMETRIC) gpuMetrics.init();
    // get metrics for specific process
    cpuMetrics.init("HceAILLInfServe");  // statistic only HceAIInfServe process
    // cpuMetrics.init(); // statistics all cpu usage
    stop_metrics = false;

    // ---------------------------------------------------------------------------
    //                                 init display
    //  ---------------------------------------------------------------------------
    Plot pl(0.0, 50.0, -30.0, 30.0, 0.1, 5.0);
    vector<Point2f> footprint;
    footprint.push_back(Point2f(0.2, 0.2));
    footprint.push_back(Point2f(0.2, -0.2));
    footprint.push_back(Point2f(-0.2, -0.2));
    footprint.push_back(Point2f(-0.2, 0.2));

    pl.drawFootprint(footprint);

    std::cout << "Initialize display load..." << std::endl;
    FusionType_t fusionType = FusionType_t::FUSION_1C1R;
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
      std::thread t(workload, std::ref(host), std::ref(port),
                    std::ref(contents), std::ref(inputs), repeats,
                    &msg_buffer[i], i, crossStreamNum, warmupFlag);
      vThs.push_back(std::move(t));
    }

    // // TODO: enable AI Inference
    // for(unsigned i = 0; i < threadNum; ++i){
    //     initMessageBuffer(&msg_buffer[i]);
    //     std::thread t(workload, std::ref(host), std::ref(port),
    //     std::ref(contents), std::ref(inputs), i, &msg_buffer[i], fpsWindow);
    //     //workload for ai inference vThs.push_back(std::move(t));
    // }
    sleep(2);

    // start to display
    displayThread = std::thread(displayload, std::ref(windowImage));
    std::vector<std::string> repeatinputs;
    for (unsigned i = 0; i < repeats; ++i) {
      repeatinputs.insert(repeatinputs.end(), inputs.begin(), inputs.end());
    }
    // TODO: continuously update OSD on windowImage
    for (unsigned j = 0; j < threadNum; ++j) {
      bool showMetrics = j == 0;
      std::thread d(OSDload, std::ref(repeatinputs), j, displayType,
                    windowImage, params, &msg_buffer[j], std::ref(pl),
                    mediaType, showMetrics, saveFlag, logoFlag);
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

    float totalRequests = (float)threadNum * repeats;
    float mean =
        totalTime /
        g_total.size();  // mean time for each thread (include all repeats)
    std::cout << "Mean time: " << mean << " ms" << std::endl;
    // float qps = totalRequests / (mean / 1000.0);
    // std::cout << "\n qps: " << qps << std::endl;
    // std::cout << "\n qps per stream: " << qps / totalStreamNum << std::endl;

    /* frames_each_stream / time_each_stream => fps_each_stream */
    float fps = ((float)totalFrames / totalStreamNum) / (mean / 1000.0);
    std::cout << "\n=================================================\n"
              << std::endl;
    std::cout << "WARMUP: " << std::to_string(warmupFlag) << std::endl;
    std::cout << "fps: " << fps << std::endl;
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
