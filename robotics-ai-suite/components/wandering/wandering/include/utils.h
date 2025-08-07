// SPDX-License-Identifier: Apache-2.0
/*
Copyright (C) 2025 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*/

#ifndef UTILS_H
#define UTILS_H
#include <stdio.h>
#include <iostream>
#include <array>

#include "nav2_costmap_2d/cost_values.hpp"

#define COSTMAP_VAL_SIZE 256

using namespace std;

array<uint8_t, COSTMAP_VAL_SIZE> occup_cost_mapping();

#endif