# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

#----------------------------------------------------------------------------------------------------------------------
# Flags
#----------------------------------------------------------------------------------------------------------------------
SHELL:=/bin/bash
CURRENT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
ROS_DISTRO ?= humble

# Version info for packaging
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

# Absolute path to the git repository root (needed so super-linter sees .git even when invoked from this component)
REPO_ROOT:=$(shell git rev-parse --show-toplevel 2>/dev/null || echo $(ROOT_DIR))

# Path of this component relative to repo root (used to scope linting with FILTER_REGEX_INCLUDE)
COMPONENT_PATH_REL:=$(shell realpath --relative-to "$(REPO_ROOT)" "$(ROOT_DIR)" 2>/dev/null || echo robotics-ai-suite/components/multicam-demo)

# Add --break-system-packages flag for jazzy (Python 3.12+)
ifeq ($(ROS_DISTRO),jazzy)
    PIP_EXTRA_FLAGS := --break-system-packages
else
    PIP_EXTRA_FLAGS :=
endif

#----------------------------------------------------------------------------------------------------------------------
# Docker Settings
#----------------------------------------------------------------------------------------------------------------------
DOCKER_IMAGE_NAME=realsense-d457-ai-demo

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
.PHONY: default license-check lint lint-all lint-python lint-yaml lint-githubactions lint-bash lint-json lint-markdown image test package source-package models yolov8_models mobilenet_models demo bash clean

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	@docker run --rm --volume ${CURRENT_DIR}:/data fsfe/reuse:5.0.2 lint

lint:
	@$(call msg, Running all linters using super-linter ...)
	VALIDATE_GITHUB_ACTIONS=true \
	VALIDATE_YAML=true \
	VALIDATE_JSON=true \
	VALIDATE_PYTHON=true \
	VALIDATE_BASH=true \
	VALIDATE_MARKDOWN=true \
		$(MAKE) lint-all

lint-all:
	@$(call msg, Running super-linter ...)
	@docker run --rm --platform linux/amd64 \
		-e SHELL=/bin/bash \
		-e RUN_LOCAL=true \
		-e DEFAULT_BRANCH=main \
		-e VALIDATE_ALL_CODEBASE=false \
		-e FILTER_REGEX_INCLUDE="^$(COMPONENT_PATH_REL)/" \
		-e LINTER_RULES_PATH=$(COMPONENT_PATH_REL)/.github/linters \
		$(if $(VALIDATE_GITHUB_ACTIONS),-e VALIDATE_GITHUB_ACTIONS=$(VALIDATE_GITHUB_ACTIONS)) \
		$(if $(GITHUB_ACTIONS_COMMAND_ARGS),-e GITHUB_ACTIONS_COMMAND_ARGS=$(GITHUB_ACTIONS_COMMAND_ARGS)) \
		$(if $(VALIDATE_YAML),-e VALIDATE_YAML=$(VALIDATE_YAML)) \
		$(if $(VALIDATE_JSON),-e VALIDATE_JSON=$(VALIDATE_JSON)) \
		$(if $(VALIDATE_PYTHON),-e VALIDATE_PYTHON=$(VALIDATE_PYTHON)) \
		$(if $(VALIDATE_BASH),-e VALIDATE_BASH=$(VALIDATE_BASH)) \
		$(if $(VALIDATE_MARKDOWN),-e VALIDATE_MARKDOWN=$(VALIDATE_MARKDOWN)) \
		-v $(REPO_ROOT):/tmp/lint \
			ghcr.io/super-linter/super-linter:slim-v7.3.0

lint-python:
	@$(call msg, Running Python linter ...)
	@VALIDATE_PYTHON=true $(MAKE) lint-all

lint-yaml:
	@$(call msg, Running YAML linter ...)
	@VALIDATE_YAML=true $(MAKE) lint-all

