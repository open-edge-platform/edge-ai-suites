# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# -*- encoding: utf-8 -*-
"""
@Time:         2023/05/31
@Author:       weiguang.han@intel.com
@description:  The function of this script is to extract the needed data in the txt files
               saved by ros2 topics to form the trajectory files in tum format,
               visualize them and save the comparison of them as a picture.
"""

import matplotlib.pyplot as plt

# store the x and y values to visualize the trajectory
X1, Y1, X2, Y2, X3, Y3 = [], [], [], [], [], []

# the top, down, left, right boundaries of image
X_MIN = 10000.0
X_MAX = -10000.0
Y_MIN = 10000.0
Y_MAX = -10000.0

# max timestamp of bag file msg
TIMESTAMP_MAX = 0.0


def safe_float_convert(s):
    """Safely convert string to float, handling .nan values"""
    if s == '.nan' or s.lower() == 'nan':
        return float('nan')
    try:
        return float(s)
    except ValueError:
        print(f"Warning: Could not convert '{s}' to float, using NaN")
        return float('nan')


# extract timestamp, tx, ty, tz, qx, qy, qz, qw
# from the raw data to form the trajectory in tum format
def get_file_config(i):
    """Get file configuration for tracker type i"""
    if i == 0:
        # tracker0.txt is consisted of multiple messages
        # and each of the message occupies 54 lines.
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        return {
            'txt_path': './tracker0.txt',
            'save_tum_txt_path': './tracker0_tum.txt',
            'data_lines': 54,
            'line_num': [2, 3, 8, 9, 10, 12, 13, 14, 15]
        }
    if i == 1:
        # tracker2.txt is consisted of multiple messages
        # and each of the message occupies 54 lines.
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        return {
            'txt_path': './tracker2.txt',
            'save_tum_txt_path': './tracker2_tum.txt',
            'data_lines': 54,
            'line_num': [2, 3, 8, 9, 10, 12, 13, 14, 15]
        }
    if i == 2:
        # kf_robot.txt is consisted of multiple messages
        # and each of the message occupies 102 lines.
        # The lines where the timestamp, tx, ty, tz, qx, qy, qz, qw are located in each msg.
        return {
            'txt_path': './kf_robot.txt',
            'save_tum_txt_path': './kf_robot_tum.txt',
            'data_lines': 102,
            'line_num': [2, 3, 9, 10, 11, 13, 14, 15, 16]
        }
    return {}


def process_file_to_tum(config):
    """Process raw file and convert to TUM format"""
    txt_path = config['txt_path']
    save_tum_txt_path = config['save_tum_txt_path']
    data_lines = config['data_lines']
    line_num = config['line_num']

    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.readlines()

    j = 0
    with open(save_tum_txt_path, 'w', encoding='utf-8') as r:
        while j < len(content):
            div = j % data_lines
            if div in line_num:
                if div == line_num[0]:
                    r.write(content[j][9:-1])
                    r.write('.')
                elif div == line_num[1]:
                    r.write(content[j][14:-1])
                    r.write(' ')
                elif div == line_num[-1]:
                    r.write(content[j][9:-1])
                    r.write('\n')
                else:
                    r.write(content[j][9:-1])
                    r.write(' ')
            j = j + 1


def update_global_bounds(x_val, y_val):
    """Update global X and Y boundaries"""
    # pylint: disable=global-statement
    global X_MIN, X_MAX, Y_MIN, Y_MAX

    X_MIN = min(X_MIN, x_val)
    X_MAX = max(X_MAX, x_val)
    Y_MIN = min(Y_MIN, y_val)
    Y_MAX = max(Y_MAX, y_val)


def update_timestamp_max(timestamp, tracker_id):
    """Update maximum timestamp from trackers (excluding robot localization)"""
    # pylint: disable=global-statement
    global TIMESTAMP_MAX

    # only calculate the max timestamp from two trackers since robot localization package
    # will continue to produce incorrect pose outputs when the bag playing is done
    if tracker_id != 2 and timestamp > TIMESTAMP_MAX:
        TIMESTAMP_MAX = timestamp


def add_trajectory_point(x_val, y_val, tracker_id):
    """Add point to appropriate trajectory list"""
    if tracker_id == 0:
        X1.append(x_val)
        Y1.append(y_val)
    elif tracker_id == 1:
        X2.append(x_val)
        Y2.append(y_val)
    elif tracker_id == 2:
        X3.append(x_val)
        Y3.append(y_val)


def update_bounds_and_trajectory(value, i):
    """Update global bounds and trajectory data"""
    timestamp, x_val, y_val = value[0], value[1], value[2]

    update_timestamp_max(timestamp, i)

    # Handle trackers 0 and 1
    if i in (0, 1):
        update_global_bounds(x_val, y_val)
        add_trajectory_point(x_val, y_val, i)
    # Handle robot localization (tracker 2) - filter out wrong pose outputs
    elif timestamp < TIMESTAMP_MAX:
        update_global_bounds(x_val, y_val)
        add_trajectory_point(x_val, y_val, i)


# extract timestamp, tx, ty, tz, qx, qy, qz, qw
# from the raw data to form the trajectory in tum format
def convert_to_tum(i):
    """Convert raw trajectory data to TUM format"""
    config = get_file_config(i)
    if not config:
        return

    process_file_to_tum(config)

    with open(config['save_tum_txt_path'], 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            value = [safe_float_convert(s) for s in line.split()]
            if len(value) >= 3:  # Ensure we have x, y coordinates
                update_bounds_and_trajectory(value, i)


def main():
    """Main function to process trajectories and create visualization"""
    i = 0

    while i < 3:
        convert_to_tum(i)
        i = i + 1

    # add extra space for better visualization effect
    x_range = X_MAX - X_MIN
    y_range = Y_MAX - Y_MIN
    plt.xlim((X_MIN - x_range / 8, X_MAX + x_range / 8))
    plt.ylim((Y_MIN - y_range / 8, Y_MAX + y_range / 8))

    plt.xlabel('x')
    plt.ylabel('y')

    plt.plot(X1, Y1, color='blue', label='tracker0')
    plt.plot(X2, Y2, color='grey', label='tracker2')
    plt.plot(X3, Y3, color='red', label='kf_robot')

    plt.legend()
    plt.savefig('./compare', bbox_inches='tight')
    plt.show()


if __name__ == '__main__':
    main()
