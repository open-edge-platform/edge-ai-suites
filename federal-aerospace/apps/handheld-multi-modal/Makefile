# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# handheld-multi-modal packaging logic.
#
# Owns the sparse-checkout of the vippet tool from edge-ai-libraries.
# The parent (federal-aerospace/Makefile) delegates to this Makefile and
# wraps the staged tree into a ZIP.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Directory of this Makefile.
SELF_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# --- Configuration -----------------------------------------------------------

# Where to stage the resolved tree (REQUIRED for `stage`).
# Must be passed as an absolute path by the caller.
STAGE_DIR ?=

# Scratch space for the vippet source checkout.
WORK_DIR  ?= $(SELF_DIR)/.work

# vippet pin — single source of truth lives next to this Makefile.
VIPPET_REPO ?= https://github.com/open-edge-platform/edge-ai-libraries.git
VIPPET_REF  ?= $(strip $(file < $(SELF_DIR)/VIPPET_REF))
VIPPET_PATH ?= tools/visual-pipeline-and-platform-evaluation-tool

TEMPLATE_DIR := $(SELF_DIR)/templates

.PHONY: stage vippet clean help

help: ## Show this help
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

stage: ## Stage the handheld-multi-modal tree at $(STAGE_DIR)
	@if [[ -z "$(STAGE_DIR)" ]]; then echo "error: STAGE_DIR is required" >&2; exit 2; fi
	@echo ">> Staging handheld-multi-modal at $(STAGE_DIR)"
	@rm -rf "$(STAGE_DIR)"
	@mkdir -p "$(STAGE_DIR)/handheld-multi-modal"
	rsync -a --exclude='templates' --exclude='VIPPET_REF' --exclude='Makefile' --exclude='.work' \
		"$(SELF_DIR)/" "$(STAGE_DIR)/handheld-multi-modal/"
	cp "$(TEMPLATE_DIR)/README.md" "$(STAGE_DIR)/README.md"
	install -m 0755 "$(TEMPLATE_DIR)/run.sh" "$(STAGE_DIR)/run.sh"
	$(MAKE) --no-print-directory vippet VIPPET_DEST="$(STAGE_DIR)/vippet"

vippet: ## Sparse-checkout the vippet tool into $(VIPPET_DEST)
	@if [[ -z "$(VIPPET_DEST)" ]]; then echo "error: VIPPET_DEST is required" >&2; exit 2; fi
	@echo ">> Sparse-checking out vippet @ $(VIPPET_REF) (docs excluded)"
	@rm -rf "$(WORK_DIR)/vippet_src"
	git clone --filter=blob:none --no-checkout --depth 1 \
		--branch "$(VIPPET_REF)" "$(VIPPET_REPO)" "$(WORK_DIR)/vippet_src"
	cd "$(WORK_DIR)/vippet_src" && \
		git sparse-checkout init --no-cone && \
		printf '$(VIPPET_PATH)/**\n!$(VIPPET_PATH)/docs/**\n' | \
			git sparse-checkout set --stdin && \
		git checkout
	@rm -rf "$(VIPPET_DEST)"
	@mkdir -p "$(VIPPET_DEST)"
	cp -a "$(WORK_DIR)/vippet_src/$(VIPPET_PATH)/." "$(VIPPET_DEST)/"
	@echo "$(VIPPET_REF)" > "$(VIPPET_DEST)/.vippet-ref"
	@rm -rf "$(VIPPET_DEST)"
	@mkdir -p "$(VIPPET_DEST)"
	cp -a "$(WORK_DIR)/vippet_src/$(VIPPET_PATH)/." "$(VIPPET_DEST)/"
	@echo "$(VIPPET_REF)" > "$(VIPPET_DEST)/.vippet-ref"

clean: ## Remove this app's scratch directory
	rm -rf "$(WORK_DIR)"
