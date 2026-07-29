// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <filesystem>
#include <string>

#include "mapenginetest.hpp"

TEST_F(MapEngineTest, mapTest)
{
  path fileLocation = __FILE__;
  fileLocation = fileLocation.parent_path().string() + "/inputs/map.log";
  ASSERT_TRUE(testInit(fileLocation.string(), false));
  ASSERT_TRUE(testCoord());
  SUCCEED();
}

TEST_F(MapEngineTest, costmapTest)
{
  path fileLocation = __FILE__;
  fileLocation = fileLocation.parent_path().string() + "/inputs/costmap.log";
  ASSERT_TRUE(testInit(fileLocation.string(), true));
  ASSERT_TRUE(testCoord());
  SUCCEED();
}

TEST_F(MapEngineTest, costmapTestWithReset)
{
  path fileLocation = __FILE__;
  fileLocation = fileLocation.parent_path().string() + "/inputs/costmap.log";
  ASSERT_TRUE(testInit(fileLocation.string(), true));
  ASSERT_TRUE(testCoord());
  resetVisited();
  ASSERT_TRUE(testCoord());
  SUCCEED();
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);

  bool all_successful = RUN_ALL_TESTS();

  return all_successful;
}
