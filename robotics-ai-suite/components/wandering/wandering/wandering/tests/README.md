<!--
Copyright (C) 2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Wandering App Test Suite

## testing

## Running

After building wandering app, navigate to `build/wandering_app` and run:
```bash
ctest -V -R test_goalcatcher
ctest -V -R test_mapengine
ctest -V -R test_mapper
ctest -V -R test_inputs
ctest -V -R test_invalid_param
```
