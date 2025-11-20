CONTAINER_IDS=$(docker ps -a --filter "status=running" -q | xargs -r docker inspect --format '{{.Config.Image}} {{.Id}}' | grep "dataprep-visualdata-milvus" | awk '{print $2}')

# Check if any containers were found
if [ -z "$CONTAINER_IDS" ]; then
  echo "No containers found"
  exit 0
fi

CONTAINER_IDS=($CONTAINER_IDS)
NUM_CONTAINERS=${#CONTAINER_IDS[@]}

docker exec -it ${CONTAINER_IDS[0]} bash -c "python example/example_utils.py -d DAVIS"
exit 0