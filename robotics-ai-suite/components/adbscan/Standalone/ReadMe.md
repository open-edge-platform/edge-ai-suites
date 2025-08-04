This directory contains the source code, executables, input directory and files, and output directory for standalone ADBScan code.
1. If a change is made to the source code, use make to invoke Makefile to rebuild the app;
2. To run the core ADBScan algorithm, use the following shell script: ./run_ADBScan.sh, where input/output files are specified:
      ./doDBScan input_file output_file
   e.g.,
      ./doDBScan ./input/0000000080.bin ./output/output_cpu.txt
3. To create cluster hierachy and bounding boxes from the output_cpu.txt file, run Util in this format:
      ./Util.exe ./input.txt
4. To validate the output clusters, use the visualization plot_clusters.py in /validation direction
