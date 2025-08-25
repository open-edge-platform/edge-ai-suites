#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
'''
Author: ao.du@intel.com
Time: 5/18/2023
Usage: Filter invaild test results from result.xlsx which is the output of benchmark when setting arg: "--save_to_excel".
       This scirpt will output mean value in mean sheet and list the data that need to be tested again in filtered sheet.
       Then go back to run benchmark scirpt with arg: "--dataset_sublist" to test the data in filtered sheet again.
'''

import pandas as pd
import argparse
import sys
import os

def average_scale_correction(scale_correction_list):
    scale_correction_list = list(filter(lambda n: n not in ['None', 'none', 0, None], scale_correction_list))
    if(len(scale_correction_list)==0):
        return None
    res = sum([abs(float(item)-1.0)*100.0 for item in scale_correction_list])/len(scale_correction_list)
    return round(res,6)

def mean(x):
    x = list(filter(lambda n: n not in ['None', 'none', None], x))
    if len(x) != 0:
        res = sum([float(item) for item in x])/len(x)
        return round(res,6)
    else:
        return 0

def args_parse():
    parser = argparse.ArgumentParser(description="filter the invalid data in result.xlsx")
    parser.add_argument("-f", "--result_dir", type=str, dest="result_dir",
                        help="the result xlsx file", default='benchmark/results/')
    parser.add_argument("-t", "--traj_coverage_thre", type=str, dest="traj_coverage_thre",
                        help="specify the threshold of trajectory ratio", default=0.6)
    parser.add_argument("-m", "--tum_euroc_ape_threshold", type=str, dest="tum_euroc_ape_threshold",
                        help="specify the threshold of ape for filtering mono&stereo datatype", default=0.15)
    parser.add_argument("-k", "--kitti_ape_ratio_threshold", type=str, dest="kitti_ape_ratio_threshold",
                        help="specify the threshold of ape for filtering KITTI data", default=1)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    
    args = args_parse()
    result_dir = args.result_dir
    result_file = result_dir + 'result.xlsx'
    traj_coverage_thre = float(args.traj_coverage_thre)  # threshold of 'traj_conv'/'gt_conv'
    tum_euroc_ape_threshold = float(args.tum_euroc_ape_threshold)
    kitti_ape_ratio_threshold = float(args.kitti_ape_ratio_threshold)

    filter_list = []
    unique_filter_list = []
    test_cmd_list = []

    if not os.path.exists(result_file):
        sys.exit('"{}" not found, run benchmark with --save_to_excel to get a result.xlsx file before filter results'.format(result_file))
    data = pd.read_excel(result_file, sheet_name='result', header=0)
    data['isvalid'] = True
    ### 1. filter the rows with traj errors:
    for index, row in data.iterrows():
        ratio = row['traj_conv'] / row['gt_conv']
        if ratio < traj_coverage_thre:
            # print(f"Row {index}: dataname={row['dataset']}, dataset={row['dataname']}")
            filter_list.append([row['dataset'],row['dataname']])
            data.at[index,'isvalid'] = False

    data_traj_filtered = data[data['isvalid']==True]

    ### 2. filter the mono&stereo data which rows have 'ape' - min('ape') > threshold
    # exclude kitti data 
    mono_ste_traj_filtered = data_traj_filtered[~(data_traj_filtered['dataname'].str.contains('kitti'))]
    # Group rows by ['dataset', 'dataname']
    g_mono_ste_traj_filtered = mono_ste_traj_filtered.groupby(['dataset', 'dataname'])
    mono_ste_invalid = mono_ste_traj_filtered[mono_ste_traj_filtered['ape'] > g_mono_ste_traj_filtered['ape'].transform('min') + tum_euroc_ape_threshold]
    for idx, row in mono_ste_invalid.iterrows():
        filter_list.append([row['dataset'],row['dataname']])
        data.loc[idx,'isvalid'] = False

    ### 3. filter the kitti data by standard deviation of 'ape'
    # only include kitti data
    kitti_traj_filtered = data_traj_filtered.loc[data_traj_filtered['dataname'].str.contains('kitti')]
    g_kitti_traj_filtered = kitti_traj_filtered.groupby(['dataset', 'dataname'])
    # We only mark 'invalid' for rows in the groups with large std value 
    # first, find the groups with large std values
    std_deviation = g_kitti_traj_filtered['ape'].agg(['mean', 'std'])
    filtered_std_deviation = std_deviation[std_deviation['std'] / std_deviation['mean'] > kitti_ape_ratio_threshold]
    filtered_std_list = []
    for idx, row in filtered_std_deviation.iterrows():
        filtered_std_list.append([row[0],row[1]])
    # second, for each group with large std value, filter the rows with 'ape' much larger than min 'ape' of the group
    kitti_invalid = kitti_traj_filtered[kitti_traj_filtered['ape'] / g_kitti_traj_filtered['ape'].transform('min') > 2*kitti_ape_ratio_threshold]
    for idx, row in kitti_invalid.iterrows():
        if [row[0],row[1]] in filtered_std_list:
            filter_list.append([row[0],row[1]])
            data.loc[idx,'isvalid']=False

    # Iterate over the filter_list and append only unique occurrences
    for elem in filter_list:
        if elem not in unique_filter_list:
            unique_filter_list.append(elem)

    # add mean sheet and filtered sheet to result.xlsx
    data_valid = data[data['isvalid']==True]
    data_valid = data_valid.drop('traj_conv',axis=1)
    data_valid = data_valid.drop('gt_conv',axis=1)
    data_valid = data_valid.drop('isvalid',axis=1)
    data_valid_enough = data_valid.groupby(['dataset', 'dataname'], as_index=False).filter(lambda x: x['ape'].count() >= 3)
    data_valid_not_enough = data_valid.groupby(['dataset', 'dataname'], as_index=False).filter(lambda x: x['ape'].count() < 3)
    data_mean = data_valid_enough.groupby(['dataset', 'dataname'], as_index=False).agg({"ape":mean,"rpe":mean,"scale":average_scale_correction})

    # delete the data which have tested enough times
    for idx, row in data_valid_enough.iterrows():
        if [row['dataset'],row['dataname']] in unique_filter_list:
            unique_filter_list.remove([row['dataset'],row['dataname']])
    data_filtered = pd.DataFrame(unique_filter_list)
    # somehow, some cases have no invalid data, but not finish three times test
    for idx, row in data_valid_not_enough.iterrows():
        if [row['dataset'],row['dataname']] not in unique_filter_list:
            unique_filter_list.append([row['dataset'],row['dataname']])
    data_filtered = pd.DataFrame(unique_filter_list)
    if len(data_filtered.columns)>0:
        data_filtered = data_filtered.sort_values([0, 1])
    writer = pd.ExcelWriter(result_file, engine='openpyxl', mode='a', if_sheet_exists='replace')
    data = data.sort_values(['dataset', 'dataname'])
    data_mean = data_mean.sort_values(['dataset', 'dataname'])
    data.to_excel(writer, index=False, header=True, sheet_name="result")
    data_mean.to_excel(writer, index=False, header=True, sheet_name="mean")
    data_filtered.to_excel(writer, index=False, header=False, sheet_name="filtered")
    writer.save()