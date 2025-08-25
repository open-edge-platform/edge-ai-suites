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

#include <memory>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/vector3.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav2_dynamic_msgs/msg/obstacle.hpp"
#include "nav2_dynamic_msgs/msg/obstacle_array.hpp"
#include "visualization_msgs/msg/marker.hpp"
#include "visualization_msgs/msg/marker_array.hpp"
#include "pcl_conversions/pcl_conversions.h"
#include "print_info.h"
#include "doDBSCAN.hpp"

using std::placeholders::_1;
using namespace std;

extern Config_params_t CONFIG_PARAMS;

bool b_Verbose = false;

typedef struct _point
{
  float x;
  float y;
  float z;
} Point_xyz;  //Point type used for ADBSCAN input 

vector<Point_xyz> PointCloud2_to_point_xyz (const sensor_msgs::msg::PointCloud2::SharedPtr point_cloud2_msgs)
{

    pcl::PointCloud<pcl::PointXYZ> point_cloud;
    pcl::fromROSMsg(*point_cloud2_msgs, point_cloud);

    vector<Point_xyz> point_list;

    for(const auto& pt : point_cloud.points)
    {         
        Point_xyz new_pt;
        new_pt.x = pt.x;
        new_pt.y = pt.y;
        new_pt.z = pt.z;
        point_list.push_back(new_pt);   
    }

    return point_list;
 }

//publish Marker array to visualize clusters
visualization_msgs::msg::MarkerArray Get_MarkerArray(vector<Obstacle> obstacles)
{
    //auto obstacleArr_msg = nav2_dynamic_msgs::msg::ObstacleArray(); 
    auto markerArr_msg = visualization_msgs::msg::MarkerArray();

    int obstacle_num = obstacles.size();
    for (int i=0; i<obstacle_num; i++)
    {
      visualization_msgs::msg::Marker tmp_marker;
      tmp_marker.header.frame_id = "map";
      tmp_marker.type = visualization_msgs::msg::Marker::CUBE;
      tmp_marker.action = tmp_marker.ADD;
      tmp_marker.id = i;

      tmp_marker.pose.position.x = obstacles[i].c_x;
      tmp_marker.pose.position.y = obstacles[i].c_y;
      tmp_marker.pose.position.z = obstacles[i].c_z;
      tmp_marker.pose.orientation.x = 0.0;
      tmp_marker.pose.orientation.y = 0.0;
      tmp_marker.pose.orientation.z = 0.0;
      tmp_marker.pose.orientation.w = 1.0;

      tmp_marker.scale.x = obstacles[i].x;
      tmp_marker.scale.y = obstacles[i].y;
      tmp_marker.scale.z = obstacles[i].z;

      tmp_marker.color.r = 0.0f;
      tmp_marker.color.g = 1.0f;
      tmp_marker.color.b = 0.0f;
      tmp_marker.color.a = 1.0;
    
      markerArr_msg.markers.push_back(tmp_marker);

    }

    return markerArr_msg;
}

//convert a vector of 3D points to flat memory for ADBSCAN input
int Convert_vec_pData(vector<Point_xyz> point_list, void * &p_LiDAR_data)
{
    //get the size of point cloud
    int num_pt = point_list.size();
    //allocate the memory location
    LiDAR_data_4D_t * p_LiDAR_4D, * start_pt;
    //p_LiDAR_4D = (LiDAR_data_4D_t *)malloc(num_pt*sizeof(LiDAR_data_4D_t));
    p_LiDAR_4D = (LiDAR_data_4D_t *)p_LiDAR_data;
    if ( p_LiDAR_4D == NULL) return -1;  //failed to allocate memory
    start_pt = p_LiDAR_4D;
    for (int i = 0; i<num_pt; i++)
    {
        p_LiDAR_4D->val[0] = point_list[i].x;
        p_LiDAR_4D->val[1] = point_list[i].y;
        p_LiDAR_4D->val[2] = point_list[i].z;
        p_LiDAR_4D->val[3] = 0.0;  //reflection value, not used
        p_LiDAR_4D++;
    }

    //flatten into void * type
    p_LiDAR_data = (void *)start_pt;

    return 0;
}

