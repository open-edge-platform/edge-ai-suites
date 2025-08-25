#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
"""
Transform image and imu files to a ros bag file
usage  convert_files_to_bag.py [directory]
file folder:
    [color]  [depth] IMU.txt TIMESTAMP.txt
example: FMDataset
Author: Ming Ouyang
"""
from __future__ import print_function
import time
import cv2
import time, sys, os
from ros import rosbag
import roslib
import rospy
roslib.load_manifest('sensor_msgs')
from sensor_msgs.msg import Image,Imu
import realsense2_camera.msg 
from geometry_msgs.msg import Vector3
import numpy as np
from numpy import asarray
from cv_bridge import CvBridge
from PIL import ImageFile
from PIL import Image as ImagePIL
from sensor_msgs.msg import CameraInfo
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped

def quaternion_to_rotation_matrix(quat):
  
  print ("q: ", quat)
  w = quat[0]
  x = quat[1]
  y = quat[2]
  z = quat[3]
  y2 = y * y
  x2 = x * x
  z2 = z * z
  xy = x * y
  xz = x * z
  yw = y * w
  zw = z * w
  yz = y  * z
  xw = x * w

  rot_matrix =[[1.0 - 2 * y2 - 2 * z2, 2 * xy - 2 * zw, 2 * xz + 2 * yw],
              [2 * xy + 2 * zw, 1.0 - 2 * x2 - 2 * z2,  2*yz - 2 * xw],
              [2 * xz - 2 * yw, 2*yz + 2 * xw, 1.0 - 2 * x2 - 2 * y2]]
  return rot_matrix

def transform_point(R, t, p_from):
    p_to =[ R[0][0] * p_from[0] + R[0][1] * p_from[1] + R[0][2] * p_from[2]+ t[0],
            R[1][0] * p_from[0] + R[1][1] * p_from[1] + R[1][2] * p_from[2]+ t[1],
            R[2][0] * p_from[0] + R[2][1] * p_from[1] + R[2][2] * p_from[2]+ t[2]]
    return p_to


    

def CompSortFileNamesNr(f):
    g = os.path.splitext(os.path.split(f)[1])[0] #get the file of the
    numbertext = ''.join(c for c in g if c.isdigit())
    return int(numbertext)

def ReadImages(filename):
    '''Generates a list of files from the directory'''
    print("Reading image file path from directory %s" % filename+"/TIMESTAMP.txt")
    file = open(filename+"/TIMESTAMP.txt",'r')
    all = file.readlines()
    timestamp = []
    images = []
    index = 0
    for f in all:
        index = index + 1
        if index == 1:
            continue
        line = f.rstrip('\n').split(',')
        timestamp.append(line[0])
        images.append(line[1])
    print("Total add %i images!"%(index))
    return images,timestamp

def ReadIMU(filename):
    '''return IMU data and timestamp of IMU'''
    file = open(filename + "/IMU.txt",'r')
    all = file.readlines()
    timestamp = []
    imu_data = []
    index = 0
    for f in all:
        index = index + 1
        if index == 1:
            continue
        line = f.rstrip('\n').split(',')
        timestamp.append(line[0])
        imu_data.append(line[1:])
    print("Total add %i imus!"%(index))
    return timestamp,imu_data





