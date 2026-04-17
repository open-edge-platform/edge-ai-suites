// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "MapEngine.h"
#include "fuzztest/fuzztest.h"
#include "gtest/gtest.h"

void testFunctionsWithInput(bool useCostMap, double robotRadius, double x, double y)
{
  MapEngine mapEngine(useCostMap, robotRadius);
  mapEngine.getNextGoalCoord(x, y);
}

FUZZ_TEST(MapEngineTest, testFunctionsWithInput);