//convert ADBSCAN output into ObstacleArray for publication
nav2_dynamic_msgs::msg::ObstacleArray Convert_Obstacles_to_ObstacleArr(vector<Obstacle> obstacles)
{
    auto obstacleArr_msg = nav2_dynamic_msgs::msg::ObstacleArray(); 
      
    int obstacle_num = obstacles.size();
    for (int i=0; i<obstacle_num; i++)
    {
      nav2_dynamic_msgs::msg::Obstacle tmp_obstacle;
      for (int j = 0 ; j < 16; j++)
      {
        tmp_obstacle.uuid.uuid[j] = i % 128;
      }
      tmp_obstacle.position.x = obstacles[i].c_x;
      tmp_obstacle.position.y = obstacles[i].c_y;
      tmp_obstacle.position.z = obstacles[i].c_z;
      tmp_obstacle.size.x = obstacles[i].x;
      tmp_obstacle.size.y = obstacles[i].y;
      tmp_obstacle.size.z = obstacles[i].z;
      tmp_obstacle.velocity.x = 0.0;
      tmp_obstacle.velocity.y = 0.0;
      tmp_obstacle.velocity.z = 0.0;
      tmp_obstacle.score = 0.0;

      obstacleArr_msg.obstacles.push_back(tmp_obstacle);

      if (b_Verbose)
      {
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "c_x = '%f'", obstacles[i].c_x);
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "c_y = '%f'", obstacles[i].c_y);
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "c_z = '%f'", obstacles[i].c_z);
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "size.x = '%f'", obstacles[i].x);
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "size.y = '%f'", obstacles[i].y);
        RCLCPP_INFO(rclcpp::get_logger("verbose: "), "size.z = '%f'", obstacles[i].z);
      }
    }

    return obstacleArr_msg;
}

