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

#include <fstream>
#include <stdio.h>
#include <mutex>
#include <iomanip>

#include <rclcpp/rclcpp.hpp>
#include "nav2_costmap_2d/cost_values.hpp"

#include "MapEngine.h"
#include "utils.h"

using std::placeholders::_1;

static const std::array<uint8_t, 256> costs_mapping =
    occup_cost_mapping();

MapEngine::MapEngine(bool useCostMap, double robotRadius): robotIMapIndex_(0), robotJMapIndex_(0), unexploredPrctg_(0), freePrctg_(0), occupiedPrctg_(0),
     robotRadius_(robotRadius), coordOffset_(0), robotRadiusCells_(0),
     logCounter(0), logRate_(256), mapPrintCounter_(0), useCostMap_(useCostMap), resetDone_(false), storeMapToFile_(false)
  {
      this->map_ = std::make_shared<nav_msgs::msg::OccupancyGrid>();
  }

MapEngine::~MapEngine() {
    this->printMap();
}

bool MapEngine::init() {
    if (!this->isMapValid())
        return false;

    this->checkMapCoverage();
    return true;
}

void MapEngine::mapCallback(const nav_msgs::msg::OccupancyGrid::SharedPtr map) {
    this->map_ = map;
    this->updateMapInfo();
}

void MapEngine::updateMapInfo() {
    uint64_t mapSize = (uint64_t)this->map_->info.width * (uint64_t)this->map_->info.height;
    if (this->visitedMap_.size() != mapSize)
        this->visitedMap_.resize(mapSize, false);
    uint32_t diffThr = 20;
    if (this->map_->info.width < this->costmap_.getSizeInCellsX() && this->map_->info.height < this->costmap_.getSizeInCellsY()) {
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Received map update with smaller dimensions %dx%d, compared to %dx%d.",
            this->map_->info.width, this->map_->info.height, this->costmap_.getSizeInCellsX(), this->costmap_.getSizeInCellsY());
        if ((this->costmap_.getSizeInCellsX() - this->map_->info.width) > diffThr && (this->costmap_.getSizeInCellsY() - this->map_->info.height) > diffThr) {
            RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Will reset visited places...");
            this->resetVisitedMap();
            this->resetDone_ = true;
        }
    }

    auto* mutex = this->costmap_.getMutex();
    std::lock_guard<std::recursive_mutex> lock(*mutex);

    this->costmap_.resizeMap(this->map_->info.width, this->map_->info.height, this->map_->info.resolution,
                    this->map_->info.origin.position.x, this->map_->info.origin.position.y);

    uint8_t* costmap_data = this->costmap_.getCharMap();
    for (uint64_t i = 0; i < mapSize; i++) {
        uint8_t cell_cost = static_cast<uint8_t>(this->map_->data[i]);
        costmap_data[i] = costs_mapping[cell_cost];
    }

    this->robotRadiusCells_ = this->costmap_.cellDistance(this->robotRadius_);
    this->coordOffset_ = this->costmap_.cellDistance(2 * this->robotRadius_);
}

bool MapEngine::checkAreaForValue(uint32_t i, uint32_t j, uint32_t range, uint8_t value) {
    uint8_t* costmap_data = this->costmap_.getCharMap();
    for (uint32_t k = (i - range); k < (i + range); k++) {
        for (uint32_t l = (j - range); l < (j + range); l++) {
            uint32_t index = this->costmap_.getIndex(k, l);
            if (!this->useCostMap_) {
                if (this->visitedMap_[index] || costmap_data[index] != value)
                    return false;
            } else {
                if (this->visitedMap_[index] || costmap_data[index] > nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE)
                    return false;
            }
        }
    }

    return true;
}

/*
    Print map values as well as visited places map.
    Mostly for debugging purpose.
*/
void MapEngine::printMap() {
    if (!this->storeMapToFile_)
        return;
    std::string mapFilename = "map" + std::to_string(this->mapPrintCounter_) + ".log";
    std::string visitedFilename = "visited" + std::to_string(this->mapPrintCounter_) + ".log";
    ofstream mapfp;
    ofstream visitedMapFp;
    mapfp.open(mapFilename);
    if (!mapfp.is_open())
        return;
    visitedMapFp.open(visitedFilename);
    if (!visitedMapFp.is_open()) {
        mapfp.close();
        return;
    }
    for (uint32_t i = 0; i < this->costmap_.getSizeInCellsY(); i++) {
        mapfp << "[" << right << setw(4) << i << "]";
        visitedMapFp << "[" << right << setw(4) << i << "]";
        for (uint32_t j = 0; j < this->costmap_.getSizeInCellsX(); j++) {
            uint32_t index = this->costmap_.getIndex(i, j);
            mapfp << right << setw(3) << this->map_->data[index];
            visitedMapFp << right << setw(3) << (this->visitedMap_[index] ? 1 : 0);
        }
        mapfp << endl;
        visitedMapFp << endl;
    }
    mapfp.close();
    visitedMapFp.close();
    this->mapPrintCounter_++;
}

