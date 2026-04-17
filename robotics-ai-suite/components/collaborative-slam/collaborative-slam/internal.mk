# internal.mk
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Internal targets for testing with proprietary bagfiles (NOT_FOR_RELEASE)

ROS_DISTRO ?= humble
ifeq ($(ROS_DISTRO),humble)
	UBUNTU_CODENAME := jammy
else
	UBUNTU_CODENAME := noble
endif

.PHONY: test-e2e-internal

test-e2e-internal:
	@# Help: Runs smoke tests with internal bagfile "ros-$(ROS_DISTRO)-bagfile-demo-mapping" (/NOT-FOR-RELEASE/cslam-unit-test/demo_mapping from AMR repo)
	@set -e; \
	for pattern in "ros-$(ROS_DISTRO)-*-slam-sse_*.deb" "ros-$(ROS_DISTRO)-*-tracker-sse_*.deb" "ros-$(ROS_DISTRO)-*-tracker-smoke-test_*.deb"; do \
		files=$$(find . -name "$$pattern" -not -name "*-build-deps_*" -not -name "*-dbgsym_*"); \
		if [ -z "$$files" ]; then \
			echo "Error: No .deb package found matching pattern '$$pattern'"; \
			exit 1; \
		fi; \
	done
	curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
	echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(UBUNTU_CODENAME) isar main" | tee /etc/apt/sources.list.d/eci.list > /dev/null
	echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(UBUNTU_CODENAME) isar main" | tee -a /etc/apt/sources.list.d/eci.list > /dev/null
	echo "deb [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/$(UBUNTU_CODENAME) amr main" > /etc/apt/sources.list.d/amr.list
	echo "deb-src [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/$(UBUNTU_CODENAME) amr main" >> /etc/apt/sources.list.d/amr.list
	apt-get -qq update && apt-get install -y --allow-downgrades ros-$(ROS_DISTRO)-dbow2 nlohmann-json3-dev python3-pip python3-ament-package ros-$(ROS_DISTRO)-image-transport-plugins
	@# Install univloc-msgs package
	@if dpkg -i ./ros-$(ROS_DISTRO)-univloc-msgs_*.deb 2>/dev/null; then \
		echo "univloc-msgs installed successfully"; \
		apt-get install -f -y --allow-downgrades; \
	else \
		echo "dpkg failed for univloc-msgs, trying apt fallback"; \
		apt-get install -y --allow-downgrades ros-$(ROS_DISTRO)-univloc-msgs || echo "Warning: univloc-msgs not available in apt"; \
	fi
	@# Install slam-sse packages
	@for deb in $$(find . -name "ros-$(ROS_DISTRO)-*-slam-sse_*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*"); do \
		echo "Installing $$deb"; \
		if dpkg -i "$$deb" 2>/dev/null; then \
			echo "$$deb installed successfully"; \
		else \
			echo "dpkg failed for $$deb, fixing dependencies"; \
		fi; \
	done; \
	apt-get install -f -y --allow-downgrades
	@# Install tracker-sse packages
	@for deb in $$(find . -name "ros-$(ROS_DISTRO)-*-tracker-sse_*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*"); do \
		echo "Installing $$deb"; \
		if dpkg -i "$$deb" 2>/dev/null; then \
			echo "$$deb installed successfully"; \
		else \
			echo "dpkg failed for $$deb, fixing dependencies"; \
		fi; \
	done; \
	apt-get install -f -y --allow-downgrades
	@# Install tracker-smoke-test packages
	@for deb in $$(find . -name "ros-$(ROS_DISTRO)-*-tracker-smoke-test_*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*"); do \
		echo "Installing $$deb"; \
		if dpkg -i "$$deb" 2>/dev/null; then \
			echo "$$deb installed successfully"; \
		else \
			echo "dpkg failed for $$deb, fixing dependencies"; \
		fi; \
	done; \
	apt-get install -f -y --allow-downgrades
	$(if $(filter humble,$(ROS_DISTRO)),python3 -m pip install --upgrade pip &&) \
	pip3 install pytest $(if $(filter humble,$(ROS_DISTRO)),-U,--break-system-packages)
	. /opt/ros/$(ROS_DISTRO)/setup.sh && pytest tests/ -s -v --tb=short --capture=no > cslam_smoke_test_$(ROS_DISTRO).log 2>&1
