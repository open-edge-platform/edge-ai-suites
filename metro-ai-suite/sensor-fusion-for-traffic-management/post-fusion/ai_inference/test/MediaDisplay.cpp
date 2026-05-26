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
#include "modules/visualization/Plot.h"
#include "math.h"

using namespace hce::ai::inference;

#define SHOWGPUMETRIC true

std::vector<std::size_t> g_total;
std::vector<std::size_t> g_frameCnt;
std::vector<double> g_latency;
std::vector<double> g_inference_latency;
std::vector<double> g_video_latency;
std::mutex g_mutex;

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
void parseInputs(const std::string data_path, std::vector<std::string> &inputs, std::string &mediaType)
{
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
            std::vector<std::string> radarInputs;
            getAllFiles(data_path + "/radar", radarInputs, ".bin");

            if (bgrInputs.size() != radarInputs.size()) {
                HVA_ERROR("each sensor input should have equal sizes, but got bgr: %d, radar: %d", bgrInputs.size(), radarInputs.size());
                HVA_ASSERT(false);
            }
            std::string path;
            // insert aligned sensor data by sequence
            for (int i = 0; i < bgrInputs.size(); i++) {
                path = parseAbsolutePath(bgrInputs[i]);
                inputs.push_back(path);
                path = parseAbsolutePath(radarInputs[i]);
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
              unsigned pipeline_repeats,
              unsigned fpsWindow)
{
    GRPCClient client{host, port};

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
                timeArr.push_back(duration);

                if (isFirst) {
                    std::lock_guard<std::mutex> lg(g_mutex);
                    std::cout << ", thread " << thread_id << ", latency: " << duration << "ms" << std::endl;
                    // g_latency.push_back(duration);
                    first_response_received = response_received;
                    isFirst = false;
                }

                reply_status = reply.status();
                std::cout << "frame index: " << frameCnt << ", reply_status: " << reply_status << std::endl;
                std::cout << msg << std::endl;

                // frameCnt += 1;
                // float curFPS = frameCnt * 1000.0 / duration;
                // std::cout << "curFPS: " << curFPS << ", frames: " << frameCnt << std::endl;
                // msg = to_string(curFPS).substr(0, 5) + msg;
                float timeElapsed = 0.0;
                int fpsCnt = 0;
                if (frameCnt > 0) {
                    if (frameCnt == firstResponseIndex) {
                        fpsCnt = 0;
                    }
                    else {
                        if (0 >= fpsWindow) {
                            // start record time when 1st frame is received
                            timeElapsed = timeArr[frameCnt] - timeArr[firstResponseIndex];
                            if (timeElapsed < 0)
                                std::cout << "timeElapse: " << timeElapsed << std::endl;
                            fpsCnt = frameCnt - firstResponseIndex;
                        }
                        else {
                            int last = frameCnt > fpsWindow ? frameCnt - fpsWindow : 0;
                            timeElapsed = timeArr[frameCnt] - timeArr[last];
                            fpsCnt = frameCnt > fpsWindow ? fpsWindow : frameCnt;
                        }
                    }
                }
                frameCnt += 1;

                float curFPS = fpsCnt == 0 ? 0 : fpsCnt * 1000.0 / timeElapsed;
                std::cout << "curFPS: " << curFPS << ", frames: " << frameCnt << std::endl;
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

        firstResponseIndex = timeArr.size();
    }

    std::lock_guard<std::mutex> lg(g_mutex);
    g_total.push_back(timeUsed.count());
    g_frameCnt.push_back(frameCnt);
}

