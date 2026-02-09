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
#include <iostream>
#include <sstream>
#include <string.h>
#include "CLI/CLI.hpp"

using CLI::enums::operator<<;
using namespace std;

/************************************************************************************************************************************************
./config_gen.py   -o output_config.txt  -i “display=0 row=4 column=4 w=1920 h=1080”  “display=1 row=4 column=4 w=3840 h=2160”  -f video_urls.txt

video_urls.txt is like(left to right,  up to down) :
test.h264
test.h265
null
rtsp://xx.xx.xx
null
rtsp://xx.xx.xx
**************************************************************************************************************************************************/

const int MAX_DISP_INDEX = 4;

typedef struct {
    int rowCount;
    int columnCount;
    int width;
    int height;
    string urlFileName;
    vector<shared_ptr<string>> urls;
} DisplayPara;

typedef struct {
    string outFileName;
    DisplayPara dispParas[MAX_DISP_INDEX];
} ConfigPara;

vector<shared_ptr<string>> getURLs(string fileName)
{
    ifstream ifs;

    vector<shared_ptr<string>> urls;

    try {
        ifs.open (fileName, ifstream::in);
    } catch (ios_base::failure& e) {
        cerr << e.what() << '\n';
        return urls;
    }

    while (ifs.good()) {
        auto line = make_shared<string>();

        getline(ifs, *line, '\n');
        if(!line->empty()) {
            urls.push_back(line);
        }
    }

    ifs.close();

    return urls;

}

void genConfigFile(ConfigPara &para)
{
    ofstream ofs;
    try {
        ofs.open (para.outFileName, ifstream::out);
    } catch (ios_base::failure& e) {
        cerr << e.what() << '\n';
        return;
    }
    //gen newvl
    int vlID = 0;
    int decID = 0;
    for(int i = 0; i  < MAX_DISP_INDEX; i++) {
        if(para.dispParas[i].urlFileName.empty())
            continue;
        para.dispParas[i].urls = getURLs(para.dispParas[i].urlFileName);
        ofs << "newvl -i " << vlID << " -W " <<  para.dispParas[i].width
            << "  -H " << para.dispParas[i].height << "  --refresh=30 "
            << " --format=nv12 " << " --dispid=" << i << endl;

        int dispchID = 0;
        for(int r = 0; r < para.dispParas[i].rowCount; r++) {
            for(int c = 0; c < para.dispParas[i].columnCount; c++) {
                int W = para.dispParas[i].width /  para.dispParas[i].columnCount;
                int H = para.dispParas[i].height / para.dispParas[i].rowCount;
                int x = W * c;
                int y = H * r;
                string inputName =  *para.dispParas[i].urls[(r*para.dispParas[i].columnCount+c)%para.dispParas[i].urls.size()];
                string codec("h264");
                string h265str("265");
                if (inputName.length() > h265str.length() ) {
                    if (0 == inputName.compare(inputName.length() - h265str.length(), h265str.length(), h265str)) {
                        codec = "h265";
                    }
                }
                ofs << "dispch " << " --id=" << dispchID << " -W " << W << " -H " << H
                    << " -x " << x << " -y " << y << " --videolayer=" << vlID << endl;
                ofs << "newdec" << " --id=" << decID++ << " --input=" 
                    << *para.dispParas[i].urls[(r*para.dispParas[i].columnCount+c)%para.dispParas[i].urls.size()]
                    << " --codec="<< codec << " --sink=disp" << dispchID << " -f NV12" << endl;
                dispchID++;
            }
        }
        ofs << "ctrl --cmd=run  --time=0" << endl;
        vlID++;
    }
    ofs.close();
}

int main(int argc, char **argv) {
    try {

    CLI::App app{"App description"};

    ConfigPara configPara;
    // Define options
    app.add_option("-o,--output", configPara.outFileName, "output file name")->default_val("config.txt");

    for(int i = 0; i < MAX_DISP_INDEX; i++) {
        char display_subcommand_index[32];
        snprintf(display_subcommand_index, sizeof(display_subcommand_index), "display%d", i);
        auto display = app.add_subcommand(display_subcommand_index, "add a display channel");

        display->add_option("-r, --row-count", configPara.dispParas[i].rowCount, "row count")->required();
        display->add_option("-c,--column-count", configPara.dispParas[i].columnCount, "column count")->required();
        display->add_option("-W,--width", configPara.dispParas[i].width, "display width")->required();
        display->add_option("-H,--height", configPara.dispParas[i].height, "display height")->required();
        display->add_option("-f,--file", configPara.dispParas[i].urlFileName, "url file")->required()->check(CLI::ExistingFile);
    }

    CLI11_PARSE(app, argc, argv);

    genConfigFile(configPara);
    } catch (std::runtime_error e) {
        cerr<<e.what()<<std::endl;
    }


    return 0;
}


