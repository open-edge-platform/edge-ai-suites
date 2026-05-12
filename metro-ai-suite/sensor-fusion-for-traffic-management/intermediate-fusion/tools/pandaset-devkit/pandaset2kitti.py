from python.pandaset import DataSet, geometry
from shutil import copyfile
import numpy as np
import math
import sys
import os
import time
import transforms3d as t3d
import pandas
map_pandaset_to_kitti = {
    'Car': 'Car',
    'Pickup Truck': 'Truck',
    'Medium-sized Truck': 'Truck',
    'Semi-truck': 'Truck',
    'Towed Object': 'DontCare',  
    'Motorcycle': 'Cyclist',
    'Other Vehicle - Construction Vehicle': 'Misc',
    'Other Vehicle - Uncommon': 'Misc',
    'Other Vehicle - Pedicab': 'Misc',
    'Emergency Vehicle': 'DontCare',  
    'Bus': 'Tram',  
    'Personal Mobility Device': 'Cyclist', 
    'Motorized Scooter': 'Cyclist',  
    'Bicycle': 'Cyclist',
    'Train': 'Tram',
    'Trolley': 'Tram',
    'Tram / Subway': 'Tram',
    'Pedestrian': 'Pedestrian',
    'Pedestrian with Object': 'Pedestrian',
    'Animals - Other': 'DontCare', 
    'Animals - Bird':'DontCare',
    'Pylons':'DontCare',
    'Road Barriers':'DontCare',
    'Signs': 'DontCare',
    'Cones': 'DontCare',
    'Construction Signs': 'DontCare',
    'Temporary Construction Barriers':'DontCare',
    'Rolling Containers': 'DontCare',
    'Other': 'DontCare',

}
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
        
        
        # draw origin
        #mayavi.mlab.points3d(0, 0, 0, color=(1, 1, 1), mode="sphere",scale_factor=1)
        mayavi.mlab.points3d(0, 0, 0, color=(1, 1, 1), mode="sphere",scale_factor=3)
        # draw axes
        axes = np.array(
            [[20.0, 0.0, 0.0, 0.0], [0.0, 20.0, 0.0, 0.0], [0.0, 0.0, 20.0, 0.0]],
            dtype=np.float64,
        )
        #x
        mayavi.mlab.plot3d(
            [0, axes[0, 0]],
            [0, axes[0, 1]],
            [0, axes[0, 2]],
            color=(1, 0, 0),
            tube_radius=None,
            figure=fig,
        )
        #y
        mayavi.mlab.plot3d(
            [0, axes[1, 0]],
            [0, axes[1, 1]],
            [0, axes[1, 2]],
            color=(0, 1, 0),
            tube_radius=None,
            figure=fig,
        )
        #z
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

            box = x, y, z, w, l, h, yaw

            corners = geometry.center_box_to_corners(box)
            s = corners
            box_point.append(s)
        
        
        for box in box_point:
            plot3Dboxes1(box)
          
        #mayavi.mlab.show()
        print(pc0.shape)
        myName = input()
        time.sleep(0.1)
        
def _heading_position_to_mat(heading, position):
    quat = np.array([heading["w"], heading["x"], heading["y"], heading["z"]])
    pos = np.array([position["x"], position["y"], position["z"]])
    transform_matrix = t3d.affines.compose(np.array(pos),
                                           t3d.quaternions.quat2mat(quat),
                                           [1.0, 1.0, 1.0])
    return transform_matrix

# def convert_calib_v2x_to_kitti(cam_K, t_velo2cam, r_velo2cam):
#     P2 = np.zeros([3, 4])
#     P2[:3, :3] = np.array(cam_K).reshape([3, 3], order="C")
#     P2 = P2.reshape(12, order="C")

#     Tr_velo_to_cam = np.concatenate((r_velo2cam, t_velo2cam), axis=1)
#     Tr_velo_to_cam = Tr_velo_to_cam.reshape(12, order="C")

#     return P2, Tr_velo_to_cam

