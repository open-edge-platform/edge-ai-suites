# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

SHELL := /bin/bash

CHILD_CHART_DIR := ../../live-video-captioning/charts
PARENT_CHART_DIR := .
VALUES_FILE ?= ./values-override.yaml
RELEASE ?= live-video-captioning-rag
NAMESPACE ?=
HELM ?= helm

HELM_NAMESPACE_ARGS :=
HELM_INSTALL_NAMESPACE_ARGS :=
ifneq ($(strip $(NAMESPACE)),)
HELM_NAMESPACE_ARGS += --namespace $(NAMESPACE)
HELM_INSTALL_NAMESPACE_ARGS += --namespace $(NAMESPACE)
endif

.PHONY: help deps deps-child deps-parent deploy uninstall template lint

help:
	@echo "Targets:"
	@echo "  make deps       Build chart dependencies in correct order"
	@echo "  make deploy     Build deps and helm upgrade --install"
	@echo "  make uninstall  Uninstall release"
	@echo "  make template   Render manifests locally"
	@echo "  make lint       Lint parent chart"
	@echo ""
	@echo "Variables (override with VAR=value):"
	@echo "  RELEASE=$(RELEASE)"
	@echo "  NAMESPACE=$(NAMESPACE) (empty = use kube context namespace)"
	@echo "  VALUES_FILE=$(VALUES_FILE)"
	@echo "  HELM=$(HELM)"

deps: deps-child deps-parent

deps-child:
	$(HELM) dependency build $(CHILD_CHART_DIR)

deps-parent:
	$(HELM) dependency build $(PARENT_CHART_DIR)

deploy: deps
	$(HELM) upgrade --install $(RELEASE) $(PARENT_CHART_DIR) \
		$(HELM_INSTALL_NAMESPACE_ARGS) \
		-f $(VALUES_FILE)

uninstall:
	$(HELM) uninstall $(RELEASE) $(HELM_NAMESPACE_ARGS)

template: deps
	$(HELM) template $(RELEASE) $(PARENT_CHART_DIR) -f $(VALUES_FILE)

lint: deps
	$(HELM) lint $(PARENT_CHART_DIR)
