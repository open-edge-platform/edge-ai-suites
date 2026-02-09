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

using CLI::enums::operator<<;
using namespace SVET_APP;

/**
 * Configuration Parser constructor.
 *
 * @param description: The description of this application.
 * @return None.
 */
ConfigParser::ConfigParser(char *description) : mDescription(description)
{
    initialize();
}

/**
 * Configuration Parser deconstructor.
 */
ConfigParser::~ConfigParser(void)
{
    if(mpApp)
    {
        delete mpApp;
        mpApp = nullptr;
    }
}

/**
 * Initilize CLI::App class and add all options or subcommands for it.
 *
 * @param  None.
 * @return None.
 */
void ConfigParser::initialize(void)
{
    mpApp = new CLI::App("SVET 2.0 Beta");

    mpApp->require_subcommand(1);

    //quit command
    auto quit = mpApp->add_subcommand("quit", "terminate this demo");
    quit->callback([&]() { exit(0);});

    //load command
    auto load = mpApp->add_subcommand("load", "Load Config file");
    load->add_option("-f,--file,file", mConfigFile, "Config File Name")
        ->check(CLI::ExistingFile);

    load->callback([&]() {   std::cout << "loading config file:"
			     << mConfigFile << std::endl;
                             parse(mConfigFile.c_str());});

    //ctrl operator
    auto ctrl_subcommand = mpApp->add_subcommand("ctrl",
		                "Control the pipeline work status");

    std::map<std::string, CtrlCMD> ctrl_cmd_map {{"run", CtrlCMD::Run},
                                                 {"stop", CtrlCMD::Stop},
                                                 {"noop", CtrlCMD::Noop},
                                                 {"update", CtrlCMD::Update},
                                                 {"listDisplay", CtrlCMD::ShowDisplay}};

    ctrl_subcommand->add_option("-c,--cmd", mCtrlPara.cmd ,
		    "Switch pipeline status, available is run stop noop update info")
                   ->required()
                   ->transform(CLI::CheckedTransformer(ctrl_cmd_map, CLI::ignore_case));
    ctrl_subcommand->add_option("-t,--time", mCtrlPara.time,
		    "time (ms) for ctrl cmd take effect")->required();
    ctrl_subcommand->add_option("-l,--vl", mCtrlPara.videoLayerId,
		    "video layer id for the display streams in curretn command group");

    ctrl_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::Ctrl));

    //newvl
    auto newvideolayer_subcommand = mpApp->add_subcommand("newvl", "create a new video layer for output");
    newvideolayer_subcommand->add_option("-i,--id", mNewVOPara.id,
                                         "The ID of new created video layer. It must be unique.")->required();
    newvideolayer_subcommand->add_option("-W,--resW", mNewVOPara.resW, "width")->required();
    newvideolayer_subcommand->add_option("-H,--resH", mNewVOPara.resH, "hight")->required();
    newvideolayer_subcommand->add_option("-r,--refresh", mNewVOPara.refresh, "display refresh rate");
    newvideolayer_subcommand->add_option("-p,--fps", mNewVOPara.fps, "video layer compositon fps");
    newvideolayer_subcommand->add_option("-d,--dispid", mNewVOPara.dispid, "display device ID");
    newvideolayer_subcommand->add_option("--tilenum", mNewVOPara.tilenum, "number of tiles");
    //newvideolayer_subcommand->add_option("-l,--layer", mNewVOPara.layer,"layer number");

    std::map<std::string, uint32_t> fourcc_format_map{{"NV12", int(VideoFrameType::FOURCC_NV12)},
                                                      {"RGB4", int(VideoFrameType::FOURCC_RGB4)},
                                                      {"YUY2", int(VideoFrameType::FOURCC_YUY2)}};

    newvideolayer_subcommand->add_option("-f,--format", mNewVOPara.format,
                                         "Video FOURCC Format, NV12/YUY2/AYUV/P010/Y210/Y410/P016/Y216/Y416")
                    ->transform(CLI::CheckedTransformer(fourcc_format_map, CLI::ignore_case));

    newvideolayer_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::NewVideoLayer));

    //dispch
    auto dispch_subcommand = mpApp->add_subcommand("dispch", "set display channel");
    dispch_subcommand->add_option("-i,--id", mDpyChPara.id,"channel ID")->required();
    dispch_subcommand->add_option("-W", mDpyChPara.w,"Width")->required();
    dispch_subcommand->add_option("-H", mDpyChPara.h,"Hight")->required();
    dispch_subcommand->add_option("-x", mDpyChPara.x,"X Position on display");
    dispch_subcommand->add_option("-y", mDpyChPara.y,"Y Position on display");
    dispch_subcommand->add_option("-v,--videolayer", mDpyChPara.videoLayer, "video output device");
    dispch_subcommand->add_option("--tileid", mDpyChPara.tileid, "tile id for tile composition");

    dispch_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::DispCH));

    //newdec
    auto newdec_subcommand = mpApp->add_subcommand("newdec", "new decoder");
    newdec_subcommand->add_option("-i,--id", mNewDecPara.id,"decode channel ID")->required();
    newdec_subcommand->add_option("-I,--input", mNewDecPara.input,"input video file")->required();
    newdec_subcommand->add_option("-d,--dump", mNewDecPara.dump,"dump file name");
    newdec_subcommand->add_option("-l,--loop", mNewDecPara.loopInput,"1: enable loop input.");
    newdec_subcommand->add_option("-c,--codec", mNewDecPara.codec,"Codec name, h264/h265/jpeg");
    newdec_subcommand->add_option("-W,--decW", mNewDecPara.decW,"decode output width");
    newdec_subcommand->add_option("-H,--decH", mNewDecPara.decH,"decode output height");
    newdec_subcommand->add_option("-r,--rotate", mNewDecPara.rotate,"rotation degrees");
    newdec_subcommand->add_option("-s,--sink", mNewDecPara.sink,"specify the display channel");
    newdec_subcommand->add_option("--sfc", mNewDecPara.sfcEnable,"1: enable sfc 0: disable sfc");
    newdec_subcommand->add_option("-f,--format", mNewDecPara.decFormat,
                      "Video FOURCC Format, NV12/YUY2/AYUV/P010/Y210/Y410/P016/Y216/Y416")
                     ->transform(CLI::CheckedTransformer(fourcc_format_map, CLI::ignore_case));

    std::map<std::string, DecMode> dec_mod_map {{"playback", DecMode::Playback},
                                                {"preview",  DecMode::Preview }};

    newdec_subcommand->add_option("-m,--mode", mNewDecPara.mode ,
                    "decode channel mode: playback/preview")
                   ->transform(CLI::CheckedTransformer(dec_mod_map, CLI::ignore_case));

    newdec_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::NewDec));

    //decctrl
    auto decctrl_subcommand = mpApp->add_subcommand("decctrl", "decoder control");
    decctrl_subcommand->add_option("-i,--id", mDecCtrlPara.decid,"decode channel ID")->required();

    decctrl_subcommand->add_option("-W,--width", mDecCtrlPara.w,"user pic width");
    decctrl_subcommand->add_option("-H,--height", mDecCtrlPara.h,"user pic height");

    std::map<std::string, DecCtrlCMD> dec_ctrl_cmd_map {{"remove", DecCtrlCMD::Remove},
                                                    {"addpic", DecCtrlCMD::AddPic},
                                                    {"delpic", DecCtrlCMD::RemovePic}};
    decctrl_subcommand->add_option("-p,--pic", mDecCtrlPara.picFilename,"user picture filename");

    decctrl_subcommand->add_option("-c,--cmd", mDecCtrlPara.cmd ,
                      "decode control command: remove/addpic/delpic")
	              ->required()
                      ->transform(CLI::CheckedTransformer(dec_ctrl_cmd_map, CLI::ignore_case));

    decctrl_subcommand->add_option("-I,--instant", mDecCtrlPara.instant,
                                   "user picture enable instant flag ");


    decctrl_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::DecCtrl));

    //dispchctrl
    auto dispchctrl_subcommand = mpApp->add_subcommand("dispchctrl", "display channel control");
    dispchctrl_subcommand->add_option("-i,--id", mDispChCtrlPara.id,"display channel ID")->required();
    dispchctrl_subcommand->add_option("-v,--void", mDispChCtrlPara.videoLayer, "video output ID")->required();
    dispchctrl_subcommand->add_option("--osdid", mDispChCtrlPara.osdid,"OSD ID");

    dispchctrl_subcommand->add_option("-x", mDispChCtrlPara.x, "Position for Zoom In area");
    dispchctrl_subcommand->add_option("-y", mDispChCtrlPara.y, "Position for Zoom In area");
    dispchctrl_subcommand->add_option("-W", mDispChCtrlPara.w, "Region size for Zoom In area");
    dispchctrl_subcommand->add_option("-H", mDispChCtrlPara.h, "Region size Zoom In area");

    std::map<std::string, DispChCtrlCMD> dispch_ctrl_cmd_map {{"pause",  DispChCtrlCMD::Pause},
                                                        {"resume", DispChCtrlCMD::Resume},
                                                        {"hide",   DispChCtrlCMD::Hide},
                                                        {"show",   DispChCtrlCMD::Show},
                                                        {"zoomin", DispChCtrlCMD::ZoomIn},
                                                        {"zoomout", DispChCtrlCMD::ZoomOut},
                                                        {"addosd", DispChCtrlCMD::AddOsd},
                                                        {"delosd", DispChCtrlCMD::DelOsd}};

    dispchctrl_subcommand->add_option("-c,--cmd", mDispChCtrlPara.cmd ,
                                   "display channel control command: pause/resume/hide/show/zoomin/zoomout")
            ->required()
            ->transform(CLI::CheckedTransformer(dispch_ctrl_cmd_map, CLI::ignore_case));

    dispchctrl_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::DispChCtrl));

    //newpp
    auto newpp_subcommand = mpApp->add_subcommand("newpp", "create post process node");
    newpp_subcommand->add_option("-i,--id", mPPPara.id,"pp id")->required();
    newpp_subcommand->add_option("-s,--sink", mPPOutputPara.sink,"output sink")->required();
    newpp_subcommand->add_option("-W,--width", mPPOutputPara.w,"width");
    newpp_subcommand->add_option("-H,--height", mPPOutputPara.h,"height");
    newpp_subcommand->add_option("-F,--format", mPPOutputPara.format,
                "Video FOURCC Format, NV12/YUY2/AYUV/P010/Y210/Y410/P016/Y216/Y416")
              ->transform(CLI::CheckedTransformer(fourcc_format_map, CLI::ignore_case));
    newpp_subcommand->add_option("-r,--rotation", mPPOutputPara.rotation,"rotation");
    newpp_subcommand->add_option("-f,--framerate", mPPOutputPara.framerate,"framerate");
    newpp_subcommand->add_option("--cropW", mPPOutputPara.cropW,"cropW");
    newpp_subcommand->add_option("--cropH", mPPOutputPara.cropH,"cropH");
    newpp_subcommand->add_option("--cropX", mPPOutputPara.cropX,"cropX");
    newpp_subcommand->add_option("--cropY", mPPOutputPara.cropY,"cropY");
    newpp_subcommand->add_option("-d,--denoise", mPPOutputPara.denoise,"denoise");
    newpp_subcommand->parse_complete_callback([&]() {
                      auto ouput_para_ptr (std::make_shared<PostProcessOutputPara>(mPPOutputPara));
	              mPPPara.OutputParas.push_back(ouput_para_ptr);
                  ConfigParser::storeResult(OpType::NewVpp);
                  });

    //osdctrl
    auto osdctrl_subcommand = mpApp->add_subcommand("osdctrl", "OSD control");
    osdctrl_subcommand->add_option("-i,--id", mOsdCtrlPara.id,"Specify the OSD ID to add")->required();

    std::map<std::string, OSDCtrlCMD> osd_ctrl_cmd_map {{"add", OSDCtrlCMD::Add},
                                                        {"remove", OSDCtrlCMD::Remove},
                                                        {"setattrs", OSDCtrlCMD::SetAttrs}};

    osdctrl_subcommand->add_option("-c,--cmd", mOsdCtrlPara.cmd ,
                        "OSD control command: add/remove/setattrs")
                      ->required()
                      ->transform(CLI::CheckedTransformer(osd_ctrl_cmd_map, CLI::ignore_case));

    osdctrl_subcommand->add_option("-d,--dispch", mOsdCtrlPara.dispch,"attach to a specific display channel id");
    osdctrl_subcommand->add_option("-v,--videolayer", mOsdCtrlPara.videoLayer,"attach to a specific videolayer id ");
    osdctrl_subcommand->add_option("--ppstream", mOsdCtrlPara.ppstream,"attach to a specific pp stream id");
    osdctrl_subcommand->add_option("-W,--width", mOsdCtrlPara.width,"width");
    osdctrl_subcommand->add_option("-H,--height", mOsdCtrlPara.height,"height");
    osdctrl_subcommand->add_option("-g,--gridSize", mOsdCtrlPara.gridSize,"gridSize");
    osdctrl_subcommand->add_option("-x", mOsdCtrlPara.x,"Center x position");
    osdctrl_subcommand->add_option("-y", mOsdCtrlPara.y,"Center y position");

    osdctrl_subcommand->callback(std::bind(&ConfigParser::storeResult, this, OpType::OsdCtrl));
}

