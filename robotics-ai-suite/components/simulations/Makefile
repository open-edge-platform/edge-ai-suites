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
else ifeq ($(ROS_DISTRO),jazzy)
	UBUNTU_CODENAME := noble
else
	$(error Unsupported ROS_DISTRO: $(ROS_DISTRO). Supported: humble, jazzy)
endif

PACKAGES := package/turtlesim_tutorial package/realsense2_tutorial PicknPlace/robot_config PicknPlace/gazebo_plugins PicknPlace/picknplace PicknPlace

.DEFAULT_GOAL := help
.PHONY: license-check package test lint lint-all lint-clang lint-python lint-yaml lint-githubactions lint-bash lint-markdown lint-json source-package clean help

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

package:
	@# Help: Build Debian packages
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c " \
			set -e && \
			apt-get -qq update && apt install -qq -y equivs devscripts lsb-release curl gnupg && \
			git config --global --add safe.directory '*' && \
			\
			echo 'Installing Gazebo for $(ROS_DISTRO)...' && \
			curl --connect-timeout 30 --max-time 60 --retry 3 \
				--output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
				https://packages.osrfoundation.org/gazebo.gpg && \
			echo \"deb [arch=\$$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable \$$(lsb_release -cs) main\" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null && \
			apt-get update && \
			if [ '$(ROS_DISTRO)' = 'humble' ]; then \
				apt-get install -y ignition-fortress gz-sim7-cli libgz-sim7 libgz-sim7-dev ros-humble-ros-gz; \
			elif [ '$(ROS_DISTRO)' = 'jazzy' ]; then \
				apt-get install -y gz-harmonic gz-sim8-cli libgz-sim8 libgz-sim8-dev ros-jazzy-ros-gz ros-jazzy-gz-sim-vendor; \
			fi && \
			\
			echo 'Building Debian packages...' && \
			current_dir=\"\$$(pwd)\" && \
			packages=\"$(PACKAGES)\" && \
			for pkg in \$${packages}; do \
				SRC_DIR=\"\$${current_dir}/\$${pkg}/$(ROS_DISTRO)/debian\"; \
				echo \"Setting up debian control files for \$$pkg (\$$SRC_DIR)\"; \
				if [ ! -d \"\$$SRC_DIR\" ]; then \
					echo \"❌ ERROR: \$$SRC_DIR does not exist.\"; \
					exit 1; \
				fi; \
				rm -rf \"\$${current_dir}/\$${pkg}/debian\"; \
				cp -r \"\$$SRC_DIR\" \"\$${current_dir}/\$${pkg}/debian\"; \
			done && \
			\
			apt-get install -f -y && dpkg --configure -a && \
			\
			for pkg in \$${packages}; do \
				echo \"Installing dependencies for: \$$pkg\"; \
				mk-build-deps -i --host-arch amd64 --build-arch amd64 -t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' \$${current_dir}/\$$pkg/debian/control; \
			done && \
			\
			for pkg in \$${packages}; do \
				cd \$${current_dir}/\$$pkg && \
				echo \"Building package: \$$pkg\" && \
				DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -us -uc -b -tc -d && \
				cd \$${current_dir}; \
			done && \
			\
			mkdir -p output && \
			find .. -type f -name '*.deb' -not -name '*-build-deps_*' -exec mv {} output/ \\; || echo 'No .deb files found'"

