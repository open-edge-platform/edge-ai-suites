# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

ROS_DISTRO ?= humble
ifeq ($(ROS_DISTRO),humble)
	UBUNTU_CODENAME := jammy
else
	UBUNTU_CODENAME := noble
endif

.DEFAULT_GOAL := help
.PHONY: build license-check help lint lint-all lint-clang lint-python lint-yaml lint-githubactions lint-bash lint-markdown lint-json test source-package clean

build:
	@# Help: Build debian package
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		--pull always \
		-w /src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "apt -qq update && apt -q install -y equivs devscripts && cd pointcloud_groundfloor_segmentation && \
			echo \"Setting up debian control files for ${ROS_DISTRO}\" && \
			if [ ! -d ${ROS_DISTRO}/debian ]; then \
				echo \"❌ ERROR: ${ROS_DISTRO}/debian does not exist.\" && \
				exit 1;\
			fi  && \
			rm -rf debian && \
			cp -r ${ROS_DISTRO}/debian/ ./debian && \
        		mk-build-deps -i --host-arch amd64 --build-arch amd64 \
				-t \"apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades\" debian/control && \
			dpkg-buildpackage -us -uc"

test:
	@# Help: Run tests
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		-w /src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "apt -qq update && apt install -y equivs devscripts psmisc && \
		cd pointcloud_groundfloor_segmentation && \
		mk-build-deps -i --host-arch amd64 --build-arch amd64 \
			-t \"apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades\" ${ROS_DISTRO}/debian/control && \
		source /opt/ros/${ROS_DISTRO}/setup.bash && \
		colcon build --cmake-args -DBUILD_TEST=ON -DCMAKE_BUILD_TYPE=Release && \
		source install/setup.bash && \
		cd build/pointcloud_groundfloor_segmentation/test && \
		./pointcloud-groundfloor-segmentation-tests >> test_log_seg_${ROS_DISTRO}.log && \
		cd ../../../ && \
		cd build/pointcloud_groundfloor_segmentation/test && \
		chmod +x test_*.sh && \
		./test_realsense.sh  >> test_log_realsense_${ROS_DISTRO}.log && \
		./test_lidar.sh  >> test_log_lidar_${ROS_DISTRO}.log"

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o groundfloor-$(VERSION).zip HEAD \
		.gitattributes .gitignore .clang-format Makefile README.md REUSE.toml \
		.github/linters .vscode docker docs LICENSES \
		pointcloud_groundfloor_segmentation/cmake \
		pointcloud_groundfloor_segmentation/include \
		pointcloud_groundfloor_segmentation/launch \
		pointcloud_groundfloor_segmentation/params \
		pointcloud_groundfloor_segmentation/rviz \
		pointcloud_groundfloor_segmentation/src \
		pointcloud_groundfloor_segmentation/CMakeLists.txt \
		pointcloud_groundfloor_segmentation/package.xml

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

help:
	@printf "%-20s %s\n" "Target" "Description"
	@printf "%-20s %s\n" "------" "-----------"
	@grep -E '^[a-zA-Z0-9_%-]+:|^[[:space:]]+@# Help:' Makefile | \
	awk '\
		/^[a-zA-Z0-9_%-]+:/ { \
			target = $$1; \
			sub(":", "", target); \
		} \
		/^[[:space:]]+@# Help:/ { \
			if (target != "") { \
				help_line = $$0; \
				sub("^[[:space:]]+@# Help: ", "", help_line); \
				printf "%-20s %s\n", target, help_line; \
				target = ""; \
			} \
		}' | sort -k1,1

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

lint-clang:
	@# Help: Run clang linter using super-linter
	VALIDATE_CLANG_FORMAT=true make lint-all

lint-python:
	@# Help: Run Python linter using super-linter
	VALIDATE_PYTHON_PYLINT=true VALIDATE_PYTHON_FLAKE8=true make lint-all

lint-yaml:
	@# Help: Run YAML linter using super-linter
	VALIDATE_YAML=true make lint-all

lint-githubactions:
	@# Help: Run Github Actions linter using super-linter
	VALIDATE_GITHUB_ACTIONS=true make lint-all

lint-bash:
	@# Help: Run Bash linter using super-linter
	VALIDATE_BASH=true make lint-all

lint-markdown:
	@# Help: Run Markdown linter using super-linter
	VALIDATE_MARKDOWN=true make lint-all

lint-json:
	@# Help: Run JSON linter using super-linter
	VALIDATE_JSON=true make lint-all

clean:
	@# Help: Clean build artifacts
	rm -rf build* install* log* debian/ ros-* *.deb
	cd pointcloud_groundfloor_segmentation && rm -rf build* debian/ ros-* *.deb