void parseReply(cv::Mat &frame, std::string imsg, int frameCnt)
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

    vector<int> roi_arr(4);

    double latency;
    std::chrono::time_point<std::chrono::high_resolution_clock> startTime, endTime;
    if (jsonTree.get<double>("latency")){
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
            auto roi_item = roi_i->second;
            std::string roi_class_name = roi_item.get<string>("roi_class");
            float roi_score = roi_item.get<float>("roi_score");

            // if (roi_class.size() != 4 && roi_score < 0.8)
            // continue;

            // read media results from roi
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
            cv::Point start_point(roi_arr[0], roi_arr[1]);
            cv::Point start_point2(roi_arr[0], max(10, roi_arr[1] - 6));
            cv::Point end_point(roi_arr[0]+roi_arr[2], roi_arr[1]+roi_arr[3]);
            char objectStr[256];
            sprintf(objectStr, "[%s]: %0.2f", roi_class_name.c_str(), roi_score);

            cv::putText(frame, objectStr, start_point2, cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar{0, 127, 255}, 1, cv::LINE_8);
            cv::rectangle(frame, start_point, end_point, cv::Scalar{0, 255, 0}, 1, cv::LINE_8);

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
    sprintf(latencyStr, "E2E Processing Latency: %.2lf ms", latency);
    std::string latencyStrStd = latencyStr;
    std::cout << " latency: " << latency << "ms" << ", frames: " << frameCnt << std::endl;

    std::string fpsStr = "FPS: " + ifps;
    std::string frameCntStr = "FrameCnt: " + to_string(frameCnt);


    // show FPS
    textSize = cv::getTextSize(fpsStr, font, fontScale, thickness, &baseline);
    cv::putText(frame, fpsStr, cv::Point(frame.cols - textSize.width, offset), font, fontScale, {0, 255, 0}, thickness, cv::LINE_8);
    offset += textSize.height + baseline + lineSpace;

    textSize = cv::getTextSize(frameCntStr, font, fontScale, thickness, &baseline);
    cv::putText(frame, frameCntStr, cv::Point(frame.cols - textSize.width, offset), font, fontScale, {0, 255, 0}, thickness, cv::LINE_8);
    offset += baseline + textSize.height + lineSpace;

    // show latency
    textSize = cv::getTextSize(latencyStrStd, font, fontScale, thickness, &baseline);
    cv::putText(frame, latencyStrStd, cv::Point(frame.cols - textSize.width, offset), font, fontScale, {0, 255, 0}, thickness, cv::LINE_8);
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

void renderOSDImage(cv::Mat &osd_image, int frame_index, MessageBuffer_t *db)
{
    // float frame_height = raw_image.rows;
    // cv::Mat plot = pl.getPlotImage();
    // cv::resize(raw_image, raw_image, Size(plot.rows * raw_image.cols / raw_image.rows, plot.rows));
    // cv::hconcat(raw_image, plot, osd_image);
    // float resize_rate = static_cast<float>(frame_height / plot.rows);

    parseReply(osd_image, replyGet(db), frame_index);
}

/**
 * @brief on screen display load, to prepare show_image for each channel
 * @param data_path input file path
 * @param j thread id
 * @param dis
 */
void OSDload(const std::vector<std::string> &inputs,
             unsigned thread_id,
             cv::Mat windowImage,
             MessageBuffer_t *db,
             const std::string mediaType,
             bool saveFlag = false,
             bool logoFlag = true)
{
    // query each frame
    cv::VideoWriter video;
    if (saveFlag) {
        std::string filaPath = "./radar.avi";
        video.open(filaPath, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'), 25.0, cv::Size(windowImage.cols, windowImage.rows), true);
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
        substr.append("/../../ai_inference/test/demo/intel-logo-1C1R.png");
        logo = cv::imread(substr);
        cv::cvtColor(logo, logoGray, cv::COLOR_BGR2GRAY);
        cv::threshold(logoGray, mask, 80, 255, cv::THRESH_BINARY);
        cv::bitwise_not(mask, maskInv);
    }
    if (mediaType == "multisensor") {
        // decode images
        // need parse radar output from output node and display on birdview
        // each input should be "*.bin", and organized with sequece: [bgr, radar]
        int total_frames = inputs.size() / 2;
        for (int i = 0; i < total_frames; i++) {
            char *buffer;
            size_t length;
            readRawDataFromBinary(inputs[i * 2], buffer, length);
            if (length == 0) {
                continue;
            }
            cv::Mat rawData(1, length, CV_8UC1, (void *)buffer);
            cv::Mat decodedImage = cv::imdecode(rawData, cv::ImreadModes::IMREAD_COLOR);
            if (logoFlag) {
                cv::Mat roi, roiBg, roiFg, dst;
                roi = decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10, decodedImage.rows - logo.rows - 10, logo.cols, logo.rows));
                cv::bitwise_and(roi, roi, roiBg, maskInv);
                cv::bitwise_and(logo, logo, roiFg, mask);
                cv::add(roiBg, roiFg, dst);
                cv::addWeighted(dst, 0.5, roi, 0.5, 0,
                                decodedImage(cv::Rect(decodedImage.cols - logo.cols - 10, decodedImage.rows - logo.rows - 10, logo.cols, logo.rows)));
            }

            // cv::Mat osd_image;
            renderOSDImage(decodedImage, i, db);
            std::lock_guard<std::mutex> lg(g_window_mutex);
            decodedImage.copyTo(windowImage);

            if (saveFlag) {
                video.write(decodedImage);
            }
            delete[] buffer;
        }
    }
    else {
        std::cerr << "Invalid media type was parsed: " << mediaType << "!" << std::endl;
    }

    video.release();

    stop_display = true;
    std::cout << "Display done!" << std::endl;
}

