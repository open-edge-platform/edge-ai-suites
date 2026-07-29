import numpy as np
import cv2
import open3d as o3d
import matplotlib.pyplot as plt
import os
from typing import Tuple, List, Dict, Optional
import glob
import argparse
import traceback

class KittiDairV2XVerifier:
    """KITTI format DAIR-V2X-I dataset calibration parameter verifier"""
    
    def __init__(self, kitti_root: str, decode_img: bool = False):
        """
        Initialize the verifier
        Args:
            kitti_root: KITTI format dataset root directory
            decode_img: Whether to decode image files (when images are stored in .bin format)
        """
        self.kitti_root = kitti_root
        self.decode_img = decode_img
        
        # Define all object categories and their color encodings (BGR format)
        self.object_colors = {
            'Car': (0, 255, 0),           # Green
            'Truck': (0, 165, 255),       # Orange
            'Van': (255, 0, 255),         # Purple
            'Tram': (255, 255, 0),        # Cyan (Bus mapped to Tram)
            'Pedestrian': (255, 0, 0),    # Blue
            'Cyclist': (0, 255, 255),     # Yellow
            'DontCare': (128, 128, 128),  # Gray
            'Unknown': (128, 128, 128)    # Gray
        }
        
    def load_calibration_data(self, frame_id: str, split: str = 'training') -> Dict[str, np.ndarray]:
        """
        Load KITTI format calibration data
        Args:
            frame_id: Frame ID (e.g., '000000')
            split: Dataset split ('training' or 'testing')
        Returns:
            calib_data: Calibration data dictionary
        """
        calib_path = os.path.join(self.kitti_root, split, 'calib', f'{frame_id}.txt')
        
        if not os.path.exists(calib_path):
            raise FileNotFoundError(f"Calibration file not found: {calib_path}")
        
        calib_data = {}
        
        with open(calib_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    key, values = line.split(':', 1)
                    key = key.strip()
                    values = np.array([float(x) for x in values.strip().split()])
                    
                    if key in ['P0', 'P1', 'P2', 'P3']:
                        calib_data[key] = values.reshape(3, 4)
                    elif key == 'R0_rect':
                        calib_data[key] = values.reshape(3, 3)
                    elif key in ['Tr_velo_to_cam', 'Tr_imu_to_velo']:
                        calib_data[key] = values.reshape(3, 4)
        
        # Extract camera intrinsic matrix
        if 'P2' in calib_data:
            P2 = calib_data['P2']
            calib_data['K'] = P2[:3, :3]  # Intrinsic matrix
            
        print(f"Calibration data loaded for frame {frame_id}:")
        if 'K' in calib_data:
            K = calib_data['K']
            print(f"  - Focal length: fx={K[0,0]:.1f}, fy={K[1,1]:.1f}")
            print(f"  - Principal point: cx={K[0,2]:.1f}, cy={K[1,2]:.1f}")
        
        if 'Tr_velo_to_cam' in calib_data:
            print(f"  - Velodyne to camera transformation available")
        
        return calib_data
    
    def load_pointcloud(self, frame_id: str, split: str = 'training') -> np.ndarray:
        """
        Load KITTI format point cloud data
        Args:
            frame_id: Frame ID
            split: Dataset split
        Returns:
            points: Point cloud coordinates and intensities (N, 4) [x, y, z, intensity]
        """
        pc_path = os.path.join(self.kitti_root, split, 'velodyne', f'{frame_id}.bin')
        
        if not os.path.exists(pc_path):
            raise FileNotFoundError(f"Point cloud file not found: {pc_path}")
        
        # Read binary point cloud file
        points = np.fromfile(pc_path, dtype=np.float32).reshape(-1, 4)
        
        print(f"Point cloud loaded: {len(points)} points")
        print(f"  - X range: [{points[:, 0].min():.2f}, {points[:, 0].max():.2f}]")
        print(f"  - Y range: [{points[:, 1].min():.2f}, {points[:, 1].max():.2f}]")
        print(f"  - Z range: [{points[:, 2].min():.2f}, {points[:, 2].max():.2f}]")
        
        return points
    
    def decode_image(self, bin_path: str) -> np.ndarray:
        """
        Decode binary image file
        Args:
            bin_path: Binary image file path
        Returns:
            image: BGR image
        """
        try:
            with open(bin_path, 'rb') as f:
                img_data = f.read()
            img_array = np.frombuffer(img_data, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            raise RuntimeError(f"Failed to decode image from {bin_path}: {e}")
    
    def load_image(self, frame_id: str, split: str = 'training') -> np.ndarray:
        """
        Load KITTI format image data
        Args:
            frame_id: Frame ID
            split: Dataset split
        Returns:
            image: BGR image
        """
        if self.decode_img:
            # Image stored in .bin format, needs decoding
            image_path = os.path.join(self.kitti_root, split, 'image_2', f'{frame_id}.bin')
            
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Binary image file not found: {image_path}")
            
            image = self.decode_image(image_path)
        else:
            # Image stored in standard formats (png, jpg, etc.)
            # Try multiple common formats
            image_extensions = ['.png', '.jpg', '.jpeg']
            image_path = None
            
            for ext in image_extensions:
                candidate_path = os.path.join(self.kitti_root, split, 'image_2', f'{frame_id}{ext}')
                if os.path.exists(candidate_path):
                    image_path = candidate_path
                    break
            
            if image_path is None:
                raise FileNotFoundError(f"Image file not found for frame {frame_id} in {split} set")
            
            image = cv2.imread(image_path)
            
        if image is None:
            raise RuntimeError(f"Failed to load image for frame {frame_id}")
            
        return image
    
    def load_3d_labels(self, frame_id: str) -> List[Dict]:
        """
        Load KITTI format 3D annotation data
        Args:
            frame_id: Frame ID
        Returns:
            labels: 3D annotation list
        """
        label_path = os.path.join(self.kitti_root, 'training', 'label_2', f'{frame_id}.txt')
        
        if not os.path.exists(label_path):
            print(f"Warning: Label file not found: {label_path}")
            return []
        
        labels = []
        
        try:
            with open(label_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split()
                    if len(parts) < 15:
                        continue
                    
                    label = {
                        'type': parts[0],
                        'truncated': float(parts[1]),
                        'occluded': int(parts[2]),
                        'alpha': float(parts[3]),
                        'bbox_2d': [float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])],
                        'dimensions': [float(parts[8]), float(parts[9]), float(parts[10])],  # h, w, l
                        'location': [float(parts[11]), float(parts[12]), float(parts[13])],   # x, y, z
                        'rotation_y': float(parts[14])
                    }
                    labels.append(label)
            
            print(f"Loaded {len(labels)} 3D labels")
            
            # Count statistics for each category
            type_count = {}
            for label in labels:
                obj_type = label['type']
                type_count[obj_type] = type_count.get(obj_type, 0) + 1
            print(f"Object types: {type_count}")
            
        except Exception as e:
            print(f"Error loading label file {label_path}: {e}")
            return []
        
        return labels
    
    def transform_points_to_camera(self, points_3d: np.ndarray, calib_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Transform points from ego coordinate system to camera coordinate system
        Args:
            points_3d: 3D point coordinates in ego coordinate system (N, 3)
            calib_data: Calibration data
        Returns:
            points_cam: Points in camera coordinate system (N, 3)
        """
        if 'Tr_velo_to_cam' not in calib_data:
            raise ValueError("Tr_velo_to_cam not found in calibration data")
        
        # Get ego to camera transformation matrix
        Tr_velo_to_cam = calib_data['Tr_velo_to_cam']  # 3x4
        
        # Build 4x4 transformation matrix
        T_velo_to_cam = np.eye(4)
        T_velo_to_cam[:3, :] = Tr_velo_to_cam
        
        # Convert to homogeneous coordinates
        points_homo = np.hstack([points_3d, np.ones((points_3d.shape[0], 1))])
        
        # Apply transformation
        points_cam_homo = (T_velo_to_cam @ points_homo.T).T
        points_cam = points_cam_homo[:, :3]
        
        return points_cam
    
    def project_to_image(self, points_cam: np.ndarray, calib_data: Dict[str, np.ndarray], 
                        image_shape: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project points from camera coordinate system to image pixel coordinates
        Args:
            points_cam: Points in camera coordinate system (N, 3)
            calib_data: Calibration data
            image_shape: Image dimensions (height, width)
        Returns:
            points_2d: Image coordinates (M, 2)
            valid_mask: Valid points mask
        """
        if 'K' not in calib_data:
            raise ValueError("Camera intrinsics not found in calibration data")
        
        K = calib_data['K']
        
        # Filter points behind the camera
        front_mask = points_cam[:, 2] > 0
        points_cam_front = points_cam[front_mask]
        
        if len(points_cam_front) == 0:
            return np.array([]), front_mask
        
        # Project to image plane
        points_2d_homo = (K @ points_cam_front.T).T
        points_2d = points_2d_homo[:, :2] / points_2d_homo[:, 2:3]
        
        # Filter points outside image boundaries
        h, w = image_shape
        boundary_mask = (
            (points_2d[:, 0] >= 0) & (points_2d[:, 0] < w) &
            (points_2d[:, 1] >= 0) & (points_2d[:, 1] < h)
        )
        
        # Update valid mask
        valid_indices = np.where(front_mask)[0]
        final_valid_mask = np.zeros_like(front_mask)
        final_valid_mask[valid_indices[boundary_mask]] = True
        
        return points_2d[boundary_mask], final_valid_mask
    
    def get_3d_box_corners(self, label: Dict) -> np.ndarray:
        """
        Get the 8 corner coordinates of KITTI format 3D box
        Args:
            label: KITTI format annotation dictionary
        Returns:
            corners: 8 corner coordinates (8, 3) in ego coordinate system
        """
        try:
            # KITTI format data
            h, w, l = label['dimensions']  # height, width, length
            x, y, z = label['location']    # x, y, z in ego coordinate
            ry = label['rotation_y']       # for dair-v2x-i is rotation around Z axis
            
            # Define 8 corners in local coordinate system (center at origin)
            # KITTI ego coordinate system: x=forward, y=left, z=up
            corners_local = np.array([
                [-l/2, -w/2, -h/2],  # 0: back-bottom-right
                [l/2, -w/2, -h/2],   # 1: front-bottom-right
                [l/2, w/2, -h/2],    # 2: front-bottom-left
                [-l/2, w/2, -h/2],   # 3: back-bottom-left
                [-l/2, -w/2, h/2],   # 4: back-top-right
                [l/2, -w/2, h/2],    # 5: front-top-right
                [l/2, w/2, h/2],     # 6: front-top-left
                [-l/2, w/2, h/2]     # 7: back-top-left
            ])
            
            # Rotation matrix (around Z axis)
            cos_ry = np.cos(ry)
            sin_ry = np.sin(ry)

            R = np.array(
                [[cos_ry, -sin_ry, 0], [sin_ry, cos_ry, 0], [0, 0, 1]]
            )
            
            # Apply rotation and translation
            corners_rotated = (R @ corners_local.T).T
            corners_ego = corners_rotated + np.array([x, y, z])
            
            return corners_ego
            
        except Exception as e:
            print(f"Error processing 3D box: {e}")
            return np.array([])
    
    def create_depth_colormap(self, depths: np.ndarray) -> np.ndarray:
        """
        Create depth color mapping
        Args:
            depths: Depth values array
        Returns:
            colors: RGB color array (N, 3)
        """
        if len(depths) == 0:
            return np.array([])
        
        # Normalize depth values to [0, 1]
        depths_norm = (depths - depths.min()) / (depths.max() - depths.min() + 1e-8)
        
        # Use colormap to create colors
        colormap = plt.cm.jet
        colors_rgba = colormap(depths_norm)
        colors_rgb = (colors_rgba[:, :3] * 255).astype(np.uint8)
        
        return colors_rgb
    
    def draw_3d_box_projection(self, image: np.ndarray, corners_2d: np.ndarray, 
                              color: Tuple[int, int, int] = (0, 255, 0), 
                              thickness: int = 2) -> np.ndarray:
        """
        Draw 2D projection of 3D box on image
        Args:
            image: Input image
            corners_2d: Projected 8 corners (8, 2)
            color: Line color (B, G, R)
            thickness: Line thickness
        Returns:
            image: Image after drawing
        """
        if len(corners_2d) != 8:
            return image
        
        corners_2d = corners_2d.astype(int)
        
        # Define edge connections for 3D box
        edges = [
            # Bottom face
            (0, 1), (1, 2), (2, 3), (3, 0),
            # Top face
            (4, 5), (5, 6), (6, 7), (7, 4),
            # Vertical edges
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]
        
        # Draw edges
        for start_idx, end_idx in edges:
            start_point = tuple(corners_2d[start_idx])
            end_point = tuple(corners_2d[end_idx])
            cv2.line(image, start_point, end_point, color, thickness)
        
        return image
    
    def draw_2d_bbox(self, image: np.ndarray, bbox: List[float], 
                     color: Tuple[int, int, int] = (255, 0, 0), 
                     thickness: int = 2) -> np.ndarray:
        """
        Draw 2D bounding box on image
        Args:
            image: Input image
            bbox: [x1, y1, x2, y2]
            color: Line color (B, G, R)
            thickness: Line thickness
        Returns:
            image: Image after drawing
        """
        x1, y1, x2, y2 = [int(coord) for coord in bbox]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        return image
    
    def visualize_projection(self, frame_id: str, split: str = 'training', 
                           max_points: int = 50000, save_path: Optional[str] = None,
                           show_2d_bbox: bool = True) -> np.ndarray:
        """
        Visualize point cloud and 3D box projection on image
        Args:
            frame_id: Frame ID
            split: Dataset split
            max_points: Maximum number of points to display
            save_path: Save path
            show_2d_bbox: Whether to show 2D bounding boxes
        Returns:
            result_image: Visualization result image
        """
        print(f"Processing frame {frame_id}...")
        
        try:
            # Load data
            calib_data = self.load_calibration_data(frame_id, split)
            points_data = self.load_pointcloud(frame_id, split)
            image = self.load_image(frame_id, split)
            labels = self.load_3d_labels(frame_id) if split == 'training' else []
            
            if image is None:
                print(f"Error: Could not load image for frame {frame_id}")
                return None
            
            print(f"Image shape: {image.shape}")
            print(f"Point cloud size: {len(points_data)}")
            print(f"Number of labels: {len(labels)}")
            
            # Extract 3D coordinates
            points_3d = points_data[:, :3]  # x, y, z
            intensities = points_data[:, 3]  # intensity
            
            # Randomly sample point cloud to reduce computation
            if len(points_3d) > max_points:
                indices = np.random.choice(len(points_3d), max_points, replace=False)
                points_3d = points_3d[indices]
                intensities = intensities[indices]
            
            # Transform point cloud to camera coordinate system
            points_cam = self.transform_points_to_camera(points_3d, calib_data)
            
            # Project to image
            points_2d, valid_mask = self.project_to_image(
                points_cam, calib_data, (image.shape[0], image.shape[1])
            )
            
            # Create result image
            result_image = image.copy()
            
            print(f"Valid projected points: {len(points_2d)}")
            
            if len(points_2d) > 0:
                # Get depth values of valid points
                valid_depths = points_cam[valid_mask, 2]
                
                # Create depth color mapping
                colors = self.create_depth_colormap(valid_depths)
                
                # Draw point cloud projection
                for i, (point_2d, color) in enumerate(zip(points_2d, colors)):
                    x, y = int(point_2d[0]), int(point_2d[1])
                    cv2.circle(result_image, (x, y), 1, 
                              (int(color[2]), int(color[1]), int(color[0])), -1)
            
            # Draw 3D box projections
            valid_box_count = 0
            for i, label in enumerate(labels):
                try:
                    # Get 3D box corners
                    corners_3d = self.get_3d_box_corners(label)
                    
                    if len(corners_3d) == 0:
                        continue
                    
                    # Transform to camera coordinate system
                    corners_cam = self.transform_points_to_camera(corners_3d, calib_data)
                    
                    # Check how many corners are in front of the camera
                    front_corners = np.sum(corners_cam[:, 2] > 0)
                    
                    if front_corners >= 4:  # Draw only if at least 4 corners are in front
                        # Project all corners
                        corners_2d_all = []
                        valid_corners = 0
                        
                        for corner_cam in corners_cam:
                            if corner_cam[2] > 0:  # In front of camera
                                corner_2d_homo = calib_data['K'] @ corner_cam
                                corner_2d = corner_2d_homo[:2] / corner_2d_homo[2]
                                corners_2d_all.append(corner_2d)
                                
                                # Check if within image boundaries
                                if (0 <= corner_2d[0] < image.shape[1] and 
                                    0 <= corner_2d[1] < image.shape[0]):
                                    valid_corners += 1
                            else:
                                # For points behind camera, use placeholder
                                corners_2d_all.append([0, 0])
                        
                        corners_2d_all = np.array(corners_2d_all)
                        
                        # If there are enough corners within image, draw 3D box
                        if valid_corners >= 2:
                            # Choose color based on object type
                            obj_type = label['type']
                            color = self.object_colors.get(obj_type, self.object_colors['Unknown'])
                            
                            result_image = self.draw_3d_box_projection(
                                result_image, corners_2d_all, color, thickness=2
                            )
                            valid_box_count += 1
                            
                            # Add object type label
                            if valid_corners > 0:
                                # Find topmost valid corner as label position
                                valid_points = corners_2d_all[corners_cam[:, 2] > 0]
                                if len(valid_points) > 0:
                                    label_pos = valid_points[np.argmin(valid_points[:, 1])]
                                    cv2.putText(result_image, f"3D-{obj_type}", 
                                              (int(label_pos[0]), int(label_pos[1]) - 5),
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                        
                        # Draw 2D annotation box (if enabled)
                        if show_2d_bbox and 'bbox_2d' in label:
                            bbox_2d = label['bbox_2d']
                            result_image = self.draw_2d_bbox(
                                result_image, bbox_2d, (0, 0, 255), thickness=1
                            )
                            
                            # Add 2D annotation type label
                            label_pos = (int(bbox_2d[0]), int(bbox_2d[1]) - 20)
                            cv2.putText(result_image, f"2D-{obj_type}", 
                                      label_pos, cv2.FONT_HERSHEY_SIMPLEX, 
                                      0.5, (0, 0, 255), 1)
                        
                except Exception as e:
                    print(f"Error processing 3D box {i}: {e}")
                    continue
            
            # Add information text
            info_color = (255, 255, 255)
            y_offset = 30
            cv2.putText(result_image, f"Frame: {frame_id}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, info_color, 2)
            y_offset += 40
            cv2.putText(result_image, f"Points: {len(points_2d)}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
            y_offset += 40
            cv2.putText(result_image, f"3D Boxes: {valid_box_count}/{len(labels)}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
            y_offset += 40
            cv2.putText(result_image, f"Split: {split}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
            y_offset += 40
            cv2.putText(result_image, f"Resolution: {image.shape[1]}x{image.shape[0]}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
            y_offset += 40
            cv2.putText(result_image, f"Coordinate: KITTI ego (x=front, y=left, z=up)", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, info_color, 1)
            
            # Add color legend
            legend_y = y_offset + 60
            legend_items = list(self.object_colors.items())
            
            for i, (name, color) in enumerate(legend_items):
                if name == 'Unknown':
                    continue  # Skip Unknown category
                y_pos = legend_y + i * 25
                cv2.rectangle(result_image, (10, y_pos - 10), (30, y_pos + 10), color, -1)
                cv2.putText(result_image, name, (35, y_pos + 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, info_color, 1)
            
            # Add instructions
            if show_2d_bbox:
                legend_y += len([x for x in legend_items if x[0] != 'Unknown']) * 25 + 20
                cv2.putText(result_image, "3D projection (colored)", (10, legend_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, info_color, 1)
                cv2.putText(result_image, "2D annotation (red)", (10, legend_y + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Save results
            if save_path:
                cv2.imwrite(save_path, result_image)
                print(f"Result saved to {save_path}")
            
            return result_image
            
        except Exception as e:
            print(f"Error processing frame {frame_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def batch_verify(self, frame_ids: List[str], split: str = 'training', 
                     output_dir: str = "verification_results"):
        """
        Batch verify multiple frames
        Args:
            frame_ids: Frame ID list
            split: Dataset split
            output_dir: Output directory
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"Starting batch verification for {len(frame_ids)} frames in {split} set...")
        
        success_count = 0
        for i, frame_id in enumerate(frame_ids):
            try:
                save_path = os.path.join(output_dir, f"verification_{frame_id}.jpg")
                result_image = self.visualize_projection(
                    frame_id, split=split, save_path=save_path
                )
                
                if result_image is not None:
                    success_count += 1
                
                print(f"Progress: {i+1}/{len(frame_ids)} completed ({success_count} successful)")
                
            except Exception as e:
                print(f"Error processing frame {frame_id}: {e}")
                continue
        
        print(f"Batch verification completed. {success_count}/{len(frame_ids)} frames processed successfully.")
        print(f"Results saved in {output_dir}")

def get_available_frames(kitti_root: str, split: str = 'training', max_frames: int = 20) -> List[str]:
    """
    Get available frame ID list
    Args:
        kitti_root: KITTI dataset root directory
        split: Dataset split
        max_frames: Maximum number of frames
    Returns:
        frame_ids: Available frame ID list
    """
    image_dir = os.path.join(kitti_root, split, 'image_2')
    if not os.path.exists(image_dir):
        print(f"Error: Image directory not found: {image_dir}")
        return []
    
    # Get all image files, supporting multiple formats
    image_files = []
    
    # Supported image formats: standard formats and binary formats
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.bin']
    
    for ext in extensions:
        files = glob.glob(os.path.join(image_dir, ext))
        image_files.extend(files)
    
    # Remove duplicates and sort
    image_files = list(set(image_files))
    image_files.sort()

    print(f"Found {len(image_files)} image files in {image_dir}")
    if image_files:
        print(f"Sample files: {[os.path.basename(f) for f in image_files[:3]]}")
    
    # Extract frame IDs
    frame_ids = []
    for img_file in image_files[:max_frames]:
        frame_id = os.path.basename(img_file).split('.')[0]
        frame_ids.append(frame_id)
    
    return frame_ids

def create_summary_image(frame_ids: List[str], output_path: str = "verification_summary.jpg"):
    """
    Create summary image showing thumbnails of multiple frames
    Args:
        frame_ids: Frame ID list
        output_path: Output path
    """
    try:
        images = []
        for frame_id in frame_ids:
            img_path = f"verification_results/verification_{frame_id}.jpg"
            if os.path.exists(img_path):
                img = cv2.imread(img_path)
                if img is not None:
                    # Scale to uniform size
                    img_resized = cv2.resize(img, (640, 360))  # 16:9 ratio
                    # Add frame ID label
                    cv2.putText(img_resized, f"Frame: {frame_id}", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    images.append(img_resized)
        
        if len(images) >= 4:
            # Create 2x2 grid
            top_row = np.hstack([images[0], images[1]])
            bottom_row = np.hstack([images[2], images[3]])
            summary_img = np.vstack([top_row, bottom_row])
        elif len(images) >= 2:
            # Create 1x2 grid
            summary_img = np.hstack(images[:2])
        elif len(images) == 1:
            summary_img = images[0]
        else:
            print("No images found for summary")
            return
        
        cv2.imwrite(output_path, summary_img)
        print(f"Summary image saved to {output_path}")
        
    except Exception as e:
        print(f"Error creating summary image: {e}")

def generate_verification_report(frame_ids: List[str], verifier: KittiDairV2XVerifier, split: str):
    """
    Generate verification report
    Args:
        frame_ids: Frame ID list
        verifier: Verifier instance
        split: Dataset split
    """
    print(f"\n=== Verification Report ===")
    
    total_frames = len(frame_ids)
    successful_frames = 0
    total_objects = 0
    object_type_stats = {}
    
    for frame_id in frame_ids:
        result_path = f"verification_results/verification_{frame_id}.jpg"
        if os.path.exists(result_path):
            successful_frames += 1
            
            # Count annotation information (only training set has annotations)
            if split == 'training':
                try:
                    labels = verifier.load_3d_labels(frame_id)
                    frame_object_count = len(labels)
                    total_objects += frame_object_count
                    
                    for label in labels:
                        obj_type = label.get('type', 'Unknown')
                        object_type_stats[obj_type] = object_type_stats.get(obj_type, 0) + 1
                        
                except Exception as e:
                    print(f"Error processing labels for {frame_id}: {e}")
    
    print(f"Processed frames: {successful_frames}/{total_frames}")
    if split == 'training':
        print(f"Total objects detected: {total_objects}")
        print(f"Object type distribution:")
        for obj_type, count in sorted(object_type_stats.items()):
            percentage = (count / total_objects * 100) if total_objects > 0 else 0
            print(f"  - {obj_type}: {count} ({percentage:.1f}%)")
    
    # Save report to file
    with open("dair_v2x_verification_report.txt", 'w') as f:
        f.write("KITTI-Format DAIR-V2X-I Calibration Verification Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Processing Summary:\n")
        f.write(f"  - Dataset split: {split}\n")
        f.write(f"  - Processed frames: {successful_frames}/{total_frames}\n")
        f.write(f"  - Success rate: {successful_frames/total_frames*100:.1f}%\n")
        
        if split == 'training':
            f.write(f"  - Total objects: {total_objects}\n")
            f.write(f"\nObject Type Distribution:\n")
            for obj_type, count in sorted(object_type_stats.items()):
                percentage = (count / total_objects * 100) if total_objects > 0 else 0
                f.write(f"  - {obj_type}: {count} ({percentage:.1f}%)\n")
        
        f.write(f"\nDataset Information:\n")
        f.write(f"  - Original format: DAIR-V2X-I (virtual LiDAR coordinate)\n")
        f.write(f"  - Converted format: KITTI (ego coordinate)\n")
        f.write(f"  - Coordinate system: x=front, y=left, z=up\n")
        f.write(f"  - Class mapping applied for KITTI compatibility\n")
        
        f.write(f"\nGenerated Files:\n")
        f.write(f"  - Individual results: verification_results/\n")
        f.write(f"  - Summary image: verification_summary.jpg\n")
        f.write(f"  - This report: dair_v2x_verification_report.txt\n")
        
        f.write(f"\nCalibration Quality Assessment:\n")
        f.write(f"  - Point cloud alignment with image features\n")
        f.write(f"  - 3D box projection accuracy\n")
        if split == 'training':
            f.write(f"  - Alignment between 3D projections and 2D annotations\n")
        f.write(f"  - Different object types shown in different colors\n")
        f.write(f"  - Virtual LiDAR to camera transformation verification\n")
    
    print(f"\nDetailed report saved to dair_v2x_verification_report.txt")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Verify KITTI-format DAIR-V2X-I dataset calibration parameters')
    parser.add_argument('--kitti_root', type=str, default='./dair-v2x-i-kitti',
                       help='KITTI format dataset root directory (default: ./dair-v2x-i-kitti)')
    parser.add_argument('--split', type=str, default='training', choices=['training', 'testing'],
                       help='Dataset split to verify (default: training)')
    parser.add_argument('--max_frames', type=int, default=100,
                       help='Maximum number of frames to process (default: 100)')
    parser.add_argument('--batch_frames', type=int, default=25,
                       help='Number of frames for batch verification (default: 25)')
    parser.add_argument('--max_points', type=int, default=50000,
                       help='Maximum points to display for visualization (default: 50000)')
    parser.add_argument('--output_dir', type=str, default='dair_v2x_verification_results',
                       help='Output directory for verification results (default: dair_v2x_verification_results)')
    parser.add_argument('--single_frame', type=str, default=None,
                       help='Verify only a specific frame ID (e.g., 000000)')
    parser.add_argument('--no_batch', action='store_true',
                       help='Skip batch verification, only verify single frame')
    parser.add_argument('--show_2d_bbox', action='store_true', default=True,
                       help='Show 2D bounding boxes (only for training split)')
    parser.add_argument('--decode_img', action='store_true',
                       help='Decode binary image files (.bin format) - use when dataset was converted with --encode_img')
    
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Check if dataset exists
    if not os.path.exists(args.kitti_root):
        print(f"Error: KITTI data directory not found: {args.kitti_root}")
        print("Please make sure the KITTI format folder exists and contains the converted data.")
        print("Expected structure:")
        print("  kitti_root/")
        print("    ├── training/")
        print("    │   ├── image_2/")
        print("    │   ├── velodyne/")
        print("    │   ├── label_2/")
        print("    │   └── calib/")
        print("    └── testing/")
        print("        ├── image_2/")
        print("        ├── velodyne/")
        print("        └── calib/")
        print("Run dair_v2x_i_to_kitti.py first to convert the dataset.")
        return
    
    print(f"KITTI data root: {os.path.abspath(args.kitti_root)}")
    print(f"Dataset split: {args.split}")
    print(f"Max frames to detect: {args.max_frames}")
    print(f"Max points for visualization: {args.max_points}")
    print(f"Output directory: {args.output_dir}")
    print(f"Decode images: {args.decode_img}")
    
    # Create verifier
    verifier = KittiDairV2XVerifier(args.kitti_root, decode_img=args.decode_img)
    
    # Get available frames
    if args.single_frame:
        available_frames = [args.single_frame]
        print(f"Verifying single frame: {args.single_frame}")
    else:
        available_frames = get_available_frames(args.kitti_root, args.split, max_frames=args.max_frames)
        
        if not available_frames:
            print(f"No valid frames found in {args.split} set!")
            return
        
        print(f"Found {len(available_frames)} available frames in {args.split} set: {available_frames[:5]}...")
    
    # Verify single frame
    frame_id = available_frames[0]
    print(f"\n=== Single Frame Verification: {frame_id} ===")
    
    result_image = verifier.visualize_projection(
        frame_id, 
        split=args.split,
        max_points=args.max_points,
        save_path=f"dair_v2x_verification_{frame_id}.jpg",
        show_2d_bbox=(args.split == 'training' and args.show_2d_bbox)
    )
    
    if result_image is not None:
        print(f"Single frame verification completed for {frame_id}")
        
        # Create thumbnail for quick preview
        height, width = result_image.shape[:2]
        scale = 0.3  # Scale to 30% of original size
        thumbnail_width = int(width * scale)
        thumbnail_height = int(height * scale)
        thumbnail = cv2.resize(result_image, (thumbnail_width, thumbnail_height))
        cv2.imwrite(f"dair_v2x_verification_{frame_id}_thumbnail.jpg", thumbnail)
        print(f"Thumbnail saved as dair_v2x_verification_{frame_id}_thumbnail.jpg")
    
    # Batch verification
    if not args.no_batch and len(available_frames) > 1:
        print(f"\n=== Batch Verification (first {args.batch_frames} frames) ===")
        sample_frames = available_frames[:args.batch_frames]
        verifier.batch_verify(sample_frames, split=args.split, output_dir=args.output_dir)
        
        # Create summary image
        print(f"\n=== Creating Summary Image ===")
        create_summary_image(sample_frames, output_path="dair_v2x_verification_summary.jpg")
        
        # Generate verification report
        generate_verification_report(sample_frames, verifier, args.split)
    
    print("\n=== DAIR-V2X-I Verification completed! ===")
    print("Generated files:")
    print(f"- dair_v2x_verification_{frame_id}.jpg (single frame result)")
    print(f"- dair_v2x_verification_{frame_id}_thumbnail.jpg (thumbnail)")
    if not args.no_batch:
        print(f"- {args.output_dir}/ (batch results)")
        print(f"- dair_v2x_verification_summary.jpg (summary image)")
        print(f"- dair_v2x_verification_report.txt (detailed report)")
    print("\nVisualization elements:")
    print("- Point cloud projection with depth colors (blue=far, red=near)")
    print("- 3D boxes from KITTI labels (colored by object type)")
    if args.split == 'training' and args.show_2d_bbox:
        print("- 2D annotation boxes (red rectangles)")
        print("- Labels: '3D-ObjectType' for 3D projections, '2D-ObjectType' for 2D annotations")
    print("- Different object types shown in different colors")
    print("\nFor calibration verification, check:")
    print("- Point cloud alignment with road surfaces and object boundaries")
    print("- 3D box projection accuracy and alignment with objects")
    if args.split == 'training':
        print("- Consistency between 3D projections and 2D ground truth annotations")
    print("\nCoordinate system used:")
    print("- KITTI ego coordinate system: x=forward, y=left, z=up")
    print("- Same as DAIR-V2X-I virtual LiDAR coordinate system")

if __name__ == "__main__":
    main()
