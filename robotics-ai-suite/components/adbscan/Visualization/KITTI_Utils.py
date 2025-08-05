# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#Created by Jun Cao on 6/22/21
#This set of tools contains common tools used for lidar point cloud processing
#Tested on Kitti dataset, and can be used for other point cloud processing tasks
#Modification may be needed when use

import numpy as np
import math
import cv2
from mpl_toolkits import mplot3d
import matplotlib.pyplot as plt

#read config
#the config file format is name = value
def read_config(fname): #return a dictionary of name/value pair
    config_dict = dict()
    with open(fname,'r') as config_file:
        for line in config_file: 
            col = line.split('=')
            name = col[0].strip()
            value = col[1].strip()
            config_dict[name] = value
    return config_dict

#This is to read bin file containing lidar scan data
def read_bin_file(bin_file):
    #read point cloud data into the pointcloud list
    pointcloud = np.fromfile(bin_file, dtype=np.float32, count=-1).reshape([-1,4])
    
    #read in a seperate list of x,y,z,r 
    print(pointcloud.shape)
    x = pointcloud[:, 0]  # x position of point
    y = pointcloud[:, 1]  # y position of point
    z = pointcloud[:, 2]  # z position of point
    r = pointcloud[:, 3]  # reflectance value of point
    d = np.sqrt(x ** 2 + y ** 2)  # Map Distance from sensor

    print(x[100], y[100],z[100], r[100], d[100])
    
    #or read it into a list of 3D point
    points = pointcloud[:, 0:3]
    
#Read the transformation matrix from calib file and return the matrix
def read_calib(calib_file):
    with open(calib_file) as f:
        calib = f.readlines()
        
    P2 = np.matrix([float(x) for x in calib[2].strip('\n').split(' ')[1:]]).reshape(3,4)
    R0_rect = np.matrix([float(x) for x in calib[4].strip('\n').split(' ')[1:]]).reshape(3,3)
    # Add a 1 in bottom-right, reshape to 4 x 4
    R0_rect = np.insert(R0_rect,3,values=[0,0,0],axis=0)
    R0_rect = np.insert(R0_rect,3,values=[0,0,0,1],axis=1)
    Tr_velo_to_cam = np.matrix([float(x) for x in calib[5].strip('\n').split(' ')[1:]]).reshape(3,4)
    Tr_velo_to_cam = np.insert(Tr_velo_to_cam,3,values=[0,0,0,1],axis=0)

    return Tr_velo_to_cam
    
def calc_centroid(point_list):
    total_x = total_y = total_z = 0.0
    cluster_size = len(point_list)
    for pt in point_list:
        total_x += pt[0]
        total_y += pt[1]
        total_z += pt[2]
    centroid = (total_x/cluster_size, total_y/cluster_size, total_z/cluster_size)
    
    return centroid
    
def calc_bottom(point_list):
    total_x = total_y = min_z = 0.0
    cluster_size = len(point_list)
    for pt in point_list:
        total_x += pt[0]
        total_y += pt[1]
        if pt[2] < min_z:
            min_z = pt[2]
    bottom = (total_x/cluster_size, total_y/cluster_size, min_z)
    
    return bottom
    
class Frame:
    def __init__(self, frame_nbr):
        self.cluster_list = []
        self.frame_nbr = frame_nbr
        self.size = 0
        
    def add_cluster(self, new_cluster):
        self.cluster_list.append(new_cluster)
        self.size = len(self.cluster_list)
    
class Cluster:
    def __init__(self):
        self.point_list = []
        self.centroid = (0,0,0)  #centrod of the point list
        self.bottom = (0,0,0)
        self.cluster_nbr = 0 #read from input, unique to frame
        self.obj_ID = -1 #matched with prevous frame, unique to video sequence
        self.size = 0 #number of points in the cluster
        
    def add_point(self, pt):
        self.point_list.append(pt)
        
    def set_size(self):
        self.size =  len(self.point_list)
        
    def set_centroid(self):
        self.centroid = calc_centroid(self.point_list)

    def set_bottom(self):
        self.bottom = calc_bottom(self.point_list)
           
