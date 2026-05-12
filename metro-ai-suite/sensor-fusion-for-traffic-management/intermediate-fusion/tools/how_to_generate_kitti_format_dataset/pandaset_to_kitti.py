import os
import numpy as np
import pandas as pd
import pickle
import gzip
import json
import cv2
from PIL import Image
import shutil
from pathlib import Path
import pandaset
from pandaset.geometry import lidar_points_to_ego, projection, center_box_to_corners
from scipy.spatial.transform import Rotation as R
import transforms3d as t3d
import argparse

class PandaSetToKittiConverter:
    def __init__(self, pandaset_root, output_root, encode_img=False, undistort_img=False, calib_file=None):
        """
        PandaSet to KITTI format converter
        
        Args:
            pandaset_root: PandaSet dataset root directory
            output_root: Output KITTI format dataset directory
            encode_img: Whether to encode images as binary files (True: encode as .bin files, False: save as .png files)
            undistort_img: Whether to undistort images using camera distortion parameters
            calib_file: Path to static_extrinsic_calibration.yaml file containing camera parameters
        """
        self.pandaset_root = pandaset_root
        self.output_root = output_root
        self.encode_img = encode_img
        self.undistort_img = undistort_img
        self.calib_file = calib_file
        self.dataset = pandaset.DataSet(pandaset_root)
        
        # Try to import yaml
        try:
            import yaml
            self.yaml_available = True
        except ImportError:
            print("Warning: PyYAML not installed. Install with: pip install PyYAML")
            self.yaml_available = False
        
        # Load camera calibration parameters if undistort is enabled
        self.camera_calib_data = None
        if self.undistort_img and self.calib_file and self.yaml_available:
            self.load_camera_calibration()
        elif self.undistort_img and not self.calib_file:
            print("Warning: Undistort option enabled but no calibration file provided")
            self.undistort_img = False
        elif self.undistort_img and not self.yaml_available:
            print("Warning: Undistort option enabled but PyYAML not available")
            self.undistort_img = False
        
        # KITTI class mapping (PandaSet -> KITTI)
        self.class_mapping = {
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
        
    def load_camera_calibration(self):
        """Load camera calibration parameters from YAML file"""
        try:
            import yaml
            with open(self.calib_file, 'r') as file:
                self.camera_calib_data = yaml.safe_load(file)
            print(f"Loaded camera calibration from: {self.calib_file}")
            
            # Verify required data exists
            if 'front_camera' in self.camera_calib_data:
                if 'intrinsic' in self.camera_calib_data['front_camera']:
                    intrinsic = self.camera_calib_data['front_camera']['intrinsic']
                    if 'D' in intrinsic and 'K' in intrinsic:
                        print("  - Front camera distortion parameters loaded successfully")
                        return
            
            print("Warning: Required camera parameters not found in calibration file")
            self.undistort_img = False
            self.camera_calib_data = None
            
        except Exception as e:
            print(f"Error loading camera calibration file: {e}")
            self.undistort_img = False
            self.camera_calib_data = None
    
    def undistort_image(self, img, camera_name='front_camera'):
        """
        Undistort image using camera parameters from YAML file
        
        Args:
            img: Input distorted image
            camera_name: Camera name ('front_camera' or 'back_camera')
            
        Returns:
            undistorted_img: Undistorted image
        """
        try:
            if not self.camera_calib_data or camera_name not in self.camera_calib_data:
                print(f"Warning: No calibration data found for {camera_name}")
                return img
            
            camera_data = self.camera_calib_data[camera_name]['intrinsic']
            
            # Get distortion coefficients and camera matrix
            D_raw = np.array(camera_data['D'], dtype=np.float64)
            K_list = camera_data['K']
            K = np.array([[K_list[0], K_list[1], K_list[2]],
                          [K_list[3], K_list[4], K_list[5]],
                          [K_list[6], K_list[7], K_list[8]]], dtype=np.float64)
            
            # Validate camera matrix
            if K.shape != (3, 3):
                print(f"    Error: Invalid camera matrix shape: {K.shape}, expected (3,3)")
                return img
            
            # Ensure exactly 5 distortion parameters for standard radial-tangential model
            if len(D_raw) < 5:
                # Pad with zeros if less than 5 parameters
                D = np.zeros(5, dtype=np.float64)
                D[:len(D_raw)] = D_raw
                print(f"    Warning: Only {len(D_raw)} distortion parameters provided, padded to 5: {D}")
            elif len(D_raw) > 5:
                # Use only first 5 parameters
                D = D_raw[:5]
                print(f"    Info: Using first 5 of {len(D_raw)} distortion parameters: {D}")
            else:
                D = D_raw
                print(f"    Info: Using standard radial-tangential model with {len(D)} distortion parameters: {D}")
            
            # Apply standard radial-tangential undistortion
            h, w = img.shape[:2]
            map1, map2 = cv2.initUndistortRectifyMap(
                K, D, np.eye(3), K, (w, h), cv2.CV_32FC1
            )
            undistorted_img = cv2.remap(img, map1, map2, cv2.INTER_LINEAR)
            
            return undistorted_img
            
        except Exception as e:
            print(f"Warning: Could not undistort image: {e}")
            return img  # Return original image if undistortion fails
        
    def encode_image(self, img, flag=True):
        """
        Encode image to binary format
        
        Args:
            img: Input image
            flag: True for camera (jpg), False for depth image (png)
        
        Returns:
            img_encode: Encoded binary data
        """
        if flag:
            img_encode = cv2.imencode(".jpg", img)[1]
        else:
            img_encode = cv2.imencode(".png", img)[1]
        return img_encode
        
    def create_kitti_directories(self):
        """Create KITTI format directory structure"""
        dirs = [
            'training/image_2',      # Left camera images
            'training/velodyne',     # Point cloud data
            'training/label_2',      # 2D labels
            'training/calib',        # Calibration files
            'testing/image_2',
            'testing/velodyne', 
            'testing/calib'
        ]
        
        for dir_path in dirs:
            os.makedirs(os.path.join(self.output_root, dir_path), exist_ok=True)
            
    
    def pose_to_transform_matrix(self, pose):
        """Convert pose to 4x4 transformation matrix, sensor local coordinate system → ego coordinate system transformation matrix"""
        quat = np.array([pose['heading']["w"], pose['heading']["x"], pose['heading']["y"], pose['heading']["z"]])
        pos = np.array([pose['position']["x"], pose['position']["y"], pose['position']["z"]])
        transform_matrix = t3d.affines.compose(np.array(pos),
                                            t3d.quaternions.quat2mat(quat),
                                            [1.0, 1.0, 1.0])
        return transform_matrix

    # def ego_to_camera_transform(self, camera_pose, lidar_pose):
    #     """
    #     Calculate transformation matrix from standard ego coordinate system to camera coordinate system
    #     """
    #     # Camera pose in world coordinate system
    #     T_world_to_camera = np.linalg.inv(self.pose_to_transform_matrix(camera_pose))
        
    #     # ego(LiDAR) pose in world coordinate system  
    #     T_world_to_ego = np.linalg.inv(self.pose_to_transform_matrix(lidar_pose))
        
    #     # ego to camera transformation: T_ego_to_camera = T_world_to_camera @ T_ego_to_world
    #     T_ego_to_camera = T_world_to_camera @ np.linalg.inv(T_world_to_ego)
        
    #     return T_ego_to_camera
    
    def normative_ego_to_camera_transform(self, camera_pose, lidar_pose):
        """
        Calculate transformation matrix from standard ego coordinate system to camera coordinate system
        """
        # Camera pose in world coordinate system
        T_world_to_camera = np.linalg.inv(self.pose_to_transform_matrix(camera_pose))
        
        # ego(LiDAR) pose in world coordinate system  
        T_world_to_pandaset_ego = np.linalg.inv(self.pose_to_transform_matrix(lidar_pose))
        
        # PandaSet ego to camera transformation
        T_pandaset_ego_to_camera = T_world_to_camera @ np.linalg.inv(T_world_to_pandaset_ego)

        # Pandaset ego coordinates are:
        # - x pointing to the right
        # - y pointing to the front
        # - z pointing up
        # Normative coordinates are:
        # - x pointing foreward
        # - y pointings to the left
        # - z pointing to the top
        # So a transformation is required to the match the normative coordinates
        
        # PandaSet ego -> standard ego transformation
        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = np.array([
            [0,  1,  0],  # x_ego = y_pandaset (front)
            [-1, 0,  0],  # y_ego = -x_pandaset (left = -right)
            [0,  0,  1]   # z_ego = z_pandaset (up)
        ])
    
        # normative ego to camera transformation
        T_normative_ego_to_camera = T_pandaset_ego_to_camera @ np.linalg.inv(transform_matrix)

        return T_normative_ego_to_camera

    def world_to_camera_transform(self, camera_pose):
        """
        Calculate transformation matrix from world coordinate system (original lidar coordinate system) to camera coordinate system
        """
        camera_pose_mat = self.pose_to_transform_matrix(camera_pose)

        T_world_to_camera = np.linalg.inv(camera_pose_mat)
        
        return T_world_to_camera
    
    def world_to_normative_ego_transform(self, lidar_pose):
        """
        Calculate transformation matrix from world coordinate system (original lidar coordinate system) to standard ego
        """
        lidar_pose_mat = self.pose_to_transform_matrix(lidar_pose)

        T_world_to_pandaset_ego = np.linalg.inv(lidar_pose_mat)

        # PandaSet ego -> standard ego transformation
        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = np.array([
            [0,  1,  0],  # x_ego = y_pandaset (front)
            [-1, 0,  0],  # y_ego = -x_pandaset (left = -right)
            [0,  0,  1]   # z_ego = z_pandaset (up)
        ])

        T_world_to_ego = transform_matrix @ T_world_to_pandaset_ego

        return T_world_to_ego
    
    def pandaset_ego_to_normative_ego(self, points_pandaset):
        """
        Convert PandaSet ego coordinate system to standard ego coordinate system
        
        PandaSet ego: x=right, y=front, z=up
        Standard ego:    x=front, y=left,  z=up
        
        Args:
            points_pandaset: Points in PandaSet ego coordinate system, shape (N, 3)
        
        Returns:
            points: Points in standard ego coordinate system, shape (N, 3)
        """
        transform_matrix = np.array([
            [0,  1,  0],  # x_kitti = y_pandaset
            [-1, 0,  0],  # y_kitti = -x_pandaset
            [0,  0,  1]   # z_kitti = z_pandaset
        ])

        points = (transform_matrix @ points_pandaset.T).T
        return points

    def convert_sequence(self, seq_id, split='training'):
        """Convert single sequence"""
        print(f"Converting sequence {seq_id}...")
        
        seq = self.dataset[seq_id]
        seq.load()

        # Select pandar64 (sensor_id=1) - Forward-Facing LiDAR
        seq.lidar.set_sensor(1)
        
        # Get number of frames
        num_frames = len(seq.lidar.timestamps)
        
        print(f"Found {num_frames} frames in sequence {seq_id}")
        
        for frame_idx in range(num_frames):
            # Generate global frame ID
            global_frame_id = f"{int(seq_id):03d}_{frame_idx:06d}"
            
            try:
                # 1. Convert point cloud data
                self.convert_lidar_data(seq, frame_idx, global_frame_id, split)
                
                # 2. Convert camera images
                self.convert_camera_data(seq_id, frame_idx, global_frame_id, split)
                
                # 3. Generate calibration files
                self.generate_calibration_file(seq, frame_idx, global_frame_id, split)
                
                # 4. Convert annotation data (training set only)
                if split == 'training':
                    self.convert_annotations(seq, frame_idx, global_frame_id)
                    
                print(f"  Frame {frame_idx}/{num_frames-1} processed")
                
            except Exception as e:
                print(f"  Error processing frame {frame_idx}: {e}")
                continue
                
    def convert_lidar_data(self, seq, frame_idx, global_frame_id, split):
        """
        Convert LiDAR data to standard ego coordinate system
        """
        try:
            # Get LiDAR data (in world coordinate system)
            lidar_data = seq.lidar[frame_idx]
            lidar_pose = seq.lidar.poses[frame_idx]
            
            # Check if data is valid
            if lidar_data is None or len(lidar_data) == 0:
                print(f"    Warning: Empty lidar data for frame {frame_idx}")
                output_path = os.path.join(self.output_root, split, 'velodyne', f'{global_frame_id}.bin')
                np.array([], dtype=np.float32).tofile(output_path)
                return
            
            # Extract xyz coordinates and intensity
            points_world = lidar_data[['x', 'y', 'z']].values
            intensity = lidar_data['i'].values if 'i' in lidar_data.columns else np.zeros(len(points_world))
            intensity = intensity.astype(np.float32) / 255
            
            # Convert to ego coordinate system using official method
            points_ego = lidar_points_to_ego(points_world, lidar_pose)
            points_normative_ego = self.pandaset_ego_to_normative_ego(points_ego)

            # Combine into KITTI format [x, y, z, intensity]
            kitti_points = np.hstack([points_normative_ego, intensity.reshape(-1, 1)])

            # Save as binary file
            output_path = os.path.join(self.output_root, split, 'velodyne', f'{global_frame_id}.bin')
            kitti_points.astype(np.float32).tofile(output_path)
            
            print(f"    Converted {len(points_ego)} points to ego coordinate system")
            
        except Exception as e:
            print(f"    Error converting lidar data for frame {frame_idx}: {e}")
            output_path = os.path.join(self.output_root, split, 'velodyne', f'{global_frame_id}.bin')
            np.array([], dtype=np.float32).tofile(output_path)
        
    def convert_camera_data(self, seq_id, frame_idx, global_frame_id, split):
        """Convert camera images with optional undistortion"""
        try:
            # Get front_camera image path
            camera_path = os.path.join(self.pandaset_root, seq_id, 'camera', 'front_camera', f'{frame_idx:02d}.jpg')
            
            if not os.path.exists(camera_path):
                print(f"    Warning: Camera image not found: {camera_path}")
                return
            
            # Read original image
            img_bgr = cv2.imread(camera_path)
            if img_bgr is None:
                print(f"    Warning: Could not read image: {camera_path}")
                return
            
            # Apply undistortion if requested
            if self.undistort_img:
                img_bgr = self.undistort_image(img_bgr, 'front_camera')
                
            if self.encode_img:
                # Encoding mode: encode as binary file
                output_path = os.path.join(self.output_root, split, 'image_2', f'{global_frame_id}.bin')
                
                # Encode as binary
                encoded_img = self.encode_image(img_bgr, flag=True)
                
                # Save binary file
                with open(output_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                    
                print(f"    {'Undistorted and e' if self.undistort_img else 'E'}ncoded image to binary: {os.path.basename(output_path)}")
            else:
                # Direct save mode
                output_path = os.path.join(self.output_root, split, 'image_2', f'{global_frame_id}.jpg')
                
                if self.undistort_img:
                    # Save undistorted image
                    cv2.imwrite(output_path, img_bgr)
                    print(f"    Undistorted and saved image: {os.path.basename(output_path)}")
                else:
                    # Direct copy original file
                    import shutil
                    shutil.copy2(camera_path, output_path)
                    print(f"    Copied image: {os.path.basename(output_path)}")

        except Exception as e:
            print(f"    Error converting camera data for frame {frame_idx}: {e}")
            import traceback
            traceback.print_exc()
            
    def generate_calibration_file(self, seq, frame_idx, global_frame_id, split):
        """Generate KITTI format calibration file - ego to camera transformation"""
        try:
            camera_intrinsics = seq.camera['front_camera'].intrinsics
            camera_pose = seq.camera['front_camera'].poses[frame_idx]
            lidar_pose = seq.lidar.poses[frame_idx]
            
            # Get camera intrinsics and projection matrix
            fx, fy, cx, cy = camera_intrinsics.fx, camera_intrinsics.fy, camera_intrinsics.cx, camera_intrinsics.cy
            K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
            P2 = np.hstack([K, np.zeros((3, 1))])
            
            # ego to camera transformation matrix
            T_ego_to_camera = self.normative_ego_to_camera_transform(camera_pose, lidar_pose)
            Tr_velo_to_cam = T_ego_to_camera[:3, :]  # 3x4 transformation matrix

            Tr_world_to_ego = self.world_to_normative_ego_transform(lidar_pose)
            Tr_world_to_ego = Tr_world_to_ego[:3, :]  # 3x4 transformation matrix
            Tr_world_to_cam = self.world_to_camera_transform(camera_pose)
            Tr_world_to_cam = Tr_world_to_cam[:3, :]  # 3x4 transformation matrix
            
            # Write calibration file
            calib_path = os.path.join(self.output_root, split, 'calib', f'{global_frame_id}.txt')
            with open(calib_path, 'w') as f:
                f.write(f"P0: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P1: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P2: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P3: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"R0_rect: {' '.join(map(str, np.eye(3).flatten()))}\n")
                f.write(f"Tr_velo_to_cam: {' '.join(map(str, Tr_velo_to_cam.flatten()))}\n")
                f.write(f"Tr_imu_to_velo: {' '.join(map(str, np.eye(3, 4).flatten()))}\n")
                f.write(f"Tr_world_to_ego: {' '.join(map(str, Tr_world_to_ego.flatten()))}\n")
                f.write(f"Tr_world_to_cam: {' '.join(map(str, Tr_world_to_cam.flatten()))}\n")
                
        except Exception as e:
            print(f"    Error generating calibration file for frame {frame_idx}: {e}")
            import traceback
            traceback.print_exc()
            
    def convert_annotations(self, seq, frame_idx, global_frame_id):
        """Convert 3D annotations to KITTI format"""
        try:
            # Load 3D annotations
            try:
                cuboids = seq.cuboids[frame_idx]
            except:
                print(f"Unable to load cuboids for frame {frame_idx}, creating empty label file.")
                # If unable to load cuboids, create empty annotation file
                label_path = os.path.join(self.output_root, 'training', 'label_2', f'{global_frame_id}.txt')
                open(label_path, 'w').close()
                return
                
            if cuboids is None or len(cuboids) == 0:
                # Create empty annotation file
                print(f"No cuboids found for frame {frame_idx}, creating empty label file.")
                label_path = os.path.join(self.output_root, 'training', 'label_2', f'{global_frame_id}.txt')
                open(label_path, 'w').close()
                return
                
            camera_pose = seq.camera['front_camera'].poses[frame_idx]
            lidar_pose = seq.lidar.poses[frame_idx]
            camera_intrinsics = seq.camera['front_camera'].intrinsics
            
            # Get camera intrinsics
            fx = camera_intrinsics.fx
            fy = camera_intrinsics.fy
            cx = camera_intrinsics.cx
            cy = camera_intrinsics.cy
            
            # Camera intrinsic matrix
            K = np.array([
                [fx, 0, cx],
                [0, fy, cy],
                [0, 0, 1]
            ])
            
            # world to camera transformation matrix
            T_world_to_camera = self.world_to_camera_transform(camera_pose)
            
            kitti_labels = []
            
            for _, cuboid in cuboids.iterrows():
                # Map classes
                pandaset_class = cuboid.get('label', 'Other')
                kitti_class = self.class_mapping.get(pandaset_class, 'DontCare')
                
                # 3D bounding box parameters (world coordinate system)
                position_world = np.array([cuboid['position.x'], cuboid['position.y'], cuboid['position.z']])
                dimensions = np.array([cuboid['dimensions.x'], cuboid['dimensions.y'], cuboid['dimensions.z']])
                yaw = cuboid.get('yaw', 0.0) # Rotation of cuboid around the z-axis
                
                # Convert to ego coordinate system
                ego_center = lidar_points_to_ego(position_world.reshape(1, 3), lidar_pose)[0]

                # Compute the yaw in ego coordinates
                yaxis_points_from_pose = lidar_points_to_ego(np.array([[0, 0, 0], [0, 1., 0]]), lidar_pose)
                yaxis_from_pose = yaxis_points_from_pose[1, :] - yaxis_points_from_pose[0, :]
                
                # rotation angle in rads of the y axis around the z axis
                zrot_world_to_ego = np.arctan2(-yaxis_from_pose[0], yaxis_from_pose[1])
                ego_yaw = yaw + zrot_world_to_ego
                
                # # Normalize to [-π, π]
                # while ego_yaw > np.pi:
                #     ego_yaw -= 2 * np.pi
                # while ego_yaw < -np.pi:
                #     ego_yaw += 2 * np.pi

                # Pandaset ego coordinates are:
                # - x pointing to the right
                # - y pointing to the front
                # - z pointing up
                # Normative coordinates are:
                # - x pointing foreward
                # - y pointings to the left
                # - z pointing to the top
                # So a transformation is required to match the normative coordinates
                
                ego_x = ego_center[1]   # x_normative = y_pandaset (front)
                ego_y = -ego_center[0]  # y_normative = -x_pandaset (left = -right)
                ego_z = ego_center[2]   # z_normative = z_pandaset (up)
                
                ego_dx = dimensions[1]  # length (front-back) -> x dimension in normative
                ego_dy = dimensions[0]  # width (left-right) -> y dimension in normative  
                ego_dz = dimensions[2]  # height (up-down) -> z dimension in normative
                
                # Convert to camera coordinate system
                position_world_homo = np.append(position_world, 1)
                position_camera = (T_world_to_camera @ position_world_homo)[:3]

                # Filter objects behind camera
                if position_camera[2] <= 0:
                    continue
                    
                # Get 3D bounding box corners and project to image
                corners_3d_camera = self.get_3d_bbox_corners_camera(
                    position_world, dimensions, yaw, T_world_to_camera
                )
                
                # Project to image plane
                bbox_2d = self.project_3d_corners_to_2d(corners_3d_camera, K)
                
                if bbox_2d is None:
                    continue
                    
                # KITTI format annotation
                truncated = 0.0  # Truncation level
                occluded = 0     # Occlusion level
                alpha = ego_yaw  # Observation angle
                
                # Construct KITTI annotation line
                label_line = f"{kitti_class} {truncated:.2f} {occluded} {alpha:.6f} " \
                           f"{bbox_2d[0]:.2f} {bbox_2d[1]:.2f} {bbox_2d[2]:.2f} {bbox_2d[3]:.2f} " \
                           f"{ego_dz} {ego_dy} {ego_dx} {ego_x} {ego_y} {ego_z} {ego_yaw}"
                
                kitti_labels.append(label_line)
                
            # Save annotation file
            label_path = os.path.join(self.output_root, 'training', 'label_2', f'{global_frame_id}.txt')
            with open(label_path, 'w') as f:
                for label in kitti_labels:
                    f.write(label + '\n')
                
            print(f"    Saved {len(kitti_labels)} annotations")
                
        except Exception as e:
            print(f"    Error converting annotations for frame {frame_idx}: {e}")
            import traceback
            traceback.print_exc()
            # Create empty annotation file
            label_path = os.path.join(self.output_root, 'training', 'label_2', f'{global_frame_id}.txt')
            open(label_path, 'w').close()
    
    def get_3d_bbox_corners_camera(self, position_world, dimensions, yaw, T_world_to_camera):
        """
        Get 8 corners of 3D bounding box in camera coordinate system
        
        Args:
            position_world: Center point in world coordinate system (3,)
            dimensions: PandaSet format dimensions [width, length, height] (3,)
            yaw: Yaw angle in world coordinate system (scalar)
            T_world_to_camera: World to camera transformation matrix (4, 4)
        
        Returns:
            corners_camera: 8 corner coordinates in camera coordinate system (8, 3)
        """
        # 1. Generate 8 corners in world coordinate system
        # Use official center_box_to_corners function (input world coordinate system parameters)
        box_world = [position_world[0], position_world[1], position_world[2],
                     dimensions[0], dimensions[1], dimensions[2], yaw]
        corners_world = center_box_to_corners(box_world)

        # 2. Convert to camera coordinate system
        corners_world_homo = np.hstack([corners_world, np.ones((8, 1))])
        corners_camera_homo = (T_world_to_camera @ corners_world_homo.T).T
        corners_camera = corners_camera_homo[:, :3]
        
        return corners_camera

    def project_3d_corners_to_2d(self, corners_3d_camera, K):
        """
        Project 3D corners to image plane and calculate 2D bounding box
        
        Args:
            corners_3d_camera: 8 corner coordinates in camera coordinate system (8, 3)
            K: Camera intrinsic matrix (3, 3)
        
        Returns:
            bbox_2d: [x1, y1, x2, y2] or None
        """
        # Filter points behind camera
        valid_corners = corners_3d_camera[corners_3d_camera[:, 2] > 0]
        
        if len(valid_corners) == 0:
            return None
        
        # Project to image plane
        points_2d_homo = (K @ valid_corners.T).T
        points_2d = points_2d_homo[:, :2] / points_2d_homo[:, 2:3]
        
        # Calculate 2D bounding box
        x_min, y_min = np.min(points_2d, axis=0)
        x_max, y_max = np.max(points_2d, axis=0)
        
        return [x_min, y_min, x_max, y_max]

    def project_3d_to_2d(self, points3d_camera, K, filter_outliers=True):
        """Project 3D points to 2D image"""
        if len(points3d_camera) == 0:
            return None
        
        inliner_indices_arr = np.arange(points3d_camera.shape[1])
        if filter_outliers:
            condition = points3d_camera[2, :] > 0.0
            points3d_camera = points3d_camera[:, condition]
            inliner_indices_arr = inliner_indices_arr[condition]
            
        # Project to image plane
        points2d_camera = K @ points3d_camera.T
        points2d_camera = points2d_camera[:2] / points2d_camera[2]

        # if filter_outliers:
        #     image_w, image_h = camera_data.size
        #     condition = np.logical_and(
        #         (points2d_camera[:, 1] < image_h) & (points2d_camera[:, 1] > 0),
        #         (points2d_camera[:, 0] < image_w) & (points2d_camera[:, 0] > 0))
        #     points2d_camera = points2d_camera[condition]
        #     points3d_camera = (points3d_camera.T)[condition]
        #     inliner_indices_arr = inliner_indices_arr[condition]
        
        # Calculate 2D bounding box
        x_min, x_max = points2d_camera[0].min(), points2d_camera[0].max()
        y_min, y_max = points2d_camera[1].min(), points2d_camera[1].max()

        return [x_min, y_min, x_max, y_max]
        
    def convert_dataset(self, sequences=None, train_ratio=0.8):
        """Convert entire dataset"""
        print("Creating KITTI directory structure...")
        self.create_kitti_directories()
        
        if sequences is None:
            # Auto-detect all sequences
            sequences = []
            for item in os.listdir(self.pandaset_root):
                if os.path.isdir(os.path.join(self.pandaset_root, item)) and item.isdigit():
                    sequences.append(item)
            sequences.sort()
            
        print(f"Found {len(sequences)} sequences: {sequences}")
        
        # Split training and testing sets
        split_idx = int(len(sequences) * train_ratio)
        train_sequences = sequences[:split_idx]
        test_sequences = sequences[split_idx:]
        
        print(f"Training sequences: {train_sequences}")
        print(f"Testing sequences: {test_sequences}")
        
        # Convert training set
        for seq_id in train_sequences:
            self.convert_sequence(seq_id, 'training')
            
        # Convert testing set
        for seq_id in test_sequences:
            self.convert_sequence(seq_id, 'testing')
            
        print("Conversion completed!")
        print(f"Output directory: {self.output_root}")
        print("\nImportant Notes:")
        print("1. Converted point cloud data is in ego coordinate system")
        print("2. Used pandar64 (sensor_id=1) forward-facing LiDAR data")
        print("3. Used front_camera camera data")
        print("4. Calibration parameters generated in KITTI format, including ego to camera transformation")
        print("5. KITTI tools can be used for calibration verification")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Convert PandaSet dataset to KITTI format')
    parser.add_argument('--pandaset_root', type=str, default='./pandaset',
                       help='PandaSet dataset root directory (default: ./pandaset)')
    parser.add_argument('--output_root', type=str, default='./pandaset-kitti',
                       help='Output KITTI format dataset directory (default: ./pandaset-kitti)')
    parser.add_argument('--sequences', type=str, nargs='+', default=None,
                       help='Specific sequences to convert (default: auto-detect all)')
    parser.add_argument('--train_ratio', type=float, default=1.0,
                       help='Training set ratio (default: 1.0)')
    parser.add_argument('--encode_img', action='store_true',
                       help='Encode images as binary files (.bin) instead of PNG files')
    parser.add_argument('--undistort_img', action='store_true', dest='undistort_img',
                       help='Enable image undistortion (default: disabled, seems pandaset images are pre-undistorted)')
    parser.add_argument('--calib_file', type=str, default="./static_extrinsic_calibration.yaml",
                       help='Path to static_extrinsic_calibration.yaml file containing camera parameters')
    
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    
    # Check if input directory exists
    if not os.path.exists(args.pandaset_root):
        print(f"Error: PandaSet data directory not found: {args.pandaset_root}")
        print("Please make sure the pandaset folder exists and contains the dataset.")
        print("Expected structure:")
        print("  pandaset/")
        print("    ├── 001/")
        print("    ├── 002/")
        print("    └── ...")
        exit(1)
    
    print(f"PandaSet data root: {os.path.abspath(args.pandaset_root)}")
    print(f"Output root: {os.path.abspath(args.output_root)}")
    print(f"Encode images: {args.encode_img}")
    print(f"Undistort images: {args.undistort_img}")
    if args.calib_file:
        print(f"Calibration file: {args.calib_file}")
    if args.encode_img:
        print("  - Images will be saved as binary .bin files")
    else:
        print("  - Images will be saved as .jpg files")
    if args.undistort_img:
        print("  - Images will be undistorted using standard radial-tangential camera model")
    else:
        print("  - Images will be saved without undistortion (use --undistort_img to disable this message)")
    
    # Create converter
    converter = PandaSetToKittiConverter(
        args.pandaset_root, 
        args.output_root, 
        args.encode_img,
        args.undistort_img,
        args.calib_file
    )
    
    # Convert dataset
    converter.convert_dataset(sequences=args.sequences, train_ratio=args.train_ratio)
