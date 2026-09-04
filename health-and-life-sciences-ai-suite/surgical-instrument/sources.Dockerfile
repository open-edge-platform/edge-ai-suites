# GPL source-redistribution image for the Surgical Instrument (endoscopy) app.
#
# Builds an image that contains the upstream source tarballs for every
# GPL-licensed Debian package present in the runtime image, satisfying the
# GPL "offer of source" obligation for redistribution (OSPDT).
#
# Build:
#   docker build -f sources.Dockerfile -t hls-si-endoscopy-sources:latest \
#     --build-arg TAG=<runtime-image-tag> .
# Inspect:
#   docker run --rm hls-si-endoscopy-sources:latest        # `tree sources`

ARG REGISTRY_URL=intel/
ARG TAG=2026.2.0-rc2

# -------- Stage 1: Download GPL Sources --------
FROM ${REGISTRY_URL}hls-si-endoscopy:${TAG} AS source-builder
LABEL stage="source-builder"

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    dpkg-dev ca-certificates

COPY ./thirdparty/third_party_deb_deps.txt /thirdparty/

# Enable deb-src repositories (handles both traditional and DEB822 formats)
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -Ei 's/^# deb-src /deb-src /' /etc/apt/sources.list; \
    fi && \
    if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
        sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources; \
    fi && \
    apt-get update && \
    mkdir -p /sources && cd /sources && \
    for package in $(cat /thirdparty/third_party_deb_deps.txt | xargs -n1); do \
        grep -l GPL /usr/share/doc/${package}/copyright; \
        exit_status=$?; \
        if [ $exit_status -eq 0 ]; then \
            apt-get source -q --download-only $package; \
        fi \
    done

# -------- Final Stage --------
FROM ${REGISTRY_URL}hls-si-endoscopy:${TAG} AS final

LABEL description="Source redistribution image for GPL-licensed packages in intel/hls-si-endoscopy"

USER root

# Create non-root user
RUN useradd -ms /bin/bash sourceuser || true

# Install tools and adjust permissions
RUN apt-get update && apt-get install --no-install-recommends -y tree && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /opt/sources && chown -R sourceuser:sourceuser /opt/sources

# Copy downloaded sources from builder
COPY --from=source-builder /sources /opt/sources

# Copy version manifest for reference
COPY ./thirdparty/third_party_deb_deps_versions.txt /opt/sources/

# Fix ownership post-copy
RUN chown -R sourceuser:sourceuser /opt/sources

USER sourceuser

WORKDIR /opt
CMD ["tree", "sources"]
