import os, sys
sys.path.append(os.getcwd())

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import numpy as np
import shutil
import argparse
from pathlib import Path
import mmcv
import mmengine
import cv2
from mmdet3d.structures import points_cam2img
from mmdet3d.structures.ops import box_np_ops

# kitti_categories = ('Pedestrian', 'Cyclist', 'Car')

def write_lines(path, lines_with_return_character):
    with open(path, 'w') as f:
        f.writelines(lines_with_return_character)

def get_intrinsics(intrinsic_file_path, cam_id= 0):
    ''' load perspective intrinsics '''
    # Reference:
    # https://github.com/autonomousvision/kitti360Scripts/blob/7c144cb069234bbe75b83e75c9ff2a120eab8b4b/kitti360scripts/helpers/project.py#L111-L136
    intrinsic_loaded = False
    width = -1
    height = -1
    with open(intrinsic_file_path) as f:
        intrinsics = f.read().splitlines()
    for line in intrinsics:
        line = line.split(' ')
        if line[0] == 'P_rect_%02d:' % cam_id:
            temp = [float(x) for x in line[1:]]
            temp = np.reshape(temp, [3,4])
            K    = np.eye(4).astype(np.float32)
            K[:3, :]= temp
            P0_rect = temp
            intrinsic_loaded = True
        elif line[0] == 'R_rect_%02d:' % cam_id:
            R_rect = np.eye(4)
            R_rect[:3,:3] = np.array([float(x) for x in line[1:]]).reshape(3,3)
        elif line[0] == "S_rect_%02d:" % cam_id:
            width = int(float(line[1]))
            height = int(float(line[2]))
    assert(intrinsic_loaded==True)
    assert(width>0 and height>0)

    # R_rect is with Y up. Multiply the first row of R_rect by -1 to make Y down.
    # Adjust the intrinsics as well.
    R_rect[1] *= -1.0
    K[:, 1]   *= -1.0

    return K, R_rect, P0_rect

def readVariable(fid,name,M,N):
    # Reference:
    # https://github.com/autonomousvision/kitti360Scripts/blob/7c144cb069234bbe75b83e75c9ff2a120eab8b4b/kitti360scripts/devkits/commons/loadCalibration.py#L9-L33
    # rewind
    fid.seek(0,0)

    # search for variable identifier
    line = 1
    success = 0
    while line:
        line = fid.readline()
        if line.startswith(name):
            success = 1
            break

    # return if variable identifier not found
    if success==0:
      return None

    # fill matrix
    line = line.replace('%s:' % name, '')
    line = line.split()
    assert(len(line) == M*N)
    line = [float(x) for x in line]
    mat = np.array(line).reshape(M, N)

    return mat

def get_ego_to_camera(camera_to_ego_file_path, cam_id= 0):
    # Reference:
    # https://github.com/autonomousvision/kitti360Scripts/blob/master/kitti360scripts/devkits/commons/loadCalibration.py#L35-L51
    # open file
    fid = open(camera_to_ego_file_path, 'r')

    # read variables
    cameras = ['image_%02d' % cam_id]
    lastrow = np.array([0,0,0,1]).reshape(1,4)
    for camera in cameras:
        camera_to_ego = np.concatenate((readVariable(fid, camera, 3, 4), lastrow))

    # close file
    fid.close()
    return np.linalg.inv(camera_to_ego)

# Original helper functions remain unchanged
def read_cam_to_velo(path):
    with open(path, 'r') as f:
        vals = [float(v) for v in f.read().strip().split()]
    mat = np.array(vals, dtype=np.float32).reshape(3, 4)
    return mat

def cam_to_velo_to_velo_to_cam(cam_to_velo_3x4):
    R = cam_to_velo_3x4[:, :3]
    t = cam_to_velo_3x4[:, 3:]
    R_inv = R.T
    t_inv = -R_inv @ t
    velo_to_cam_3x4 = np.hstack((R_inv, t_inv))
    return velo_to_cam_3x4

