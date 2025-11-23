# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

.PHONY: build clean

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

ROS_DISTRO ?= humble

# Version info for packaging
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

PACKAGES := segmentation_realsense_tutorial object_detection_tutorial yolov8/src/yolo_msgs yolov8/src/yolo

.PHONY: license-check build tests clean source-package

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	@docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

build:
	@# Help: Build code using colcon
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		--pull always \
		-w /src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "apt -qq update && apt install -y equivs devscripts lld wget && . /opt/ros/$(ROS_DISTRO)/setup.sh; \
			wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/openvino-archive-keyring.gpg; \
			echo \"deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main\" | tee /etc/apt/sources.list.d/intel-openvino-2024.list; \
			apt -qq update && ./scripts/build.sh"

tests:
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl -v https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -o /usr/share/keyrings/openvino-archive-keyring.gpg && \
			cat /usr/share/keyrings/openvino-archive-keyring.gpg | gpg --dearmor | tee /usr/share/keyrings/openvino-archive-keyring.gpg && \
			echo \"deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main\" | tee /etc/apt/sources.list.d/intel-openvino-2024.list && \
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

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o multicam-demo-$(VERSION).zip HEAD \
		.gitignore .gitattributes .gitmodules Makefile README.md REUSE.toml \
		.github/linters LICENSES object_detection_tutorial scripts segmentation_realsense_tutorial yolov8

clean:
	@# Clean: Removes build artifacts. Some commands require sudo to properly cleanup, so running it in container to avoid permission issues
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "cd /src && rm -rf ros-* build/ install/; \
		$(foreach pkg,$(PACKAGES), cd /src/$(pkg) && rm -rf debian/ build/ install/ obj-x86_64-linux-gnu/;)"
