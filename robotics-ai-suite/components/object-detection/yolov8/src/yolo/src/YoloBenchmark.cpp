// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include <iostream>
#include "CLI11.hpp"
#include "Pipeline.hpp"
#include "Constants.hpp"
#include "PythonDownload.hpp"

int main(int argc, char **argv)
{
    int exitCode = 0;
    try{
        ov::Core core;
        
        CLI::App app{"YoloV8 Ros Node"};

        std::string device = "CPU";
        app.add_option("-d,--device", device, "Device to run inference {CPU, GPU}");

        int input_queue_max_size = 4;
        app.add_option("-q,--input_queue_max_size", input_queue_max_size, "Input queue max size");

        std::string input_topic_name = "/camera/color/image_raw";
        app.add_option("-i,--input_topic_name", input_topic_name, "Input topic name");

        std::string depth_input_topic_name = "/camera/depth/image_raw";
        app.add_option("-j,--depth_input_topic_name", depth_input_topic_name, "Depth input topic name");

        int worker_threads = 2;
        app.add_option("-w,--worker_threads", worker_threads, "Number of worker threads");

        bool half = true;
        app.add_flag("--half", half, "Half precision (default true) {true, false}");

        int time = 60;
        app.add_option("-t,--time", time, "Time to run benchmark in seconds");

        ov::hint::PerformanceMode performance_mode = ov::hint::PerformanceMode::THROUGHPUT;
        app.add_option("-p,--performance_mode", performance_mode, "Performance mode {1=Latency, 2=Throughput, 3=Cumulative throughput}");

        bool publish_video = true;
        app.add_flag("--publish_video", publish_video, "Publish video");

        bool publish_detections = false;
        app.add_flag("--publish_detections", publish_detections, "Publish detections");

        CLI11_PARSE(app, argc, argv);

        std::vector<cv::Size> resolutions = {cv::Size(640,480),cv::Size(320,240),cv::Size(1280,720)};
        std::ofstream csv_file;
        try {
            csv_file.open("stats.csv");
            csv_file << "resolution,task,model_size,half,device,performance_mode,queue_size,worker_threads,fps_average,fps_deviation,latency_average,latency_deviation,queue_size_average" << std::endl;

            for (Task task : {Task::DETECTION,Task::SEGMENTATION,Task::POSE}) {
                for (ModelSize model_size : {ModelSize::N,ModelSize::S,ModelSize::M,ModelSize::L,ModelSize::XL}) {
                    for (auto resolution : resolutions) {
                        try {
                            std::cout << "Downloading model" << endl;
                            std::string model_path = download_model(resolution,task,half,model_size);
                            std::cout << "Model downloaded" << endl;
                            Pipeline pipeline(core);

                            std::string run_name = "yolov8"+ model_size_strings[(int)model_size] + task_strs_strings[(int)task] + "_" + to_string(resolution.width) + "x" + to_string(resolution.height) + "_" + (half ? "Half" : "Full");
                            std::string timestamp = to_string(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count());
                            pipeline.stats.save_path = "stats/" + timestamp + "_" + run_name;
                            std::cout << "Starting " << run_name << std::endl;
                        

                            pipeline.configure("yolo",
                                {model_path, ""}, 
                                device, 
                                performance_mode,
                                ov::hint::Priority::HIGH,
                                ov::hint::ExecutionMode::PERFORMANCE,
                                std::max(worker_threads/2,1),
                                worker_threads,
                                "",
                                input_queue_max_size,
                                publish_video, publish_detections
                            );
                        
                            pipeline.add_input_topic(input_topic_name);
                            auto start = std::chrono::high_resolution_clock::now();
                            auto end = std::chrono::high_resolution_clock::now();
                            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
                            while (true) {
                                end = std::chrono::high_resolution_clock::now();
                                duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
                                if (duration.count() > time*1000)
                                {
                                    break;
                                }
                                std::this_thread::sleep_for(100ms);
                            }
                            #ifdef PLOT
                            try{
                                pipeline.stats.make_latencies_histogram();
                                pipeline.stats.make_fps_histograms();
                                pipeline.stats.make_queue_sizes_histogram();
                            } catch (const std::exception& e) {
                                std::cerr << "Error in generating plots: " << e.what() << std::endl;
                            }
                            #endif
                        
                            std::string csv_line = std::to_string(resolution.width) + "x" + std::to_string(resolution.height) + "," + task_names_strings[(int)task] + "," + model_size_strings[(int)model_size] + "," + std::to_string(half) + "," + device + "," + std::to_string((int)performance_mode) + "," + std::to_string(input_queue_max_size) + "," + std::to_string(worker_threads) + "," + pipeline.stats.to_csv();
                            csv_file << csv_line << std::endl;
                        } catch (const std::exception &e) {
                                std::cerr << "Exception during processing: " << e.what() << std::endl;
                        }
                    }
                }
            }
        } catch (const std::exception &e) {
            std::cerr << "Error opening or writing to CSV file: " << e.what() << std::endl;
            exitCode = -1;
        }
           
        csv_file.close();
        exitCode = 0;
    }
    
    catch (const CLI::ParseError &e) {
        std::cerr << "Error parsing command line: " << e.what() << std::endl;
        exitCode = -1;
    }

    catch (const std::exception &e) {
        std::cerr << "An exception occurred: " << e.what() << std::endl;
        exitCode = -1;
    }

    catch (...) {
        std::cerr << "An unknown exception occurred." << std::endl;
        exitCode = -1;
    }
    return exitCode;
}
