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

#include <sys/timeb.h>
#include <chrono>
#include <mutex>
#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>
#include <boost/property_tree/json_parser.hpp>

#include "utils/testUtils.hpp"
#include "utils/displayUtils.hpp"

#include "common/base64.hpp"
#include "low_latency_client/grpcClient.hpp"
#include "utils/sys_metrics/cpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_metrics_warpper.hpp"
#include "utils/sys_metrics/gpu_monitor.h"
#include "modules/visualization/Plot.h"
#include "math.h"

using namespace hce::ai::inference;

#define SHOWGPUMETRIC true

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
double g_latency_sum = 0;
int64_t g_latency_count = 0;
double g_inference_latency_sum = 0;
int64_t g_inference_latency_count = 0;
std::mutex g_mutex;

// system metrics
// GPUMetrics gpuMetrics;
CPUMetrics cpuMetrics;

std::mutex g_window_mutex;
static const string WINDOWNAME = "Camera + Radar Sensor Fusion";

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
            std::cout << "Load " << inputs.size() << " files from folder: " << data_path.c_str() << ", mark media type as: " << mediaType << std::endl;
        }
        else {
            std::cerr << "Unknown data_path is specified: " << data_path.c_str() << ", it's neither regular file nor a directory, please check!" << std::endl;
            HVA_ASSERT(false);
        }
    }
    else {
        std::cerr << "File not exists: " << data_path.c_str() << std::endl;
        HVA_ASSERT(false);
    }
}

void workload(const std::string &host,
              const std::string &port,
              const std::string &json,
              const std::vector<std::string> &mediaVector,
              unsigned repeats,
              unsigned thread_id,
              unsigned stream_num,
              unsigned pipeline_repeats,
              bool warmup_flag,
              const std::string reportFileName)
{
    GRPCClient client{host, port};

    std::chrono::time_point<std::chrono::high_resolution_clock> request_sent, response_received, first_response_received;
    std::chrono::milliseconds timeUsed(0);
    std::chrono::milliseconds thisTime(0);
    std::size_t frameCnt(0);


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
                auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - request_sent).count();

                if (isFirst) {
                    std::lock_guard<std::mutex> lg(g_mutex);
                    // std::cout << ", thread " << thread_id << ", latency: " << duration << "ms" << std::endl;
                    // g_latency.push_back(duration);
                    first_response_received = response_received;
                    isFirst = false;
                }

                reply_status = reply.status();
                if (reply.status() == 0) {
                    boost::property_tree::ptree jsonMessage;
                    std::stringstream ss(reply.message());
                    boost::property_tree::read_json(ss, jsonMessage);
                    // job_handle = jsonMessage.get<size_t>("handle");
                    // std::cout << "pipeline has been loaded, job handle: " << job_handle << std::endl;
                    if (jsonMessage.get<std::string>("Type", "") == "PerformanceData") {
                        // performance Data
                        std::cout << "save report to " << reportFileName << std::endl;
                        boost::property_tree::write_json(reportFileName, jsonMessage);
                        continue;
                    }
                    else {
                        double latency;
                        latency = jsonMessage.get<double>("latency");
                        g_latency_sum += latency;
                        ++g_latency_count;
                        if (jsonMessage.count("latency2") > 0) {
                            latency = jsonMessage.get<double>("latency2");
                            g_latency_sum += latency;
                            ++g_latency_count;
                        }
                        if (jsonMessage.count("latency3") > 0) {
                            latency = jsonMessage.get<double>("latency3");
                            g_latency_sum += latency;
                            ++g_latency_count;
                        }
                        if (jsonMessage.count("latency4") > 0) {
                            latency = jsonMessage.get<double>("latency4");
                            g_latency_sum += latency;
                            ++g_latency_count;
                        }
                        
                        if (jsonMessage.count("inference_latency") > 0) {
                            latency = jsonMessage.get<double>("inference_latency");
                            g_inference_latency_sum += latency;
                            ++g_inference_latency_count;
                        }
                        if (jsonMessage.count("inference_latency2") > 0) {
                            latency = jsonMessage.get<double>("inference_latency2");
                            g_inference_latency_sum += latency;
                            ++g_inference_latency_count;
                        }
                        if (jsonMessage.count("inference_latency3") > 0) {
                            latency = jsonMessage.get<double>("inference_latency3");
                            g_inference_latency_sum += latency;
                            ++g_inference_latency_count;
                        }
                        if (jsonMessage.count("inference_latency4") > 0) {
                            latency = jsonMessage.get<double>("inference_latency4");
                            g_inference_latency_sum += latency;
                            ++g_inference_latency_count;
                        }
                    }
                    // std::cout<< "frame index: "<< frameCnt <<" latency :"<<latency <<std::endl;
                }

                std::cout << "frame index: " << frameCnt << ", reply_status: " << reply_status << std::endl;
                // std::cout << msg << std::endl;

                int getCPUUti = cpuMetrics.cpuUtilization();
                float getGPUUti = gpuBusyValue.load();
                // float getGPUUti = gpuMetrics.gpuAllUtilization(1);
                cpuUtilizationVal += getCPUUti;
                gpuAllUtilizationVal += getGPUUti;

                int fpsCnt = frameCnt - firstResponseIndex;
                frameCnt += 1;
                std::lock_guard<std::mutex> lg(g_mutex);  // Acquire lock before accessing shared variable
                auto timeElapsed = std::chrono::duration_cast<std::chrono::milliseconds>(response_received - first_response_received).count();
                float curFPS = fpsCnt == 0 ? 0 : fpsCnt * 1000.0 / timeElapsed;
                std::cout << "curFPS: " << curFPS << ", frames: " << frameCnt << std::endl;
                msg = to_string(curFPS).substr(0, 5) + msg;

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
        std::cout << "request done with " << frameCnt << " frames" << std::endl;
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

