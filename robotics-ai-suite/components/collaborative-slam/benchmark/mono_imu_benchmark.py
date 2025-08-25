#!/usr/bin/env python3
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

'''
Author: han.yin@intel.com, yujie.wang@intel.com
'''

import os
import sys
import argparse
import statistics as sta
import pandas as pd

from launch import LaunchDescription, LaunchService, logging
from launch.actions import ExecuteProcess, TimerAction, EmitEvent, RegisterEventHandler
from launch.events import Shutdown
from launch.event_handlers import OnProcessIO

correct_loop_sequences = ["V1_01_easy", "V1_02_medium", "V2_01_easy", "V2_02_medium"]
clean_keyframe_sequences = ["MH_03_medium", "MH_04_difficult", "MH_05_difficult", "V1_03_difficult", "V2_03_difficult"]

class MonocularInertialBenchmark:
    __evo_ape_cmd = ["evo_ape", "tum", "-vas"]
    __evo_rpe_cmd = ["evo_rpe", "tum", "-vas"]
    def __init__(self, name, bagfile, groundtruth, ros1_path, dataset, wait_time, resultfile_dir):
        self.name = name
        self.bagfile = bagfile
        self.referfile = groundtruth
        self.ape_rmse_list = []
        self.rpe_rmse_list = []
        self.scale_correction_list = []
        self.ros1_path = ros1_path
        self.dataset = dataset
        self.wait_time = wait_time
        self.resultfile_dir = resultfile_dir
        self.resultfile = "client0map0.txt"
        self.traj_coverage = 0
        self.gt_coverage = 0

    def __generate_ros1_env(self):
        subprocess_env = os.environ.copy()
        subprocess_env.update({"ROS_PACKAGE_PATH": os.path.join(self.ros1_path, "share")})
        subprocess_env.update({"ROS_ETC_DIR": os.path.join(self.ros1_path, "etc/ros")})
        subprocess_env.update({"ROS_MASTER_URI": "http://localhost:11311"})
        subprocess_env.update({"ROS_LOCALHOST_ONLY": "0"})
        subprocess_env.update({"ROS_ROOT": os.path.join(self.ros1_path, "share/ros")})
        ld_path = subprocess_env["LD_LIBRARY_PATH"] + ":" + os.path.join(self.ros1_path, "lib")
        subprocess_env.update({"LD_LIBRARY_PATH": ld_path})

        return subprocess_env

    def __on_evo_process_output(self, event):

        for line in event.text.decode().splitlines():
            if line.lstrip().lower().startswith(("compared")):
                print("POSE: {}; ".format(line.lstrip().split()[1]), end="")
            elif line.lstrip().lower().startswith(("min")):
                print("MIN: {}; ".format(line.lstrip().split()[1]), end="")
            elif line.lstrip().lower().startswith(("max")):
                print("MAX: {}; ".format(line.lstrip().split()[1]), end="")
            elif line.lstrip().lower().startswith(("median")):
                print("MEDIAN: {}; ".format(line.lstrip().split()[1]), end="")
            elif line.lstrip().lower().startswith(("scale correction")):
                self.scale_correction_list.append(float(line.lstrip().split(": ")[1]))
                print("SCALE: {}".format(self.scale_correction_list[-1]))
            elif line.lstrip().lower().startswith(("rmse")):
                if self.evaluate_ape:
                    self.ape_rmse_list.append(float(line.lstrip().split()[1]))
                    print("APE RMSE: {}".format(self.ape_rmse_list[-1]))
                else:
                    self.rpe_rmse_list.append(float(line.lstrip().split()[1]))
                    print("RPE RMSE: {}".format(self.rpe_rmse_list[-1]))

    def __generate_output_data(self):
        xlsxdata = {
            'dataset': ['mono_imu'],
            'dataname': [self.name],
            #'repeat_num': [test_loop+1],
            'ape': [self.ape_rmse_list[-1]],
            'rpe': [self.rpe_rmse_list[-1]],
            'traj_conv': [self.traj_coverage],
            'gt_conv': [self.gt_coverage],
            'scale': [self.scale_correction_list[-1] if self.evaluate_ape else self.scale_correction_list[-2]],
            # 'scale': [self.scale_correction_list[-1]]
            'isvalid': ['None']
        }
        return xlsxdata
    
    def result_isavailable(self):
        # Check if trajectory file is generated
        trajectory_file_list = []
        for filename in os.listdir(self.resultfile_dir):
            if filename.startswith("client0map") and filename.endswith("txt"):
                trajectory_file_list.append(filename)

        if len(trajectory_file_list) == 0:
            print("No new trajectory file generated", file=sys.stderr)
            return -1

        max_size = 0
        for filename in trajectory_file_list:
            candidate_file = os.path.join(self.resultfile_dir, filename)
            file_size = os.stat(candidate_file).st_size
            if file_size > max_size:
                max_size = file_size
                self.resultfile = candidate_file

        result_timestamp_list = list()
        refer_timestamp_list = list()
        with open(os.path.join(self.resultfile_dir, self.resultfile)) as resultfile:
            for line in resultfile.readlines():
                timestamp = float(line.split()[0])
                result_timestamp_list.append(timestamp)

        with open(self.referfile) as referfile:
            for line in referfile.readlines():
                first_word = line.split()[0]
                if first_word[0] != "#":
                    refer_timestamp_list.append(float(first_word))

        # The time period of generating keyframe must be longer than the 90% of the total time period
        # The time of generating the last keyframe must be within 1 seconds till the end of the total time period
        result_start_timestamp = result_timestamp_list[0]
        result_end_timestamp = result_timestamp_list[-1]
        refer_start_timestamp = refer_timestamp_list[0]
        refer_end_timestamp = refer_timestamp_list[-1]

        result_duration = result_end_timestamp - result_start_timestamp
        refer_duration = refer_end_timestamp - refer_start_timestamp
        #if (result_duration/refer_duration) > 0.9 and (refer_end_timestamp - result_end_timestamp) < 1:
        self.traj_coverage = "{:.2f}".format(result_duration)
        self.gt_coverage = "{:.2f}".format(refer_duration)
        print("trajectory coverage: {:.2f}s; groundtruth coverage:{:.2f}s".format(result_duration, refer_duration))
        # Check is skipped for now
        #if (result_duration/refer_duration) > 0.5:
        #    return 0
        #else:
        #    print("Produced trajectory duration did not cover at least 50% of reference trajectory!")
        #    return -2
        return 0

    def evaluate_result(self, is_ape=True):
        self.evaluate_ape = is_ape

        ld_evaluate = LaunchDescription()
        ls_evaluate = LaunchService()

        # Avoid unnecessary log info output
        logging.launch_config.level = logging.logging.WARN

        if is_ape:
            evaluate_cmd = self.__evo_ape_cmd + [self.referfile, os.path.join(self.resultfile_dir, self.resultfile)]
        else:
            evaluate_cmd = self.__evo_rpe_cmd + [self.referfile, os.path.join(self.resultfile_dir, self.resultfile)]

        evo_process = ExecuteProcess(
            cmd = evaluate_cmd,
            shell = True
        )

        process_output_handler = OnProcessIO(target_action = evo_process, on_stdout = self.__on_evo_process_output)

        ld_evaluate.add_action(evo_process)
        ld_evaluate.add_action(RegisterEventHandler(process_output_handler))
        ls_evaluate.include_launch_description(ld_evaluate)

        ret = ls_evaluate.run()

        return 0

    def average_evaluation(self, is_ape=True):
        if is_ape:
            if len(self.ape_rmse_list) == 0:
                return "Failed"
            else:
                average_rmse = (sum([item ** 2 for item in self.ape_rmse_list])/len(self.ape_rmse_list)) ** 0.5
        else:
            if len(self.rpe_rmse_list) == 0:
                return "Failed"
            else:
                average_rmse = (sum([item ** 2 for item in self.rpe_rmse_list])/len(self.rpe_rmse_list)) ** 0.5
        return "{0:.6f}".format(average_rmse)

    def average_scale_correction(self):
        return sum([abs(float(item)-1.0)*100.0 for item in self.scale_correction_list])/len(self.scale_correction_list)

    def average_ape_scale_correction(self):
        return sum([abs(float(item)-1.0)*100.0 for idx, item in enumerate(self.scale_correction_list) if idx%2==0])/(len(self.scale_correction_list)/2)
    
    def store_trajectory_file(self):
        dst_file_index = len(self.ape_rmse_list)
        src_file = os.path.join(self.resultfile_dir, self.resultfile)
        dst_file = os.path.join(self.resultfile_dir, ("result_" + self.name + "_" + str(dst_file_index) + ".txt"))
        os.replace(src_file, dst_file)

    def run_single_test(self):
        # Generate server node execute process command
        launch_file_cmd = ["ros2", "launch", "univloc_server", "server.launch.py"]
        launch_params = ["fix_scale:=true", "rviz:=false"]
        launch_params.append("save_traj_folder:=" + self.resultfile_dir)
        if self.dataset == "euroc":
            if self.name in correct_loop_sequences:
                launch_params.append("correct_loop:=true")
                print("{} will set correct_loop as true...".format(self.name))
            else:
                launch_params.append("correct_loop:=false")
                print("{} will set correct_loop as false...".format(self.name))

        server_cmd = launch_file_cmd + launch_params

        # Generate basic tracker node execute process command
        if self.dataset == "euroc":
            launch_file_cmd = ["ros2", "launch", "univloc_tracker", "euroc_mono.launch.py"]
        launch_params = ["camera_setup:=Monocular_Inertial", "gui:=false", "rviz:=false", "publish_tf:=false",
                        "log_level:=warning"]
        if self.dataset == "euroc":
            if self.name in clean_keyframe_sequences:
                launch_params.append("clean_keyframe:=true")
                print("{} will set clean_keyframe as true...".format(self.name))
            else:
                launch_params.append("clean_keyframe:=false")
                print("{} will set clean_keyframe as false...".format(self.name))
        tracker_cmd = launch_file_cmd + launch_params

        # Generate environment list of playback execute process
        playback_env = self.__generate_ros1_env()

        # Clean previously generated result file
        for filename in os.listdir(self.resultfile_dir):
            if filename.startswith("client0map") and filename.endswith("txt"):
                os.remove(os.path.join(self.resultfile_dir, filename))

        print("Waiting for bag file to finish...")

        ld_test = LaunchDescription()
        ls_test = LaunchService()

        # Avoid unnecessary log info output
        logging.launch_config.level = logging.logging.WARN

        # Generate playback execute process
        playback_cmd = ["ros2", "bag", "play", "-s", "rosbag_v2", self.bagfile]
        wait_to_shutdown = TimerAction(period=self.wait_time, actions=[EmitEvent(event=Shutdown())])
        playback_process = ExecuteProcess(
            cmd = playback_cmd,
            shell = True,
            output = 'own_log',
            env = playback_env,
            on_exit = wait_to_shutdown
        )
        # camera info is no longer a separate rosbag, thus no need for waiting too long
        wait_to_play = TimerAction(period=2.0, actions=[playback_process])

        # Generate tracker node execute process

        tracker_process = ExecuteProcess(
            cmd = tracker_cmd,
            shell = False,
            output = 'own_log',
            additional_env = {'SPDLOG_LEVEL': 'warning'}
        )

        # Generate server node execute process
        server_process = ExecuteProcess(
            cmd = server_cmd,
            output = 'own_log',
            additional_env = {'SPDLOG_LEVEL': 'warning'},
            shell = False
        )

        # Group and launch tracker node, server node and playback execute process to launch service
        ld_test.add_action(tracker_process)
        ld_test.add_action(server_process)
        ld_test.add_action(wait_to_play)
        ls_test.include_launch_description(ld_test)

        ret = ls_test.run()
        # print("ls_test LaunchService return code: {}".format(ret))

        print("Done playing bag file! Waiting for {}secs to start the next process...".format(self.wait_time))

        return 0
    
    def write_to_xlsx(self, file, sheet):
        # create new xlsx file if the file not exists
        if not os.path.exists(file):
            result_header={
                'dataset': [],
                'dataname': [],
                'ape': [],
                'rpe': [],
                'traj_conv': [],
                'gt_conv': [],
                'scale': [],
                'isvalid': []
            }
            writer = pd.ExcelWriter(file, engine='xlsxwriter')
            df_header = pd.DataFrame(result_header)
            df_header.to_excel(writer, sheet_name="result", index=False)
            writer.save()
        
        data = self.__generate_output_data()
        # find startrow for writing new data
        df = pd.read_excel(file, sheet_name=sheet)
        num_rows = len(df)
        #print(f'The length of {sheet} in example.xlsx is {num_rows} rows.')
        df_new = pd.DataFrame(data)
        writer = pd.ExcelWriter(file, engine='openpyxl', mode='a', if_sheet_exists='overlay')
        # Write the new data to the existing sheet
        df_new.to_excel(writer, sheet_name=sheet, index=False, header=False, startrow=num_rows+1)
        # Save the writer
        writer.save()

