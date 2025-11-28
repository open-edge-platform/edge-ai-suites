/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023-2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <chrono>
#include <mutex>
#include <vector>
#include <string.h>
#include <opencv2/opencv.hpp>
#include <opencv2/imgproc.hpp>
#include <iostream>
#include <opencv2/core.hpp>
#include <opencv2/videoio.hpp>
#include <opencv2/highgui.hpp>
#include "modules/visualization/Plot.h"

#define DISPLAY_WIDTH 640
#define DISPLAY_HEIGHT 480
#define MAX_MESSAGE_BUFFER_SIZE 10000
#define MAX_INPUTS 16


typedef struct DisplayParams_t {
    std::string name;                       // display title
    cv::Size windowSize;                    // overall display window size
    cv::Size oriSize;                       // original frame size
    cv::Size frameSize;                     // pannel size
    cv::Size fusionSize;
    cv::Size mediaFusionSize;
    size_t count;                           // pannels number
    cv::Point points[MAX_INPUTS];           // left-top coordinate
} DisplayParams_t;

typedef struct MessageBuffer_t {
    std::string buffer[MAX_MESSAGE_BUFFER_SIZE];
    size_t read_pos;
    size_t write_pos;
    std::mutex mtx;
    bool is_end;

    std::condition_variable not_full;
    std::condition_variable not_empty;
} MessageBuffer_t;

/**
 * @brief init message buffer
 */
void initMessageBuffer(MessageBuffer_t* b)
{
    b->write_pos = 0;
    b->read_pos = 0;
    b->is_end = false;
}
//RGB-->BGR
static Scalar TXT_COLOR = { 181,104,0 };
static Scalar V_COLOR = { 0,255,0 };
static Scalar N_COLOR = { 247,63,234 };
static Scalar P_COLOR = { 255,0,0 };
static Scalar BG_COLOR = { 250,250,250 };
static Scalar RED_COLOR = { 0,0,250 };
void MyText(cv::Mat frame, string text, Point start, cv::Scalar rgb)
{
    int LineW = 1;
    cv::rectangle(frame,
        cv::Point(start.x-2,start.y+2),
        // Point(start.x+18*LineW*text.length(),start.y-25*LineW),
        cv::Point(start.x + 9*text.length(), start.y-15),
        BG_COLOR,
        FILLED,
        LINE_8);

    cv::putText(frame,
        text,
        start,
        FONT_HERSHEY_SIMPLEX,
        0.5,
        rgb,
        1.5,
        LINE_8);
}

enum FusionType_t {
    FUSION_1C1R,
    FUSION_2C1R,
    FUSION_4C4R,
    FUSION_16C4R,
};

/**
 * @brief split display windows
 * @param count display count
 * @return DisplayParams_t
 */
DisplayParams_t prepareDisplayParams(FusionType_t fusionType, size_t count, std::string name, Plot& pl) {
    DisplayParams_t params;
    params.name = name;
    params.count = count;
    // params.windowSize = cv::Size(DISPLAY_WIDTH, DISPLAY_HEIGHT);

    size_t gridCount = static_cast<size_t>(ceil(sqrt(count)));
    size_t gridStepX = static_cast<size_t>(DISPLAY_WIDTH / gridCount);
    size_t gridStepY = static_cast<size_t>(DISPLAY_HEIGHT / gridCount);
    if (gridStepX == 0 || gridStepY == 0) {
        throw std::logic_error("Can't display every input: there are too many of them");
    }
    params.oriSize = cv::Size(gridStepX, gridStepY);

    cv::Mat plot = pl.getPlotImage();
    params.fusionSize = plot.size();

    // cv::Mat frameData = windowImage;
    // resize(frameData, frameData,
    //        Size(plot.rows * frameData.cols / frameData.rows, plot.rows));
    // cv::Mat radarSight_map;
    // cv::hconcat(frameData, plot, radarSight_map);
    // params.mediaFusionSize = radarSight_map.size();
    // cv::Mat mediaFusionImage = cv::Mat::zeros(params.mediaFusionSize, CV_8UC3);
    size_t frameResizeY;
    if (fusionType == FUSION_16C4R) {
        frameResizeY = plot.rows / 2;
    } else {
        frameResizeY = plot.rows;
    }
    size_t frameResizeX = gridStepX * frameResizeY/gridStepY;
    size_t mediaFusionX = plot.cols + frameResizeX;
    size_t mediaFusionY = plot.rows;
    params.frameSize = cv::Size(frameResizeX, frameResizeY);

    if (fusionType == FUSION_4C4R) {
        params.windowSize = cv::Size((frameResizeX + plot.cols) * 2, mediaFusionY * 2);       // 1932 1000
        params.mediaFusionSize = cv::Size((frameResizeX + plot.cols) * 2, mediaFusionY * 2);  // 1932 1000
        plot.rows += plot.rows;
        plot.cols += plot.cols;
    } else if (fusionType == FUSION_1C1R) {
            params.windowSize = cv::Size(frameResizeX + plot.cols, mediaFusionY);       // 1266 500
            params.mediaFusionSize = cv::Size(frameResizeX + plot.cols, mediaFusionY);  // 1266 500
    } else if (fusionType == FUSION_2C1R) {
            params.windowSize = cv::Size(frameResizeX * 2 + plot.cols, mediaFusionY);       // 1932 500
            params.mediaFusionSize = cv::Size(frameResizeX * 2 + plot.cols, mediaFusionY);  // 1932 500
    } else if (fusionType == FUSION_16C4R) {
        params.windowSize = cv::Size(frameResizeX * 4 + plot.cols * 2, mediaFusionY * 2);       // 3864 2000
        params.mediaFusionSize = cv::Size(frameResizeX * 4 + plot.cols * 2, mediaFusionY * 2);  // 3864 2000
        plot.rows += plot.rows;
        plot.cols += plot.cols;
    }
    else
        throw std::logic_error("Invalid display type");
  
    for (size_t i = 0; i < count; i++) {
        cv::Point p;
        p.x = frameResizeX * (i / gridCount);
        p.y = frameResizeY * (i % gridCount);
        params.points[i] = p;
    }

    return params;
}

