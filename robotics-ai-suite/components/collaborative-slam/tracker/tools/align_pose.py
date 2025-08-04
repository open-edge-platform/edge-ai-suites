# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import numpy as np
import zipfile
import sys
import shutil
import os

from numpy.matrixlib.defmatrix import matrix
import pyquaternion
import subprocess

def read_camera_poses(filename):
    with open(filename) as file:
        poses=[]
        times=[]
        for line in file:
            elems = line.rstrip().split(' ')
            times.append(elems[0])
            mat = []
            for p in elems:
                if p == '':
                    continue
                mat.append(float(p))

            #print(mat[1:4])
            #print(mat[4:])
            position = np.asarray(mat[1:4])
            rotation = np.asarray(mat[4:])

            M = np.eye(4)
            M[0, 0] = -1.
            M[1, 1] = 1.
            M[2, 2] = 1.

            qw = rotation[3]
            qx = rotation[0]
            qy = rotation[1]
            qz = rotation[2]

            quaternion = pyquaternion.Quaternion(qw, qx, qy, qz)
            rotation = quaternion.rotation_matrix

            extrinsics = np.eye(4)
            extrinsics[:3, :3] = rotation
            extrinsics[:3, 3] = position
            poses.append(extrinsics)

        return times, poses


def get_align_mat(file_path):
    result_zip = zipfile.ZipFile(file_path)
    result_zip.extractall("results_mid")
    align_mat = np.load("results_mid/alignment_transformation_sim3.npy")
    shutil.rmtree("results_mid")
    return align_mat


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usgae: python a.py gt_txt current_txt result.zip")
        sys.exit()

    align_mat = get_align_mat(sys.argv[3])

    times, poses = read_camera_poses(sys.argv[2])

    time_poses = []
    for idx in range(len(poses)):
        pose = np.dot(align_mat, poses[idx])

        # w x y z
        new_pose_quant = np.array(list(pyquaternion.Quaternion(matrix=pose[0:3, 0:3])))
        time_pose = []
        time_pose.append(times[idx])
        time_pose.append(str(pose[0,3]))
        time_pose.append(str(pose[1,3]))
        time_pose.append(str(pose[2,3]))
        time_pose.append(str(new_pose_quant[1]))
        time_pose.append(str(new_pose_quant[2]))
        time_pose.append(str(new_pose_quant[3]))
        time_pose.append(str(new_pose_quant[0]))
        time_poses.append(time_pose)

    with open("new_pose.txt", "w") as f:
        for line in time_poses:
            for id in range(len(line)):
                f.write(line[id])
                if id != 7:
                    f.write(" ")
            f.write("\n")
    subprocess.call(["evo_ape","tum", sys.argv[1], "new_pose.txt", "-p"])
    os.remove("new_pose.txt")