def args_parse(default_bagfile_dir):
    parser = argparse.ArgumentParser(description="Automatically run EuRoC dataset with monocular and imu input and print the accuracy data to standard output")
    parser.add_argument("dataset", type=str, help="The dataset to be tested, only support option: euroc",
                        choices=["euroc"])
    parser.add_argument("-b", "--bagfile_dir", type=str, dest="bagfile_dir",
                        help="The directory which stores the .bag file", default=default_bagfile_dir)
    parser.add_argument("-f", "--resultfile_dir", type=str, dest="resultfile_dir",
                        help="The directory of the result file which stores the trajectory data", default="./")
    parser.add_argument("-r", "--repeat", type=int, dest="repeat_num",
                        help="The number to repeat for each test", default=1)
    parser.add_argument("-g", "--groudtruth", type=str, dest="groundtruth_dir",
                        help="The directory of the groudtruth files", default="")
    parser.add_argument("--rmse", type=float, dest="rmse_threshold",
                        help="The threshold of evaluated RMSE to pass a single test", default=-1.0)
    parser.add_argument("-s", "--scale", type=float, dest="scale_threshold",
                        help="The threshold of scale correction percentage to pass a single test", default=5.0)
    parser.add_argument("-w", "--wait", type=float, dest="wait",
                        help="The delay to exit nodes after playback of .bag file", default=5.0)
    parser.add_argument("-p", "--ros1_path", type=str, dest="ros1_path",
                        help="The installation path of the ROS1", default="/opt/ros/noetic")
    parser.add_argument("--store", action="store_true",
                        help="Store tracjectory files for each test loop.")
    parser.add_argument("--evaluate_rpe", action="store_true",
                        help="Evalute rpe for trajectory output.")
    parser.add_argument("--save_to_excel", action="store_true",
                        help="Save accuracy data of each test loop to result.xlsx.")
    parser.add_argument("--from_scratch", action="store_true", 
                        help="from_scratch will remove the old reult.xlsx and test all the benchmark from scratch, otherwise the result will be added to the current result.xlsx")
    parser.add_argument("--retest_failures_once", action="store_true",
                        help="only test the dataset in the filtered sheet of result.xlsx, this should be used together with --save_to_excel")
    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)
    if not os.path.isdir(bagfile_dir):
        sys.exit('-b: "{}" is not a directory'.format(bagfile_dir))

    resultfile_dir = os.path.realpath(args.resultfile_dir)
    if not os.path.isdir(resultfile_dir):
        print("Create {} as the directory to store the result file".format(resultfile_dir))
        os.makedirs(resultfile_dir)

    if os.path.isdir(args.groundtruth_dir):
        groundtruth_dir = os.path.realpath(args.groundtruth_dir)
    else:
        print("Since the directory of groundtruth is not a directory, will use the directory of .bag files instead")
        groundtruth_dir = os.path.realpath(args.bagfile_dir)

    ros1_install_path = os.path.realpath(args.ros1_path)
    if not os.path.isdir(ros1_install_path):
        sys.exit('-p: "{}" is not a directory'.format(ros1_install_path))

    if args.retest_failures_once:
        if not args.save_to_excel:
            sys.exit('--retest_failures_once should be used together with --save_to_excel')

    args_dict = dict()
    args_dict.update({"DATASET": args.dataset})
    args_dict.update({"BAG": bagfile_dir})
    args_dict.update({"RETEST_FAILURES_ONCE": args.retest_failures_once})
    args_dict.update({"RESULT": resultfile_dir})
    args_dict.update({"REPEAT": int(args.repeat_num)})
    args_dict.update({"GROUNDTRUTH": groundtruth_dir})
    args_dict.update({"RMSE": args.rmse_threshold})
    args_dict.update({"WAIT": args.wait})
    args_dict.update({"ROS1PATH": ros1_install_path})
    args_dict.update({"STORE": args.store})
    args_dict.update({"SAVE_TO_EXCEL": args.save_to_excel})
    args_dict.update({"FROM_SCRATCH": args.from_scratch})
    args_dict.update({"RPE": args.evaluate_rpe})
    args_dict.update({"SCALE": args.scale_threshold})

    return args_dict


