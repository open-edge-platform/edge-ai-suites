set -e

IMAGE_TAG=${1-intel/vppsample:2025.2.0}
DOCKERFILE=${2-Dockerfile.sample}

docker build \
    --network=host \
    --build-arg http_proxy=$http_proxy \
    --build-arg https_proxy=$https_proxy \
    -t $IMAGE_TAG \
    -f $DOCKERFILE ..
