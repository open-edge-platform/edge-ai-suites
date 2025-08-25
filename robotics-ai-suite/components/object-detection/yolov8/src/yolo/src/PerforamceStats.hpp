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

#pragma once
#include <vector>
#include <set>
#include <chrono>
#include <algorithm>
#include <mutex>
#ifdef PLOT
#include "matplot/matplot.h"
#endif 

using namespace std;

class Stats {
public:
    string save_path = "./results";
    bool draw_histograms = false;
    bool save_csv = true;

private:
    queue<chrono::duration<double>> latencies_queue;
    queue<chrono::time_point<chrono::system_clock>> arrival_times_queue;
    queue<chrono::time_point<chrono::system_clock>> departure_times_queue;
    queue<int> queue_sizes_queue;

    mutex latencies_queue_mutex;
    mutex arrival_times_queue_mutex;
    mutex departure_times_queue_mutex;
    mutex queue_sizes_queue_mutex;

    static constexpr initializer_list<float> color = {0.0, 0.8, 0.4, 0.4};
    
    template <typename T>
    vector<T> get_queue_vector(queue<T> &queue)
    {
        vector<T> vector(queue.size());
        for (int i = 0; i < vector.size(); i++)
        {
            vector[i] = queue.front();
            queue.pop();
        }
        return vector;
    }


    float measured_fps_average = 0.0;
    float measured_latency_average = 0.0;
    float measured_queue_size_average = 0.0;

    float measured_fps_deviation = 0.0;
    float measured_latency_deviation = 0.0;


public:

    #ifdef PLOT
    void make_latencies_histogram()
    {
        lock_guard<mutex> lock(latencies_queue_mutex);
        if (latencies_queue.empty())
        {
            cout << "No latencies" << endl;
            return;
        }

        vector<chrono::duration<double>> latencies= get_queue_vector<chrono::duration<double>>(latencies_queue);
        vector<double> latencies_seconds(latencies.size());
        for (int i = 0; i < latencies.size(); i++)
        {
            latencies_seconds[i] = latencies[i].count();
        }

        double sum = accumulate(latencies_seconds.begin(), latencies_seconds.end(), 0.0);
        double mean = sum / latencies_seconds.size();
        double sq_sum = inner_product(latencies_seconds.begin(), latencies_seconds.end(), latencies_seconds.begin(), 0.0);
        double stdev = sqrt(sq_sum / latencies_seconds.size() - mean * mean);

        measured_latency_average = mean;
        measured_latency_deviation = stdev;

        sort(latencies_seconds.begin(), latencies_seconds.end());

        double percentile_99 = latencies_seconds[latencies_seconds.size() * 0.99];

        if(draw_histograms){
            auto h = matplot::hist(latencies_seconds, 100);
            h->face_color(color);
            matplot::title("Latencies (seconds)");
            matplot::xlabel("Latency (seconds) mean: " + to_string(mean) + " std: " + to_string(stdev) + " 99th percentile: " + to_string(percentile_99));
            cout << "saving to: " << save_path+"/lantencies_histogram" << endl;
            matplot::save(save_path+"/lantencies_histogram", "png");
        }
        if(save_csv){
            ofstream myfile;
            myfile.open (save_path+"/latencies.csv");
            myfile << "latency\n";
            for (int i = 0; i < latencies_seconds.size(); i++)
            {
                myfile << latencies_seconds[i] << "\n";
            }
            myfile.close();
        }
    }

