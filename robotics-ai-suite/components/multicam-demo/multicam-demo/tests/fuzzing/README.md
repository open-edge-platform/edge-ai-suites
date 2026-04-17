<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Fuzzing test for applications.robotics.mobile.realsense-d457-ai-demo

In this readme file the fuzzing test for realsense-d457-ai-demo is explained. The fuzzer used here for fuzzing the code written in Python is [Google atheris](https://github.com/google/atheris). As an initial example, the constructor of the class "ImreadWrapper" from the python file images_capture.py is considered.

## Prerequisite

As a prerequisite the [python3.x](https://www.python.org/downloads/) and the [Google atheris](https://github.com/google/atheris) must be installed.

```bash
# Install python3.8
$ sudo apt-get -y install python3.8

#Install Google atheris
$ pip3 install atheris
```


## Execution

The command used for executing the fuzzer is as given below:

```bash
# Fuzzer command
$ python3 realsense-d457-ai-demo_fuzzing.py -atheris_runs=200000 2>&1 | tee -a ./realsense-d457-ai-demo_fuzzing.log
```

Here, the fuzzer is run for 200000 iterations and the report is saved in the file `realsense-d457-ai-demo_fuzzing.log`.
The script `run_fuzzing.sh` is created to run the fuzzer. This script will also capture the fuzzer log into a file along with the start and end timestamp of the fuzzer run. The log file looks like as shown below.

```text
--------------------------------------------------------
Fuzzing log for realsense-d457-ai-demo.
--------------------------------------------------------


Fuzzing sart timestamp: Wed Jun 26 08:28:29 AM EDT 2024
--------------------------------------------------------

INFO: Using built-in libfuzzer
WARNING: Failed to find function "__sanitizer_acquire_crash_state".
WARNING: Failed to find function "__sanitizer_print_stack_trace".
WARNING: Failed to find function "__sanitizer_set_death_callback".
INFO: Running with entropic power schedule (0xFF, 100).
INFO: Seed: 3141140511
INFO: -max_len is not provided; libFuzzer will not generate inputs larger than 4096 bytes
INFO: A corpus is not provided, starting from an empty corpus
#2  INITED exec/s: 0 rss: 91Mb
WARNING: no interesting inputs were found so far. Is the code instrumented for coverage?
This may also happen if the target rejected all inputs we tried so far
Done 200000 in 2 second(s)

 --------------------------------------------------------
Fuzzing end timestamp: Wed Jun 26 08:28:31 AM EDT 2024
```