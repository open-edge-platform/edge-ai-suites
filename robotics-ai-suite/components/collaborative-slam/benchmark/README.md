### Description

The benchmark is used to test the robustness and the accuray of the Collaborative SLAM system on ROS2. Currently, it contains five test scripts which support the following tests:
   ```
(1) RGBD input for TUM dataset
(2) Monocular input for TUM, EuRoC and KITTI datasets
(3) Stereo input for EuRoC and KITTI datasets
(4) Monocular with IMU input for EuRoC dataset
(5) Stereo with IMU input for EuRoC dataset
   ```
The benchmark scripts will launch two ROS node: univloc_tracker and univloc_server together with another process to play the .bag/.orig.bag file as the input. We prefer the .bag file since they are already decompressed and don't need to consume resource for decompression while playing. For each sequence in the dataset, the benchmark will test it and calculate the RMSE of the pose trajectory by the "evo_ape" and "evo_rpe" tools. For EuRoC dataset, we wil also calculate the scale percentage error when using IMU as auxiliary sensor input.

---

### Dependency

1. evo toolkit is necessary through [this_page](https://github.com/MichaelGrupp/evo). After installation, please add it to your PATH by:
   ```
   export PATH=$PATH:{evo_binary_path}
   ```

2. To use the automatic benchmarking script for all datasets ```auto_test_filter.sh```, additional packages are needed through
   ```
   pip3 install pandas==1.4.0 xlsxwriter openpyxl
   ```
   We recommend to follow the specific version of ```pandas``` above, otherwise you may encounter error caused by API changes of ```pandas```.

---

### Argument

1. Benchmark for all scripts:
```
- positional arguments:
  {tum, euroc, kitti}              the dataset to be tested. 
                                   for `rgbd_benchmark.py`, option: tum
                                   for `mono_benchmark.py`, option: tum/euroc/kitti
                                   for `mono_imu_benchmark.py`, option: euroc
                                   for `stereo_benchmark.py`, option: euroc/kitti
                                   for `stereo_imu_benchmark.py`, option: euroc

- optional arguments:
  -h, --help                       show this help message and exit
  -b BAGFILE_DIR, --bagfile_dir BAGFILE_DIR
                                   the directory which stores the .bag file
  -f RESULTFILE_DIR, --resultfile_dir RESULTFILE_DIR
                                   the directory of the result file which stores the trajectory data
  -r REPEAT_NUM, --repeat REPEAT_NUM
                                   the number to repeat for each test 
  -g GROUNDTRUTH_DIR, --groudtruth GROUNDTRUTH_DIR
                                   the directory of the groudtruth files
  -w WAIT, --wait WAIT             the delay to exit nodes after playback of .bag file
  -p ROS1_PATH, --ros1_path ROS1_PATH
                                   the installation path of the ROS1
  --rmse RMSE_THRESHOLD            the threshold of evaluated RMSE to pass a single test
  --store STORE_TRUE               store tracjectory files for each test loop
  --evaluate_rpe                   evalute rpe for trajectory output
  --save_to_excel                  save accuracy data of each test loop to result.xlsx
  --from_scratch                   add from_scratch will remove the old reult.xlsx and test all the benchmark from scratch, otherwise the result will be added to the current result.xlsx
  --retest_failures_once           only test the dataset in the filtered sheet of result.xlsx, "--retest_failures_once" should be used together with "--save_to_excel"
```
2. filter.py for filtering results calculated by benchmark scripts:
```
- optional arguments:
  -h, --help                       show this help message and exit
  -f, --result_dir,                the directory which stores the result xlsx file
  -t, --traj_coverage_thr,         specify the ratio threshold of trajectory_conv/gt_trajectory_conv
  -m, --tum_euroc_ape_threshold,   specify the threshold of ape for filtering TUM&EuRoC datatype
  -k, --kitti_ape_ratio_threshold, specify the threshold of ape for filtering KITTI datatype
```
3. auto_test_filter.sh including whole test and filter scripts:

```
- command format: bash benchmark/auto_test_filter.sh arg1 arg2
(1) If the first argument "arg1" is 'yes' or 'y', it will run all the benchmark scripts on all datasets from scratch and output the results in the result sheet of result.xlsx. Then run the filter.py to filter the invalid results and calculate the mean values. The output is stored in the mean sheet and filtered sheet in result.xlsx. Otherwise, the process will not go through these scripts and will directly go to the next part.
(2) The second argument "arg2" is a integer number, it will loop such times as following: It will run all the benchmark scripts on the datasets which are stored in the filtered sheet of result.xlsx. Then run the filter.py to update the mean sheet and filter the datasets which may need to be tested again.
```
---

### Note

1. Since the TUM, EuRoc and KITTI datasets are all packaged as the ROS1 format, so you also need to install a ROS1 version on your environment. Currently, we are using ROS Noetic on our development environment. For installation you can refer to http://wiki.ros.org/noetic/Installation.

2. The script matches the groundtruth file with the .bag/.orig.bag file by their name format. In the TUM dataset, the gorundtruth files are always named as `{test_case_name}-groundtruth.txt` and the .bag files are always named as `{test_case_name}.bag` or `{test_case_name}.orig.bag`. But in the EuRoC dataset, the user should first manually transform the .csv gorundtruth files to tum format and rename them to `{test_case_name}-groundtruth.tum`. The transform command is `evo_traj euroc data.csv --save_as_tum` and you can refer to https://github.com/MichaelGrupp/evo/wiki/Formats for more information.

3. The benchmark scripts are based on ROS2 launch module.
