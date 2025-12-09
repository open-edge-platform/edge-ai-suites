# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

.PHONY: build clean

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

ROS_DISTRO ?= humble

ifeq ($(ROS_DISTRO),humble)
	OPENVINO_DISTRO := ubuntu22
else
	OPENVINO_DISTRO := ubuntu24
endif

# Version info for packaging
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

PACKAGES := segmentation_realsense_tutorial object_detection_tutorial yolov8/src/yolo_msgs yolov8/src/yolo

.PHONY: license-check package test clean source-package lint lint-all

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	@docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

package:
	@# Help: Build Debian packages
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		--pull always \
		-w /src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/openvino-archive-keyring.gpg > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino ${OPENVINO_DISTRO} main\" | tee /etc/apt/sources.list.d/intel-openvino.list && \
			echo -e \"Package: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001\" | tee /etc/apt/preferences.d/intel-openvino > /dev/null && \
			echo -e \"\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001\" | tee -a /etc/apt/preferences.d/intel-openvino > /dev/null && \
			echo -e \"\nPackage: ros-${ROS_DISTRO}-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002\" | tee -a /etc/apt/preferences.d/intel-openvino > /dev/null && \
			echo -e \"\nPackage: ros-${ROS_DISTRO}-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002\" | tee -a /etc/apt/preferences.d/intel-openvino > /dev/null && \
			apt -qq update && apt install -y equivs devscripts lld && . /opt/ros/$(ROS_DISTRO)/setup.sh && ./scripts/build.sh"

test:
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl -v https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -o /usr/share/keyrings/openvino-archive-keyring.gpg && \
			cat /usr/share/keyrings/openvino-archive-keyring.gpg | gpg --dearmor | tee /usr/share/keyrings/openvino-archive-keyring.gpg && \
			echo \"deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino ${OPENVINO_DISTRO} main\" | tee /etc/apt/sources.list.d/intel-openvino.list && \
            apt -qq update && apt -q -y install lld devscripts debhelper openvino libopencv-dev && \
			$(foreach pkg,$(PACKAGES), cd /src/$(pkg) && cp -r ${ROS_DISTRO}/debian/ . && dpkg-buildpackage -Tclean -d && rm -rf debian/ &&) \
			cd /src && source /opt/ros/${ROS_DISTRO}/setup.sh && \
			colcon build \
            	--executor sequential \
            	--event-handlers console_direct+ \
            	--cmake-args \
					-DCMAKE_LINKER=/usr/bin/ld.lld \
					-DCMAKE_EXE_LINKER_FLAGS=\"-fuse-ld=lld\" \
					-DCMAKE_SHARED_LINKER_FLAGS=\"-fuse-ld=lld\" && \
			source install/setup.bash && \
			colcon test \
				--return-code-on-test-failure \
				--executor sequential \
				--event-handlers console_direct+ < /dev/null"

lint:
	@# Help: Run all sub-linters using super-linter (using linters defined for this repo only)
	VALIDATE_GITHUB_ACTIONS=true \
	VALIDATE_YAML=true \
	VALIDATE_JSON=true \
	VALIDATE_PYTHON_PYLINT=true \
	VALIDATE_PYTHON_FLAKE8=true \
	VALIDATE_BASH=true \
	VALIDATE_MARKDOWN=true \
	VALIDATE_CLANG_FORMAT=true \
		make lint-all

lint-all:
	@# Help: Run super-linter over entire repository (auto-detects code to lint)
	docker run --rm --platform linux/amd64 \
		-e SHELL=/bin/bash \
		-e RUN_LOCAL=true \
		--env-file ".github/linters/super-linter.env" \
		$(if $(VALIDATE_GITHUB_ACTIONS),-e VALIDATE_GITHUB_ACTIONS=$(VALIDATE_GITHUB_ACTIONS)) \
		$(if $(VALIDATE_YAML),-e VALIDATE_YAML=$(VALIDATE_YAML)) \
		$(if $(VALIDATE_JSON),-e VALIDATE_JSON=$(VALIDATE_JSON)) \
		$(if $(VALIDATE_PYTHON_PYLINT),-e VALIDATE_PYTHON_PYLINT=$(VALIDATE_PYTHON_PYLINT)) \
		$(if $(VALIDATE_PYTHON_FLAKE8),-e VALIDATE_PYTHON_FLAKE8=$(VALIDATE_PYTHON_FLAKE8)) \
		$(if $(VALIDATE_BASH),-e VALIDATE_BASH=$(VALIDATE_BASH)) \
		$(if $(VALIDATE_MARKDOWN),-e VALIDATE_MARKDOWN=$(VALIDATE_MARKDOWN)) \
		$(if $(VALIDATE_CLANG_FORMAT),-e VALIDATE_CLANG_FORMAT=$(VALIDATE_CLANG_FORMAT)) \
		-v $(ROOT_DIR):/tmp/lint \
			ghcr.io/super-linter/super-linter:slim-v8.1.0

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o object-detection-$(VERSION).zip HEAD \
		.gitattributes Makefile README.md REUSE.toml .github/linters LICENSES \
		object_detection_tutorial scripts segmentation_realsense_tutorial yolov8

clean:
	@# Clean: Removes build artifacts. Some commands require sudo to properly cleanup, so running it in container to avoid permission issues
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "cd /src && rm -rf ros-* build/ install/; \
		$(foreach pkg,$(PACKAGES), cd /src/$(pkg) && rm -rf debian/ build/ install/ obj-x86_64-linux-gnu/;)"
