CONTAINER_IDS=$(docker ps -a --filter "status=running" -q | xargs -r docker inspect --format '{{.Config.Image}} {{.Id}}' | grep "visual-search-qa-app" | awk '{print $2}')

# Check if any containers were found
if [ -z "$CONTAINER_IDS" ]; then
  echo "No containers found"
  exit 0
fi

CONTAINER_IDS=($CONTAINER_IDS)
NUM_CONTAINERS=${#CONTAINER_IDS[@]}

# download test image inside the container
docker exec -it ${CONTAINER_IDS[0]} bash -c "mkdir -p /home/user/data/sanity_tests"
docker exec -it ${CONTAINER_IDS[0]} bash -c "curl -L "http://farm6.staticflickr.com/5268/5602445367_3504763978_z.jpg" -o /home/user/data/sanity_tests/girl.jpg"

for file in sanity_tests/*.py; do
  docker cp "$file" ${CONTAINER_IDS[0]}:/home/user/visual-search-qa/src/
done

declare -a TEST_RESULTS
pass_count=0
total_count=0

for test_file in sanity_tests/test_*.py; do
  test_file_name=$(basename "$test_file")  # Remove the sanity_tests/ prefix
  echo "Running tests in $test_file_name"
  # Capture the output of the pytest command
  output=$(docker exec -it ${CONTAINER_IDS[0]} bash -c "cd /home/user/visual-search-qa/src && python -m pytest $test_file_name --tb=short")
  echo "$output"
  exit_code=$?

  total_count=$((total_count + 1))
  # Check if the output contains "failed"
  if echo "$output" | grep -q "failed"; then
    TEST_RESULTS+=("$test_file_name: FAIL")
  else
    TEST_RESULTS+=("$test_file_name: PASS")
    pass_count=$((pass_count + 1))  # Increment the pass count
  fi

done

echo "Test Results Summary:"
for result in "${TEST_RESULTS[@]}"; do
  echo "$result"
done

# Calculate the pass rate
if [ $total_count -gt 0 ]; then
  pass_rate=$(echo "scale=2; ($pass_count / $total_count) * 100" | bc)
else
  pass_rate=0
fi

echo "Pass Rate: $pass_rate%"