/**
 * store the parse result for operate command
 *
 * @param operate  operate type
 * @return None
 */
void ConfigParser::storeResult(OpType operate)
{
    auto opcmd = std::make_shared<OperateCmd>();
    opcmd->type = operate;
    switch(operate)
    {
    case OpType::OsdCtrl:
        opcmd->para = std::make_shared<OSDCtrlPara>(mOsdCtrlPara);
        break;
    case OpType::NewVpp:
        opcmd->para = std::make_shared<PostProcessPara>(mPPPara);
        mPPPara.OutputParas.clear();
        break;
    case OpType::DecCtrl:
        opcmd->para = std::make_shared<DecCtrlPara>(mDecCtrlPara);
        break;
    case OpType::DispChCtrl:
        opcmd->para = std::make_shared<DispChCtrlPara>(mDispChCtrlPara);
        break;
    case OpType::NewDec:
        opcmd->para = std::make_shared<NewDecPara>(mNewDecPara);
        break;
    case OpType::DispCH:
        opcmd->para = std::make_shared<DispStreamPara>(mDpyChPara);
        break;
    case OpType::NewVideoLayer:
        opcmd->para = std::make_shared<NewVideoLayerPara>(mNewVOPara);
        break;
    case OpType::Ctrl:
        opcmd->para = std::make_shared<CtrlPara>(mCtrlPara);
        break;
    default:
        break;
    }
    mResults.push(opcmd);
}

