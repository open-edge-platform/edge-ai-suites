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
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <optional>
#include <queue>
#include <string>
#include <thread>
#include <vector>
#include <unordered_map>
#include <sstream>

#include "rclcpp/node.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "std_msgs/msg/string.hpp"
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <tf2_msgs/msg/tf_message.hpp>


#include "opencv4/opencv2/opencv.hpp"

#include "PerforamceStats.hpp"
#include "ThreadSafeQueue.hpp"
#include "QueryFrame.hpp"
#include "ImageSync.hpp"
#include "Constants.hpp"

#ifdef PLOT
#include <matplot/matplot.h>
#endif

using namespace std;




class Pipeline
{
public:
    rclcpp::Node::SharedPtr node;
    Stats stats;

private:
    string name;
    vector<rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr> subscribers;
    chrono::time_point<chrono::system_clock> last_arrival_times[256];
    size_t added_streams = 0;

    vector<string> topics;
    shared_ptr<ov::Model> model;
    ov::CompiledModel compiled_model;

    std::string map_frame = "map";
    std::shared_ptr<tf2_ros::TransformListener> tf_listener_{ nullptr };
    std::unique_ptr<tf2_ros::Buffer> tf_buffer_;

    unordered_map<string,rclcpp::Publisher<yolo_msgs::msg::YoloFrame>::SharedPtr> detections_publishers;
    unordered_map<string,rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr> video_publishers;

    size_t input_queue_max_size = 100;

    // Hardcoded constants
    const unsigned long batch_size = 1;

    // Parameters for now hard_coded
    const float modelScoreThreshold = 0.5;
    const float modelNMSThreshold = 0.5;

    // parameters of the model
    unsigned long number_of_boxes = 8400; // 6300 for s
    cv::Size model_shape = cv::Size( 640, 640 );
    ov::element::Type input_type = ov::element::f32;

    // number of workers
    int number_of_workers = 1;


    ImageSync image_sync[256];

    ThreadSafeQueue<QueryFrame> input_queue;
    ThreadSafeQueue<QueryFrame> results_queue;

    thread background_thread;
    thread node_thread;
    thread results_thread;
    shared_ptr<rclcpp::executors::MultiThreadedExecutor> executor = nullptr;

    vector<ov::Tensor> input_tensors;
    vector<QueryFrame> query_frames;
    vector<ov::InferRequest> infer_requests;
    vector<cv::Mat> input_buffers;
    vector<shared_ptr<vector<float>>> input_datas;

    ov::Core &core;

    Task task;

    unsigned int frame_counter = 0;
    mutex frame_counter_mutex;

    bool publish_video = true;
    bool publish_detections = true;

    bool configured = false;
    bool destruction_imminent = false;
    bool destruction_imminent_publishing = false;
    bool destruction_imminent_background = false;



