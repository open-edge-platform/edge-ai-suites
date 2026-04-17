# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail

COMMIT := $(shell git rev-parse --short HEAD)
DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
VERSION := $(COMMIT)-$(DATE)

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
ROS_DISTRO?=humble

.DEFAULT_GOAL := help
.PHONY: license-check build-nav2-msgs build-nav2-amcl build help source-package lint lint-all

license-check:
	@# Help: Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
	docker run --rm --volume ${ROOT_DIR}:/data fsfe/reuse:5.0.2 lint

build-nav2-msgs:
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "mkdir -p /tmp/build && cd /tmp/build/ && apt update && apt install -y quilt equivs devscripts && \
			apt source ros-${ROS_DISTRO}-nav2-msgs && \
			export QUILT_PATCHES=debian/patches && \
			export QUILT_REFRESH_ARGS=\"-p ab --no-timestamps --no-index\" && \
			cd ./ros-${ROS_DISTRO}-nav2-msgs-* && \
			quilt import -f -d n /src/3rd_party/patches/${ROS_DISTRO}/*-msgs-*.patch && \
			quilt push -a && \
			echo \"Building patched nav2_msgs packages\" && \
			mk-build-deps -i --host-arch amd64 --build-arch amd64 -t \"apt -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades\" ./debian/control  && \
			echo \"1.0\" > ./debian/source/format && \
			sed -i 's/\(.*-nav2-msgs\) (\(.*\)) \(.*\)/\1 (\2-patch1) \3/g' ./debian/changelog && \
			dpkg-buildpackage && \
			find .. -name \"ros-${ROS_DISTRO}-nav2-msgs_*.deb\" -exec cp {} /src/ \;"

build-nav2-amcl: build-nav2-msgs
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c "mkdir -p /tmp/build && cd /tmp/build/ && apt update && apt install -y quilt equivs devscripts && \
			apt source ros-${ROS_DISTRO}-nav2-amcl && \
			find /src -name \"ros-${ROS_DISTRO}-nav2-msgs_*.deb\" -exec apt-get install -y -f {} \; && \
			export QUILT_PATCHES=debian/patches && \
			export QUILT_REFRESH_ARGS=\"-p ab --no-timestamps --no-index\" && \
			cd ./ros-${ROS_DISTRO}-nav2-amcl-* && \
			quilt import -f -d n /src/3rd_party/patches/${ROS_DISTRO}/*-amcl-*.patch && \
			quilt push -a && \
			echo \"Building patched amcl packages\" && \
			mk-build-deps -i --host-arch amd64 --build-arch amd64 -t \"apt -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades\" ./debian/control  && \
			echo \"1.0\" > ./debian/source/format && \
			sed -i 's/\(.*-nav2-amcl\) (\(.*\)) \(.*\)/\1 (\2-patch1) \3/g' ./debian/changelog && \
			dpkg-buildpackage && \
			find .. -name \"ros-${ROS_DISTRO}-nav2-amcl_*.deb\" -exec cp {} /src/ \;"

build: build-nav2-msgs build-nav2-amcl
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		amd64/ros:${ROS_DISTRO}-ros-base \
		bash -c " \
			cd /src && apt update && apt install -y equivs devscripts && \
			find .. -name \"ros-${ROS_DISTRO}-nav2-msgs_*.deb\" -exec apt install -y -f {} \; && \
			find .. -name \"ros-${ROS_DISTRO}-nav2-amcl_*.deb\" -exec apt install -y -f {} \; ;\
			for path in its_planner relocalization send_localization collab_slam; do \
				echo \"Processing package: \$${path}\"; \
				mk-build-deps -i --host-arch amd64 --build-arch amd64 -t \"apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades\" \$${path}/${ROS_DISTRO}/debian/control && \
				cd \$${path} && \
				rm -rf ./debian && \
				cp -r ./${ROS_DISTRO}/debian ./debian && \
				echo \"Building packages for: \$${path}\" && \
				dpkg-buildpackage && \
				rm -rf ./debian ./.obj-x86_64-linux-gnu && \
				cd /src && \
				echo \"Installing newly built packages...\" && \
				find .. -name \"*.deb\" -not -name \"*-build-deps_*\" -not -name \"*-dbgsym_*\" -exec apt-get install -y -f {} \; ; \
			done ; \
			ls | grep ros-${ROS_DISTRO} | grep -v deb | xargs sudo rm -rf --"


source-package:
	@# Help: Create source package tarball
	git archive --format=zip -o its-planner-$(VERSION).zip HEAD \
		.gitattributes .gitignore .gitmodules Makefile README.md REUSE.toml run_its.sh \
		.github/linters 3rd_party collab_slam docs its_planner LICENSES relocalization send_localization

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
