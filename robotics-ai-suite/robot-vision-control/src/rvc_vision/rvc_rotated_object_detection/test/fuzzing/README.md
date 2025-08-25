# Fuzzing Example for Python Code
The scope of this PR is to provide **only an initial example** for fuzzing code written in Python for 
the Robotics SDK and RVC repos. The identified fuzzer is the [Google atheris](https://github.com/google/atheris) framework.

## Execution
Follows a list of used commands for executing the fuzzing and generating a coverage report.

### Standard Execution
Specifying a certain amount of runs:
```
python3 fuzzing/fuzz_detector.py -atheris_runs=20
```
Using a timeout (seconds):
```
python3 fuzzing/fuzz_detector.py -max_total_time=60
```

### Execution with Coverage
```
python3 -m coverage run fuzzing/fuzz_detector.py -atheris_runs=20
python3 -m coverage report
```
The `report` argument can be replaced with arguments like `html`, `json`, etc.

Sometimes, the coverage report cannot be generated when the `-max_total_time` option is used (probably because of
a non clean termination of the program).

## Output
Follows the produced output for the previously described commands.

### Execution output
```
python3 -m coverage run fuzzing/fuzz_detector.py -atheris_runs=200
INFO: Using built-in libfuzzer
WARNING: Failed to find function "__sanitizer_acquire_crash_state".
WARNING: Failed to find function "__sanitizer_print_stack_trace".
WARNING: Failed to find function "__sanitizer_set_death_callback".
INFO: Running with entropic power schedule (0xFF, 100).
INFO: Seed: 3265257615
INFO: -max_len is not provided; libFuzzer will not generate inputs larger than 4096 bytes
INFO: A corpus is not provided, starting from an empty corpus
#2      INITED exec/s: 0 rss: 468Mb
WARNING: no interesting inputs were found so far. Is the code instrumented for coverage?
This may also happen if the target rejected all inputs we tried so far
#16     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 468Mb
#32     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 468Mb
#64     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 468Mb
#128    pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 468Mb
Done 200 in 40 second(s)
rvc@kadasd543:~/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/test$
rvc@kadasd543:~/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/test$
rvc@kadasd543:~/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/test$
rvc@kadasd543:~/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/test$
rvc@kadasd543:~/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/test$ python3 -m coverage run fuzzing/fuzz_detector.py -atheris_runs=200
INFO: Using built-in libfuzzer
WARNING: Failed to find function "__sanitizer_acquire_crash_state".
WARNING: Failed to find function "__sanitizer_print_stack_trace".
WARNING: Failed to find function "__sanitizer_set_death_callback".
INFO: Running with entropic power schedule (0xFF, 100).
INFO: Seed: 3418003968
INFO: -max_len is not provided; libFuzzer will not generate inputs larger than 4096 bytes
INFO: A corpus is not provided, starting from an empty corpus
#2      INITED exec/s: 0 rss: 467Mb
WARNING: no interesting inputs were found so far. Is the code instrumented for coverage?
This may also happen if the target rejected all inputs we tried so far
#16     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 467Mb
#32     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 467Mb
#64     pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 467Mb
#128    pulse  corp: 1/1b lim: 4 exec/s: 5 rss: 467Mb
Done 200 in 40 second(s)
```

### Coverage Report
Please note that it was asked to instrument only one specific function but, apparently, this mechanism works recursively for the subsequent calls:
```
 python3 -m coverage report
Name                                                                                                                                                                                                              Stmts   Miss  Cover
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_messages/rosidl_generator_py/rvc_messages/__init__.py                                                                                      0      0   100%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_messages/rosidl_generator_py/rvc_messages/msg/__init__.py                                                                                  2      0   100%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_messages/rosidl_generator_py/rvc_messages/msg/_pose_stamped.py                                                                           126     83    34%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_messages/rosidl_generator_py/rvc_messages/msg/_pose_stamped_list.py                                                                       93     62    33%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_vision_messages/rosidl_generator_py/rvc_vision_messages/__init__.py                                                                        0      0   100%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_vision_messages/rosidl_generator_py/rvc_vision_messages/msg/__init__.py                                                                    2      0   100%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_vision_messages/rosidl_generator_py/rvc_vision_messages/msg/_rotated_bb.py                                                               159    103    35%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/build/rvc_vision_messages/rosidl_generator_py/rvc_vision_messages/msg/_rotated_bb_list.py                                                           93     46    51%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/rvc_rotated_object_detection/__init__.py                                  0      0   100%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/rvc_rotated_object_detection/object_detection.py                        237    159    33%
/home/rvc/workspace/frameworks.industrial.robotics.rvc.use-cases/src/frameworks.industrial.robotics.rvc.vision/rvc_rotated_object_detection/rvc_rotated_object_detection/rotated_object_detection_parameters.py     436    380    13%
/opt/ros/humble/lib/python3.10/site-packages/ament_index_python/__init__.py                                                                                                                                          14      0   100%
/opt/ros/humble/lib/python3.10/site-packages/ament_index_python/constants.py       
...
fuzzing/fuzz_detector.py                                                                                                                                                                                             34      4    88%
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
TOTAL                                                                                                                                                                                                             19557  12690    35%
```
