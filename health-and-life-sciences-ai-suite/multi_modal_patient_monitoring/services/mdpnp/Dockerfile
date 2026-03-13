############################
# Stage 1: Builder
############################
FROM eclipse-temurin:17-jdk AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Install required native tools (rtiddsgen requires cpp)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cpp \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Configure Gradle proxy (only if provided)
RUN mkdir -p /root/.gradle && \
    if [ -n "$HTTP_PROXY" ]; then \
      echo "systemProp.http.proxyHost=$(echo $HTTP_PROXY | sed -e 's|http://||' -e 's|:.*||')" >> /root/.gradle/gradle.properties && \
      echo "systemProp.http.proxyPort=$(echo $HTTP_PROXY | sed -e 's|.*:||')" >> /root/.gradle/gradle.properties ; \
    fi && \
    if [ -n "$HTTPS_PROXY" ]; then \
      echo "systemProp.https.proxyHost=$(echo $HTTPS_PROXY | sed -e 's|http://||' -e 's|:.*||')" >> /root/.gradle/gradle.properties && \
      echo "systemProp.https.proxyPort=$(echo $HTTPS_PROXY | sed -e 's|.*:||')" >> /root/.gradle/gradle.properties ; \
    fi


WORKDIR /workspace

# Copy Gradle wrapper first (better layer caching)
COPY mdpnp/gradlew mdpnp/settings.gradle* mdpnp/build.gradle* mdpnp/gradle.properties ./mdpnp/
COPY mdpnp/gradle ./mdpnp/gradle

WORKDIR /workspace/mdpnp
RUN chmod +x gradlew

# Download dependencies first (cache-friendly)
RUN ./gradlew --no-daemon dependencies || true

# Now copy full source
COPY mdpnp /workspace/mdpnp

# Build flat runtime
RUN ./gradlew --no-daemon --info :interop-lab:demo-apps:makeFlatRuntime


############################
# Stage 2: Runtime
############################
FROM eclipse-temurin:17-jre

# Create non-root user
RUN useradd -m mdpnpuser

WORKDIR /opt/mdpnp

# Copy built flat runtime
COPY --from=builder /workspace/mdpnp/interop-lab/demo-apps/flat ./flat

ENV LD_LIBRARY_PATH=/opt/mdpnp/flat
ENV RTI_LICENSE_FILE=/opt/mdpnp/flat/OpenICE_license.dat

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root
USER mdpnpuser

WORKDIR /opt/mdpnp/flat

ENTRYPOINT ["/entrypoint.sh"]