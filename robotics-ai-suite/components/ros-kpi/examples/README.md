<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# ROS2 KPI Monitoring Stack - Examples

This directory contains practical examples for using the monitoring stack.

## Available Examples

### [Quick Performance Check](quick_check.md)
30-second quick check to verify system health.
- **Use when**: You want a fast overview
- **Duration**: 30 seconds
- **Output**: Basic performance metrics

### [Monitor Specific Node](monitor_specific_node.md)
Detailed monitoring of a single ROS2 node.
- **Use when**: Analyzing a particular node's performance
- **Duration**: Flexible (until you stop it)
- **Output**: Detailed timing and resource data

### [Debug Performance Issue](debug_performance.md)
Step-by-step guide to debug performance problems.
- **Use when**: Something is slow and you need to find out why
- **Duration**: As long as needed to reproduce the issue
- **Output**: Comprehensive analysis data

## Quick Reference

```bash
# Quick check (fastest)
make quick-check

# Monitor specific node
make monitor NODE=/your_node

# Debug with a named session
uv run python src/monitor_stack.py --node /your_node --session debug_test

# List all previous monitoring sessions
make list-sessions
```

## Creating Custom Examples

Feel free to add your own examples! Each example should:
1. Have a clear use case
2. Include step-by-step instructions
3. Explain expected output
4. Provide analysis guidance

## Need Help?

- See [QUICK_START.md](../docs/QUICK_START.md) for basic usage
- See [COMMANDS.md](../docs/COMMANDS.md) for all commands
- See [README.md](../README.md) for full documentation
