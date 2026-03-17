# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv==0.9.22

COPY . .

# Create virtual environment and install dependencies using uv
RUN uv sync && uv pip install -r ui/requirements.txt

# Copy license file
COPY third_party_programs.txt /licenses/third_party_programs.txt

# Optionally download copyleft sources if requested
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        apt-get update && \
        # Get list of installed deb packages with copyleft licenses \
        sed -Ei 's/# deb-src /deb-src /' /etc/apt/sources.list && \
        apt-get update && \
        mkdir -p /copyleft_sources/deb && cd /copyleft_sources/deb && \
        echo -n $null > copyleft_package_list.txt && \
        for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
            grep -l 'Copyleft\|GPL\|LGPL\|EPL\|MPL\|CDDL' /usr/share/doc/${package}/copyright; \
            exit_status=$?; \
            if [ $exit_status -eq 0 ]; then \
                echo $package >> copyleft_package_list.txt; \
                apt-get source -q --download-only $package; \
            fi; \
        done; \
        # Get source code for installed Python packages with copyleft licenses \
        mkdir -p /copyleft_sources/python && \
        cd /copyleft_sources/python && \
        apt-get update && apt-get install -y --no-install-recommends gcc build-essential libffi-dev python3-dev && \
        # Download python package sources with relevant licenses \
        pip3 freeze | cut -d= -f1 | while read pkg; do \
            meta=$(pip3 show $pkg 2>/dev/null); \
            lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
            if [ ! -z "$lic" ]; then \
                echo "Downloading source for $pkg with license: $lic"; \
                pip3 download --no-binary :all: $pkg || true; \
            fi; \
        done; \
        apt-get remove --purge -y gcc build-essential libffi-dev python3-dev; \
    fi

# Create non-root user and adjust permissions
RUN useradd -m -u 1000 traffic && \
    chmod +x docker-entrypoint.sh && \
    chown -R traffic:traffic /app

# Switch to non-root user
USER traffic

# Update PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Expose API port and UI port
EXPOSE 8081 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8081/health || exit 1

# Run both API and UI services using entrypoint script
CMD ["bash", "docker-entrypoint.sh"]