/**
 * Parse command line arguments.
 *
 * @param argc: The count of arguments.
 * @param argv: The string array of arguments.
 * @return 0 or error code.
 */
int ConfigParser::parse(int argc, char** argv)
{
    CLI11_PARSE(*mpApp, argc, argv);

    return 0;
}

/**
 * Parse one line from configuration file.
 *
 * @param line: one line string.
 * @return 0 or error code.
 */
int ConfigParser::parseOneLine(const std::string &line)
{
    int file_argc = 0;
    char *file_argv[1024];

    file_argv[file_argc++] = mDescription;

    std::istringstream iss(line);
    //strs only just for auto decontruct substr after parse
    std::vector<std::shared_ptr<std::string>> strs;

    while(iss.good())
    {
        std::string *substr = new std::string("");
        iss >> *substr;
        file_argv[file_argc++] = const_cast<char *>(substr->c_str());
        strs.push_back(std::shared_ptr<std::string>(substr));
    }

    return parse(file_argc, file_argv);
}

/**
 * Parse configuration file.
 *
 * @param filename: file name.
 * @return 0 or error code.
 */
int ConfigParser::parse(const char *filename)
{
    std::ifstream ifs;

    try
    {
        ifs.open (filename, std::ifstream::in);
    }
    catch (std::ios_base::failure& e)
    {
        std::cerr << e.what() << '\n';
        return -1;
    }

    while (ifs.good())
    {
        std::string line;

        std::getline(ifs, line, '\n');
        if (line.size() == 0)
        {
            continue;
        }
        if (parseOneLine(line) < 0) 
        {
            //std::cout << "parse error for line: " << line << std::endl;
            break;
        }
    }

    ifs.close();

    return 0;
}

