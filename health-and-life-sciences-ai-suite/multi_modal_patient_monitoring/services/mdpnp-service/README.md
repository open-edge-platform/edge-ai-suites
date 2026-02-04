# mdpnp-service


## Build the application
./gradlew :interop-lab:demo-apps:makeFlatRuntime


## Build the Dockerfile
docker build -t ai-hl-mdpnp-service .


## Run Container
docker run --rm ai-hl-mdpnp-service