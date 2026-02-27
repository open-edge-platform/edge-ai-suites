# mdpnp-service


## Build the application (optional local build)

If you have the MD PnP OpenICE repository checked out locally, you can
build the flat runtime yourself for development:

```bash
cd mdpnp
./gradlew :interop-lab:demo-apps:makeFlatRuntime
```

## Build the Docker image (multi-stage)

The recommended way for this suite is to build the image using the
multi-stage Dockerfile, which runs the Gradle `makeFlatRuntime` task
inside the builder stage.

Make sure the MD PnP source tree is available under the `mdpnp/`
directory in this service folder (for example via a Git submodule or
copy of the upstream repo).

```bash
docker build -t ai-hl-mdpnp-service .
```

This will:
- Use a Gradle 7.6 + JDK 17 builder stage to run
	`gradle :interop-lab:demo-apps:makeFlatRuntime --no-daemon` inside
	the container.
- Copy the generated `flat/` runtime into a lean Eclipse Temurin 17
	Runtime image.

## Run Container

```bash
docker run --rm ai-hl-mdpnp-service
```