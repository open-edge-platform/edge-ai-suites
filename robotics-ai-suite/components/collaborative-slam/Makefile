# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

-include internal.mk

# Version info for packaging
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
.PHONY: help clean clean-colcon clean-debian license-check lint lint-all lint-clang lint-python lint-yaml lint-githubactions lint-bash lint-markdown lint-json package source-package

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

package:
	@# Help: Build Debian package
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-e DEBIAN_FRONTEND=noninteractive \
		-e MK_BUILD_DEPS_AUTO=yes \
		-e no_proxy=$(no_proxy) \
		amd64/ros:$(ROS_DISTRO)-ros-base \
		bash -c "cd /src/ && \
			curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/${UBUNTU_CODENAME} isar main\" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null && \
			echo \"deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/${UBUNTU_CODENAME} amr main\" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/${UBUNTU_CODENAME} amr main\" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
			echo \"deb-src [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/${UBUNTU_CODENAME} amr main\" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
			curl https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | \
				gpg --yes --dearmor --output /usr/share/keyrings/oneapi-archive-keyring.gpg && \
			echo \"deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main\" > /etc/apt/sources.list.d/oneAPI.list && \
			apt update && apt install -y quilt equivs devscripts && \
			scripts/uni-build.sh $(ROS_DISTRO) && cp -r /tmp/$(ROS_DISTRO)_cslam_deb_packages/ /src/$(ROS_DISTRO)_cslam_deb_packages"

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
	git archive --format=zip -o collaborative-slam-$(VERSION).zip HEAD \
		.gitattributes .gitignore Makefile README.md REUSE.toml \
		.github/linters 3rd benchmark cmake docs include LICENSES msgs package scripts server slam tracker

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
