/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include <iostream>
#include <sys/timeb.h>
#include <chrono>
#include <mutex>
#include <boost/property_tree/json_parser.hpp>

#include "utils/testUtils.hpp"
#include "low_latency_client/grpcClient.hpp"

#include "low_latency_client/grpcClient.hpp"
#include "utils/sys_metrics/cpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_monitor.h"
#include "math.h"

using namespace hce::ai::inference;

#define SHOWGPUMETRIC true

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
std::mutex g_mutex;
double g_latency_sum = 0;
int64_t g_latency_count = 0;

double g_inference_latency_sum = 0;
int64_t g_inference_latency_count = 0;

double g_video_latency_sum = 0;
int64_t g_video_latency_count = 0;

double g_lidar_latency_sum = 0;
int64_t g_lidar_latency_count = 0;

double g_latency_min = 10000;
double g_latency_max = 0;
double g_inference_latency_min = 10000;
double g_inference_latency_max = 0;
double g_video_latency_min = 10000;
double g_video_latency_max = 0;
double g_lidar_latency_min = 10000;
double g_lidar_latency_max = 0;

// system metrics
// GPUMetrics gpuMetrics;
CPUMetrics cpuMetrics;
std::atomic_bool stop_metrics;

void workload(const std::string &host,
              const std::string &port,
              const std::string &json,
              const std::string &data_path,
              unsigned repeats,
              const std::string &media_type,
              unsigned thread_id,
              unsigned stream_num,
              bool warmup_flag,
              unsigned pipeline_repeats,
              const std::string reportFileName)
{
    GRPCClient client{host, std::to_string(std::stoi(port) + thread_id)};

    std::chrono::time_point<std::chrono::high_resolution_clock> request_sent, first_response_received, response_received;
    std::chrono::milliseconds timeUsed(0);
    std::chrono::milliseconds thisTime(0);
    std::size_t frameCnt(0);

    std::vector<std::string> mediaVector;
    if (media_type == "media") {
        // use case:
        // traverse image folder as inputs

        if (!checkIsFolder(data_path)) {
            HVA_ERROR("path should be valid folder: %s", data_path.c_str());
            HVA_ASSERT(false);
        }

        getAllFiles(data_path + "/image_2", mediaVector, ".bin");
        std::sort(mediaVector.begin(), mediaVector.end());

        std::cout << "Load " << mediaVector.size() << " files from folder: " << data_path.c_str() << std::endl;
    }
    else if (media_type == "multisensor") {
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
            mediaVector.push_back(path);
            path = parseAbsolutePath(lidarInputs[i]);
            mediaVector.push_back(path);
            path = parseAbsolutePath(calibInputs[i]);
            mediaVector.push_back(path);
        }
        std::cout << "Load " << mediaVector.size() << " files from folder: " << data_path.c_str() << std::endl;
    }
    else {
        std::cerr << "testGRPCCPlusLPipeline receive unknow media type: " << media_type.c_str() << std::endl;
        HVA_ASSERT(false);
    }

    // std::vector<std::string> inputs;
    // // repeat input media for `stream_num` times
    // for (unsigned i = 0; i < stream_num; i ++) {
    //     inputs.insert(inputs.end(), mediaVector.begin(), mediaVector.end());
    // }
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
    double cpuUtilizationVal = 0.0;
    double gpuAllUtilizationVal = 0.0;
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

        // request_sent = std::chrono::high_resolution_clock::now();
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
                    // std::cout << ", thread " << thread_id << ", latency: " << duration << "ms" << std::endl;
                    // g_latency.push_back(duration);
                    first_response_received = response_received;
                    isFirst = false;
                }
                if (reply.status() == 0) {
                    boost::property_tree::ptree jsonMessage;
                    std::stringstream ss(reply.message());
                    boost::property_tree::read_json(ss, jsonMessage);
                    // job_handle = jsonMessage.get<size_t>("handle");
                    // std::cout << "pipeline has been loaded, job handle: " << job_handle << std::endl;
                    double latency;
                    if (jsonMessage.get<std::string>("Type", "") == "PerformanceData") {
                        // performance Data
                        std::cout << "save report to " << reportFileName << std::endl;
                        boost::property_tree::write_json(reportFileName, jsonMessage);
                        continue;
                    }
                    // else if(jsonMessage.count("roi_info") > 0) {
                    //     boost::property_tree::ptree roi_info = jsonMessage.get_child("roi_info");
                    //     for (auto roi_i = roi_info.begin(); roi_i != roi_info.end(); ++roi_i) {
                    //         auto roi_item = roi_i->second;
                    //         latency = roi_item.get<int64_t>("latency");
                    //         g_latency_sum += latency;
                    //         ++g_latency_count;
                    //     }
                    // }
                    else if (jsonMessage.get<std::string>("Type", "") == "PerformanceData") {
                        // PerformanceData msg, ignore
                        continue;
                    }
                    else {
                        // get latency from jsonMessage
                        std::string baseKey = "latency";
                        std::string key;
                        for (int i = 1; i <= 6; ++i) {
                            if (1 == i) {
                                key = baseKey;
                            }
                            else {
                                key = baseKey + std::to_string(i);
                            }
                            if (jsonMessage.count(key) > 0) {
                                latency = jsonMessage.get<double>(key);
                                g_latency_sum += latency;
                                ++g_latency_count;
                                g_latency_min = latency < g_latency_min ? latency : g_latency_min;
                                g_latency_max = latency > g_latency_max ? latency : g_latency_max;
                            }
                        }

                        baseKey = "inference_latency";
                        for (int i = 1; i <= 6; ++i) {
                            if (1 == i) {
                                key = baseKey;
                            }
                            else {
                                key = baseKey + std::to_string(i);
                            }
                            if (jsonMessage.count(key) > 0) {
                                latency = jsonMessage.get<double>(key);
                                g_inference_latency_sum += latency;
                                ++g_inference_latency_count;
                                g_inference_latency_min = latency < g_inference_latency_min ? latency : g_inference_latency_min;
                                g_inference_latency_max = latency > g_inference_latency_max ? latency : g_inference_latency_max;
                            }
                        }

                        baseKey = "video_latency";
                        for (int i = 1; i <= 6; ++i) {
                            if (1 == i) {
                                key = baseKey;
                            }
                            else {
                                key = baseKey + std::to_string(i);
                            }
                            if (jsonMessage.count(key) > 0) {
                                latency = jsonMessage.get<double>(key);
                                g_video_latency_sum += latency;
                                ++g_video_latency_count;
                                g_video_latency_min = latency < g_video_latency_min ? latency : g_video_latency_min;
                                g_video_latency_max = latency > g_video_latency_max ? latency : g_video_latency_max;
                            }
                        }

                        if (jsonMessage.count("lidar_latency") > 0) {
                            latency = jsonMessage.get<double>("lidar_latency");
                            g_lidar_latency_sum += latency;
                            ++g_lidar_latency_count;
                            g_lidar_latency_min = latency < g_lidar_latency_min ? latency : g_lidar_latency_min;
                            g_lidar_latency_max = latency > g_lidar_latency_max ? latency : g_lidar_latency_max;
                        }
                    }
                    // std::cout<< "frame index: "<< frameCnt <<" latency :"<<latency <<std::endl;
                }

                reply_status = reply.status();
                // std::cout << "frame index: " << frameCnt << ", reply_status: " << reply_status << std::endl;
                // std::cout << msg << std::endl;

                int getCPUUti = cpuMetrics.cpuUtilization();
                float getGPUUti = gpuBusyValue.load();
                cpuUtilizationVal += getCPUUti;
                gpuAllUtilizationVal += getGPUUti;

                int fpsCnt = frameCnt - firstResponseIndex;
                frameCnt += 1;
                std::lock_guard<std::mutex> lg(g_mutex);  // Acquire lock before accessing shared variable
                auto timeElapsed = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - first_response_received).count();
                float curFPS = fpsCnt == 0 ? 0 : fpsCnt * 1000.0 / timeElapsed;
                std::cout << "[thread " << thread_id << "], curFPS: " << curFPS << ", frames: " << frameCnt << std::endl;

                if (frameCnt % 100 == 0) {
                    std::string info = "[thread " + std::to_string(thread_id) + "] " + std::to_string(frameCnt) + " frames have been processed.";
                    std::cout << info << std::endl;
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

    cpuUtilizationVal /= (frameCnt * cpuMetrics.cpuThreads());
    gpuAllUtilizationVal /= frameCnt;
    std::cout << "cpuUtilizationVal: " << cpuUtilizationVal << "%; gpuAllUtilizationVal: " << gpuAllUtilizationVal << "%" << std::endl;

    std::lock_guard<std::mutex> lg(g_mutex);
    g_total.push_back(timeUsed.count());
    g_frameCnt.push_back(frameCnt);
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

int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (argc < 8 || argc > 11) {
            std::cerr << "Usage: testGRPCCPlusLPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <media_type> [<pipeline_repeats>] "
                         "[<cross_stream_num>] [<warmup_flag: 0 | 1>]\n"
                      << "Example:\n"
                      << "    ./testGRPCCPlusLPipeline 127.0.0.1 50052 ../../ai_inference/test/configs/raddet/localRadarPipeline.json 1 1 /path/to/dataset "
                         "multisensor\n"
                      << "Or:\n"
                      << "    ./testGRPCCPlusLPipeline 127.0.0.1 50052  ../../ai_inference/test/configs/raddet/localMediaPipeline.json 1 1 /path/to/dataset "
                         "multisensor\n"
                      << "Or:\n"
                      << "    ./testGRPCCPlusLPipeline 127.0.0.1 50052 ../../ai_inference/test/configs/raddet/localFusionPipeline.json  1 1 /path/to/dataset "
                         "multisensor\n"
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
        std::string mediaType(argv[7]);

        HVA_DEBUG("mediatype: %s", mediaType);
        HVA_DEBUG("dataPath: %s", dataPath.c_str());

        // optional args
        unsigned pipeline_repeats = 1;
        unsigned crossStreamNum = 1;
        bool warmupFlag = true;

        if (argc == 9) {
            pipeline_repeats = atoi(argv[8]);
        }
        if (argc == 10) {
            pipeline_repeats = atoi(argv[8]);
            crossStreamNum = atoi(argv[9]);
        }
        if (argc == 11) {
            pipeline_repeats = atoi(argv[8]);
            crossStreamNum = atoi(argv[9]);
            warmupFlag = bool(atoi(argv[10]));
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

        // ---------------------------------------------------------------------------
        //                                 init cpu/gpu metrics
        //  ---------------------------------------------------------------------------
        std::cout << "Initialize system metrics for cpu and gpu..." << std::endl;
        // if (SHOWGPUMETRIC)
        //     gpuMetrics.init();
        // get metrics for specific process
        // cpuMetrics.init("HceAILLInfServe");  // statistic only HceAIInfServe process
        cpuMetrics.init();  // for C+L, we may create multiple HceAIInfServe process, need to monitor all HceAIInfServe process
        // ---------------------------------------------------------------------------
        //                                 processing
        //  ---------------------------------------------------------------------------
        std::cout << "Start processing with " << threadNum << " threads: total-stream = " << totalStreamNum << ", each thread will process " << crossStreamNum
                  << " streams" << std::endl;

        vThs.clear();

        std::vector<std::string> inputs;  // paths of input bin files

        for (unsigned i = 0; i < threadNum; ++i) {
            std::string reportFileName = "performance_data_" + std::to_string(i) + ".json";
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(dataPath), repeats, mediaType, i, crossStreamNum, warmupFlag,
                          pipeline_repeats, reportFileName);
            vThs.push_back(std::move(t));
        }

        int interval = 1;
        if (getGPUUtilization(interval) < 0) {
            std::cerr << "Error: Get GPU utilization error." << std::endl;
            return EXIT_FAILURE;
        }
        sleep(2);

        for (auto &item : vThs) {
            item.join();
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
        double latency_ave = g_latency_sum / (double)g_latency_count;
        double inference_latency_ave = 0;
        double video_latency_ave = 0.0;
        double lidar_latency_ave = 0.0;
        if (g_inference_latency_count != 0) {
            inference_latency_ave = g_inference_latency_sum / (double)g_inference_latency_count;
        }
        if (g_video_latency_count != 0) {
            video_latency_ave = g_video_latency_sum / (double)g_video_latency_count;
        }
        if (g_lidar_latency_count != 0) {
            lidar_latency_ave = g_lidar_latency_sum / (double)g_lidar_latency_count;
        }

        std::cout << "g_latency_count: " << g_latency_count << ", g_inference_latency_count: " << g_inference_latency_count
                  << ", g_video_latency_count: " << g_video_latency_count << ", g_lidar_latency_count: " << g_lidar_latency_count << std::endl;


        std::cout << "\n=================================================\n" << std::endl;
        std::cout << "WARMUP: " << std::to_string(warmupFlag) << std::endl;
        std::cout << "fps: " << fps << std::endl;
        std::cout << "average latency " << latency_ave << std::endl;
        std::cout << "video pipeline average latency " << video_latency_ave << std::endl;
        std::cout << "inference average latency " << inference_latency_ave << std::endl;
        std::cout << "lidar average latency " << lidar_latency_ave << std::endl;

        std::cout << "average latency min: " << g_latency_min << std::endl;
        std::cout << "average latency max: " << g_latency_max << std::endl;
        std::cout << "inference latency min: " << g_inference_latency_min << std::endl;
        std::cout << "inference latency max: " << g_inference_latency_max << std::endl;
        std::cout << "video latency min: " << g_video_latency_min << std::endl;
        std::cout << "video latency max: " << g_video_latency_max << std::endl;
        std::cout << "lidar latency min: " << g_lidar_latency_min << std::endl;
        std::cout << "lidar latency max: " << g_lidar_latency_max << std::endl;

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
