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
#include "geometry_msgs/msg/twist.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav2_dynamic_msgs/msg/obstacle.hpp"
#include "nav2_dynamic_msgs/msg/obstacle_array.hpp"
#include "visualization_msgs/msg/marker.hpp"
#include "visualization_msgs/msg/marker_array.hpp"
#include "pcl_conversions/pcl_conversions.h"
#include "print_info.h"
#include "doDBSCAN.hpp"
#include "follow_me_interfaces/msg/gesture_category.hpp"

using std::placeholders::_1;
using namespace std;

Config_params_t CONFIG_PARAMS;

bool b_Verbose = false;

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
    p_LiDAR_4D = (LiDAR_data_4D_t *)malloc(num_pt*sizeof(LiDAR_data_4D_t));
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

      tmp_obstacle.position.x = obstacles[i].c_x;
      tmp_obstacle.position.y = obstacles[i].c_y;
      tmp_obstacle.position.z = obstacles[i].c_z;
      tmp_obstacle.size.x = obstacles[i].x;
      tmp_obstacle.size.y = obstacles[i].y;
      tmp_obstacle.size.z = obstacles[i].z;

      obstacleArr_msg.obstacles.push_back(tmp_obstacle);
    }

    return obstacleArr_msg;
}

class MinimalSubscriber : public rclcpp::Node
{
  public:
    MinimalSubscriber()
    : Node("adbscan_sub_w_gesture_node")
    {
      //Read configurable parameters from config file or command line
#ifdef PRE_ROS_HUMBLE
      this->declare_parameter("Lidar_type");
      this->declare_parameter("Lidar_topic");
      this->declare_parameter("gesture_enable");
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
      this->declare_parameter("init_tgt_loc");
      this->declare_parameter("max_dist");
      this->declare_parameter("min_dist");
      this->declare_parameter("max_linear");
      this->declare_parameter("max_angular");
      this->declare_parameter("max_frame_blocked");
      this->declare_parameter("tracking_radius");
#else
      /* From ROS Humble and beyond, declare_parameter() defaultValue is mandatory */
      this->declare_parameter("Lidar_type", std::string("RS"));
      this->declare_parameter("Lidar_topic", std::string("/camera/depth/color/points"));
      this->declare_parameter("gesture_enable", true);
      this->declare_parameter("Verbose", true);
      this->declare_parameter("subsample_ratio", double(15.0));
      this->declare_parameter("x_filter_back", double(3.0));
      this->declare_parameter("y_filter_left", double(2.0));
      this->declare_parameter("y_filter_right" ,double(-2.0));
      this->declare_parameter("z_filter", double(-0.1));
      this->declare_parameter("Z_based_ground_removal", double(1.0));
      this->declare_parameter("base", double(5.29545454));
      this->declare_parameter("coeff_1", double(-0.164835164));
      this->declare_parameter("coeff_2", double(-0.017982017));
      this->declare_parameter("scale_factor", double(0.9));
      this->declare_parameter("init_tgt_loc", double(0.5));
      this->declare_parameter("max_dist", double(1.5));
      this->declare_parameter("min_dist", double(0.5));
      this->declare_parameter("max_linear", double(0.8));
      this->declare_parameter("max_angular", double(0.8));
      this->declare_parameter("max_frame_blocked", int(2));
      this->declare_parameter("tracking_radius", double(0.2));
     
#endif

      rclcpp::Parameter Lidar_type_param = this->get_parameter("Lidar_type");
      rclcpp::Parameter Lidar_topic_param = this->get_parameter("Lidar_topic");
      rclcpp::Parameter gesture_enable_param = this->get_parameter("gesture_enable");
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
      rclcpp::Parameter init_tgt_loc_param = this->get_parameter("init_tgt_loc");
      rclcpp::Parameter max_dist_param = this->get_parameter("max_dist");
      rclcpp::Parameter min_dist_param = this->get_parameter("min_dist");
      rclcpp::Parameter max_linear_param = this->get_parameter("max_linear");
      rclcpp::Parameter max_angular_param = this->get_parameter("max_angular");
      rclcpp::Parameter max_frame_blocked_param = this->get_parameter("max_frame_blocked");
      rclcpp::Parameter tracking_radius = this->get_parameter("tracking_radius");

      Lidar_type_ = Lidar_type_param.as_string();
      Lidar_topic_ = Lidar_topic_param.as_string();
      Verbose_ = Verbose_param.as_bool();
      gesture_enable_ = gesture_enable_param.as_bool();
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
      CONFIG_PARAMS.init_tgt_loc = init_tgt_loc_param.as_double();
      CONFIG_PARAMS.max_dist = max_dist_param.as_double();
      CONFIG_PARAMS.min_dist = min_dist_param.as_double();
      CONFIG_PARAMS.max_linear = max_linear_param.as_double();
      CONFIG_PARAMS.max_angular = max_angular_param.as_double();
      CONFIG_PARAMS.max_frame_blocked = max_frame_blocked_param.as_int();
      CONFIG_PARAMS.tracking_radius = tracking_radius.as_double();

      cout << "Use gesture control: " << gesture_enable_ << endl;
      target_loc.x = CONFIG_PARAMS.init_tgt_loc; //0.5;
      target_loc.y = 0;
      target_loc.z = 0;
      nbr_frame_blocked = CONFIG_PARAMS.max_frame_blocked; //initially set to allow 5 blocked frame
      cout <<"config max_frame_blocked: " << CONFIG_PARAMS.max_frame_blocked << endl;

      cout << "initial target location: " << target_loc.x << endl;
      target_found = false;
      motor_initiated_ = false;
      gesture_category_ = std::string("No_Action"); 

      if (Verbose_)
      {
        RCLCPP_INFO(this->get_logger(), "adbscan_sub_w_gesture_node started; ");
      }
      auto defalt_qos = rclcpp::QoS(rclcpp::SystemDefaultsQoS());
      if(gesture_enable_)
      {
        subscription_gesture_ = this->create_subscription<follow_me_interfaces::msg::GestureCategory>(
            "gesture",
            defalt_qos, 
            std::bind(&MinimalSubscriber::gesture_callback, this, std::placeholders::_1));
      }
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
      //publisher_ = this->create_publisher<nav2_dynamic_msgs::msg::ObstacleArray>("obstacle_array", 1); 
      //publisher_ = this->create_publisher<geometry_msgs::msg::Twist>("turtle1/cmd_vel", 1);  //jcao7
      publisher_ = this->create_publisher<geometry_msgs::msg::Twist>("cmd_vel", 1);
      i += 0.1;
      publisher_markers_ = this->create_publisher<visualization_msgs::msg::MarkerArray>("marker_array",  rclcpp::QoS(1)); 

    }

