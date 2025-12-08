# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

# Version info for packaging
COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

ROS_DISTRO ?= humble

# Map ROS_DISTRO to Ubuntu codename
ifeq ($(ROS_DISTRO),humble)
	UBUNTU_CODENAME := jammy
	OPENVINO_DISTRO := ubuntu22
else
	UBUNTU_CODENAME := noble
	OPENVINO_DISTRO := ubuntu24
endif

# Base packages for all distributions
PACKAGES_BASE = ROS2_node \
	Follow_me_RS_2D/src/follow_me_interfaces \
	Follow_me_RS_2D/src/adbscan_ros2 \
	Follow_me_RS_2D/src/gesture_recognition_pkg \
	Follow_me_RS_2D/src/speech_recognition_pkg \
	Follow_me_RS_2D/src/text_to_speech_pkg \
	package/tutorial-aaeon-adbscan \
	package/tutorial_follow-me \
	package/tutorial_follow-me-w-gesture

# Add turtlebot3_simulations only for humble
ifeq ($(ROS_DISTRO),humble)
	PACKAGES = $(PACKAGES_BASE) Follow_me_RS_2D/src/turtlebot3_simulations/followme_turtlebot3_gazebo
else
	PACKAGES = $(PACKAGES_BASE)
endif

.DEFAULT_GOAL := help
.PHONY: license-check package test lint lint-all lint-clang lint-python lint-yaml lint-githubactions lint-bash lint-markdown lint-json clean-colcon clean-debian clean source-package help

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

package:
	@# Help: Build Debian packages
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e OPENVINO_INSTALL_DIR="/opt/intel/openvino" \
		-e OPENVINO_DOWNLOAD_MODELS="no" \
		-e INTEL_OPENVINO_DIR="/opt/intel/openvino" \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null && \
			curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/intel-archive-keyring.gpg > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | tee /etc/apt/sources.list.d/eci.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | tee -a /etc/apt/sources.list.d/eci.list > /dev/null && \
			$(if $(filter humble,$(ROS_DISTRO)),echo -e \"Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000\n\nPackage: libflann*\nPin: version 1.19.*\nPin-Priority: -1\n\nPackage: flann*\nPin: version 1.19.*\nPin-Priority: -1\" | tee /etc/apt/preferences.d/isar > /dev/null && ,)\
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | tee /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/intel-archive-keyring.gpg] https://apt.repos.intel.com/openvino ${OPENVINO_DISTRO} main\" | sudo tee /etc/apt/sources.list.d/intel-openvino.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/intel-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main\" | tee /etc/apt/sources.list.d/oneAPI.list > /dev/null && \
			echo -e \"Package: intel-oneapi-runtime-*\nPin: version 2025.*\nPin-Priority: 1001\" | tee /etc/apt/preferences.d/oneAPI > /dev/null && \
			apt-get -qq update && apt-get install -qq -y devscripts equivs && \
			for path in ${PACKAGES}; do \
				echo \"Building package: \$$path\"; \
				cd /src/\$$path && \
				rm -rf debian && cp -r ${ROS_DISTRO}/debian ./debian && \
				mk-build-deps -i --host-arch amd64 --build-arch amd64 \
						-t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' debian/control && \
				DEB_BUILD_OPTIONS='verbose' dpkg-buildpackage -us -uc -b -d && \
				find . -path ./output -prune -o -type f -name '*.deb' -not -name '*-build-deps_*' -not -name '*-dbgsym_*' -not -name '*.changes' -exec apt-get install -f -y {} \; ; \
			done; \
			find . -path ./output -prune -o -type f -name '*.deb' -not -name '*-build-deps_*' -exec mv {} ./ \; || echo 'No .deb files found'"

test:
	@# Help: Test code using colcon
	@if ! ls ros-$(ROS_DISTRO)-adbscan-ros2_*.deb 2>/dev/null | grep -q .; then \
		echo "Error: ros-$(ROS_DISTRO)-adbscan-ros2*.deb not found. Run 'make package' first"; \
		exit 1; \
	fi
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null && \
			curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/intel-archive-keyring.gpg > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | tee /etc/apt/sources.list.d/eci.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | tee -a /etc/apt/sources.list.d/eci.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | tee /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/intel-archive-keyring.gpg] https://apt.repos.intel.com/openvino ${OPENVINO_DISTRO} main\" | sudo tee /etc/apt/sources.list.d/intel-openvino.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/intel-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main\" | tee /etc/apt/sources.list.d/oneAPI.list > /dev/null && \
			echo -e \"Package: intel-oneapi-runtime-*\nPin: version 2025.*\nPin-Priority: 1001\" | tee /etc/apt/preferences.d/oneAPI > /dev/null && \
			apt-get -qq update && apt install -qq -y equivs devscripts libtbb-dev \
				$(if $(filter humble,$(ROS_DISTRO)),ros-${ROS_DISTRO}-gazebo-ros-pkgs) \
				ros-${ROS_DISTRO}-pcl-conversions && \
			find . -maxdepth 1 -name 'ros-$(ROS_DISTRO)-adbscan-ros2*.deb' -not -name '*-build-deps_*' -not -name '*-dbgsym_*' -exec apt-get install -f -y {} \; && \
			current_dir=\"\$$(pwd)\" && \
			\
			for path in ${PACKAGES}; do \
				if [ ! -d \"\$$path\" ]; then \
					echo \"Skipping \$$path: not a directory\"; \
					continue; \
				fi; \
				echo \"Cleaning up debian build in \$$path folder\"; \
				cd \$$path && \
				dpkg-buildpackage -Tclean -d && \
				cd \$$current_dir; \
			done && \
			\
			echo 'Setting up ROS environment and running tests...' && \
			. /opt/ros/${ROS_DISTRO}/setup.sh && \
			colcon build --executor sequential --event-handlers console_direct+ && \
			colcon test --return-code-on-test-failure --executor sequential --event-handlers console_direct+"

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

clean-colcon:
	@# Help: Clean up Colcon build and test artifacts
	rm -rf build/ install/ log/

clean-debian:
	@# Help: Clean up Debian packaging artifacts
	@for path in ${PACKAGES}; do \
		if [ -d "$$path/debian" ]; then \
			echo "Removing $$path/debian"; \
			rm -rf "$$path/debian"; \
		fi; \
	done
	rm -f *.deb *.build *.changes *.dsc *.tar.gz *.buildinfo
	rm -rf ROS2_node/.obj-x86_64-linux-gnu-oneapi/
	rm -rf ROS2_node/.obj-x86_64-linux-gnu/
	rm -rf package/tutorial-aaeon-adbscan/obj-x86_64-linux-gnu/
	rm -rf package/tutorial_follow-me-w-gesture/obj-x86_64-linux-gnu/
	rm -rf package/tutorial_follow-me/obj-x86_64-linux-gnu/

clean: clean-debian clean-colcon
	@# Help: Clean up all build artifacts

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o adbscan-$(VERSION).zip HEAD \
		.gitattributes .gitignore Makefile README.md REUSE.toml \
		.github/linters docs input LICENSES output package \
		Follow_me_RS_2D ROS2_node Standalone Visualization

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