    void post_process_callback( ov::Tensor &box_proposals, optional<ov::Tensor> &masks_tensor,
                                QueryFrame frame )
    {
        ov::Shape box_proposals_shape;
        ov::Shape masks_shape;

        if ( task == DETECTION )
        {
            box_proposals_shape =
                ov::Shape( { batch_size, 4 + number_of_classes, number_of_boxes } );
        }
        if ( task == SEGMENTATION )
        {
            box_proposals_shape = ov::Shape(
                { batch_size, 4 + number_of_classes + number_of_masks, number_of_boxes } );
            masks_shape = ov::Shape( { batch_size, static_cast<unsigned long>( number_of_masks ),
                                       static_cast<unsigned long>( model_shape.height / 4 ),
                                       static_cast<unsigned long>( model_shape.width / 4 ) } );
        }
        if ( task == POSE )
        {
            box_proposals_shape = ov::Shape(
                { batch_size, 4 + 1 + pose_points * values_per_point, number_of_boxes } );
        }

        vector<float> output_buffer( box_proposals.get_size() );
        assert( box_proposals.get_shape() == box_proposals_shape );
        if ( task == SEGMENTATION )
        {
            assert( masks_tensor.has_value() );
            assert( masks_tensor.value().get_shape() == masks_shape );
        }

        move( box_proposals.data<float>(), box_proposals.data<float>() + box_proposals.get_size(),
              output_buffer.begin() );
        int b = box_proposals.get_shape()[0];
        int c = box_proposals.get_shape()[1];
        int d = box_proposals.get_shape()[2];

        // TODO Check if transpose of mask is needed
        vector<float> transposed_output_buffer( output_buffer.size() );
        for ( int i = 0; i < b; ++i )
        {
            for ( int j = 0; j < d; ++j )
            {
                for ( int k = 0; k < c; ++k )
                {
                    transposed_output_buffer[i * d * c + j * c + k] =
                        output_buffer[i * c * d + k * d + j];
                }
            }
        }
        int detections = box_proposals.get_shape()[2];
        int informations = box_proposals.get_shape()[1];

        float x_factor = (float)frame.msg->width / (float)model_shape.width;
        float y_factor = (float)frame.msg->height / (float)model_shape.height;

        vector<int> class_ids( detections );
        vector<float> confidences( detections );
        vector<cv::Rect> boxes( detections );
        vector<vector<float>> masks;
        if ( task == SEGMENTATION )
        {
            masks.resize( detections );
        }
        vector<vector<float>> poses;
        if ( task == POSE )
        {
            poses.resize( detections );
        }
        auto process_box = [&]( vector<float>::iterator data_start, const int &detection_index ) {
            auto [x, y, w, h] =
                std::make_tuple( data_start[0], data_start[1], data_start[2], data_start[3] );
            auto [left, top, width, height] = std::make_tuple(
                int( ( x - 0.5 * w ) * x_factor ), int( ( y - 0.5 * h ) * y_factor ),
                int( w * x_factor ), int( h * y_factor ) );

            left = max( left, 0 );
            top = max( top, 0 );
            width = min( width, (int)frame.msg->width - left );
            height = min( height, (int)frame.msg->height - top );

            boxes[detection_index] = cv::Rect( left, top, width, height );

            if ( task == DETECTION || task == SEGMENTATION )
            {
                auto max_it = max_element( data_start + 4, data_start + 4 + number_of_classes );
                int class_id = max_it - data_start - 4;
                class_ids[detection_index] = class_id;
                confidences[detection_index] = *max_it;
            }
            else
            {
                confidences[detection_index] = data_start[4];
            }

            if ( task == SEGMENTATION )
            {
                masks[detection_index].resize( number_of_masks );
                copy( data_start + 4 + number_of_classes,
                      data_start + 4 + number_of_classes + number_of_masks,
                      masks[detection_index].begin() );
            }
            if ( task == POSE )
            {
                poses[detection_index].resize( pose_points * values_per_point );
                move( data_start + 4, data_start + 4 + pose_points * values_per_point,
                      poses[detection_index].begin() );
                for ( int i = 0; i < pose_points; i++ )
                {
                    poses[detection_index][i * values_per_point + 1] =
                        poses[detection_index][i * values_per_point + 1] * y_factor;
                    poses[detection_index][i * values_per_point + 2] =
                        poses[detection_index][i * values_per_point + 2] * x_factor;
                }
            }
        };

        vector<float>::iterator data = transposed_output_buffer.begin();
        for ( int i = 0; i < detections; ++i )
        {
            process_box( data, i );
            data += informations;
        }
        vector<int> nms_result;
        cv::dnn::NMSBoxes( boxes, confidences, modelScoreThreshold, modelNMSThreshold, nms_result );

        vector<QueryFrame::Detection> reduced_detections{};

        static random_device rd;
        static mt19937 gen( rd() );
        static uniform_int_distribution<int> dis( 100, 255 );
        vector<cv::Mat> masks_vector;
        if ( task == SEGMENTATION )
        {
            masks_vector.resize( masks_tensor.value().get_size() );
            for ( int i = 0; i < number_of_masks; i++ )
            {
                masks_vector[i] = cv::Mat( masks_shape[2], masks_shape[3], CV_32FC1,
                                           std::move( masks_tensor.value().data<float>() +
                                                 i * masks_shape[2] * masks_shape[3] ) );
            }
        }

        for ( size_t i = 0; i < nms_result.size(); ++i )
        {
            int idx = nms_result[i];

            QueryFrame::Detection result;
            result.class_id = class_ids[idx];
            result.confidence = confidences[idx];

            result.color = cv::Scalar( dis( gen ), dis( gen ), dis( gen ) );

            result.className = classes[result.class_id];
            result.box = boxes[idx];

            if ( task == SEGMENTATION )
            {
                cv::Size small_box_size = cv::Size( (float)result.box.width / x_factor / 4.0f,
                                                    result.box.height / y_factor / 4 );
                cv::Mat low_res_mask_mat = cv::Mat( small_box_size, CV_32FC1, 0.0f );
                for ( int j = 0; j < number_of_masks; j++ )
                {
                    for ( int k = 0; k < small_box_size.height; k++ )
                    {
                        for ( int l = 0; l < small_box_size.width; l++ )
                        {
                            int y_offset = ( (float)result.box.y ) / y_factor / 4.0f;
                            int x_offset = ( (float)result.box.x ) / x_factor / 4.0f;
                            low_res_mask_mat.at<float>( k, l ) +=
                                masks_vector[j].at<float>( ( k + y_offset ), ( l + x_offset ) ) *
                                masks[idx][j];
                        }
                    }
                }
                cv::Mat resized_mask;
                cv::resize( low_res_mask_mat, resized_mask,
                            cv::Size( result.box.width, result.box.height ), 0, 0,
                            cv::INTER_CUBIC );
                result.mask.resize( resized_mask.rows * resized_mask.cols );
                move( resized_mask.begin<float>(), resized_mask.end<float>(), result.mask.begin() );
            }
            if ( task == POSE )
            {
                result.pose = poses[idx];
            }

            reduced_detections.push_back( result );
        }
        frame.detections = reduced_detections;
        frame.departure_time = chrono::high_resolution_clock::now();
        results_queue.push( frame );
    }

