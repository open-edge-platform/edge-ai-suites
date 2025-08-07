#include "bitstream_file_reader.h"

#include <iostream>
#include <thread>         // std::this_thread::sleep_for
#include <chrono>         // std::chrono::seconds

void testFileReader(const char* filename)
{
    BitstreamReader *reader = new BitstreamFileReader;
    if (reader->Open(filename) != 0)
    {
        std::cout << "Open " << filename << "Failed!\n";	
        reader->Close();
        delete reader;
	return;
    }

    FILE *out = fopen("fileout", "wb");
    char buff[1024];

    do
    {
        int retBytes = reader->Read(buff, 1024);
        if(retBytes > 0) 
	{
            fwrite(buff, 1, retBytes, out);
	}
	else 
	{
            break;
	}
    } while(1);

    fclose(out);
    reader->Close();
    delete reader;
}


int main(int argc,char*argv[])
{
    if (argc != 2) 
    {
        std::cout << "Usage: ./BitstreamFileReaderTest filename" << std::endl;
        return -1;
    }
    testFileReader(argv[1]);

    return 0;
}
