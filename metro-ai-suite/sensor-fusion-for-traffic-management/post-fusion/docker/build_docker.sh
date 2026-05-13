set -e

IMAGE_TAG=${1-tfcc:latest}
DOCKERFILE=${2-Dockerfile_TFCC.dockerfile}
BASE=${3-ubuntu}
BASE_VERSION=${4-24.04}

docker build \
    --network=host \
    --build-arg http_proxy=$http_proxy \
    --build-arg https_proxy=$https_proxy \
    --build-arg BASE=$BASE \
    --build-arg BASE_VERSION=$BASE_VERSION \
    -t $IMAGE_TAG \
    -f $DOCKERFILE ..