    void create_background_thread()
    {
        thread background_thread( [&]() {
            auto now = rclcpp::Clock().now();

            input_tensors.resize( number_of_workers );
            query_frames.resize( number_of_workers );

            if ( model_shape.height <= 0 || model_shape.width <= 0 )
            {
                cout << "\033[1;31m"
                     << "Model shape has negative dimensions something went terribly wrong"
                     << "\033[0m" << endl;
                throw;
            }
            int sizes[4] = { 1, 3, model_shape.height, model_shape.width };
            unsigned long input_height = model_shape.height;
            unsigned long input_width = model_shape.width;
            ov::Shape input_shape = ov::Shape( { 1, 3, input_height, input_width } );
            input_buffers.resize( number_of_workers,
                                  cv::Mat( 4, sizes, ov_element_to_cv_type( input_type ) ) );
            input_datas.resize( number_of_workers );

            auto pre_processing = [&]( int i ) {
                cv::Size frame_shape =
                    cv::Size( query_frames[i].msg->width, query_frames[i].msg->height );
                cv::Mat input_image =
                    cv::Mat( frame_shape, CV_8UC3, query_frames[i].msg->data.data() );

                cv::resize( input_image, input_image, model_shape, 0, 0, cv::INTER_CUBIC );
                cv::dnn::blobFromImage( input_image, input_buffers[i], 1.0 / 255.0, model_shape,
                                        cv::Scalar(), true, false );
                input_tensors[i] =
                    ov::Tensor( ov::element::f32, input_shape, std::move( input_buffers[i].data ) );
            };

            for ( int i = 0; i < number_of_workers; i++ )
            {
                infer_requests.push_back( compiled_model.create_infer_request() );

                infer_requests[i].set_callback( [&, i]( exception_ptr ex ) {
                    if ( destruction_imminent )
                    {
                        cout << "Worker thread exiting" << i << endl;
                        return;
                    }
                    if ( ex )
                    {
                        cout << "Exception in thread" << endl;
                        return;
                    }
                    if ( task == DETECTION || task == POSE )
                    {
                        ov::Tensor output_tensor = infer_requests[i].get_output_tensor( 0 );
                        optional<ov::Tensor> masks = {};
                        post_process_callback( output_tensor, masks, query_frames[i] );
                    }
                    if ( task == SEGMENTATION )
                    {
                        ov::Tensor box_proposals = infer_requests[i].get_output_tensor( 0 );
                        optional<ov::Tensor> masks = { infer_requests[i].get_output_tensor( 1 ) };
                        post_process_callback( box_proposals, masks, query_frames[i] );
                    }

                    optional<QueryFrame> try_pop = {};
                    while ( !try_pop )
                    {     
                        if ( destruction_imminent )
                        {
                            cout << "Worker thread exiting" << i << endl;
                            return;
                        }
                        try_pop = input_queue.try_pop();
                    }
                    query_frames[i] = try_pop.value();

                    pre_processing( i );
                    infer_requests[i].set_input_tensor( input_tensors[i] );
                    infer_requests[i].start_async();
                } );

                auto try_pop = input_queue.try_pop();
                while ( true )
                {
                    if ( try_pop )
                    {
                        query_frames[i] = try_pop.value();
                        pre_processing( i );
                        infer_requests[i].set_input_tensor( input_tensors[i] );
                        infer_requests[i].start_async();
                        cout << "Started Worker: " << i << endl;
                        break;
                    }
                    else
                    {
                        try_pop = input_queue.try_pop();
                        if ( destruction_imminent_background )
                        {
                            cout << "Background thread exiting" << endl;
                            return;
                        }
                        cout << "Waiting for initial input, Input queue size " << input_queue.size()
                             << endl;
                        this_thread::sleep_for( chrono::milliseconds( 100 ) );
                    }
                }
            }

            while ( true ) // this keeps objects alive
            {
                if ( destruction_imminent_background )
                {
                    cout << "Background thread exiting" << endl;
                    return;
                }
                this_thread::sleep_for( chrono::milliseconds( 100 ) );
                stats.add_queue_size( input_queue.size() );
            }
        } );
        background_thread.detach();
    }
    
