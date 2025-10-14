#!/bin/bash

for file in logs/run_dls_*.log; do
    echo "Processing $file"
    grep tracer_pipeline "$file" | awk '{ print $12 } ' > "${file%.log}_latency.txt"
    echo "Latency data saved to ${file%.log}_latency.txt"
    grep FpsCounter "$file" > "${file%.log}_fps.txt"
    echo "FPS data saved to ${file%.log}_fps.txt"
done