def convert_calib_pandaset_to_kitti(frame_id, seq, calib_path):
    ## get front camera calib information
    front_cam = seq.camera['front_camera']
    camera_pose = front_cam.poses[frame_id]
    camera_heading = camera_pose['heading']
    camera_position = camera_pose['position']
    camera_pose_mat = _heading_position_to_mat(camera_heading, camera_position)

    trans_lidar_to_camera = np.linalg.inv(camera_pose_mat)
    camera_intrinsics = front_cam.intrinsics
    cam_K = np.eye(3, dtype=np.float64)
    cam_K[0, 0] = camera_intrinsics.fx
    cam_K[1, 1] = camera_intrinsics.fy
    cam_K[0, 2] = camera_intrinsics.cx
    cam_K[1, 2] = camera_intrinsics.cy
    
    P2 = np.zeros([3, 4])
    P2[:3, :3] = np.array(cam_K).reshape([3, 3], order="C")
    P2 = P2.reshape(12, order="C")
    Tr_velo_to_cam = trans_lidar_to_camera[:3, :]
    Tr_velo_to_cam = Tr_velo_to_cam.reshape(12, order="C")
    # return P2, Tr_velo_to_cam
    str_P2 = "P2: "
    str_Tr_velo_to_cam = "Tr_velo_to_cam: "
    for ii in range(11):
        str_P2 = str_P2 + str(P2[ii]) + " "
        str_Tr_velo_to_cam = str_Tr_velo_to_cam + str(Tr_velo_to_cam[ii]) + " "
    str_P2 = str_P2 + str(P2[11])
    str_Tr_velo_to_cam = str_Tr_velo_to_cam + str(Tr_velo_to_cam[11])

    str_P0 = str_P2
    str_P1 = str_P2
    str_P3 = str_P2
    str_R0_rect = "R0_rect: 1 0 0 0 1 0 0 0 1"
    str_Tr_imu_to_velo = str_Tr_velo_to_cam

    with open(calib_path, "w") as fp:
        gt_line = (
            str_P0
            + "\n"
            + str_P1
            + "\n"
            + str_P2
            + "\n"
            + str_P3
            + "\n"
            + str_R0_rect
            + "\n"
            + str_Tr_velo_to_cam
            + "\n"
            + str_Tr_imu_to_velo
        )
        fp.write(gt_line)
    
def project_to_image(points, camera_data, camera_pose, camera_intrinsics, filter_outliers=True):

    projected_points =[]
    camera_heading = camera_pose['heading']
    camera_position = camera_pose['position']
    camera_pose_mat = _heading_position_to_mat(camera_heading, camera_position)

    trans_lidar_to_camera = np.linalg.inv(camera_pose_mat)

    for point in points:
        points3d_lidar = point
        points3d_camera = trans_lidar_to_camera[:3, :3] @ (points3d_lidar.T) + \
                            trans_lidar_to_camera[:3, 3].reshape(3, 1)

        K = np.eye(3, dtype=np.float64)
        K[0, 0] = camera_intrinsics.fx
        K[1, 1] = camera_intrinsics.fy
        K[0, 2] = camera_intrinsics.cx
        K[1, 2] = camera_intrinsics.cy

        inliner_indices_arr = np.arange(points3d_camera.shape[1])
        if filter_outliers:
            condition = points3d_camera[2, :] > 0.0
            points3d_camera = points3d_camera[:, condition]
            inliner_indices_arr = inliner_indices_arr[condition]

        points2d_camera = K @ points3d_camera
        points2d_camera = (points2d_camera[:2, :] / points2d_camera[2, :]).T

        if filter_outliers:
            image_w, image_h = camera_data[0].size
            condition = np.logical_and(
                (points2d_camera[:, 1] < image_h) & (points2d_camera[:, 1] > 0),
                (points2d_camera[:, 0] < image_w) & (points2d_camera[:, 0] > 0))
            points2d_camera = points2d_camera[condition]
            points3d_camera = (points3d_camera.T)[condition]
            inliner_indices_arr = inliner_indices_arr[condition]
        projected_points.append(points2d_camera)
    return projected_points
        
        
    
    