    void create_publishing_thread(int num_threads)
    {
        auto worker = [&](int id) {
            auto query_frame_option = results_queue.try_pop();
            auto start = chrono::high_resolution_clock::now();
            auto end = chrono::high_resolution_clock::now();
            while ( true )
            {
                end = chrono::high_resolution_clock::now();
                if (id==0 && chrono::duration_cast<chrono::milliseconds>( end - start ).count() > 1000 )
                {
                    frame_counter_mutex.lock();
                    cout << "[" << this->name << "] Frames processed per second: " << frame_counter << endl;
                    frame_counter=0;
                    frame_counter_mutex.unlock();
                    start = chrono::high_resolution_clock::now();
                }
                query_frame_option = results_queue.try_pop();
                while ( query_frame_option.has_value() )
                {
                    QueryFrame &query_frame = query_frame_option.value();
                    frame_counter_mutex.lock();
                    frame_counter++;
                    frame_counter_mutex.unlock();
                    query_frame.departure_time = chrono::high_resolution_clock::now();
                    stats.add_departure_time( query_frame.departure_time );
                    stats.add_latency(query_frame.departure_time - query_frame.arrival_time);
                    if ( publish_video )
                    {
                        if (video_publishers.find(query_frame.topic_name) == video_publishers.end() ){
                            video_publishers[query_frame.topic_name] = node->create_publisher<sensor_msgs::msg::Image>("/"+name+query_frame.topic_name+"/video", 10 );
                        }
                        video_publishers[query_frame.topic_name]->publish(  query_frame.to_image_msg( task )  );
                    }
                    if ( publish_detections )
                    {
                        if (detections_publishers.find(query_frame.topic_name) == detections_publishers.end() ){
                            detections_publishers[query_frame.topic_name] = node->create_publisher<yolo_msgs::msg::YoloFrame>("/"+name+query_frame.topic_name+"/yolo_frame", 10 );
                        }
                        detections_publishers[query_frame.topic_name]->publish(std::move( *query_frame.to_YoloFrame( task ) ) );
                    }

                    query_frame_option = results_queue.try_pop();
                }
                if ( destruction_imminent_publishing )
                {
                    cout << "Publishing thread exiting" << endl;
                    return;
                }
                this_thread::sleep_for( chrono::milliseconds( 2 ) );
            }
        };

        vector<thread> threads;
        for (int i = 0; i < num_threads; ++i) {
            threads.emplace_back(worker,i);
        }

        for (auto& t : threads) {
            t.detach();
        }
    }

public:
    void add_input_topic( string topic_name,int max_fps =-1 )
    {
        cout << "\033[1;32m"
             << "Adding input topic: " << topic_name << "\033[0m" << endl;
        const size_t added_streams_const = this->added_streams;
        auto subscriber = node->create_subscription<sensor_msgs::msg::Image>(
            topic_name, 10, [&,topic_name,added_streams_const]( const sensor_msgs::msg::Image::SharedPtr image_msg )
            {
                if (max_fps != -1){
                    auto now = chrono::high_resolution_clock::now();
                    auto last_arrival_time = last_arrival_times[added_streams_const];
                    auto time_since_last_arrival = chrono::duration_cast<chrono::milliseconds>( now - last_arrival_time ).count();
                    auto time_to_wait = 1000.0/max_fps;
                    if (time_since_last_arrival < time_to_wait){
                        return;
                    }
                    last_arrival_times[added_streams_const] = now;
                }
                
                QueryFrame query_frame( image_msg );
                query_frame.topic_name = topic_name;
                stats.add_arrival_time( query_frame.arrival_time );
                input_queue.push( query_frame );
        } );
        this->added_streams++;
        subscribers.push_back( subscriber );
    }