bool MapEngine::getNextFreeCell(uint32_t &i, uint32_t &j) {
    uint32_t index = 0;
    uint32_t range = this->coordOffset_;
    uint32_t boxSize;
    auto* mutex = this->costmap_.getMutex();
    std::lock_guard<std::recursive_mutex> lock(*mutex);
    boxSize = this->robotRadiusCells_;
    for (i = this->robotIMapIndex_; i < (this->costmap_.getSizeInCellsX() - range); i+= range) {
        for (j = range; j < (this->costmap_.getSizeInCellsY() - range); j += range) {
            //RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Checking cell found (%d, %d).",
            //        i, j);
            if (this->checkAreaForValue(i, j, boxSize, nav2_costmap_2d::FREE_SPACE)) {
                index = this->costmap_.getIndex(i, j);
                this->visitedMap_[index] = true;
                RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Free cell found (%d, %d).",
                    i, j);
                return true;
            }
        }
    }

    for (i = this->robotIMapIndex_; i > range; i -= range) {
        for (j = (this->costmap_.getSizeInCellsY() - range); j > range; j -= range) {
            index = this->costmap_.getIndex(i, j);
            //RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Checking cell found (%d, %d).",
            //        i, j);
            if (this->checkAreaForValue(i, j, boxSize, nav2_costmap_2d::FREE_SPACE)) {
                this->visitedMap_[index] = true;
                RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Free cell found (%d, %d).",
                    i, j);
                return true;
            }
        }
    }

    return false;
}

bool MapEngine::isMapValid() {
    if (this->map_->info.width == 0 && this->map_->info.height == 0)
        return false;

    return true;
}

bool MapEngine::setRobotPose(const geometry_msgs::msg::PoseStamped pose) {
    this->robotPose_ = pose;
    bool shouldLog = (0 % this->logRate_) == 0;
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Current pose: (%f, %f), orientation %f.", this->robotPose_.pose.position.x,
        this->robotPose_.pose.position.y, this->robotPose_.pose.orientation.w);
    
    if (!this->costmap_.worldToMap(this->robotPose_.pose.position.x, this->robotPose_.pose.position.y,
        this->robotIMapIndex_, this->robotJMapIndex_)) {
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Robot pose out of bounds!");
        return false;
    }

    this->visitedMap_[this->costmap_.getIndex(this->robotIMapIndex_, this->robotJMapIndex_)] = true;
    return true;
}

double MapEngine::getUnexploredPrstg() const {
    return this->unexploredPrctg_;
}

void MapEngine::checkMapCoverage() {
    if (!this->isMapValid())
        return;
    bool shouldLog = (this->logCounter % this->logRate_) == 0;
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Map W: %d H: %d", this->map_->info.width, this->map_->info.height);
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Origin position %f %f", this->costmap_.getOriginX(), this->costmap_.getOriginY());
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Resolution %f", this->costmap_.getResolution());
    uint32_t unexplored = 0;
    uint32_t freeSpace = 0;
    uint32_t occupiedSpace = 0;
    uint64_t total = (uint64_t)this->map_->info.width * (uint64_t)this->map_->info.height;
    for (uint64_t i = 0; i < total; i++) {
        if (this->map_->data[i] >= 0 && this->map_->data[i] < 100)
            freeSpace++;
        else if (this->map_->data[i] == -1)
            unexplored++;
        else if (this->map_->data[i] >= 100)
            occupiedSpace++;
    }
    this->unexploredPrctg_ = ((double) unexplored / (double) total) * 100;
    this->freePrctg_ = ((double) freeSpace / (double) total) * 100;
    this->occupiedPrctg_ = ((double) occupiedSpace / (double) total) * 100;
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Unexplored space %.0f%%", this->unexploredPrctg_);
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Free space %.0f%%", this->freePrctg_);
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Occupied space %.0f%%", this->occupiedPrctg_);
    RCLCPP_INFO_EXPRESSION(rclcpp::get_logger("wandering_mapper"), shouldLog, "Robot cell distance %d", this->coordOffset_);
    this->logCounter++;
}