#plot lidar point cloud data in a given color
#arr_x,arr_y,arr_z are 1-d list of coordinates, 
def plot_point_cloud_3D(arr_x, arr_y, arr_z, color):
    fig = plt.figure()
    ax = plt.axes(projection='3d')
    ax.scatter3D(arr_x, arr_y, arr_z, c=color)
    ax.set_title('3D line plot')
    plt.show()
    
#plot a line in 3D space in a given color
def plot_3D_line(arr_x, arr_y, arr_z, color):
    fig = plt.figure()
    ax = plt.axes(projection='3d')
    ax.plot3D(arr_x, arr_y, arr_z, c=color)
    ax.set_title('3D line plot')
    plt.show()
    
#given 2 corners, draw 3D bounding box
def draw_3D_BBox(fig, ax, top_corner, bottom_corner, color):
    
    x0 = bottom_corner[0]
    x1 = top_corner[0]
    y0 = bottom_corner[1]
    y1 = top_corner[1]
    z0 = bottom_corner[2]
    z1 = top_corner[2]
    
    b0 = (x0, y0, z0)
    b1 = (x0, y1, z0)
    b2 = (x1, y1, z0)
    b3 = (x1, y0, z0)
    
    t0 = (x0, y0, z1)
    t1 = (x0, y1, z1)
    t2 = (x1, y1, z1)
    t3 = (x1, y0, z1)
    
    #fig = plt.figure()
    #ax = plt.axes(projection = '3d')
    #draw top rectangle
    ax.plot3D([t0[0],t1[0],t2[0],t3[0],t0[0]],[t0[1],t1[1],t2[1],t3[1],t0[1]], [t0[2],t1[2],t2[2],t3[2],t0[2]], c=color)
    ax.plot3D([b0[0],b1[0],b2[0],b3[0],b0[0]],[b0[1],b1[1],b2[1],b3[1],b0[1]], [b0[2],b1[2],b2[2],b3[2],b0[2]], c=color)
    ax.plot3D([b0[0],t0[0]],[b0[1],t0[1]],[b0[2],t0[2]],c=color)
    ax.plot3D([b1[0],t1[0]],[b1[1],t1[1]],[b1[2],t1[2]],c=color)
    ax.plot3D([b2[0],t2[0]],[b2[1],t2[1]],[b2[2],t2[2]],c=color)
    ax.plot3D([b3[0],t3[0]],[b3[1],t3[1]],[b3[2],t3[2]],c=color)
    
    #ax.set_title('3D Bounding Box')
    #plt.show()  
    
#given a cluster of points, draw 3D bounding box
def draw_BB_Points(fig, ax, points, color):    
    point_list = points
    X_list = []
    Y_list = []
    Z_list = []
    for pt in point_list:
        X_list.append(pt[0])
        Y_list.append(pt[1])
        Z_list.append(pt[2])
            
    topCorner = (max(X_list), max(Y_list), max(Z_list))
    bottomCorner = (min(X_list), min(Y_list), min(Z_list))
    draw_3D_BBox(fig, ax, topCorner, bottomCorner, color)    
    
#Create a top view of 3D image by projecting to x,y plane
#given a list of points in 3D, return a list of points in x,y plane
#Input point is 3D (x,y,z) tuple, return (x,y)    
def top_view(points_3D):
    points_2D = []
    for point in points_3D:
        points_2D.append(point[0], point[1])
    return points_2D

#Calculate the Euclidean distance between two 3D points   
#the point is (x,y,z,reflex,obj_ID), obj_ID is refereded by pt[-1]
#only use the first 3 values in tuple for location
def dist(pt1, pt2):
    return math.sqrt((pt1[0]-pt2[0])**2+(pt1[1]-pt2[1])**2 +(pt1[2]-pt2[2])**2 )

#return color code for a given number of colors
def get_color_progressive(color_code, nbr):
    color = (255, 255, 0)
    colors = []
    for i in range(nbr):
        colors.append(color)
        
    return colors[color_code]

