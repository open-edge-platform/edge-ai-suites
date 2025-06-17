CONTAINER_IDS=$(docker ps -a --filter "ancestor=dataprep-visualdata-milvus" -q)

# Check if any containers were found
if [ -z "$CONTAINER_IDS" ]; then
  echo "No containers found"
  exit 0
fi

CONTAINER_IDS=($CONTAINER_IDS)
NUM_CONTAINERS=${#CONTAINER_IDS[@]}

docker exec -it ${CONTAINER_IDS[0]} bash -c "python example/example_utils.py -d DAVIS"
exit 0
