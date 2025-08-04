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

#include "utils.h"

/*
    Occupancy grid provides values [-1..100] and costmap
    takes [0..255].
*/
array<uint8_t, COSTMAP_VAL_SIZE> occup_cost_mapping()
{
  array<uint8_t, COSTMAP_VAL_SIZE> cost_translation_table{};

  // Linearly map from [-1..100] to [0..255]
  for (int i = 0; i < COSTMAP_VAL_SIZE; ++i) {
    // Use a safer version of the calculation to avoid integer overflows
    cost_translation_table[i] = static_cast<uint8_t>((i == 0) ? nav2_costmap_2d::FREE_SPACE :
                                                      (i == 99) ? nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE :
                                                      (i == 100) ? nav2_costmap_2d::LETHAL_OBSTACLE :
                                                      (i == COSTMAP_VAL_SIZE-1) ? nav2_costmap_2d::NO_INFORMATION :
                                                      ((i - 1) * 251) / 97 + 1);
  }
  return cost_translation_table;
}