    optional<geometry_msgs::msg::TransformStamped> get_pose( std::string frame )
    {
        if(map_frame == ""){
            return {};
        }
        geometry_msgs::msg::TransformStamped transform;
        try
        {
            transform = tf_buffer_->lookupTransform( map_frame, frame, tf2::TimePointZero );
        }
        catch ( const tf2::TransformException &ex )
        {
            RCLCPP_INFO( node->get_logger(), "Could not transform %s to %s: %s", map_frame.c_str(),
                         frame.c_str(), ex.what() );
            return {};
        }
        return { transform };
    };

    void add_joint_rgb_depth_topics( string rgb_topic_name, string depth_topic_name,int max_fps =-1 )
    {
        cout << "\033[1;32m"
             << "Adding input topics: " << rgb_topic_name << " " << depth_topic_name << "\033[0m"
             << endl;
        
        const int added_streams_const = this->added_streams++;
        image_sync[added_streams_const].callback = [this,max_fps,rgb_topic_name,added_streams_const]( const sensor_msgs::msg::Image::SharedPtr &rgb_image,
                                   const sensor_msgs::msg::Image::SharedPtr &depth_image ) {
            if (max_fps != -1){
                    auto now = chrono::high_resolution_clock::now();
                    auto last_arrival_time = last_arrival_times[added_streams_const];
                    auto time_since_last_arrival = chrono::duration_cast<chrono::milliseconds>( now - last_arrival_time ).count();
                    auto time_to_wait = 1000.0/max_fps;
                    if (time_since_last_arrival < time_to_wait){
                        return;
                    }
                    last_arrival_times[added_streams_const] = now;
            }

            if ( rgb_image->encoding != "rgb8" ||
                 !( depth_image->encoding == "32FC1" || depth_image->encoding == "16UC1" ) )
            {
                cout << "\033[1;31m"
                     << "Wrong encoding, had: " << rgb_image->encoding << " "
                     << depth_image->encoding << " expected: rgb8 32FC1"
                     << "\033[0m" << endl;

                return;
            }

            QueryFrame query_frame( rgb_image );
            query_frame.topic_name = rgb_topic_name;
            stats.add_arrival_time( query_frame.arrival_time );
            query_frame.image_origin = get_pose( rgb_image->header.frame_id );
            query_frame.msg_depth = { depth_image };
            input_queue.push( query_frame );
        };

        rclcpp::QoS qos = rclcpp::QoS( rclcpp::KeepLast( 10 ) ).best_effort();

        subscribers.emplace_back( node->create_subscription<sensor_msgs::msg::Image>(
            rgb_topic_name, qos, [&]( const sensor_msgs::msg::Image::SharedPtr image_msg ) {
                image_sync[added_streams_const].callback_rgb( image_msg );
            } ) );
        subscribers.emplace_back( node->create_subscription<sensor_msgs::msg::Image>(
            depth_topic_name, qos, [&]( const sensor_msgs::msg::Image::SharedPtr image_msg ) {
                image_sync[added_streams_const].callback_depth( image_msg );
            } ) );
    }

    void enque_image( sensor_msgs::msg::Image::SharedPtr image_msg, string image_source = "/enque" )
    {
        QueryFrame query_frame( image_msg );
        query_frame.topic_name = image_source;
        stats.add_arrival_time( query_frame.arrival_time );
        this->input_queue.push( query_frame );
    }

    optional<QueryFrame> try_pop_processed_image()
    {
        auto query_frame = results_queue.try_pop();
        if ( query_frame.has_value() )
        {
            stats.add_latency( query_frame.value().departure_time -
                               query_frame.value().arrival_time );
            stats.add_departure_time( query_frame.value().departure_time );
        }
        return query_frame;
    }

    int input_queue_size()
    {
        return input_queue.size();
    }