def CreateBag(args):# Directory
    '''read time stamps'''
    imutimesteps,imudata = ReadIMU(args[0]) #the url of  IMU data
    rgbd_imgs, rgbdtimestamps = ReadImages(args[0])  #sychrilized rgb and depth image has the same timestamp and name
    '''Creates a bag file with camera images'''
    if not os.path.exists(args[1]):
        os.system(r'touch %s' % args[1])
    bag = rosbag.Bag(args[1], 'w')

    align_depth_to_color = False
    if len(args) ==3:
        align_depth_to_color = args[2]
    
    depth_scale = 0.001

    filename = args[0] + "/"

    align_depth_image_dir = args[0] +"/align_depth_image"
    if align_depth_to_color:
        if not os.path.exists(align_depth_image_dir):
            os.mkdir(align_depth_image_dir)
    align_depth_image_dir=args[0]+'/align_depth_image/'
    print("align_depth_image_dir: ", align_depth_image_dir)


    #camera_info msg.  just copy from file. TODO: read from yaml file

    color_camera_info_msg = CameraInfo()
    color_camera_info_msg.header.frame_id = "color"
    color_camera_info_msg.height  = 480
    color_camera_info_msg.width = 640
    color_camera_info_msg.K = [608, 0, 331, 0, 608, 246, 0, 0, 1]
    color_camera_info_msg.D = [0.0644, -0.114, 0.00127, 0.00203, 0.]
    color_camera_info_msg.distortion_model = "plumb_bob"
    
    depth_camera_info_msg = CameraInfo()
    depth_camera_info_msg.header.frame_id = "depth"
    depth_camera_info_msg.height  = 480
    depth_camera_info_msg.width = 640
    depth_camera_info_msg.K = [583, 0, 325, 0, 583, 240, 0, 0, 1]
    depth_camera_info_msg.distortion_model = "plumb_bob"

    # GyroInfo_msg = realsense2_camera.msg._IMUInfo()
    # GyroInfo_msg.frame_id = "gyro"
    # GyroInfo_msg.bias_variances=[5e-7, 5e-7,5e-7]
    # GyroInfo_msg.noise_variances = [0.147,0.147,0.147]

    # AccelInfo_msg=realsense2_camera.msg._IMUInfo()
    # AccelInfo_msg.frame_id = "accel"
    # AccelInfo_msg.bias_variances=[0.001,0.001,0.001]
    # AccelInfo_msg.noise_variances = [0.000244,0.000244,0.000244]

    depth2color_extrinsic_msg = TransformStamped()
    depth2color_extrinsic_msg.child_frame_id="color"
    depth2color_extrinsic_msg.header.frame_id = "depth"
    depth2color_extrinsic_msg.transform.rotation.w= 1.0
    depth2color_extrinsic_msg.transform.rotation.x= 0.0
    depth2color_extrinsic_msg.transform.rotation.y= 0.0 
    depth2color_extrinsic_msg.transform.rotation.z= 0.0
    depth2color_extrinsic_msg.transform.translation.x=-0.057460
    depth2color_extrinsic_msg.transform.translation.y=-0.001073
    depth2color_extrinsic_msg.transform.translation.z=-0.002205


    color2imu_extrinsic_msg = TransformStamped()
    color2imu_extrinsic_msg.child_frame_id="imu"
    color2imu_extrinsic_msg.header.frame_id = "color"
    color2imu_extrinsic_msg.transform.rotation.w= 0.999991
    color2imu_extrinsic_msg.transform.rotation.x= -0.0028654
    color2imu_extrinsic_msg.transform.rotation.y= -0.0031236
    color2imu_extrinsic_msg.transform.rotation.z= 0.0003588
    color2imu_extrinsic_msg.transform.translation.x=-0.080775
    color2imu_extrinsic_msg.transform.translation.y= 0.001211
    color2imu_extrinsic_msg.transform.translation.z=-0.002030


    extrinsic_msg = TFMessage()
    extrinsic_msg.transforms.append(depth2color_extrinsic_msg)
    extrinsic_msg.transforms.append(color2imu_extrinsic_msg)

    fx_depth = depth_camera_info_msg.K[0]
    fy_depth=depth_camera_info_msg.K[4]
    cx_depth = depth_camera_info_msg.K[2]
    cy_depth=depth_camera_info_msg.K[5]

    k1 = color_camera_info_msg.D[0]
    k2 = color_camera_info_msg.D[1]
    p1 = color_camera_info_msg.D[2]
    p2 = color_camera_info_msg.D[3]

    fx_color = color_camera_info_msg.K[0]
    fy_color = color_camera_info_msg.K[4]
    cx_color = color_camera_info_msg.K[2]
    cy_color = color_camera_info_msg.K[5]

    pose_quaternion = [float(depth2color_extrinsic_msg.transform.rotation.w), float(depth2color_extrinsic_msg.transform.rotation.x), float(depth2color_extrinsic_msg.transform.rotation.y), float(depth2color_extrinsic_msg.transform.rotation.z)]
    t = [float(depth2color_extrinsic_msg.transform.translation.x),float(depth2color_extrinsic_msg.transform.translation.y),float(depth2color_extrinsic_msg.transform.translation.z)]
    R = quaternion_to_rotation_matrix(pose_quaternion)
    print("pose_quaternion", pose_quaternion)
    print("t,", t)
    print("R:", R)

    try:
        for i in range(len(imudata)):
            imu = Imu()
            angular_v = Vector3()
            linear_a = Vector3()
            if len(imudata[i])<6:
                continue
            angular_v.x = float(imudata[i][0])
            angular_v.y = float(imudata[i][1])
            angular_v.z = float(imudata[i][2])
            linear_a.x = float(imudata[i][3])
            linear_a.y = float(imudata[i][4])
            linear_a.z = float(imudata[i][5])
            imuStamp = rospy.rostime.Time.from_sec(float(imutimesteps[i])/ 1000000)  # according to the timestamp unit
            imu.header.stamp=imuStamp
            imu.angular_velocity = angular_v
            imu.linear_acceleration = linear_a

            bag.write("imu",imu,imuStamp)


        '''read image size'''
        total_img_num = len(rgbd_imgs)
        for i in range(total_img_num):
            #Adding depth image
            Stamp = rospy.rostime.Time.from_sec(float(rgbdtimestamps[i])/ 1000000)  # Modify according to your own time unit
            '''set image information '''
            depth_image = ImagePIL.open(filename+"depth/"+ rgbd_imgs[i])
            br = CvBridge()
            data = asarray(depth_image)
            depth_image_msg = br.cv2_to_imgmsg(data)  # Convert the depth image to a message
            depth_image_msg.header.stamp = Stamp
            depth_image_msg.header.frame_id = "camera"
            bag.write('camera/depth', depth_image_msg, Stamp)

            rgb_image = ImagePIL.open(filename+"color/"+ rgbd_imgs[i])
            data = asarray(rgb_image)
            rgb_image_msg = br.cv2_to_imgmsg(data)  # Convert the color image to a message
            rgb_image_msg.header.stamp = Stamp
            rgb_image_msg.header.frame_id = "camera"
            rgb_image_msg.encoding = "rgb8"
            bag.write('camera/color', rgb_image_msg, Stamp)

            if i==0:
                print("Depth image mode: ", depth_image.mode)
            
            if align_depth_to_color:              
                align_depth_to_color_image = ImagePIL.new(depth_image.mode, (color_camera_info_msg.width, color_camera_info_msg.height), (0)) 
                for u in range(depth_camera_info_msg.width):
                    for v in range(depth_camera_info_msg.height):
                        u32_depth = depth_image.getpixel((u,v))
                        if u32_depth ==0:
                            continue
                        depth = float(u32_depth) * 0.001
                        position_in_depth_frame = [ (u- cx_depth)*depth / fx_depth, (v- cy_depth)*depth / fy_depth , depth]
                        position_in_color_frame = transform_point(R,t, position_in_depth_frame)
                        position_in_norm_color_frame = [position_in_color_frame[0]/position_in_color_frame[2], position_in_color_frame[1]/position_in_color_frame[2]]
                        # distortion
                        x = position_in_norm_color_frame[0]
                        y = position_in_norm_color_frame[1]
                        x2 = x * x
                        y2 = y * y
                        r2 = x2 + y2
                        r4 = r2 * r2
                        xy = x * y
                        x_distorted = x * (1 + k1 * r2 + k2 * r4) + 2*p1 * x*y+p2*(r2 + 2 * x2)
                        y_distorted = y * (1 + k1 * r2 + k2 * r4) + 2*p2 * x*y+p1*(r2 + 2 * y2)
                        #re-project to color image frame
                        
                        u_image = int (x_distorted  * fx_color + cx_color)
                        v_image = int(y_distorted  * fy_color + cy_color)
                        if u_image>=0 and u_image < align_depth_to_color_image.width and v_image >=0 and v_image < align_depth_to_color_image.height:
                            align_depth_to_color_image.putpixel((u_image,v_image), u32_depth)
                data = asarray(align_depth_to_color_image)
                align_depth_to_color_image.save(align_depth_image_dir + rgbd_imgs[i] )
                align_depth_to_color_image_msg = br.cv2_to_imgmsg(data)  # Convert the image to a message
                align_depth_to_color_image_msg.header.stamp = Stamp
                align_depth_to_color_image_msg.header.frame_id = "camera"
                align_depth_to_color_image_msg.encoding = depth_image_msg.encoding
                bag.write('camera/align_depth_to_color', align_depth_to_color_image_msg, Stamp)


            if i%20==0:
                depth_camera_info_msg.header.stamp = Stamp
                bag.write('camera/depth_image_info', depth_camera_info_msg, Stamp)
                color_camera_info_msg.header.stamp = Stamp
                bag.write('camera/color_image_info', color_camera_info_msg, Stamp)
                # GyroInfo_msg.header.stamp = Stamp
                # bag.write('imu/gyro', GyroInfo_msg, Stamp)
                # AccelInfo_msg.header.stamp = Stamp
                # bag.write('imu/accel', AccelInfo_msg, Stamp)
                extrinsic_msg.transforms[0].header.stamp = Stamp
                extrinsic_msg.transforms[1].header.stamp = Stamp
                if not align_depth_to_color:
                    print('\r Progress: {0}{1}%'.format('*'*(i/20),( (float(i) * 100)/ (float(total_img_num))  )), end='')
            if align_depth_to_color:
                print('\r Progress: {0}{1}%'.format('*'*(i/20),( (float(i) * 100)/ (float(total_img_num))  )), end='')

    finally:
        bag.close()

if __name__ == "__main__":
      print(sys.argv)
      CreateBag(sys.argv[1:])