  private:
    void gesture_callback(const follow_me_interfaces::msg::GestureCategory::SharedPtr _msg)
    {
      RCLCPP_INFO(this->get_logger(), "Subscribing to gesture topic");
      this->gesture_category_ = _msg->gesture_category;
    }
    void topic_2D_callback(const sensor_msgs::msg::LaserScan::SharedPtr _msg) 
    {
      RCLCPP_INFO(this->get_logger(), "Msg: number of input points: '%ld'", (_msg->ranges).size());
      timespec t1, t2;
      clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
      print_info();
      RCLCPP_INFO(this->get_logger(), this->gesture_category_.c_str());
      float current_angle = _msg->angle_min - _msg->angle_increment;
      Point_xyz new_target_loc;
      this->target_found = false;
        
      //vector to hold the point cloud data temporarily before converting to (void *) type
      vector<Point_xyz> point_list;
      int scan_size = _msg->ranges.size();
      
      for (int i=0; i<scan_size; i++  )
      {
        Point_xyz tmp_pt;
        current_angle = current_angle + _msg->angle_increment;
        
        //if (Verbose_) cout << "_msg->ranges["<<i<<"] = " << _msg->ranges[i] << endl;
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
      int result = Convert_vec_pData(point_list, p_Data);

      if (result == 0) //function successful, run ADBSCAN to obtain a list of objects
      {
        vector<Obstacle> obstacles;
        new_target_loc = doDBSCAN(p_Data, point_list.size() *sizeof(LiDAR_data_4D_t), 2, this->target_loc, nbr_frame_blocked, obstacles);
        if (new_target_loc.x  > 0 && this->gesture_category_ == "Thumb_Up")
        {
          this->motor_initiated_ = true;
        }
        if (this->motor_initiated_ && new_target_loc.x > 0 && this->gesture_category_ != "Thumb_Down")
        {
            this->target_loc = new_target_loc;
            this->target_found = true;
        }
        else
        {
            this->target_loc.x = CONFIG_PARAMS.init_tgt_loc; //0.5;
            this->target_loc.y = 0;
            this->target_loc.z = 0;
            this->target_found = false;
            this->nbr_frame_blocked = CONFIG_PARAMS.max_frame_blocked; //5
            this->motor_initiated_ = false;
        }

        publish_message();
        
      }
      else
        RCLCPP_ERROR(this->get_logger(), "Failed to convert input data");
      clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
      cout << "================================================================================"<< std::endl;
      cout << "Total execution time (From reading pointcloud data to publishing twist msg)= "  << diff(t1, t2)*1000 << " [ms]" << std::endl;
      cout << "================================================================================"<< std::endl;
      count_++;
    } 

    void topic_3D_callback(const sensor_msgs::msg::PointCloud2::SharedPtr _msg)
    {
      RCLCPP_INFO(this->get_logger(), "3D Msg received:");
      timespec t1, t2;
      clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
      print_info();

      Point_xyz new_target_loc;
      
      vector<Point_xyz> point_list = PointCloud2_to_point_xyz(_msg);

      //jcao7 for RealSense, go through each point and rotate 
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

      int result = Convert_vec_pData(point_list, p_Data);
      if (result == 0) //convert successful, run ADBSCAN to obtain a list of objects
      {
        vector<Obstacle> obstacles;
        if (Lidar_type_ == "3D")
          new_target_loc = doDBSCAN(p_Data, point_list.size() *sizeof(LiDAR_data_4D_t), 3, this->target_loc, nbr_frame_blocked, obstacles);
        else if (Lidar_type_ == "RS")  //subsampling but not filtering
          new_target_loc = doDBSCAN(p_Data, point_list.size() *sizeof(LiDAR_data_4D_t), 4, this->target_loc, nbr_frame_blocked, obstacles);

        //marker array msg to be publish
        visualization_msgs::msg::MarkerArray markerArr;
        markerArr = Get_MarkerArray(obstacles);
        publisher_markers_->publish(markerArr);
        if (new_target_loc.x  > 0 && this->gesture_category_ == "Thumb_Up")
        {
          this->motor_initiated_ = true;
        }
        if (this->motor_initiated_ && new_target_loc.x > 0 && this->gesture_category_ != "Thumb_Down")
        {
            this->target_loc = new_target_loc;
            this->target_found = true;
        }
        else
        {
            this->target_loc.x = CONFIG_PARAMS.init_tgt_loc; //0.5;
            this->target_loc.y = 0;
            this->target_loc.z = 0;
            this->target_found = false;
            this->nbr_frame_blocked = CONFIG_PARAMS.max_frame_blocked; //5
            this->motor_initiated_ = false;
        }
        cout << "target_found = " << this->target_found << endl;
        cout << "motor_initiated = " << this->motor_initiated_ << endl;
        publish_message();
        /* if (new_target_loc.x  > 0)  //target found; if no target found, new target_loc.x was set to -1
        {
          this->target_loc = new_target_loc;
          this->target_found = true;
        
          //construct and publish Twist message based on this->target_loc;
          publish_message(); //publisher_->publish(ObstacleArr);
        } */
      }
      else
        RCLCPP_ERROR(this->get_logger(), "Failed to convert input data");
      clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
      cout << "================================================================================"<< std::endl;
      cout << "Total execution time (From reading pointcloud data to publishing twist msg)= "  << diff(t1, t2)*1000 << " [ms]" << std::endl;
      cout << "================================================================================"<< std::endl;
      //exit(0); //zzz for debug
      count_++;
        
    } 

    //given this->target_loc 
    void publish_message()
    {
      auto message = geometry_msgs::msg::Twist();

      if( target_found == false) //target not found, set linear and angular velocity to 0.0
      {
        message.linear.x = 0.0;
        message.angular.z = 0.0;

        cout << "target not found, no movement" << endl;
        publisher_->publish(message);
        
        return;
      }
      
      float MAX_ANGULAR = CONFIG_PARAMS.max_angular;
      float MAX_DIST = CONFIG_PARAMS.max_dist;
      float MIN_DIST = CONFIG_PARAMS.min_dist;
      float MAX_LINEAR = CONFIG_PARAMS.max_linear;

      float angular_vel = 0.0;
      float target_angle = atan(target_loc.y/target_loc.x);
      
      cout << "target angle: " << target_angle << endl;
      if (abs(target_angle) > 0.15 ) //angle big enough
        angular_vel = MAX_ANGULAR;
      else
        angular_vel = MAX_ANGULAR*(abs(target_angle)/0.15);

      if (target_loc.y<0)
        angular_vel = -angular_vel;

      message.angular.z = angular_vel;
      // if (Lidar_type_ == "RS")
      //     message.angular.z = -angular_vel;
      // else
      //     message.angular.z = angular_vel;

      float distance = sqrt(target_loc.x*target_loc.x + target_loc.y*target_loc.y);
      RCLCPP_INFO(this->get_logger(), "distance : '%f'", distance);
      if ( distance < MIN_DIST ||  distance > MAX_DIST) //too far or too close, stop linear movement
            message.linear.x = 0.0;
      else if (distance > 1.0)
            message.linear.x = MAX_LINEAR;
      else
            message.linear.x = MAX_LINEAR * (distance - MIN_DIST)/(1.0 - MIN_DIST);

      //message.linear.x = 4.0; //used for testing
      //message.angular.z = 2.0 + i;
      //message.angular.z = 0.0;

      RCLCPP_INFO(this->get_logger(), "Sending - Linear Velocity : '%f', Angular Velocity : '%f'", message.linear.x, message.angular.z);
      publisher_->publish(message);
      //exit(0); //for debug
      i += 0.1; 
    }

    string Lidar_type_;
    string Lidar_topic_;
    bool Verbose_;
    bool gesture_enable_;
    bool motor_initiated_;
    string gesture_category_;// relevant gestures: "No_Action", "Thumb_Up", Thumb_Down"
    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr subscription_2D_; 
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr subscription_3D_; 
    rclcpp::Subscription<follow_me_interfaces::msg::GestureCategory>::SharedPtr subscription_gesture_; 
    //rclcpp::Publisher<nav2_dynamic_msgs::msg::ObstacleArray>::SharedPtr publisher_;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_;
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr publisher_markers_;
    int count_;
    Point_xyz target_loc;
    bool target_found;
    float i; //this can be used to keep track of iteration
    int nbr_frame_blocked; //used for occlusion handling
    clockid_t clk_id = CLOCK_MONOTONIC_RAW; //CLOCK_REALTIME;
};

int main(int argc, char * argv[])
{
  try {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<MinimalSubscriber>());
    rclcpp::shutdown();
  }
  catch (...) {
    std::cerr << "Caught unknown exception" << std::endl;
    rclcpp::shutdown();
    return 1; // Return a non-zero value to indicate an error
  }
  return 0;
}
