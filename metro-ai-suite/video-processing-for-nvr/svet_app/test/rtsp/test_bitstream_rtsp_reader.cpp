#include "bitstream_file_reader.h"
#include "bitstream_rtsp_reader.h"

#include <iostream>
#include <thread>         // std::this_thread::sleep_for
#include <chrono>         // std::chrono::seconds
#include <vector>

using namespace std;

void testRTSPReader(const char* url, bool dumptofile, int clientid)
{
    BitstreamReader *reader = new BitstreamRTSPReader;

  
    while (reader->Open(url) != 0) 
    {
        std::cout << "Open " << url << " Failed!\n";	
    }

    FILE *out = nullptr;
    if (dumptofile) {
        string dumpname("/tmp/rtspout");
        dumpname += std::to_string(clientid);
        out = fopen(dumpname.c_str(), "wb+");
        if (!out) {
            std::cout<<"Open output file failed"<<std::endl;
            reader->Close();
            delete reader;
            return;
        }
    }
    

    char buff[1024*1024+4];
    do
    {
        int retBytes = reader->Read(buff, 1024*1024+4);
        if(retBytes >= 0 && out)
        {
            fwrite(buff, 1, retBytes, out);
            fflush(out);
        } 
        else if(retBytes < 0)
        {
            break; 
        }
    }while(1);

    if (out)
        fclose(out);
    reader->Close();
    delete reader;
}


int main(int argc,char*argv[])
{
    if (argc < 1) 
    {
        std::cout << "Usage: ./BitstreamFileReaderTest client_number uri_addr1 uri_addr2 uri_addr3 ..." << std::endl;
        return -1;
    }

    int clientNum = atoi(argv[1]);

    if (clientNum < 1) {
        std::cout << "the client_number must be bigger than 1"<< std::endl;
        return -1;
    }

    if (clientNum  > (argc - 2) * 4) {
        std::cout << "Please provide " << (clientNum + 3) / 4 << "url number at least" << std::endl;
        return -1;
    }

    vector<thread *> clients;
    for (int i = 0; i < clientNum; i++) {
        unsigned int urlIdx = i / 4;
        cout << "create thread " << i << " with url "<<argv[2 + urlIdx]<<endl;
        thread *p = new thread(testRTSPReader, argv[2 + urlIdx], true, i);
        std::this_thread::sleep_for(std::chrono::seconds(1));
        clients.push_back(p);
    }

    //std::this_thread::sleep_for(std::chrono::seconds(10));
    for (auto &c : clients) {
        c->join();
    }

    
    for (auto &c : clients) {
        delete c;
        c = nullptr;
    }

    return 0;
}
