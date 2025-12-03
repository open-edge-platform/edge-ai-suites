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

## Uninstall docker image
1. Run `docker rmi -f $(docker images --format "{{.Repository}}:{{.Tag}}" | grep 'vppsample')` remove all vppsample docker images

## Caution
This container image is intended for demo purposes only and not intended for production use. To receive expanded security maintenance from Canonical on the Ubuntu base layer, you may follow the [how-to guide to enable Ubuntu Pro in a Dockerfile](https://documentation.ubuntu.com/pro-client/en/docs/howtoguides/enable_in_dockerfile) which will require the image to be rebuilt.
