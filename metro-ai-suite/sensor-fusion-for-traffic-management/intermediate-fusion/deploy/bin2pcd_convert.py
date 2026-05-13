import numpy as np
import os

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



if __name__ == "__main__":

    # bin_dir ="/mnt/project/garnet_park/metro-2.0/PointPillar/LidarObjectDetection-PointPillars/data/nv-data"
    # pcd_dir ="/mnt/project/garnet_park/metro-2.0/PointPillar/LidarObjectDetection-PointPillars/data/nv-data-pcd"
    # if not os.path.exists(pcd_dir):
    #     os.makedirs(pcd_dir)
    # for file in os.listdir(bin_dir):
    #     if file.endswith(".bin"):
    #         bin_file = os.path.join(bin_dir, file)
    #         pcd_file = os.path.join(pcd_dir, file.replace(".bin", ".pcd"))
    #         bin_to_pcd(bin_file, pcd_file)
    #         print(f"Convert {bin_file} to {pcd_file} successfully!")

    bin_file ="data/v2xfusion/dataset/velodyne/000000.bin"
    pcd_file ="data/v2xfusion/dataset/velodyne/000000.pcd"
    bin_to_pcd(bin_file, pcd_file)