int getGPUUtilization(int interval = 1)
{
    try {
        std::string command = "sudo timeout 1 intel_gpu_top -l -J";
        std::thread gt(runIntelGpuTop, command, interval);

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
        if (argc < 7 || argc > 10) {
            std::cerr << "Usage: testGRPC16C4RPipeline <host> <port> <json_file> <total_stream_num> <repeats> <data_path> [<pipeline_repeats>] "
                         "[<cross_stream_num>] [<warmup_flag: 0 | 1>]\n"
                      << "Example:\n"
                      << "    ./testGRPC16C4RPipeline 127.0.0.1 50052 ../../ai_inference/test/configs/raddet/16C4R/localFusionPipeline.json 4 1 /path-to-dataset\n"
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
        HVA_DEBUG("dataPath: %s", dataPath.c_str());

        // optional args
        unsigned pipeline_repeats = 1;
        unsigned crossStreamNum = 1;
        bool warmupFlag = true;
        if (argc == 8) {
            pipeline_repeats = atoi(argv[7]);
        }
        if (argc == 9) {
            pipeline_repeats = atoi(argv[7]);
            crossStreamNum = atoi(argv[8]);
        }
        if (argc == 10) {
            pipeline_repeats = atoi(argv[7]);
            crossStreamNum = atoi(argv[8]);
            warmupFlag = bool(atoi(argv[9]));
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

        int datarepeats = repeats;
        // data repeat in pipeline
        if (contents.find("data_repeats_placeholder") != std::string::npos) {
            std::cout << "support data repeats" << std::endl;
            contents = std::regex_replace(contents, std::regex("data_repeats_placeholder"), std::to_string(datarepeats));
        }
        std::cout << contents << std::endl;
        std::vector<std::thread> vThs;

        // ---------------------------------------------------------------------------
        //                                 init cpu/gpu metrics
        //  ---------------------------------------------------------------------------
        std::cout << "Initialize system metrics for cpu and gpu..." << std::endl;
        // if (SHOWGPUMETRIC)
        //     gpuMetrics.init();
        // get metrics for specific process
        cpuMetrics.init("HceAILLInfServe");  // statistic only HceAIInfServe process

        // ---------------------------------------------------------------------------
        //                                 processing
        //  ---------------------------------------------------------------------------
        std::cout << "Start processing with " << threadNum << " threads: total-stream = " << totalStreamNum << ", each thread will process " << crossStreamNum
                  << " streams" << std::endl;

        vThs.clear();
        std::vector<std::string> inputs;  // paths of input bin files
        std::string mediaType;
        parseInputs(dataPath, inputs, mediaType);

        for (unsigned i = 0; i < threadNum; ++i) {
            std::string reportFileName = "performance_data_" + std::to_string(i) + ".json";
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(inputs), repeats, i, crossStreamNum, pipeline_repeats,
                          warmupFlag, reportFileName);
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
        if (g_inference_latency_count != 0) {
            inference_latency_ave = g_inference_latency_sum / (double)g_inference_latency_count;
        }

        std::cout << "\n=================================================\n" << std::endl;
        std::cout << "WARMUP: " << std::to_string(warmupFlag) << std::endl;
        std::cout << "fps: " << fps << std::endl;
        std::cout << "average latency " << latency_ave << std::endl;
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
