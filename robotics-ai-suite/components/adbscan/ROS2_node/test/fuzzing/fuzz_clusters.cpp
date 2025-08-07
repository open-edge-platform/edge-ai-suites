// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "gtest/gtest.h"
#include "fuzztest/fuzztest.h"

#include "../../src/Util.hpp"

void testCalculateClusters(std::vector<double> x, std::vector<double> y, std::vector<double> z)
{
    std::vector<Point> points_in_frame;
    for (auto i = 0; i < x.size(); i++)
    {
        points_in_frame.push_back(Point(x[i], y[i], z[i]));
    }
    get_clusters(std::move(points_in_frame));
}

FUZZ_TEST(ADBSCANTest, testCalculateClusters)
    .WithDomains(/*x:*/fuzztest::Arbitrary<std::vector<double>>().WithSize(50),
                 /*y:*/fuzztest::Arbitrary<std::vector<double>>().WithSize(50),
                 /*z:*/fuzztest::Arbitrary<std::vector<double>>().WithSize(50));