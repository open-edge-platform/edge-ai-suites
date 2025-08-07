# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits import mplot3d
from KITTI_Utils import *
import sys

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
 
def print_frame(frame): #print all info in a frame
    print('frame info:')
    print('frame size:', len(frame.cluster_list))
    output_file = open('centroid_file.txt','w')
    for cluster in frame.cluster_list:
        print('centroid:', cluster.centroid)
        print('cluster.cluster_nbr, size:', cluster.cluster_nbr, len(cluster.point_list))
        output_str = str(cluster.cluster_nbr)+','+str(cluster.centroid[0])+','+str(cluster.centroid[1])+','+ str(cluster.centroid[2])+'\n'
        output_file.write(output_str)
        
    output_file.close()
    return
    
def plot_frame(frame):
    #first sort the cluster by size
    cluster_by_size = dict() #key is cluster number, value is size
    
    clusters = frame.cluster_list
    #put cluster ID and size into dictionary
    for cluster in clusters:
        cluster_by_size[cluster.cluster_nbr] = cluster.size
    
    #key/value pair of cluster_nbr/size; only need first 12
    sorted_cluster = sorted(cluster_by_size.items(), key=lambda item:item[1], reverse=True)
    print('sorted_cluster: ', sorted_cluster)
    cluster_to_plot = sorted_cluster[:12] #only plot 12 largest cluster
    cluster_nbr_to_plot = [x[0] for x in cluster_to_plot]
    print('cluster_nbr_to_plot:', cluster_nbr_to_plot) #cluster_nbr
    #plot the first 12 clusters order by size

    fig = plt.figure()
    ax = plt.axes(projection='3d')
    
    tracking_obj = {16:1, 15:2, 12:3}
        
    for cluster in clusters: #one iteration for one cluster
        xdata = []
        ydata = []
        zdata = []
      
        for idx in range(len(clusters)):
  
            points = cluster.point_list
            if len(points) > 20: 
                draw_BB_Points(fig, ax, points, 'red')
                
                xdata = [x[0] for x in points]
                ydata = [x[1] for x in points]
                zdata = [x[2] for x in points]
                
                ax.scatter3D(xdata, ydata, zdata, c='blue')
                ax.text(cluster.centroid[0]+0.5, cluster.centroid[1]-0.9, cluster.centroid[2], cluster.cluster_nbr, color='#b40426', size = 16)
    
             
    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')
    
    plt.title('3D Cluster Plot')
    plt.show()

######################   main  ################        
if __name__ == "__main__":

    cluster_nbr = 0
    #find the largest 12 clusters and plot them
    cluster_size =[] 
    max_cluster_nbr = 0
    frame_files = [] #frames to be loaded; each file contains a frame data
    #frame_files.append('2011-09-26-drive-0005-sync-0-9_DBSCAN_results.txt') #add all consecutive input frame  
    frame_files.append(str(sys.argv[1]))
    cur_frame_nbr = 0 #first frame       
    frames = []
    for file_name in frame_files:   
        print ('open %s to read'%file_name)
        frame_file = open(file_name)
        #everything here is in one frame
        cur_frame = Frame(cur_frame_nbr) #create a new frame object
        
        clusters = [] #empty cluster list for all clusters in current frame
        for line in frame_file:
            col = line.split(' ')
            col_num = len(col)
            cluster_nbr = int(col[4])
            if cluster_nbr > 0:  #valid cluster

                pt = (float(col[1]),float(col[2]),float(col[3])) #point value, to be appended to point_list
                
                if len(clusters) == 0: #emply cluster list, first cluster in the frame
                    cur_cluster = Cluster() #create cluster object and set values 
                    cur_cluster.cluster_nbr = cluster_nbr
                    cur_cluster.add_point(pt)
                    if cur_frame_nbr == 0:  #first frame
                        cur_cluster.object_ID = cluster_nbr
                        
                    clusters.append(cur_cluster)
                    
                else: #traverse the point_list to find same cluster number     
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

            for each_cluster in clusters:
                each_cluster.set_centroid()
                each_cluster.set_bottom()
                each_cluster.set_size()
                
            #attach clusters to frame object   
            cur_frame.cluster_list = clusters  #attach clusters[] to frame
        frames.append(cur_frame)
        print_frame(frames[0])
        plot_frame(frames[0])
        
        

