############################
# Stage 1: Builder
############################
FROM eclipse-temurin:17-jdk AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

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

# Copy Gradle wrapper first (for caching)
COPY gradlew settings.gradle.kts build.gradle ./
COPY gradle ./gradle

RUN chmod +x gradlew

# Warm up Gradle wrapper + dependencies (prevents timeout later)
RUN ./gradlew --no-daemon dependencies || true

# Copy full source
COPY src ./src
COPY libs ./libs
COPY native ./native

# Optional RTI setup (if required)
ENV RTI_DDS_HOME=/opt/rtidds
RUN mkdir -p "$RTI_DDS_HOME/lib/java" && \
    cp libs/*.jar "$RTI_DDS_HOME/lib/java/" || true

# Build
RUN ./gradlew --no-daemon clean build


############################
# Stage 2: Runtime
############################
FROM eclipse-temurin:17-jre

# Create non-root user
RUN useradd -m ddsuser

WORKDIR /opt/dds-bridge

# Copy artifacts
COPY --from=builder /workspace/build/libs/dds-bridge-1.0.jar ./dds-bridge.jar
COPY --from=builder /workspace/build/distributions/dds-bridge-1.0.tar /tmp/app.tar

# Extract distribution
RUN mkdir -p /opt/dds-bridge/dist && \
    tar -xf /tmp/app.tar -C /opt/dds-bridge/dist --strip-components=1 && \
    rm /tmp/app.tar

# Copy runtime dependencies
COPY libs ./libs
COPY native ./native

ENV LD_LIBRARY_PATH=/opt/dds-bridge/native/libs/linux
ENV RTI_LICENSE_FILE=/opt/dds-bridge/libs/OpenICE_license.dat

USER ddsuser

ENTRYPOINT ["java", \
  "-Djava.library.path=/opt/dds-bridge/native/libs/linux", \
  "-cp", "/opt/dds-bridge/dds-bridge.jar:/opt/dds-bridge/libs/*:/opt/dds-bridge/dist/lib/*", \
  "org.intel.MdPnpEventConsumer"]