/**
 * Get user input and parse, should be called repeatly.
 *
 * @param None.
 * @return None.
 */
void ConfigParser::parseInput(void)  //thread
{
    std::string line;

    std::cout << "(svet)>> ";
    std::getline(std::cin, line, '\n');
    if (line.size() == 0)
    {
        return;
    }
    parseOneLine(line);
}

void ConfigParser::printCmdInfo(std::shared_ptr<OperateCmd> opcmd) {

    OpType type = opcmd->type ;
    switch(type)
    {
        case OpType::Ctrl:
        {
            CtrlPara *para = reinterpret_cast<CtrlPara *>(opcmd->para.get());
            std::cout << "OpType::Ctrl: "
                      << "cmd=" << para->cmd
                      << " time=" << para->time
                      << " targer video layer id = " << para->videoLayerId
                      << std::endl;
        }
            break;
        case OpType::NewVideoLayer:
        {
            NewVideoLayerPara *para = reinterpret_cast<NewVideoLayerPara *>(opcmd->para.get());
            std::cout << "OpType::NewVideoLayer: \n";
            std::cout << "ID: " << para->id << std::endl;
            std::cout << "resW: " << para->resW << std::endl;
            std::cout << "resH: " << para->resH << std::endl;
            std::cout << "refresh: " << para->refresh << std::endl;
            std::cout << "dispid: " << para->dispid << std::endl;
            //std::cout << "layer: " << para->layer << std::endl;
            std::cout << "format " << FormatToString(para->format) << std::endl;
        }
            break;
        case OpType::DispCH:
        {
            DispStreamPara *para = reinterpret_cast<DispStreamPara *>(opcmd->para.get());
            std::cout << "OpType::DispPara: " << std::endl;
            std::cout << "id: " << para->id << std::endl;
            std::cout << "w: " << para->w << std::endl;
            std::cout << "h: " << para->h << std::endl;
            std::cout << "x: " << para->x << std::endl;
            std::cout << "y: " << para->y << std::endl;
            std::cout << "videoLayer: " << para->videoLayer << std::endl;
        }
            break;
        case OpType::NewDec:
        {
            NewDecPara *para = reinterpret_cast<NewDecPara *>(opcmd->para.get());
            std::cout << "OpType::NewDec: " << std::endl;
            std::cout << "id: " << para->id << std::endl;
            std::cout << "input: " << para->input << std::endl;
            std::cout << "dump: " << para->dump << std::endl;
            std::cout << "codec: " << para->codec << std::endl;
            //when SFC enabled, w and h can be got from the sink,  display channel
            if (para->decW > 0 && para->decH > 0) {
                std::cout << "w: " << para->decW << std::endl;
                std::cout << "h: " << para->decH << std::endl;
            }
            std::cout << "sfc: " << para->sfcEnable << std::endl;
            std::cout << "format: " << FormatToString(para->decFormat) << std::endl;
            std::cout << "rotate: " << para->rotate << std::endl;
            std::cout << "sink: " << para->sink << std::endl;
            std::cout << "mode: " << para->mode << std::endl;
        }
            break;
        case OpType::DecCtrl:
        {
            DecCtrlPara *para = reinterpret_cast<DecCtrlPara *>(opcmd->para.get());
            std::cout << " OpType::DecCtrl " << std::endl;
            std::cout << "id: " << para->decid << std::endl;
            std::cout << "cmd: " << para->cmd << std::endl;

            if (para->cmd == DecCtrlCMD::AddPic) {
                    std::cout << "width: " << para->w << std::endl;
                    std::cout << "height: " << para->h << std::endl;
                    std::cout << "user picture file name: " << para->picFilename <<std::endl;
                    std::cout << "user picture instant flag: " << para->instant << std::endl;
            }
        }
            break;
        case OpType::NewVpp:
        {
            PostProcessPara *para = reinterpret_cast<PostProcessPara *>(opcmd->para.get());
            auto output = para->OutputParas;
            std::cout << " OpType::NewVpp " << std::endl;
            std::cout << "OutputParas.size= " << output.size() << std::endl;
            for(auto it = output.begin(); it != output.end(); ++it)
            {
                std::cout << "id: " << para->id << ", cropX: " << (*it)->cropX;
                std::cout << ",cropY: "<<(*it)->cropY << ",cropW: "<<(*it)->cropW<< ",cropH: "<<(*it)->cropH;
                std::cout << ", sink: " << (*it)->sink << std::endl;
            }
        }
            break;
        case OpType::OsdCtrl:
        {
            OSDCtrlPara *para = reinterpret_cast<OSDCtrlPara *>(opcmd->para.get());
            std::cout << " OpType::OsdCtrl " << std::endl;
            std::cout << "id: " << para->id << std::endl;
            std::cout << "cmd: " << para->cmd << std::endl;
            std::cout << "dispch: " << para->dispch << std::endl;
            std::cout << "videolayer: " << para->videoLayer << std::endl;
            std::cout << "ppstream: " << para->ppstream << std::endl;
            std::cout << "width: " << para->width << std::endl;
            std::cout << "height: " << para->height << std::endl;
            std::cout << "gridSize: " << para->gridSize << std::endl;
            std::cout << "x: " << para->x << std::endl;
            std::cout << "y: " << para->y << std::endl;
        }
            break;
        case OpType::DispChCtrl:
        {
            DispChCtrlPara *para = reinterpret_cast<DispChCtrlPara *>(opcmd->para.get());
            std::cout << " OpType::DispChCtrl " << std::endl;
            std::cout << "id: " << para->id << std::endl;
            std::cout << "cmd: " << para->cmd << std::endl;
        }
            break;
        default:
            std::cout << "Unknown command type :" << type;
            break;

    }
    return;
}

