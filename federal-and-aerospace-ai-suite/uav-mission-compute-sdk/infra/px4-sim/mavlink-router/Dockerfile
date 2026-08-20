# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential pkg-config \
    libssl-dev meson ninja-build python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/mavlink-router/mavlink-router.git /src \
    && cd /src \
    && git submodule update --init --recursive \
    && meson setup build . -Dsystemdsystemunitdir=/usr/lib/systemd/system \
    && ninja -C build \
    && ninja -C build install \
    && rm -rf /src

ENV http_proxy= https_proxy= no_proxy=

COPY main.conf /etc/mavlink-router/main.conf

CMD ["mavlink-routerd", "-c", "/etc/mavlink-router/main.conf"]