def bin_to_pcd(bin_file, pcd_file):
    point_cloud = np.fromfile(bin_file, dtype=np.float32).reshape(-1, 4)
    timestamp = np.full((point_cloud.shape[0], 1), 1.571255e+09)
    point_cloud = np.hstack((point_cloud, timestamp))    
    
    header = f"""# .PCD v0.7 - Point Cloud Data file format
VERSION 0.7
FIELDS x y z intensity timestamp
SIZE 4 4 4 4 8
TYPE F F F U F
COUNT 1 1 1 1 1
WIDTH {point_cloud.shape[0]}
HEIGHT 1
VIEWPOINT 0 0 0 1 0 0 0
POINTS {point_cloud.shape[0]}
DATA ascii
"""
    with open(pcd_file, 'w') as f:
        f.write(header)
        for point in point_cloud:
            f.write(f"{point[0]} {point[1]} {point[2]} {point[3]} {point[4]}\n")

def create_reduced_point_cloud(data_path, save_path=None, with_back=False):
    '''
    Create reduced point cloud by removing points that are outside the image FOV
    data_path: path to the kitti formatted data folder
    save_path: path to save the reduced point cloud, if None, save to data_path
    with_back: whether to keep the points that are behind the camera
    Will save bin files with reduced points to a new folder named velodyne_reduced
    and also save pcd files for C+L pipeline input.
    '''

    bin_paths = list(Path(data_path).rglob('*.bin'))
    print(f'Found {len(bin_paths)} .bin files.')

    for v_path in mmengine.track_iter_progress(bin_paths):
        points_v = np.fromfile(
            str(v_path), dtype=np.float32,
            count=-1).reshape([-1, 4])
        # import ipdb; ipdb.set_trace()
        if save_path is None:
            save_dir = v_path.parent.parent / (v_path.parent.stem + '_reduced')
            if not save_dir.exists():
                save_dir.mkdir()
            save_filename = save_dir / v_path.name

            rect = np.eye(4, dtype=np.float32)
            ## 
            P2 = np.array([
                [5.525542610000e+02, 0.000000000000e+00, 6.820494530000e+02, 0.000000000000e+00],
                [0.000000000000e+00, 5.525542610000e+02, 2.387695490000e+02, 0.000000000000e+00],
                [0.000000000000e+00, 0.000000000000e+00, 1.000000000000e+00, 0.000000000000e+00]
            ], dtype=np.float32)
            ## concat P2 and [0,0,0,1]
            P2 = np.vstack((P2, np.array([0, 0, 0, 1], dtype=np.float32)))
            
            Trv2c = np.array([
                [4.307104274631e-02, -9.990043640137e-01, -1.162548549473e-02, 2.623469531536e-01],
                [-8.829286694527e-02, 7.784613873810e-03, -9.960641264915e-01, -1.076341345906e-01],
                [9.951629042625e-01, 4.392797127366e-02, -8.786966651678e-02, -8.292052149773e-01]
            ], dtype=np.float32)
            ## concat Trv2c and [0,0,0,1]
            Trv2c = np.vstack((Trv2c, np.array([0, 0, 0, 1], dtype=np.float32)))

            image_shape = np.array([376, 1408], dtype=np.int32)

            # print('rect:', rect)
            # print('P2:', P2)
            # print('Trv2c:', Trv2c)
            # print('image_shape:', image_shape)
            points_v = box_np_ops.remove_outside_points(points_v, rect, Trv2c, P2,
                                                    image_shape)

            print(f'Saving to {save_filename}, points shape: {points_v.shape}')

            with open(save_filename, 'w') as f:
                points_v.tofile(f)

# Thread-safe progress counter
class ProgressCounter:
    def __init__(self, total):
        self.total = total
        self.count = 0
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.count += 1
            if self.count % 100 == 0 or self.count == self.total:
                print(f"Progress: {self.count}/{self.total} ({self.count/self.total*100:.1f}%)", flush=True)

