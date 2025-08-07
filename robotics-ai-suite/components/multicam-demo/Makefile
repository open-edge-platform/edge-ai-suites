# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#----------------------------------------------------------------------------------------------------------------------
# Flags
#----------------------------------------------------------------------------------------------------------------------
SHELL:=/bin/bash
CURRENT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


#----------------------------------------------------------------------------------------------------------------------
# Docker Settings
#----------------------------------------------------------------------------------------------------------------------
DOCKER_IMAGE_NAME=realsense-d457-ai-demo
export DOCKER_BUILDKIT=1


DOCKER_RUN_PARAMS= \
	-it --rm -a stdout -a stderr -e DISPLAY=${DISPLAY} -e NO_AT_BRIDGE=1  \
	--privileged -v /dev:/dev \
	-e DPNP_RAISE_EXCEPION_ON_NUMPY_FALLBACK=0 \
	--cap-add=SYS_ADMIN --cap-add=SYS_PTRACE \
        -v ${CURRENT_DIR}/src:/workspace/src \
        -v ${CURRENT_DIR}/scripts:/workspace/scripts \
        -v ${CURRENT_DIR}/config:/workspace/config \
	-v ${CURRENT_DIR}/models:/workspace/models \
	-v ${CURRENT_DIR}/videos:/workspace/videos \
	-v /tmp/.X11-unix:/tmp/.X11-unix  -v ${HOME}/.Xauthority:/home/root/.Xauthority \
	${DOCKER_IMAGE_NAME}
	
#----------------------------------------------------------------------------------------------------------------------
# Targets
#----------------------------------------------------------------------------------------------------------------------
default: demo
.PHONY:  models

build:
	@$(call msg, Building Docker image ${DOCKER_IMAGE_NAME} ...)
	@docker build --rm . -t ${DOCKER_IMAGE_NAME}

yolov8_models: build
	@$(call msg, Preparing the yolov8 models ...)
	@docker run ${DOCKER_RUN_PARAMS} bash -c ' \
		source /opt/intel/oneapi/setvars.sh && source /opt/intel/openvino/setupvars.sh  && \
		/workspace/scripts/yolov8_model_prepare.sh yolov8n yolov8s yolov8m yolov8n-seg yolov8s-seg yolov8m-seg \
		'

mobilenet_models: build
	@$(call msg, Preparing the mobilenet models ...)
	@docker run ${DOCKER_RUN_PARAMS} bash -c ' \
		source /opt/intel/oneapi/setvars.sh  && source /opt/intel/openvino/setupvars.sh  && \
		rm -rf ./models/mobilenet-ssd && \
			omz_downloader --name mobilenet-ssd && omz_converter --name mobilenet-ssd && \
			mv ./public/mobilenet-ssd ./models && rm -rf ./public\
		'

models:  yolov8_models mobilenet_models

demo:
	@$(call msg, Running the RealSense AI Demo ...)
	@xhost +
	@docker run ${DOCKER_RUN_PARAMS} \
		bash -c 'cd src && source /opt/intel/oneapi/setvars.sh && source /opt/intel/openvino/setupvars.sh &> /dev/null && \
				  python3 pyrealsense2_ai_demo_launcher.py --config=../config/config.js'

bash: build
	@xhost +
	@docker run ${DOCKER_RUN_PARAMS} bash

clean:
	@$(call msg, Running the Docker rmi command to remove ${DOCKER_IMAGE_NAME} docker image...)
	@docker rmi ${DOCKER_IMAGE_NAME} 2> /dev/null || (echo "No such image: ${DOCKER_IMAGE_NAME}, exiting make clean command"; exit 1)
	echo "${DOCKER_IMAGE_NAME} deleted"

#----------------------------------------------------------------------------------------------------------------------
# helper functions
#----------------------------------------------------------------------------------------------------------------------
define msg
	tput setaf 2 && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo  "" && \
	echo "         "$1 && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo "" && \
	tput sgr0
endef
