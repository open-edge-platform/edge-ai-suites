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

#ifndef DODBSCAN_HPP_
#define DODBSCAN_HPP_

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <vector>

#define BOOST_MPL_CFG_NO_PREPROCESSED_HEADERS
#define BOOST_MPL_LIMIT_VECTOR_SIZE 50
#include <boost/mpl/vector.hpp>

#include "ADBScan.h"
#include "Util.hpp"

vector<Obstacle> doDBSCAN(
  void * p_Data, int LiDAR_data_size, int dimension, std::vector<double> * benchmark_time);

double diff(timespec start, timespec end);

#endif  // DODBSCAN_HPP_