# Function to process a single frame
def process_frame(frame_data):
    """
    Perform all operations for a single frame
    frame_data: Dictionary containing all the information needed to process a frame
    """
    try:
        index = frame_data['index']
        frame_id = frame_data['frame_id']
        pose = frame_data['pose']
        img_folder = frame_data['img_folder']
        output_folder = frame_data['output_folder']
        rect_to_intri = frame_data['rect_to_intri']
        cam_to_rect = frame_data['cam_to_rect']
        P0_rect = frame_data['P0_rect']
        ego_to_camera = frame_data['ego_to_camera']
        velo_to_cam = frame_data['velo_to_cam']
        velodyne_folder = frame_data['velodyne_folder']
        progress_counter = frame_data['progress_counter']
        
        img_name = str(frame_id).zfill(10)
        img_path = os.path.join(img_folder, img_name + ".png")
        
        # 1. Copy image, encode image
        new_img_name = f"{frame_id:06d}"
        temp_img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        if temp_img.dtype == np.uint16:
            temp_img = (temp_img / 256).astype(np.uint8)
        else:
            temp_img = temp_img.astype(np.uint8)

        output_image_bin_path  = os.path.join(output_folder, "image_2", new_img_name + ".bin")
        img_encode = cv2.imencode('.jpg', temp_img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])[1]
        img_encode.tofile(output_image_bin_path)

        # 2. Generate calibration file
        output_calib_file_path = os.path.join(output_folder, "calib", new_img_name + ".txt")
        world_to_ego = np.linalg.inv(np.concatenate((pose, np.array([0.,0.,0.,1.]).reshape(1,4))))
        world_to_rect = np.matmul(np.matmul(cam_to_rect, ego_to_camera), world_to_ego)
        
        calib_text_to_write = 'P2: ' + ' '.join(['{:.12e}'.format(x) for x in P0_rect.flatten()[:12].tolist()]) + "\n"
        calib_text_to_write += 'R0_rect: 1.000000000000 0.000000000000 0.000000000000 0.000000000000 1.000000000000 0.000000000 0.000000000000 0.000000000000 1.000000000000' + "\n"
        calib_text_to_write += 'Tr_velo_to_cam: ' + ' '.join(['{:.12e}'.format(x) for x in velo_to_cam.flatten()[:12].tolist()]) + "\n"
        
        write_lines(output_calib_file_path, calib_text_to_write)

        # 3. copy bin files to velodyne folder
        velodyne_path = os.path.join(velodyne_folder, img_name + ".bin")
        output_velodyne_path = os.path.join(output_folder, "velodyne", new_img_name + ".bin")
        shutil.copy(velodyne_path, output_velodyne_path)
        
        # # 3. Convert point cloud file
        # velodyne_path = os.path.join(velodyne_folder, img_name + ".bin")
        # output_velodyne_path = os.path.join(output_folder, "velodyne", new_img_name + ".pcd")
        # bin_to_pcd(velodyne_path, output_velodyne_path)

        # Update progress
        progress_counter.increment()
        
        return f"Successfully processed frame {frame_id}"
        
    except Exception as e:
        return f"Error processing frame {frame_id}: {str(e)}"

def parse_args():
    parser = argparse.ArgumentParser(description='Convert KITTI-360 to KITTI format')
    parser.add_argument('kitti360folder', help='folder to kitti 360')
    parser.add_argument('output_folder', help='fodler to save kitti formatted data')
    args = parser.parse_args()
    return args

