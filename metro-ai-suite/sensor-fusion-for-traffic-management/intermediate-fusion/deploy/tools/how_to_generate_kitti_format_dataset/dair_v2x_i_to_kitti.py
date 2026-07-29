import os
import numpy as np
import json
import cv2
from PIL import Image
import shutil
from pathlib import Path
import glob
from scipy.spatial.transform import Rotation as R
import open3d as o3d
import argparse

class DairV2XToKittiConverter:
    def __init__(self, dair_v2x_root, output_root, encode_img=False, undistort_img=False):
        """
        DAIR-V2X-I to KITTI format converter
        
        Args:
            dair_v2x_root: DAIR-V2X-I dataset root directory
            output_root: Output KITTI format dataset directory
            encode_img: Whether to encode images as binary files (True: encode as .bin files, False: save as .png files)
            undistort_img: Whether to undistort images using camera distortion parameters (default: False)
            
        Note:
            - DAIR-V2X-I dataset images are already undistorted during data collection
            - This version ALWAYS uses the original 'cam_K' matrix for 3D-2D projections
            - Default undistort_img=False since images are pre-undistorted in the dataset
            - Only enable undistortion if you have raw distorted images from DAIR-V2X-I
        """
        self.dair_v2x_root = dair_v2x_root
        self.output_root = output_root
        self.encode_img = encode_img
        self.undistort_img = undistort_img
        
        # KITTI class mapping (DAIR-V2X -> KITTI)
        self.class_mapping = {
            'Car': 'Car',
            'Truck': 'Truck', 
            'Van': 'Van',
            'Bus': 'Bus',
            'Pedestrian': 'Pedestrian',
            'Cyclist': 'Cyclist',
            'Tricyclist': 'Tricyclist',
            'Motorcyclist': 'Motorcyclist',
            'Barrowlist': 'Barrowlist',
            'Trafficcone': 'Trafficcone',
            'Unknown': 'DontCare'
        }
        
    def encode_image(self, img, flag=True):
        """
        Encode image as binary format
        
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
            'training/label_2',      # 3D labels
            'training/calib',        # Calibration files
            'testing/image_2',
            'testing/velodyne', 
            'testing/calib'
        ]
        
        for dir_path in dirs:
            os.makedirs(os.path.join(self.output_root, dir_path), exist_ok=True)
    
    def load_json(self, file_path):
        """Load JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON file {file_path}: {e}")
            return None
    
    def undistort_image(self, img, camera_intrinsic_data):
        """
        Undistort image using camera parameters from DAIR-V2X-I format
        
        Args:
            img: Input distorted image
            camera_intrinsic_data: Camera intrinsic data from JSON file
            
        Returns:
            undistorted_img: Undistorted image
            K_new: New camera matrix after undistortion (for consistent projection)
        """
        try:
            if not camera_intrinsic_data:
                print(f"    Warning: No camera intrinsic data provided")
                return img, None
            
            # Get distortion coefficients and camera matrix
            if 'cam_D' not in camera_intrinsic_data or 'cam_K' not in camera_intrinsic_data:
                print(f"    Warning: Missing camera parameters in intrinsic data")
                return img, None
                
            D_raw = np.array(camera_intrinsic_data['cam_D'], dtype=np.float64)
            K = np.array(camera_intrinsic_data['cam_K'], dtype=np.float64).reshape(3, 3)
            
            # Validate camera matrix
            if K.shape != (3, 3):
                print(f"    Error: Invalid camera matrix shape: {K.shape}, expected (3,3)")
                return img, None
            
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
            
            # Get optimal new camera matrix for undistortion
            h, w = img.shape[:2]
            
            # Apply standard radial-tangential undistortion with new camera matrix
            map1, map2 = cv2.initUndistortRectifyMap(
                K, D, np.eye(3), K, (w, h), cv2.CV_32FC1
            )
            undistorted_img = cv2.remap(img, map1, map2, cv2.INTER_LINEAR)

            return undistorted_img
            
        except Exception as e:
            print(f"    Warning: Could not undistort image: {e}")
            return img, None  # Return original image if undistortion fails
    
    def read_pcd_file(self, pcd_path):
        """Read PCD format point cloud file"""
        try:
            pcd = o3d.io.read_point_cloud(pcd_path)

            points = o3d.t.io.read_point_cloud(pcd_path).point["positions"].numpy() # x y z
            intensity = o3d.t.io.read_point_cloud(pcd_path).point["intensity"].numpy() # intensity
            intensity = intensity.astype(np.float32) / 255
            points_with_intensity = np.hstack([points, intensity.reshape(-1, 1)])

            return points_with_intensity

        except Exception as e:
            print(f"Error reading PCD file {pcd_path}: {e}")
            return np.array([])
    
    def virtual_lidar_to_kitti_ego(self, points_virtual_lidar):
        """
        Convert DAIR-V2X virtual LiDAR coordinate system to KITTI standard ego coordinate system
        
        Virtual LiDAR: x=front, y=left, z=up
        KITTI ego: x=front, y=left, z=up
        
        Since coordinate system definitions are the same, directly return original point cloud
        
        Args:
            points_virtual_lidar: Points in virtual LiDAR coordinate system (N, 3)
        Returns:
            points_kitti: Points in KITTI ego coordinate system (N, 3)
        """
        return points_virtual_lidar
    
    def convert_lidar_data(self, pcd_path, frame_id, split):
        """Convert LiDAR data"""
        try:
            if not os.path.exists(pcd_path):
                print(f"    Warning: PCD file not found: {pcd_path}")
                output_path = os.path.join(self.output_root, split, 'velodyne', f'{frame_id}.bin')
                np.array([], dtype=np.float32).tofile(output_path)
                return
            
            # Read point cloud data
            points_data = self.read_pcd_file(pcd_path)
            
            if len(points_data) == 0:
                print(f"    Warning: Empty lidar data for frame {frame_id}")
                output_path = os.path.join(self.output_root, split, 'velodyne', f'{frame_id}.bin')
                np.array([], dtype=np.float32).tofile(output_path)
                return
            
            # Extract coordinates and intensity
            points_virtual_lidar = points_data[:, :3]  # x, y, z
            if points_data.shape[1] >= 4:
                intensity = points_data[:, 3]
            else:
                intensity = np.zeros(len(points_virtual_lidar))
            
            # Convert to KITTI standard ego coordinate system (same coordinate system, direct copy)
            points_kitti_ego = self.virtual_lidar_to_kitti_ego(points_virtual_lidar)
            
            # Combine into KITTI format [x, y, z, intensity]
            kitti_points = np.hstack([points_kitti_ego, intensity.reshape(-1, 1)])
            
            # Save as binary file
            output_path = os.path.join(self.output_root, split, 'velodyne', f'{frame_id}.bin')
            kitti_points.astype(np.float32).tofile(output_path)
            
            print(f"    Converted {len(points_kitti_ego)} points to KITTI ego coordinate system")
            
        except Exception as e:
            print(f"    Error converting lidar data for frame {frame_id}: {e}")
            output_path = os.path.join(self.output_root, split, 'velodyne', f'{frame_id}.bin')
            np.array([], dtype=np.float32).tofile(output_path)
    
    def convert_camera_data(self, image_path, frame_id, split, camera_intrinsic_path=None):
        """Convert camera images with optional undistortion"""
        try:
            if not os.path.exists(image_path):
                print(f"    Warning: Image file not found: {image_path}")
                return None
            
            # Read original image
            image = cv2.imread(image_path)
            if image is None:
                print(f"    Warning: Failed to read image: {image_path}")
                return None
            
            # Apply undistortion if requested
            if self.undistort_img and camera_intrinsic_path:
                camera_intrinsic_data = self.load_json(camera_intrinsic_path)
                if camera_intrinsic_data:
                    image = self.undistort_image(image, camera_intrinsic_data)
                else:
                    print(f"    Warning: Could not load camera intrinsics for undistortion: {camera_intrinsic_path}")
            
            if self.encode_img:
                # Encode mode: save as binary file
                output_path = os.path.join(self.output_root, split, 'image_2', f'{frame_id}.bin')
                
                # Encode as binary
                encoded_img = self.encode_image(image, flag=True)
                
                # Save binary file
                with open(output_path, 'wb') as f:
                    f.write(encoded_img.tobytes())
                    
                print(f"    {'Undistorted and e' if self.undistort_img else 'E'}ncoded image to binary: {os.path.basename(output_path)}")
            else:
                # Direct save mode
                # Detect original file extension
                _, ext = os.path.splitext(image_path)
                if not ext:
                    ext = '.jpg'  # Default extension
                
                output_path = os.path.join(self.output_root, split, 'image_2', f'{frame_id}{ext}')
                
                if self.undistort_img:
                    # Save undistorted image
                    cv2.imwrite(output_path, image)
                    print(f"    Undistorted and saved image: {os.path.basename(output_path)}")
                else:
                    # Copy original file directly
                    import shutil
                    shutil.copy2(image_path, output_path)
                    print(f"    Copied image: {os.path.basename(image_path)} -> {os.path.basename(output_path)}")
            
            return None  # No longer return K_new since we always use original cam_K
            
        except Exception as e:
            print(f"    Error converting camera data for frame {frame_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_calibration_file(self, frame_id, split, camera_intrinsic_path, virtual_lidar_to_camera_path):
        """Generate KITTI format calibration file"""
        try:
            # Load camera intrinsics
            camera_intrinsic = self.load_json(camera_intrinsic_path)
            if camera_intrinsic is None:
                print(f"    Warning: Could not load camera intrinsics for frame {frame_id}")
                camera_intrinsic = {}
            
            # Always use original camera matrix K for projection, regardless of undistortion
            if 'cam_K' in camera_intrinsic:
                # Use original camera matrix K
                K = np.array(camera_intrinsic['cam_K']).reshape(3, 3)
                P2 = np.hstack([K, np.zeros((3, 1))])
                print(f"    Using original camera matrix cam_K for projection")
                print(f"    K: fx={K[0,0]:.2f}, fy={K[1,1]:.2f}, cx={K[0,2]:.2f}, cy={K[1,2]:.2f}")
            else:
                # Default intrinsics if cam_K not available
                K = np.array([[1000, 0, 960], [0, 1000, 540], [0, 0, 1]])
                P2 = np.hstack([K, np.zeros((3, 1))])
                print(f"    Warning: Using default camera intrinsics for frame {frame_id}")
            
            # Load virtual LiDAR to camera extrinsics
            extrinsic_data = self.load_json(virtual_lidar_to_camera_path)
            if extrinsic_data is not None:
                # Build 4x4 transformation matrix
                R = np.array(extrinsic_data['rotation']).reshape(3, 3)
                t = np.array(extrinsic_data['translation']).reshape(3, 1)
                
                T_velo_to_cam = np.eye(4)
                T_velo_to_cam[:3, :3] = R
                T_velo_to_cam[:3, 3] = t.flatten()
                
                Tr_velo_to_cam = T_velo_to_cam[:3, :]  # 3x4 transformation matrix
            else:
                # Use identity matrix as default
                Tr_velo_to_cam = np.eye(3, 4)
                print(f"    Warning: Using identity transform for frame {frame_id}")
            
            # Write calibration file
            calib_path = os.path.join(self.output_root, split, 'calib', f'{frame_id}.txt')
            with open(calib_path, 'w') as f:
                f.write(f"P0: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P1: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P2: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"P3: {' '.join(map(str, P2.flatten()))}\n")
                f.write(f"R0_rect: {' '.join(map(str, np.eye(3).flatten()))}\n")
                f.write(f"Tr_velo_to_cam: {' '.join(map(str, Tr_velo_to_cam.flatten()))}\n")
                f.write(f"Tr_imu_to_velo: {' '.join(map(str, np.eye(3, 4).flatten()))}\n")
            
        except Exception as e:
            print(f"    Error generating calibration file for frame {frame_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_3d_annotations(self, label_path, frame_id, virtual_lidar_to_camera_path):
        """Convert 3D annotations to KITTI format"""
        try:
            if not os.path.exists(label_path):
                print(f"    Warning: Label file not found: {label_path}")
                # Create empty annotation file
                output_path = os.path.join(self.output_root, 'training', 'label_2', f'{frame_id}.txt')
                open(output_path, 'w').close()
                return
            
            # Read annotation file
            label_data = self.load_json(label_path)
            if label_data is None or len(label_data) == 0:
                print(f"    Warning: Empty or invalid label file: {label_path}")
                output_path = os.path.join(self.output_root, 'training', 'label_2', f'{frame_id}.txt')
                open(output_path, 'w').close()
                return
            
            # Load extrinsics for visibility check
            extrinsic_data = self.load_json(virtual_lidar_to_camera_path)
            T_velo_to_cam = np.eye(4)
            if extrinsic_data is not None:
                R = np.array(extrinsic_data['rotation']).reshape(3, 3)
                t = np.array(extrinsic_data['translation']).reshape(3, 1)
                T_velo_to_cam[:3, :3] = R
                T_velo_to_cam[:3, 3] = t.flatten()
            
            kitti_labels = []
            
            for obj in label_data:
                try:
                    # Map class
                    obj_type = obj.get('type', 'Unknown')
                    kitti_class = self.class_mapping.get(obj_type, 'DontCare')
                    
                    # Skip DontCare class
                    if kitti_class == 'DontCare':
                        continue
                    
                    # 3D BBox
                    if '3d_location' in obj and '3d_dimensions' in obj:
                        # Center point position (virtual LiDAR coordinate system)
                        location = obj['3d_location']
                        center_virtual_lidar = np.array([
                            float(location['x']), 
                            float(location['y']), 
                            float(location['z'])
                        ])
                        
                        # Dimensions
                        dimensions = obj['3d_dimensions']
                        h = float(dimensions['h'])  # Height
                        w = float(dimensions['w'])  # Width
                        l = float(dimensions['l'])  # Length                        
                        # Rotation angle
                        rotation_y = float(obj.get('rotation', 0.0))
                        
                        # Convert to KITTI ego coordinate system (same coordinate system, direct copy)
                        center_kitti_ego = self.virtual_lidar_to_kitti_ego(center_virtual_lidar.reshape(1, 3))[0]
                        
                        # Convert to camera coordinate system for visibility check
                        center_ego_homo = np.append(center_kitti_ego, 1)
                        center_camera = (T_velo_to_cam @ center_ego_homo)[:3]
                        
                        # Filter objects behind camera
                        if center_camera[2] <= 0:
                            continue
                        
                        # KITTI format parameters
                        truncated = float(obj.get('truncated_state', 0.0))
                        occluded = int(obj.get('occluded_state', 0))
                        alpha = float(obj.get('alpha', rotation_y))  # Observation angle
                        
                        # 2D bounding box (if available)
                        if '2d_box' in obj:
                            bbox_2d = obj['2d_box']
                            x1 = float(bbox_2d['xmin'])
                            y1 = float(bbox_2d['ymin'])
                            x2 = float(bbox_2d['xmax'])
                            y2 = float(bbox_2d['ymax'])
                        else:
                            # Use default values
                            x1, y1, x2, y2 = 0, 0, 50, 50
                        
                        # 3D information (in KITTI ego coordinate system)
                        x, y, z = center_kitti_ego
                        ry = rotation_y
                        
                        # Construct KITTI annotation line
                        label_line = f"{kitti_class} {truncated:.2f} {occluded} {alpha:.6f} " \
                                   f"{x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} " \
                                   f"{h:.2f} {w:.2f} {l:.2f} {x:.2f} {y:.2f} {z:.2f} {ry:.6f}"
                        
                        kitti_labels.append(label_line)
                        
                except Exception as e:
                    print(f"    Error processing object in {label_path}: {e}")
                    continue
            
            # Save annotation file
            output_path = os.path.join(self.output_root, 'training', 'label_2', f'{frame_id}.txt')
            with open(output_path, 'w') as f:
                for label in kitti_labels:
                    f.write(label + '\n')
            
            print(f"    Saved {len(kitti_labels)} annotations")
            
        except Exception as e:
            print(f"    Error converting annotations for frame {frame_id}: {e}")
            import traceback
            traceback.print_exc()
            # Create empty annotation file
            output_path = os.path.join(self.output_root, 'training', 'label_2', f'{frame_id}.txt')
            open(output_path, 'w').close()
    
    def convert_dataset(self, data_split='training', max_frames=None):
        """Convert dataset"""
        print("Creating KITTI directory structure...")
        self.create_kitti_directories()
        
        # Check data_info.json
        data_info_path = os.path.join(self.dair_v2x_root, 'data_info.json')
        if not os.path.exists(data_info_path):
            print(f"Error: data_info.json not found at {data_info_path}")
            return
        
        print(f"Found data_info.json: {data_info_path}")
        
        # Read data information
        data_info = self.load_json(data_info_path)
        if data_info is None:
            print("Error: Failed to load data_info.json")
            return
        
        print(f"Total frames in data_info.json: {len(data_info)}")
        
        # Process each frame data
        frame_count = 0
        processed_count = 0
        
        for frame_info in data_info:
            if max_frames and frame_count >= max_frames:
                break
                
            frame_count += 1
            frame_id = f"{frame_count-1:06d}"
            
            try:
                print(f"Processing frame {frame_id} ({frame_count}/{len(data_info)})...")
                
                # Get file paths (relative to dataset root directory)
                image_path = os.path.join(self.dair_v2x_root, frame_info.get('image_path', ''))
                pointcloud_path = os.path.join(self.dair_v2x_root, frame_info.get('pointcloud_path', ''))
                camera_intrinsic_path = os.path.join(self.dair_v2x_root, frame_info.get('calib_camera_intrinsic_path', ''))
                virtual_lidar_to_camera_path = os.path.join(self.dair_v2x_root, frame_info.get('calib_virtuallidar_to_camera_path', ''))
                
                # Annotation file path
                label_virtuallidar_path = os.path.join(self.dair_v2x_root, frame_info.get('label_lidar_std_path', ''))
                
                # Convert data
                self.convert_lidar_data(pointcloud_path, frame_id, data_split)
                self.convert_camera_data(image_path, frame_id, data_split, camera_intrinsic_path)
                self.generate_calibration_file(frame_id, data_split, camera_intrinsic_path, virtual_lidar_to_camera_path)
                
                # Only convert annotations for training set
                if data_split == 'training':
                    self.convert_3d_annotations(label_virtuallidar_path, frame_id, virtual_lidar_to_camera_path)
                
                processed_count += 1
                print(f"  Frame {frame_id} processed successfully")
                
            except Exception as e:
                print(f"  Error processing frame {frame_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\nConversion completed!")
        print(f"Processed: {processed_count}/{frame_count} frames")
        print(f"Output directory: {self.output_root}")
        print(f"\nImportant Notes:")
        print(f"1. Converted point cloud data is in KITTI standard ego coordinate system")
        print(f"2. Coordinate system: x=front, y=left, z=up")
        print(f"3. Calibration parameters generated in KITTI format")
        print(f"4. Class mapping: {self.class_mapping}")
        print(f"5. Can use KITTI tools for calibration verification")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Convert DAIR-V2X-I dataset to KITTI format')
    parser.add_argument('--dair_v2x_root', type=str, default='./dair-v2x-i',
                       help='DAIR-V2X-I dataset root directory (default: ./dair-v2x-i)')
    parser.add_argument('--output_root', type=str, default='./dair-v2x-i-kitti',
                       help='Output KITTI format dataset directory (default: ./dair-v2x-i-kitti)')
    parser.add_argument('--data_split', type=str, default='training', choices=['training', 'testing'],
                       help='Data split to convert (default: training)')
    parser.add_argument('--max_frames', type=int, default=None,
                       help='Maximum number of frames to convert (default: all)')
    parser.add_argument('--encode_img', action='store_true',
                       help='Encode images as binary files (.bin) instead of jpg files')
    parser.add_argument('--undistort_img', action='store_true', 
                       help='Enable image undistortion (default: disabled, since DAIR-V2X-I images are pre-undistorted)')
    
    return parser.parse_args()


def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Check if input directory exists
    if not os.path.exists(args.dair_v2x_root):
        print(f"Error: DAIR-V2X-I data directory not found: {args.dair_v2x_root}")
        print("Please make sure the dair-v2x-i folder exists and contains the dataset.")
        print("Expected structure:")
        print("  dair-v2x-i/")
        print("    ├── data_info.json")
        print("    ├── velodyne/")
        print("    ├── image/")
        print("    ├── calib/")
        print("    └── label/")
        return
    
    print(f"DAIR-V2X-I data root: {os.path.abspath(args.dair_v2x_root)}")
    print(f"Output root: {os.path.abspath(args.output_root)}")
    print(f"Data split: {args.data_split}")
    print(f"Max frames: {args.max_frames if args.max_frames else 'All'}")
    print(f"Encode images: {args.encode_img}")
    print(f"Undistort images: {args.undistort_img}")
    if args.encode_img:
        print("  - Images will be saved as binary .bin files")
    else:
        print("  - Images will be saved as .jpg files")
    if args.undistort_img:
        print("  - Images will be undistorted using standard radial-tangential camera model")
        print("  - WARNING: DAIR-V2X-I images are already pre-undistorted!")
    else:
        print("  - Images will be used as-is (recommended for DAIR-V2X-I dataset)")
    
    # Create converter
    converter = DairV2XToKittiConverter(args.dair_v2x_root, args.output_root, args.encode_img, args.undistort_img)
    
    # Convert dataset
    converter.convert_dataset(
        data_split=args.data_split,
        max_frames=args.max_frames
    )


if __name__ == "__main__":
    main()
