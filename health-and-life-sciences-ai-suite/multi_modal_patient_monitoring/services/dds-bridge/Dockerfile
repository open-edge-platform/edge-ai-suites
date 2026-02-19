##########
# Builder stage
##########

FROM eclipse-temurin:17 AS builder

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /workspace

# Copy Gradle wrapper and build configuration
COPY gradlew settings.gradle.kts build.gradle gradle.properties ./
COPY gradle ./gradle

# Copy source, local libs, and native artifacts needed for compilation
COPY src ./src
COPY libs ./libs
COPY native ./native

RUN chmod +x gradlew

# Some builds expect RTI_DDS_HOME to resolve additional JARs.
# For container builds, point it at a local path that reuses the project libs.
ENV RTI_DDS_HOME=/opt/rtidds
RUN mkdir -p "$RTI_DDS_HOME/lib/java" \
    && cp libs/*.jar "$RTI_DDS_HOME/lib/java/" || true

# Build the application (including distribution archive)
RUN ./gradlew clean build --no-daemon


##########
# Runtime stage
##########

FROM eclipse-temurin:17

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Application directory inside the container
WORKDIR /opt/dds-bridge

# Copy the built artifacts from the builder stage
COPY --from=builder /workspace/build/libs/dds-bridge-1.0.jar /opt/dds-bridge/dds-bridge-1.0.jar
COPY --from=builder /workspace/build/distributions/dds-bridge-1.0.tar /tmp/dds-bridge-1.0.tar

# Extract distribution under /opt/dds-bridge/dist so we can use its lib/ on the classpath
RUN mkdir -p /opt/dds-bridge/dist \
	&& tar -xf /tmp/dds-bridge-1.0.tar -C /opt/dds-bridge/dist --strip-components=1 \
	&& rm /tmp/dds-bridge-1.0.tar

# Copy project-local libs (license file and MDPnP jars)
COPY libs /opt/dds-bridge/libs

# Copy native DDS libraries
COPY native /opt/dds-bridge/native

# Native library and RTI license configuration
ENV LD_LIBRARY_PATH=/opt/dds-bridge/native/libs/linux
ENV RTI_LICENSE_FILE=/opt/dds-bridge/libs/OpenICE_license.dat

# Run the application directly from the JAR using all dependencies on the classpath
ENTRYPOINT ["java", "-Djava.library.path=/opt/dds-bridge/native/libs/linux", "-cp", "/opt/dds-bridge/dds-bridge-1.0.jar:/opt/dds-bridge/libs/*:/opt/dds-bridge/dist/lib/*", "org.intel.MdPnpEventConsumer"]