#measure the cosine similarity between 2 vectors    
def cosine_sim(vec1, vec2):
    vec_len = len(vec1)
    sum = 0
    for idx in range(vec_len):
        sum += vec1[idx]*vec2[idx]

    return match.sqrt(sum)
    
    
#measure the weighted similarity between vectors
#vec1, vec2, coeff are 1-D vector with same size
def weighted_sim(vec1, vec2, coeff): 
    vec_len = len(vec1)
    sum = 0
    for idx in range(vec_len):
        sum += coeff[idx]*vec1[idx]*vec2[idx]

    return match.sqrt(sum)

#read ADBSCAN result txt file into Frame object
def read_frame_file(file_name):
    print ('open %s to read'%file_name)
    frame_file = open(file_name)
    #everything here is in one frame
    #cur_frame = Frame(cur_frame_nbr) #create a new frame object
    
    clusters = [] #empty cluster list for all clusters in current frame
    for line in frame_file:
        col = line.split(' ')
        col_num = len(col)
        cluster_nbr = int(col[4])
        if cluster_nbr > 0:  #valid cluster
            #print('x,y,z:',col[1],col[2],col[3])
            pt = (float(col[1]),float(col[2]),float(col[3]), 0) #point value, to be appended to point_list
            #print ('total cluster number:', len(clusters))
            if len(clusters) == 0: #emply cluster list, first cluster in the frame
                cur_cluster = Cluster() #create cluster object and set values 
                cur_cluster.cluster_nbr = cluster_nbr
                cur_cluster.add_point(pt)
                #if cur_frame_nbr == 0:  #first frame
                #    cur_cluster.object_ID = cluster_nbr
                #cur_frame.add_cluster(cur_cluster) #add cluster to the frame
                
                clusters.append(cur_cluster)
                print('cur_cluster number of points:', len(cur_cluster.point_list))
            else: #traverse the point_list to find same cluster number
                  #if cluster found, append point to it              
                cluster_nbr_found = False
                for iter in clusters:
                    if iter.cluster_nbr == cluster_nbr: #matched, add to existing cluster
                        iter.add_point(pt)
                        cluster_nbr_found = True
                if cluster_nbr_found == False: # not found, create a new cluster
                    cur_cluster = Cluster() #create cluster object and set values
                    cur_cluster.cluster_nbr = cluster_nbr
                    cur_cluster.add_point(pt)
                    
                    clusters.append(cur_cluster)

        for cluster in clusters: #set the properties for each cluster
            cluster.set_centroid()
            cluster.set_bottom()
            cluster.set_size()

    return clusters

    
#-----------  test driver to demostrate the usage  --------------
if __name__ == '__main__':
    #read_bin_file('0000000000.bin')
    # sample results:
    #(121015, 4)
    #32.325 15.034 1.415 0.34 35.65006

    #test point cloud plot
    #x = [1,2,3,4,5]
    #y = [3,2,3,0,4]
    #z = [3,4,0,5,2]
    #plot_point_cloud_3D(x, y, z, 'red')

    #test plot a line
    #x = np.linspace(5,5,50)
    #y = np.linspace(0,20,50)
    #z = np.linspace(0,25,50)
    #plot_3D_line(x, y, z, 'green')
    fig = plt.figure()
    ax = plt.axes(projection = '3d')
    #print(read_calib('calib_velo_to_cam.txt'))
    #test bounding box
    draw_3D_BBox(fig, ax, (9,9,9), (0,0,0), 'blue')
    #points = [(1,3,3), (2,2,4), (3,3,0)]
    #draw_BB_Points(fig, ax, points, 'blue')
    ax.set_title('3D Bounding Box')
    plt.show()  
    
    #print(read_config('config.txt'))
    #cluster_list = read_frame_file('2011-09-26-drive-0005-sync-0-1_DBSCAN_results.txt')
    #print('cluster list size:', len(cluster_list))
    #for each_cluster in cluster_list:
    #    print (each_cluster.centroid)
    #    features = Feature(each_cluster)
    #    features.set_features()
    #    print('cluster height: ', features.height)
    #    print('cluster length: ', features.length)
     #   print(' ')
        #get cluster features
        