class MinimalSubscriber : public rclcpp::Node
{
  public:
    MinimalSubscriber()
      : Node("adbscan_sub_node")
    {
      //Read configurable parameters from config file or command line
#ifdef PRE_ROS_HUMBLE
      this->declare_parameter("Lidar_type");
      this->declare_parameter("Lidar_topic");
      this->declare_parameter("Verbose");
      this->declare_parameter("subsample_ratio");
      this->declare_parameter("x_filter_back");
      this->declare_parameter("y_filter_left");
      this->declare_parameter("y_filter_right");
      this->declare_parameter("z_filter");
      this->declare_parameter("Z_based_ground_removal");
      this->declare_parameter("base");
      this->declare_parameter("coeff_1");
      this->declare_parameter("coeff_2");
      this->declare_parameter("scale_factor");
      this->declare_parameter("oneapi_library");
      this->declare_parameter("benchmark_number_of_frames");
#else
      /* From ROS Humble and beyond, declare_parameter() defaultValue is mandatory */
      this->declare_parameter("Lidar_type", std::string("RS"));
      this->declare_parameter("Lidar_topic", std::string("/camera/depth/color/points"));
      this->declare_parameter("Verbose", true);
      this->declare_parameter("subsample_ratio", double(150.0));
      this->declare_parameter("x_filter_back", double(3.0));
      this->declare_parameter("y_filter_left", double(2.0));
      this->declare_parameter("y_filter_right" ,double(-2.0));
      this->declare_parameter("z_filter", double(-0.1));
      this->declare_parameter("Z_based_ground_removal", double(1.0));
      this->declare_parameter("base", double(5.29545454));
      this->declare_parameter("coeff_1", double(-0.164835164));
      this->declare_parameter("coeff_2", double(-0.017982017));
      this->declare_parameter("scale_factor", double(0.9));
      this->declare_parameter("oneapi_library", std::string("kdtree"));
      this->declare_parameter("benchmark_number_of_frames", int(1));
#endif
      rclcpp::Parameter Lidar_type_param = this->get_parameter("Lidar_type");
      rclcpp::Parameter Lidar_topic_param = this->get_parameter("Lidar_topic");
      rclcpp::Parameter Verbose_param = this->get_parameter("Verbose");
      rclcpp::Parameter subsample_ratio_param = this->get_parameter("subsample_ratio");
      rclcpp::Parameter x_filter_back_param = this->get_parameter("x_filter_back");
      rclcpp::Parameter y_filter_left_param = this->get_parameter("y_filter_left");
      rclcpp::Parameter y_filter_right_param = this->get_parameter("y_filter_right");
      rclcpp::Parameter z_filter_param = this->get_parameter("z_filter");
      rclcpp::Parameter Z_based_ground_removal_param = this->get_parameter("Z_based_ground_removal");
      rclcpp::Parameter base_param = this->get_parameter("base");
      rclcpp::Parameter coeff_1_param = this->get_parameter("coeff_1");
      rclcpp::Parameter coeff_2_param = this->get_parameter("coeff_2");
      rclcpp::Parameter scale_factor_param = this->get_parameter("scale_factor");
      rclcpp::Parameter oneapi_library_param = this->get_parameter("oneapi_library");

#ifdef USE_ONEAPI
      adbscan_version_ = "oneAPI";
#else
      adbscan_version_ = "Standard";
#endif
      Lidar_type_ = Lidar_type_param.as_string();
      Lidar_topic_ = Lidar_topic_param.as_string();
      Verbose_ = Verbose_param.as_bool();
      t_pre = 0.0;
      t_adb = 0.0;
      t_post = 0.0;
      CONFIG_PARAMS.subsample_ratio = subsample_ratio_param.as_double();
      CONFIG_PARAMS.x_filter_back = x_filter_back_param.as_double();
      CONFIG_PARAMS.y_filter_left = y_filter_left_param.as_double();
      CONFIG_PARAMS.y_filter_right = y_filter_right_param.as_double();
      CONFIG_PARAMS.z_filter = z_filter_param.as_double();
      CONFIG_PARAMS.Z_based_ground_removal = Z_based_ground_removal_param.as_double();
      CONFIG_PARAMS.base = base_param.as_double();
      CONFIG_PARAMS.coeff_1 = coeff_1_param.as_double();
      CONFIG_PARAMS.coeff_2 = coeff_2_param.as_double();
      CONFIG_PARAMS.Lidar_type = Lidar_type_param.as_string();
      CONFIG_PARAMS.scale_factor = scale_factor_param.as_double();
      CONFIG_PARAMS.oneapi_library = oneapi_library_param.as_string();

      // oneapi_library_ parameter is used to print out the library name with benchmark data
      // In case of invalid parameter (else condition), library choice is Standard PCL kdtree (based on the if_else condition in  dbscan_adaptiveK.cpp)
      if (CONFIG_PARAMS.oneapi_library == "oneapi_kdtree")
      {
        oneapi_library_ = "oneAPI KDTree";
      }
      else if (CONFIG_PARAMS.oneapi_library == "oneapi_octree")
      {
        oneapi_library_ = "oneAPI OCTree";
      }
      else
      {
        oneapi_library_ = "Standard PCL KDTree";
      }
      count_ = 0;
      start_recording_time_ = false;
      benchmark_number_of_frames = this->get_parameter("benchmark_number_of_frames").as_int();
      if (Verbose_) 
      {
        RCLCPP_INFO(this->get_logger(), "Verbose mode"); 
        b_Verbose = true;
      }

      if (Verbose_)
      {
        RCLCPP_INFO(this->get_logger(), "adbscan_sub_node started; ");
      }
      auto defalt_qos = rclcpp::QoS(rclcpp::SystemDefaultsQoS());
      if (Lidar_type_ == "2D")
        subscription_2D_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
            Lidar_topic_,
            defalt_qos, 
            std::bind(&MinimalSubscriber::topic_2D_callback, this, std::placeholders::_1));
      else if (Lidar_type_ == "3D" || Lidar_type_ == "RS")
        subscription_3D_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            Lidar_topic_,
            defalt_qos, 
            std::bind(&MinimalSubscriber::topic_3D_callback, this, std::placeholders::_1));
      else
        RCLCPP_ERROR(this->get_logger(), "topic not found");
      
      //create publisher to publish array of detected objects, topics: obstacle_array/marker_array

      publisher_ = this->create_publisher<nav2_dynamic_msgs::msg::ObstacleArray>("obstacle_array", 1); 
      publisher_markers_ = this->create_publisher<visualization_msgs::msg::MarkerArray>("marker_array",  rclcpp::QoS(1));  

    }

  private:
    void topic_2D_callback(const sensor_msgs::msg::LaserScan::SharedPtr _msg) //const jcao
    {
      
      RCLCPP_INFO(this->get_logger(), "Msg: number of input points: '%ld'", (_msg->ranges).size());
      print_info();
      timespec t1, t2;
      clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
      double t_publish = 0.0;
      double t_cartesian_conv = 0.0;
      std::vector<double> benchmarking_time(5, 0.0); // subsample_and_filter, param_gen, adbscan, points_in_frame and cluster_grouping
      float current_angle = _msg->angle_min - _msg->angle_increment;
        
      //vector to hold the point cloud data temporarily before converting to (void *) type
      vector<Point_xyz> point_list;
      int scan_size = _msg->ranges.size();     
      for (int i=0; i<scan_size; i++  )
      {
        Point_xyz tmp_pt;
        current_angle = current_angle + _msg->angle_increment;
        
        if (_msg->ranges[i] < _msg->range_min)
        {
            tmp_pt.x = 0; 
            tmp_pt.y = 0;
            tmp_pt.z = 0;
        }
        else if (_msg->ranges[i] > _msg->range_max)
        {
            tmp_pt.x = _msg->range_max;
            tmp_pt.y = _msg->range_max;
            tmp_pt.z = 0;
        }
        else//valid range information
        {
            //append to the point cloud list
            tmp_pt.x = _msg->ranges[i]*cos(current_angle);
            tmp_pt.y = _msg->ranges[i]*sin(current_angle);
            tmp_pt.z = 0.0;
            point_list.push_back(tmp_pt);
        }
      } 

      RCLCPP_INFO(this->get_logger(), "valid data point number:  '%ld'", point_list.size() );
      //convert point list into void *p_Data format
      void * p_Data;  //to hold lidar scan (x,y,z) format
      //allocate memory for lidar scan point cloud data
      //p_Data = malloc(point_list.size() *sizeof(LiDAR_data_4D_t));
      p_Data = (void *)malloc(point_list.size()*sizeof(LiDAR_data_4D_t));
      if (p_Data == NULL)
      {
        RCLCPP_ERROR(this->get_logger(), "Failed to allocate memory");
      }
      int result = Convert_vec_pData(point_list, p_Data);
      clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
      t_cartesian_conv = diff(t1, t2);
      if (Verbose_) RCLCPP_INFO(this->get_logger(), "data converted into flat memory");
      if (result == 0) //function successful, run ADBSCAN to obtain a list of objects
      {
        vector<Obstacle> obstacles = doDBSCAN(p_Data, point_list.size() *sizeof(LiDAR_data_4D_t),2, &benchmarking_time);
        // RCLCPP_INFO(this->get_logger(), " obstacle size = '%ld' ", obstacles.size());
        clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
        //Obstacle msg to be published
        nav2_dynamic_msgs::msg::ObstacleArray ObstacleArr;
        ObstacleArr = Convert_Obstacles_to_ObstacleArr(obstacles);
        publisher_->publish(ObstacleArr);
        //marker array msg to be publish
        RCLCPP_INFO(this->get_logger(), " obstacle size = '%ld' ", obstacles.size());
        visualization_msgs::msg::MarkerArray markerArr;
        markerArr = Get_MarkerArray(std::move(obstacles));
        publisher_markers_->publish(markerArr);
        clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
        t_publish = diff(t1, t2);
      }
      else
         RCLCPP_ERROR(this->get_logger(), "Failed to convert input data");
      count_++;
      // Need to skip recording the timing of the very first frame due to the large overhead of gpu ramp up time
      if(!start_recording_time_ && count_ == 2)
      {
        start_recording_time_ = true;
        count_ = 1;
      }
      /* Print benchmarking data */
      if (start_recording_time_)
      {
        cout << "============= Frame: " << count_ << "================" << std::endl;
        // Add guard against numeric overflow
        if ((std::numeric_limits<double>::max() - 1000*(t_cartesian_conv + benchmarking_time[0])) < t_pre ||
            (std::numeric_limits<double>::max() - 1000*(benchmarking_time[1] + benchmarking_time[2])) < t_adb ||
            (std::numeric_limits<double>::max() - 1000*(benchmarking_time[3] + benchmarking_time[4] + t_publish)) < t_post)
        {
            count_ -= 1;
            benchmark_number_of_frames = count_;
        }
        else
        {
          t_pre += 1000*(t_cartesian_conv + benchmarking_time[0]); // cartesian_conversion & subsampling_filtering
          t_adb += 1000*(benchmarking_time[1] + benchmarking_time[2]); // adbscan_param_generation & adbscan_kdtree_plus_clustering
          t_post += 1000*(benchmarking_time[3] + benchmarking_time[4] + t_publish); // points_in_frame_vector_store & cluster_grouping_and_centroid_calculation & obstacle_publishing
        }
        if(count_!= 0 && count_ == benchmark_number_of_frames)
        {
          double total_time = (t_pre + t_adb + t_post) / count_;
          cout << "======================|========================|=================|================="<< std::endl;
          cout << "   " << adbscan_version_ << " ADBSCAN : Benchmarking data (average of " << benchmark_number_of_frames <<" frame(s))" << std::endl;
          cout << "======================|========================|=================|================="<< std::endl;
          cout << "    Preprocess        |        ADBSCAN         |   Post-process  |    Total         "<< std::endl;
          cout << "======================|========================|=================|==================="<< std::endl;
          cout << "     " << t_pre/count_ << "ms       |          " << t_adb/count_ << "ms    |       " << t_post/count_ << "ms      "<<total_time << "ms     "<< std::endl; 
          cout << "======================|========================|=================|==================="<< std::endl;
          if (adbscan_version_ == "oneAPI")
          {
            cout << "Using " << oneapi_library_ << std::endl;
          }
          count_ = 0;
          t_pre = 0.0;
          t_adb = 0.0;
          t_post = 0.0;
        }
      }
      if (p_Data) free(p_Data);
    } 

    void topic_3D_callback(const sensor_msgs::msg::PointCloud2::SharedPtr _msg)
    {
      
      RCLCPP_INFO(this->get_logger(), "3D Msg received:");
      print_info();
      std::vector<double> benchmarking_time(5, 0.0); // subsample_and_filter, param_gen, adbscan, points_in_frame and cluster_grouping
      double t_publish = 0.0;
      double t_cartesian_conv = 0.0;
      timespec t1, t2;
      clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
      //vector to hold the "visualization_msgs" cloud data temporarily before converting to (void *) type
      vector<Point_xyz> point_list = PointCloud2_to_point_xyz(_msg);

      //For RealSense, go through each point and rotate 
      if (Lidar_type_ == "RS")
      {
        int num_pt = point_list.size();
        float tmp;
        for (int i = 0; i<num_pt; i++)
        {
          tmp = point_list[i].z;
          point_list[i].z = -point_list[i].y;
          point_list[i].y = -point_list[i].x;
          point_list[i].x = tmp;
        }
      }
      
      //convert point list into void *p_Data format
      void * p_Data;  //to hold lidar scan (x,y,z) format
      //allocate memory for lidar scan point cloud data
      int data_size = point_list.size();
      RCLCPP_INFO(this->get_logger(), "number of raw points: '%d' ", data_size);
      p_Data = (void *)malloc(data_size*sizeof(LiDAR_data_4D_t));
      if (p_Data == NULL)
      {
        RCLCPP_ERROR(this->get_logger(), "Failed to allocate memory");
      }
      //p_Data = (LiDAR_data_4D_t *)malloc(data_size*sizeof(LiDAR_data_4D_t));
      int result = Convert_vec_pData(std::move(point_list), p_Data);
      clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
      t_cartesian_conv = diff(t1, t2);
      cout << "test CPU: ADBScan cartesian conversion time: "  << t_cartesian_conv << " [s]" << endl;
      if (result == 0) //function successful, run ADBSCAN to obtain a list of objects
      {
        vector<Obstacle> obstacles;
        if (Lidar_type_ == "3D")
          obstacles = doDBSCAN(p_Data, data_size*sizeof(LiDAR_data_4D_t), 3, &benchmarking_time);
        else if (Lidar_type_ == "RS")  //subsampling but not filtering
          obstacles = doDBSCAN(p_Data, data_size*sizeof(LiDAR_data_4D_t), 4, &benchmarking_time); 
        clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
        //obstacle msg to be published
        nav2_dynamic_msgs::msg::ObstacleArray ObstacleArr;
        ObstacleArr = Convert_Obstacles_to_ObstacleArr(obstacles);
        publisher_->publish(ObstacleArr);

        //marker array msg to be publish
        visualization_msgs::msg::MarkerArray markerArr;
        markerArr = Get_MarkerArray(std::move(obstacles));
        publisher_markers_->publish(markerArr);
        clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
        t_publish = diff(t1, t2);
      }
      else
        RCLCPP_ERROR(this->get_logger(), "Failed to convert input data");

      count_++;
      // Need to skip recording the timing of the very first frame due to the large overhead of gpu ramp up time
      if(!start_recording_time_ && count_ == 2)
      {
        start_recording_time_ = true;
        count_ = 1;
      }
      /* Print benchmarking data */
      if(start_recording_time_)
      {
        cout << "============= Frame: " << count_ << "================" << std::endl;
        // Add guard against numeric overflow
        if ((std::numeric_limits<double>::max() - 1000*(t_cartesian_conv + benchmarking_time[0])) < t_pre ||
            (std::numeric_limits<double>::max() - 1000*(benchmarking_time[1] + benchmarking_time[2])) < t_adb ||
            (std::numeric_limits<double>::max() - 1000*(benchmarking_time[3] + benchmarking_time[4] + t_publish)) < t_post)
        {
            count_ -= 1;
            benchmark_number_of_frames = count_;
        }
        else
        {
          t_pre += 1000*(t_cartesian_conv + benchmarking_time[0]); // cartesian_conversion & subsampling_filtering
          t_adb += 1000*(benchmarking_time[1] + benchmarking_time[2]); // adbscan_param_generation & adbscan_kdtree_plus_clustering
          t_post += 1000*(benchmarking_time[3] + benchmarking_time[4] + t_publish); // points_in_frame_vector_store & cluster_grouping_and_centroid_calculation & obstacle_publishing
        }
        if(count_!= 0 && count_ == benchmark_number_of_frames)
        {
          double total_time = (t_pre + t_adb + t_post) / count_;
          cout << "======================|========================|=================|================="<< std::endl;
          cout << "   " << adbscan_version_ << " ADBSCAN : Benchmarking data (average of " << benchmark_number_of_frames <<" frame(s))" << std::endl;
          cout << "======================|========================|=================|================="<< std::endl;
          cout << "    Preprocess        |        ADBSCAN         |   Post-process  |    Total         "<< std::endl;
          cout << "======================|========================|=================|==================="<< std::endl;
          cout << "     " << t_pre/count_ << "ms       |          " << t_adb/count_ << "ms    |       " << t_post/count_ << "ms      "<<total_time << "ms     "<< std::endl; 
          cout << "======================|========================|=================|==================="<< std::endl;
          if (adbscan_version_ == "oneAPI")
          {
            cout << "Using " << oneapi_library_ << std::endl;
          }
          count_ = 0;
          t_pre = 0.0;
          t_adb = 0.0;
          t_post = 0.0;
        }
      }
      if (p_Data) free(p_Data);
    } 

    string Lidar_type_;
    string Lidar_topic_;
    string adbscan_version_;
    string oneapi_library_;
    bool Verbose_;
    bool start_recording_time_;
    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr subscription_2D_; 
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr subscription_3D_; 
    rclcpp::Publisher<nav2_dynamic_msgs::msg::ObstacleArray>::SharedPtr publisher_;
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr publisher_markers_;
    int count_;
    int benchmark_number_of_frames;
    double t_pre;
    double t_adb;
    double t_post;
    clockid_t clk_id = CLOCK_MONOTONIC_RAW; //CLOCK_REALTIME;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  //rclcpp::spin(std::make_shared<MinimalSubscriber>());
  try
  {
    rclcpp::spin(std::make_shared<MinimalSubscriber>());
  }
  catch(...)
  {
    std::cerr << "Failed to run adbscan_sub node. " << std::endl;
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
