############################
# Stage 1: Build MDPnP
############################
FROM gradle:7.6-jdk17 AS builder

USER root

ARG HTTP_PROXY
ARG HTTPS_PROXY

# Install C toolchain so rtiddsgen can find the C preprocessor (cpp)
RUN apt-get update \
    && apt-get install -y --no-install-recommends cpp build-essential \
    && rm -rf /var/lib/apt/lists/*

# Configure Gradle proxy
RUN mkdir -p /home/gradle/.gradle && \
    echo "systemProp.http.proxyHost=$(echo $HTTP_PROXY | sed -e 's|http://||' -e 's|:.*||')" >> /home/gradle/.gradle/gradle.properties && \
    echo "systemProp.http.proxyPort=$(echo $HTTP_PROXY | sed -e 's|.*:||')" >> /home/gradle/.gradle/gradle.properties && \
    echo "systemProp.https.proxyHost=$(echo $HTTPS_PROXY | sed -e 's|http://||' -e 's|:.*||')" >> /home/gradle/.gradle/gradle.properties && \
    echo "systemProp.https.proxyPort=$(echo $HTTPS_PROXY | sed -e 's|.*:||')" >> /home/gradle/.gradle/gradle.properties

WORKDIR /build

COPY mdpnp /build/mdpnp

RUN chown -R gradle:gradle /build

USER gradle

WORKDIR /build/mdpnp

RUN gradle --no-daemon --info :interop-lab:demo-apps:makeFlatRuntime

############################
# Stage 2: Runtime Image
############################
FROM eclipse-temurin:17-jre

WORKDIR /opt/mdpnp

# Copy only generated flat runtime from builder stage
COPY --from=builder /build/mdpnp/interop-lab/demo-apps/flat /opt/mdpnp/flat

# Runtime environment variables
ENV LD_LIBRARY_PATH=/opt/mdpnp/flat
ENV RTI_LICENSE_FILE=/opt/mdpnp/flat/OpenICE_license.dat

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /opt/mdpnp/flat

ENTRYPOINT ["/entrypoint.sh"]