def cuboids_to_boxes(cuboids0, poses):
    numb_ob = 0
    sensor1_num = 0
    labels = []
    for i, row in cuboids0.iterrows():
        sensor_id = row["cuboids.sensor_id"]
        if sensor_id == 1:
            sensor1_num += 1
            continue
        box = row["position.x"], row["position.y"], row["position.z"], row["dimensions.x"], row["dimensions.y"],  row["dimensions.z"], row["yaw"]

        corners = geometry.center_box_to_corners(box)
        rotate_corners = geometry.lidar_points_to_ego(corners, poses)

        s = rotate_corners
        # change x and y
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
        
        # projected_corners = project_to_image([p0,p1,p2,p3,p4,p5,p6,p7])

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

def write_kitti_in_txt(my_json, path_txt):
    wf = open(path_txt, "w")
    for item in my_json:
        i1 = str(item["type"]).title()
        i2 = str(item["truncated_state"])
        i3 = str(item["occluded_state"])
        i4 = str(item["alpha"])
        i5, i6, i7, i8 = (
            str(item["2d_box"]["xmin"]),
            str(item["2d_box"]["ymin"]),
            str(item["2d_box"]["xmax"]),
            str(item["2d_box"]["ymax"]),
        )
        # i9, i10, i11 = str(item["3d_dimensions"]["h"]), str(item["3d_dimensions"]["w"]), str(item["3d_dimensions"]["l"])
        i9, i11, i10 = str(item["3d_dimensions"]["h"]), str(item["3d_dimensions"]["l"]), str(item["3d_dimensions"]["w"])
        i12, i13, i14 = str(item["3d_location"]["x"]), str(item["3d_location"]["y"]), str(item["3d_location"]["z"])
        # i15 = str(item["rotation"])
        i15 = str(-0.5 * np.pi  - float(item["rotation"]))
        item_list = [i1, i2, i3, i4, i5, i6, i7, i8, i9, i10, i11, i12, i13, i14, i15]
        item_string = " ".join(item_list) + "\n"
        wf.write(item_string)
    wf.close()
def cuboids_to_boxes_transform_coord(cuboids: pandas.DataFrame, poses, rotate_yaw=None):
    str_ret = ''
    numb_ob = 0
    sensor1_num = 0
    for i, row in cuboids.iterrows():

        sensor_id = row["cuboids.sensor_id"]
        if sensor_id == 1:
            sensor1_num += 1
            continue

        # pos_x, pos_y, pos_z, dim_x, dim_y, dim_z, yaw = row["position.x"], row["position.y"], row["position.z"], row["dimensions.x"], row["dimensions.y"],  row["dimensions.z"], row["yaw"]
        w, l, h = row["dimensions.x"], row["dimensions.y"],  row["dimensions.z"]
        yaw = row["yaw"] + rotate_yaw
        center_xyz = np.array([[row["position.x"], row["position.y"], row["position.z"]]])
        rotate_corners, _ = geometry.lidar_points_to_ego_rotate(center_xyz, poses)
        x, y, z = rotate_corners[0, 0], rotate_corners[0, 1], rotate_corners[0, 2]

        while yaw < -np.pi:
            yaw = np.pi * 2 + yaw
        while yaw > np.pi:
            yaw = yaw - np.pi * 2
        
        category_before =row['label']
        category = map_pandaset_to_kitti[category_before]
        truncation = 0.0  # Example value, adjust as needed
        occlusion = 0  # Example value, adjust as needed
        # alpha = row['yaw']  # Assuming 'yaw' corresponds to observation angle
        alpha = -yaw
        bbox_2d = [0, 0, 0, 0]  # Placeholder for 2D bbox, adjust as needed
        rotation_y = row['yaw'] 
        # str = '{} {} {} {} {} {} {} {}\n'.format(row["label"], y, x, z, l, w, h, -yaw)
        str = f"{category} {truncation} {occlusion} {alpha} " \
                    f"{bbox_2d[0]} {bbox_2d[1]} {bbox_2d[2]} {bbox_2d[3]} " \
                    f"{l} {w} {h} " \
                    f"{x} {y} {z} {rotation_y}\n"

        str_ret += str
        numb_ob = numb_ob + 1
    # print("sensor1_num:{}".format(sensor1_num))
    return str_ret, numb_ob
                  
