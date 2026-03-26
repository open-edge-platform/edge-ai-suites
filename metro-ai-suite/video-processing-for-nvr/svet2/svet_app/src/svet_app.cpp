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
#include "config_parser.h"

#include <iostream>
#include <sstream>
#include <string.h>
#include <chrono>
#include <thread>

#include "pipeline_manager.h"
#include "display_device.h"
#include "svet_util.h"
#include "spdlog/spdlog.h"

using std::cout;
using std::endl;
using spdlog::info;
using spdlog::debug;
using spdlog::error;

using namespace SVET_APP;
//show the parsed parameter and push to a vector
//Return  OpType::Ctrl if there is any. Otherwise returns error code;
int get_para(ConfigParser &parser, OperateCmds &cmds, CtrlPara &ctrlCmd) {
    using CLI::enums::operator<<;

    debug("---commands group begin");
    while(!parser.mResults.empty()) {
        auto opcmd = parser.mResults.front();
        OpType type = opcmd->type;
        switch (type) {
            case OpType::Ctrl: {
                CtrlPara *para = reinterpret_cast<CtrlPara *>(opcmd->para.get());
                parser.printCmdInfo(opcmd);

                if (para->cmd == CtrlCMD::ShowDisplay) {
                    DisplayDevice::ShowDisplayDevices();
                }

                parser.mResults.pop(); //No need to pass command "Ctrl" to pipeline manager. It's handled in application.
                cout<<"--commands group end"<<endl;
                ctrlCmd = *para;
                return 0;
            }

            case OpType::NewVideoLayer:
            case OpType::DispCH:
            case OpType::DispChCtrl:
            case OpType::NewDec:
            case OpType::DecCtrl:
            case OpType::NewVpp:
            case OpType::OsdCtrl:
            {
                parser.printCmdInfo(opcmd);
                cmds.push_back(opcmd);
            }
                break;
            default:
                parser.printCmdInfo(opcmd);
                break;
        }
        parser.mResults.pop();
    }
    debug("Wait for Ctrl command");
    return SVET_ERR_INVALID_PARA;
}

bool process_one_group_cmds(PipelineManager &pm, OperateCmds &cmds, CtrlPara &ctrlCmd) {
    if (cmds.size() > 0) {
        pm.processCmds(cmds, ctrlCmd);
        cmds.clear();
    }

    if (ctrlCmd.time > 0) {
        info("Sleep for {} ms", ctrlCmd.time);
        std::this_thread::sleep_for(std::chrono::milliseconds(ctrlCmd.time));
    }
    if (ctrlCmd.cmd == CtrlCMD::Stop) {
        info("SVET app: Will stop the pipeline");
        return true;
    }
    return false;
}

int main(int argc, char **argv) {
    try {
        ConfigParser parser(argv[0]);
        PipelineManager pm;
        OperateCmds cmds;
        CtrlPara ctrlCmd;
        int res = 0;

        spdlog::set_level(spdlog::level::err);

        parser.parse(argc, argv);
        while (parser.mResults.size() > 0 && res >= 0) {
            res = get_para(parser, cmds, ctrlCmd);
            if (res >= 0) {
                int isStop = process_one_group_cmds(pm, cmds, ctrlCmd);
                if (isStop) {
                    pm.stopLoop();
                    return 0;
                }
            }
        }

        while(1) 
        {
            parser.parseInput();
            res = get_para(parser, cmds, ctrlCmd);
            if (res >= 0) {
                int isStop = process_one_group_cmds(pm, cmds, ctrlCmd);
                if (isStop) {
                    pm.stopLoop();
                    return 0;
                }
            }
        }
    } catch (...) {
        std::cerr<<"SVET app: unknown exception"<<std::endl;
    }

    return 0;
}
