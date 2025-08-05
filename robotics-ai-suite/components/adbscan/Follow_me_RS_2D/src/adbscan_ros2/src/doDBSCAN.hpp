// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "ADBScan.h"
#include <iostream>
#include <fstream>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <time.h>
#include <cstdlib>
#include <vector>
#include "Util.hpp"

Point_xyz doDBSCAN(void *p_Data, int LiDAR_data_size, int dimension, Point_xyz target_loc, int& num_blocked_frame, vector<Obstacle>& obstacle_list);
double diff(timespec start, timespec end);