/**
 * @brief use a seperate thread to continuously imshow()
 */
void displayload(cv::Mat windowImage)
{
    while (!stop_display) {
        cv::imshow(WINDOWNAME, windowImage);
        cv::waitKey(5);

        // sleep for 33 ms
        sleep(0.03);
        // sleep(0.1);
    }
}


int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (argc < 8 || argc > 14) {
            std::cerr << "Usage: MediaDisplay <host> <port> <json_file> <total_stream_num> <repeats> <data_path> <data_type> "
                         "[<save_flag: 0 | 1>] [<pipeline_repeats>] [<fps_window: unsigned>] [<cross_stream_num>] [<warmup_flag: 0 | 1>] [<logo_flag: 0 | 1>]\n"
                      << "Example:\n"
                      << "    ./MediaDisplay 127.0.0.1 50052 ../../ai_inference/test/configs/raddet/localFusionPipeline.json 1 1 "
                         "/path/to/dataset multisensor \n"
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
        std::string dataType(argv[7]);
        HVA_DEBUG("dataType: %s", dataType);
        HVA_DEBUG("dataPath: %s", dataPath.c_str());

        // optional args
        unsigned fpsWindow = 0;
        unsigned pipeline_repeats = 1;
        unsigned crossStreamNum = 1;
        bool warmupFlag = true;
        bool saveFlag = false;
        bool logoFlag = true;

        if (argc == 9) {
            saveFlag = bool(atoi(argv[8]));
        }
        if (argc == 10) {
            saveFlag = bool(atoi(argv[8]));
            pipeline_repeats = atoi(argv[9]);
        }
        if (argc == 11) {
            saveFlag = bool(atoi(argv[8]));
            pipeline_repeats = atoi(argv[9]);
            fpsWindow = atoi(argv[10]);
        }
        if (argc == 12) {
            saveFlag = bool(atoi(argv[8]));
            pipeline_repeats = atoi(argv[9]);
            fpsWindow = atoi(argv[10]);
            crossStreamNum = atoi(argv[11]);
        }
        if (argc == 13) {
            saveFlag = bool(atoi(argv[8]));
            pipeline_repeats = atoi(argv[9]);
            fpsWindow = atoi(argv[10]);
            crossStreamNum = atoi(argv[11]);
            warmupFlag = bool(atoi(argv[12]));
        }
        if (argc == 14) {
            saveFlag = bool(atoi(argv[8]));
            pipeline_repeats = atoi(argv[9]);
            fpsWindow = atoi(argv[10]);
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

        // ---------------------------------------------------------------------------
        //                                 init display
        //  ---------------------------------------------------------------------------
        cv::Mat windowImage = cv::Mat::zeros(cv::Size(640, 480), CV_8UC3); 
        stop_display = false;

        // ---------------------------------------------------------------------------
        //                                 processing
        //  ---------------------------------------------------------------------------
        std::cout << "Start processing with " << threadNum << " threads: total-stream = " << totalStreamNum << ", each thread will process " << crossStreamNum
                  << " streams" << std::endl;

        vThs.clear();
        dThs.clear();
        std::vector<std::string> inputs;  // paths of input bin files
        std::string mediaType;
        parseInputs(dataPath, inputs, mediaType);

        struct MessageBuffer_t msg_buffer[threadNum];
        for (unsigned i = 0; i < threadNum; ++i) {
            initMessageBuffer(&msg_buffer[i]);
            std::thread t(workload, std::ref(host), std::ref(port), std::ref(contents), std::ref(inputs), i, &msg_buffer[i], repeats, crossStreamNum,
                          warmupFlag, pipeline_repeats, fpsWindow);  // workload for ai inference
            vThs.push_back(std::move(t));
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
            pipeline_repeatinputs.insert(pipeline_repeatinputs.end(), repeatinputs.begin(), repeatinputs.end());
        }
        // TODO: continuously update OSD on windowImage
        for (unsigned j = 0; j < threadNum; ++j) {
            bool showMetrics = j == 0;
            std::thread d(OSDload, std::ref(pipeline_repeatinputs), j, windowImage, &msg_buffer[j], mediaType, saveFlag, logoFlag);
            dThs.push_back(std::move(d));
        }

        for (auto &item : vThs) {
            item.join();
        }

        for (auto &item : dThs) {
            item.join();
        }

        displayThread.join();

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
