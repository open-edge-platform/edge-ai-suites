/******************************************************************************\
Copyright (C) 2019-2021 Intel Corporation.


This software and the related documents are Intel copyrighted materials,
and your use of them is governed by the express license under which they
were provided to you (normally a Nondisclosure Agreement). Unless the
License provides, otherwise, you may not use, modify, copy, publish,
distribute, disclose or transmit this software or the related documents
without Intel's prior written permission.


This software and the related documents are provided as is, with no
express or implied warranties, other than those that are expressly
stated in the License.
\**********************************************************************************/

#include "config_parser.h"

#include <iostream>
#include <sstream>
#include <string.h>

using namespace SVET_APP;
//show the parsed parameter
void print_para(ConfigParser &parser)
{
	using CLI::enums::operator<<;
        while(!parser.mResults.empty())
        {
             auto opcmd = parser.mResults.front();
             parser.printCmdInfo(opcmd);
             parser.mResults.pop();
        }
}


int main(int argc, char **argv) {
    try {
        ConfigParser parser(argv[0]);
        parser.parse(argc, argv);
        print_para(parser);
        while(1) 
        {
            parser.parseInput();
            print_para(parser);
        }
    } catch (...) {
        std::cerr<<"An unknown exception happened"<<std::endl;
    }
    return 0;
}