if __name__ == '__main__':

    # save_dataset_dir = os.path.join(root_dir, 'dataset', 'kitti')
    save_dataset_dir = '/home/lijie/data2/pandaset_output/front_lidar/kitti'
    mode = "test"  ## change mode
    assert mode in ['train', 'val', 'test'], 'Invalid mode: {}'.format(mode)
    is_test = (mode == 'test')
    sub_folder = 'testing' if is_test else 'training'
    image_dir = os.path.join(save_dataset_dir, sub_folder, "image_2")
    lidar_dir = os.path.join(save_dataset_dir, sub_folder, "velodyne")
    calib_dir = os.path.join(save_dataset_dir, sub_folder, "calib")
    label_dir = os.path.join(save_dataset_dir, sub_folder, "label_2")
    split_txt_path = os.path.join(save_dataset_dir, 'ImageSets', '{}.txt'.format(mode))  #
    
    split_fd = os.open(split_txt_path, os.O_RDWR|os.O_CREAT ) 
    save_file_id = 0
   
    # pandaset_dir = os.path.join('../', mode)
    pandaset_dir = '/home/lijie/data2/pandaset_down'
    dataset = DataSet(pandaset_dir)
    print('====================================')
    print(dataset.sequences())
    print("len of sequences", len(dataset.sequences()))
    print(dataset.sequences(with_semseg=True))
    print("available semseg length", len(dataset.sequences(with_semseg=True)))
        
    for sequence in dataset.sequences():
        print("sequence:",sequence)

        seq = dataset[sequence]
        seq.load_lidar().load_cuboids().load_gps()
        seq.load()
        
        seq.lidar.set_sensor(1)  # set to include only front-facing LiDAR
        
        
        
        frame_num = len(seq.lidar.data)
        for id in range(frame_num):
            pc0 = seq.lidar[id].to_numpy()
            poses = seq.lidar.poses[id]

            cuboids0 = seq.cuboids[id] 

            pc0[:, :3], rotate_yaw = geometry.lidar_points_to_ego_rotate(pc0[:, :3], poses)

            pc0[:,[0,1]]=pc0[:,[1,0]]
            
            
            save_file_id_str = str(save_file_id)
            save_file_id_str = save_file_id_str.zfill(6)
            

            lidarData = pc0[:, :4]
            lidarData = lidarData.reshape(-1, 4).astype(np.float32)

            numb_ob, labels = cuboids_to_boxes(cuboids0, poses)
            labels = np.array(labels)

            calib_str_ret = '{} {} {} {} {}\n'.format(seq.gps[id]['lat'], seq.gps[id]['long'], seq.gps[id]['height'], seq.gps[id]['xvel'], seq.gps[id]['yvel'])

            lidarData, labels = get_filtered_lidar(lidarData, boundary, labels)
            

            velodyne_file_new = os.path.join(lidar_dir, save_file_id_str) + '.bin'
            lidarData.tofile(velodyne_file_new)

            label_file_new = os.path.join(label_dir, save_file_id_str) + '.txt'
            label_fd = os.open( label_file_new,  os.O_RDWR|os.O_CREAT )
            str_ret = ''
            box_point =[]

            # 
            # ego_pandar_points, rotate_yaw  = geometry.lidar_points_to_ego_rotate(lidarData[:, :3], poses)        
            labels, bun_ob = cuboids_to_boxes_transform_coord(cuboids0, poses, rotate_yaw)

            
            os.write(label_fd, str.encode(labels))
            
            os.close( label_fd )

            source = os.path.join(pandaset_dir, sequence, 'camera/front_camera' , str(id).zfill(2)) + '.jpg';
            target = os.path.join(image_dir, save_file_id_str) + '.jpg' 
            copyfile(source, target)

            
            ## save calib  info
            calib_file = os.path.join(calib_dir, save_file_id_str) + '.txt'
            convert_calib_pandaset_to_kitti(id, seq, calib_file)

            os.write(split_fd, str.encode(save_file_id_str))
            os.write(split_fd, str.encode("\n"))

            save_file_id = save_file_id + 1

            if(IS_3D_SHOW):
                lidar_show(lidarData, labels[:,2:9])
            print(save_file_id_str)
            

        dataset.unload(seq)

    print('====================================')
    os.close( split_fd )
    
    