def generate_bagfile_list(bagfile_dir):
    bagfile_list = list()
    bagfile_prefix_list = list()
    bagfile_dir_list = os.listdir(bagfile_dir)
    for name in bagfile_dir_list:
        if not os.path.isfile(os.path.join(bagfile_dir, name)):
            continue

        name_suffix_list = name.split(".")
        if len(name_suffix_list) == 2 and name_suffix_list[1] == "bag":
            if name_suffix_list[0] not in bagfile_prefix_list:
                bagfile_list.append(name)
                bagfile_prefix_list.append(name_suffix_list[0])
        elif len(name_suffix_list) == 3 and name_suffix_list[1] == "orig" and name_suffix_list[2] == "bag":
            if name_suffix_list[0] not in bagfile_prefix_list:
                bagfile_list.append(name)
                bagfile_prefix_list.append(name_suffix_list[0])
            else:
                obj_index = bagfile_prefix_list.index(name_suffix_list[0])
                bagfile_list[obj_index] = name
        else:
            continue

    return bagfile_list, bagfile_prefix_list

def filter_bagfile_list(bagfile_list, bagfile_prefix_list, listfile):
    if not os.path.exists(listfile):
        sys.exit('"{}" not found, run benchmark with --save_to_excel to get a result.xlsx file before filter results'.format(listfile))
    pd_prex = pd.read_excel(listfile, sheet_name='filtered', header=None)
    filtered_list = pd_prex.values.tolist()

    filtered_bag_list = []
    filtered_bagfile_prefix_list = []
    for bag, prex in zip(bagfile_list, bagfile_prefix_list):
        if ['mono_imu', prex] in filtered_list:
            filtered_bag_list.append(bag)
            filtered_bagfile_prefix_list.append(prex)

    return filtered_bag_list, filtered_bagfile_prefix_list

