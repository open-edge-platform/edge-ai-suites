/*

 * INTEL CONFIDENTIAL

 *

 * Copyright (C) 2023-2024 Intel Corporation

 *

 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the

 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not

 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's

 * prior written permission.

 *

 * This software and the related documents are provided as is, with no express or implied warranties, other than those

 * that are expressly stated in the License.

 */
#pragma once
#include <iostream>
#include <cstdint>
#include <queue>
#include "CLI/CLI.hpp"
#include "svet_cmd.h"

namespace SVET_APP {
//Parse command line arguments or config file or user input
//store the parsed results 
    class ConfigParser {
    public:
        ConfigParser(char *description);

        ~ConfigParser(void);

        int parse(int argc, char **argv);

        int parse(const char *filename);

        void parseInput(void);

        void printCmdInfo(std::shared_ptr<OperateCmd> opCmd);

        ConfigParser(ConfigParser const&) = delete;
        ConfigParser& operator=(ConfigParser const&) = delete;

    public:
        std::queue<std::shared_ptr<OperateCmd>> mResults;
    private:
        void initialize(void);

        int parseOneLine(const std::string &line);

        void storeResult(OpType operate);

    private:
        char *mDescription;
        CLI::App *mpApp;

        std::string mConfigFile;

        //parameters with default value
        CtrlPara mCtrlPara;
        NewVideoLayerPara mNewVOPara;
        DispStreamPara mDpyChPara;
        NewDecPara mNewDecPara;
        DecCtrlPara mDecCtrlPara;
        DispChCtrlPara mDispChCtrlPara;
        PostProcessOutputPara mPPOutputPara;
        PostProcessPara mPPPara;
        OSDCtrlPara mOsdCtrlPara;
    };
}