lint-githubactions:
	@$(call msg, Running GitHub Actions linter ...)
	@VALIDATE_GITHUB_ACTIONS=true \
	GITHUB_ACTIONS_COMMAND_ARGS="-ignore SC2043 -ignore SC2011 -ignore SC2035 -ignore SC2156 -ignore SC2038 -ignore SC2061 -ignore SC2129 -ignore \".+\" section is missing in workflow -ignore unexpected key \".+\" for \"workflow\" section" \
		$(MAKE) lint-all

lint-bash:
	@$(call msg, Running Bash linter ...)
	@VALIDATE_BASH=true $(MAKE) lint-all

lint-json:
	@$(call msg, Running JSON linter ...)
	@VALIDATE_JSON=true $(MAKE) lint-all

lint-markdown:
	@$(call msg, Running Markdown linter ...)
	@VALIDATE_MARKDOWN=true $(MAKE) lint-all

image:
	@$(call msg, Building Docker image ${DOCKER_IMAGE_NAME} ...)
	@docker build --rm . -t ${DOCKER_IMAGE_NAME}

test:
	@$(call msg, Running unit tests in container ...)
	@rm -f $(CURRENT_DIR)/tests/unittest/realsense-d457-ai-demo_pytest.log
	@docker run --rm -t --platform linux/amd64 \
		-v $(CURRENT_DIR):/workspace \
		-w /workspace/tests/unittest \
		amd64/ros:$(ROS_DISTRO)-ros-base \
		bash -c "set -o pipefail && \
		apt-get -qq update && \
		DEBIAN_FRONTEND=noninteractive apt-get -q install -y python3-pip python3-pytest python3-opencv && \
		pip3 install $(PIP_EXTRA_FLAGS) pyrealsense2 && \
		export PYTHONPATH=/workspace/src && \
		echo '-----------------------------------------' | tee -a realsense-d457-ai-demo_pytest.log && \
		echo 'Unit test log for realsense-d457-ai-demo.' | tee -a realsense-d457-ai-demo_pytest.log && \
		echo '-----------------------------------------' | tee -a realsense-d457-ai-demo_pytest.log && \
		echo '' | tee -a realsense-d457-ai-demo_pytest.log && \
		echo \"Unit test start timestamp: \$$(date)\" | tee -a realsense-d457-ai-demo_pytest.log && \
		python3 -m pytest -v realsense-d457-ai-demo_pytest.py | tee -a realsense-d457-ai-demo_pytest.log; \
		TEST_EXIT_CODE=\$$?; \
		echo \"Unit test end timestamp: \$$(date)\" | tee -a realsense-d457-ai-demo_pytest.log; \
		exit \$$TEST_EXIT_CODE"

package:
	@$(call msg, Building Debian packages in container ...)
	@docker run --rm -t --platform linux/amd64 \
		-v $(CURRENT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e MK_BUILD_DEPS_AUTO=yes \
		amd64/ros:$(ROS_DISTRO)-ros-base \
		bash -c "apt-get -qq update && \
		apt-get -qq install -y equivs devscripts dh-python python3-all cython3 && \
		rm -rf debian && cp -r $(ROS_DISTRO)/debian ./debian && \
		mk-build-deps -i --host-arch amd64 --build-arch amd64 \
		  -t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' debian/control && \
		DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc && \
		mv ../*.deb ./ 2>/dev/null || true"
	@$(call msg, Debian packages built successfully)

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o multicam-demo-$(VERSION).zip HEAD \
		.gitignore Dockerfile Makefile README.md requirements.txt REUSE.toml \
		.github/linters/yamllint.yml config docs images LICENSES scripts src videos \
		humble jazzy

yolov8_models: image
	@$(call msg, Preparing the yolov8 models ...)
	@docker run ${DOCKER_RUN_PARAMS} bash -c ' \
		source /opt/intel/oneapi/setvars.sh && source /opt/intel/openvino/setupvars.sh  && \
		/workspace/scripts/yolov8_model_prepare.sh yolov8n yolov8s yolov8m yolov8n-seg yolov8s-seg yolov8m-seg \
		'

mobilenet_models: image
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

bash: image
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
	tput setaf 2 2>/dev/null || true && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo  "" && \
	echo "         "$1 && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo "" && \
	tput sgr0 2>/dev/null || true
endef