# Groundtruth name format: 1. EuRoC name-groundtruth.tum
def generate_groundtruth_list(groundtruth_dir, bagfile_prefix_list):
    groundtruth_list = list()
    bagfile_index_list = list()
    groundtruth_dir_list = os.listdir(groundtruth_dir)
    for name in groundtruth_dir_list:
        if not os.path.isfile(os.path.join(groundtruth_dir, name)):
            continue

        name_suffix_list = name.split(".")
        if len(name_suffix_list) == 2 and name_suffix_list[1] == "tum":
            groundtruth_name = name_suffix_list[0].split("-")[0]
            groundtruth_suffix = name_suffix_list[0].split("-")[1]
            if (groundtruth_name in bagfile_prefix_list) and (groundtruth_suffix == "groundtruth"):
                groundtruth_list.append(name)

    return groundtruth_list


def generate_test_list(bagfile_list, bagfile_prefix_list, groundtruth_list, args_dict):
    benchmark_list = list()
    for name in groundtruth_list:
        groundtruth_name = name.split("-")[0]
        bagfile_index = bagfile_prefix_list.index(groundtruth_name)
        bagfile = os.path.join(args_dict["BAG"], bagfile_list[bagfile_index])
        groundtruth = os.path.join(args_dict["GROUNDTRUTH"], name)
        item = MonocularInertialBenchmark(bagfile_prefix_list[bagfile_index], bagfile, groundtruth, args_dict["ROS1PATH"], args_dict["DATASET"], args_dict["WAIT"], args_dict["RESULT"])
        benchmark_list.append(item)

    return benchmark_list


