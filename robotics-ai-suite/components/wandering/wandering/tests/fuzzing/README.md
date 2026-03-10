<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Fuzzing
The fuzzing tests in this folder relies on the Google
[Fuzztest framework](https://github.com/google/fuzztest). The test can be
executed relying on the
`ger-registry.caas.intel.com/isd-ka/eci-fuzzer:latest` Docker image.
The following sections describe the steps to do so.

## Github Action
...

## Manual Execution
The steps in this section show how to manually run the fuzz tests.

### Docker Environment
The `eci-fuzzer` image is based on this
[Dockerfile](https://github.com/intel-innersource/frameworks.industrial.edge-controls.cicd.docker-images/blob/main/dev/amr-build/Dockerfile).
The image can be pulled directly from Harbor:
```bash
docker pull ger-registry.caas.intel.com/isd-ka/eci-fuzzer:latest
```

#### Start the Docker Container
The following commands allow to start a Docker container based on the `eci-fuzzer`
image and to connect to it:
```bash
cd applications.robotics.mobile.wandering
docker run -v $PWD:/home -itd --name <<wandering_fuzzer_container>> ger-registry.caas.intel.com/isd-ka/eci-fuzzer:latest 'bash'
docker exec -it <<wandering_fuzzer_container>> /bin/bash
```

#### Environment Setup
The ROS2 environment can be set up by sourcing the following file:
```bash
source /opt/ros/humble/setup.bash
```

### Build and Execute Tests
The tests can be built as follows:
```bash
cd /home
CXX=clang++ colcon build --packages-select wandering_app --cmake-args -DCXX=clang++ -DFUZZTEST_FUZZING_MODE=ON -DBUILD_TESTING=OFF
...
```
At the end of the compilation process, the test can be executed producing a similar output:
```bash
build/wandering_app/fuzz_mapengine -fuzz_for=2s

[.] Sanitizer coverage enabled. Counter map size: 32117, Cmp map size: 262144
[==========] Running 1 test from 1 test suite.
[----------] Global test environment set-up.
[----------] 1 test from MapEngineTest
[ RUN      ] MapEngineTest.testFunctionsWithInput
FUZZTEST_PRNG_SEED=MvzUJwl4oTsd9xBv-vC8ewJ8QQ82KMKNytmcKhlh2p0
[*] Corpus size:     1 | Edges covered:     53 | Fuzzing time:        665.802us | Total runs:  1.00e+00 | Runs/secs:  1501 | Max stack usage:    14208
[.] Fuzzing timeout set to: 2s
[*] Corpus size:     2 | Edges covered:     54 | Fuzzing time:        749.727us | Total runs:  4.00e+00 | Runs/secs:  5335 | Max stack usage:    14208
[*] Corpus size:     3 | Edges covered:     55 | Fuzzing time:        936.066us | Total runs:  2.50e+01 | Runs/secs: 26707 | Max stack usage:    14208
[*] Corpus size:     4 | Edges covered:     57 | Fuzzing time:        1.22407ms | Total runs:  5.90e+01 | Runs/secs: 48199 | Max stack usage:    14208
[*] Corpus size:     5 | Edges covered:     57 | Fuzzing time:       1.271593ms | Total runs:  6.20e+01 | Runs/secs: 48757 | Max stack usage:    14208
[*] Corpus size:     6 | Edges covered:     58 | Fuzzing time:      90.721405ms | Total runs:  1.25e+04 | Runs/secs: 137387 | Max stack usage:    14208
[*] Corpus size:     7 | Edges covered:     59 | Fuzzing time:     500.020285ms | Total runs:  6.96e+04 | Runs/secs: 139230 | Max stack usage:    14208

[.] Fuzzing was terminated.

=================================================================
=== Fuzzing stats

Elapsed time: 2.000113205s
Total runs: 286514
Edges covered: 59
Total edges: 32117
Corpus size: 7
Max stack used: 14208

[       OK ] MapEngineTest.testFunctionsWithInput (2000 ms)
[----------] 1 test from MapEngineTest (2000 ms total)

[----------] Global test environment tear-down
[==========] 1 test from 1 test suite ran. (2000 ms total)
[  PASSED  ] 1 test.

```
