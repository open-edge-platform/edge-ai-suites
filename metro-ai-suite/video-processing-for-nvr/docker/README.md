# Build and run docker image

## System requirements

**Operating System:**
* Ubuntu 24.04

**Software:**
* VPP SDK

## Build docker image  
1. Build docker image for reference application `bash build_sample.sh`  
Make sure docker is corrently installed and configured. 

## Run docker container  
1. Run `sudo init 3` switch to non-GUI mode
2. Run a sample test in docker container : `bash run.sh`  

## Run docker compose
1. Run `sudo init 3` switch to non-GUI mode
2. Run `bash ./startup.sh`
