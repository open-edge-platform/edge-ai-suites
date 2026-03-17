#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.

echo "Starting AMR simulation..."

# Start the motion program in its own process group so all children can be killed together
setsid nohup ros2 launch picknplace warehouse.launch.py > picknplace_launch.log 2>&1 &
MOTION_PID=$!
echo "PicknPlace PID: $MOTION_PID"

# Allow simulation to stabilize
sleep 20

# Auto-press the Gazebo play button
echo "Pressing play button in GZ"
gz service -s /world/default/control \
  --reqtype gz.msgs.WorldControl \
  --reptype gz.msgs.Boolean \
  --req 'pause: false' \
  --timeout 2000

echo "Starting performance measurement..."

# Start measurement program (no duration — runs until signalled)
nohup uv run python src/monitor_stack.py --gpu --algorithm picknplace > monitor_gpu.log 2>&1 &
MONITOR_PID=$!

# Wait until demo reports completion instead of fixed sleep
echo "Waiting for AMR demo to complete..."
timeout 360 bash -c \
  'tail -f picknplace_launch.log | grep -q "AMR DEMO COMPLETE"'

# Check if we timed out or demo completed
if [ $? -eq 0 ]; then
  echo "AMR demo completed successfully."
else
  echo "WARNING: Timed out waiting for AMR demo to complete."
fi

echo "Stopping monitor..."
kill -SIGINT $MONITOR_PID
wait $MONITOR_PID

echo "Stopping PicknPlace node with Ctrl-C..."

# Kill the entire process group (ros2 launch + all spawned nodes + Gazebo)
kill -SIGINT -$MOTION_PID 2>/dev/null || true
sleep 3
# Force-kill anything still running in the group
kill -SIGKILL -$MOTION_PID 2>/dev/null || true

# Wait for processes to exit
wait $MOTION_PID 2>/dev/null
wait $MONITOR_PID

# Report monitor results
SESSION_PATH=$(grep "Session complete" monitor_gpu.log | grep -oP "monitoring_sessions/\S+")
if [ -n "$SESSION_PATH" ]; then
  echo "Performance monitor finished. Results saved to: $SESSION_PATH"
else
  echo "Performance monitor finished."
fi

echo "Experiment finished."
