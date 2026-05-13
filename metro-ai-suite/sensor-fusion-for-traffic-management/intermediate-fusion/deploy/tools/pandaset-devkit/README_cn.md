# panda64_2_kitti

# 历史日志
    2021-03-03 第一次保存，完成panda64转kitti功能
## 概述

禾塞panda64[PandaSet](https://pandaset.org/ "Pandaset Official Website") 数据集转kitti。
pandaset数据集[下载](https://scale.com/resources/download/pandaset)
pandaset[工具包](https://github.com/scaleapi/pandaset-devkit)代码

## PandaSet数据集说明

### 数据集简介

国内激光雷达制造商禾赛科技与人工智能数据标注平台公司Scale AI联合发布了面向L5级自动驾驶的开源商用数据集——PandaSet数据集。该数据集可用于训练机器学习模型 ，助力自动驾驶的实现。数据集首次同时使用了机械旋转和图像级前向两类激光雷达进行数据采集，输出点云分割结果，并面向科研及商业应用公开。
数据集包括48，000多个摄像头图像和16，000个激光雷达扫描点云图像(超过100个8秒场景)。它还包括每个场景的28个注释和大多数场景的37个语义分割标签。
采集数据车辆为克莱斯勒，传感器套件主要包括1个机械LiDAR，1个固态LiDAR，5个广角摄像头，1个长焦摄像头，板载GPS / IMU。

### 数据集格式说明

数据下载解压后，会出现103个以序列命名的文件夹，不同序列代表不同场景下的数据。
每个序列文件夹又包含4个文件夹，分别是annotations，camera，lidar，meta。
00.pkl.gz~79.pkl.gz 分别对应80帧连续帧的数据，
其格式如下：

```text
.
├── LICENSE.txt
├── annotations
│   ├── cuboids
│   │   ├── 00.pkl.gz
│   │   .
│   │   .
│   │   .
│   │   └── 79.pkl.gz
│   └── semseg  // Semantic Segmentation is available for specific scenes
│       ├── 00.pkl.gz
│       .
│       .
│       .
│       ├── 79.pkl.gz
│       └── classes.json
├── camera
│   ├── back_camera
│   │   ├── 00.jpg
│   │   .
│   │   .
│   │   .
│   │   ├── 79.jpg
│   │   ├── intrinsics.json
│   │   ├── poses.json
│   │   └── timestamps.json
│   ├── front_camera
│   │   └── ...
│   ├── front_left_camera
│   │   └── ...
│   ├── front_right_camera
│   │   └── ...
│   ├── left_camera
│   │   └── ...
│   └── right_camera
│       └── ...
├── lidar
│   ├── 00.pkl.gz
│   .
│   .
│   .
│   ├── 79.pkl.gz
│   ├── poses.json
│   └── timestamps.json
└── meta
    ├── gps.json
    └── timestamps.json
```

### 数据使用说明

pandaset提供了加载数据集的工具包[pandaset-devkit](https://github.com/scaleapi/pandaset-devkit)
安装好工具包后可以直接调用API得到我们想要的数据。

## panda64_2_kitti

pandaset2kitti.py:

```sh

from python.pandaset import DataSet, geometry
from shutil import copyfile
import numpy as np
import math
import sys
import os
import time


CLASS_NAME_TO_ID = {
        'Car': 0,
        'PickupTruck': 1,
        'Medium-sizedTruck': 2,
        'Semi-truck': 3,
        'TowedObject': 4,
        'Motorcycle': 5,
        'OtherVehicle-ConstructionVehicle': 6,
        'OtherVehicle-Uncommon': 7,
        'OtherVehicle-Pedicab': 8,
        'EmergencyVehicle': 27,
        'EmergencyVehicle': 9,
        'Bus': 10,
        'PersonalMobilityDevice': 11,
        'MotorizedScooter': 12,
        'Bicycle': 13,
        'Train': 14,
        'Trolley': 15,
        'Tram': -99,
        'Pedestrian': 16,
        'PedestrianwithObject': 17,      
        'Animals-Bird': 18,
        'Animals-Other': 19,
        'Pylons': 20,
        'RoadBarriers': 21,
        'Signs': 22,
        'Cones': 23,
        'ConstructionSigns': 24,
        'TemporaryConstructionBarriers': 25,
        'RollingContainers': 26,
        'DontCare': -1
    }
ID_TO_CLASS_NAME = {v:k for k,v in CLASS_NAME_TO_ID.items()}      
OBJ_IDD_TO_ID = {'0': 0}
boundary = {
        "minX": 0,
        "maxX": 50,
        "minY": -25,
        "maxY": 25,
        "minZ": -1.5,
        "maxZ": 3.5
    }
    
IS_3D_SHOW = False

if(IS_3D_SHOW):
    import mayavi.mlab
    import mayavi.mlab as mlab
    fig = mayavi.mlab.figure(bgcolor=(0, 0, 0), size=(640, 500))   


    def plot3Dboxes(s):

        p0 = [s[0][0], s[0][1], s[0][2]]
        p1 = [s[1][0], s[1][1], s[1][2]]
        p2 = [s[2][0], s[2][1], s[2][2]]
        p3 = [s[3][0], s[3][1], s[3][2]]
        p4 = [s[4][0], s[4][1], s[4][2]]
        p5 = [s[5][0], s[5][1], s[5][2]]
        p6 = [s[6][0], s[6][1], s[6][2]]
        p7 = [s[7][0], s[7][1], s[7][2]]
        corners1 = np.array( [p0, p1, p2, p3, p0] )
        corners2 = np.array( [p4, p5, p6, p7, p4] )
        corners3 = np.array( [p0, p4, p7, p3, p0] )
        corners4 = np.array( [p1, p2, p6, p5, p1] )
        
        mlab.plot3d(corners1[:,0], corners1[:,1], corners1[:,2], color=(0.23, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners2[:,0], corners2[:,1], corners2[:,2], color=(0.23, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners3[:,0], corners3[:,1], corners3[:,2], color=(0.23, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners4[:,0], corners4[:,1], corners4[:,2], color=(0.23, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        
    def plot3Dboxes1(s):

        p0 = [s[0][0], s[0][1], s[0][2]]
        p1 = [s[1][0], s[1][1], s[1][2]]
        p2 = [s[2][0], s[2][1], s[2][2]]
        p3 = [s[3][0], s[3][1], s[3][2]]
        p4 = [s[4][0], s[4][1], s[4][2]]
        p5 = [s[5][0], s[5][1], s[5][2]]
        p6 = [s[6][0], s[6][1], s[6][2]]
        p7 = [s[7][0], s[7][1], s[7][2]]
        corners1 = np.array( [p0, p1, p2, p3, p0] )
        corners2 = np.array( [p4, p5, p6, p7, p4] )
        corners3 = np.array( [p0, p4, p7, p3, p0] )
        corners4 = np.array( [p1, p2, p6, p5, p1] )
        
        mlab.plot3d(corners1[:,0], corners1[:,1], corners1[:,2], color=(1, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners2[:,0], corners2[:,1], corners2[:,2], color=(1, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners3[:,0], corners3[:,1], corners3[:,2], color=(1, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        mlab.plot3d(corners4[:,0], corners4[:,1], corners4[:,2], color=(1, 0.6, 1), colormap='Spectral', representation='wireframe', line_width=1)
        

    def lidar_show(pc0, labels):
        mayavi.mlab.clf(fig)
        x = pc0[:, 0]  # x position of point
        y = pc0[:, 1]  # y position of point
        z = pc0[:, 2]  # z position of point
        r = pc0[:, 3]  # reflectance value of point
        d = np.sqrt(x ** 2 + y ** 2)  # Map Distance from sensor
        degr = np.degrees(np.arctan(z / d))
        col = z
        mayavi.mlab.points3d(x, y, z,
                             col,  # Values used for Color
                             mode="point",
                             colormap='spectral',  # 'bone', 'copper', 'gnuplot'
                             # color=(0, 1, 0),   # Used a fixed (r,g,b) instead
                             figure=fig,
                             )
        
        
        # 绘制原点
        #mayavi.mlab.points3d(0, 0, 0, color=(1, 1, 1), mode="sphere",scale_factor=1)
        mayavi.mlab.points3d(0, 0, 0, color=(1, 1, 1), mode="sphere",scale_factor=3)
        # 绘制坐标
        axes = np.array(
            [[20.0, 0.0, 0.0, 0.0], [0.0, 20.0, 0.0, 0.0], [0.0, 0.0, 20.0, 0.0]],
            dtype=np.float64,
        )
        #x轴
        mayavi.mlab.plot3d(
            [0, axes[0, 0]],
            [0, axes[0, 1]],
            [0, axes[0, 2]],
            color=(1, 0, 0),
            tube_radius=None,
            figure=fig,
        )
        #y轴
        mayavi.mlab.plot3d(
            [0, axes[1, 0]],
            [0, axes[1, 1]],
            [0, axes[1, 2]],
            color=(0, 1, 0),
            tube_radius=None,
            figure=fig,
        )
        #z轴
        mayavi.mlab.plot3d(
            [0, axes[2, 0]],
            [0, axes[2, 1]],
            [0, axes[2, 2]],
            color=(0, 0, 1),
            tube_radius=None,
            figure=fig,
        )
        
        #obj
        mayavi.mlab.plot3d(
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 0, 0, 1, 1, 0],
            [0, 0, 0, 0, 1, 1, 1, 1],
            color=(1, 0, 0),
            tube_radius=None,
            figure=fig,
        )
        
        '''
        for box in obj_box:
            plot3Dboxes(box)
        '''
        
        box_point = []
        for x, y, z, w, l, h, yaw in labels:
            
            # 　坐标信息
            box = x, y, z, w, l, h, yaw
            # 将中心点，长宽高和航向角信息转变为８个顶点的信息
            corners = geometry.center_box_to_corners(box)
            # 将８个顶点在转换回 中心点，长宽高和航向角
            s = corners
            box_point.append(s)
        
        
        for box in box_point:
            plot3Dboxes1(box)
          
        #mayavi.mlab.show()
        print(pc0.shape)
        myName = input()
        time.sleep(0.1)

def cuboids_to_boxes(cuboids0, poses):
    numb_ob = 0
    sensor1_num = 0
    labels = []
    for i, row in cuboids0.iterrows():
        # cuboids.sensor_id值为-1,0,1，
        # 对于两个雷达重复区域的框用0表示(mechanical 360° LiDAR)，用1表示 (front-facing LiDAR)，其它区域用-1表示
        sensor_id = row["cuboids.sensor_id"]
        if sensor_id == 1:
            sensor1_num += 1
            continue
        # 　坐标信息
        box = row["position.x"], row["position.y"], row["position.z"], row["dimensions.x"], row["dimensions.y"],  row["dimensions.z"], row["yaw"]
        # 将中心点，长宽高和航向角信息转变为８个顶点的信息
        corners = geometry.center_box_to_corners(box)
        # 将８个顶点的坐标位置进行坐标系转换
        rotate_corners = geometry.lidar_points_to_ego(corners, poses)
		
        # 将８个顶点在转换回 中心点，长宽高和航向角
        s = rotate_corners
        # 将obj的x与y调换
        for i in range(len(s)):
            x = s[i][1]
            s[i][1] = s[i][0]
            s[i][0] = x

        p0 = [s[0][0], s[0][1], s[0][2]]
        p1 = [s[1][0], s[1][1], s[1][2]]
        p2 = [s[2][0], s[2][1], s[2][2]]
        p3 = [s[3][0], s[3][1], s[3][2]]
        p4 = [s[4][0], s[4][1], s[4][2]]
        p5 = [s[5][0], s[5][1], s[5][2]]
        p6 = [s[6][0], s[6][1], s[6][2]]
        p7 = [s[7][0], s[7][1], s[7][2]]

        x = (p0[0] + p1[0] + p2[0] + p3[0] + p4[0] + p5[0] + p6[0] + p7[0]) / 8
        y = (p0[1] + p1[1] + p2[1] + p3[1] + p4[1] + p5[1] + p6[1] + p7[1]) / 8
        z = (p0[2] + p1[2] + p2[2] + p3[2] + p4[2] + p5[2] + p6[2] + p7[2]) / 8
        l = math.sqrt(math.pow((p1[0] - p0[0]), 2) + math.pow(p1[1] - p0[1], 2))
        w = math.sqrt(math.pow((p3[0] - p0[0]), 2) + math.pow(p3[1] - p0[1], 2))
        h = math.sqrt(math.pow(p4[2] - p0[2], 2))
        sina = float((p0[0] - p1[0]) / l)
        cosa = float((p0[1] - p1[1]) / l)
        yaw = math.atan(sina / cosa)
        yaw2 = math.atan2(p0[0]- p1[0], p0[1] - p1[1])
        class_label = row["label"]
        class_label = class_label.replace(" ", "")
        uuid = row["uuid"]
        
        
        obj_name = class_label  # 'Car', 'Pedestrian', ...
        if obj_name not in CLASS_NAME_TO_ID:
            continue
        else:
            cat_id = int(CLASS_NAME_TO_ID[obj_name])
            
        if cat_id <= -99:  # ignore Tram and Misc
            continue
            
        idd_tmp = uuid
        idd_dic = 0
        if idd_tmp not in OBJ_IDD_TO_ID:
            idd_length = len(OBJ_IDD_TO_ID)
            OBJ_IDD_TO_ID[idd_tmp] = idd_length
            idd_dic = idd_length
        else:
            idd_dic = int(OBJ_IDD_TO_ID[idd_tmp])           
        
        object_label = [cat_id, idd_dic, x, y, z, w, l, h, np.pi*2 - yaw2, yaw]
        
        labels.append(object_label)  
        numb_ob = numb_ob + 1
        
    # print("sensor1_num:{}".format(sensor1_num))
    return numb_ob, labels

def get_filtered_lidar(lidar, boundary, labels=None):
    minX = boundary['minX']
    maxX = boundary['maxX']
    minY = boundary['minY']
    maxY = boundary['maxY']
    # Remove the point out of range x,y,z
    mask = np.where((lidar[:, 0] >= minX) & (lidar[:, 0] <= maxX) &
                    (lidar[:, 1] >= minY) & (lidar[:, 1] <= maxY))
    lidar = lidar[mask]
    if labels is not None:
        label_x = (labels[:, 2] >= minX) & (labels[:, 2] < maxX)
        label_y = (labels[:, 3] >= minY) & (labels[:, 3] < maxY)
        mask_label = label_x & label_y
        labels = labels[mask_label]
        
        return lidar, labels
    else:
        return lidar
                  
if __name__ == '__main__':
    ''' 坐标系
        xyz:右前上
    '''
    
    root_dir = '/home/l3plus/hegaozhi/data/pandaset/pandaset/pandaset-devkit-master/'
    save_dataset_dir = os.path.join(root_dir, 'dataset', 'kitti')
    mode = "test"
    assert mode in ['train', 'val', 'test'], 'Invalid mode: {}'.format(mode)
    is_test = (mode == 'test')
    sub_folder = 'testing' if is_test else 'training'
    image_dir = os.path.join(save_dataset_dir, sub_folder, "image_2")
    lidar_dir = os.path.join(save_dataset_dir, sub_folder, "velodyne")
    calib_dir = os.path.join(save_dataset_dir, sub_folder, "calib")
    label_dir = os.path.join(save_dataset_dir, sub_folder, "label_2")
    split_txt_path = os.path.join(save_dataset_dir, 'ImageSets', '{}.txt'.format(mode))
    
    split_fd = os.open( split_txt_path, os.O_RDWR|os.O_CREAT )
    #split_fd = os.open( split_txt_path, os.O_RDWR|os.O_APPEND )
    save_file_id = 0
   
    pandaset_dir = os.path.join('../', mode)
    dataset = DataSet(pandaset_dir)
    print('====================================')
    print(dataset.sequences())
    print("序列长度", len(dataset.sequences()))
    print(dataset.sequences(with_semseg=True))
    print("适用于分割的序列长度", len(dataset.sequences(with_semseg=True)))
        
    for sequence in dataset.sequences():
        print("sequence:",sequence)
        # 在先前返回的列表中选择一个来访问特定序列
        seq = dataset[sequence]
        # 将传感器数据和元数据加载到内存中，比较耗时
        # seq.load()
        # 如果只需要雷达数据和对应标签，可以只使用下面的代码加载序列，节约时间
        seq.load_lidar().load_cuboids().load_gps()
        
        # 360°旋转的雷达pandar64
        seq.lidar.set_sensor(0)  # set to include only mechanical 360° LiDAR
        # 固定朝前的雷达pandarGT
        #seq.lidar.set_sensor(1)  # set to include only front-facing LiDAR
        
        
        
        frame_num = len(seq.lidar.data)
        for id in range(frame_num):
            # 获取雷达数据
            pc0 = seq.lidar[id].to_numpy()
            # 获取姿态
            poses = seq.lidar.poses[id]
            # 获取标签
            cuboids0 = seq.cuboids[id] 
            #print(cuboids0.columns)
            # 坐标变换,将世界坐标转lidar坐标
            pc0[:, :3] = geometry.lidar_points_to_ego(pc0[:, :3], poses)
            # x与y坐标转换
            pc0[:,[0,1]]=pc0[:,[1,0]]
            
            
            save_file_id_str = str(save_file_id)
            save_file_id_str = save_file_id_str.zfill(6)
            
            # 获取点云
            lidarData = pc0[:, :4]
            lidarData = lidarData.reshape(-1, 4).astype(np.float32)
            # 获取标签
            numb_ob, labels = cuboids_to_boxes(cuboids0, poses)
            labels = np.array(labels)
            # 获取gps
            calib_str_ret = '{} {} {} {} {}\n'.format(seq.gps[id]['lat'], seq.gps[id]['long'], seq.gps[id]['height'], seq.gps[id]['xvel'], seq.gps[id]['yvel'])
            
            # 滤波:截取前向180度目标
            lidarData, labels = get_filtered_lidar(lidarData, boundary, labels)
            
            # 存储点云
            velodyne_file_new = os.path.join(lidar_dir, save_file_id_str) + '.bin'
            lidarData.tofile(velodyne_file_new)
            # 存储标签
            label_file_new = os.path.join(label_dir, save_file_id_str) + '.txt'
            label_fd = os.open( label_file_new,  os.O_RDWR|os.O_CREAT )
            str_ret = ''
            for cat_id, idd_dic, x, y, z, w, l, h, yaw, yaw2 in labels:
                class_label = ID_TO_CLASS_NAME[cat_id]
                str1 = '{} {} {} {} {} {} {} {} {} {}\n'.format(class_label, idd_dic, x, y, z, w, l, h, yaw, yaw2)
                str_ret = str_ret + str1
            os.write(label_fd, str.encode(str_ret))
            os.close( label_fd )
            # 存储前向camera
            source = os.path.join(pandaset_dir, sequence, 'camera/front_camera' , str(id).zfill(2)) + '.png';
            target = os.path.join(image_dir, save_file_id_str) + '.jpg' 
            copyfile(source, target)
            # gps存储
            gps_file_new = os.path.join(calib_dir, save_file_id_str) + '.txt'
            calib_fd = os.open( gps_file_new,  os.O_RDWR|os.O_CREAT )
            os.write(calib_fd, str.encode(calib_str_ret))
            os.close( calib_fd )
            
            # 文件名称写入字符串
            os.write(split_fd, str.encode(save_file_id_str))
            os.write(split_fd, str.encode("\n"))

            save_file_id = save_file_id + 1
            # 可视化
            if(IS_3D_SHOW):
                lidar_show(lidarData, labels[:,2:9])
            print(save_file_id_str)
            

        # 释放加载
        dataset.unload(seq)

    # 关闭文件
    print('====================================')
    os.close( split_fd )
```

## 3D可视化mayavi

mayavi_view.py

```sh
import numpy as np
import mayavi.mlab
import math
import sys
import os

from numpy import cos,sin,pi,arange
from traits.api import HasTraits,Instance,Range,on_trait_change
from traitsui.api import View,Item,Group
from mayavi.core.ui.api import MayaviScene,SceneEditor,MlabSceneModel
from mayavi.core.api import PipelineBase


fig = mayavi.mlab.figure(bgcolor=(0, 0, 0), size=(640, 500))  
     
def lidar_show(pc0):
    x = pc0[:, 0]  # x position of point
    y = pc0[:, 1]  # y position of point
    z = pc0[:, 2]  # z position of point
    r = pc0[:, 3]  # reflectance value of point
    d = np.sqrt(x ** 2 + y ** 2)  # Map Distance from sensor
    degr = np.degrees(np.arctan(z / d))
    col = z
                                               
    mayavi.mlab.points3d(x, y, z,
                         col,  # Values used for Color
                         mode="point",
                         colormap='spectral',  # 'bone', 'copper', 'gnuplot'
                         # color=(0, 1, 0),   # Used a fixed (r,g,b) instead
                         figure=fig,
                         )
    
    
    # 绘制原点
    mayavi.mlab.points3d(0, 0, 0, color=(1, 1, 1), mode="sphere",scale_factor=1)
    # 绘制坐标
    axes = np.array(
        [[20.0, 0.0, 0.0, 0.0], [0.0, 20.0, 0.0, 0.0], [0.0, 0.0, 20.0, 0.0]],
        dtype=np.float64,
    )
    #x轴
    mayavi.mlab.plot3d(
        [0, axes[0, 0]],
        [0, axes[0, 1]],
        [0, axes[0, 2]],
        color=(1, 0, 0),
        tube_radius=None,
        figure=fig,
    )
    #y轴
    mayavi.mlab.plot3d(
        [0, axes[1, 0]],
        [0, axes[1, 1]],
        [0, axes[1, 2]],
        color=(0, 1, 0),
        tube_radius=None,
        figure=fig,
    )
    #z轴
    mayavi.mlab.plot3d(
        [0, axes[2, 0]],
        [0, axes[2, 1]],
        [0, axes[2, 2]],
        color=(0, 0, 1),
        tube_radius=None,
        figure=fig,
    )
    #mayavi.mlab.show()
    print(pc0.shape)
    
if __name__ == '__main__':
    pointcloud = np.fromfile(str("/home/l3plus/hegaozhi/data/pandaset/pandaset/pandaset-devkit-master/000000.bin"), dtype=np.float32, count=-1).reshape([-1, 4])
    lidar_show(pointcloud)
    myName = input()
    pointcloud = np.fromfile(str("/home/l3plus/hegaozhi/data/pandaset/pandaset/pandaset-devkit-master/000001.bin"), dtype=np.float32, count=-1).reshape([-1, 4])
    print('--')
    lidar_show(pointcloud)
    myName = input()
    
    
```

## 3D可视化pcl

```sh

import numpy as np
import pcl.pcl_visualization
import time
# lidar_path 指定一个kitti 数据的点云bin文件就行了
points = np.fromfile("/home/l3plus/hegaozhi/data/pandaset/pandaset/pandaset-devkit-master/000000.bin", dtype=np.float32).reshape(-1, 4)  # .astype(np.float16)


# 这里对第四列进行赋值，它代表颜色值，根据你自己的需要赋值即可；
#points[:, 3] =  points[:, 2]
# PointCloud_PointXYZRGB 需要点云数据是N*4，分别表示x,y,z,RGB ,其中RGB 用一个整数表示颜色；
color_cloud = pcl.PointCloud_PointXYZI(points)

visual = pcl.pcl_visualization.CloudViewing()
visual.ShowGrayCloud(color_cloud, b'cloud')
print('+++')
time.sleep(100)
visual.ShowGrayCloud(color_cloud, b'cloud')
print('+++')
time.sleep(100)
print('+++')
visual.ShowGrayCloud(color_cloud, b'cloud')
print('+++')
time.sleep(100)

#flag = True
#while flag:
#    flag != visual.WasStopped()

```