    void configure( string name, 
                    pair<string, string> model_path, 
                    string device,
                    ov::hint::PerformanceMode performance_mode,
                    ov::hint::Priority priority = ov::hint::Priority::MEDIUM,
                    ov::hint::ExecutionMode execution_mode = ov::hint::ExecutionMode::PERFORMANCE,
                    size_t num_requests = 2,
                    size_t number_of_workers = 1,
                    string map_frame = "",
                    const int input_queue_max_size = 10,
                    bool publish_video = true, bool publish_detections = true )
    {  
        this->map_frame = map_frame;
        if ( model_path.first.length() == 0 )
        {
            cout << "Model path cannot be empty" << endl;
            return;
        }
        try
        {
            rclcpp::init( 0, nullptr );
        }
        catch ( const std::exception &e )
        {
            std::cerr << e.what() << '\n';
        }
        this->name = name;
        this->publish_video = publish_video;
        this->publish_detections = publish_detections;
        this->input_queue_max_size = input_queue_max_size;
        input_queue.max_queue_size = input_queue_max_size;
        results_queue.max_queue_size = input_queue_max_size;
        if ( model_path.second.length() == 0 )
        {
            model = core.read_model( model_path.first );
        }
        else
        {
            model = core.read_model( model_path.first, model_path.second );
        }

        model_shape =
            cv::Size( model->input( 0 ).get_partial_shape().operator[]( 3 ).get_length(),
                      model->input( 0 ).get_partial_shape().operator[]( 2 ).get_length() );
        cout << "Model shape: " << model_shape << endl;
        cout << "Model height: " << model_shape.height << endl;
        cout << "Model width: " << model_shape.width << endl;
        model->reshape( ov::PartialShape( { 1, 3, model_shape.height, model_shape.width } ) );
        number_of_boxes = model->output( 0 ).get_partial_shape().operator[]( 2 ).get_length();
        this->number_of_workers = number_of_workers;

        if ( model->output( 0 ).get_partial_shape().operator[]( 1 ).get_length() ==
             4 + number_of_classes )
        {
            task = DETECTION;
        }
        else if ( model->output( 0 ).get_partial_shape().operator[]( 1 ).get_length() ==
                  4 + number_of_classes + number_of_masks )
        {
            task = SEGMENTATION;
        }
        else if ( model->output( 0 ).get_partial_shape().operator[]( 1 ).get_length() ==
                  4 + 1 + pose_points * values_per_point )
        {
            task = POSE;
        }
        else
        {
            cout << "\033[1;31m"
                 << "Wrong output shape"
                 << "\033[0m" << endl;
            cout << "Output shape: "
                 << model->output( 0 ).get_partial_shape().operator[]( 1 ).get_length() << endl;
            cout << "Expected: " << 4 + number_of_classes << " or "
                 << 4 + number_of_classes + number_of_masks << " or "
                 << 4 + 1 + pose_points * values_per_point << endl;
            raise( SIGINT );
        }

        auto preproc = ov::preprocess::PrePostProcessor( model );
        cout << "Node created" << endl;
        preproc.input( 0 ).tensor().set_element_type( input_type );
        model = preproc.build();
        cout << "Node created" << endl;
        if (device == "CPU"){
            this->compiled_model =
            core.compile_model( model, device, 
                                ov::hint::performance_mode( performance_mode ),
                                ov::hint::execution_mode( execution_mode ),
                                ov::hint::num_requests( num_requests ));
        }else{
            this->compiled_model = core.compile_model( model, device, 
                                ov::hint::performance_mode( performance_mode ),
                                ov::hint::execution_mode( execution_mode ),
                                ov::hint::num_requests( num_requests ), ov::hint::model_priority(priority) );
        }
        
        
        cout << "Node created" << endl;
        this->node = rclcpp::Node::make_shared( name );
        tf_buffer_ = std::make_unique<tf2_ros::Buffer>( node->get_clock() );
        tf_listener_ = std::make_shared<tf2_ros::TransformListener>( *tf_buffer_ );
        cout << "Node created" << endl;
        executor.reset( new rclcpp::executors::MultiThreadedExecutor );
        cout << "Node created" << endl;
        std::thread node_thread( [&]() {
            executor->add_node( node );
            executor->spin();
            cout << "Node thread joined" << endl;
        } );

        node_thread.detach();
        cout << "Node thread started" << endl;


        create_background_thread();
        cout << "Background thread started" << endl;
        if ( publish_detections || publish_video )
        {
            create_publishing_thread(max((size_t)1,number_of_workers/2));
            cout << "Publishing thread started" << endl;
        }

        configured = true;
    }

    Pipeline( ov::Core &core ) : core( core ){
        for (int i = 0; i < 256; i++){
            last_arrival_times[i] = chrono::time_point<chrono::system_clock>();
        }
    }

    ~Pipeline()
    {
        if ( !configured )
        {
            return;
        }
        cout << "Destroying pipeline and cleaning up" << endl;
        executor->cancel();
        for ( auto &subscriber : subscribers )
        {
            subscriber.reset();
        }
        destruction_imminent = true;
        destruction_imminent_publishing = true;
        destruction_imminent_background = true;
        sleep( 1 );
        
    }
};