# Main processing loop
def main(kitti_360_folder, output_folder):
    for drive_id, drive_id_test_flag in zip(drive_id_list, drive_id_test_flag_list):
        drive_name = "2013_05_28_drive_" + str(drive_id).zfill(4) + "_sync"
        img_folder = os.path.join(kitti_360_folder, "data_2d_raw", drive_name, "image_00/data_rect")
        
        camera_calib_folder = os.path.join(kitti_360_folder, "calibration")
        intrinsics_file = os.path.join(camera_calib_folder, "perspective.txt")
        ego_to_cam_file = os.path.join(camera_calib_folder, "calib_cam_to_pose.txt")
        world_to_ego_folder = os.path.join(kitti_360_folder, "data_poses", drive_name)
        world_to_ego_file = os.path.join(world_to_ego_folder, "poses.txt")
        
        # Preload calibration information
        rect_to_intri, cam_to_rect, P0_rect = get_intrinsics(intrinsic_file_path=intrinsics_file)
        ego_to_camera = get_ego_to_camera(camera_to_ego_file_path=ego_to_cam_file)
        cam_to_velo = read_cam_to_velo(os.path.join(camera_calib_folder, "calib_cam_to_velo.txt"))
        velo_to_cam = cam_to_velo_to_velo_to_cam(cam_to_velo)
        
        # Load poses
        poses = np.loadtxt(world_to_ego_file)
        frames = poses[:,0].astype(np.uint64)
        poses = np.reshape(poses[:,1:],[-1,3,4])
        
        velodyne_folder = kitti_360_folder + "/data_3d_raw/" + drive_name + "/velodyne_points/data"
        
        # Create progress counter
        progress_counter = ProgressCounter(len(frames))
        
        # Prepare data for all frames
        frame_data_list = []
        for index, frame_id in enumerate(frames):
            pose = poses[frames == frame_id][0]
            
            frame_data = {
                'index': index,
                'frame_id': frame_id,
                'pose': pose,
                'img_folder': img_folder,
                'output_folder': output_folder,
                'rect_to_intri': rect_to_intri,
                'cam_to_rect': cam_to_rect,
                'P0_rect': P0_rect,
                'ego_to_camera': ego_to_camera,
                'velo_to_cam': velo_to_cam,
                'velodyne_folder': velodyne_folder,
                'progress_counter': progress_counter
            }
            frame_data_list.append(frame_data)
        
        # Process using thread pool
        max_workers = min(32, os.cpu_count() * 2)  # Limit maximum number of threads
        print(f"Processing {len(frames)} frames using {max_workers} threads...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_frame = {executor.submit(process_frame, frame_data): frame_data['frame_id'] 
                             for frame_data in frame_data_list}
            
            # Collect results
            for future in as_completed(future_to_frame):
                frame_id = future_to_frame[future]
                try:
                    result = future.result()
                    if "Error" in result:
                        print(result)
                except Exception as exc:
                    print(f'Frame {frame_id} generated an exception: {exc}')
        
        print(f"Completed processing drive {drive_id}")

if __name__ == "__main__":
    # main()
    args = parse_args()
    kitti_360_folder = args.kitti360folder
    output_folder = args.output_folder

    # Original configuration remains unchanged
    detect_cat_list = ['person', 'car', 'truck', 'bicycle', 'building']
    detect_cat_map_dict = {x:x.title() for x in detect_cat_list}
    detect_cat_map_dict['person'] = 'Pedestrian'
    detect_cat_map_dict['bicycle']= 'Cyclist'

    
    drive_id_list = [0]
    drive_id_test_flag_list = [False]

    # drive_id_list       = [0, 2, 3, 4, 5, 6, 7, 9, 10, 8, 18]
    # drive_id_test_flag_list = [False]*9 + [True]*2
    
    # Code for creating output folders remains unchanged
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    if not os.path.exists(os.path.join(output_folder, "calib")):
        os.makedirs(os.path.join(output_folder, "calib"))   
    if not os.path.exists(os.path.join(output_folder, "image_2")):
        os.makedirs(os.path.join(output_folder, "image_2"))
    if not os.path.exists(os.path.join(output_folder, "velodyne")):
        os.makedirs(os.path.join(output_folder, "velodyne"))

    main(kitti_360_folder, output_folder)

    save_path = None
    lidar_folder = os.path.join(output_folder, "velodyne")
    create_reduced_point_cloud(lidar_folder, save_path)

