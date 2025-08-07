#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
"""
Author: Ming
"""
from __future__ import print_function
import time, sys, os
from ros import rosbag
import roslib
import rospy
roslib.load_manifest('sensor_msgs')
from sensor_msgs.msg import CameraInfo   

def CreateBag(args):# Directory
 
    '''Creates a bag file with camera images'''
    if not os.path.exists(args[1]):
        os.system(r'touch %s' % args[1])
    bag = rosbag.Bag(args[1], 'w')   

    #camera_info msg.  just copy from file. TODO: read from yaml file
    color_camera_info_msg = CameraInfo()
    color_camera_info_msg.header.frame_id = "color"
    color_camera_info_msg.height  = 480
    color_camera_info_msg.width = 752
    color_camera_info_msg.K = [458.654, 0, 367.215, 0, 457.296, 248.375, 0, 0, 1]
    color_camera_info_msg.D = [-0.28340811, 0.07395907, 0.00019359, 1.76187114e-05, 0.]
    color_camera_info_msg.distortion_model = "Brown Conrady"
    
    Stamp = rospy.rostime.Time.from_sec(100000000)
    for i in range (1,10):
        color_camera_info_msg.header.stamp = rospy.get_rostime()
        bag.write('/cam0/camera_info', color_camera_info_msg, Stamp)
        time.sleep(1)

    bag.close()

if __name__ == "__main__":
      print(sys.argv)
      rospy.init_node("convert_camera_info")
      CreateBag(sys.argv[0:])