test:
	@# Help: Test with existing packages or build & test with Colcon
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e ROS_DISTRO=$(ROS_DISTRO) \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c " \
			set -e && \
			apt-get -qq update && apt install -qq -y equivs devscripts dh-python lsb-release curl gnupg && \
			git config --global --add safe.directory '*' && \
			\
			echo 'Installing Gazebo for $(ROS_DISTRO)...' && \
			curl --connect-timeout 30 --max-time 60 --retry 3 \
				--output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
				https://packages.osrfoundation.org/gazebo.gpg && \
			echo \"deb [arch=\$$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable \$$(lsb_release -cs) main\" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null && \
			apt-get update && \
			if [ '$(ROS_DISTRO)' = 'humble' ]; then \
				apt-get install -y ignition-fortress gz-sim7-cli libgz-sim7 libgz-sim7-dev ros-humble-ros-gz; \
			elif [ '$(ROS_DISTRO)' = 'jazzy' ]; then \
				apt-get install -y gz-harmonic gz-sim8-cli libgz-sim8 libgz-sim8-dev ros-jazzy-ros-gz ros-jazzy-gz-sim-vendor; \
			fi && \
			\
			echo 'Checking for existing packages...' && \
			if [ -d \"./output\" ] && [ \"\$$(ls -A ./output/*.deb 2>/dev/null)\" ]; then \
				echo 'Using existing packages from ./output/'; \
				mkdir -p packages; \
				cp ./output/*.deb ./packages/ 2>/dev/null || true; \
			else \
				echo 'No existing packages found, building new ones...' && \
				current_dir=\"\$$(pwd)\" && \
				packages=\"$(PACKAGES)\" && \
				for pkg in \$${packages}; do \
					SRC_DIR=\"\$${current_dir}/\$${pkg}/$(ROS_DISTRO)/debian\"; \
					if [ ! -d \"\$$SRC_DIR\" ]; then \
						echo \"❌ ERROR: \$$SRC_DIR does not exist.\"; \
						exit 1; \
					fi; \
					rm -rf \"\$${current_dir}/\$${pkg}/debian\"; \
					cp -r \"\$$SRC_DIR\" \"\$${current_dir}/\$${pkg}/debian\"; \
				done && \
				\
				apt-get install -f -y && dpkg --configure -a && \
				\
				for pkg in \$${packages}; do \
					mk-build-deps -i --host-arch amd64 --build-arch amd64 -t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' \$${current_dir}/\$$pkg/debian/control; \
				done && \
				\
				for pkg in \$${packages}; do \
					cd \$${current_dir}/\$$pkg && \
					echo \"Building: \$$pkg\" && \
					DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -us -uc -b -tc -d && \
					cd \$${current_dir}; \
				done && \
				\
				mkdir -p packages && \
				find .. -type f -name '*.deb' -not -name '*-build-deps_*' -exec mv {} packages/ \\; || echo 'No .deb files found'; \
			fi && \
			\
			echo 'Installing packages...' && \
			if [ \"\$$(ls -A ./packages/*.deb 2>/dev/null)\" ]; then \
				dpkg -i ./packages/*.deb || true; \
				apt-get update; \
				apt-get install -f -y; \
				echo '✅ Packages installed successfully'; \
			else \
				echo '❌ No .deb packages found'; \
				exit 1; \
			fi && \
			\
			echo 'Running Colcon tests...' && \
			. /opt/ros/$(ROS_DISTRO)/setup.sh && \
			mkdir -p test_ws/src && \
			cd test_ws && \
			cp -r ../package ./src/ && \
			cp -r ../PicknPlace ./src/ && \
			colcon build --executor sequential --event-handlers console_direct+ && \
			colcon test --return-code-on-test-failure --executor sequential --event-handlers console_direct+ && \
			colcon test-result --verbose"
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

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o simulations-$(VERSION).zip HEAD \
		.gitattributes .gitignore Makefile README.md REUSE.toml \
		.github/linters docs LICENSES package PicknPlace scripts

clean:
	@# Help: Clean up generated Debian packages and artifacts
	rm -rf output packages test_ws
	find . -type f \( -name "*.deb" -o -name "*.build" -o -name "*.changes" -o -name "*.dsc" -o -name "*.tar.gz" -o -name "*.buildinfo" \) -delete
	@packages="$(PACKAGES)"; \
	for pkg in $$packages; do \
		if [ -d "$$pkg/debian" ]; then \
			echo "Removing $$pkg/debian"; \
			rm -rf "$$pkg/debian"; \
		fi; \
	done

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
