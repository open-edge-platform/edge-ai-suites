#!/bin/bash
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

# Intro: test all the benchmark scripts on all datasets and then retest for a given number times on filtered results.
# Usage: bash benchmark/auto_test_filter.sh arg1 arg2
# (1) If "arg1" is 'yes' or 'y', it will run all the benchmark scripts on all datasets from scratch and output the results in the result sheet of result.xlsx.
#     Then run the filter.py to filter the invalid results and calculate the mean values. The output is stored in the mean sheet and filtered sheet in result.xlsx.
#     Otherwise, the process will not go through these scripts and will directly go to the next part.
# (2) The second argument "arg2" is a integer number, it will loop such times as following:
#     It will run all the benchmark scripts on the datasets which are stored in the filtered sheet of result.xlsx.
#     Then run the filter.py to update the mean sheet and filter the datasets which may need to be tested again.
# VIP: remember to change the paths for bag, ground truth and trajectory result saving before running the script

if [ $1  = "yes" ] || [ $1  = "y" ]
then
    echo "from now on, all dataset will be tested from scratch"
    ./benchmark/rgbd_benchmark.py tum -b ./dataset/TUM_rgbd -f ./benchmark/results -g ./benchmark/groundtruth/TUM -r 3 --evaluate_rpe --save_to_excel --from_scratch
    ./benchmark/mono_benchmark.py tum -b ./dataset/TUM_mono -f ./benchmark/results -g ./benchmark/groundtruth/TUM -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/mono_benchmark.py euroc -b ./dataset/EuRoC_mono -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/mono_benchmark.py kitti -b /workspace/bagfiles/applications/robotics/mobile/collaborative-slam/kitti -f ./benchmark/results -g ./benchmark/groundtruth/KITTI -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/mono_imu_benchmark.py euroc -b ./dataset/EuRoC_mono -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/stereo_benchmark.py euroc -b ./dataset/EuRoC_stereo -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/stereo_benchmark.py kitti -b /workspace/bagfiles/applications/robotics/mobile/collaborative-slam/kitti -f ./benchmark/results -g ./benchmark/groundtruth/KITTI -r 3 --evaluate_rpe --save_to_excel
    ./benchmark/stereo_imu_benchmark.py euroc -b ./dataset/EuRoC_stereo -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel
    python3 ./benchmark/filter.py -t 0.6 -m 0.15 -k 1
fi

if [[ $2 =~ ^[0-9]+$ ]]
then
    echo "from now on, the result will be filterd for $2 times"
    for ((i = 1; i <= $2; i++))
    do
        ./benchmark/rgbd_benchmark.py tum -b ./dataset/TUM_rgbd -f ./benchmark/results -g ./benchmark/groundtruth/TUM -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/mono_benchmark.py tum -b ./dataset/TUM_mono -f ./benchmark/results -g ./benchmark/groundtruth/TUM -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/mono_benchmark.py euroc -b ./dataset/EuRoC_mono -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/mono_benchmark.py kitti -b /workspace/bagfiles/applications/robotics/mobile/collaborative-slam/kitti -f ./benchmark/results -g ./benchmark/groundtruth/KITTI -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/mono_imu_benchmark.py euroc -b ./dataset/EuRoC_mono -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/stereo_benchmark.py euroc -b ./dataset/EuRoC_stereo -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/stereo_benchmark.py kitti -b /workspace/bagfiles/applications/robotics/mobile/collaborative-slam/kitti -f ./benchmark/results -g ./benchmark/groundtruth/KITTI -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        ./benchmark/stereo_imu_benchmark.py euroc -b ./dataset/EuRoC_stereo -f ./benchmark/results -g ./benchmark/groundtruth/EuRoC -r 3 --evaluate_rpe --save_to_excel --retest_failures_once
        python3 ./benchmark/filter.py -t 0.6 -m 0.15 -k 1
    done
else
    echo "$2 is not a integer number, process exit"
fi
