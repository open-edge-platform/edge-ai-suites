#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e

tc_error() { echo -e "\033[0;31m[ERROR]\033[0m TC installation not found"; exit 1; }
cleanup() { docker rm -f tc-nginx &>/dev/null 2>&1 || true; }

trap 'cleanup' EXIT

[ -f "/usr/bin/containerd-shim-kata-v2" ] || tc_error
[ -d "/opt/kata" ] || tc_error
[ -f "/etc/kata-containers/configuration.toml" ] || tc_error

docker rm -f tc-nginx &>/dev/null 2>&1 || true
docker run -d --name tc-nginx --runtime io.containerd.kata.v2 nginx:1.27.0 &>/dev/null || tc_error

sleep 3
# Verify containerd-shim-kata-v2 is running for this container
sandbox_id=$(docker inspect tc-nginx --format='{{.Id}}' 2>/dev/null)
ps aux | grep "containerd-shim-kata-v2" | grep -v grep | grep -q "$sandbox_id" || tc_error
cleanup
