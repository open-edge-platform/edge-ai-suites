# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail

COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

ROS_DISTRO ?= humble

# Map ROS_DISTRO to Ubuntu codename
ifeq ($(ROS_DISTRO),humble)
	UBUNTU_CODENAME := jammy
else
	UBUNTU_CODENAME := noble
endif

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	MAKE_JOBS ?= $(shell sysctl -n hw.ncpu)
else
	MAKE_JOBS ?= $(shell nproc)
endif

.DEFAULT_GOAL := help
.PHONY: build clean help license-check lint lint-all package test source-package

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

package:
	@# Help: Build Debian package
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e MK_BUILD_DEPS_AUTO=yes \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "export DEBIAN_FRONTEND=noninteractive && apt-get -qq update && apt-get -qq install -y equivs devscripts && cd /src && \
		rm -rf debian && cp -r "$(ROS_DISTRO)/debian" ./debian && \
		mk-build-deps -i --host-arch amd64 --build-arch amd64 \
		  -t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' debian/control && \
		DEB_BUILD_OPTIONS='nocheck parallel=$(MAKE_JOBS)' dpkg-buildpackage -us -uc && \
		mv ../*.deb ./ 2>/dev/null || true"

test-e2e:
	@# Help: Run E2E functional tests
	@if ! ls ros-$(ROS_DISTRO)-fast-mapping*.deb 2>/dev/null | grep -v 'ros-$(ROS_DISTRO)-fast-mapping-build-deps_.*_amd64.deb' | grep -q .; then \
		echo "Error: ros-$(ROS_DISTRO)-fast-mapping*.deb not found. Run 'make package' first"; \
		exit 1; \
	fi
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null && \
		echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null && \
		echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null && \
		echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null && \
		echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
		apt-get -qq update && apt-get -q install -y wget python3 python3-pip xvfb graphicsmagick && cd /src && \
		$(if $(filter humble,$(ROS_DISTRO)),python3 -m pip install --upgrade pip &&) \
		pip3 install pytest Pillow $(if $(filter humble,$(ROS_DISTRO)),-U,--break-system-packages) && \
		find . -name '*.deb' -not -name '*-build-deps_*' -not -name '*-dbgsym_*' -exec apt-get -q install -y {} \; && \
		source /opt/ros/$(ROS_DISTRO)/setup.bash && \
		pytest tests/ -v"

build:
	@# Help: Build code using colcon
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "apt -qq update && DEBIAN_FRONTEND=noninteractive apt -o=Dpkg::Use-Pty=0 -qq install -y ros-$(ROS_DISTRO)-cv-bridge libboost-dev && cd /src && . /opt/ros/$(ROS_DISTRO)/setup.sh && \
		colcon build --executor sequential --event-handlers console_direct- compile_commands- console_cohesion- console_package_list- console_start_end+ console_stderr+ desktop_notification- event_log- log- log_command- status- store_result- summary+ terminal_title-"

test:
	@# Help: Test code using colcon
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "apt -qq update && DEBIAN_FRONTEND=noninteractive apt -qq install -y ros-$(ROS_DISTRO)-cv-bridge libboost-dev && cd /src && . /opt/ros/$(ROS_DISTRO)/setup.sh && \
		colcon test --return-code-on-test-failure --executor sequential --event-handlers console_direct- compile_commands- console_cohesion- console_package_list- console_start_end+ console_stderr+ desktop_notification- event_log- log- log_command- status- store_result- summary+ terminal_title-"

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
	rm -rf debian
	rm -f *.deb *.build *.changes *.dsc *.tar.gz *.buildinfo

clean: clean-debian clean-colcon
	@# Help: Clean up all build artifacts

source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o fast-mapping-$(VERSION).zip HEAD \
		.bdsignore.all .gitattributes .gitignore CMakeLists.txt Makefile package.xml README.md REUSE.toml \
		.github/linters dependencies docs include launch LICENSES src tests \
		humble jazzy

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
