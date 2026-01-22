FROM eclipse-temurin:17

# Application directory inside the container
WORKDIR /opt/dds-bridge

# Copy the built application JAR
# Ensure `./gradlew clean build` has been run so build/libs/dds-bridge-1.0.jar exists.
COPY build/libs/dds-bridge-1.0.jar /opt/dds-bridge/dds-bridge-1.0.jar

# Copy Gradle distribution to bring in all runtime dependencies (including gRPC jars)
# Ensure the distribution archive build/distributions/dds-bridge-1.0.tar exists (created by the application plugin).
COPY build/distributions/dds-bridge-1.0.tar /tmp/dds-bridge-1.0.tar

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
