# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

# -*- encoding: utf-8 -*-
'''
@Time:         2023/05/31
@Author:       weiguang.han@intel.com
@description:  The function of this script is to extract the needed data in the txt files
               saved by ros2 topics to form the trajectory files in tum format, visualize them and save the comparison of them as a picture.
'''

import matplotlib.pyplot as plt
import numpy as np

# store the x and y values to visualize the trajectory
X1, Y1, X2, Y2, X3, Y3 = [], [], [], [], [], []

# the top, down, left, right boundries of image
x_min = 10000.0
x_max = -10000.0
y_min = 10000.0
y_max = -10000.0

# max timestamp of bag file msg
timestamp_max = 0.0

# extract timestamp, tx, ty, tz, qx, qy, qz, qw from the raw data to form the trajectory in tum format
def convert_to_tum(i):

    global x_min
    global x_max
    global y_min
    global y_max
    global timestamp_max

    if i == 0:
        txt_path = "./tracker0.txt"
        save_tum_txt_path = "./tracker0_tum.txt"
        # tracker0.txt is consisted of multiple messages and each of the message occupies 54 lines.
        data_lines = 54
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        line_num = [2, 3, 8, 9, 10, 12, 13, 14, 15]

    if i == 1:
        txt_path = "./tracker2.txt"
        save_tum_txt_path = "./tracker2_tum.txt"
        # tracker2.txt is consisted of multiple messages and each of the message occupies 54 lines.
        data_lines = 54
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        line_num = [2, 3, 8, 9, 10, 12, 13, 14, 15]

    if i == 2:
        txt_path = "./kf_robot.txt"
        save_tum_txt_path = "./kf_robot_tum.txt"
        # kf_robot.txt is consisted of multiple messages and each of the message occupies 102 lines.
        data_lines = 102
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        line_num = [2, 3, 9, 10, 11, 13, 14, 15, 16]

    f = open(txt_path)
    content = f.readlines()
    j = 0

    with open(save_tum_txt_path, "w") as r:
        while j < len(content):
            div = j % data_lines
            if (div in line_num):
                if div == line_num[0]:
                    r.write(content[j][9:-1])
                    r.write(".")
                elif div == line_num[1]:
                    r.write(content[j][14:-1])
                    r.write(" ")
                elif div == line_num[-1]:
                    r.write(content[j][9:-1])
                    r.write('\n')
                else:
                    r.write(content[j][9:-1])
                    r.write(" ")
            j = j + 1
    f.close()

    with open(save_tum_txt_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            value = [float(s) for s in line.split()]
            # only calculate the max timestamp from two trackers since robot localization package will
            # continue to produce incorrect pose outputs when the bag playing is done
            if i != 2 and value[0] > timestamp_max:
                timestamp_max = value[0]
            if i == 0 or i == 1:
                if value[1] < x_min:
                    x_min = value[1]
                if value[1] > x_max:
                    x_max = value[1]
                if value[2] < y_min:
                    y_min = value[2]
                if value[2] > y_max:
                    y_max = value[2]
                if i == 0:
                    X1.append(value[1])
                    Y1.append(value[2])
                elif i == 1:
                    X2.append(value[1])
                    Y2.append(value[2])
            # filter out the wrong pose outputs from robot localization package after bag playing is done
            elif value[0] < timestamp_max:
                if value[1] < x_min:
                    x_min = value[1]
                if value[1] > x_max:
                    x_max = value[1]
                if value[2] < y_min:
                    y_min = value[2]
                if value[2] > y_max:
                    y_max = value[2]
                X3.append(value[1])
                Y3.append(value[2])


def main():
    i = 0

    while i < 3:
        convert_to_tum(i)
        i = i + 1

    # add extra space for better visualization effect
    x_range = x_max - x_min
    y_range = y_max - y_min
    plt.xlim((x_min - x_range/8, x_max + x_range/8))
    plt.ylim((y_min - y_range/8, y_max + y_range/8))

    plt.xlabel('x')
    plt.ylabel('y')

    plt.plot(X1, Y1, color='blue', label='tracker0')
    plt.plot(X2, Y2, color='grey', label='tracker2')
    plt.plot(X3, Y3, color='red', label='kf_robot')

    plt.legend()
    plt.savefig('./compare', bbox_inches='tight')
    plt.show()


if __name__ == "__main__":
    main()