def main():
    ret = 0
    # Use environment variable as default value of .bag file directory
    if "BAGFILE_DIR" in os.environ:
        default_bagfile_dir = os.getenv("BAGFILE_DIR")
    else:
        default_bagfile_dir = os.getenv("HOME")
    args_dict = args_parse(default_bagfile_dir)

    bagfile_list, bagfile_prefix_list = generate_bagfile_list(args_dict["BAG"])
    if args_dict["RETEST_FAILURES_ONCE"]:
        bagfile_list, bagfile_prefix_list = filter_bagfile_list(bagfile_list, bagfile_prefix_list, args_dict["RESULT"]+'/result.xlsx')
    if args_dict["DATASET"] == "euroc":
        groundtruth_list = generate_groundtruth_list(args_dict["GROUNDTRUTH"], bagfile_prefix_list)
    benchmark_list = generate_test_list(bagfile_list, bagfile_prefix_list, groundtruth_list, args_dict)

    if args_dict["SAVE_TO_EXCEL"]:
        if args_dict["FROM_SCRATCH"]:
            excel_name = args_dict["RESULT"]+"/result.xlsx"
            if os.path.exists(excel_name):
                print('Warning: The old result file "{}" will be removed'.format(excel_name))
                os.remove(excel_name)

    separator = "-" * 100
    print(separator)
    print("We will run below test and {} times for each test".format(args_dict["REPEAT"]))
    print(separator)
    for item in benchmark_list:
        print('Test Name: {}\nBagfile: {}\nGroundtruth: {}\n'.format(item.name, item.bagfile, item.referfile))

    benchmark_ape_rmse_dict = dict()
    benchmark_rpe_rmse_dict = dict()
    benchmark_scale_correction_dict = dict()
    for item in benchmark_list:
        print(separator)
        print("Start running test {}".format(item.name))
        for test_loop in range(args_dict["REPEAT"]):
            print("Loop {}".format(test_loop+1))
            status = item.run_single_test()
            if status != 0:
                ret = -1
                print('Test "{}" failed due to timeout or some other reason, jump to next case'.format(item.name), file=sys.stderr)
                break

            status = item.result_isavailable()
            if status != 0:
                ret = -1
                print('The result of test "{}" is unavailable'.format(item.name), file=sys.stderr)
                continue

            status = item.evaluate_result()
            if status != 0:
                ret = -1
                print('The result evaluation of ape test "{}" is failed'.format(item.name), file=sys.stderr)
                continue

            if args_dict["RPE"]:
                status = item.evaluate_result(False)
                if status != 0:
                    ret = -1
                    print('The result evaluation of rpe test "{}" is failed'.format(item.name), file=sys.stderr)
                    continue

            if args_dict["SAVE_TO_EXCEL"]:
                item.write_to_xlsx(args_dict["RESULT"]+"/result.xlsx", "result")
                
            if args_dict["STORE"]:
                item.store_trajectory_file()

        print("Finish running test {}\n".format(item.name))
        test_average_ape_rmse = item.average_evaluation()
        benchmark_ape_rmse_dict.update({item.name: test_average_ape_rmse})

        if args_dict["RPE"]:
            test_average_rpe_rmse = item.average_evaluation(False)
            benchmark_rpe_rmse_dict.update({item.name: test_average_rpe_rmse})

        test_average_scale_correction = item.average_scale_correction()
        benchmark_scale_correction_dict.update({item.name: test_average_scale_correction})
        print(item.scale_correction_list)
        print(test_average_scale_correction)

    print("{0}\nThe ape evaluaton for each test is listed below\n{0}".format(separator))
    for item in benchmark_ape_rmse_dict:
        print('Test Name: {}\nRMSE: {}\n\n'.format(item, benchmark_ape_rmse_dict[item]))
        # only if the --rmse if specified as a positive value in argument, it will judge whether the RMSE is larger than that value.
        # otherwise, by default --rmse which is -1.0, process will not execute this comparision
        if benchmark_ape_rmse_dict[item] != "Failed" and args_dict["RMSE"] > 0:
            if float(benchmark_ape_rmse_dict[item]) > args_dict["RMSE"]:
                ret = -1
                print("RMSE bigger than allowed {}\n".format(args_dict["RMSE"]))

    if args_dict["RPE"]:
        print("{0}\nThe rpe evaluaton for each test is listed below\n{0}".format(separator))
        for item in benchmark_rpe_rmse_dict:
            print('Test Name: {}\nRMSE: {}\n\n'.format(item, benchmark_rpe_rmse_dict[item]))

    print("{0}\nThe scale evaluaton for each test is listed below\n{0}".format(separator))
    for item in benchmark_scale_correction_dict:
        print('Test Name: {}\nScale correction percentage: {}\n\n'.format(item, benchmark_scale_correction_dict[item]))
        if float(benchmark_scale_correction_dict[item]) > args_dict["SCALE"]:
            ret = -1
            print("Scale correction percentage error bigger than allowed {}\n".format(args_dict["SCALE"]))

    return ret

if __name__ == "__main__":
    sys.exit(main())