    void make_fps_histograms()
    {
        lock_guard<mutex> lock(arrival_times_queue_mutex);
        lock_guard<mutex> lock2(departure_times_queue_mutex);
        if (arrival_times_queue.empty() || departure_times_queue.empty())
        {
            cout << "No fps data" << endl;
            return;
        }
        vector<chrono::time_point<chrono::system_clock>> arrival_times = get_queue_vector<chrono::time_point<chrono::system_clock>>(arrival_times_queue);
        vector<chrono::time_point<chrono::system_clock>> departure_times = get_queue_vector<chrono::time_point<chrono::system_clock>>(departure_times_queue);
        

        sort(arrival_times.begin(), arrival_times.end());
        sort(departure_times.begin(), departure_times.end());

        auto fps_count = [](vector<chrono::time_point<chrono::system_clock>> &times)
        {
            int start = 0;
            int end = 0;
            int fps = 0;
            vector<int> fps_vector;

            while (end < times.size())
            {
                if (times[end] - times[start] > chrono::seconds(1))
                {
                    fps_vector.push_back(fps);
                    start += 1;
                    fps -= 1;
                }
                else
                {
                    fps += 1;
                    end += 1;
                }
            }

            return fps_vector;
        };

        vector<int> fps_arrival = fps_count(arrival_times);
        vector<int> fps_departure = fps_count(departure_times);

        int max_fps_arrival = *max_element(fps_arrival.begin(), fps_arrival.end());
        int max_fps_departure = *max_element(fps_departure.begin(), fps_departure.end());
        int min_fps_arrival = *min_element(fps_arrival.begin(), fps_arrival.end());
        int min_fps_departure = *min_element(fps_departure.begin(), fps_departure.end());

        int n_bins_arrival = max_fps_arrival - min_fps_arrival + 1;
        int n_bins_departure = max_fps_departure - min_fps_departure + 1;

        double sum_arrival = accumulate(fps_arrival.begin(), fps_arrival.end(), 0.0);
        double mean_arrival = sum_arrival / fps_arrival.size();
        double sq_sum_arrival = inner_product(fps_arrival.begin(), fps_arrival.end(), fps_arrival.begin(), 0.0);
        double stdev_arrival = sqrt(sq_sum_arrival / fps_arrival.size() - mean_arrival * mean_arrival);

        double sum_departure = accumulate(fps_departure.begin(), fps_departure.end(), 0.0);
        double mean_departure = sum_departure / fps_departure.size();
        double sq_sum_departure = inner_product(fps_departure.begin(), fps_departure.end(), fps_departure.begin(), 0.0);
        double stdev_departure = sqrt(sq_sum_departure / fps_departure.size() - mean_departure * mean_departure);

        measured_fps_average = mean_departure;
        measured_fps_deviation = stdev_departure;
        if(draw_histograms){
            auto h = matplot::hist(fps_arrival, n_bins_arrival);
            h->face_color(color);
            matplot::title("FPS arrival");
            matplot::xlabel("FPS: " + to_string(mean_arrival) + " std: " + to_string(stdev_arrival));
            matplot::save(save_path+"/fps_arrival_histogram", "png");

            auto h2 = matplot::hist(fps_departure, n_bins_departure);
            h2->face_color(color);
            matplot::title("FPS departure");
            matplot::xlabel("FPS: " + to_string(mean_departure) + " std: " + to_string(stdev_departure));
            matplot::save(save_path+"/fps_departure_histogram", "png");
        }

        if(save_csv){
            ofstream myfile;
            myfile.open (save_path+"/fps_arrival.csv");
            myfile << "fps\n";
            for (int i = 0; i < fps_arrival.size(); i++)
            {
                myfile << fps_arrival[i] << "\n";
            }
            myfile.close();

            myfile.open (save_path+"/fps_departure.csv");
            myfile << "fps\n";
            for (int i = 0; i < fps_departure.size(); i++)
            {
                myfile << fps_departure[i] << "\n";
            }
            myfile.close();
        }
    }

    void make_queue_sizes_histogram()
    {
        lock_guard<mutex> lock(queue_sizes_queue_mutex);
        if (queue_sizes_queue.empty())
        {
            cout << "No queue sizes" << endl;
            return;
        }
        vector<int> queue_sizes = get_queue_vector<int>(queue_sizes_queue);
        double sum = accumulate(queue_sizes.begin(), queue_sizes.end(), 0.0);
        double mean = sum / queue_sizes.size();

        measured_queue_size_average = mean;

        int max_val = *max_element(queue_sizes.begin(), queue_sizes.end());
        
        sort(queue_sizes.begin(), queue_sizes.end());
        if(draw_histograms){ 
            auto h = matplot::hist(queue_sizes, max_val);
            h->face_color(color);
            matplot::title("Queue sizes");
            matplot::xlabel("Queue size mean: " + to_string(mean));
            matplot::save(save_path+"/queue_sizes_histogram", "png");
        }
        if(save_csv){
            ofstream myfile;
            myfile.open (save_path+"/queue_sizes.csv");
            myfile << "queue_size\n";
            for (int i = 0; i < queue_sizes.size(); i++)
            {
                myfile << queue_sizes[i] << "\n";
            }
            myfile.close();
        }
    }
    #endif

    void add_latency(chrono::duration<double> latency)
    {
        lock_guard<mutex> lock(latencies_queue_mutex);
        latencies_queue.push(latency);
    }

    void add_arrival_time(chrono::time_point<chrono::system_clock> arrival_time)
    {
        lock_guard<mutex> lock(arrival_times_queue_mutex);
        arrival_times_queue.push(arrival_time);
    }

    void add_departure_time(chrono::time_point<chrono::system_clock> departure_time)
    {
        lock_guard<mutex> lock(departure_times_queue_mutex);
        departure_times_queue.push(departure_time);
    }

    void add_queue_size(int queue_size)
    {
        lock_guard<mutex> lock(queue_sizes_queue_mutex);
        queue_sizes_queue.push(queue_size);
    }

    static string csv_header()
    {
        return "fps_average,fps_deviation,latency_average,latency_deviation,queue_size_average";
    }

    string to_csv()
    {
        return to_string(measured_fps_average) + "," + to_string(measured_fps_deviation) + "," + to_string(measured_latency_average) + "," + to_string(measured_latency_deviation) + "," + to_string(measured_queue_size_average);
    }

    void update_save_path(string new_save_path)
    {
        save_path = new_save_path;
        if (filesystem::exists(save_path))
        {
            cout << "Save path exists" << endl;
        }
        else
        {
            cout << "Save path does not exist" << endl;
            filesystem::create_directory(save_path);
        }
    }

    Stats()
    {
        update_save_path(save_path);
    }

};
