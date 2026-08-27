# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Federal Aerospace packaging — orchestration only.
#
# Component-specific staging logic lives in each component's own Makefile.
# This Makefile is the single source of truth for local and CI builds.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := all

# --- Configuration -----------------------------------------------------------

DIST_DIR  ?= dist
BUILD_DIR ?= build
ROOT      := $(abspath .)

# Source directories for each packaged component.
HANDHELD_SRC := handheld-multi-modal
DTD_SRC      := deterministic-threat-detection
UAVSDK_SRC   := uav-mission-compute-sdk
UAVVA_SRC    := uav-vision-analytics

# Output archives.
HANDHELD_ZIP := $(DIST_DIR)/handheld-multi-modal.zip
DTD_ZIP      := $(DIST_DIR)/deterministic-threat-detection.zip
UAV_ZIP      := $(DIST_DIR)/uav-mission-apps.zip
SOLUTION_ZIP := $(DIST_DIR)/federal-and-aerospace-ai-suite.zip

# Forwarded to sub-Makefiles when overridden on the command line.
override_vars := $(foreach v,VIPPET_REPO VIPPET_REF VIPPET_PATH,\
	$(if $(filter command,$(origin $(v))),$(v)='$($(v))'))

# --- Public targets ----------------------------------------------------------

.PHONY: all
all: handheld-multi-modal deterministic-threat-detection uav-mission-apps federal-and-aerospace-ai-suite ## Build every component ZIP

.PHONY: handheld-multi-modal
handheld-multi-modal: $(HANDHELD_ZIP) ## Build handheld-multi-modal.zip (includes vippet)

.PHONY: deterministic-threat-detection
deterministic-threat-detection: $(DTD_ZIP) ## Build deterministic-threat-detection.zip

.PHONY: uav-mission-apps
uav-mission-apps: $(UAV_ZIP) ## Build uav-mission-apps.zip (uav-mission-compute-sdk + uav-vision-analytics)

.PHONY: federal-and-aerospace-ai-suite
federal-and-aerospace-ai-suite: $(SOLUTION_ZIP) ## Build federal-and-aerospace-ai-suite.zip with the entire solution

.PHONY: clean
clean: ## Remove build and dist directories
	rm -rf "$(BUILD_DIR)" "$(DIST_DIR)"
	$(MAKE) --no-print-directory -C $(HANDHELD_SRC) clean

.PHONY: help
help: ## Show this help
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-32s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- handheld-multi-modal — delegate to the app's Makefile -------------------

HANDHELD_STAGE := $(BUILD_DIR)/handheld-multi-modal
HANDHELD_STAMP := $(BUILD_DIR)/.handheld.stamp

$(HANDHELD_ZIP): $(HANDHELD_STAMP)
	@mkdir -p "$(DIST_DIR)"
	@rm -f "$@"
	cd "$(BUILD_DIR)" && zip -rq "$(abspath $@)" handheld-multi-modal
	@echo "Archive ready: $@"

$(HANDHELD_STAMP): $(shell find $(HANDHELD_SRC) -type f 2>/dev/null)
	$(MAKE) --no-print-directory -C $(HANDHELD_SRC) stage \
		STAGE_DIR="$(ROOT)/$(HANDHELD_STAGE)" $(override_vars)
	@mkdir -p "$(dir $@)"
	touch "$@"

# --- Simple component ZIPs (just zip the source directory) -------------------

$(DTD_ZIP): $(shell find $(DTD_SRC) -type f 2>/dev/null)
	@mkdir -p "$(DIST_DIR)"
	@rm -f "$@"
	zip -rq "$@" "$(DTD_SRC)"
	@echo "Archive ready: $@"

$(UAV_ZIP): $(shell find $(UAVSDK_SRC) $(UAVVA_SRC) -type f 2>/dev/null)
	@mkdir -p "$(DIST_DIR)"
	@rm -f "$@"
	zip -rq "$@" "$(UAVSDK_SRC)" "$(UAVVA_SRC)"
	@echo "Archive ready: $@"

# --- Full solution ZIP -------------------------------------------------------
#
# Bundles the entire federal-and-aerospace-ai-suite tree, with handheld-multi-modal already
# resolved (i.e. with its vippet sparse checkout dropped in).

SOLUTION_STAGE := $(BUILD_DIR)/federal-and-aerospace-ai-suite

$(SOLUTION_ZIP): $(HANDHELD_STAMP) \
		$(shell find $(DTD_SRC) $(UAVSDK_SRC) $(UAVVA_SRC) docs -type f 2>/dev/null) \
		README.md
	@echo ">> Staging federal-and-aerospace-ai-suite (full solution)"
	@rm -rf "$(SOLUTION_STAGE)"
	@mkdir -p "$(SOLUTION_STAGE)/federal-and-aerospace-ai-suite"
	rsync -a \
		--exclude='build' --exclude='dist' --exclude='.git' \
		--exclude='handheld-multi-modal/templates' \
		--exclude='handheld-multi-modal/VIPPET_REF' \
		--exclude='handheld-multi-modal/.work' \
		./ "$(SOLUTION_STAGE)/federal-and-aerospace-ai-suite/"
	cp -a "$(HANDHELD_STAGE)/vippet-fedaero" "$(SOLUTION_STAGE)/federal-and-aerospace-ai-suite/handheld-multi-modal/"
	@mkdir -p "$(DIST_DIR)"
	@rm -f "$@"
	cd "$(SOLUTION_STAGE)" && zip -rq "$(abspath $@)" federal-and-aerospace-ai-suite
	@echo "Archive ready: $@"
