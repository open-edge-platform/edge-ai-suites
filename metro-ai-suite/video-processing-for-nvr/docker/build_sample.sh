set -e

IMAGE_TAG=${1-vppsample:latest}
DOCKERFILE=${2-Dockerfile.sample}

cd ..
sudo apt download intel-vppsdk
cd docker

docker build \
    --network=host \
    --build-arg http_proxy=$http_proxy \
    --build-arg https_proxy=$https_proxy \
    -t $IMAGE_TAG \
    -f $DOCKERFILE ..
