set -e

IMAGE_TAG=${1-vppsample:latest}
DOCKERFILE=${2-Dockerfile.sample}
BASE=${3-vppsdk}
BASE_VERSION=${4-latest}

docker build \
    --network=host \
    --build-arg http_proxy=$http_proxy \
    --build-arg https_proxy=$https_proxy \
    --build-arg BASE=$BASE \
    --build-arg BASE_VERSION=$BASE_VERSION \
    -t $IMAGE_TAG \
    -f $DOCKERFILE ..
