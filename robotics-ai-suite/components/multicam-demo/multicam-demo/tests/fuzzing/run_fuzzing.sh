#!/bin/bash

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# Run fuzzing for realsense-d457-ai-demo using google atheris (https://github.com/google/atheris)
FUZZ_SCRIPT='tests/fuzzing/realsense-d457-ai-demo_fuzzing.py'
FUZZ_LOG='tests/fuzzing/realsense-d457-ai-demo_fuzzing.log'


if [ -f $FUZZ_LOG ]; then
  rm -f $FUZZ_LOG
fi

echo -e "--------------------------------------------------------" | tee -a $FUZZ_LOG
echo "Fuzzing log for realsense-d457-ai-demo." | tee -a $FUZZ_LOG
echo -e "-------------------------------------------------------- \n \n" | tee -a $FUZZ_LOG
echo "Fuzzing sart timestamp: $(date)" | tee -a $FUZZ_LOG
echo -e "-------------------------------------------------------- \n" | tee -a $FUZZ_LOG

python3 $FUZZ_SCRIPT -atheris_runs=2000000 2>&1 | tee -a $FUZZ_LOG

echo -e "\n---------------------------------------------------------" | tee -a $FUZZ_LOG
echo "Fuzzing end timestamp: $(date)" | tee -a $FUZZ_LOG
