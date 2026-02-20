############################
# Stage 1: Builder
############################
FROM eclipse-temurin:17-jdk AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /workspace

# Copy Gradle wrapper & config first (cache optimization)
COPY gradlew settings.gradle.kts build.gradle gradle.properties ./
COPY gradle ./gradle

RUN chmod +x gradlew

# Download dependencies first
RUN ./gradlew --no-daemon dependencies || true

# Copy full source
COPY src ./src
COPY libs ./libs
COPY native ./native

# Setup RTI_DDS_HOME (if required by build)
ENV RTI_DDS_HOME=/opt/rtidds
RUN mkdir -p "$RTI_DDS_HOME/lib/java" \
    && cp libs/*.jar "$RTI_DDS_HOME/lib/java/" || true

# Build
RUN ./gradlew clean build --no-daemon


############################
# Stage 2: Runtime
############################
FROM eclipse-temurin:17-jre

# Create non-root user
RUN useradd -m ddsuser

WORKDIR /opt/dds-bridge

# Copy only required runtime artifacts
COPY --from=builder /workspace/build/libs/dds-bridge-1.0.jar ./dds-bridge.jar
COPY --from=builder /workspace/build/distributions/dds-bridge-1.0.tar /tmp/app.tar

# Extract distribution
RUN mkdir -p /opt/dds-bridge/dist \
    && tar -xf /tmp/app.tar -C /opt/dds-bridge/dist --strip-components=1 \
    && rm /tmp/app.tar

COPY libs ./libs
COPY native ./native

ENV LD_LIBRARY_PATH=/opt/dds-bridge/native/libs/linux
ENV RTI_LICENSE_FILE=/opt/dds-bridge/libs/OpenICE_license.dat

USER ddsuser

ENTRYPOINT ["java", "-Djava.library.path=/opt/dds-bridge/native/libs/linux", \
            "-cp", "/opt/dds-bridge/dds-bridge.jar:/opt/dds-bridge/libs/*:/opt/dds-bridge/dist/lib/*", \
            "org.intel.MdPnpEventConsumer"]