/*
    Move robot in one of the four directions(left, right, up, down)
    based on either farest free cell or nearest unkown cell.
*/
bool MapEngine::exploreDirections(double &x, double &y, bool unknownArea) {
    uint8_t counter = 0;
    for (auto &movement : this->movMethodNames_) {
        uint32_t i = this->robotIMapIndex_;
        uint32_t j = this->robotJMapIndex_;
        bool foundCell = false;
        uint8_t directionIndex = counter * 2;
        if (unknownArea) {
            if (this->moveToNearestUnknownCell(i, j, this->directions_[directionIndex], this->directions_[directionIndex + 1]) == nav2_costmap_2d::NO_INFORMATION)
                foundCell = true;
        } else {
            this->moveToFarestFreeCell(i, j, this->directions_[directionIndex], this->directions_[directionIndex + 1]);
            if (this->shouldMove(i, j))
                foundCell = true;
        }
        if (foundCell) {
            uint32_t index = this->costmap_.getIndex(i, j);
            if (!this->visitedMap_[index]) {
                this->visitedMap_[index] = true;
                this->costmap_.mapToWorld(i, j, x, y);
                RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Move %s at (%d, %d), with coord (%f, %f).",
                movement.c_str(), i, j, x, y);
                return true;
            }
        }
        counter++;
    }

    return false;
}

bool MapEngine::getNextGoalCoord(double &x, double &y) {
    if (!this->isMapValid())
        return false;
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Finding the farest free cell...");
    if (this->exploreDirections(x, y, false))
        return true;
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Farest free non-visited cell not found! Trying to explore unknown space...");
    if (this->exploreDirections(x, y, true))
        return true;

    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Did not find unknown space cell. Trying to find any free non-visited cell...");
    uint32_t i = this->robotIMapIndex_;
    uint32_t j = this->robotJMapIndex_;
    if (!this->getNextFreeCell(i, j)) {
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Did not find next coordinates!");
        this->printMap();
        return false;
    }
    this->costmap_.mapToWorld(i, j, x, y);
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Moving robot at (%d, %d), with coord (%f, %f).",
         i, j, x, y);
    return true;
}

/*
    Try to find and move to uknown are cell.
    New unknown cell will be added only if it is
    further than robot radius.
*/
uint8_t MapEngine::moveToNearestUnknownCell(uint32_t &i, uint32_t &j, int thrI, int thrJ) {
    if(!isWithinCostmap(i, j, thrI, thrJ))
        return 0;
    uint8_t value = this->costmap_.getCost(i, j);
    if (value < nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE) {
        i += thrI;
        j += thrJ;
        return this->moveToNearestUnknownCell(i, j, thrI, thrJ);
    } else if (value == nav2_costmap_2d::NO_INFORMATION) {
        if (!this->shouldMove(i, j)) {
            i += thrI;
            j += thrJ;
            return this->moveToNearestUnknownCell(i, j, thrI, thrJ);
        }
    }

    return value;
}

void MapEngine::resetVisitedMap() {
    uint64_t size = this->visitedMap_.size();
    this->visitedMap_.clear();
    this->visitedMap_.resize(size, false);
}

bool MapEngine::shouldReset() {
    if (this->resetDone_) {
        this->resetDone_ = false;
        return true;
    }

    return false;
}

/*
    Check if robot should move to target cell.
    If target cell is too close (less than robot size),
    then the move should not happen.
*/
bool MapEngine::shouldMove(uint32_t targetI, uint32_t targetJ) {
    // Avoiding integer overflow/underflow
    uint32_t iDiff = std::max(targetI, this->robotIMapIndex_) - std::min(targetI, this->robotIMapIndex_);
    uint32_t jDiff = std::max(targetJ, this->robotJMapIndex_) - std::min(targetJ, this->robotJMapIndex_);
    if (iDiff <= this->coordOffset_ && jDiff <= this->coordOffset_)
        return false;

    return true;
}

void MapEngine::moveToFarestFreeCell(uint32_t &i, uint32_t &j, int thrI, int thrJ) {
    if (this->isWithinCostmap(i, j, thrI, thrJ)) {
        if (this->costmap_.getCost(i, j) >= nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE)
            return;
        i += thrI;
        j += thrJ;
        this->moveToFarestFreeCell(i, j, thrI, thrJ);
    }
}

/*
    If cell is within the costmap size.
*/
bool MapEngine::isWithinCostmap(uint32_t i, uint32_t j, int thrI, int thrJ) {
    if (i <= (this->costmap_.getSizeInCellsX() - abs(thrI)) && j <= (this->costmap_.getSizeInCellsY() - abs(thrJ)) && i>=abs(thrI) && j>=abs(thrJ))
        return true;

    return false;
}
